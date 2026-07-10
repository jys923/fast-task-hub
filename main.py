import time
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, EmailStr
from tasks import send_welcome_email_async

# 1. Database 설정 (로컬 SQLite 파일 사용)
DATABASE_URL = "sqlite:///./local_service.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. DB 테이블 모델 정의
class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    status = Column(String, default="PENDING")

# 서버 시작 시 테이블 자동 생성
Base.metadata.create_all(bind=engine)

# DB 세션 의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 3. Request용 Pydantic 스키마 정의
class UserCreate(BaseModel):
    email: EmailStr
    name: str

# 4. FastAPI 앱 선언
app = FastAPI(title="Fast Task Hub - Step 1")

# 가상의 무거운 이메일 발송 함수 (동기식)
def send_welcome_email_sync(email: str, name: str):
    print(f"[Email] '{email}' 주소로 환영 메일 발송 시작 (5초 소요)...")
    time.sleep(5)  # 5초간 네트워크 지연 시뮬레이션
    print(f"[Email] '{email}' 주소로 환영 메일 발송 완료!")

# 5. API 엔드포인트 구현
@app.post("/users", status_code=201)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserORM).filter(UserORM.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    
    new_user = UserORM(email=user_data.email, name=user_data.name, status="PENDING")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # ❌ [기존 동기 방식 제거]
    # send_welcome_email_sync(new_user.email, new_user.name)
    
    # ⭕ [새로운 비동기 방식 도입] 
    # 레디스 큐에 유저 ID 하나만 툭 던지고 즉시 다음 줄로 넘어갑니다.
    send_welcome_email_async.delay(new_user.id)
    
    return {
        "message": "회원가입 접수가 완료되었습니다. 환영 메일은 백그라운드에서 발송됩니다.",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "status": new_user.status  # 현재는 PENDING 상태로 즉시 반환됨
        }
    }

@app.get("/users/{user_id}")
def get_user_status(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "status": user.status
    }