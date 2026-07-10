import time
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Celery 인스턴스 생성 (우체통 주소를 RabbitMQ로 변경)
# 형식: amqp://계정:비밀번호@호스트:포트//
celery_app = Celery(
    "tasks",
    broker="amqp://yoon:password123@127.0.0.1:5672//",
    backend="rpc://"  # RabbitMQ 환경에서는 rpc://를 백엔드로 쓰는 것이 안정적이고 매끄럽습니다.
)
# 2. Celery 태스크 내부에서 DB에 접근하기 위한 설정 (main.py와 동일한 DB)
DATABASE_URL = "sqlite:///./local_service.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. 비동기로 처리할 이메일 발송 함수 정의
@celery_app.task
def send_welcome_email_async(user_id: int):
    # 🌟 [핵심 변경] DB를 열기도 전에, 주문서를 받자마자 무조건 10초를 먼저 멈춥니다.
    print(f"[Celery] 주문 접수 완료. 의도적으로 10초 대기 작동 시작...")
    time.sleep(10) 
    
    db = SessionLocal()
    try:
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()
        
        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True)
            email = Column(String)
            name = Column(String)
            status = Column(String)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "User not found"

        # 실제 이메일 발송 처리 시뮬레이션
        print(f"[Celery] '{user.email}' 주소로 환영 메일 실제 발송!")

        # 작업 성공 후 최종 업데이트
        user.status = "ACTIVE"
        db.commit()
        return f"Email sent to {user.email}"
        
    except Exception as e:
        db.rollback()
        return "Failed"
    finally:
        db.close()