# 교육 레슨

`lessons/<대분류>/<id>.md` — 레슨 하나 = 파일 하나 = 텍스트 설명 + 객관식 퀴즈 1문항. 목표 300개(대분류 13개).
`raw/`는 근거 원본(Git 제외, 목록은 raw/README.md).

```yaml
---
doc_id: G-001            # 대분류 글자 + 번호, 전체에서 유일
category: G 금지목록
order: 1                 # 대분류 안 순서
title: ...
source: KADA             # 근거 기관: WADA · KADA · ADEL
reference: ...           # 근거 문서 이름·조항(raw에 있는 것)
url: ...
version: 2026
roles: [athlete, support]
topic: list              # 열람 화면 묶음: basics · violations · list · testing · roles
summary: ...             # 한 줄 요약
reviewed: false          # 사람이 검토하면 true
quiz:
  question: ...
  choices: [..., ..., ..., ...]   # 4지선다
  answer: 2              # 정답 번호(1부터)
  explanation: ...       # 정답 해설
---
## 소제목     ← 본문은 `## ` 소제목으로 나눔(AI 검색 단위)
```
