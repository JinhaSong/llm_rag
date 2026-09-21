#!/usr/bin/env python3
"""수 관련 세부유형에서 number 세트를 primary 로 승격.

수포합(이틀·사흘·어제 등)을 표제어 풀에서 뺀 뒤로 시점·기간은 "2 + 날 + 전"처럼
숫자 조합으로 답해야 하는데, number 가 secondary 에 머물러 후보 상위에 오르지
못해 0~10 중 2개만 나오는 문제가 있었다. (2026-09-21 회의 요구사항)

사용: python3 promote_number_set.py <llm_rag_repo_root>
"""
import json, os, shutil, sys

ROOT = sys.argv[1]
BASE = os.path.join(ROOT, "dataset-builder/data/llm_pipeline/variants")

# 답이 수로 표현되는 세부유형 (server.js 의 NUMERIC_SUBCATEGORIES 와 일치시킬 것)
NUMERIC_SUBS = ["pain_score", "severity", "onset", "duration", "frequency", "surgery_time"]


def patch(var):
    p = f"{BASE}/{var}/intent_gloss_sets.json"
    ig = json.load(open(p, encoding="utf-8"))
    subsets = ig.get("subCategorySets", {})
    changed = []
    for sub in NUMERIC_SUBS:
        spec = subsets.get(sub)
        if not spec:
            continue
        primary = list(spec.get("primary") or [])
        secondary = list(spec.get("secondary") or [])
        if "number" in primary:
            continue
        primary.append("number")
        secondary = [s for s in secondary if s != "number"]
        spec["primary"] = primary
        spec["secondary"] = secondary
        changed.append(f"{sub}: primary={primary}")
    if not os.path.exists(p + ".bak3"):
        shutil.copy2(p, p + ".bak3")
    json.dump(ig, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  [{var}] {len(changed)}개 승격")
    for c in changed:
        print(f"      {c}")


if __name__ == "__main__":
    print("=== number 세트 primary 승격 ===")
    for v in ("1107", "keywords"):
        patch(v)
