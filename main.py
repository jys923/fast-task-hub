from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# tasks.py에서 Celery 앱 임포트
from tasks import celery_app, send_welcome_email_async

DATABASE_URL = "sqlite:///./local_service.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserORM(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    status = Column(String, default="STEP_1_RECEIVED")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pure DB-Driven Progress Hub")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserCreate(BaseModel):
    email: EmailStr
    name: str

# 1. 회원가입 요청 API (응답으로 user_id를 확실하게 반환합니다)
@app.post("/users", status_code=201)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserORM).filter(UserORM.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    
    new_user = UserORM(email=user_data.email, name=user_data.name, status="STEP_1_RECEIVED")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Celery 일꾼에게 작업을 넘깁니다.
    send_welcome_email_async.delay(new_user.id)
    
    # 🌟 프론트엔드가 조회할 수 있도록 user_id를 명확하게 리턴합니다.
    return {
        "message": "회원가입 접수 완료",
        "user_id": new_user.id,
        "status": new_user.status
    }

# 2. 실시간 진행률 조회 API (발급받은 user_id 하나로만 깔끔하게 찌릅니다)
@app.get("/users/{user_id}/progress")
def get_user_progress(user_id: int, db: Session = Depends(get_db)):
    # DB에서 유저의 현재 세분화 상태 획득
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    
    # 상태별 퍼센트 및 메시지 매핑 체계
    status_map = {
        "STEP_1_RECEIVED": {"percentage": 0.0, "msg": "회원가입 요청 접수됨", "completed": False},
        "STEP_2_VALIDATED": {"percentage": 25.0, "msg": "유저 정보 검증 중...", "completed": False},
        "STEP_3_EMAIL_GENERATED": {"percentage": 50.0, "msg": "환영 이메일 템플릿 생성 중...", "completed": False},
        "STEP_4_EMAIL_SENT": {"percentage": 75.0, "msg": "이메일 실제 발송 중...", "completed": False},
        "ACTIVE": {"percentage": 100.0, "msg": "가입 승인 및 이메일 발송 완료", "completed": True}
    }
    
    current_progress = status_map.get(
        user.status, 
        {"percentage": 0.0, "msg": "상태 확인 불가", "completed": False}
    )

    return {
        "user_id": user.id,
        "business_status": user.status,
        "percentage": current_progress["percentage"],
        "status_message": current_progress["msg"],
        "is_completed": current_progress["completed"]
    }