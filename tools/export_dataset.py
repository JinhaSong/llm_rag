#!/usr/bin/env python3
"""dataset-builder/data 의 운영 데이터에서 검수·배포용 데이터셋을 dataset/ 로 내보낸다.

운영 데이터(임베딩 포함 14MB JSON)는 사람이 확인하기 어려우므로, 분류 데이터셋을
CSV 로 함께 풀어 둔다. dataset/ 는 이 스크립트로 언제든 재생성된다.

사용: python3 tools/export_dataset.py
"""
import csv, json, os

SRC = "dataset-builder/data/llm_pipeline"
DST = "dataset"


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return json.load(f)


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {path}  ({len(rows)}행)")


def main():
    os.makedirs(DST, exist_ok=True)
    pool = load("question_answer_pool.json")
    qs = pool["questions"]

    # 1) 원본 분류 데이터셋 (운영 데이터와 동일 내용)
    with open(f"{DST}/question_answer_pool.json", "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)
    print(f"  {DST}/question_answer_pool.json")

    # 2) 의사 질문 + 분류 라벨
    write_csv(f"{DST}/questions.csv",
              ["question_id", "question", "stage", "sub_category", "answer_count", "gloss_origins"],
              [[q["questionId"], q["question"], q["stage"], q["subCategory"],
                len(q.get("answerPool") or []),
                " ".join(str(o) for o in (q.get("glossOrigins") or []))] for q in qs])

    # 3) 환자 답변 (질문별로 펼침)
    rows = []
    for q in qs:
        for a in (q.get("answerPool") or []):
            rows.append([q["questionId"], q["stage"], q["subCategory"], a])
    write_csv(f"{DST}/answers.csv", ["question_id", "stage", "sub_category", "answer"], rows)

    # 4) 분류 체계
    combos = {}
    for q in qs:
        combos.setdefault((q["stage"], q["subCategory"]), 0)
        combos[(q["stage"], q["subCategory"])] += 1
    write_csv(f"{DST}/categories.csv", ["stage", "sub_category", "question_count"],
              [[s, c, n] for (s, c), n in sorted(combos.items())])

    # 5) 표제어 풀 (임베딩 제외)
    for var, out in (("1107", "gloss_pool_1107.csv"), ("keywords", "gloss_pool_keywords.csv")):
        db = load(f"variants/{var}/gloss_vector_db.json")
        write_csv(f"{DST}/{out}", ["origin", "gloss", "category"],
                  [[d.get("origin"), d.get("gloss"), d.get("category", "")]
                   for d in db["documents"]])

    # 6) 규모 요약
    ans = sum(len(q.get("answerPool") or []) for q in qs)
    summary = {
        "questions": len(qs),
        "answers": ans,
        "unique_answers": len({a for q in qs for a in (q.get("answerPool") or [])}),
        "stages": len({q["stage"] for q in qs}),
        "sub_categories": len({q["subCategory"] for q in qs}),
        "stage_sub_combinations": len(combos),
        "gloss_pool_1107": len(load("variants/1107/gloss_vector_db.json")["documents"]),
        "gloss_pool_keywords": len(load("variants/keywords/gloss_vector_db.json")["documents"]),
    }
    with open(f"{DST}/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  {DST}/summary.json")
    print("\n규모:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
