# -*- coding: utf-8 -*-
"""q_type 판정 규칙 (2026-09-21 회의 정의)
  s 선택형: 보기를 2개 이상 제시하고 그중 하나를 고르게 하는 질문
  c 확인형: 예/아니오로 답하는 질문
  o 오픈형: 자유 응답을 요구하는 질문
"""
import re

WH = r"어디|언제|어떻게|어떤|어떨|어때|무엇|무슨|얼마나|얼마|몇|어느|왜|누가|어떠"

CHOICE = [
    r"아니면",
    r"(이|가|은|는)?\s*냐\s*.{0,12}냐",
    r"(중에|중\s*(어느|언제|무엇|뭐|어떤))",
    r"(오른쪽|왼쪽|좌측|우측).{0,8}(오른쪽|왼쪽|좌측|우측)",
    r"(아침|점심|저녁|낮|밤|새벽|오전|오후).{0,16}(아침|점심|저녁|낮|밤|새벽|오전|오후)",
    r"까요.{0,24}까요",                      # "약만 드릴까요, 주사 놓을까요?"
    r"\S+이나\s+\S+\s*(있|없|하)",            # "고혈압이나 당뇨 있으세요?"
    r"(주사|약|수술|시술).{0,20}(주사|약|수술|시술).{0,14}(할까요|드릴까요|해드릴까요|원하세요)",
]
# 자유 응답을 요구하는 비(非)의문사 형태
OPEN_EXTRA = [
    r"(보세요|말씀해|설명해|표현해)",              # "아픈 것을 표현해 보세요."
    r"(빈도|정도|기간|시점|증상)(은|는)요",         # "통증 오는 빈도는요?"
    r"다른\s+\S+(은|는|이|가)?\s*(있|없)",        # "다른 질환은 있으세요?" (열거 기대)
]


def classify_qtype(q: str) -> str:
    s = (q or "").strip()
    for p in CHOICE:
        if re.search(p, s):
            return "s"
    if len(re.findall(r"아프세요|아파요|아프신가요", s)) >= 2:
        return "s"
    for p in OPEN_EXTRA:
        if re.search(p, s):
            return "o"
    if re.search(WH, s):
        return "o"
    return "c"


if __name__ == "__main__":
    import json, collections
    gold = json.load(open("/tmp/qtype_gold.json", encoding="utf-8"))
    cm = collections.Counter(); wrong = []
    for r in gold:
        p = classify_qtype(r["q"])
        cm[(r["t"], p)] += 1
        if p != r["t"]: wrong.append((r["t"], p, r["q"]))
    n = len(gold); ok = sum(v for (a, b), v in cm.items() if a == b)
    print(f"수작업 라벨 대비 일치: {ok}/{n} = {100*ok/n:.1f}%")
    labs = ["o", "c", "s"]
    print("\n혼동행렬 (행=라벨, 열=예측)")
    print("      " + "".join(f"{p:>6s}" for p in labs))
    for a in labs:
        print(f"  {a}   " + "".join(f"{cm[(a,b)]:6d}" for b in labs))
    print(f"\n불일치 {len(wrong)}건:")
    for a, b, q in wrong: print(f"  라벨={a} 예측={b} | {q[:54]}")
