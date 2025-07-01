# app/routers/ai_analysis.py

import json

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import report_runner

router = APIRouter(
    tags=["AI学情分析 (AI Analysis)"],
)


@router.post("/reports/{report_id}/ai-analysis", summary="提交AI分析任务（异步）", status_code=status.HTTP_202_ACCEPTED)
def handle_submit_ai_analysis(
        report_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    为指定报告提交一个AI分析任务。

    此接口为异步接口，会立即返回。AI分析将在后台执行。
    客户端需要通过轮询报告详情接口来获取最终的分析结果和状态。
    """
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()

    # 1. 前置检查
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告未找到")
    if report.status != 'completed':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="主报告尚未完成，无法进行AI分析。")
    if report.ai_analysis_status == 'processing':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI分析任务已在处理中，请勿重复提交。")

    # 如果已完成，直接返回缓存结果，提高效率，避免重复执行
    if report.ai_analysis_status == 'completed' and report.ai_analysis_cache:
        # 使用200 OK状态码，因为是直接返回数据，而不是接受任务
        return {
            "message": "AI分析已完成，直接从缓存返回。",
            "report_id": report.id,
            "ai_analysis_status": report.ai_analysis_status,
            "analysis": json.loads(report.ai_analysis_cache) if report.ai_analysis_cache else None
        }

    # 2. 更新状态为“处理中”，作为任务锁，防止重复提交
    report.ai_analysis_status = 'processing'
    db.commit()

    # 3. 将真正的耗时任务添加到后台队列
    background_tasks.add_task(report_runner.run_ai_analysis_task, report_id=report.id)

    # 4. 立即返回202，告知客户端任务已接受
    return {
        "message": "AI分析任务已成功提交，正在后台处理。",
        "report_id": report.id,
        "ai_analysis_status": 'processing'
    }
