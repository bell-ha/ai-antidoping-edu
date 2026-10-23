"""약물 DB(SQLite): 원천 JSON이 바뀌면 데모에서는 다시 빌드, 시범에서는 시작 거부."""

import sqlite3

import pytest

from app.drugs import drug_db


@pytest.fixture
def db(tmp_path):
    return drug_db.build(tmp_path / "drugs.sqlite")


def test_built_db_is_current_and_round_trips(db):
    assert drug_db.is_current(db)
    data = drug_db.load(db)
    assert data["substances"]["substances"]["pseudoephedrine"]["status"] == "THRESHOLD"
    assert data["kr"]["products"] and data["wada"]["items"]


def test_stale_db_is_rebuilt(db, monkeypatch):
    real = drug_db.source_hashes()
    monkeypatch.setattr(drug_db, "source_hashes", lambda: {**real, "substances": "changed"})
    assert not drug_db.is_current(db)
    drug_db.ensure(path=db)  # 다시 빌드
    assert drug_db.is_current(db)


def test_name_index_is_queryable(db):
    con = sqlite3.connect(db)
    rows = con.execute("select target_type from name_index where norm = 'pseudoephedrine'").fetchall()
    assert ("substance",) in rows
