"""환각 최소화 안전장치 (D15). 계획서 2단계 마지막 항목의 실체.

1. 질문 분류: 검사 회피 질문과 강요 피해 고백은 LLM을 부르지 않고 서버 고정 응답을 준다(S5 결과가 결정적).
2. 인용은 프롬프트에 넣은 청크 id만 남긴다.
3. 남은 인용이 없으면 LLM 문장을 버리고 서버 고정 문구로 바꾼다(out_of_scope 표시와 무관).
4. 전문가 안내 플래그 = LLM 판단 OR 서버 규칙(본인 상황에 대한 의료·법적 판단 질문, 확인이 필요한 판정 결과).
"""

import re
from typing import Literal

from app.schemas import ChatResponse, CheckResult, Chunk, Citation, LlmAnswer

NO_EVIDENCE = (
    "교육 자료에서 이 질문에 대한 근거를 찾지 못했어요. "
    "정확한 확인은 KADA(한국도핑방지위원회)나 팀 닥터에게 문의하세요."
)
OUT_OF_SCOPE = "반도핑 교육 자료 범위 밖의 질문이에요. 도핑 규정, 약·보충제 확인, 검사 절차에 대해 물어봐 주세요."
EVASION = (
    "검사를 피하거나 결과를 바꾸는 방법은 알려드릴 수 없어요.\n\n"
    "금지물질은 끊은 뒤에도 오랫동안 검출될 수 있고, 검사를 피하거나 방해하는 행위 자체도 도핑방지규정 위반이에요. "
    "건강에도 되돌리기 어려운 영향을 줄 수 있어요.\n\n"
    "이미 복용했거나 걱정되는 상황이라면 KADA나 팀 닥터와 먼저 상의하세요."
)
COERCION = (
    "말해줘서 고마워요. 원하지 않는 약을 권유받거나 모르게 받은 상황은 혼자 해결하지 않아도 돼요.\n\n"
    "받은 약이나 포장이 있다면 버리지 말고 보관하고, 언제 무엇을 받았는지 기록해 두세요. "
    "KADA에 상담하거나 믿을 수 있는 다른 어른(부모님, 팀 닥터 등)에게 알리세요."
)
REFUSED = "이 질문에는 답할 수 없어요. 반도핑 규정이나 건강에 관한 궁금한 점은 KADA나 팀 닥터에게 문의하세요."
UNAVAILABLE = "지금은 답변을 만들 수 없어요. 잠시 후 다시 시도하거나 KADA에 문의하세요."
NOT_PREPARED = "데모 모드에서 준비되지 않은 질문이에요. 추천 질문을 눌러 보세요."

# 검사 회피·은폐
EVASION_PATTERNS = [
    r"(검사|도핑|소변|혈액).*안\s*걸",
    r"검출\s*(안|이\s*안|되지|않)",
    r"들키",
    r"반감기.*(끊|안\s*걸)",
    r"(검사|검출).*기간\s*지나",
    r"몇\s*(주|일)\s*전에?\s*(끊|중단)",
    r"끊으면.*(안\s*걸|검사|검출)",
    r"검사.*(피하|빠져|속이)",
    r"소변.*(바꾸|대신)",
    r"대리\s*검사",
    # 단어만 있으면 교육 질문("은폐제가 뭐야?"). 행동을 묻는 형태일 때만 잡는다.
    r"(은폐|마스킹|희석).*(하려면|하는\s*법|방법|어떻게)",
    r"소변.*희석",
]
# 강요·모르게 받은 약 (§10 N-5 일부. 위기 범주 전체와 연락처는 Phase 2에서 연구진이 확정)
# 강한 신호만. "모르고 먹은 거면 괜찮아?"는 엄격책임을 묻는 교육 질문이라 넣지 않는다. "코치가 프로틴 줬는데 먹어도 돼?" 같은 일상 질문은 LLM 경로 + 전문가 배너(GIVEN_BY_STAFF).
COERCION_PATTERNS = [
    r"강요",
    r"억지로",
    r"모르게",
    r"(싫|거절|안\s*먹).*(는데|었는데).*(먹으래|시켰|줬)",
]
GIVEN_BY_STAFF = r"(코치|감독|지도자|선배|트레이너).*(먹으래|먹으라|먹였|줬는데|줬어|시켰)"
# 본인 상황에 대한 의료·법적 판단 (교육 주제인 TUE·제재·병원 일반 질문은 잡지 않음)
EXPERT_PATTERNS = [
    r"용량",
    r"몇\s*(mg|밀리|알|정)",
    r"진단",
    r"(내가|저는|제가|나는).*(먹고\s*있|복용\s*중|처방\s*받은|처방받은)",
    r"징계\s*받",
    r"소송",
]

Kind = Literal["evasion", "coercion"]


def classify(question: str) -> Kind | None:
    if any(re.search(p, question) for p in COERCION_PATTERNS):
        return "coercion"
    if any(re.search(p, question) for p in EVASION_PATTERNS):
        return "evasion"
    return None


def fixed(kind: Kind) -> ChatResponse:
    """LLM을 부르지 않는 고정 응답. 둘 다 '범위 밖'이 아니라 전문가 안내 대상이다."""
    return ChatResponse(kind="fixed", answer=EVASION if kind == "evasion" else COERCION, citations=[], refer_to_expert=True, out_of_scope=False)


def server_message(text: str) -> ChatResponse:
    """서버가 만든 안내 문구(거절, 캐시 없음, API 오류). guard를 거치지 않는다."""
    return ChatResponse(kind="server", answer=text, citations=[], refer_to_expert=False, out_of_scope=True)


def needs_expert(question: str, check: CheckResult | None) -> bool:
    if any(re.search(p, question, re.IGNORECASE) for p in EXPERT_PATTERNS) or re.search(GIVEN_BY_STAFF, question):
        return True
    return check is not None and check.status in ("PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "CONDITIONAL", "UNKNOWN")


def apply(answer: LlmAnswer, chunks: list[Chunk], question: str, check: CheckResult | None) -> ChatResponse:
    by_id = {c.id: c for c in chunks}
    cited = [by_id[i] for i in dict.fromkeys(answer.citations) if i in by_id]
    refer = answer.refer_to_expert or needs_expert(question, check)
    if not cited:
        text = OUT_OF_SCOPE if answer.out_of_scope else NO_EVIDENCE
        return ChatResponse(kind="server", answer=text, citations=[], refer_to_expert=refer, out_of_scope=True)
    citations = [Citation(chunk_id=c.id, source=c.source, title=f"{c.title} — {c.section}", url=c.url) for c in cited]
    return ChatResponse(answer=answer.answer, citations=citations, refer_to_expert=refer, out_of_scope=answer.out_of_scope)
