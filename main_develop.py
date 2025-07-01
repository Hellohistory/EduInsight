# main.py

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.feature_analysis import router as analysis_router
from app.routers.ai_analysis import router as ai_analysis_router

from app.routers.feature_classes import router as classes_router
from app.routers.feature_exams import router as exams_router
from app.routers.feature_grades import router as grades_router
from app.routers.feature_scores import router as scores_router
from app.routers.feature_students import router as students_router

from app.database import Base, engine


def initialize_database():
    db_file = "school_analysis_compact.db"
    if not os.path.exists(db_file):
        print("首次运行：创建数据库和表结构中...")
        Base.metadata.create_all(bind=engine)
        print("数据库初始化完成。")
    else:
        print("数据库已存在，跳过初始化。")


initialize_database()

app = FastAPI(
    title="EduInsight 分析系统 API",
    description="由 Hellohistory 开发设计",
    version="1.0.0",
)

# 添加 CORS 中间件
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api/analysis", tags=["学情分析 (Feature Analysis)"])
app.include_router(ai_analysis_router, prefix="/api/analysis", tags=["AI学情分析 (AI Analysis)"])
app.include_router(students_router, prefix="/api/students", tags=["学生管理"])
app.include_router(classes_router, prefix="/api/classes", tags=["班级管理"])
app.include_router(grades_router, prefix="/api/grades", tags=["年级管理"])
app.include_router(exams_router, prefix="/api/exams", tags=["考试与学科管理"])
app.include_router(scores_router, prefix="/api/scores", tags=["成绩管理"])


@app.get("/api", summary="API 根路径与健康检查")
def read_root():
    return {"message": "欢迎使用由 Hellohistory 开发设计的 EduInsight 分析系统 API"}



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
