#!/usr/bin/env python3
"""questionPatterns 보정: 시간대/상황 질문이 severity+number 세트를 끌어오는 문제 수정.
원인: '많이 아프' 정규식이 '어떤 시간에 많이 아프세요?'까지 매칭 -> 0~10 숫자 덤프.
사용: python3 fix_patterns.py <llm_rag_repo_root>
"""
import json, os, re, shutil, sys

ROOT = sys.argv[1]
BASE = os.path.join(ROOT, "dataset-builder/data/llm_pipeline/variants")

TIMEBLOCK = (r"아침|저녁|밤|새벽|오전|오후|낮|시간대|어떤\s*시간|무슨\s*시간|"
             r"주무실|잠\s*잘|일어날\s*때|어떤\s*상황|무슨\s*상황|어떨\s*때|어떤\s*경우")

OLD_SEV = r"몇\s*점|점수|강도|얼마나\s*아프|많이\s*아프"
NEW_SEV = r"^(?!.*(" + TIMEBLOCK + r")).*(몇\s*점|점수|강도|얼마나\s*아프|많이\s*아프)"

NEW_TIME_RULE = {
    "pattern": TIMEBLOCK,
    "sets": ["time"],
    "secondarySets": ["frequency", "severity", "body_action"],
    "note": "시간대/상황별 변화 질문 — severity·number 오적용 방지용",
}


def patch(var):
    p = f"{BASE}/{var}/intent_gloss_sets.json"
    ig = json.load(open(p, encoding="utf-8"))
    pats = ig.get("questionPatterns", [])
    changed_sev = False
    for r in pats:
        if r.get("pattern") == OLD_SEV:
            r["pattern"] = NEW_SEV
            r["note"] = "시간대/상황 표현이 있으면 매칭 제외 (숫자 덤프 방지)"
            changed_sev = True
    already = any(r.get("pattern") == TIMEBLOCK for r in pats)
    if not already:
        # severity 규칙 앞에 삽입 (누적 구조라 순서는 가독성 목적)
        idx = next((i for i, r in enumerate(pats) if r.get("pattern") == NEW_SEV), len(pats))
        pats.insert(idx, NEW_TIME_RULE)
    ig["questionPatterns"] = pats
    if not os.path.exists(p + ".bak2"):
        shutil.copy2(p, p + ".bak2")
    json.dump(ig, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  [{var}] severity 패턴 수정={changed_sev}, 시간대 패턴 추가={not already}, 총 {len(pats)}개")


def verify():
    tests = [
        ("어떤 시간에 많이 아프세요?", False, True),
        ("아침에 일어날 때 아프세요? 밤에 많이 아프세요?", False, True),
        ("어떤 상황에서 많이 아프세요?", False, True),
        ("아침과 저녁 중 언제 아프세요?", False, True),
        ("주무실 때가 더 아프세요?", False, True),
        ("많이 아프세요?", True, False),
        ("통증이 몇 점이나 되는 거 같으세요?", True, False),
        ("얼마나 아프세요?", True, False),
    ]
    print("  --- 검증 (기대 severity/time) ---")
    ok = True
    for q, esev, etime in tests:
        s = bool(re.search(NEW_SEV, q)); t = bool(re.search(TIMEBLOCK, q))
        mark = "OK " if (s == esev and t == etime) else "FAIL"
        if mark == "FAIL": ok = False
        print(f"    [{mark}] {q[:40]:42s} sev={s} time={t}")
    print("  전체:", "통과 ✅" if ok else "실패 ❌")


if __name__ == "__main__":
    print("=== questionPatterns 보정 ===")
    for v in ("1107", "keywords"):
        patch(v)
    verify()
