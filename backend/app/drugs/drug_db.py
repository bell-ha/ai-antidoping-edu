"""약물 DB (SQLite). 원천 JSON(검토 대상, 레포에 커밋) → var/drugs.sqlite(생성물, .gitignore).

    cd backend && .venv/bin/python -m app.drugs.drug_db   # 빌드
    sqlite3 ../var/drugs.sqlite "select * from name_index where norm like 'pseudo%'"   # 조회 예

원천:
  knowledge/drugs/curated/substances.json            손 조회표(성분)
  knowledge/drugs/curated/products.json              손 조회표(제품·제품군)
  knowledge/drugs/kada/processed/herbal_medicine_2025.json   KADA 한약재 가이드라인의 11종(한약재 → 검출 성분)
  knowledge/drugs/wada/processed/prohibited_list_<연도>.json   WADA 금지목록 추출본
  knowledge/drugs/kr_source/processed/kr_products.json.gz                한글 제품명 → 성분(심평원 약가마스터)
원천 파일의 sha256을 meta에 기록하고, 서버는 시작할 때 원천과 다르면 데모 모드에서는 다시 빌드하고
시범 모드(DEMO_MODE=0)에서는 시작을 거부한다(검토하지 않은 DB로 판정하지 않도록).
판정 규칙(부분 일치·투여 경로·ATC 계열)은 substances.py에 있고, 이 모듈은 저장과 읽기만 한다.
"""

import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

from app.config import DRUGS, VAR

DB = VAR / "drugs.sqlite"
SCHEMA_VERSION = "2"  # 2: hand_products.herbal

SCHEMA = """
create table meta(key text primary key, value text not null);
create table substances(id text primary key, name_ko text, name_en text, status text, wada_class text, note text,
                        source_url text, reviewed integer);
create table substance_aliases(substance_id text references substances(id), alias text);
create table hand_products(id text primary key, kind text, supplement integer, herbal integer, note text, links text,
                           reviewed integer);
create table hand_product_aliases(product_id text references hand_products(id), alias text);
create table hand_product_ingredients(product_id text references hand_products(id),
                                      substance_id text references substances(id), pos integer);
create table wada_items(id integer primary key, name text, section text, subsection text, subsection_title text,
                        prohibited text, kind text, condition text, footnote_stars integer, page integer, source text);
create table wada_item_names(item_id integer references wada_items(id), name text, type text);
create table kr_ingredients(id integer primary key, name text);
create table kr_groups(group_code text, ingredient_id integer references kr_ingredients(id), route text, form text,
                       pos integer);
create table kr_products(item_code text primary key, name text, otc text, group_code text, atc text);
create table name_index(norm text, target_type text, target_id text);
create index name_index_norm on name_index(norm);
create index kr_products_name on kr_products(name);
create index kr_groups_code on kr_groups(group_code);
"""


def sources() -> dict[str, Path]:
    version = json.loads((DRUGS / "curated/substances.json").read_text(encoding="utf-8"))["list_version"]
    return {"substances": DRUGS / "curated/substances.json", "products": DRUGS / "curated/products.json",
            "herbs": DRUGS / "kada/processed/herbal_medicine_2025.json",
            "wada": DRUGS / f"wada/processed/prohibited_list_{version}.json", "kr_products": DRUGS / "kr_source/processed/kr_products.json.gz"}


def source_hashes() -> dict[str, str]:
    return {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in sources().items()}


def build(path: Path = DB) -> Path:
    from app.drugs.substances import name_variants, normalize  # 순환 import 방지: 함수 안에서

    src = sources()
    substances = json.loads(src["substances"].read_text(encoding="utf-8"))
    products = json.loads(src["products"].read_text(encoding="utf-8"))
    herbs = json.loads(src["herbs"].read_text(encoding="utf-8"))
    note = herbs["note"]
    links = [{"label": "KADA 한약재 도핑방지 가이드라인", "url": herbs["board_page"]}]
    for name, h in herbs["herbs"].items():  # 한약재도 손 조회표 제품처럼 다룬다(herbal 표시만 다름)
        if name in products["products"]:
            raise ValueError(f"한약재 '{name}'이 curated/products.json에도 있어요. 한 곳에만 두세요.")
        products["products"][name] = dict(kind="product", aliases=h["aliases"], ingredients=h["ingredients"],
                                          supplement=False, herbal=True, note=note, links=links, reviewed=h["reviewed"])
    wada = json.loads(src["wada"].read_text(encoding="utf-8"))
    with gzip.open(src["kr_products"], "rt", encoding="utf-8") as f:
        kr = json.load(f)

    path.parent.mkdir(parents=True, exist_ok=True)  # var/는 레포에 없다(생성물 폴더)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    meta = {"schema_version": SCHEMA_VERSION, "sources": source_hashes(),
            "substances": {k: v for k, v in substances.items() if k != "substances"},
            "wada": {k: v for k, v in wada.items() if k not in ("items",)},
            "kr_meta": kr["meta"]}
    con.executemany("insert into meta values (?, ?)", [(k, json.dumps(v, ensure_ascii=False)) for k, v in meta.items()])

    names = []
    for sid, s in substances["substances"].items():
        con.execute("insert into substances values (?,?,?,?,?,?,?,?)",
                    (sid, s["name_ko"], s["name_en"], s["status"], s.get("wada_class"), s.get("note"), s["source_url"],
                     int(s["reviewed"])))
        con.executemany("insert into substance_aliases values (?,?)", [(sid, a) for a in s.get("aliases", [])])
        names += [(k, "substance", sid) for n in [s["name_ko"], s["name_en"], *s.get("aliases", [])]
                  for k in name_variants(n)]
    for pid, p in products["products"].items():
        con.execute("insert into hand_products values (?,?,?,?,?,?,?)",
                    (pid, p["kind"], int(p.get("supplement", False)), int(p.get("herbal", False)), p.get("note"),
                     json.dumps(p.get("links", []), ensure_ascii=False), int(p["reviewed"])))
        con.executemany("insert into hand_product_aliases values (?,?)", [(pid, a) for a in p.get("aliases", [])])
        con.executemany("insert into hand_product_ingredients values (?,?,?)",
                        [(pid, sid, i) for i, sid in enumerate(p["ingredients"])])
        names += [(normalize(n), "hand_product", pid) for n in [pid, *p.get("aliases", [])]]
    for i, item in enumerate(wada["items"]):
        con.execute("insert into wada_items values (?,?,?,?,?,?,?,?,?,?,?)",
                    (i, item["name"], item["section"], item.get("subsection"), item.get("subsection_title"),
                     item["prohibited"], item["kind"], item.get("condition"), item.get("footnote_stars"),
                     item.get("page"), item.get("source")))
        extra = [(i, n, "synonym") for n in item.get("synonyms", [])] + [(i, n, "alias") for n in item.get("aliases", [])]
        con.executemany("insert into wada_item_names values (?,?,?)", extra)
        names += [(k, "wada_item", str(i)) for n in [item["name"], *(x[1] for x in extra)] for k in name_variants(n)]
    con.executemany("insert into kr_ingredients values (?,?)", list(enumerate(kr["ingredients"])))
    con.executemany("insert into kr_groups values (?,?,?,?,?)",
                    [(code, ing, route, form, pos) for code, rows in kr["groups"].items()
                     for pos, (ing, route, form) in enumerate(rows)])
    con.executemany("insert into kr_products values (?,?,?,?,?)",
                    [(code, name, otc, group, atc) for name, code, otc, group, atc in kr["products"]])
    names += [(normalize(name), "kr_product", code) for name, code, *_ in kr["products"]]
    con.executemany("insert into name_index values (?,?,?)", names)
    con.commit()
    con.close()
    tmp.replace(path)  # 다 만든 뒤에만 교체(중간 실패가 반쪽 DB를 남기지 않게)
    return path


def is_current(path: Path = DB) -> bool:
    if not path.exists():
        return False
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = dict(con.execute("select key, value from meta").fetchall())
    except sqlite3.DatabaseError:
        return False
    finally:
        con.close()
    return (json.loads(row.get("schema_version", "null")) == SCHEMA_VERSION
            and json.loads(row.get("sources", "{}")) == source_hashes())


def ensure(demo_mode: bool, path: Path = DB) -> None:
    """서버 시작 시: 원천과 맞지 않으면 데모에서는 다시 빌드, 시범에서는 거부."""
    if is_current(path):
        return
    if not demo_mode:
        raise RuntimeError("약물 DB가 없거나 원천 JSON과 다릅니다. `python -m app.drugs.drug_db`로 빌드한 뒤 시작하세요.")
    build(path)


def load(path: Path = DB) -> dict:
    """substances.py가 쓰던 모양(손 조회표·WADA·제품 목록)으로 DB를 읽는다."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    q = con.execute
    meta = {k: json.loads(v) for k, v in q("select key, value from meta")}
    aliases: dict[str, list[str]] = {}
    for sid, a in q("select substance_id, alias from substance_aliases order by rowid"):
        aliases.setdefault(sid, []).append(a)
    substances = dict(meta["substances"], substances={
        sid: dict(name_ko=ko, name_en=en, aliases=aliases.get(sid, []), status=st, wada_class=cls, note=note,
                  source_url=url, reviewed=bool(rev))
        for sid, ko, en, st, cls, note, url, rev in q("select * from substances order by rowid")})

    p_alias: dict[str, list[str]] = {}
    for pid, a in q("select product_id, alias from hand_product_aliases order by rowid"):
        p_alias.setdefault(pid, []).append(a)
    p_ing: dict[str, list[str]] = {}
    for pid, sid in q("select product_id, substance_id from hand_product_ingredients order by product_id, pos"):
        p_ing.setdefault(pid, []).append(sid)
    products = {"products": {
        pid: dict(kind=kind, aliases=p_alias.get(pid, []), ingredients=p_ing.get(pid, []), supplement=bool(sup),
                  herbal=bool(herb), note=note, links=json.loads(links), reviewed=bool(rev))
        for pid, kind, sup, herb, note, links, rev in q("select * from hand_products order by rowid")}}

    w_names: dict[int, dict[str, list[str]]] = {}
    for iid, name, typ in q("select item_id, name, type from wada_item_names order by rowid"):
        w_names.setdefault(iid, {"synonym": [], "alias": []})[typ].append(name)
    cols = ["id", "name", "section", "subsection", "subsection_title", "prohibited", "kind", "condition",
            "footnote_stars", "page", "source"]
    items = []
    for row in q("select * from wada_items order by id"):
        item = dict(zip(cols, row))
        names = w_names.get(item.pop("id"), {"synonym": [], "alias": []})
        items.append(dict(item, synonyms=names["synonym"], aliases=names["alias"]))
    wada = dict(meta["wada"], items=items)

    groups: dict[str, list] = {}
    for code, ing, route, form in q("select group_code, ingredient_id, route, form from kr_groups "
                                    "order by group_code, pos"):
        groups.setdefault(code, []).append([ing, route, form])
    kr = dict(meta=meta["kr_meta"], ingredients=[n for (n,) in q("select name from kr_ingredients order by id")],
              groups=groups, products=[list(r) for r in q("select name, item_code, otc, group_code, atc "
                                                            "from kr_products order by name, item_code")])
    con.close()
    return dict(substances=substances, products=products, wada=wada, kr=kr)


if __name__ == "__main__":
    print(build())
