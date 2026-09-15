# Gloss Recommender

클론하거나 pull한 뒤 저장소 루트에서 아래만 실행하면 된다. 환경 변수, 데이터 복사, 모델 수동 설치는 필요 없다.

```bash
docker compose up -d --build
```

첫 실행에서 `qwen3:14b`와 `bge-m3`를 Ollama가 자동으로 받는다. 이미 받은 적 있으면 건너뛴다.

같은 코드로 표제어 목록만 다른 서버가 두 대 뜬다.

| 주소 | 목록 | 규모 |
|---|---|---:|
| http://localhost:8777 | ETRIKSL 1107 (수포합 제외, 0–10 유지) | 약 1,104개 |
| http://localhost:8779 | 엑셀 2탭 답변 핵심표제어 only (수포합 제외, 0–10 보충) | 약 111개 |

질문·답변 pool과 분류 코드는 공유하고, 키워드 후보가 되는 표제어 사전만 갈라진다. 둘을 비교한 뒤 한쪽을 고르면 된다.

사전 조건은 Docker Compose와 NVIDIA Container Toolkit뿐이다. 모델은 이미지에 넣지 않고 받는 쪽 계정의 `~/.ollama`에 남기므로 `docker compose down` 후에도 다시 받지 않는다.
