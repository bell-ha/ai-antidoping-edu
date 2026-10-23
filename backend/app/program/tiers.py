"""모델 결과 → 줄 세우기 → 단계.

- 기준: 연구진 모델의 관측 − 예측(kg)이 큰 선수, 즉 예측보다 기록이 많이 오른 선수가 앞.
- 모델 결과가 없는 선수(기록이 모자람 등)는 줄 맨 뒤 → 가장 낮은 단계.
- 전체 인원을 단계 수로 고르게 나눈다(100명·5단계면 20명씩). 1단계가 가장 낮고, 단계가 높을수록
  한 주에 듣는 교육과 갑자기 퀴즈가 많다(교육 내용 난이도는 같고 양만 다르다).
"""

import json
import sqlite3

import yaml

from app import config, db
from app.model import adapter
from app.schemas import ModelResult, ProgramSettings, RecordRow, TierSetting


def default_settings() -> ProgramSettings:
    return ProgramSettings.model_validate(yaml.safe_load((config.SETTINGS / "program.yaml").read_text(encoding="utf-8")))


def load_settings(con: sqlite3.Connection) -> ProgramSettings:
    row = con.execute("SELECT tiers_json FROM settings ORDER BY id DESC LIMIT 1").fetchone()
    return ProgramSettings(tiers=json.loads(row["tiers_json"])) if row else default_settings()


def save_settings(con: sqlite3.Connection, settings: ProgramSettings, admin_id: int | None) -> None:
    tiers = [t.model_copy(update={"tier": i}) for i, t in enumerate(settings.tiers, start=1)]  # 1부터 빈틈없이
    con.execute("INSERT INTO settings (changed_at, changed_by, tiers_json) VALUES (?, ?, ?)",
                (db.now_iso(), admin_id, json.dumps([t.model_dump() for t in tiers])))


def tier_setting(con: sqlite3.Connection, tier: int | None) -> TierSetting:
    tiers = load_settings(con).tiers
    return tiers[min(max((tier or 1), 1), len(tiers)) - 1]


def records(con: sqlite3.Connection, athlete_id: int) -> list[RecordRow]:
    from app.model.predict import weight_class
    sex = con.execute("SELECT sex FROM athletes WHERE id = ?", (athlete_id,)).fetchone()["sex"]
    rows = con.execute("SELECT * FROM records WHERE athlete_id = ? ORDER BY date, id", (athlete_id,)).fetchall()
    return [RecordRow(id=r["id"], date=r["date"], competition_category=r["competition_category"], body_weight=r["body_weight"],
                      snatch=r["snatch"], clean_jerk=r["clean_jerk"], weight_class=weight_class(sex, r["body_weight"]),
                      total=r["snatch"] + r["clean_jerk"]) for r in rows]


def compute_model(con: sqlite3.Connection, athlete_id: int) -> ModelResult:
    """그 선수의 지금 기록 전부로 모델을 돌리고 결과를 한 줄 남긴다."""
    a = con.execute("SELECT sex, birth_year FROM athletes WHERE id = ?", (athlete_id,)).fetchone()
    result = adapter.result(a["sex"], a["birth_year"], records(con, athlete_id))
    con.execute("INSERT INTO model_results (athlete_id, computed_at, model_version, residual, result_json) VALUES (?, ?, ?, ?, ?)",
                (athlete_id, db.now_iso(), result.model_version, result.residual_observed_minus_predicted, result.model_dump_json()))
    return result


def latest_model(con: sqlite3.Connection, athlete_id: int) -> tuple[int, ModelResult] | None:
    row = con.execute("SELECT id, result_json FROM model_results WHERE athlete_id = ? ORDER BY id DESC LIMIT 1",
                      (athlete_id,)).fetchone()
    return (row["id"], ModelResult.model_validate_json(row["result_json"])) if row else None


def rank_all(con: sqlite3.Connection) -> int:
    """활성 선수 전원을 줄 세워 단계를 새로 매긴다. 반환: batch 번호."""
    n_tiers = len(load_settings(con).tiers)
    ids = [r["id"] for r in con.execute("SELECT id FROM athletes WHERE active = 1 ORDER BY id")]
    entries = []
    for athlete_id in ids:
        latest = latest_model(con, athlete_id) or (None, None)
        residual = latest[1].residual_observed_minus_predicted if latest[1] else None
        entries.append((athlete_id, residual, latest[0]))
    # 관측 − 예측 내림차순, 결과 없음은 맨 뒤. 같으면 선수 id 순(재현 가능)
    entries.sort(key=lambda e: (e[1] is None, -(e[1] or 0.0), e[0]))
    batch = (con.execute("SELECT COALESCE(MAX(batch), 0) FROM tier_assignments").fetchone()[0]) + 1
    n, at = len(entries), db.now_iso()
    for i, (athlete_id, _, result_id) in enumerate(entries):
        tier = n_tiers - (i * n_tiers) // n
        con.execute("INSERT INTO tier_assignments (batch, athlete_id, rank, tier, model_result_id, assigned_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (batch, athlete_id, i + 1, tier, result_id, at))
    return batch


def current(con: sqlite3.Connection, athlete_id: int) -> sqlite3.Row | None:
    """가장 최근 줄 세우기에서 그 선수의 순위·단계."""
    return con.execute("""SELECT rank, tier FROM tier_assignments
                          WHERE athlete_id = ? AND batch = (SELECT MAX(batch) FROM tier_assignments)""", (athlete_id,)).fetchone()
