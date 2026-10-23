# knowledge — 앱이 쓰는 자료

두 갈래뿐이다: **약물(drugs)** 은 약물 판정 규칙이 읽고, **교육(education)** 은 선수가 듣고 질문하기가 근거로 쓴다.
출처마다 `raw/`(받은 원본 그대로, Git 제외 — 목록·원본 주소·sha256은 각 `raw/README.md`)와 `processed/`(앱이 읽는 가공본)로 나눈다.

```
knowledge/
├── drugs/
│   ├── wada/        raw: 2026 금지목록 PDF(영문)
│   │                processed: prohibited_list_2026.json(성분 443개) · wada_manual_2026.yaml(자동 추출 손 보정)
│   ├── kada/        raw: 2026 금지목록 국영 대역 · 한약재 가이드라인 · 보충제 안내자료(실태조사 보고서) · TUE 질환별 가이드 · TUE 국제표준
│   │                processed: prohibited_sections_ko_2026.json(분류 한글 이름) · documents.json(문서 목록·게시판 주소)
│   │                           · herbal_medicine_2025.json(한약재 11종, 사람이 옮김)
│   ├── kr_source/   raw: 심평원 약가마스터 CSV
│   │                processed: kr_products.json.gz(국내 제품명 → 성분)
│   └── curated/     사람이 직접 만든 조회표: substances.json(자주 묻는 성분 58개) · products.json(제품·제품군 18개)
└── education/
    ├── lessons/     교육 300개(A~M 13개 대분류). 형식은 education/README.md
    └── raw/         레슨의 근거 원문: WADA ISE·Athlete Curriculum · ADEL 목차 · KADA 교육자료 21건
```

## raw → processed 만드는 법

| 가공본 | 만드는 것 | 원본이 바뀌면 |
|---|---|---|
| `drugs/wada/processed/` | `scripts/build_wada.py`(PDF 자동 추출 + 손 보정 yaml) | 해마다 새 금지목록 → 다시 추출하고 `docs/WADA-REVIEW.md`로 사람 검토 |
| `drugs/kada/processed/` 분류 이름·문서 목록 | `scripts/build_kada.py` | 다시 실행 |
| `drugs/kada/processed/herbal_medicine_2025.json` | 사람이 옮김(이미지 PDF) | 가이드라인 7쪽을 보고 고침 |
| `drugs/kr_source/processed/` | `scripts/build_kr_source.py` | 심평원 파일을 새로 받아 다시 실행 |
| `education/lessons/` | 사람(과 AI)이 원문을 읽고 씀 | 원문이 바뀐 레슨을 고침 |

약물 가공본과 조회표는 서버가 시작할 때 `var/drugs.sqlite`(약물 DB)로 묶인다(`backend/app/drugs/drug_db.py`). 원본 파일이 바뀌면 데모에서는 다시 만들고, 시범 운영에서는 시작을 거부한다.

## 검토

모든 항목이 `reviewed: false`다. 사람이 원문과 대조해 확인한 뒤 `true`로 바꾼다. 하나라도 `false`면 시범 운영 모드(`DEMO_MODE=0`)는 켜지지 않는다.
