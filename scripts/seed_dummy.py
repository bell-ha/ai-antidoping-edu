"""더미 선수 100명 넣기 (D37). 경기 기록만 만들고, 모델을 돌려 단계를 매긴다.

    cd backend && .venv/bin/python ../scripts/seed_dummy.py

- 운영 DB(var/app.sqlite)에 선수가 이미 있으면 아무것도 하지 않는다(덮어쓰지 않음).
- 관리자 1명 + 남자 역도 선수 100명. 로그인 코드는 var/dummy_codes.csv에만 남는다(DB에는 해시만).
- 기록이 1~2개뿐인 선수도 섞는다 → 모델 결과가 없어 가장 낮은 단계.
- 마지막 대회에서 기록이 크게 오른 선수, 내려간 선수도 섞는다 → 줄 세우기가 실제로 갈리게.
"""

import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, db  # noqa: E402
from app.api.admin import new_code  # noqa: E402
from app.program import tiers  # noqa: E402

N = 100
SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모남궁"
GIVEN = ["민준", "서준", "도윤", "예준", "시우", "하준", "주원", "지호", "지후", "준우", "준서", "건우", "도현", "현우", "지훈",
         "우진", "선우", "서진", "민재", "현준", "연우", "유준", "정우", "승우", "승현", "시윤", "준혁", "은우", "지환", "승민",
         "지우", "유찬", "윤우", "민성", "준영", "시후", "진우", "지원", "수호", "재윤", "태윤", "동현", "재민", "민혁", "성민",
         "태민", "영훈", "상우", "경민", "재현", "동하", "형준", "태현", "규민", "성현", "한결", "다온", "이안", "로운", "범수"]
# 2018 IWF 남자 체급 → (대표 계체 체중, 국내 상위권 합계 대략)
CLASSES = [(55, 54.5, 235), (61, 60.6, 260), (67, 66.7, 285), (73, 72.6, 305), (81, 80.5, 325), (89, 88.4, 340),
           (96, 95.5, 350), (102, 101.3, 355), (109, 108.2, 365), (999, 125.0, 385)]
CATEGORIES = ["domestic"] * 5 + ["other_international"] * 2 + ["continent", "world"]


def _months(start: int, end: int, n: int, rng: random.Random) -> list[str]:
    picks = sorted(rng.sample(range(start, end + 1), n))
    return [f"{m // 12}-{m % 12 + 1:02d}" for m in picks]


def _athlete(i: int, rng: random.Random) -> dict:
    name = rng.choice(SURNAMES) + rng.choice(GIVEN)
    birth = rng.randint(1994, 2007)
    _, bw, top = rng.choice(CLASSES)
    level = rng.uniform(0.72, 1.02)
    roll = rng.random()
    n = rng.randint(1, 2) if roll < 0.08 else rng.randint(4, 10)
    last_month = 2026 * 12 + 8  # 2026-09까지
    first_month = max((birth + 15) * 12, 2018 * 12)
    dates = _months(first_month, last_month, n, rng)
    shape = "jump" if roll > 0.88 else "drop" if roll > 0.80 else "steady"
    rows, total = [], top * level * rng.uniform(0.9, 0.97)
    for k, d in enumerate(dates):
        age = int(d[:4]) - birth
        growth = 0.025 if age < 23 else 0.008 if age < 28 else -0.005
        total *= 1 + growth * rng.uniform(0.3, 1.4) + rng.gauss(0, 0.015)
        if k == n - 1 and shape == "jump":
            total *= rng.uniform(1.08, 1.16)
        if k == n - 1 and shape == "drop":
            total *= rng.uniform(0.86, 0.93)
        t = round(total)
        snatch = round(t * rng.uniform(0.43, 0.47))
        rows.append(dict(date=d, competition_category=rng.choice(CATEGORIES), body_weight=round(bw + rng.uniform(-1.8, 0.4), 1),
                         snatch=snatch, clean_jerk=t - snatch))
    return dict(number=f"WL-{i:03d}", name=name, birth_year=birth, records=rows)


def main() -> None:
    rng = random.Random()
    out = config.VAR / "dummy_codes.csv"
    with db.connect() as con:
        if con.execute("SELECT COUNT(*) FROM athletes").fetchone()[0]:
            sys.exit(f"이미 선수가 있어요. 다시 만들려면 {config.APP_DB}를 지우고 실행하세요.")
        codes = []
        admin_code = new_code("ADMIN")
        con.execute("INSERT INTO admins (name, code_hash, created_at) VALUES (?, ?, ?)", ("관리자", db.code_hash(admin_code), db.now_iso()))
        codes.append(("ADMIN", "관리자", "admin", admin_code))
        for i in range(1, N + 1):
            a = _athlete(i, rng)
            code = new_code(a["number"])
            cur = con.execute("INSERT INTO athletes (number, name, birth_year, code_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                              (a["number"], a["name"], a["birth_year"], db.code_hash(code), db.now_iso()))
            for r in a["records"]:
                con.execute("""INSERT INTO records (athlete_id, date, competition_category, body_weight, snatch, clean_jerk, entered_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (cur.lastrowid, r["date"], r["competition_category"], r["body_weight"], r["snatch"], r["clean_jerk"],
                             db.now_iso()))
            tiers.compute_model(con, cur.lastrowid)
            codes.append((a["number"], a["name"], "athlete", code))
        tiers.rank_all(con)
        counts = con.execute("""SELECT tier, COUNT(*) FROM tier_assignments WHERE batch = (SELECT MAX(batch) FROM tier_assignments)
                                GROUP BY tier ORDER BY tier""").fetchall()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("number", "name", "role", "code"), *codes])
    print(f"관리자 1명 + 선수 {N}명. 단계별 인원: {', '.join(f'{t}단계 {c}명' for t, c in counts)}")
    print(f"로그인 코드: {out}")


if __name__ == "__main__":
    main()
