import time
from celery import Celery

# 1. Celery 인스턴스 설정 (RabbitMQ 브로커 및 rpc:// 결과 저장소 활성화)
celery_app = Celery(
    "tasks",
    broker="amqp://yoon:password123@127.0.0.1:5672//",
    backend="rpc://"  # 🌟 RPC 백엔드 다시 부활!
)

# 2. bind=True를 주어 self 인자로 Celery 내장 상태 제어권을 확보합니다.
@celery_app.task(bind=True)
def send_welcome_email_async(self, user_id: int):
    try:
        # [상태 1] 25% -> 래빗엠큐 RPC 임시 채널로 진행 상황 즉시 전송
        print("====== [RPC] 1단계: 유저 정보 검증 시작 ======")
        self.update_state(state="PROGRESS", meta={"current": 25, "msg": "유저 정보 검증 중..."})
        time.sleep(10)

        # [상태 2] 50%
        print("====== [RPC] 2단계: 이메일 템플릿 생성 시작 ======")
        self.update_state(state="PROGRESS", meta={"current": 50, "msg": "환영 이메일 템플릿 생성 중..."})
        time.sleep(10)

        # [상태 3] 75%
        print("====== [RPC] 3단계: 이메일 발송 시작 ======")
        user_status = "STEP_4_EMAIL_SENT"
        self.update_state(state="PROGRESS", meta={"current": 75, "msg": "이메일 실제 발송 중..."})
        time.sleep(10)

        print("====== [RPC] 4단계: 모든 프로세스 완료 ======")
        # 최종 완료 시 결과 데이터 리턴
        return {"current": 100, "msg": "가입 승인 및 이메일 발송 완료"}

    except Exception as e:
        self.update_state(state="FAILURE", meta={"msg": f"에러 발생: {str(e)}"})
        return "Failed"