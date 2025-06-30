# app/feature_analysis.py

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.analysis_engine.facade import AnalysisEngine
from app.database import get_db
from app.services import ai_analyzer, report_runner

router = APIRouter(
    tags=["学情分析 (Feature Analysis)"],
)

@router.post("/submit", response_model=schemas.ReportSubmissionResponse, summary="【核心】提交分析任务", status_code=202)
def handle_submit_analysis(
    request: schemas.AnalysisSubmissionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    提交一个新的单场考试分析任务，支持范围为整校、年级或班级。

    任务将在后台异步执行，提交后立即返回任务信息。
    """
    exam = db.query(models.Exam).filter(models.Exam.id == request.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    # 若为整场考试分析，更新考试状态为 submitted，避免重复分析
    if request.scope.level == 'FULL_EXAM':
        if exam.status not in ['draft', 'submitted']:
            raise HTTPException(status_code=400, detail="该考试已分析完成，无法重复提交全校分析。")
        exam.status = 'submitted'

    # 创建分析报告记录
    new_report = models.AnalysisReport(
        report_name=request.report_name,
        exam_id=request.exam_id,
        source_description=f"Scope: {request.scope.level}, IDs: {request.scope.ids}",
        status="processing",
        report_type="single"
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # 异步启动分析任务（后台执行）
    background_tasks.add_task(
        report_runner.run_single_exam_analysis_task,
        report_id=new_report.id,
        scope_level=request.scope.level,
        scope_ids=request.scope.ids
    )

    return {"message": "分析任务已成功提交，正在后台处理。", "report_id": new_report.id}


@router.post("/compare", response_model=schemas.ReportSubmissionResponse, summary="创建多场考试对比分析任务", status_code=202)
def handle_create_comparison_report(
    request_data: schemas.ComparisonReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    基于多个已完成的单场考试报告，生成一份对比分析报告。
    """
    source_reports = db.query(models.AnalysisReport).filter(
        models.AnalysisReport.id.in_(request_data.report_ids),
        models.AnalysisReport.status == "completed",
        models.AnalysisReport.report_type == "single"
    ).all()

    if len(source_reports) != len(request_data.report_ids):
        raise HTTPException(status_code=404, detail="一个或多个源报告ID不存在或尚未分析完成。")

    report_name = request_data.report_name or f"对 {len(source_reports)} 场考试的对比分析"

    new_comparison_report = models.AnalysisReport(
        report_name=report_name,
        status="processing",
        source_description=f"Comparing reports: {str(request_data.report_ids)}",
        report_type="comparison"
    )
    db.add(new_comparison_report)
    db.commit()
    db.refresh(new_comparison_report)

    # 异步执行对比分析
    background_tasks.add_task(
        report_runner.run_comparison_analysis_task,
        comparison_report_id=new_comparison_report.id,
        source_report_ids=request_data.report_ids
    )

    return {"message": "对比分析任务已创建。", "report_id": new_comparison_report.id}


@router.get("/reports", response_model=schemas.PaginatedAnalysisReportResponse, summary="获取分析报告列表")
def get_all_reports(
    page: int = Query(1, gt=0, description="页码"),
    page_size: int = Query(10, gt=0, le=100, description="每页数量"),
    query: Optional[str] = Query(None, description="报告名称搜索关键字"),
    status: Optional[str] = Query(None, description="按状态筛选 (processing, completed, failed)"),
    report_type: Optional[str] = Query(None, description="按报告类型筛选 (single, comparison)"),
    db: Session = Depends(get_db)
):
    """
    分页查询分析报告列表，支持名称模糊搜索、状态筛选、类型筛选。
    """
    base_query = db.query(models.AnalysisReport)
    if query:
        base_query = base_query.filter(models.AnalysisReport.report_name.ilike(f"%{query}%"))
    if status:
        base_query = base_query.filter(models.AnalysisReport.status == status)
    if report_type:
        base_query = base_query.filter(models.AnalysisReport.report_type == report_type)

    total = base_query.count()
    reports = base_query.order_by(models.AnalysisReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {"items": reports, "total": total, "page": page, "pageSize": page_size}


@router.get("/reports/{report_id}", response_model=schemas.AnalysisReport, summary="获取单个分析报告的元数据和完整结果")
def get_report_details(report_id: int, db: Session = Depends(get_db)):
    """
    获取指定分析报告的完整内容，包括元数据与分析结构体。
    """
    report = db.query(models.AnalysisReport).options(joinedload(models.AnalysisReport.exam)).filter(
        models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    return report

def get_report_from_db(report_id: int, db: Session) -> models.AnalysisReport:
    """
    工具函数：从数据库中读取报告，并验证其已完成状态与数据存在性。
    """
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    if report.status != 'completed':
        raise HTTPException(status_code=400, detail=f"报告状态为 '{report.status}'，尚未分析完成。")
    if not report.full_report_data:
        raise HTTPException(status_code=404, detail="报告数据为空。")
    return report


@router.get("/reports/{report_id}/group-stats", summary="获取报告的整体统计数据")
def get_report_group_stats(report_id: int, db: Session = Depends(get_db)):
    """
    从报告中提取整体（年级/全体）统计数据结构。
    """
    report = get_report_from_db(report_id, db)
    engine = AnalysisEngine(report.full_report_data)
    return engine.get_group_stats()


@router.get("/reports/{report_id}/class/{class_name}", summary="获取报告中指定班级的报告")
def get_report_class_details(report_id: int, class_name: str, db: Session = Depends(get_db)):
    """
    获取分析报告中某个班级的详细结构数据。
    """
    report = get_report_from_db(report_id, db)
    engine = AnalysisEngine(report.full_report_data)
    class_report = engine.get_class_report(class_name)
    if not class_report:
        raise HTTPException(status_code=404, detail=f"在报告中未找到班级 '{class_name}'")
    return class_report


@router.get("/reports/{report_id}/student/{student_name}", summary="获取报告中指定学生的报告")
def get_report_student_details(report_id: int, student_name: str, db: Session = Depends(get_db)):
    """
    获取分析报告中某位学生的详细结构数据。
    """
    report = get_report_from_db(report_id, db)
    engine = AnalysisEngine(report.full_report_data)
    student_report = engine.get_student_report(student_name)
    if not student_report:
        raise HTTPException(status_code=404, detail=f"在报告中未找到学生 '{student_name}'")
    return student_report


@router.get("/reports/{report_id}/charts", summary="获取报告的图表优化数据")
def get_report_chart_data(report_id: int, db: Session = Depends(get_db)):
    """
    动态生成并返回图表所需的结构化数据。
    图表数据不存数据库，前端每次访问时实时生成。
    """
    report = get_report_from_db(report_id, db)
    engine = AnalysisEngine(report.full_report_data)
    return engine.get_chart_data()


@router.delete("/reports/{report_id}", status_code=204, summary="删除分析报告")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    """
    从数据库中删除指定的分析报告。
    """
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    db.delete(report)
    db.commit()
    return


@router.post("/reports/{report_id}/retry", status_code=202, summary="重试失败的分析任务")
def retry_report_analysis(report_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    对失败的分析报告任务进行重试。会从报告源描述中恢复 scope_level 和 scope_ids。
    """
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    if report.status != 'failed':
        raise HTTPException(status_code=400, detail="只有失败的任务才能重试")
    if not report.source_description:
        raise HTTPException(status_code=400, detail="报告缺少源描述，无法重试")

    try:
        # 从 source_description 中提取 scope_level 和 scope_ids
        scope_level_match = re.search(r"Scope: (\w+)", report.source_description)
        scope_ids_match = re.search(r"IDs: \[([\d,\s]*)\]", report.source_description)
        if not scope_level_match or not scope_ids_match:
            raise ValueError("无法从描述中解析出原始分析范围")

        scope_level = scope_level_match.group(1)
        scope_ids_str = scope_ids_match.group(1)
        scope_ids = [int(sid.strip()) for sid in scope_ids_str.split(',') if sid.strip().isdigit()] if scope_ids_str else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析重试参数失败: {e}")

    report.status = "processing"
    report.error_message = None
    db.commit()

    background_tasks.add_task(
        report_runner.run_single_exam_analysis_task,
        report_id=report.id,
        scope_level=scope_level,
        scope_ids=scope_ids
    )
    return {"message": "任务已重新提交，正在后台处理。", "report_id": report.id}


@router.post("/reports/{report_id}/ai-analysis", summary="为报告生成或获取AI分析摘要")
def generate_ai_summary(report_id: int, db: Session = Depends(get_db)):
    """
    基于已有的分析报告内容，生成 AI 摘要（如 GPT 分析）。
    若之前生成过将直接返回缓存结果。
    """
    try:
        analysis, source = ai_analyzer.get_or_generate_ai_analysis(report_id=report_id, db=db)
        return {"analysis": analysis, "source": source}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发生未知错误: {str(e)}")
