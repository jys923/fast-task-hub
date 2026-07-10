import time
from celery import Celery

# 로컬 Docker로 띄운 Redis를 바라보도록 설정
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def heavy_data_process(target_name: str):
    print(f"[Worker] '{target_name}'에 대한 무거운 백그라운드 작업 시작...")
    time.sleep(5)  # 5초짜리 무거운 연산 시뮬레이션
    print(f"[Worker] '{target_name}' 백그라운드 작업 완료!")
    return f"{target_name} 처리 완료"