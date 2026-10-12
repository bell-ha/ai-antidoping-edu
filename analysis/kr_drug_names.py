"""한글 제품명 → 영문 성분명 조회표 만들기 (약물 확인의 제품 검색).

    python3 analysis/kr_drug_names.py --standard private/sources/hira_standard_code.csv \\
        --ingredient private/sources/hira_ingredient.csv

출처(공공누리 제1유형: 출처표시, 키·로그인 없이 내려받음):
  - 건강보험심사평가원_약가마스터_의약품표준코드 (data.go.kr 15067462, 분기 갱신)
  - 건강보험심사평가원_약가마스터_의약품주성분   (data.go.kr 15067461, 연 갱신)
두 파일을 일반명코드로 이어 붙인다. KADA 검색·약학정보원·Global DRO는 약관상 쓰지 않는다.

출력 data/kr_products.json.gz — 성분 사전과 제품 배열로 정규화한다:
  ingredients : [영문 일반명, …]                         (원문 그대로. 염 제거·매칭은 substances.py가 한다)
  groups      : {일반명코드: [[성분 번호, 투여, 제형], …]}  (투여: 내복·주사·외용·기타 — S9·S3 판정에 쓰임)
  products    : [[한글상품명, 품목기준코드, 전문/일반, 일반명코드, ATC코드], …]
                (ATC는 금지목록에 이름이 없는 같은 계열 성분을 잡는 데 쓰인다 — 예: 목록에 없는 당질코르티코이드)
취소된 품목과 일반명코드가 없는 품목(한약재 등)은 뺀다. 일반명코드는 있는데 주성분 파일에 없는 품목은
groups에 없으므로 서버가 "성분 정보를 찾지 못함"(UNKNOWN)으로 처리한다 — 두 파일의 갱신 시점이 달라서 생긴다.
"""

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "standard": dict(label="건강보험심사평가원_약가마스터_의약품표준코드", url="https://www.data.go.kr/data/15067462/fileData.do"),
    "ingredient": dict(label="건강보험심사평가원_약가마스터_의약품주성분", url="https://www.data.go.kr/data/15067461/fileData.do"),
}
LICENSE = "공공누리 제1유형(출처표시)"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> list[dict]:
    with path.open(encoding="cp949", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--standard", type=Path, required=True)
    ap.add_argument("--ingredient", type=Path, required=True)
    ap.add_argument("--standard-date", default="2026-08-31", help="표준코드 파일의 기준일(데이터셋 페이지 표시)")
    ap.add_argument("--ingredient-date", default="2025-10-31")
    ap.add_argument("--out", type=Path, default=ROOT / "data/kr_products.json.gz")
    args = ap.parse_args()

    names: dict[str, int] = {}
    groups: dict[str, list] = {}
    for r in read(args.ingredient):
        idx = names.setdefault(r["일반명"], len(names))
        row = [idx, r["투여"], r["제형"]]
        if row not in groups.setdefault(r["일반명코드"], []):
            groups[r["일반명코드"]].append(row)

    products: dict[str, list] = {}
    for r in read(args.standard):
        code = r["일반명코드(성분명코드)"]
        if r["취소일자"] or not code:
            continue
        products.setdefault(r["품목기준코드"], [r["한글상품명"], r["품목기준코드"], r["전문일반구분"], code,
                                                r["국제표준코드(ATC코드)"]])

    rows = sorted(products.values())
    missing = sum(1 for p in rows if p[3] not in groups)
    used = {p[3] for p in rows} & set(groups)
    out = dict(
        meta=dict(sources=[dict(SOURCES["standard"], date=args.standard_date, sha256=sha256(args.standard)),
                           dict(SOURCES["ingredient"], date=args.ingredient_date, sha256=sha256(args.ingredient))],
                  license=LICENSE, reviewed=False,
                  counts=dict(products=len(rows), groups=len(used), ingredients=len(names), join_missing=missing)),
        ingredients=list(names),
        groups={k: groups[k] for k in sorted(used)},
        products=rows,
    )
    raw = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode()
    with gzip.GzipFile(args.out, "wb", mtime=0) as f:  # mtime=0: 같은 입력이면 같은 파일
        f.write(raw)
    print(json.dumps(out["meta"]["counts"], ensure_ascii=False), f"{len(raw) / 1e6:.1f}MB → {args.out.stat().st_size / 1e6:.2f}MB gz")


if __name__ == "__main__":
    main()
