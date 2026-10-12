"""WADA 금지목록 PDF → 구조화 JSON (D10 조회표의 원천 자료).

    <PyMuPDF가 있는 가상환경>/bin/python analysis/wada_extract.py --pdf <레포 밖>/2026list_en.pdf \\
        --year 2026 --url <원문 URL> --out data/wada/prohibited_list_2026.json

WADA는 금지목록을 PDF로만 배포한다(기계용 형식 없음). 원문 PDF는 레포에 넣지 않고 sha256과 URL만 기록한다.
성분명 목록은 WADA가 선수·관계자에게 공유를 권장하는 사실 정보다.

추출 방식: PyMuPDF로 줄마다 좌표를 읽고, 쪽마다 글머리(•) 위치로 단(2~3단)을 나눠 읽기 순서를 복원한다.
각 항목은 섹션(S0–S9, M1–M3, P1)과 하위 분류(S6.B 등), 상시/경기기간 중, 예외(EXCEPTIONS) 여부,
각주 별표(예: Cathine** → 기준치 각주), 괄호 안 동의어를 가진다.

한계(그대로 출력에 남긴다):
- WADA 목록은 닫힌 목록이 아니다("including, but not limited to", "similar chemical structure").
  여기 없는 이름을 "허용"으로 해석하면 안 된다(D10).
- 기준치·투여 경로·종목 조건은 섹션 원문(section_text)에 있다. 판정 규칙은 substances.check()가 정한다.
- 자동 추출이므로 사람이 검토하기 전에는 reviewed=false.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf

TOP = {  # 섹션 → (상시 여부, 표시명)
    "S0": ("all_times", "Non-approved substances"), "S1": ("all_times", "Anabolic agents"),
    "S2": ("all_times", "Peptide hormones, growth factors, related substances, and mimetics"),
    "S3": ("all_times", "Beta-2 agonists"), "S4": ("all_times", "Hormone and metabolic modulators"),
    "S5": ("all_times", "Diuretics and masking agents"), "M1": ("all_times", "Manipulation of blood and blood components"),
    "M2": ("all_times", "Chemical and physical manipulation"), "M3": ("all_times", "Gene and cell doping"),
    "S6": ("in_competition", "Stimulants"), "S7": ("in_competition", "Narcotics"),
    "S8": ("in_competition", "Cannabinoids"), "S9": ("in_competition", "Glucocorticoids"),
    "P1": ("particular_sports", "Beta-blockers"),
}
BULLET = "•"
TOP_RE = re.compile(r"^(S\d|M\d|P1)(?:\s+([A-Z][A-Z0-9 ,\-–&/()]+))?$")
SUB_RE = re.compile(r"^((?:S|M|P)\d(?:\.[0-9A-Z]+)+)[\.:]?\s*(.*)$")
INLINE_RE = re.compile(r"(?:e\.g\.|including,? but not limited to:?|such as:?)\s*(.*)$", re.I)
STOP_RE = re.compile(r"^(and other substances|and other|NOTE\b|All prohibited substances|The presence)", re.I)
FOOT_RE = re.compile(r"^(\*+)\s+(.*)$")
# 물질 이름이 아닌 설명 문장을 거르는 표현
NOT_NAME = re.compile(r"\b(is|are|prohibited|class|where relevant|administration of|covers|such as|"
                      r"concentration|detection|athlete|sport|substances? (?:with|that)|including)\b", re.I)


def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip(" .;:,")
    name = re.sub(r"^(?:and|or|in|inhaled|e\.g\.)\s+", "", name, flags=re.I)
    return name


def looks_like_name(name: str) -> bool:
    return 2 < len(name) <= 70 and not NOT_NAME.search(name) and not name[:1].isdigit() or \
        bool(re.match(r"^\d+[\-ɑßα]", name)) and len(name) <= 70 and not NOT_NAME.search(name)


def page_lines(page) -> list[tuple[int, float, float, str]]:
    """(단 번호, y, x, 텍스트)를 읽기 순서로. 글머리 위치로 단을 정하고, 글머리 영역 밖은 0단."""
    raw = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            # 글머리표가 "•" 대신 제어 문자(\x07)나 다른 기호로 들어간 쪽이 있다 → "•"로 통일
            t = "".join(s["text"] for s in line["spans"]).replace("\t", " ").replace("\x07", " ")
            t = re.sub(r"^[\x07\u2022\u25cf\u25aa\uf0b7]\s*", BULLET + " ", t.strip()).strip()
            if t:
                raw.append((line["bbox"][1], line["bbox"][0], t))
    # 글머리 기호만 따로 떨어진 줄("•")은 같은 높이의 본문 줄과 합친다. "–" 하위 항목도 글머리로 본다
    merged = []
    for y, x, t in sorted(raw):
        if t == BULLET:
            continue
        if t.startswith("–"):
            t = BULLET + " " + t.lstrip("– ").strip()
        elif any(t2 == BULLET and abs(y2 - y) < 3 and x2 < x for y2, x2, t2 in raw):
            t = BULLET + " " + t
        merged.append((y, x, t))
    raw = merged
    bullets = sorted((y, x) for y, x, t in raw if t.startswith(BULLET))
    if not bullets:
        return [(0, y, x, t) for y, x, t in sorted(raw)]
    # 글머리 영역: y 간격이 45 이상 벌어지면 다른 영역
    regions, cur = [], [bullets[0]]
    for yx in bullets[1:]:
        if yx[0] - cur[-1][0] > 45:
            regions.append(cur); cur = []
        cur.append(yx)
    regions.append(cur)
    out = []
    used = set()
    spans = []
    for reg in regions:
        starts = sorted({round(x / 10) * 10 for _, x in reg})
        cols = []
        for s in starts:  # 가까운 시작점은 같은 단
            if not cols or s - cols[-1] > 40:
                cols.append(s)
        y0, y1 = reg[0][0] - 2, reg[-1][0] + 40
        spans.append((y0, y1, cols))
    heading = lambda t: bool(TOP_RE.match(t) or SUB_RE.match(t) or t.upper().startswith(("EXCEPTION", "NOTE")))
    for y0, y1, cols in spans:
        # 제목 줄은 단에 넣지 않는다 → 영역 뒤로 정렬돼 오른쪽 단 항목이 다음 섹션으로 넘어가지 않음
        inside = [(y, x, t) for y, x, t in raw if y0 <= y <= y1 and (y, x, t) not in used and not heading(t)]
        # 영역 안이라도 단 시작보다 왼쪽에서 시작하는 긴 문단(예: "and other substances…")은 영역 끝에 둔다
        for c_i, c in enumerate(cols):
            nxt = cols[c_i + 1] if c_i + 1 < len(cols) else 10_000
            for y, x, t in sorted(inside):
                if c - 5 <= x < nxt - 5:
                    out.append((c_i, y, x, t)); used.add((y, x, t))
    rest = [(0, y, x, t) for y, x, t in raw if (y, x, t) not in used]
    # 읽기 순서: 영역 위 문단 → 영역(단별) → 영역 아래 문단, 영역이 여러 개면 y 순서로 끼워 넣는다
    blocks = [(y, [(0, y, x, t)]) for _, y, x, t in rest]
    for y0, y1, _ in spans:
        blocks.append((y0, [r for r in out if y0 <= r[1] <= y1]))
    ordered = []
    for _, rows in sorted(blocks, key=lambda b: b[0]):
        ordered.extend(rows)
    return ordered


def join_line(prev: str, nxt: str) -> str:
    """줄바꿈 하이픈: 앞 글자가 숫자·괄호면 화학명 하이픈이라 유지, 글자면 단어가 쪼개진 것이라 제거."""
    if prev.endswith("-") and nxt[:1].islower() and not re.search(r"[\d\)\]]-$", prev):
        return prev[:-1] + nxt
    return f"{prev} {nxt}" if prev and not prev.endswith("-") else prev + nxt


def split_top(text: str, seps: str) -> list[str]:
    """괄호 밖의 구분자로만 자른다(화학명 안의 쉼표 보호). 숫자 사이 쉼표(3,17)도 자르지 않는다."""
    parts, depth, cur = [], 0, ""
    for i, ch in enumerate(text):
        depth += ch in "([" ; depth -= ch in ")]"
        if depth == 0 and ch in seps and not (ch == "," and i + 1 < len(text) and text[i + 1].isdigit()):
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def parse_item(text: str) -> dict | None:
    text = re.sub(r"\s+", " ", text.lstrip(BULLET).strip()).rstrip(".;,")
    stars = 0
    m = re.match(r"^([^*(\[]*?)(\*+)", text)
    if m:
        stars = len(m.group(2))
    text = text.replace("*", "")
    m = re.match(r"^([^(\[]+?)\s*[\(\[](.*)[\)\]]\s*$", text)
    name, inner = (m.group(1), m.group(2)) if m else (text, "")
    name = clean_name(name)
    if not looks_like_name(name):
        return None
    synonyms = [clean_name(x) for x in split_top(inner, ",;") if looks_like_name(clean_name(x))] if inner else []
    return dict(name=name, synonyms=synonyms, footnote_stars=stars)


def extract(pdf: Path) -> tuple[list[dict], dict]:
    """항목: kind = prohibited | threshold | exception, condition = 짧은 조건 문장(원문 발췌)."""
    doc = pymupdf.open(pdf)
    items, sections = [], {}
    st = dict(top=None, sub=None, sub_title=None, exceptions=False, p1_sports=True)
    buf = dict(bullet=None, inline=None, foot=None)
    footnotes: dict[str, dict[int, str]] = {}

    def add(text, page, kind_hint, condition=None):
        it = parse_item(text)
        if not it or not st["top"]:
            return
        if st["top"] == "P1" and st["p1_sports"]:
            sections["P1"].setdefault("sports", []).append(it["name"]); return
        items.append(dict(**it, section=st["top"], subsection=st["sub"], subsection_title=st["sub_title"],
                          prohibited=TOP[st["top"]][0], kind="exception" if st["exceptions"] else kind_hint,
                          condition=condition, page=page + 1))

    def flush(page):
        b, inl, ft = buf["bullet"], buf["inline"], buf["foot"]
        buf.update(bullet=None, inline=None, foot=None)
        if ft:
            footnotes.setdefault(st["top"], {})[ft[0]] = re.sub(r"\s+", " ", ft[1]).strip()
        if b:
            text = re.sub(r"\s+", " ", b.lstrip(BULLET)).strip()
            cond = text[:160] if st["exceptions"] or ":" in text else None
            head, sep, rest = text.partition(":")
            im = INLINE_RE.search(text)
            if st["exceptions"]:
                # "Inhaled salbutamol: maximum …" / "Drospirenone; pamabrom; and topical … (e.g. dorzolamide, brinzolamide)"
                parts = split_top(head if sep and not im else text, ";")
                for part in parts:
                    sub_im = re.search(r"\(e\.g\.\s*([^)]*)\)", part)
                    adm = re.search(r"administration of ([A-Za-z][\w\-]+)", part)
                    if sub_im:
                        names = split_top(sub_im.group(1), ",")
                    elif adm and "carbonic" not in adm.group(1):
                        names = [adm.group(1)]
                    else:
                        names = split_top(part, ",") if "(" not in part else [part]
                    for n in names:
                        add(n, page, "exception", cond)
            elif im and im.group(1):
                for n in split_top(re.sub(r"\band\b", ",", im.group(1)), ",;"):
                    add(n, page, "prohibited", text[:160])
            else:
                add(text, page, "prohibited")
            # 괄호 속 예시도 각각 항목으로: "Anti-activin receptor IIB antibodies (e.g. bimagrumab)"
            if not st["exceptions"]:
                for eg in re.findall(r"\(e\.g\.\s*([^)]*)\)", text):
                    for n in split_top(re.sub(r"\band\b", ",", eg), ",;"):
                        add(n, page, "prohibited", text[:160])
        if inl:
            for n in split_top(re.sub(r"\band\b", ",", inl), ",;"):
                add(n, page, "prohibited")

    for page_no, page in enumerate(doc):
        if page_no < 3:
            continue
        for _, y, x, t in page_lines(page):
            if t.strip().upper() == "INDEX":
                flush(page_no)
                return finish(items, sections, footnotes)
            if t.isdigit() or (y < 30 and not TOP_RE.match(t)):  # 쪽 번호·머리말 (쪽 맨 아래 각주는 남긴다)
                continue
            mt = TOP_RE.match(t)
            if mt:
                flush(page_no)
                if mt.group(1) != st["top"]:
                    st.update(top=mt.group(1), sub=None, sub_title=None, exceptions=False, p1_sports=True)
                    sections.setdefault(st["top"], dict(title=TOP[st["top"]][0 + 1], prohibited=TOP[st["top"]][0]))
                continue
            if st["top"] is None:
                continue
            mf = FOOT_RE.match(t)
            if mf:
                flush(page_no); buf["foot"] = [len(mf.group(1)), mf.group(2)]; continue
            if buf["foot"] is not None and not t.startswith(BULLET) and not SUB_RE.match(t):
                buf["foot"][1] += " " + t; continue
            m = SUB_RE.match(t)
            if m and m.group(1).startswith(st["top"]):
                flush(page_no)
                st.update(sub=m.group(1), sub_title=m.group(2).split(" e.g.")[0].strip(" .:")[:80], exceptions=False)
                im = INLINE_RE.search(t)
                if m.group(1).count(".") >= 2 and m.group(2):  # S4.4.2 Insulins and insulin-mimetics, e.g. …
                    add(re.split(r",?\s*(?:e\.g\.|including)", m.group(2))[0], page_no, "prohibited")
                if im and im.group(1):
                    buf["inline"] = im.group(1)
                continue
            if t.upper().startswith("EXCEPTION"):
                flush(page_no); st["exceptions"] = True; continue
            if st["top"] == "P1" and "not limited to" in t.lower():
                flush(page_no); st["p1_sports"] = False; continue
            if t.startswith(BULLET):
                flush(page_no); buf["bullet"] = t; continue
            if STOP_RE.match(t):
                flush(page_no); continue
            if buf["bullet"] is not None:
                buf["bullet"] = join_line(buf["bullet"], t)
            elif buf["inline"] is not None:
                buf["inline"] = join_line(buf["inline"], t) if buf["inline"] else t
            else:
                im = INLINE_RE.search(t)
                if im:
                    flush(page_no); buf["inline"] = im.group(1)
    flush(len(doc) - 1)
    return finish(items, sections, footnotes)


def finish(items: list[dict], sections: dict, footnotes: dict) -> tuple[list[dict], dict]:
    """각주를 항목에 반영: 기준치(greater than … per millilitre) → threshold, 모니터링(not considered Prohibited) →
    이름들을 exception으로 추가, 그 밖(예: Epinephrine 국소 사용)은 condition으로만."""
    for sec, notes in footnotes.items():
        sections[sec]["footnotes"] = {"*" * k: v[:300] for k, v in sorted(notes.items())}
        for it in items:
            if it["section"] == sec and it["footnote_stars"] in notes:
                note = notes[it["footnote_stars"]]
                if re.search(r"greater than .*per millilitre", note, re.I):
                    it["kind"] = "threshold"
                it["condition"] = note[:300]
        for k, note in notes.items():
            if re.search(r"not considered Prohibited", note, re.I):
                names = note.split(":")[0]
                for n in split_top(re.sub(r"\band\b", ",", names), ","):
                    items.append(dict(name=clean_name(n), synonyms=[], footnote_stars=k, section=sec,
                                      subsection=None, subsection_title="Monitoring Program", prohibited="no",
                                      kind="exception", condition=note[:300], page=None))
    return items, sections


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--year", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    items, sections = extract(args.pdf)
    seen, unique = set(), []
    for it in items:  # 같은 섹션·이름 중복 제거(쪽 넘김으로 반복될 때)
        key = (it["section"], it["subsection"], it["name"].lower(), it["kind"])
        if key not in seen:
            seen.add(key); unique.append(it)
    out = dict(
        list_version=args.year, list_effective=f"{args.year}-01-01", list_expires=f"{args.year}-12-31",
        source_url=args.url,
        source_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        extracted_by="analysis/wada_extract.py (PyMuPDF 좌표 기반 자동 추출)", reviewed=False,
        caution="닫힌 목록이 아님: 여기 없는 이름을 허용으로 해석하지 말 것. 조건은 항목의 condition과 sections[*].footnotes.",
        section_conditions={
            "S3": "흡입 살부타몰·포르모테롤·살메테롤·빌란테롤은 용량 한도 안에서 예외(항목 condition 참고).",
            "S9": "주사·경구·직장 투여는 경기기간 중 금지, 흡입·국소 등 다른 경로는 허가 용량·적응증 안에서 금지 아님.",
            "P1": "지정 종목에서만 경기기간 중 금지(종목 목록: sections.P1.sports). 역도는 해당 없음.",
        },
        counts={s: {k: sum(1 for i in unique if i["section"] == s and i["kind"] == k)
                    for k in ("prohibited", "threshold", "exception")} for s in sections},
        sections=sections, items=unique,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], ensure_ascii=False), "총", len(unique))


if __name__ == "__main__":
    main()
