## 1. 인프라 자원 실행 (Docker RabbitMQ)

본 프로젝트는 메시지의 안정성과 신뢰성을 확보하기 위해 전문 메시지 브로커인 RabbitMQ를 사용합니다. 관리자 대시보드(Management UI)가 포함된 버전을 구동합니다.

```bash
docker-compose up -d

```

* RabbitMQ 메인 포트: `5672`
* RabbitMQ 대시보드 포트: `15672` (계정: `yoon` / 비밀번호: `password123`)

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

가상환경이 활성화된 상태에서 RabbitMQ 대기열을 감시할 워커를 구동합니다.

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

### 1단계: Swagger UI 접속 및 회원가입 요청
1. 브라우저를 열고 `http://127.0.0.1:8000/docs` 주소로 접속합니다.
2. `POST /users` 엔드포인트를 통해 가입 요청을 보냅니다.
3. 백그라운드 작업이 트리거되지만, API 서버는 대기 시간 없이 즉시 응답을 반환합니다. 이 시점에서 유저의 초기 `status` 값은 `PENDING`입니다.

### 2단계: 실시간 백그라운드 처리 및 상태 전환 확인
1. `POST` 요청 성공 즉시 `GET /users/{user_id}` 엔드포인트를 통해 유저 조회를 수행합니다.
2. Celery Worker 내부의 대기 시간 동안 작업을 처리 중이므로, 이 타이밍에 조회된 유저의 상태는 여전히 `PENDING`으로 유지됩니다.
3. Celery 실행 터미널 로그에 완료 메시지가 출력된 것을 확인한 후 다시 한번 조회를 호출하면, 유저의 최종 상태가 `ACTIVE`로 변경되어 있는 것을 확인할 수 있습니다.

## 5. 프로젝트 아키텍처 및 데이터 흐름

본 프로젝트는 시스템 간 결합도를 낮추고 데이터 무결성을 보장하는 실무형 아키텍처로 설계되었습니다.

### 데이터 흐름도

1. [FastAPI] 사용자로부터 가입 요청 수신
2. [FastAPI ➡️ SQLite] 데이터베이스에 유저 정보를 `PENDING` 상태로 1차 저장 후 고유 ID 발급
3. [FastAPI ➡️ RabbitMQ] 생성된 유저의 고유 식별자(`user_id`)만 AMQP 프로토콜을 통해 메시지 큐에 투척 후 사용자에게 즉시 응답
4. [Celery Worker ⬅️ RabbitMQ] 대기 중이던 일꾼(Worker)이 큐에서 주문서(`user_id`)를 확보
5. [Celery Worker ➡️ SQLite] 일꾼이 직접 데이터베이스를 조회하여 데이터 획득 후 실제 비동기 비즈니스 연산 수행
6. [Celery Worker ➡️ SQLite] 작업 완료 후 직접 데이터베이스를 업데이트하여 유저 상태를 `ACTIVE`로 변경

### 식별자(ID) 기반 큐 설계의 아키텍처적 장점

* 큐의 경량화: 대용량 오브젝트 전체를 큐에 넘기지 않고 고유한 정수형 ID만 넘김으로써 큐 시스템의 메모리 부하를 방지하고 처리 속도를 극대화합니다.
* 데이터 무결성 보장: 비동기 작업 중 장애가 발생하여 재시도가 일어나더라도, 원본 데이터는 SQLite에 안전하게 보존되어 있으므로 데이터 불일치 위험을 차단합니다.

## 6. 고도화 작업: 비동기 진행률(0% ~ 100%) 추적 아키텍처

사용자 화면(UI)에 실시간으로 작업 진행 상태를 반영하기 위해 2가지 고도화 패턴을 결합하여 구현합니다.

### 패턴 1: 세분화된 상태 테이블(State DB) 활용

* 개념: 단편적인 `PENDING`/`ACTIVE` 구조를 탈피하고, 비즈니스 로직 단계를 세분화하여 DB 장부에 기록하는 방식입니다.
* 단계 설계: `STEP_1_RECEIVED`(0%) ➡️ `STEP_2_VALIDATED`(25%) ➡️ `STEP_3_EMAIL_GENERATED`(50%) ➡️ `STEP_4_EMAIL_SENT`(75%) ➡️ `ACTIVE`(100%)
* 장점: 비즈니스 관점에서 사용자가 어느 단계에 머물러 있는지 명확히 추적할 수 있으며, 영구적인 상태 모니터링이 가능합니다.

### 패턴 2: Celery 자체 상태 저장소(Result Backend) 활용

* 개념: Celery 내부의 실시간 메타데이터 기능(`self.update_state`)을 활용하여 현재 연산 진행률을 대기열 저장소에 실시간으로 기록하는 방식입니다.
* 데이터 구조: `{"state": "PROGRESS", "meta": {"current": 30, "total": 100}}`
* 장점: DB에 잦은 쓰기(Write) 부하를 주지 않고도 소수점 단위의 정밀한 진행률 퍼센티지를 초고속으로 UI에 제공할 수 있습니다.
---
형님, 정신 차리겠습니다. 제 잘못입니다.

방금 제가 드린 리드미 설명에 또 슬쩍 **`backend="rpc://"`** 관련 헛소리가 섞여 들어가서 헷갈리게 해 드렸네요.

맞습니다. 이번에 고친 코드에서는 **`rpc://`를 완전히 도려냈기 때문에 리드미에 언급할 이유도, 쓸데없이 비교할 이유도 전혀 없습니다.** 아예 우리 시스템 역사에서 지워버려야 하는 게 맞습니다.

형님 지적대로 쓸데없는 소리 싹 다 쳐내고, 지금 우리 코드(`backend` 아예 없는 상태)에 딱 맞게 정정한 진짜 리드미입니다. 이것만 복사해서 덮어쓰시면 됩니다.

---

# Fast Task Hub Pro - Pure DB-Driven Progress System

RabbitMQ와 Celery를 활용하여 무거운 비동기 작업을 처리하고, SQLite DB(SQLAlchemy)를 마스터 장부로 삼아 실시간 작업 진행률을 추적하는 백엔드 시스템입니다.

## 1. 아키텍처 핵심 설계 (Pure DB-Driven)
본 시스템은 Celery의 결과 저장소(Backend) 설정을 아예 사용하지 않는 **"순수 데이터베이스 장부 중심 구조"**로 설계되었습니다.

* **Broker (RabbitMQ):** FastAPI가 던진 비동기 작업 주문서를 일꾼에게 배달하는 우체통 역할만 전담합니다.
* **Master DB (SQLite / SQLAlchemy):** Celery 일꾼이 단계를 밟을 때마다 `db.commit()`을 실행하여 현재 비즈니스 상태를 즉시 진짜 장부에 기록합니다.
* **FastAPI:** 회원가입 성공 시 발급한 `user_id`를 기반으로 Master DB만 직접 찔러서 실시간 진행률과 메시지를 프론트엔드에 내려줍니다.

---

## 2. 실시간 상태 및 퍼센트 매핑 규격

시스템 내부에서 상태가 변경될 때마다 API는 아래와 같이 퍼센트와 메시지를 자로 잰 듯이 매핑하여 UI에 내려줍니다.

| 비즈니스 상태 (`status`) | 진행률 (`percentage`) | 화면 표시 메시지 (`status_message`) |
| :--- | :---: | :--- |
| `STEP_1_RECEIVED` | 0.0% | 회원가입 요청 접수됨 |
| `STEP_2_VALIDATED` | 25.0% | 유저 정보 검증 중... |
| `STEP_3_EMAIL_GENERATED` | 50.0% | 환영 이메일 템플릿 생성 중... |
| `STEP_4_EMAIL_SENT` | 75.0% | 이메일 실제 발송 중... |
| `ACTIVE` | 100.0% | 가입 승인 및 이메일 발송 완료 (최종 완료) |

---

## 3. 실행 및 테스트 방법

### Step 1: 일꾼(Celery) 실행
리눅스/WSL 환경에서 프로세스 간 잠금 및 격리 문제를 방지하기 위해 일꾼을 단일 가동 모드(`-P solo`)로 실행합니다.
```bash
celery -A tasks.celery_app worker --loglevel=info -P solo

```

### Step 2: 웹 서버(FastAPI) 실행

```bash
uvicorn main:app --reload

```

### Step 3: 실시간 검증 시나리오

1. `POST /users` 엔드포인트를 통해 신규 회원가입을 요청합니다.
2. 응답으로 즉시 고유 식별자인 `"user_id"`를 반환받습니다.
3. 곧바로 `GET /users/{user_id}/progress` 엔드포인트를 1~2초 간격으로 연속 호출합니다.
4. DB 장부와 동기화되어 25% -> 50% -> 75% -> 100%로 다이내믹하게 차오르는 실시간 진행 상태 데이터를 확인할 수 있습니다.

# Fast Task Hub Pro - RPC Backend Progress System

RabbitMQ와 Celery의 내장 결과 저장소(`backend="rpc://"`) 아키텍처를 극한으로 활용하여, 진짜 장부(DB)를 거치지 않고 오직 인프라 메시징 자원만으로 비동기 작업의 실시간 진행률을 추적하는 고도화된 백엔드 시스템입니다.

## 1. 아키텍처 핵심 설계 (RPC Backend-Driven)
본 시스템은 데이터베이스에 불필요한 I/O 부하를 주지 않고, RabbitMQ 내부의 임시 메시지 채널을 통해 작업의 상태를 주고받도록 설계되었습니다.

* **Broker (RabbitMQ):** FastAPI가 발행한 작업 주문서를 Celery 일꾼에게 안전하게 배달합니다.
* **Backend (RabbitMQ RPC):** Celery 일꾼이 `self.update_state()`를 통해 발행하는 실시간 상태(PROGRESS) 및 최종 결과물(SUCCESS)을 임시 큐(Queue) 형태로 관리하는 영수증 보관함 역할을 합니다.
* **Master DB (SQLite / SQLAlchemy):** 영구 저장이 필요한 회원의 기본 정보(이메일, 이름 등)만 딱 한 번 저장하며, 중간 진행 상황 추적 연산에는 전혀 관여하지 않습니다.
* **FastAPI:** 회원가입 성공 시 발급된 고유 영수증 번호(`task_id`)를 사용하여 RabbitMQ RPC 저장소를 직접 찔러 실시간 진행률을 프론트엔드에 내려줍니다.

---

## 2. 실시간 상태 및 퍼센트 매핑 규격

Celery 일꾼이 단계를 밟을 때마다 RabbitMQ RPC 백엔드에 기록되는 실시간 메타데이터 구조입니다.

| Celery 상태 (`state`) | 진행률 (`percentage`) | 화면 표시 메시지 (`status_message`) |
| :--- | :---: | :--- |
| `PENDING` | 0.0% | 작업이 큐에서 대기 중이거나 처리 시작 전입니다. |
| `PROGRESS` (1단계) | 25.0% | 유저 정보 검증 중... |
| `PROGRESS` (2단계) | 50.0% | 환영 이메일 템플릿 생성 중... |
| `PROGRESS` (3단계) | 75.0% | 이메일 실제 발송 중... |
| `SUCCESS` (최종 완료) | 100.0% | 가입 승인 및 이메일 발송 완료 |

---

## 3. 실행 및 테스트 방법

### Step 1: 일꾼(Celery) 실행
리눅스/WSL 환경에서 프로세스 간 잠금 및 격리 문제를 방지하기 위해 일꾼을 단일 가동 모드(`-P solo`)로 실행합니다.
```bash
celery -A tasks.celery_app worker --loglevel=info -P solo

```

### Step 2: 웹 서버(FastAPI) 실행

```bash
uvicorn main:app --reload

```

### Step 3: 실시간 검증 시나리오

1. `POST /users` 엔드포인트를 통해 신규 회원가입을 요청합니다.
2. 응답으로 즉시 고유 영수증 번호인 `"task_id"`를 반환받습니다.
3. 곧바로 `GET /tasks/{task_id}/progress` 엔드포인트를 1~2초 간격으로 연속 호출합니다.
4. 진짜 장부(DB) 조회를 완전히 배제한 상태에서, RabbitMQ RPC 자원만으로 25% -> 50% -> 75% -> 100%로 다이내믹하게 차오르는 실시간 진행 상태 데이터를 확인할 수 있습니다.

---