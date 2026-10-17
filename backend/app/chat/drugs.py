"""질문 속 약 이름 찾기 (D37). "타이레놀 먹어도 돼?", "아세트아미노펜은?"처럼 제품명·성분명 어느 쪽으로 물어도
같은 판정이 근거로 들어가게, 질문의 낱말마다 약물 조회표(drugs.substances)를 찾아본다.
"""

import re

from app.drugs import substances
from app.schemas import CheckResult

# 낱말 끝 조사·어미(긴 것부터). 약 이름 뒤에 붙는 것만 떼어 낸다
_TAIL = sorted(["은", "는", "이", "가", "을", "를", "도", "만", "에", "의", "랑", "이랑", "하고", "과", "와", "이나", "나",
                "에서", "으로", "로", "이요", "요", "이야", "야", "인데", "이에요", "예요", "이면", "면"], key=len, reverse=True)
_SKIP = {"먹어도", "돼", "되나요", "괜찮아", "괜찮나요", "약", "금지", "금지약물", "경기", "시즌", "평소", "선수", "도핑"}
MAX = 3


def _terms(question: str) -> list[str]:
    out = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9\-]+|[가-힣A-Za-z0-9]+", question):
        stem = word
        for t in _TAIL:
            if len(stem) > len(t) + 1 and stem.endswith(t):
                stem = stem[: -len(t)]
                break
        if len(stem) >= 2 and stem not in _SKIP and stem not in out:
            out.append(stem)
    return out


def lookup(question: str) -> list[CheckResult]:
    found: list[CheckResult] = []
    for term in _terms(question):
        result = substances.check(term, "KR", "unknown")
        if result.matched_kind in ("product", "substance", "category") and (result.ingredients or result.candidates):
            found.append(result)
        if len(found) >= MAX:
            break
    return found
