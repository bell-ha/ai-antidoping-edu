"""Claude 호출과 재현 모드 (D16).

mock   : 키 없이 UI 개발용. 첫 근거를 인용하는 고정 응답. guard·S5는 이 모드로 검증되지 않는다.
live   : 매번 호출.
record : 호출하고 결과를 backend/demo/llm_cache/에 저장.
replay : 캐시만 사용. 없으면 CacheMiss.

정상 답이 아닌 경우는 예외로 알린다. 호출하는 쪽이 서버 고정 문구로 바꾼다.
"""

import hashlib
import json
import logging

import anthropic
from pydantic import ValidationError

from app import config
from app.schemas import LlmAnswer

log = logging.getLogger(__name__)

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "refer_to_expert": {"type": "boolean"},
        "out_of_scope": {"type": "boolean"},
    },
    "required": ["answer", "citations", "refer_to_expert", "out_of_scope"],
    "additionalProperties": False,
}


# 토큰 절약(2026-10-18 사용자): 근거를 전하는 2~4문단 답이라 생각 수준은 low, 답 길이 상한 1200 토큰
MAX_TOKENS = 1200


class CacheMiss(Exception):
    pass


class Refused(Exception):
    pass


class Unavailable(Exception):
    pass


def cache_key(system: str, messages: list[dict]) -> str:
    raw = json.dumps({"model": config.CLAUDE_MODEL, "system": system, "messages": messages}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _mock(evidence_ids: list[str]) -> LlmAnswer:
    return LlmAnswer(
        answer="[mock 응답] API 키 없이 화면을 개발하기 위한 고정 응답입니다. 실제 답변은 LLM_MODE=live에서 확인하세요.",
        citations=evidence_ids[:2],
        refer_to_expert=False,
        out_of_scope=not evidence_ids,
    )


def _live(system: str, messages: list[dict]) -> LlmAnswer:
    try:
        headers = {"anthropic-workspace-id": config.ANTHROPIC_WORKSPACE_ID} if config.ANTHROPIC_WORKSPACE_ID else None
        response = anthropic.Anthropic(default_headers=headers).beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AnthropicError as e:  # CredentialsError, 429, 5xx, 연결 오류
        log.warning("Claude API 오류: %s", e)
        raise Unavailable from e
    except TypeError as e:
        # 키도 ant 프로필도 없으면 SDK 1.12가 요청 단계에서 TypeError를 낸다.
        # 인자 버그도 같은 예외라 숨기지 않도록 스택 전체를 남긴다.
        log.exception("Claude 클라이언트 설정 오류 (ANTHROPIC_API_KEY 확인)")
        raise Unavailable from e
    if response.stop_reason == "refusal":
        raise Refused
    if response.stop_reason == "max_tokens":
        log.warning("응답이 max_tokens에서 잘림")
        raise Unavailable
    try:
        text = next(b.text for b in response.content if b.type == "text")
        return LlmAnswer.model_validate_json(text)
    except (StopIteration, ValidationError) as e:
        log.warning("응답 형식 오류: %s", e)
        raise Unavailable from e


def generate(system: str, messages: list[dict], evidence_ids: list[str]) -> LlmAnswer:
    mode = config.LLM_MODE
    if mode == "mock":
        return _mock(evidence_ids)
    path = config.LLM_CACHE_DIR / f"{cache_key(system, messages)}.json"
    if mode == "replay":
        if not path.exists():
            raise CacheMiss(path.name)
        return LlmAnswer.model_validate_json(path.read_text(encoding="utf-8"))
    answer = _live(system, messages)
    if mode == "record":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(answer.model_dump_json(indent=2), encoding="utf-8")
    return answer
