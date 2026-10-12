"""경기력·약물 확인·AI 교육 API. 사용자 식별은 모두 세션에서 (D23)."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config, profiles, profiling, substances
from app.api.session import current
from app.llm import client, guard, prompts
from app.rag import get_chunk, retrieve
from app.schemas import (
    ChatRequest,
    ChatResponse,
    Chunk,
    CheckRequest,
    CheckResult,
    ComputeRequest,
    ComputeResponse,
    PromptProfile,
    SessionInfo,
    DemoScenario,
    DemoScenarios,
)

router = APIRouter(prefix="/api")


@router.post("/profile/compute", response_model=ComputeResponse)
def compute(body: ComputeRequest, request: Request, who: SessionInfo = Depends(current)) -> ComputeResponse:
    """선수가 입력한 최근 기록으로 교육 프로파일을 계산한다 (D25). 입력은 저장하지 않는다."""
    if who.role != "athlete":
        raise HTTPException(403, "선수 본인만 교육 프로파일을 만들 수 있어요.")  # D9
    warnings = profiling.validate(body)
    if warnings and not body.confirmed:
        return ComputeResponse(profile=None, warnings=warnings)
    profile, prompt = profiling.compute(body)
    if not config.DEMO_MODE:
        profile.checks = []  # 판정 점검표는 테스트·설명용. 시범 선수에게는 기준 근접도가 점수처럼 읽힌다 (D7)
    # 세션(서명만 되고 암호화되지 않는 쿠키)에는 프롬프트용 필드만
    request.session["profile"] = prompt.model_dump()
    return ComputeResponse(profile=profile, warnings=warnings)


def _demo_examples() -> dict:
    path = config.DATA / "demo_examples.json"
    return json.loads(path.read_text(encoding="utf-8")) if config.DEMO_MODE and path.exists() else {}


@router.get("/demo/examples", response_model=DemoScenarios)
def demo_scenarios(who: SessionInfo = Depends(current)) -> DemoScenarios:
    """DEMO_MODE에서만: 테스트 시나리오 목록과 지금 서버 방식에서의 기대 태그."""
    if not config.DEMO_MODE:
        raise HTTPException(404)
    model = profiling.params().get("model", "synthetic_trend")
    return DemoScenarios(
        model=model,
        scenarios=[
            DemoScenario(id=k, label=v.get("label", k), description=v.get("description", ""), sex=v["sex"], expect=v["expect"][model],
                         expect_labels=[profiles.tag_label(t) for t in v["expect"][model]], warnings=v.get("warnings", []))
            for k, v in _demo_examples().items()
            if "expect" in v
        ],
    )


@router.get("/demo/examples/{athlete_id}", response_model=ComputeRequest)
def demo_example(athlete_id: str, who: SessionInfo = Depends(current)) -> ComputeRequest:
    """DEMO_MODE에서만: 페르소나 입력 예시(예시 채우기 버튼). 같은 compute 경로를 탄다."""
    examples = _demo_examples()
    if athlete_id not in examples:
        raise HTTPException(404)
    return ComputeRequest.model_validate(examples[athlete_id])


@router.post("/check", response_model=CheckResult)
def check(body: CheckRequest, who: SessionInfo = Depends(current)) -> CheckResult:
    return substances.check(body.query, body.country, body.timing)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, who: SessionInfo = Depends(current)) -> ChatResponse:
    if body.messages[-1].role != "user":
        raise HTTPException(422, "마지막 메시지는 사용자 질문이어야 해요.")
    question = body.messages[-1].content
    check_result = body.context.check_result if body.context else None

    # 검사 회피·강요 피해는 LLM을 부르지 않는다 (S5)
    kind = guard.classify(question)
    if kind is not None:
        return guard.fixed(kind)

    # 프로파일은 선수 본인이 계산한 것만 (D9, D25). 본문에는 role·프로파일이 없다.
    saved = request.session.get("profile") if who.role == "athlete" else None
    record = PromptProfile.model_validate(saved) if saved else None
    tag_labels = [profiles.tag_label(t) for t in record.tags] if record else []

    chunks = retrieve(question, k=4, role=who.role)
    system = prompts.system_prompt(who.role, record, tag_labels)
    history = [m.model_dump() for m in body.messages[:-1]]
    messages = [*history, {"role": "user", "content": f"{prompts.evidence_block(chunks, check_result)}\n\n질문: {question}"}]

    try:
        answer = client.generate(system, messages, [c.id for c in chunks])
    except client.CacheMiss:
        return guard.server_message(guard.NOT_PREPARED)
    except client.Refused:
        return guard.server_message(guard.REFUSED).model_copy(update={"refer_to_expert": True})
    except client.Unavailable:
        return guard.server_message(guard.UNAVAILABLE)
    return guard.apply(answer, chunks, question, check_result)


@router.get("/sources/{chunk_id:path}", response_model=Chunk)
def source(chunk_id: str, who: SessionInfo = Depends(current)) -> Chunk:
    chunk = get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(404)
    return chunk
