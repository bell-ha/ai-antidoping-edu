"""질문하기 (D15, D37). 선수 개인정보·기록·단계는 AI에 넘기지 않는다 — 근거는 레슨과 약물 조회표뿐.

- 질문과 답은 chat_logs에 저장하고 관리자가 선수별로 본다.
- 선수는 하루 DAILY_CHAT_LIMIT번까지 AI 답변(비용 한도). 고정 응답·서버 문구는 세지 않는다.
- 대화 기록 서명(D33): 서버가 준 답에만 서명을 붙이고, 다음 요청의 이전 답은 서명이 맞아야 받는다.
"""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config, db
from app.api.login import current
from app.chat import client, drug_lookup, guard, prompts
from app.chat.retrieve import retrieve
from app.program import lessons
from app.schemas import ChatMessage, ChatRequest, ChatResponse, RelatedLesson, SessionInfo

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)
HISTORY_TURNS = 2  # AI에 다시 보내는 이전 대화(질문+답) 수. 토큰 절약(2026-10-18 사용자)


def sign(request: Request, text: str) -> str:
    key = f"{config.SESSION_SECRET}\n{request.session.get('code_hash', '')}".encode()
    return hmac.new(key, text.encode(), hashlib.sha256).hexdigest()[:32]


def verify_history(request: Request, messages: list[ChatMessage]) -> None:
    for m in messages:
        if m.role == "assistant" and not (m.token and hmac.compare_digest(m.token, sign(request, m.content))):
            raise HTTPException(422, "대화 기록을 확인할 수 없어요. 새로 고침 후 다시 질문해 주세요.")


def _over_limit(who: SessionInfo) -> bool:
    if who.role != "athlete":
        return False
    with db.connect() as con:
        n = con.execute("SELECT COUNT(*) FROM chat_logs WHERE athlete_id = ? AND day = ? AND kind = 'chat_llm'",
                        (who.athlete_id, db.today())).fetchone()[0]
    return n >= config.DAILY_CHAT_LIMIT


def _save(who: SessionInfo, question: str, response: ChatResponse, kind: str) -> None:
    try:
        with db.connect() as con:
            con.execute("""INSERT INTO chat_logs (athlete_id, day, at, question, answer, kind, citations_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (who.athlete_id, db.today(), db.now_iso(), question, response.answer, kind,
                         json.dumps([c.chunk_id for c in response.citations])))
    except Exception:  # 기록 실패로 질문을 못 하게 하지 않는다
        log.exception("질문 기록 저장 실패")


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, who: SessionInfo = Depends(current)) -> ChatResponse:
    if body.messages[-1].role != "user":
        raise HTTPException(422, "마지막 메시지는 사용자 질문이어야 해요.")
    verify_history(request, body.messages[:-1])
    question = body.messages[-1].content
    response, kind = _answer(body, who)
    _save(who, question, response, kind)
    return response.model_copy(update={"token": sign(request, response.answer)})


def _answer(body: ChatRequest, who: SessionInfo) -> tuple[ChatResponse, str]:
    question = body.messages[-1].content
    kind = guard.classify(question)  # 검사 회피·강요 피해는 LLM을 부르지 않는다 (S5)
    if kind is not None:
        return guard.fixed(kind), "chat_fixed"
    if _over_limit(who):
        return guard.server_message(guard.DAILY_LIMIT), "chat_limit"

    checks = drug_lookup.lookup(question)
    # 약 이름이 있으면 성분 이름으로도 찾고(예: 타이레놀 → 슈도에페드린 레슨), 판정이 이미 근거라 레슨은 3개만
    names = " ".join(dict.fromkeys(i.name_ko for c in checks for i in c.ingredients))
    chunks = retrieve(f"{question} {names}", k=3) if checks else retrieve(question)
    history = [m.model_dump(exclude={"token"}) for m in body.messages[:-1][-2 * HISTORY_TURNS:]]
    messages = [*history, {"role": "user", "content": f"{prompts.evidence_block(chunks, checks)}\n\n질문: {question}"}]
    try:
        answer = client.generate(prompts.system_prompt(who.role), messages, [c.id for c in chunks])
    except client.CacheMiss:
        return guard.server_message(guard.NOT_PREPARED), "chat_server"
    except client.Refused:
        return guard.server_message(guard.REFUSED).model_copy(update={"refer_to_expert": True}), "chat_llm"
    except client.Unavailable:
        return guard.server_message(guard.UNAVAILABLE), "chat_server"
    result = guard.apply(answer, chunks, question, checks[0] if checks else None)
    if result.kind != "answer":
        return result, "chat_llm"
    related = [RelatedLesson(lesson_id=d, title=lessons.title(d), category=lessons.meta(d)["category"])
               for d in dict.fromkeys(c.chunk_id.split("#")[0] for c in result.citations) if lessons.exists(d)]
    return result.model_copy(update={"drug_checks": checks, "related_lessons": related}), "chat_llm"
