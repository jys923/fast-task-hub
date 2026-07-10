import time
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Celery 인스턴스 설정 (RabbitMQ 브로커 및 rpc:// 결과 저장소 활성화)
celery_app = Celery(
    "tasks",
    broker="amqp://yoon:password123@127.0.0.1:5672//"
)

DATABASE_URL = "sqlite:///./local_service.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB 모델 재정의용 설정
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    name = Column(String)
    status = Column(String)

# 2. bind=True를 주어 self 인자로 Celery 내장 상태 제어권을 확보합니다.
@celery_app.task(bind=True)
def send_welcome_email_async(self, user_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "User not found"

        # [상태 1] 25%
        print("====== [LOG] 1단계: 유저 정보 검증 시작 ======") # 🌟 로그 추가
        user.status = "STEP_2_VALIDATED"
        db.commit()
        time.sleep(10)

        # [상태 2] 50%
        print("====== [LOG] 2단계: 이메일 템플릿 생성 시작 ======") # 🌟 로그 추가
        user.status = "STEP_3_EMAIL_GENERATED"
        db.commit()
        time.sleep(10)

        # [상태 3] 75%
        print("====== [LOG] 3단계: 이메일 발송 시작 ======") # 🌟 로그 추가
        user.status = "STEP_4_EMAIL_SENT"
        db.commit()
        time.sleep(10)

        user.status = "ACTIVE"
        db.commit()
        print("====== [LOG] 4단계: 모든 프로세스 완료 ======") # 🌟 로그 추가
        return {"current": 100, "total": 100, "msg": "가입 승인 및 이메일 발송 완료"}

    except Exception as e:
        db.rollback()
        self.update_state(state="FAILURE", meta={"msg": f"에러 발생: {str(e)}"})
        return "Failed"
    finally:
        db.close()