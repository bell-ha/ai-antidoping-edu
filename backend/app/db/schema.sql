-- 운영 DB (var/app.sqlite, Git 제외).
-- 선수 이름·번호·출생연도·경기 기록·질문 원문이 들어간다. 로그인 코드는 HMAC 해시만.
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    code_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS athletes (
    id INTEGER PRIMARY KEY,
    number TEXT NOT NULL UNIQUE,       -- WL-001
    name TEXT NOT NULL,
    sex TEXT NOT NULL DEFAULT 'M',     -- 지금은 남자 모델만
    birth_year INTEGER NOT NULL,
    code_hash TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    date TEXT NOT NULL,                -- YYYY-MM
    competition_category TEXT NOT NULL,
    body_weight REAL NOT NULL,
    snatch INTEGER NOT NULL,
    clean_jerk INTEGER NOT NULL,
    entered_by INTEGER REFERENCES admins(id),
    entered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_athlete ON records (athlete_id, date);

-- 계산할 때마다 한 줄(나중에 "왜 이 단계였는지" 다시 볼 수 있게)
CREATE TABLE IF NOT EXISTS model_results (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    computed_at TEXT NOT NULL,
    model_version TEXT NOT NULL,
    residual REAL,                     -- 관측 − 예측(kg). 없으면 NULL
    result_json TEXT NOT NULL          -- ModelResult 전체
);
CREATE INDEX IF NOT EXISTS model_results_athlete ON model_results (athlete_id, id);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    changed_at TEXT NOT NULL,
    changed_by INTEGER REFERENCES admins(id),
    tiers_json TEXT NOT NULL           -- ProgramSettings.tiers
);

-- 줄 세우기 한 번 = 같은 batch 번호로 전원
CREATE TABLE IF NOT EXISTS tier_assignments (
    id INTEGER PRIMARY KEY,
    batch INTEGER NOT NULL,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    rank INTEGER NOT NULL,
    tier INTEGER NOT NULL,
    model_result_id INTEGER REFERENCES model_results(id),
    assigned_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tier_batch ON tier_assignments (batch, athlete_id);

CREATE TABLE IF NOT EXISTS lesson_assignments (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    lesson_id TEXT NOT NULL,
    week_start TEXT NOT NULL,          -- 배정된 주의 월요일(KST)
    completed_at TEXT,
    UNIQUE (athlete_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    lesson_id TEXT NOT NULL,
    context TEXT NOT NULL,             -- lesson | surprise | review(오답 다시 풀기)
    choice INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS quiz_athlete ON quiz_attempts (athlete_id, at);

-- 갑자기 퀴즈: 하루 첫 접속 때 뽑아 두고, 답하면 answered_at
CREATE TABLE IF NOT EXISTS surprise_quizzes (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    lesson_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    answered_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER REFERENCES athletes(id),   -- 관리자가 시험 삼아 물은 것은 NULL
    day TEXT NOT NULL,
    at TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    kind TEXT NOT NULL,                -- chat_llm | chat_fixed | chat_server | chat_limit
    citations_json TEXT
);
CREATE INDEX IF NOT EXISTS chat_athlete_day ON chat_logs (athlete_id, day);

CREATE TABLE IF NOT EXISTS visits (
    athlete_id INTEGER NOT NULL REFERENCES athletes(id),
    day TEXT NOT NULL,
    first_at TEXT NOT NULL,
    PRIMARY KEY (athlete_id, day)
);
