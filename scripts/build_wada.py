"""WADA 금지목록 PDF → 구조화 JSON (약물 판정 조회표의 원천 자료).

    <PyMuPDF·PyYAML이 있는 가상환경>/bin/python scripts/build_wada.py --pdf knowledge/drugs/wada/raw/2026list_en_final_clean_september_2025.pdf \\
        --year 2026 --url <원문 URL> --manual knowledge/drugs/wada/processed/wada_manual_2026.yaml --out knowledge/drugs/wada/processed/prohibited_list_2026.json

WADA는 금지목록을 PDF로만 배포한다(기계용 형식 없음). 원문 PDF는 레포에 넣지 않고 sha256과 URL만 기록한다.
성분명 목록은 WADA가 선수·관계자에게 공유를 권장하는 사실 정보다.

추출 방식: PyMuPDF로 줄마다 좌표를 읽고, 쪽마다 글머리(•) 위치로 단(2~3단)을 나눠 읽기 순서를 복원한다.
각 항목은 섹션(S0–S9, M1–M3, P1)과 하위 분류(S6.B 등), 상시/경기기간 중, 예외(EXCEPTIONS) 여부,
각주 별표(예: Cathine** → 기준치 각주), 괄호 안 동의어를 가진다.
문장형 섹션(S0, M1–M3), P1 종목, 섹션 NOTE, 흔한 별칭은 손 보정 파일(--manual)에서 온다(항목마다 source 표시).
원문 끝의 INDEX 표제어도 그대로 담는다 → 테스트가 "INDEX의 모든 물질이 조회되는지"를 확인한다.

한계(그대로 출력에 남긴다):
- WADA 목록은 닫힌 목록이 아니다("including, but not limited to", "similar chemical structure").
  여기 없는 이름을 "허용"으로 해석하면 안 된다.
- 판정 규칙은 substances.check()가 정한다.
- 자동 추출이므로 사람이 검토하기 전에는 reviewed=false.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf
import yaml

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
# "S1", "S2 PEPTIDE HORMONES,", "M1. MANIPULATION OF BLOOD …" (M 섹션은 코드 뒤에 점이 있다)
TOP_RE = re.compile(r"^(S\d|M\d|P1)\.?(?:\s+([A-Z][A-Z0-9 ,\-–&/()]+))?$")
SUB_RE = re.compile(r"^((?:S|M|P)\d(?:\.[0-9A-Z]+)+)[\.:]?\s*(.*)$")
EG_RE = re.compile(r"\be\.g\.\s*")
# 본문(글머리 밖)에서 이름 나열을 여는 표현. 맨 "e.g."는 문장 속 예시(투여 경로 등)라 열지 않는다
LIST_OPEN_RE = re.compile(r"(?:including,? but not limited to:?|such as:?)\s*(.*)$", re.I)
STOP_RE = re.compile(r"^(and other substances|and other|NOTE\b|All\b|The following\b|The presence|A stimulant not expressly)", re.I)
FOOT_RE = re.compile(r"^(\*+)\s+(.*)$")
# 물질 이름이 아닌 설명 문장을 거르는 표현
NOT_NAME = re.compile(r"\b(is|are|prohibited|class|where relevant|administration of|covers|such as|"
                      r"concentration|detection|athlete|sport|substances? (?:with|that)|including)\b", re.I)
# 이름 뒤에 붙는 분류 꼬리: "Fentanyl and its derivatives" → Fentanyl
TAIL_RE = re.compile(r",?\s+(?:and\s+(?:its|their)\s+(?:agonist\s+)?(?:ana-?\s*logues|derivatives|mimetics|releasing factors)"
                     r"|its analogues and fragments|and insulin-mimetics)\s*$", re.I)
INVISIBLE = re.compile(r"[​‌‍⁠﻿­]")


def norm(s: str) -> str:
    """손 보정 이름 대조용(앱의 normalize와 같은 방향): 소문자, 공백·하이픈·괄호 제거, 그리스 문자 접기."""
    s = INVISIBLE.sub("", s).lower().replace("ɑ", "a").replace("α", "a").replace("ß", "b").replace("β", "b")
    return re.sub(r"[\s\-_()\[\]’',]", "", s)


def clean_name(name: str) -> str:
    name = INVISIBLE.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" .;:,")
    name = re.sub(r"(\w|[ɑßα]) ?- (?=[a-z])", r"\1-", name)  # 줄바꿈으로 생긴 "gonadotrophin- releasing", "ɑ -pyrrolidino…"
    name = re.sub(r"([ɑßα]) -", r"\1-", name)
    name = re.sub(r"^(?:and|or|in|inhaled|e\.g\.)\s+", "", name, flags=re.I)
    name = TAIL_RE.sub("", name).strip(" .;:,")
    return name


def looks_like_name(name: str) -> bool:
    if NOT_NAME.search(name) or name.count(" ") > 8 or re.match(r"^(its|their)\b", name, re.I):
        return False
    if name[:1].isdigit():  # "1,3-dimethylbutylamine", "2,4-DNP", "17ɑ-methyl…", "1,3 DMAA"
        return bool(re.match(r"^\d+(?:,\d+)*\s?[\-ɑßα\s]", name)) and len(name) <= 200
    return 2 < len(name) <= 200


def page_lines(page) -> list[tuple[int, float, float, str]]:
    """(단 번호, y, x, 텍스트)를 읽기 순서로. 글머리가 여러 단으로 놓인 영역만 단별로 읽고, 나머지는 y 순서."""
    raw = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            # 글머리표가 "•" 대신 제어 문자(\x07)나 다른 기호로 들어간 쪽이 있다 → "•"로 통일
            t = "".join(s["text"] for s in line["spans"]).replace("\t", " ").replace("\x07", " ")
            t = re.sub(r"^[\x07•●▪]\s*", BULLET + " ", t.strip()).strip()
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
    spans = []
    for reg in regions:
        starts = sorted({round(x / 10) * 10 for _, x in reg})
        cols = []
        for s in starts:  # 가까운 시작점은 같은 단
            if not cols or s - cols[-1] > 40:
                cols.append(s)
        if len(cols) > 1:  # 한 단짜리 영역은 y 순서 그대로가 읽기 순서다
            spans.append((reg[0][0] - 2, reg[-1][0] + 40, cols))
    heading = lambda t: bool(TOP_RE.match(t) or SUB_RE.match(t) or t.upper().startswith(("EXCEPTION", "NOTE")))
    out, used = [], set()
    for y0, y1, cols in spans:
        # 제목 줄은 단에 넣지 않는다 → 영역 뒤로 정렬돼 오른쪽 단 항목이 다음 섹션으로 넘어가지 않음
        inside = [(y, x, t) for y, x, t in raw if y0 <= y <= y1 and (y, x, t) not in used and not heading(t)]
        # 단 시작보다 왼쪽에서 시작하는 긴 문단(예: "and other substances…")은 영역 밖으로 남는다
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
    """줄바꿈 하이픈: 앞 글자가 숫자·괄호·그리스 문자면 화학명 하이픈이라 유지, 글자면 단어가 쪼개진 것이라 제거."""
    if prev.endswith("-") and nxt[:1].islower() and not re.search(r"[\d\)\]ɑßα]\s?-$", prev):
        return prev[:-1] + nxt
    return f"{prev} {nxt}" if prev and not prev.endswith("-") else prev + nxt


def split_top(text: str, seps: str) -> list[str]:
    """괄호 밖의 구분자로만 자른다(화학명 안의 쉼표 보호). 숫자 사이 쉼표(3,17 / 3ß, 17ß)도 자르지 않는다."""
    parts, depth, cur = [], 0, ""
    for i, ch in enumerate(text):
        depth += ch in "([" ; depth -= ch in ")]"
        chem_comma = ch == "," and (text[i + 1:i + 2].isdigit()  # 5-N,6-N / 3,17
                                    or (re.match(r" \d", text[i + 1:i + 3]) and re.search(r"[\dɑßα]$", cur)))  # 3ß, 17ß
        if depth == 0 and ch in seps and not chem_comma:
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def split_names(text: str) -> list[str]:
    """이름 나열: 쉼표·세미콜론·"and"로 자르되 괄호 안은 보호."""
    return split_top(re.sub(r"\s+and\s+", ", ", text), ",;")


def eg_lists(text: str) -> tuple[str, list[str]]:
    """"Head (e.g. a, b and c)", "Head [e.g. …]", "Head, e.g. a and b" → (Head, 예시 이름들).
    예시는 "e.g."를 연 괄호가 닫히는 곳까지만(꼬리 ")" "]"가 이름에 붙지 않게)."""
    names, head = [], text
    for m in reversed(list(EG_RE.finditer(text))):
        before, after = text[:m.start()], text[m.end():]
        depth, opener = 0, None
        for i in range(len(before) - 1, -1, -1):  # e.g. 앞의 닫히지 않은 괄호
            depth += before[i] in ")]"; depth -= before[i] in "(["
            if depth < 0:
                opener = i; break
        if opener is not None:
            d, end = 0, len(after)
            for j, ch in enumerate(after):
                d += ch in "(["; d -= ch in ")]"
                if d < 0:
                    end = j; break
            names = split_names(after[:end]) + names
            text = text[:opener].rstrip() + " " + after[end + 1:].lstrip()  # 예시 괄호를 빼고 다시 본다
        else:
            names = split_names(after) + names
            text = before
    head = re.sub(r"[\s,(\[]+$", "", text).strip()
    return head, names


def parse_item(text: str) -> tuple[dict | None, list[str]]:
    """(항목, 괄호 속 예시 이름들). 이름 끝의 바깥 괄호만 동의어로 본다(화학명 안 괄호 보호)."""
    text = INVISIBLE.sub("", re.sub(r"\s+", " ", text.lstrip(BULLET).strip())).rstrip(".;,")
    stars = 0
    m = re.match(r"^([^*(\[]*?)(\*+)", text)
    if m:
        stars = len(m.group(2))
    text = text.replace("*", "").strip()
    text, examples = eg_lists(text)
    text = clean_name(text)
    name, inner = text, ""
    if text.endswith((")", "]")):
        depth = 0
        for i in range(len(text) - 1, -1, -1):
            depth += text[i] in ")]"; depth -= text[i] in "(["
            if depth == 0:
                if i > 0:
                    name, inner = text[:i].strip(), text[i + 1:-1]
                break
    elif "(" in text and ")" in text:  # 중간 괄호: "cannabis (hashish, marijuana) and cannabis products"
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*(.*)$", text)
        if m:
            name, inner = f"{m.group(1)} {m.group(3)}".strip(), m.group(2)
    name = clean_name(name)
    if not looks_like_name(name):
        return None, examples
    synonyms = []
    for x in split_top(inner, ",;") if inner else []:
        for y in re.split(r"\s+and\s+", x):
            y = clean_name(y)
            if looks_like_name(y) and norm(y) != norm(name):
                synonyms.append(y)
    return dict(name=name, synonyms=synonyms, footnote_stars=stars), examples


ROUTE_WORDS = {"buccal", "gingival", "sublingual", "oromucosal"}


def extract(pdf: Path, manual_sections: set[str]) -> tuple[list[dict], dict]:
    """항목: kind = prohibited | threshold | exception, condition = 조건 문장(원문 발췌)."""
    doc = pymupdf.open(pdf)
    items, sections = [], {}
    st = dict(top=None, sub=None, sub_title=None, exceptions=False, p1_sports=True, note=False)
    buf = dict(bullet=None, bx=0.0, by=0.0, bpage=0, inline=None, foot=None)
    footnotes: dict[str, dict[int, str]] = {}

    def add(text, page, kind_hint, condition=None):
        if st["note"] or not st["top"] or st["top"] in manual_sections or (st["top"] == "P1" and st["p1_sports"]):
            return
        it, examples = parse_item(text)
        for n in examples:  # "selective androgen receptor modulators [SARMs, e.g. andarine, …]" → 예시도 각자 항목
            add(n, page, kind_hint, condition)
        if not it or norm(it["name"]) in ROUTE_WORDS:
            return
        items.append(dict(**it, section=st["top"], subsection=st["sub"], subsection_title=st["sub_title"],
                          prohibited=TOP[st["top"]][0], kind="exception" if st["exceptions"] else kind_hint,
                          condition=condition, page=page + 1, source="extracted"))

    def flush():
        b, inl, ft, page = buf["bullet"], buf["inline"], buf["foot"], buf["bpage"]
        buf.update(bullet=None, inline=None, foot=None)
        if ft:
            footnotes.setdefault(st["top"], {})[ft[0]] = re.sub(r"\s+", " ", ft[1]).strip()
        if b:
            text = re.sub(r"\s+", " ", b.lstrip(BULLET)).strip()
            cond = text[:400] if st["exceptions"] or ":" in text or EG_RE.search(text) else None
            if st["exceptions"]:
                # "Inhaled salbutamol: maximum …" / "Drospirenone; pamabrom; and topical … (e.g. dorzolamide, brinzolamide)"
                head, sep, _ = text.partition(":")
                for part in split_top(head if sep and not EG_RE.search(text) else text, ";"):
                    part_head, eg = eg_lists(part)
                    adm = re.search(r"administration of ([A-Za-z][\w\-]+)", part)
                    if eg:
                        names = eg
                    elif adm and "carbonic" not in adm.group(1):
                        names = [adm.group(1)]
                    else:
                        names = split_top(part_head, ",")
                    for n in names:
                        add(n, page, "exception", cond)
            else:
                # "Diuretics such as: Acetazolamide; amiloride; …" (화학명 안의 ":"는 "4’,5’:2,3"처럼 공백 없이 붙어 있다)
                lm = re.match(r"^(.*?)\s+such as:\s*(.*)$", text)
                if lm:
                    add(lm.group(1), page, "prohibited", cond)
                    for n in split_names(lm.group(2)):
                        add(n, page, "prohibited", cond)
                else:
                    add(text, page, "prohibited", cond)
        if inl:
            for n in split_names(inl):
                add(n, buf["bpage"], "prohibited")

    for page_no, page in enumerate(doc):
        if page_no < 3:
            continue
        for _, y, x, t in page_lines(page):
            if t.strip().upper() == "INDEX":
                flush()
                return finish(items, sections, footnotes)
            if t.isdigit() or (y < 30 and not TOP_RE.match(t)):  # 쪽 번호·머리말 (쪽 맨 아래 각주는 남긴다)
                continue
            mt = TOP_RE.match(t)
            if mt:
                flush()
                if mt.group(1) != st["top"]:
                    st.update(top=mt.group(1), sub=None, sub_title=None, exceptions=False, p1_sports=True, note=False)
                    sections.setdefault(st["top"], dict(title=TOP[st["top"]][1], prohibited=TOP[st["top"]][0]))
                continue
            if st["top"] is None:
                continue
            mf = FOOT_RE.match(t)
            if mf:
                flush(); buf["foot"] = [len(mf.group(1)), mf.group(2)]; continue
            if buf["foot"] is not None and not t.startswith(BULLET) and not SUB_RE.match(t):
                buf["foot"][1] += " " + t; continue
            m = SUB_RE.match(t)
            if m and m.group(1).startswith(st["top"]):
                flush()
                st.update(sub=m.group(1), sub_title=re.split(r",?\s*(?:e\.g\.|including)", m.group(2))[0].strip(" .:")[:80],
                          exceptions=False, note=False)
                buf["bpage"] = page_no
                if m.group(1).count(".") >= 2 and m.group(2):  # "S2.1.1 Erythropoietin receptor agonists, e.g. darbepoetins …"
                    parts = re.split(r",?\s*(?:e\.g\.|including,? but not limited to:?)\s*", m.group(2), maxsplit=1)
                    head, after = parts[0], (parts[1] if len(parts) > 1 else "")
                    add(head, page_no, "prohibited")
                    buf["inline"] = after  # 예시가 다음 줄로 이어진다
                else:
                    lo = LIST_OPEN_RE.search(t)
                    if lo:
                        buf["inline"] = lo.group(1)
                continue
            if t.upper().startswith("EXCEPTION"):
                flush(); st.update(exceptions=True, note=False); continue
            if t.upper() == "NOTE":  # NOTE 아래 글머리는 조건 설명(S9 "Other routes …")이라 항목이 아니다
                flush(); st["note"] = True; continue
            if st["top"] == "P1" and "not limited to" in t.lower():
                flush(); st["p1_sports"] = False; continue
            if t.startswith(BULLET):
                flush(); buf.update(bullet=t, bx=x, by=y, bpage=page_no); continue
            if STOP_RE.match(t):
                flush(); continue
            if buf["bullet"] is not None:
                # 이어지는 줄: 바로 아래(간격 24 미만)이고 글머리보다 많이 왼쪽이 아닐 때만.
                # 아니면 글머리 목록 뒤의 다른 문단("…their esters.", "A stimulant not expressly …")이다
                if 0 < y - buf["by"] < 24 and x >= buf["bx"] - 15:
                    buf["bullet"] = join_line(buf["bullet"], t); buf["by"] = y; continue
                flush()
            if buf["inline"] is not None:
                buf["inline"] = join_line(buf["inline"], t) if buf["inline"] else t
            else:
                lo = LIST_OPEN_RE.search(t)
                if lo:
                    flush(); buf.update(inline=lo.group(1), bpage=page_no)
    flush()
    return finish(items, sections, footnotes)


def finish(items: list[dict], sections: dict, footnotes: dict) -> tuple[list[dict], dict]:
    """각주를 항목에 반영: 기준치(greater than … per millilitre) → threshold, 모니터링(not considered Prohibited) →
    이름들을 exception으로 추가, 그 밖(예: Epinephrine 국소 사용)은 condition으로만."""
    for sec, notes in footnotes.items():
        sections[sec]["footnotes"] = {"*" * k: v[:600] for k, v in sorted(notes.items())}
        for it in items:
            if it["section"] == sec and it["footnote_stars"] in notes:
                note = notes[it["footnote_stars"]]
                if re.search(r"greater than .*per millilitre", note, re.I):
                    it["kind"] = "threshold"
                it["condition"] = note[:600]
        for k, note in notes.items():
            if re.search(r"not considered Prohibited", note, re.I):
                for n in split_names(note.split(":")[0]):
                    items.append(dict(name=clean_name(n), synonyms=[], footnote_stars=k, section=sec,
                                      subsection=None, subsection_title="Monitoring Program", prohibited="no",
                                      kind="exception", condition=note[:600], page=None, source="extracted"))
    return items, sections


def extract_index(pdf: Path) -> list[dict]:
    """원문 끝 INDEX: "이름, 쪽" 표제어. 여러 줄에 걸친 표제어는 블록 단위로 합쳐진다."""
    doc = pymupdf.open(pdf)
    start = next(i for i in range(3, len(doc)) if re.search(r"^\s*INDEX\s*$", doc[i].get_text(), re.M))
    out = []
    for p in range(start, len(doc)):
        for b in doc[p].get_text("blocks"):
            t = INVISIBLE.sub("", re.sub(r"\s+", " ", b[4])).strip()
            m = re.match(r"^(.+?)((?:,\s*\d+)+)$", t)  # "Cathine, 12, 16" (여러 쪽)
            if m and t not in ("INDEX",):
                pages = [int(p) for p in re.findall(r"\d+", m.group(2))]
                out.append(dict(term=re.sub(r"(\w)- (\w)", r"\1-\2", m.group(1)).strip(), page=pages[0], pages=pages))
    return out


def apply_manual(items: list[dict], sections: dict, manual: dict) -> None:
    for sec in manual["manual_sections"]:
        sections.setdefault(sec, dict(title=TOP[sec][1], prohibited=TOP[sec][0]))
    for m in manual["items"]:
        sec = m["section"]
        items.append(dict(name=m["name"], synonyms=m.get("synonyms", []), footnote_stars=0, section=sec,
                          subsection=m.get("subsection"), subsection_title=None, prohibited=TOP[sec][0],
                          kind=m.get("kind", "prohibited"), condition=m.get("condition"), page=m.get("page"), source="manual"))
    for s in manual["synonyms"]:
        key = norm(s["name"])
        hits = [it for it in items if it["section"] == s["section"]
                and (norm(it["name"]) == key or key in {norm(x) for x in it["synonyms"]})]
        if not hits:
            raise SystemExit(f"손 보정 동의어의 대상 항목이 없음: {s}")
        for it in hits:
            it["synonyms"] += [a for a in s["add"] if norm(a) not in {norm(x) for x in it["synonyms"]} | {norm(it["name"])}]
            if s.get("source") == "alias":
                it["aliases"] = sorted(set(it.get("aliases", [])) | set(s["add"]))
    sections["P1"]["sports"] = [x["name"] for x in manual["p1_sports"]]
    sections["P1"]["sports_out_of_competition"] = [x["name"] for x in manual["p1_sports"] if x["out_of_competition"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--year", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--manual", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manual = yaml.safe_load(args.manual.read_text(encoding="utf-8"))
    items, sections = extract(args.pdf, set(manual["manual_sections"]))
    apply_manual(items, sections, manual)
    seen, unique = {}, []
    for it in items:  # 같은 섹션·이름 중복 제거(쪽 넘김, 괄호 예시와 글머리가 겹칠 때) — 동의어는 합친다
        key = (it["section"], norm(it["name"]), it["kind"])
        if key in seen:
            prev = seen[key]
            prev["synonyms"] += [s for s in it["synonyms"] if norm(s) not in {norm(x) for x in prev["synonyms"]}]
            continue
        seen[key] = it; unique.append(it)
    out = dict(
        list_version=args.year, list_effective=f"{args.year}-01-01", list_expires=f"{args.year}-12-31",
        source_url=args.url,
        source_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        extracted_by=f"scripts/build_wada.py (PyMuPDF 좌표 기반 자동 추출) + {args.manual.name} (손 보정)",
        reviewed=False,
        caution="닫힌 목록이 아님: 여기 없는 이름을 허용으로 해석하지 말 것. 조건은 항목의 condition과 sections[*].footnotes.",
        section_conditions=manual["section_conditions"],
        counts={s: {k: sum(1 for i in unique if i["section"] == s and i["kind"] == k)
                    for k in ("prohibited", "threshold", "exception")} for s in TOP if s in sections},
        sections=sections, items=unique, index=extract_index(args.pdf),
        index_not_substances=manual.get("index_not_substances") or {},
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], ensure_ascii=False), "총", len(unique), "INDEX", len(out["index"]))


if __name__ == "__main__":
    main()
