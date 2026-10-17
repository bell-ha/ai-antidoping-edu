"""모든 테스트는 운영 DB(var/app.sqlite) 대신 임시 파일을 쓴다. people: 관리자 1명 + 선수 몇 명."""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.api import login
from app.program import tiers

ADMIN_CODE = "ADMIN-test0001"


@pytest.fixture(autouse=True)
def _isolated_app_db(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APP_DB", tmp_path / "app.sqlite")
    login._failures.clear()


def _records(start_total: int, last_total: int, n: int) -> list[tuple]:
    out = []
    for k in range(n):
        total = start_total + (start_total * 0.01 * k) if k < n - 1 else last_total
        snatch = round(total * 0.45)
        out.append((f"2025-{k + 1:02d}", "domestic", 72.5, snatch, round(total) - snatch))
    return out


@dataclass
class People:
    athlete_ids: list[int]
    codes: dict[int, str]
    athlete_name: str = "테스트선수일"

    def login(self, who: str = "athlete", index: int = 0) -> TestClient:
        c = TestClient(__import__("app.main", fromlist=["app"]).app)
        code = ADMIN_CODE if who == "admin" else self.codes[self.athlete_ids[index]]
        assert c.post("/api/session", json={"code": code}).status_code == 200
        return c


@pytest.fixture
def people() -> People:
    """선수 5명: 마지막 대회에서 크게 오름 / 조금 오름 / 그대로 / 내려감 / 기록 1개뿐."""
    plans = [(250, 300, 6), (250, 262, 6), (250, 253, 6), (250, 220, 6), (250, 250, 1)]
    names = ["테스트선수일", "테스트선수이", "테스트선수삼", "테스트선수사", "테스트선수오"]
    ids, codes = [], {}
    with db.connect() as con:
        con.execute("INSERT INTO admins (name, code_hash, created_at) VALUES ('관리자', ?, ?)", (db.code_hash(ADMIN_CODE), db.now_iso()))
        for i, ((start, last, n), name) in enumerate(zip(plans, names), start=1):
            code = f"WL-{i:03d}-test"
            cur = con.execute("INSERT INTO athletes (number, name, birth_year, code_hash, created_at) VALUES (?, ?, 2000, ?, ?)",
                              (f"WL-{i:03d}", name, db.code_hash(code), db.now_iso()))
            for r in _records(start, last, n):
                con.execute("""INSERT INTO records (athlete_id, date, competition_category, body_weight, snatch, clean_jerk, entered_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""", (cur.lastrowid, *r, db.now_iso()))
            tiers.compute_model(con, cur.lastrowid)
            ids.append(cur.lastrowid)
            codes[cur.lastrowid] = code
        tiers.rank_all(con)
    return People(ids, codes)
