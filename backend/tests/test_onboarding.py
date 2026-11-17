"""온보딩: 선수 첫 안내(한 번만, 처음 기록만 남김)와 관리자 시작 체크리스트(실제 데이터로 체크)."""


def test_intro_shows_once_and_keeps_first_outcome(people):
    c = people.login("athlete")
    assert c.get("/api/athlete/home").json()["onboarding_done"] is False
    assert c.post("/api/athlete/onboarding", json={"outcome": "skipped"}).status_code == 204
    assert c.post("/api/athlete/onboarding", json={"outcome": "finished"}).status_code == 204  # 다시 보기 등: 덮어쓰지 않음
    assert c.get("/api/athlete/home").json()["onboarding_done"] is True
    other = people.login("athlete", 1)
    assert other.get("/api/athlete/home").json()["onboarding_done"] is False  # 선수마다 따로

    admin = people.login("admin")
    row = admin.get(f"/api/admin/athletes/{people.athlete_ids[0]}").json()["athlete"]
    assert row["onboarding"] == "skipped" and row["onboarding_at"]
    csv = admin.get("/api/admin/export/athletes.csv").text
    assert "첫 안내" in csv.splitlines()[0] and "건너뜀" in csv and "아직" in csv


def test_intro_rejects_unknown_outcome_and_admin(people):
    assert people.login("athlete").post("/api/athlete/onboarding", json={"outcome": "maybe"}).status_code == 422
    assert people.login("admin").post("/api/athlete/onboarding", json={"outcome": "finished"}).status_code == 403


def test_checklist_follows_data_and_can_be_hidden(people):
    admin = people.login("admin")
    items = {i["key"]: i for i in admin.get("/api/admin/checklist").json()["items"]}
    assert items["athletes"]["done"] and items["records"]["done"] and items["tiers"]["done"]
    assert not items["settings"]["done"] and not items["reviews"]["done"]

    settings = admin.get("/api/admin/overview").json()["settings"]
    admin.put("/api/admin/settings", json=settings)
    admin.put("/api/admin/reviews/A-001", json={"status": "reviewed", "note": None})
    items = {i["key"]: i for i in admin.get("/api/admin/checklist").json()["items"]}
    assert items["settings"]["done"] and items["reviews"]["done"] and items["reviews"]["detail"].startswith("1 /")

    assert admin.get("/api/admin/checklist").json()["hidden"] is False
    admin.put("/api/admin/checklist", json={"hidden": True})
    assert admin.get("/api/admin/checklist").json()["hidden"] is True
    admin.put("/api/admin/checklist", json={"hidden": False})
    assert admin.get("/api/admin/checklist").json()["hidden"] is False
    assert people.login("athlete").get("/api/admin/checklist").status_code == 403
