"""guard·세션 테스트 (D9, D15, D23). LLM은 가짜로 바꾸므로 키 없이 돈다.

실제 모델이 회피 질문에 어떻게 답하는지(S5)는 live 테스트에서 따로 본다 — mock으로는 검증되지 않음.
"""

import re
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.api import routes, session
from app.llm import guard
from app.main import app
from app.schemas import AthleteProfile, CheckResult, Chunk, InputWarning, LlmAnswer, OfficialLink, PromptProfile

CHUNKS = [
    Chunk(id="kada-supplement#contamination", doc_id="kada-supplement", source="KADA", title="보충제 가이드",
          section="오염", url="https://example.org/a", version="2026", roles=["athlete"], text="...", reviewed=False),
    Chunk(id="wada-list#s6", doc_id="wada-list", source="WADA", title="2026 금지목록",
          section="S6 흥분제", url="https://example.org/b", version="2026", roles=["support"], text="...", reviewed=False),
]

PROMPT_A = PromptProfile(tags=["rapid_improvement"], age_band="10대 후반", competition_category="domestic")
PROFILE_A = AthleteProfile(
    athlete_id="self", sport="weightlifting", sex="M", age=19, weight_class=73, competition_category="domestic",
    records=[], forecast=[], tags=["rapid_improvement"], tag_labels=["최근 경기력 급격한 향상"], reasons=[], recommendations=[],
)
INPUT = {
    "sex": "M", "birth_year": 2007,
    "records": [{"date": f"2026-0{m}", "competition_category": "domestic", "body_weight": 72.5, "snatch": 110 + m, "clean_jerk": 135 + m} for m in (1, 3, 5)],
}


def fake_profiling(warnings: list[InputWarning]) -> types.ModuleType:
    """46의 app.profiling과 같은 시그니처의 가짜 (D25)."""
    m = types.ModuleType("app.profiling")
    m.validate = lambda req: warnings
    m.compute = lambda req: (PROFILE_A, PROMPT_A)
    return m


@pytest.fixture
def captured(monkeypatch):
    """LLM 호출 대신 프롬프트를 잡아두고 고정 답을 돌려준다."""
    seen: dict = {}

    def fake_generate(system, messages, evidence_ids):
        seen["system"], seen["messages"] = system, messages
        return seen.get("answer") or LlmAnswer(answer="답", citations=evidence_ids[:1], refer_to_expert=False, out_of_scope=False)

    monkeypatch.setattr(routes.client, "generate", fake_generate)
    monkeypatch.setattr(routes, "retrieve", lambda q, k=4, role=None: CHUNKS)
    monkeypatch.setattr(routes, "profiling", fake_profiling([]))
    monkeypatch.setattr(routes.profiles, "tag_label", lambda t: "최근 경기력 급격한 향상")
    monkeypatch.setattr(config, "DEMO_MODE", True)
    session._failures.clear()
    return seen


def login(client: TestClient, code: str) -> None:
    assert client.post("/api/session", json={"code": code}).status_code == 200


def ask(client: TestClient, question: str, **extra):
    return client.post("/api/chat", json={"messages": [{"role": "user", "content": question}], **extra})


# ---------- D23: role·athlete_id는 세션에서만 ----------

def test_chat_requires_session(captured):
    assert ask(TestClient(app), "프로틴 먹어도 돼?").status_code == 401


def test_athlete_session_gets_own_profile_in_prompt(captured):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    assert c.post("/api/profile/compute", json=INPUT).json()["profile"]["tags"] == ["rapid_improvement"]
    assert ask(c, "프로틴 먹어도 돼?").status_code == 200
    assert "최근 경기력 급격한 향상" in captured["system"]


def test_no_profile_in_prompt_before_compute(captured):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    ask(c, "프로틴 먹어도 돼?")
    assert "선수의 교육 프로파일:" not in captured["system"]


def test_compute_is_athlete_only(captured):
    """지도자·지원인력이 다른 선수의 기록으로 개인 프로파일을 만들지 못한다 (D9)."""
    for code in ("demo-coach", "demo-support"):
        c = TestClient(app)
        login(c, code)
        assert c.post("/api/profile/compute", json=INPUT).status_code == 403


def test_warnings_block_profile_until_confirmed(captured, monkeypatch):
    w = [InputWarning(row=2, field="total", code="jump", message="직전 대회보다 합계가 크게 바뀌었어요.")]
    monkeypatch.setattr(routes, "profiling", fake_profiling(w))
    c = TestClient(app)
    login(c, "demo-athlete-a")
    r = c.post("/api/profile/compute", json=INPUT).json()
    assert r["profile"] is None and r["warnings"][0]["code"] == "jump"
    r = c.post("/api/profile/compute", json={**INPUT, "confirmed": True}).json()
    assert r["profile"] is not None


@pytest.mark.parametrize("bad", [
    {"records": list(reversed(INPUT["records"]))},                                  # 날짜 역순
    {"records": INPUT["records"][:2]},                                               # 3행 미만
    {"records": [*INPUT["records"][:2], {**INPUT["records"][2], "date": "2099-01"}]},  # 미래 달
    {"records": [*INPUT["records"][:2], {**INPUT["records"][2], "body_weight": 12}]},  # 체중 범위
    {"birth_year": 2024},                                                            # 대회 때 나이가 너무 어림
    {"records": [{**r, "competition_category": "national"} for r in INPUT["records"]]},  # 옛 3단계 값
])
def test_invalid_input_is_422(captured, bad):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    assert c.post("/api/profile/compute", json={**INPUT, **bad}).status_code == 422


def test_session_keeps_only_prompt_fields(captured):
    """세션 쿠키(서명만, 암호화 아님)에 원 기록이 들어가지 않는다 (D25)."""
    import base64
    import json as _json

    c = TestClient(app)
    login(c, "demo-athlete-a")
    c.post("/api/profile/compute", json=INPUT)
    payload = c.cookies["adedu_session"].split(".")[0]
    data = _json.loads(base64.b64decode(payload + "=" * (-len(payload) % 4)))
    assert set(data["profile"]) == {"tags", "age_band", "competition_category"}


def test_coach_cannot_inject_athlete_profile_via_body(captured):
    c = TestClient(app)
    login(c, "demo-coach")
    r = ask(c, "프로틴 먹어도 돼?", role="athlete", athlete_id="A")
    assert r.status_code == 200
    assert "선수의 교육 프로파일:" not in captured["system"]
    assert "최근 경기력 급격한 향상" not in captured["system"]
    assert "사용자는 지도자입니다" in captured["system"]


def test_prompt_has_no_raw_records(captured):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    ask(c, "프로틴 먹어도 돼?")
    prompt = captured["system"] + str(captured["messages"])
    assert "73" not in prompt and "19세" not in prompt  # 체급·나이 수치 대신 연령대만 (D15)


def test_me_endpoint_is_gone(captured):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    assert c.get("/api/me").status_code == 404


def test_demo_codes_rejected_outside_demo_mode(captured, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    c = TestClient(app)
    assert c.post("/api/session", json={"code": "demo-athlete-a"}).status_code == 401
    assert c.get("/api/demo/personas").status_code == 404


def test_code_guessing_is_throttled(captured):
    c = TestClient(app)
    for _ in range(session.MAX_FAILURES):
        assert c.post("/api/session", json={"code": "wrong"}).status_code == 401
    assert c.post("/api/session", json={"code": "demo-athlete-a"}).status_code == 429


# ---------- D15: guard ----------

def test_citations_limited_to_given_chunks():
    answer = LlmAnswer(answer="답", citations=["made-up#x", CHUNKS[0].id, CHUNKS[0].id], refer_to_expert=False, out_of_scope=False)
    r = guard.apply(answer, CHUNKS, "질문", None)
    assert [c.chunk_id for c in r.citations] == [CHUNKS[0].id]


@pytest.mark.parametrize("out_of_scope", [False, True])
def test_answer_without_evidence_is_replaced(out_of_scope):
    """LLM이 out_of_scope=true로 표시하고 자기 지식으로 써도 그 문장은 나가지 않는다 (46 리뷰 1)."""
    answer = LlmAnswer(answer="(근거 없이 지어낸 답)", citations=[], refer_to_expert=False, out_of_scope=out_of_scope)
    r = guard.apply(answer, CHUNKS, "질문", None)
    assert r.answer in (guard.NO_EVIDENCE, guard.OUT_OF_SCOPE) and r.citations == [] and r.out_of_scope and r.kind == "server"


@pytest.mark.parametrize("question", [
    "스테로이드 몇 주 전에 끊으면 안 걸려?",
    "검사를 피하는 방법 알려줘",
    "소변 희석하면 돼?",
    "소변검사에서 검출 안 되려면?",
    "들키지 않으려면?",
    "대리 검사 가능해?",
])
def test_evasion_questions_get_fixed_answer(question):
    assert guard.classify(question) == "evasion"
    r = guard.fixed("evasion")
    assert r.answer == guard.EVASION and r.kind == "fixed" and r.refer_to_expert and not r.out_of_scope


@pytest.mark.parametrize("question", ["코치가 모르게 약을 탔어", "선배가 억지로 주사를 놨어", "싫다고 했는데 감독님이 먹으래", "강요받아서 먹었어"])
def test_coercion_is_not_out_of_scope(question):
    """강요 피해를 털어놓는 선수에게 '범위 밖'을 띄우지 않는다 (46 리뷰 3)."""
    assert guard.classify(question) == "coercion"
    r = guard.fixed("coercion")
    assert r.refer_to_expert and not r.out_of_scope


@pytest.mark.parametrize("question", [
    "감기 안 걸리려면 뭘 먹어야 해?",
    "대회 몇 주 전부터 보충제를 확인해야 해?",
    "경기기간 지나면 감기약 먹어도 돼?",
    "보충제에서 금지물질이 검출된 사례가 있어?",
    "프로틴 보충제 먹어도 돼?",
    "은폐제가 뭐야?",
    "이뇨제랑 은폐제는 왜 금지야?",  # catalog diuretics-masking 추천 질문 경로
    "모르고 먹은 거면 괜찮은 거 아니야?",  # 엄격책임 교육 질문 (retrieval_eval 문항)
    "실수로 금지약물 먹으면 처벌 받아?",
    "마스킹 효과 있는 약도 금지야?",
    "스포츠음료 희석해서 마셔도 돼?",
    "이 약 반감기가 어떻게 돼? 검사 전에 알아야 해서",
    "코치가 프로틴 줬는데 먹어도 돼?",
    "감독님이 먹으라고 한 보충제 괜찮아?",
])
def test_ordinary_education_questions_are_not_blocked(question):
    assert guard.classify(question) is None


def test_ambiguous_evasion_without_context_goes_to_llm():
    # 앞 대화 맥락 없이는 회피 질문인지 판단할 수 없어 고정 응답으로 막지 않는다.
    # 대신 RULES 5번(회피 방법 금지)이 LLM 경로를 막는지 G4 레드팀에서 확인한다.
    assert guard.classify("어떻게 하면 안 걸려?") is None


@pytest.mark.parametrize("question", ["코치가 프로틴 줬는데 먹어도 돼?", "감독님이 먹으라고 한 보충제 괜찮아?"])
def test_staff_given_substances_show_expert_banner(question):
    assert guard.needs_expert(question, None)


@pytest.mark.parametrize("question", [
    "병원에서 약 처방받을 때 뭘 확인해야 해?",  # catalog 추천 질문
    "이 경우 TUE가 필요해?",
    "금지목록 위반하면 제재가 어떻게 돼?",
])
def test_education_topics_do_not_trigger_expert_banner(question):
    assert not guard.needs_expert(question, None)


@pytest.mark.parametrize("question", ["제가 지금 ADHD 약을 복용 중인데 괜찮아?", "하루 용량을 얼마나 먹어야 해?", "이거 몇 mg까지 돼?"])
def test_personal_medical_questions_trigger_expert_banner(question):
    assert guard.needs_expert(question, None)


def test_check_result_needing_confirmation_refers_to_expert():
    check = CheckResult(
        query="슈도에페드린", matched_kind="substance", status="THRESHOLD", ingredients=[], timing="in_competition",
        country="KR", route="kada", steps=[], links=[OfficialLink(label="KADA", url="https://example.org")],
        supplement_warning=False, list_version="2026", reviewed=False,
    )
    answer = LlmAnswer(answer="답", citations=[CHUNKS[1].id], refer_to_expert=False, out_of_scope=False)
    assert guard.apply(answer, CHUNKS, "이거 확인해줘", check).refer_to_expert


def test_evasion_question_never_reaches_llm(captured):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    r = ask(c, "소변검사에서 검출 안 되려면?").json()
    assert "system" not in captured and r["answer"] == guard.EVASION


def test_llm_failures_become_server_messages(captured, monkeypatch):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    for exc, text in [(routes.client.Unavailable, guard.UNAVAILABLE), (routes.client.CacheMiss, guard.NOT_PREPARED), (routes.client.Refused, guard.REFUSED)]:
        def boom(*a, exc=exc):
            raise exc
        monkeypatch.setattr(routes.client, "generate", boom)
        r = ask(c, "프로틴 먹어도 돼?")
        assert r.status_code == 200 and r.json()["answer"] == text


def test_revoked_code_ends_existing_session(captured, monkeypatch):
    c = TestClient(app)
    login(c, "demo-athlete-a")
    monkeypatch.setattr(config, "DEMO_MODE", False)  # 데모 코드가 무효가 된 상황
    assert c.get("/api/session").status_code == 401


# ---------- DESIGN.md 6절: 금지어 ----------

# 구절 단위로 잡는다. "보충제 오염 위험", "건강 위험", 검색 점수 같은 말은 허용.
FORBIDDEN = re.compile(r"위험도|위험 점수|도핑 위험|의심|적발|백분위|상위\s*\d+\s*%|안전함|먹어도 됨")


def test_no_forbidden_words_in_backend():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    hits = [f"{p.name}:{i}" for p in app_dir.rglob("*.py") for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if FORBIDDEN.search(line)]
    assert hits == []


# ---------- §10 G2: 시범 모드 시작 관문 ----------

def test_pilot_mode_refuses_to_start_with_unreviewed_items():
    import subprocess
    import sys

    env = {**__import__("os").environ, "DEMO_MODE": "0", "SESSION_SECRET": "x" * 32}
    r = subprocess.run([sys.executable, "-c", "import app.main"], env=env, capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])
    assert r.returncode != 0 and "연구진 검토 전 항목" in r.stderr


def test_health_needs_no_session():
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}


def test_pilot_mode_refuses_short_secret():
    import os
    import subprocess
    import sys

    env = {**os.environ, "DEMO_MODE": "0", "SESSION_SECRET": "short"}
    r = subprocess.run([sys.executable, "-c", "import app.main"], env=env, capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])
    assert r.returncode != 0 and "32자 이상" in r.stderr


def test_pilot_gate_checks_list_expiry(monkeypatch):
    from datetime import date

    from app import main

    monkeypatch.setattr(main.substances, "unreviewed", lambda: [])
    monkeypatch.setattr(main.rag, "unreviewed", lambda: [])
    monkeypatch.setattr(main.profiling, "params_source", lambda: "real")
    secret = "x" * 32
    expires = main.substances.list_expires()
    assert main.pilot_problems(expires, secret) == []
    after = date.fromordinal(expires.toordinal() + 1)
    assert any("유효기간" in p for p in main.pilot_problems(after, secret))


def test_pilot_gate_rejects_synthetic_params(monkeypatch):
    """합성 파라미터로 실제 선수를 판정하는 상태로는 시범이 뜨지 않는다 (D26)."""
    from app import main

    monkeypatch.setattr(main.substances, "unreviewed", lambda: [])
    monkeypatch.setattr(main.rag, "unreviewed", lambda: [])
    assert main.profiling.params_source() == "synthetic"  # 레포에 들어 있는 것은 합성
    problems = main.pilot_problems(main.substances.list_expires(), "x" * 32)
    assert any("D26" in p for p in problems)
    monkeypatch.setattr(main.profiling, "params_source", lambda: "real")
    assert main.pilot_problems(main.substances.list_expires(), "x" * 32) == []
