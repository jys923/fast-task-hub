# Fast Task Hub (FastAPI + Celery + Docker Redis)

로컬 `venv` 환경에서 애플리케이션을 구동하고, Redis 인프라만 Docker Compose로 분리하여 비동기 큐/워커 패턴을 실험하는 프로젝트입니다.

## 1. 인프라 자원 실행 (Docker)

먼저 로컬 포트 6379로 Redis를 실행합니다.

```bash
docker-compose up -d

```

## 2. 로컬 가상환경(venv) 및 패키지 설정

파이썬 가상환경을 생성하고 활성화한 뒤 필요한 라이브러리를 설치합니다.

### Windows (PowerShell 기준)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```

## 3. 애플리케이션 실행 단계 (터미널 분리)

### 터미널 ①: Celery Worker (일꾼) 실행

가상환경이 활성화된 상태에서 대기열을 감시할 워커를 켭니다. (Windows 환경에서는 내부 이벤트 루프 처리를 위해 `-P solo` 풀 옵션을 주는 것이 안정적입니다.)

```bash
# Windows
celery -A tasks.celery_app worker --loglevel=info -P solo

# macOS / Linux
celery -A tasks.celery_app worker --loglevel=info

```

### 터미널 ②: FastAPI 웹 서버 실행

새 터미널을 열고 가상환경을 활성화한 뒤, API 요청을 받을 웹 서버를 구동합니다.

```bash
uvicorn main:app --reload

```

## 4. 비동기 흐름 검증 및 테스트

1. 브라우저를 열고 `http://127.0.0.1:8000/trigger/Test` 주소로 접속합니다.
2. 브라우저 화면에는 5초 동안 멈추는 현상 없이 **즉시 접수 완료 JSON 응답**이 나타납니다.
3. 그와 동시에 **터미널 ①(Celery Worker)** 로그를 보면, 뒤늦게 큐에서 작업을 꺼내어 5초간 연산을 수행한 뒤 완료 로그를 출력하는 비동기 패턴을 눈으로 확인할 수 있습니다.