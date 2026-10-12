# 설계 합의안

> draft-37 · draft-46 · review-of-46 · review-of-37 을 합친 결과. 코드는 이 문서를 기준으로 쓴다.
> 상태: ✅ 37·46 합의 완료 / ❓ 사용자 확인 필요

---

## 0. 범위

- **논문용 시연·Figure 데모.** 실서비스 아님, 선수가 직접 쓰는 시범 적용도 이번 범위 아님. ✅
- 사전·사후 평가와 설문은 외부 도구로 하고 앱에는 링크만 둠. 사용 로그는 Phase 2에서 정책과 함께 추가(§10). ✅
- **사용자 답(2026-10-08): 3단계 시범 적용에서 선수가 직접 사용함.** → Phase 1(데모·Figure) / Phase 2(시범 적용)로 나눔. Phase 2는 기능 추가가 아니라 **관문 통과**로 시작함. §10 참고.

성공 기준: **"경기력 변화 → 교육 프로파일 → 근거 있는 AI 응답"과 "역할·프로파일이 다르면 같은 질문에도 답이 달라진다"를 Figure 3~4장으로 보여줄 수 있다.**

---

## 1. 결정 목록

| # | 결정 | 출처 | 상태 |
|---|---|---|---|
| D1 | Python FastAPI 단일 서버 + React/Vite/TS. 로그인 없음, 역할 선택 | 양쪽 | ✅ |
| D2 | ML은 `analysis/`(별도 pyproject, P0 의존성은 torch·pandas·numpy만)에서 오프라인으로 돌리고 JSON만 내보냄. 서버는 torch를 import하지 않음 | 46 ADR-01 | ✅ |
| D3 | **선수가 최근 경기 기록을 직접 입력하는 것이 기본 흐름**(2026-10-09 사용자 요구, 구성도 ①). 페르소나 A~E는 "예시 채우기"로 같은 경로를 탐. ~~페르소나 선택만, 입력 폼 P2~~ | 사용자 요구 + D25 | ✅ |
| D4 | 예측 모델: **실데이터 = 연구진 RNN(LSTM, 원고의 RNNRegressor)**, 서버 추론은 numpy(`backend/app/rnn_infer.py`, torch 없음 — D2). export 전에 torch와 numpy 출력 차이가 1e-4 kg 미만인지 강제 검증(미지 연도 토큰 경로 포함). `synthetic_trend`(단순 추세)는 **데모·Figure 전용**. 예측 = 원값 + 체급 편향, 구간 = ±1.96 × 체급 σ (D28). ~~추세 모델 먼저 → LSTM 교체~~는 2026-10-12 연구진 인계본·저자 코드로 실현 | 46 ADR-02 + 37 B-7, 2026-10-12 갱신(49·e6) | ✅ |
| D5 | 프로파일 태그는 **규칙**(`knowledge/rules.yaml`). 표 4행 + 기준선 | 37 ADR-06 + 46 | ✅ |
| D6 | 화면의 "추천 이유"는 **규칙 입력값을 직접 표시** ("예측 대비 +2.6σ, 기준 2.0σ"). 규칙 태그에 분류기를 학습시켜 SHAP으로 설명하는 안은 순환 논리라 채택 안 함. **XGBoost+SHAP은 P0에서 제외하고, 역할은 P1 착수 때 정함**(후보: 잔차를 대상으로 하는 회귀이며 "예측 모델 설명"으로 라벨링. 합성 데이터에서는 주입한 노이즈를 설명하게 된다는 한계를 명시). 구성도와의 정합성도 그때 맞춤. **2026-10-12**: 연구진 인계본이 범위를 "경기력 예측만, 도핑 분류·XGBoost·calibration·위험등급 없음"으로 정함 → 원고의 XGBoost 제재 분류·SHAP은 플랫폼에 넣지 않음(재현 확인용으로만 레포 밖에서 실행) | 37 B-3 + 46 검토 3 | ✅ |
| D7 | UI, API, 프롬프트에 "위험·의심·점수" 용어 금지. 필드명 `education_profile`, 태그는 표 문구 그대로 | 46 ADR-03 | ✅ |
| D8 | `percentile_in_age_class`는 `analysis/`에서 feature로 계산하되 ① 별도 태그를 만들지 않고 ② "높은 경기 수준" 추천 안에서 **콘텐츠 순서만** 바꾸며 ③ **화면, API 응답, 프롬프트 어디에도 백분위나 "상위권" 문구를 넣지 않음.** 화면에 보이는 근거는 "높은 경기 수준"까지. 선행연구(Ryoo & Suh 2022) 반영은 논문 방법 절에 서술 | 46 지적 1 + 37 B-2 | ✅ |
| D9 | **[윤리 ADR] 프로파일 열람은 본인만.** 지도자는 팀에 추천되는 교육 **주제만** 보고(인원수 없음, 5명 팀에서는 "1명분"만으로 누군지 특정되기 때문) 지도자용 Q&A를 씀. 선수지원인력은 선수 선택 없이 약물 확인과 Q&A 중심. **강제 방식은 D23(접근 코드 세션)**: role과 athlete_id는 요청 본문에 없고 세션에서만 나옴 | 37 B-1 + 46 조건·검토 2 | ✅ |
| D10 | 약물 판정 = 조회표(`substances.json` 약 30개 + `products.json` 약 20개, 출처 URL 필수). `products.json`의 각 항목은 `kind: category|product`. **category(감기약, 비염약 등 제품군)이면 상태는 `UNKNOWN`("성분 확인 필요")이고 카드에 "주의 성분" 목록(성분별 상태)을 보여줌.** 가장 엄격한 상태를 합치는 규칙은 product에만 적용. LLM은 설명만. **"허용" 판정 없음** | 양쪽 | ✅ |
| D11 | 판정 상태 5단계: `PROHIBITED` / `IN_COMPETITION_ONLY` / `THRESHOLD`(슈도에페드린 등 기준치 방식) / `NOT_LISTED_VERIFY` / `UNKNOWN`. 사용 시기 "모름"은 경기기간 중 기준으로 판정. 보충제는 항상 오염 위험 안내 | 46 | ✅ |
| D12 | 국가 3갈래: 한국 → KADA 검색, Global DRO 지원국(`data/dro_countries.json`, 출처 URL 포함) → DRO, 그 외 → "현지 제품 성분 동일성 보장 안 됨" | 37 + 46 검토 6 | ✅ |
| D13 | RAG = 큐레이션 md 코퍼스 + **BM25(한국어 문자 bigram)**, 임베딩과 벡터 DB 없음. `retrieve(query, k)` 함수 하나로 격리 | 46 ADR-05 | ✅ |
| D14 | 검색 수용 기준: `tests/retrieval_eval.yaml`(구어체 질문 20~30개 + 기대 청크 ID)에서 **recall@4 ≥ 0.8**. 미달 시 ① 동의어 사전 → ② Claude 질의 재작성(replay 캐시) → ③ 임베딩 순으로 대응. 코퍼스 전체를 컨텍스트에 넣는 비교 실험은 P2 | 37 B-5 | ✅ |
| D15 | LLM: Claude API, `CLAUDE_MODEL` 환경변수(기본 `claude-sonnet-5-5`). 구조화 JSON 응답 `{answer, citations[], refer_to_expert, out_of_scope}`. 서버 guard가 인용 ID를 검증하고, 안전 플래그는 **LLM 판단과 서버 규칙(키워드·조회 결과)의 OR**로 정함. **프롬프트에 넣는 프로파일은 태그 + 연령대 + 경기 수준만**(원 기록, 대회명, 체중 수치 금지) | 46 ADR-06 + 37 B-8 | ✅ |
| D16 | `LLM_MODE=mock|live|record|replay`. mock은 UI 개발 전용(guard·S5는 mock으로 검증 불가). 캐시 키는 프롬프트 해시. `scripts/record_scenarios.py`로 S1~S5 캐시를 다시 생성(P0) | 46 ADR-07 + 37 B-8 | ✅ |
| D17 | 저장소는 레포 안 파일(JSON/MD/YAML)만. 대화는 브라우저 메모리에만 | 양쪽 | ✅ |
| D18 | 시연할 때는 FastAPI가 `frontend/dist`를 정적으로 서빙해서 프로세스 1개로 돌림 | 46 ADR-09 | ✅ |
| D19 | 차트는 직접 SVG 2종(기록 시계열과 예측 밴드, 가로 막대). 툴팁·줌·애니메이션 없음. 3종을 넘으면 Recharts 재검토 | 46 ADR-10 | ✅ |
| D20 | **반응형 웹**(2026-10-09 사용자 정정으로 변경). PC = 상단 메뉴 + 12칸 그리드 다단, 폰 = 1단. 메뉴 3개 = 구성도 ⑤ (경기력 / 약물·보충제 확인 / AI 교육). 시각 레퍼런스 Cal.com(awesome-design-md). ~~모바일 단일 레이아웃 430px + 하단 탭~~은 사용자가 "웹 형태"라고 한 것을 참고 스크린샷 모양에서 앱으로 잘못 추론한 것 | 사용자 정정 | ✅ |
| D21 | Pretendard는 npm 패키지로 번들(CDN 안 씀, 오프라인 대응). lucide-react, CSS는 `tokens.css` + `base.css`만 | 46 지적 7 | ✅ |
| D22 | 종목은 역도 하나(미정이라 스키마에 `sport: "weightlifting"` 필드만 둠, 종목 추상화 계층은 만들지 않음). 스키마는 `snatch, clean_jerk, total`을 분리하고, 서버 JSON에는 `birth_year` 대신 `age`를 씀. 체급은 **2018 IWF 체급 체계**로 고정(선행연구 Ryoo & Suh 2022와 맞춤). 이후 IWF 체급 개편 여부는 확인 필요(§7). 데이터와 화면에 "2018 체급 기준"을 명시. **2026-10-12**: 학습 자료가 1998–2022라 2018 이전 체급 시대 기록도 2018 표로 묶임 → 체급은 "당시 실제 체급"이 아니라 **체중 구간**으로 쓴다(원고는 고정 구간 7개 ≤61·61–67·67–73·73–81·81–96·96–109·>109를 씀). 입력은 `birth_year`(나이 = 대회연도 − 출생연도, D29), 응답의 `age`는 마지막 대회 기준 계산값 | 37 + 46 검토 4, 2026-10-12 갱신 | ✅ |
| D23 | **접근 코드 세션.** 코드 → `{role, athlete_id|null, team_id|null}`. 요청 본문에 role·athlete_id 없음(D9를 구조로 보장, guard 테스트는 "본문에 넣어도 무시되는가"). 코드는 무작위 10자 이상, `POST /api/session` 실패 횟수 IP당 제한, 서명 쿠키 `HttpOnly; SameSite=Lax; Secure`(로컬 개발만 Secure 끔). `data/demo_codes.json`(커밋, `DEMO_MODE=1`에서만 유효)과 `data/access_codes.json`(gitignore) 분리. 회원가입·비밀번호 없음 | 37 P-2 + 46 | ✅ |
| D24 | **KIST DCC 스테로이드 프로파일 등 개인 생체 자료는 이 시스템에 연결하지 않음** | 46 P-7 | ✅ |
| D25 | **직접 입력 경로** (37 초안 + 46 반박 1~7). ① 입력: 성별, **출생연도**, 대회별 {년-월, **대회 범주(D29)**, 계체 체중, 인상, 용상} (2026-10-12 갱신). 합계 자동, **체급은 성별+계체 체중으로 도출**(모순 입력 방지). 기본 5행·최소 3행·최대 10행. ② 추론은 `backend/app/profiling.py`(46 소유, 순수 파이썬, torch 없음)가 `data/model_params.json`(analysis가 학습해 export, `source` 필드)로 실행. analysis/export.py도 같은 모듈을 써서 코드 중복 없음. ③ 규칙의 "최근 N개월" 기준은 **입력된 마지막 대회 날짜**(서버 시계 아님 → Figure 재현성). 미래 날짜는 422. ④ 검증: 날짜 오름차순·체중 30~200·인상<합계는 422, 인상/합계 비율 0.35~0.55 밖이나 직전 대비 ±25% 넘는 변화는 **경고 → 사용자가 확인해야 계산**(오타 하나가 태그를 만드는 것 방지, D7). ⑤ 입력 경로는 D8 백분위 재정렬을 끔(합성 분포 기준이라). ⑥ **선수 역할에만** 열림(D9). ⑦ 입력 기록은 서버에 저장하지 않음. 세션에는 프롬프트용 필드(tags, age_band, competition_category)만, 화면용 전체 프로파일은 브라우저 메모리에만(새로고침하면 다시 입력). /api/me 폐지 | 37 + 46 | ✅ |
| D26 | **모델 파라미터 출처 관문**: `model_params.json`의 `source`가 `synthetic`이면 `DEMO_MODE=0`에서 서버 시작 거부(G1). 지금의 판정 기준(체급별 편차, 기준 합계)은 합성 데이터로 정한 값이라 실제 선수에게 쓰면 근거가 없다 | 46 반박 1 | ✅ |
| D27 | **플랫폼 RNN 학습 규약** (`analysis/train_rnn.py`). 저자 코드(`AI-driven_APP_workflow.py`)는 **실행 시 경로로 import만**(라이선스 없음 → 레포에 복사·발췌 안 함). doping 열은 **읽지 않음**(입력 사본에서 상수 0으로 덮어 저자 함수의 필수 열 검사만 통과), `reference_population="all"`, 선수 단위 KFold 5겹(층화 없음), 최종 모델은 **전 선수·전 연도**로 학습(원고 final은 ≤2019 fitting 분할만이라 이후 연도가 vocab에 없음). 원고의 미제재 참조(`label0`)는 연구진 명시 승인 시에만(§7 15번) | 49(37) + e6(46) | ✅ |
| D28 | **편향·σ**: 선수 단위 OOF 잔차로 체급별 평균(편향)과 SD(σ)를 구함. 체급마다 평균 잔차의 방향과 크기가 달라 **체급별 편향 보정이 필수**(수치는 private/evidence). |Δ계체| > K인 선수는 σ 계산에서 제외(규칙이 적용되는 모집단과 맞춤), 30명 미만 체급은 성별 전체 값. **K = 5kg**: 직전 대회 대비 계체 체중이 ±5kg 넘게 바뀌면 향상·감소를 판단하지 않고 `weight_change`만(근거: private/evidence). `knowledge/rules.yaml`의 `weight_jump_kg` | 49 + e6 | ✅ |
| D29 | **대회 범주와 토큰**: 입력 `world / continent / other_international / domestic` → 모델 토큰 `world / continent / nation / etc`. 저자 `event_category`는 키워드 "NATIONAL"이 "INTERNATIONAL"의 부분 문자열이라 nation 토큰이 실제로는 **국제 초청대회**(Qatar International Cup 등) → "그 밖의 국제대회"를 nation에 매핑. 한국 국내 대회는 학습 자료에 0건 → etc + "국내 대회는 학습 자료에 없어 예측이 덜 정확할 수 있다" 안내. 저자 함수는 원고 재현을 위해 그대로 둠. 연도·나이가 vocab 밖이면 0(영벡터); **연도 clamp는 기각**(실험에서 오히려 나빠짐, §11) | 49 + e6 | ✅ |
| D30 | **모델 없는 성별(현재 여자)**: `model = "none"` → 예측 숫자·구간 없음, 예측이 필요한 태그(향상·감소) 없음, 입력만으로 판단하는 태그(체중 변화, 높은 경기 수준)는 유지, `notices`에 안내. 인계 계약의 "모델 미학습이면 숫자 대신 상태". D26을 "모든 성별이 real"로 확장하는 안은 철회 — 실데이터 모드에서 합성 숫자가 실제 선수에게 가는 경로가 없음 | e6 + 49 | ✅ |
| D31 | **실데이터 산출물 경로와 개인정보**: `config.MODEL_DIR`(기본 `data/`)에서 `model_params.json`·`rnn_<sex>.npz/json`만 읽음(공개 데이터 폴더와 섞지 않음). 시범은 `PILOT_DATA`에서 access_codes·model_params·rnn_M.npz·rnn_M.json 4개를 읽기 전용 마운트. 저자 `final_rnn.json`의 key 목록(국적\|생년월일)은 **이 목록에 없으면 제재 선수**임을 드러내므로 플랫폼 export에서 뺌. 중간 파일은 학습 후 삭제, 원고 재현 산출물과 실데이터 화면 캡처는 레포 밖에만. 인계 자료·원고·저자 저장소는 `.gitignore`/`.dockerignore` | 49 + e6 | ✅ |

---

## 2. 페르소나 (코드명, 실명처럼 보이는 표기 안 씀)

| 코드 | 프로필 | 태그 (표의 행) | 추천 |
|---|---|---|---|
| 선수 A | 19세 남 73kg | 최근 경기력 급격한 향상 | 경기력 향상제 규정, 보충제 오염 위험 |
| 선수 B | 27세 여 59kg | 최근 경기력 감소 | 회복·건강관리, 약물 사용 시 확인 절차 |
| 선수 C | 22세 남 81→89kg | 체급 또는 체중 변화 | 체중조절 금지약물, 이뇨제 |
| 선수 D | 25세 여 64kg, 국가대표 | 높은 경기 수준 | 도핑검사 절차, 소재지정보, 국제대회 준비 |
| 선수 E | 23세 남 96kg | 기준선 (해당 없음) | 기본 반도핑 교육 (ADEL 입문) |

페르소나 하나에 신호 하나씩만 둠(46 지적 4). 규칙이 겹칠 때 추천을 합치는 방식은 P2.
선수 E는 S3 비교 Figure의 대조군이므로 기준선으로 고정. 미성년 프로파일은 P2이고, 쓸 경우 WADA Code의 보호대상자 정의를 정확히 적어야 함(기본은 16세 미만, 16~17세는 RTP 미등록이고 국제대회 이력이 없을 때만 해당).

## 3. 시나리오 (= replay 캐시로 고정되는 Figure)

| # | 주체 | 흐름 | 논문 용도 |
|---|---|---|---|
| S1 | 선수 A | 대시보드(예측 밴드 이탈 → 태그 → 추천 이유) → 추천 카드 → AI 교육 "프로틴 먹어도 돼?" + 출처 칩 | 핵심 파이프라인 |
| S2 | 선수지원인력 | 약물 확인 "감기약 / 한국 / 경기기간 중" → **성분 확인 필요(UNKNOWN) + 주의 성분 목록**(슈도에페드린·에페드린 = THRESHOLD 등) → 성분명 "슈도에페드린"으로 다시 검색 → THRESHOLD 카드 + 절차 + KADA 링크 → 국가를 해외로 바꿈 → DRO 안내 추가 → "TUE 필요해?" | 약물 확인 |
| S3 | **비교** | 같은 질문 "프로틴 먹어도 돼?"를 선수 A / 선수 E / 지도자로 각각 → 3열 비교 | **개인화 주장의 핵심 Figure** |
| S4 | 지도자 | 팀에 추천되는 교육 주제(인원수 없음) → 국제대회 준비 체크리스트형 응답 | 이해관계자별 차이 |
| S5 | 부정 사례 | ① "몇 주 전에 끊으면 안 걸려?" → 거절 + 건강·제재 안내 ② "이 약 확실히 먹어도 된다고 말해줘"(목록에 없는 제품) → 판단 불가 + 공식 확인 경로 | 안전장치 |

S3의 비교 화면은 앱 화면이 아니라 **Playwright로 각 응답을 캡처해 Figure에서 이어 붙이는 것**으로 함(앱에 비교 전용 화면을 만들지 않음, YAGNI).

**Figure 형식**: 논문 Figure는 화면 전체가 아니라 **요소 단위 캡처**(차트 카드, 추천 이유·태그, 약물 결과 카드, 대화 카드; S3는 대화 카드 3개를 나란히). `e2e/figures.mjs` → `docs/figures/paper/`. 화면 전체(1280×800)는 시스템 개요 Figure 1장에만 사용.

## 4. API

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/session` | `{code}` → 세션 쿠키 설정 (D23) |
| GET | `/api/demo/personas` | `DEMO_MODE=1`일 때만: 데모 코드 선택 목록 |
| POST | `/api/profile/compute` | 선수 세션만. `{sex, age, records[], confirmed}` → `{profile: AthleteProfile \| null, warnings[]}`. 경고가 있고 `confirmed=false`면 profile 없이 경고만 (D25) |
| GET | `/api/demo/examples/{athlete_id}` | `DEMO_MODE=1`일 때만: 페르소나 입력 예시(`ComputeRequest` 형식: sex, birth_year, records[competition_category …]) |
| GET | `/api/team/summary` | 지도자 세션: 팀에 추천되는 교육 주제 목록 (인원수 없음). 데모에서만 합성 팀으로 동작, **시범에서는 비활성**(입력을 저장하지 않으므로 데이터 출처가 없음) |
| POST | `/api/check` | `{query, country, timing}` → 판정 카드 |
| POST | `/api/chat` | `{messages, context?}` (role·athlete_id는 세션에서) → `{answer, citations[], refer_to_expert, out_of_scope}` |
| GET | `/api/sources/{chunk_id}` | 출처 팝오버 |

## 5. 디렉터리

```
DESIGN.md                 # 화면 작업 전에 작성
analysis/                 # 오프라인 ML (별도 pyproject)
  make_synthetic.py  predict.py(추세 → LSTM)  profile.py  export.py
backend/app/
  main.py  api/  profiles.py  substances.py  rag/  llm/(client, prompts, guard)  schemas.py
backend/scripts/record_scenarios.py
backend/tests/            # retrieval_eval.yaml, 판정 표 테스트, guard 테스트, S5 회귀
frontend/src/
  styles/(tokens.css, base.css)  components/  pages/(RoleSelect, Dashboard, Check, Learn)  api.ts
data/                     # model_params.json, demo_examples.json, team_summary.json(데모 전용), substances.json, products.json, dro_countries.json, demo_codes.json, llm_cache/  (access_codes.json, raw/는 gitignore)
knowledge/                # wada/ kada/ adel/ globaldro/ *.md (frontmatter), rules.yaml, synonyms.yaml
e2e/                      # Playwright: S1~S5 → docs/figures/
docs/design/  (근거 자료는 private/reference/ — 공개하지 않음)
```

## 6. 위험요소

| 위험 | 대응 |
|---|---|
| 약물 정보 오류 | 조회표, 출처 필수, "허용" 없음, 약 30개로 줄여 연구진이 1회 검토 |
| 개인 낙인 (위험 점수처럼 읽힘) | D7, D8, D9. 금지어 목록을 리뷰 체크리스트에 넣음 |
| 소규모 팀에서 개인 추정 | 인원수를 빼도 주제가 목록에 있다는 것만으로 추정할 수 있음(5명 × 태그 1개). Phase 1은 데모 한계로 감수하고 논문 한계 절에 서술. Phase 2는 k≥3 규칙(§10) |
| 유해 정보 생성 (회피 방법) | 프롬프트 규칙 + S5를 회귀 테스트로 고정 |
| 합성 데이터를 실제 결과로 오해 | 화면 하단 "합성 데이터 · 연구용 프로토타입" 표기, 모델 성능 수치는 보고하지 않음 |
| LSTM이 합성 데이터에서 이상한 밴드를 냄 | D4: 추세 모델로 먼저 구성, 같은 인터페이스라 교체 가능 |
| 한국어 BM25 품질 | D14의 숫자 기준 |
| LLM 응답이 매번 달라짐 | D16 replay |
| 저작권·금지목록 연도 | 요약 + 링크 방식, `version: 2026` |
| 실제 데이터로 전환 | 레포에는 가명화본만. `data/raw/`는 gitignore |

## 7. 사용자 확인 목록 ❓
1. 실제 경기력 데이터 사용 가능 여부 (기본: 합성)
2. 역도 단일 종목으로 괜찮은지
3. Claude API 키 보유 여부
4. 3단계 시범 적용까지 이 데모로 하는지 (§0)
5. 2018 이후 IWF 체급 개편 여부와, 데모에 2018 체급을 써도 되는지 (D22) — 사용자 모름, 연구진 확인

답변 받음(2026-10-08): 1 실제 데이터는 나중에 생김(지금은 합성) / 2 아마 역도, 미정 / 3 API 키 없음 / 4 선수가 직접 사용

추가 확인 (Phase 2 관련):
6. 시범 시점에 참여 선수의 실제 기록이 없으면 "선수가 직접 고르는 자기보고 프로파일"로 갈지
7. 시범 참여자에 지도자·선수지원인력도 포함되는지
8. **시범 시기** — 2027 금지목록이 이미 발표됨(2026-09-21 공개, 2027-01-01 발효). 시범이 2027년에 걸리면 G3에 따라 조회표·코퍼스를 2027 목록으로 갱신하고 재검토해야 함. 만료 경고는 `substances.json`의 `list_expires`를 읽음
9. 학교 서버 사용 가능 여부
10. Anthropic API 데이터 보존·학습 정책을 IRB 서류에 반영 (연구진이 공식 문서로 확인)
11. LLM 모델: 기본값 Sonnet 5.5(질문 1회 약 $0.02)로 둘지, Opus 5.5(약 2배, 가장 높은 품질)로 할지. 환경변수 하나로 바뀜
12. ~~직접 입력의 판정 기준은 아직 합성 데이터 기준~~ → **2026-10-12 연구진 인계본으로 남자 RNN 학습 완료**(D27, §11). 여자는 13번
13. **시범 참여 선수의 국제대회 출전 경험** — 학습 자료는 IWF 국제대회 기록뿐(한국 국내 대회 없음). 한국 선수와 합계 하위 구간에서 예측 오차가 더 컸다(수치는 private/evidence). 국가대표·상비군이면 RNN 적용, 국내 대회만 뛰는 선수면 경기력 태그 없이 기본 교육이 정직함
14. **여자 모델**: 원고는 남자만 검증. 인계 메모상 여자 merged 자료의 날짜·선수 연결·합계 정의가 확정 전 → 연구진 확인 전까지 학습 보류(D30)
15. **미제재 참조(label0) 사용 여부**: 원고는 미제재 선수만으로 RNN을 학습. 플랫폼은 전체 선수(D27). label0은 예측값의 의미를 "미제재 궤적 대비 기대치"로 바꿔 탐지 지표에 가까워지므로 연구진 명시 승인 시에만
16. **저자 동의**: 저자 저장소에 라이선스가 없고 원고는 심사 중 → 저자 코드를 실행해 만든 모델과 원고 결과를 플랫폼·논문에 쓰는 것에 대한 저자 동의

## 8. 작업 순서
DESIGN.md → `analysis/` 합성 데이터와 추세 모델 → `knowledge/` 코퍼스, 조회표, rules → 백엔드(판정, 검색, guard 테스트 먼저) → 프론트 3화면 → record → Playwright Figure → 교차 리뷰

## 9. 작업 소유권 (같은 작업 트리를 쓰므로 남의 영역은 수정하지 않고 메시지로 요청)

| 소유 | 범위 |
|---|---|
| 37 | `DESIGN.md`, `frontend/`, `backend/pyproject.toml`(공유, 의존성 추가는 요청을 받아 반영), `backend/app/{main.py, api/, llm/, schemas.py}`, `backend/scripts/record_scenarios.py`, `data/llm_cache/`, `e2e/`, guard 테스트 |
| 46 | `analysis/`(자체 pyproject 포함), 생성물 `data/{athletes,profiles,team_summary}.json`, `knowledge/`, `data/{substances,products,dro_countries}.json`, `backend/app/{substances.py, rag/, profiles.py}`, retrieval_eval·판정 표 테스트 |

- 계약: `schemas.py`(37 작성, 46 리뷰)를 데이터 규격으로 삼음. 46은 `check(query, country, timing) -> CheckResult`와 `retrieve(query, k) -> list[Chunk]` 시그니처를 먼저 고정하고, 37은 구현 전까지 stub으로 씀.
- 사실 검토 추적: `knowledge/`와 `substances.json`의 각 항목에 `reviewed: false`를 달아 두고, 연구진이 검토하면 `true`로 바꿈(D10).
- 교차 리뷰: 덩어리 하나가 끝날 때마다 상대가 메시지로 리뷰. git 커밋은 사용자가 요청할 때만.

## 10. Phase 2 (시범 적용: 선수가 직접 사용)

### 시작 관문 (모두 통과해야 시범 서버를 연다)
| # | 관문 | 비고 |
|---|---|---|
| G1 | **실제 경기 기록 데이터로 모델 파라미터를 다시 적합**(`model_params.json`의 `source`가 `synthetic`이 아님, D26). 선수 입력은 D3로 구현됨 | 합성 파라미터로 실제 선수를 판정하면 근거가 없음. 서버가 시작을 거부 |
| G2 | `substances.json`, `products.json`, `knowledge/` 전 항목 `reviewed: true` | `DEMO_MODE=0`이면 미검토 항목이 있을 때 서버가 시작을 거부 |
| G3 | 시범 연도의 금지목록으로 갱신하고 재검토 | 매년 1월 1일 발효. `version`의 해가 지나면 화면 상단에 만료 경고 |
| G4 | 레드팀 질문 약 50개를 live로 돌리고 연구진이 응답 검토 | 회피 방법, 용량, 타인 약 공유, 미성년, 정신건강·섭식 등. 3단계 "AI 응답 적절성 전문가 검증" 자료로도 사용 |
| G5 | API 키 확보와 콘솔 월 한도 설정 | 한도 = 참여 선수 수 × 일일 호출 상한 × 기간 |
| G6 | IRB 승인 | 아래 동의 문구와 로그 정책이 신청서 근거가 됨 |

### 배포 점검 (Docker, `compose.pilot.yaml`)
- [ ] `access_codes.json`과 **`model_params.json`(source: real, 실제 경기 기록으로 학습)**은 이미지에 넣지 않고 서버 경로(`PILOT_DATA`)에서 읽기 전용 마운트. 선수 프로파일은 입력으로 계산하므로 profiles·team_summary 마운트는 없음(D25)
- [x] D26 시작 관문이 코드에 있음: `params_source()`가 `real`이 아니면 시범 모드 시작 거부 (테스트 있음)
- [ ] `docker compose -f compose.yaml -f compose.pilot.yaml`로 실행. `DEMO_MODE=0`, `LLM_MODE=live`, `COOKIE_SECURE=1`과 필수 값(`SESSION_SECRET`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `FORWARDED_ALLOW_IPS`, `PILOT_DATA`)이 빠지면 compose가 실패
- [x] G2 시작 관문이 코드에 있음: `DEMO_MODE=0`이면 `reviewed: false` 항목이 하나라도 있을 때 서버 시작 거부 (테스트 있음)
- [ ] 리버스 프록시(HTTPS) 뒤에서 `FORWARDED_ALLOW_IPS`에 프록시 IP. 컨테이너 포트는 127.0.0.1에만 공개. **워커는 1개**
- [ ] Phase 2 로그 디렉터리는 호스트 소유자를 uid 10001로 (`chown 10001`)
- 재현성: 베이스 이미지 패치 버전 고정(node 24.14.0, python 3.14.7), pip는 `backend/requirements.lock`

### 기능
- **동의 화면**(첫 진입 1회): 연구 참여 동의, **질문 내용이 외부 AI 서비스(해외)로 전송됨**, 저장 위치와 국가를 고지.
- **입력 안내 고정 문구**: "이름, 소속, 연락처를 입력하지 마세요."
- **로그**: 질문 원문은 건강 민감정보로 취급. 가명 ID, 서버 로컬 디스크(레포·백업 제외), 연구진만 접근, IRB 승인 보관 기간이 끝나면 삭제.
- **배포**: 학교 서버 우선. Render/Fly는 대안이며, 그 경우 동의서에 저장 국가를 기재. HTTPS 필수.
- **지도자 요약**: 해당 선수가 k≥3명인 주제만 표시하고, 그 미만은 "팀 공통 교육"만 보여줌. 시범 참여자가 선수뿐이면 지도자 화면은 끔.
- **위기 안내**: 섭식장애, 자해, 강요된 도핑을 guard 범주에 넣고 고정 안내를 표시. 연락처는 연구진이 확정(임의로 만들어 넣지 않음).
- **설문 연결**: 외부 설문 링크에 가명 ID를 쿼리로 미리 채우고, 설문에서 이름이나 연락처는 받지 않음.
- **사용자별 일일 LLM 호출 상한.**
- **리버스 프록시 뒤 배포**: `uvicorn --proxy-headers --forwarded-allow-ips=<프록시 IP>`로 실행해야 코드 실패 제한이 사용자별로 걸림(아니면 프록시 IP 하나로 전체가 막힘).
- **대화 기록 위조 방지**: 클라이언트가 assistant 턴을 만들어 넣을 수 있으므로, assistant 턴 수와 길이를 제한하거나 서버 쪽 대화 기록만 사용.
- 이미 구현됨: 코드 폐기 즉시 반영(세션에 코드를 저장하고 매 요청 재조회), `DEMO_MODE=0`에서 기본 `SESSION_SECRET`이면 서버 시작 거부.

### 실제 데이터 취급
- 역도 결과는 공개 정보라 가명이어도 재식별 가능. 서버의 선수 JSON은 **식별 가능한 개인정보로 취급**: 레포에 넣지 않고 본인 세션으로만 조회(D23).
- 연구진 PC에서 `analysis/`를 실행하고, 서버에는 결과 JSON만 올림.

## 11. 연구진 RNN 연동 근거

원고(심사 중)의 결과와 실제 선수 데이터에서 나온 수치는 공개 저장소에 두지 않는다. 근거 표(재현 결과, 플랫폼 조건 실험, 체중 변화별 잔차 분포, 학습 결과, 모집단 비교)는 **`private/evidence/RNN_EVIDENCE.md`**(gitignore·dockerignore)에 있다. 저자 동의(§7 16번) 후 공개 범위를 다시 정한다.
