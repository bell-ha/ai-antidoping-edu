"""KADA 원자료(knowledge/drugs/kada/raw) → 가공본(knowledge/drugs/kada/processed).

    backend/.venv/bin/python scripts/build_kada.py

만드는 것
  prohibited_sections_ko_2026.json   2026 금지목록 국문 대역본의 분류 이름(S0~S9, P1, M1~M3와 세부 분류).
                                     약물 판정 카드와 AI 근거에 "S6.B 특정 흥분제"처럼 한글 분류명을 붙이는 데 쓴다.
  documents.json                     받아 둔 KADA 문서 목록: 제목 · 출처 게시판 주소 · 원본 파일 주소 · 바로 보기 주소(view_url)
                                     · sha256 · raw 경로. 교육 레슨의 원문 링크는 view_url(브라우저에서 바로 열림)을 쓴다.
손으로 옮긴 것(이 스크립트가 만들지 않음)
  herbal_medicine_2025.json          한약재 도핑방지 가이드라인 7쪽(이미지 PDF라 글자를 뽑을 수 없어 사람이 옮김)

필요: pdftotext(poppler). 원문 PDF가 바뀌면 이 스크립트를 다시 돌리고 결과를 검토한다.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KADA = ROOT / "knowledge" / "drugs" / "kada"
EDU_RAW = ROOT / "knowledge" / "education" / "raw"
LIST_PDF = KADA / "raw" / "금지목록" / "2026 금지목록 국제표준.pdf"

# 국문판 본문에서 "코드 이름" 줄을 찾는다. 대역본이라 왼쪽은 영문, 오른쪽은 국문 — 국문이 있는 쪽만 쓴다.
HEADING = re.compile(r"(?<![A-Za-z0-9])((?:S\d|P\d|M\d)(?:\.\d)?(?:[.:]?[A-Z])?(?:\.\d)?)[.:]?\s+([가-힣][^.]{1,60}?)(?=\s{2,}|\.{3,}|$|,|:)")
# 목차 줄("M1 － M2 － M3 금지방법")처럼 잘못 잡히거나 줄바꿈으로 잘린 이름만 원문 본문에서 확인해 고친다(쪽은 국문판 기준)
FIXES = {
    "S2": "펩티드호르몬, 성장인자, 관련 약물 및 유사제",  # 쉼표에서 잘림
    "M2": "화학적, 물리적 조작",                # 쉼표에서 잘림
    "M3": "유전자 및 세포 도핑",               # 본문 573행 "M3. 유전자 및 세포도핑"
    "S2.1.3": "GATA 억제제",                    # 이름이 영문으로 시작해 정규식이 놓침(국문판 288행)
    "S2.2.1": "남성의 테스토스테론 자극 펩티드",   # 뒤의 "다음을 포함하나 이에 국한되지 않음" 제외
    "S2.2.2": "부신피질 자극 호르몬과 관련 방출인자",
    "S2.2.3": "성장호르몬, 그 유사제 및 단편",
    "S2.2.4": "성장호르몬 방출인자",
    "S4.2": "항에스트로겐류",
    "S6.A": "비특정 흥분제",
    "S6.B": "특정 흥분제",
}


def sections() -> dict[str, str]:
    text = subprocess.run(["pdftotext", "-layout", str(LIST_PDF), "-"], capture_output=True, text=True, check=True).stdout
    found: dict[str, str] = {}
    for line in text.splitlines():
        for m in HEADING.finditer(line):
            code, name = m.group(1).replace(":", "."), m.group(2).strip()
            if re.search(r"[가-힣]", name) and code not in found and not code.startswith(("M1.", "M2.", "M3.")):
                found[code] = name
    found.update(FIXES)
    order = lambda c: [int(x) if x.isdigit() else x for x in re.split(r"[.]", c[1:])] if c[0] == "S" else [99]
    return dict(sorted(found.items(), key=lambda kv: ({"S": 0, "P": 1, "M": 2}[kv[0][0]], order(kv[0]), kv[0])))


# KADA 게시판 링크 이름이 실제 내용과 다른 파일
TITLE_FIXES = {"test": "(링크 이름 오류 test.PDF) 성장호르몬결핍 아동·청소년 의사 가이드라인 v3.0"}


def documents() -> list[dict]:
    """raw/README.md 표(파일 | 원본 URL | 출처 페이지 | sha256)에서 KADA 문서만."""
    out = []
    for readme, prefix in [(KADA / "raw" / "README.md", "knowledge/drugs/kada/raw/"),
                           (EDU_RAW / "README.md", "knowledge/education/raw/")]:
        for line in readme.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4 or "kada-ad.or.kr" not in cells[1]:
                continue
            path = prefix + cells[0]
            local = ROOT / path
            out.append({
                "title": TITLE_FIXES.get(Path(cells[0]).stem, Path(cells[0]).stem),
                "raw_path": path,
                "board_page": cells[2].split()[0] if cells[2].startswith("http") else None,  # 주소 뒤 설명 글은 뺀다
                "file_url": cells[1],
                # KADA 게시판의 "PDF보기"와 같은 주소: 내려받지 않고 브라우저에서 바로 열린다(레슨 원문 링크로 쓴다)
                "view_url": cells[1] + "&pdfView=true" if "fileDownLoad" in cells[1] else cells[1],
                "sha256": hashlib.sha256(local.read_bytes()).hexdigest() if local.exists() else None,
            })
    return out


def main() -> None:
    out = KADA / "processed"
    out.mkdir(parents=True, exist_ok=True)
    secs = sections()
    (out / "prohibited_sections_ko_2026.json").write_text(json.dumps({
        "source": "KADA 2026 금지목록 국제표준(국영 대역본)", "raw_path": str(LIST_PDF.relative_to(ROOT)),
        "sha256": hashlib.sha256(LIST_PDF.read_bytes()).hexdigest(), "made_by": "scripts/build_kada.py",
        "reviewed": False, "sections": secs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    docs = documents()
    (out / "documents.json").write_text(json.dumps({
        "source": "knowledge/drugs/kada/raw/README.md · knowledge/education/raw/README.md (2026-10-17 수집)",
        "made_by": "scripts/build_kada.py", "documents": docs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"분류 {len(secs)}개, 문서 {len(docs)}개 → {out}")


if __name__ == "__main__":
    main()
