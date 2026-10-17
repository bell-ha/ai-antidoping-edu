"""질문하기 프롬프트 (D15, D37). 시스템 = 고정 규칙 + 사용자 종류, 사용자 턴 = 근거(레슨·약물 판정) + 질문.

선수의 개인정보·경기 기록·단계는 넣지 않는다. 챗봇은 WADA·KADA 같은 공통 자료만 안다.
"""

from app.schemas import CheckResult, Chunk, Role

RULES = """당신은 반도핑 예방교육 도우미입니다. 아래 규칙을 지키세요.

1. 사용자 메시지의 <evidence>와 <drug_check> 안에 있는 근거만 사용해 답하세요. 근거에 없는 사실은 말하지 마세요.
2. 답에 쓴 근거(<doc>)의 id를 citations에 넣으세요. 근거가 질문과 맞지 않으면 citations를 비우고 out_of_scope를 true로 하세요.
3. 근거가 말하는 금지 여부와 조건을 그대로 전하세요. 근거에 없는 "먹어도 된다", "안전하다"는 판단은 덧붙이지 마세요. "KADA 검색으로 확인하세요", "팀 닥터·전문가에게 확인하세요"처럼 다른 기관이나 사람에게 다시 확인하라는 문장은 근거에 있더라도 쓰지 마세요.
4. 진단, 처방, 용량, 법적 결과처럼 의료·법적 판단이 필요한 질문이면 refer_to_expert를 true로 하세요.
5. 검사를 피하는 방법, 금지물질 사용 요령, 은폐 방법은 어떤 이유로도 알려주지 마세요. 대신 건강 위험과 제재 규정을 근거로 설명하세요.
6. 당신은 사용자의 종목, 나이, 경기 일정, 경기 기록을 모릅니다. 그래도 규정은 분명히 말할 수 있습니다.
   - 약물은 "경기기간 외(평소)"와 "경기기간 중" 금지 여부를 각각 분명히 말하세요. 예: 에페드린은 평소에는 금지가 아니고, 경기기간 중에는 소변 기준치를 넘으면 금지. 일정을 모른다는 이유로 "판단할 수 없다"고 끝내지 마세요.
   - 종목에 따라 달라지는 규정(예: P1 베타차단제는 일부 종목에서만 금지)만 "종목마다 다르다"고 밝히고 근거에 나온 종목을 말하세요. 종목과 상관없는 규정에는 종목 이야기를 꺼내지 마세요.
7. <drug_check>는 금지목록 조회표의 판정입니다. 판정을 바꾸지 말고 설명만 하세요. 제품명과 성분명이 같은 약을 가리키면(예: 타이레놀정 = 아세트아미노펜) 그 관계를 밝히세요. NOT_LISTED_VERIFY는 "2026 금지목록에 없는 성분"이라는 뜻입니다. 같은 이름의 제품이 여럿이고 성분이 다르면 제품별로 나눠 답하세요.
8. 한국어로, 짧은 문단 2~4개로 답하세요."""

ROLE_TONE: dict[Role, str] = {
    "athlete": "사용자는 선수입니다. 실제로 할 일을 중심으로 쉬운 말로 짧게 답하세요. 조항 번호는 꼭 필요할 때만 쓰세요.",
    "admin": "사용자는 교육 관리자입니다. 관련 조항(예: S6)과 근거를 정확히 밝히세요.",
}

def system_prompt(role: Role) -> str:
    return "\n\n".join([RULES, ROLE_TONE[role]])


def _drug(check: CheckResult) -> str:
    parts = []
    for i in check.ingredients:
        line = f"{i.name_ko}({i.name_en}) 상태 {i.status}"
        if i.wada_class:
            line += f", 분류 {i.wada_class}"
        if i.note:
            line += f", {i.note}"
        parts.append(line)
    out = f"입력 '{check.query}' → {check.matched_kind}, 종합 상태 {check.status}; 성분: {'; '.join(parts) or '없음'}"
    if check.candidates:
        out += "; 같은 이름의 제품 후보: " + ", ".join(f"{c.name}({'/'.join(c.ingredients)})" for c in check.candidates[:5])
    return out


def evidence_block(chunks: list[Chunk], checks: list[CheckResult]) -> str:
    lines = ["<evidence>"]
    for c in chunks:
        lines.append(f'<doc id="{c.id}" source="{c.source}" title="{c.title} — {c.section}" version="{c.version}">\n{c.text}\n</doc>')
    lines.append("</evidence>")
    if checks:
        lines.append("<drug_check>\n상태 뜻: PROHIBITED=상시 금지, IN_COMPETITION_ONLY=경기기간 중에만 금지, "
                     "THRESHOLD=기준치 넘으면 금지, CONDITIONAL=투여 경로·용량 등 조건부, NOT_LISTED_VERIFY=목록에 없음, UNKNOWN=판정 못 함")
        lines += [_drug(c) for c in checks]
        lines.append("</drug_check>")
    return "\n".join(lines)
