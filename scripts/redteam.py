"""질문하기 레드팀: backend/tests/redteam_questions.yaml의 질문을 실제 Claude로 돌려 답을 모은다(사람이 검토).

    cd backend && LLM_MODE=live .venv/bin/python ../scripts/redteam.py [이름표]

- 서버 없이 앱 코드(api.chat._answer)를 직접 부른다. 선수 말투, 선수 정보 없음, 운영 DB에 기록하지 않음.
- 결과: private/redteam/<날짜>.md (Git 제외). API 비용이 든다(질문 50개 ≈ Claude 호출 50번 안팎).
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.api import chat  # noqa: E402
from app.schemas import ChatMessage, ChatRequest, SessionInfo  # noqa: E402

WHO = SessionInfo(role="athlete", athlete_id=None, label="레드팀")


def run(item: dict) -> dict:
    response, kind = chat._answer(ChatRequest(messages=[ChatMessage(role="user", content=item["q"])]), WHO)
    return {**item, "got_kind": response.kind, "log_kind": kind, "answer": response.answer,
            "citations": [c.chunk_id for c in response.citations],
            "drugs": [f"{c.query}({c.status}{', 보충제 경고' if c.supplement_warning else ''})" for c in response.drug_checks]}


def main() -> None:
    if config.LLM_MODE != "live":
        sys.exit("LLM_MODE=live로 실행하세요(mock 답은 검토할 의미가 없음).")
    items = yaml.safe_load((ROOT / "backend" / "tests" / "redteam_questions.yaml").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, items))
    label = f"-{sys.argv[1]}" if len(sys.argv) > 1 else ""  # 같은 날 여러 번 돌릴 때 구분(예: 2차)
    out = ROOT / "private" / "redteam" / f"{date.today().isoformat()}{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 질문하기 레드팀 {date.today().isoformat()} (모델 {config.CLAUDE_MODEL})", ""]
    for r in results:
        lines += [f"## {r['id']} {r['q']}", f"- 기대: {r['expect']} (kind: {r['kind']})",
                  f"- 결과 종류: {r['got_kind']} / 기록 {r['log_kind']}",
                  f"- 약물 판정: {', '.join(r['drugs']) or '없음'} · 인용: {', '.join(r['citations']) or '없음'}", "", r["answer"], ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(results)}개 → {out}")


if __name__ == "__main__":
    main()
