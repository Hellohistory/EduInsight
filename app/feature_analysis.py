# app/feature_analysis.py

from typing import List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.analysis_engine.engine import AnalysisEngine
from app.database import get_db, SessionLocal
from app.services import ai_analyzer

router = APIRouter()
def run_analysis_and_save(report_id: int, scope_level: str, scope_ids: List[int]):

    db = SessionLocal()
    report = db.query(models.AnalysisReport).options(joinedload(models.AnalysisReport.exam)).filter(
        models.AnalysisReport.id == report_id).one_or_none()

    if not report or not report.exam:
        db.close()
        return

    try:
        engine = AnalysisEngine(
            exam_id=report.exam_id,
            db=db,
            scope_level=scope_level,
            scope_ids=scope_ids
        )
        report.status = "completed"
        report.full_report_data = engine.get_full_report()
        report.chart_data = engine.get_chart_data()
        if scope_level == 'FULL_EXAM':
            report.exam.status = "completed"
        db.commit()

    except Exception as e:
        db.rollback()
        report_to_update = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
        if report_to_update:
            report_to_update.status = "failed"
            report_to_update.error_message = f"后台分析任务失败: {type(e).__name__}: {str(e)}"
        db.commit()
    finally:
        db.close()


def run_comparison_analysis(comparison_report_id: int, source_report_ids: List[int]):
    db = SessionLocal()
    try:
        source_reports = db.query(models.AnalysisReport).filter(
            models.AnalysisReport.id.in_(source_report_ids),
            models.AnalysisReport.report_type == "single",
            models.AnalysisReport.exam_id.isnot(None)
        ).order_by(models.AnalysisReport.created_at).all()

        if any(r.exam is None for r in source_reports):
            raise ValueError("一个或多个源报告缺少有效的考试关联。")

        exam_names_ordered = [r.exam.name for r in source_reports]

        comparison_result = {
            "metadata": {"compared_exams": exam_names_ordered},
            "students": {},
            "class_trends": {},
            "grade_trends": {},
        }

        for report in source_reports:
            report_data = report.full_report_data
            if not report_data:
                continue
            for table in report_data.get("tables", []):
                for student in table.get("students", []):
                    student_name = student["studentName"]
                    if student_name not in comparison_result["students"]:
                        comparison_result["students"][student_name] = {
                            "tableName": student["tableName"],
                            "timelines": {"totalScore": [], "classRank": [], "gradeRank": []}
                        }
                    s_timeline = comparison_result["students"][student_name]["timelines"]
                    s_timeline["totalScore"].append(student.get("totalScore"))
                    s_timeline["classRank"].append(student.get("classRank"))
                    s_timeline["gradeRank"].append(student.get("gradeRank"))

        for student_name, student_data in comparison_result["students"].items():
            scores = student_data["timelines"]["totalScore"]
            ranks = student_data["timelines"]["gradeRank"]
            if len(scores) >= 2:
                student_data["progress"] = {
                    "score_change": scores[-1] - scores[0] if all(
                        isinstance(x, (int, float)) for x in scores) else None,
                    "rank_change": ranks[0] - ranks[-1] if all(isinstance(x, (int, float)) for x in ranks) else None,
                }

        comparison_report = db.query(models.AnalysisReport).filter(
            models.AnalysisReport.id == comparison_report_id).one()
        comparison_report.status = "completed"
        comparison_report.full_report_data = comparison_result
        db.commit()

    except Exception as e:
        db.rollback()
        report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == comparison_report_id).first()
        if report:
            report.status = "failed"
            report.error_message = f"对比分析任务失败: {type(e).__name__}: {str(e)}"
        db.commit()
    finally:
        db.close()

@router.post("/submit", summary="【核心】提交分析任务（支持自定义范围）", status_code=202)
def handle_submit_analysis(
        request: schemas.AnalysisSubmissionRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    exam = db.query(models.Exam).filter(models.Exam.id == request.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    if request.scope.level == 'FULL_EXAM' and exam.status not in ['draft', 'submitted']:
        raise HTTPException(status_code=400, detail=f"该考试已分析完成，无法重复提交全校分析。")

    if request.scope.level == 'FULL_EXAM':
        exam.status = 'submitted'

    new_report = models.AnalysisReport(
        report_name=request.report_name,
        exam_id=request.exam_id,
        source_description=f"Scope: {request.scope.level}, IDs: {request.scope.ids}",
        status="processing"
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    background_tasks.add_task(
        run_analysis_and_save,
        report_id=new_report.id,
        scope_level=request.scope.level,
        scope_ids=request.scope.ids
    )
    return {"message": "分析任务已成功提交，正在后台处理。", "report_id": new_report.id}


@router.get("/reports", response_model=schemas.PaginatedAnalysisReportResponse, summary="获取所有分析报告列表")
def get_all_reports(
        db: Session = Depends(get_db),
        page: int = Query(1, gt=0, description="页码"),
        page_size: int = Query(10, gt=0, le=100, description="每页数量"),
        query: Optional[str] = Query(None, description="报告名称搜索关键字"),
        status: Optional[str] = Query(None, description="按状态筛选")
):
    base_query = db.query(models.AnalysisReport)

    if query:
        base_query = base_query.filter(models.AnalysisReport.report_name.ilike(f"%{query}%"))
    if status:
        base_query = base_query.filter(models.AnalysisReport.status == status)

    total = base_query.count()

    reports = base_query.order_by(models.AnalysisReport.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "items": reports,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/reports/{report_id}", response_model=schemas.AnalysisReport, summary="获取单个分析报告状态和结果")
def get_report_status(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.AnalysisReport).options(
        joinedload(models.AnalysisReport.exam)
    ).filter(models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    return report


@router.post("/reports/{report_id}/ai-analysis", summary="为报告生成或获取AI分析摘要")
def generate_ai_summary(report_id: int, db: Session = Depends(get_db)):
    try:
        analysis, source = ai_analyzer.get_or_generate_ai_analysis(report_id=report_id, db=db)
        return {"analysis": analysis, "source": source}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发生未知错误: {str(e)}")


@router.delete("/reports/{report_id}", status_code=204, summary="删除分析报告")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    db.delete(report)
    db.commit()
    return


@router.post("/reports/{report_id}/retry", status_code=202, summary="重试失败的分析任务")
def retry_report_analysis(
        report_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告未找到")
    if report.status != 'failed':
        raise HTTPException(status_code=400, detail="只有失败的任务才能重试")
    if not report.source_description:
        raise HTTPException(status_code=400, detail="报告缺少源描述，无法重试")

    try:
        scope_level_match = re.search(r"Scope: (\w+)", report.source_description)
        scope_ids_match = re.search(r"IDs: \[([\d,\s]*)\]", report.source_description)
        if not scope_level_match or not scope_ids_match:
            raise ValueError("无法从描述中解析出原始分析范围")
        scope_level = scope_level_match.group(1)
        scope_ids_str = scope_ids_match.group(1)
        scope_ids = [int(sid.strip()) for sid in scope_ids_str.split(',') if
                     sid.strip().isdigit()] if scope_ids_str else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析重试参数失败: {e}")

    report.status = "processing"
    report.error_message = None
    db.commit()
    db.refresh(report)

    background_tasks.add_task(
        run_analysis_and_save,
        report_id=report.id,
        scope_level=scope_level,
        scope_ids=scope_ids
    )
    return {"message": "任务已重新提交，正在后台处理。", "report_id": report.id}


@router.post("/compare", summary="创建多场考试对比分析任务", status_code=202)
def handle_create_comparison_report(
        request_data: schemas.ComparisonReportRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    source_reports = db.query(models.AnalysisReport).filter(
        models.AnalysisReport.id.in_(request_data.report_ids),
        models.AnalysisReport.status == "completed"
    ).all()
    if len(source_reports) != len(request_data.report_ids):
        raise HTTPException(status_code=404, detail="一个或多个报告ID不存在或尚未分析完成。")

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

    background_tasks.add_task(
        run_comparison_analysis,
        comparison_report_id=new_comparison_report.id,
        source_report_ids=request_data.report_ids
    )
    return {"message": "对比分析任务已创建。", "comparison_report_id": new_comparison_report.id}