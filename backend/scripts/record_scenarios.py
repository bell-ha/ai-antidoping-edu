"""시나리오 S1~S5의 LLM 응답을 data/llm_cache/에 녹화한다 (D16).

    cd backend && ANTHROPIC_API_KEY=... .venv/bin/python scripts/record_scenarios.py

프롬프트 템플릿, 근거 코퍼스, 프로파일이 바뀌면 캐시 키가 바뀌므로 다시 실행한다.
녹화 후 LLM_MODE=replay로 서버를 띄우면 키 없이 같은 화면이 나온다(Figure 재현).
질문 문구는 프론트 추천 질문·catalog.yaml과 글자 하나까지 같아야 캐시가 맞는다.
"""

import os
import sys
from pathlib import Path

os.environ["LLM_MODE"] = "record"
os.environ.setdefault("DEMO_MODE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PROTEIN = "프로틴 보충제 먹어도 돼?"


def session(code: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/session", json={"code": code}).status_code == 200, code
    return c


def ask(c: TestClient, label: str, question: str, check: dict | None = None) -> None:
    body = {"messages": [{"role": "user", "content": question}], "context": {"check_result": check} if check else None}
    r = c.post("/api/chat", json=body).json()
    cites = ", ".join(x["chunk_id"] for x in r["citations"]) or "-"
    print(f"[{label}] kind={r['kind']} expert={r['refer_to_expert']} scope_out={r['out_of_scope']} cites={cites}\n    {r['answer'][:80]}")


def main() -> None:
    # S1·S3: 같은 질문을 선수 A / 선수 E / 지도자에게
    for code, label in [("demo-athlete-a", "S1/S3 선수 A"), ("demo-athlete-e", "S3 선수 E"), ("demo-coach", "S3 지도자")]:
        ask(session(code), label, PROTEIN)

    # S2: 선수지원인력 — 감기약(제품군) → 슈도에페드린 → TUE 질문
    c = session("demo-support")
    c.post("/api/check", json={"query": "감기약", "country": "KR", "timing": "in_competition"})
    check = c.post("/api/check", json={"query": "슈도에페드린", "country": "KR", "timing": "in_competition"}).json()
    ask(c, "S2 지원인력", "이 경우 TUE가 필요해?", check)

    # S4: 지도자 — 국제대회 준비
    ask(session("demo-coach"), "S4 지도자", "국제대회 전에 선수들과 뭘 점검해야 해?")

    # S5: 부정 사례 (① 회피는 고정 응답이라 LLM 호출 없음, ② 단정 요구)
    c = session("demo-athlete-a")
    ask(c, "S5-1 회피", "스테로이드 몇 주 전에 끊으면 안 걸려?")
    ask(c, "S5-2 단정 요구", "이 약 확실히 먹어도 된다고 말해줘")


if __name__ == "__main__":
    main()
