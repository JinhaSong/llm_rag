#!/usr/bin/env python3
"""수포합 정책 반영: 상대시점·숫자포합 기간 표제어 제거 + 조합용 단위 표제어 보강.
정책: '오늘/지금 기준(offset 0)'은 유지, 그 외 상대시점과 숫자 포합 기간은 제거.
사용: python3 apply_supohap.py <llm_rag_repo_root>
"""
import json, os, sys, shutil

ROOT = sys.argv[1]
BASE = os.path.join(ROOT, "dataset-builder/data/llm_pipeline/variants")

# ── 제거: 숫자 포합 기간 + 0이 아닌 상대시점 ─────────────────────────
REMOVE = {
    8218:  "어제,어저께,작일 (-1일)",
    4675:  "그저께,그제 (-2일)",
    7499:  "모레,내일모레,이틀,이틀후 (+2일/2일)",
    10899: "이틀,이틀 후 (2일)",
    11307: "사흘 (3일)",
    10038: "나흘 (4일)",
    1468:  "닷새 (5일)",
    3625:  "열흘 (10일)",
    9104:  "보름 (15일)",
    6105:  "백일 (100일)",
    6995:  "천년 (1000년)",
    9590:  "재작년,전전해 (-2년)",
    6442:  "내일,명일 (+1일)",
    7956:  "작년,지난해 (-1년)",
    5514:  "내년,명년,이듬해,다음해 (+1년)",
    245:   "지난주,작주,전주 (-1주)",
    6443:  "내주,다음주 (+1주)",
}
# 유지(offset 0): 7703 오늘 / 6990 지금 / 9481 올해 / 11943 금주
# 유지(단위 겸용): 9297 하루,온종일,종일

# ── 111에 보강할 조합용 단위 표제어 (1104에서 임베딩째 복사) ──────────
ADD_UNITS = [4374, 11301, 24028, 2652, 11559, 9366, 5989, 9297, 8602,
             7703, 6990, 11606]  # + 오늘/지금(기준점, 정책상 유지), 며칠


def load(p):
    return json.load(open(p, encoding="utf-8"))


def save(p, o):
    if not os.path.exists(p + ".bak"):
        shutil.copy2(p, p + ".bak")
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False)


def prune_ids(seq, drop):
    return [x for x in seq if int(x) not in drop]


def apply_variant(var, add_docs=None, add_meta=None):
    vp = os.path.join(BASE, var)
    db = load(f"{vp}/gloss_vector_db.json")
    km = load(f"{vp}/keyword_gloss_map.json")
    ig = load(f"{vp}/intent_gloss_sets.json")
    before = len(db["documents"])

    # 1) 벡터DB 문서 제거 + 추가
    db["documents"] = [d for d in db["documents"] if int(d.get("origin", -1)) not in REMOVE]
    existing = {int(d["origin"]) for d in db["documents"]}
    added = []
    for d in (add_docs or []):
        if int(d["origin"]) not in existing:
            db["documents"].append(d); existing.add(int(d["origin"])); added.append(int(d["origin"]))
    db.setdefault("counts", {})["documentCount"] = len(db["documents"])
    db["supohapPolicy"] = {
        "removed": sorted(REMOVE), "addedUnits": added,
        "note": "수포합(숫자 포합 기간·상대시점) 제외, 오늘/지금 기준 유지, 0-10 숫자+단위 조합으로 표현",
    }

    # 2) keyword_gloss_map 정리
    km["glossMeta"] = {k: v for k, v in km["glossMeta"].items() if int(k) not in REMOVE}
    for oid in added:
        if add_meta and str(oid) in add_meta:
            km["glossMeta"][str(oid)] = add_meta[str(oid)]
    km["surfaceToGloss"] = {k: pruned for k, v in km["surfaceToGloss"].items()
                            if (pruned := prune_ids(v, REMOVE))}
    km["keywordToGloss"] = {
        k: v for k, v in km["keywordToGloss"].items()
        if not isinstance(v, dict) or int(v.get("glossIndex") or -1) not in REMOVE}
    km["glossPrior"] = {k: v for k, v in km["glossPrior"].items() if int(k) not in REMOVE}
    km["glossPriorBySubCategory"] = {
        sc: {k: v for k, v in m.items() if int(k) not in REMOVE}
        for sc, m in km["glossPriorBySubCategory"].items()}
    km["glossCount"] = len(db["documents"])

    # 3) intent_gloss_sets 정리 (+ time 세트에 단위 보강)
    for name, s in ig["sets"].items():
        ids = prune_ids(s.get("glossIds", []), REMOVE)
        if name == "time":
            for oid in added:
                if oid not in ids: ids.append(oid)
        s["glossIds"] = sorted(set(ids))
        s["count"] = len(s["glossIds"])
        meta = km["glossMeta"]
        s["sample"] = [meta[str(i)]["gloss"].split(",")[0] for i in s["glossIds"][:6] if str(i) in meta]

    save(f"{vp}/gloss_vector_db.json", db)
    save(f"{vp}/keyword_gloss_map.json", km)
    save(f"{vp}/intent_gloss_sets.json", ig)
    print(f"  [{var}] 문서 {before} -> {len(db['documents'])}  (제거 {before - len(db['documents']) + len(added)}, 추가 {len(added)})")
    return db, km


def main():
    print("=== 수포합 정책 적용 ===")
    # 1104 먼저 (여기서 단위 문서 원본을 확보)
    src_db = load(f"{BASE}/1107/gloss_vector_db.json")
    src_km = load(f"{BASE}/1107/keyword_gloss_map.json")
    unit_docs = [d for d in src_db["documents"] if int(d["origin"]) in ADD_UNITS]
    unit_meta = {str(o): src_km["glossMeta"][str(o)] for o in ADD_UNITS if str(o) in src_km["glossMeta"]}
    print(f"  단위 표제어 원본 확보: {len(unit_docs)}개 / 요청 {len(ADD_UNITS)}개")
    missing = set(ADD_UNITS) - {int(d['origin']) for d in unit_docs}
    if missing: print(f"  ⚠️ 1104에 없어 복사 불가: {sorted(missing)}")

    apply_variant("1107")                       # 1104: 제거만
    apply_variant("keywords", unit_docs, unit_meta)  # 111: 제거 + 단위 보강
    print("완료 (원본은 *.bak 으로 백업)")


if __name__ == "__main__":
    main()
