"""경기력·팀·약물 확인·AI 교육 API. 사용자 식별은 모두 세션에서 (D23)."""

from fastapi import APIRouter, Depends, HTTPException

from app import profiles, substances
from app.api.session import current
from app.llm import client, guard, prompts
from app.rag import get_chunk, retrieve
from app.schemas import AthleteProfile, ChatRequest, ChatResponse, Chunk, CheckRequest, CheckResult, SessionInfo, TeamSummary

router = APIRouter(prefix="/api")


@router.get("/me", response_model=AthleteProfile)
def me(who: SessionInfo = Depends(current)) -> AthleteProfile:
    if who.role != "athlete" or who.athlete_id is None:
        raise HTTPException(403, "선수 본인만 볼 수 있어요.")
    profile = profiles.load_profile(who.athlete_id)
    if profile is None:
        raise HTTPException(404)
    return profile


@router.get("/team/summary", response_model=TeamSummary)
def team_summary(who: SessionInfo = Depends(current)) -> TeamSummary:
    if who.role != "coach" or who.team_id is None:
        raise HTTPException(403)
    summary = profiles.load_team_summary(who.team_id)
    if summary is None:
        raise HTTPException(404)
    return summary


@router.post("/check", response_model=CheckResult)
def check(body: CheckRequest, who: SessionInfo = Depends(current)) -> CheckResult:
    return substances.check(body.query, body.country, body.timing)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, who: SessionInfo = Depends(current)) -> ChatResponse:
    if body.messages[-1].role != "user":
        raise HTTPException(422, "마지막 메시지는 사용자 질문이어야 해요.")
    question = body.messages[-1].content
    check_result = body.context.check_result if body.context else None

    # 검사 회피·강요 피해는 LLM을 부르지 않는다 (S5)
    kind = guard.classify(question)
    if kind is not None:
        return guard.fixed(kind)

    # 프로파일은 선수 본인 세션일 때만 (D9). 본문에는 role·athlete_id가 없다.
    record = profiles.load_record(who.athlete_id) if who.role == "athlete" and who.athlete_id else None
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
