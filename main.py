from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from celery.result import AsyncResult

# tasks.py에서 Celery 앱과 태스크 함수 임포트
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
    # 🌟 이제 DB에는 상태 변환 이정표를 적지 않습니다. 오직 정보 저장용!

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RPC Backend Progress Hub")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserCreate(BaseModel):
    email: EmailStr
    name: str

@app.post("/users", status_code=201)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserORM).filter(UserORM.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    
    new_user = UserORM(email=user_data.email, name=user_data.name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 🌟 비동기 태스크를 발행하고, 래빗엠큐 RPC 장부 접근용 task_id를 확보합니다.
    task_result = send_welcome_email_async.delay(new_user.id)
    
    return {
        "message": "회원가입 접수 완료",
        "user_id": new_user.id,
        "task_id": task_result.id  # 🌟 UI가 진행률을 조회할 때 쓸 영수증 번호 반환!
    }

# 🌟 래빗엠큐 RPC 결과 저장소에서 실시간으로 진행률 영수증을 가로채는 API
@app.get("/tasks/{task_id}/progress")
def get_task_progress(task_id: str):
    # Celery RPC 백엔드 장부에서 영수증 번호로 상태 직접 조회
    res = AsyncResult(task_id, app=celery_app)
    
    percentage = 0.0
    status_message = "대기 중..."
    is_completed = False
    
    # RPC 백엔드가 가로챈 실시간 상태 처리 파트
    if res.state == "PROGRESS":
        percentage = res.info.get("current", 0.0)
        status_message = res.info.get("msg", "")
    elif res.state == "SUCCESS":
        percentage = 100.0
        status_message = res.result.get("msg", "완료") if isinstance(res.result, dict) else "완료"
        is_completed = True
    elif res.state == "FAILURE":
        status_message = "작업 처리 중 시스템 에러 발생"
    elif res.state == "PENDING":
        status_message = "작업이 큐에서 대기 중이거나 처리 시작 전입니다."

    return {
        "task_id": task_id,
        "celery_state": res.state,      # 래빗엠큐가 전달한 내장 상태 (PROGRESS, SUCCESS 등)
        "percentage": percentage,       # RPC 메타데이터에서 추출한 진행률
        "status_message": status_message,
        "is_completed": is_completed
    }