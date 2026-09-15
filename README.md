# Gloss Recommender

클론하거나 pull한 뒤 저장소 루트에서 아래만 실행

```bash
docker compose up -d --build
```

첫 실행에서 `qwen3:14b`와 `bge-m3`를 Ollama가 자동으로 받음

같은 코드로 표제어 목록만 다른 서버가 2개 실행

| 주소 | 목록 | 규모 |
|---|---|---:|
| http://localhost:8777 | ETRIKSL 1107 (수포합 제외, 0–10 유지) | 약 1,104개 |
| http://localhost:8779 | 엑셀 2탭 답변 핵심표제어 only (수포합 제외, 0–10 보충) | 약 111개 |

질문·답변 pool과 분류 코드는 공유하고, 키워드 후보가 되는 표제어 사전만 갈라진다. 둘을 비교한 뒤 한쪽을 고르면 된다.
