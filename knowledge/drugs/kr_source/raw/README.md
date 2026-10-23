# 국내 의약품 목록 원본 (심평원 약가마스터)

`../processed/kr_products.json.gz`(가공본)(국내 의약품 3.3만 개: 제품명 → 성분 · 투여 경로)를 만드는 원본입니다.
공개 자료(공공누리 제1유형, 출처 표시)지만 크기(57MB)와 분기별 갱신 때문에 GitHub에는 올리지 않습니다.
앱은 이 원본이 아니라 `kr_products.json.gz`만 읽습니다.

| 파일 | 받는 곳 | 기준일 | sha256 |
|---|---|---|---|
| `hira_standard_code.csv` | [건강보험심사평가원_약가마스터_의약품표준코드](https://www.data.go.kr/data/15067462/fileData.do) | 2026-08-31 | `2d00689474851d81e6efb2ec4ccff9e271b46c5ba0d3640adfa797dff79368fa` |
| `hira_ingredient.csv` | [건강보험심사평가원_약가마스터_의약품주성분](https://www.data.go.kr/data/15067461/fileData.do) | 2025-10-31 | `2f5c7ce1484480fb50325c71a9b0fb3275f3964ea5a92ecb714aecec674e9739` |

새 버전을 받으면 이 폴더에 같은 이름으로 넣고 목록을 다시 만듭니다(`build_kr_source.py`).
