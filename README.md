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
## 4. 비동기 흐름 검증 및 테스트 (Swagger UI)

본 프로젝트는 API 응답 지연을 방지하기 위해 비동기 큐를 사용하며, Swagger UI를 통해 2단계 검증(생성 후 상태 조회) 시나리오를 테스트할 수 있습니다.

테스트를 진행하기 전, Redis 컨테이너와 FastAPI 서버, Celery Worker가 모두 정상 구동 중인지 확인하십시오.

### 1단계: Swagger UI 접속 및 회원가입 요청
1. 브라우저를 열고 `http://127.0.0.1:8000/docs` 주소로 접속합니다.
2. `POST /users` 엔드포인트를 확장한 뒤 [Try it out]을 클릭합니다.
3. Request body에 테스트용 이름과 이메일을 입력하고 [Execute]를 누릅니다.
4. 백그라운드 작업(이메일 발송 시뮬레이션)이 트리거되지만, API 서버는 대기 시간 없이 약 0.01초 만에 즉시 응답을 반환합니다. 이 시점에서 반환된 유저의 `status` 값은 `PENDING`입니다.

### 2단계: 실시간 백그라운드 처리 및 상태 전환 확인
1. `POST` 요청 성공 즉시, 아래의 `GET /users/{user_id}` 엔드포인트를 통해 방금 생성된 유저 ID로 조회를 수행합니다.
2. Celery Worker 내부에서 의도적으로 설정한 대기 시간(10초) 동안 작업을 처리 중이므로, 이 타이밍에 조회된 유저의 상태는 여전히 `PENDING`으로 유지됩니다.
3. Celery 실행 터미널 로그에 이메일 발송 완료 메시지가 출력된 것을 확인한 후, 다시 한번 `GET /users/{user_id}` 조회를 호출합니다.
4. Celery 일꾼이 직접 데이터베이스의 레코드를 업데이트 완료했으므로, 유저의 최종 상태가 `ACTIVE`로 변경되어 있는 것을 확인할 수 있습니다.


## 5. 프로젝트 아키텍처 및 데이터 흐름

본 프로젝트는 단순한 비동기 작업을 넘어, 시스템 간 결합도를 낮추고 데이터 무결성을 보장하는 실무형 아키텍처로 설계되었습니다.

### 데이터 흐름도
1. [FastAPI] 사용자로부터 가입 요청(이메일, 이름) 수신
2. [FastAPI ➡️ SQLite] 데이터베이스에 유저 정보를 `PENDING` 상태로 1차 저장 후 고유 ID 발급
3. [FastAPI ➡️ Redis] 생성된 유저의 고유 식별자(`user_id`)만 메시지 큐에 생성 요청(Payload) 후 사용자에게 즉시 응답
4. [Celery Worker ⬅️ Redis] 대기 중이던 일꾼(Worker)이 Redis 큐에서 `user_id`를 확보
5. [Celery Worker ➡️ SQLite] 일꾼이 직접 데이터베이스를 조회하여 이메일 주소 획득 후 발송 작업 수행
6. [Celery Worker ➡️ SQLite] 발송 완료 후 직접 데이터베이스를 업데이트하여 유저 상태를 `ACTIVE`로 변경

### 식별자(ID) 기반 큐 설계의 아키텍처적 장점
* 큐의 경량화: Redis 큐에 대용량 오브젝트나 가입 정보 전체를 통째로 넘기지 않고, 고유한 정수형 ID만 넘김으로써 큐 시스템의 메모리 부하를 방지하고 처리 속도를 극대화합니다.
* 데이터 무결성 보장 및 유실 방지: 네트워크 지연이나 외부 이메일 API 서버 장애로 인해 Celery 내부에서 작업 실패 및 재시도(Retry)가 발생하더라도, 실제 데이터는 SQLite 원본에 안전하게 보존되어 있으므로 데이터 불일치 및 유실 위험을 원천 차단합니다.