from fastapi import FastAPI
from tasks import heavy_data_process

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "FastAPI Server Running"}

@app.get("/trigger/{name}")
def trigger_task(name: str):
    # 📌 핵심: .delay()를 사용하여 작업을 즉시 실행하지 않고 Redis 큐로 던집니다.
    heavy_data_process.delay(name)
    
    # 큐에 던지자마자 사용자에게는 응답을 즉시 반환합니다.
    return {
        "status": "Accepted",
        "message": f"'{name}' 작업이 백그라운드 대기열에 등록되었습니다. API는 즉시 응답합니다."
    }