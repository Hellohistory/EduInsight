# app/services/report_runner.py

from typing import List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import AnalysisReport
from app.analysis_engine.facade import create_single_exam_report
from app.services import ai_analyzer


def run_single_exam_analysis_task(report_id: int, scope_level: str, scope_ids: List[int]):
    """
    执行单场考试的后台分析任务。
    (此函数保持不变)
    """
    db: Session = SessionLocal()
    try:
        report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).one_or_none()
        if not report or not report.exam:
            return

        engine = create_single_exam_report(
            exam_id=report.exam_id,
            db=db,
            scope_level=scope_level,
            scope_ids=scope_ids
        )

        report.status = "completed"
        report.full_report_data = engine.get_full_report()

        if scope_level == 'FULL_EXAM':
            report.exam.status = "completed"

        db.commit()

    except Exception as e:
        db.rollback()
        report_to_update = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
        if report_to_update:
            report_to_update.status = "failed"
            report_to_update.error_message = f"后台分析任务失败: {type(e).__name__}: {str(e)}"
            db.commit()
    finally:
        db.close()


def run_comparison_analysis_task(comparison_report_id: int, source_report_ids: List[int]):
    """
    执行多场考试的对比分析后台任务。
    (此函数保持不变)
    """
    db: Session = SessionLocal()
    try:
        source_reports = db.query(AnalysisReport).filter(
            AnalysisReport.id.in_(source_report_ids),
            AnalysisReport.report_type == "single",
            AnalysisReport.exam_id.isnot(None)
        ).order_by(AnalysisReport.created_at).all()

        if any(r.exam is None for r in source_reports):
            raise ValueError("一个或多个源报告缺少有效的考试关联。")

        exam_names_ordered = [r.exam.name for r in source_reports]

        comparison_result = {
            "metadata": {
                "compared_exams": exam_names_ordered,
                "source_report_ids": source_report_ids
            },
            "students": {},
            "class_trends": {},
            "grade_trends": {}
        }

        for idx, report in enumerate(source_reports):
            report_data = report.full_report_data
            if not report_data or 'tables' not in report_data:
                continue

            for table in report_data.get("tables", []):
                for student in table.get("students", []):
                    student_id = student.get("studentId")
                    if not student_id: continue

                    student_entry = comparison_result["students"].setdefault(student_id, {
                        "studentName": student["studentName"],
                        "tableName": student["tableName"],
                        "timelines": {
                            "totalScore": [None] * len(source_reports),
                            "gradeRank": [None] * len(source_reports)
                        }
                    })

                    ranks = student.get("ranks", {}).get("totalScore", {})
                    student_entry["timelines"]["totalScore"][idx] = student.get("totalScore")
                    student_entry["timelines"]["gradeRank"][idx] = ranks.get("gradeRank")

        for student_data in comparison_result["students"].values():
            scores = [s for s in student_data["timelines"]["totalScore"] if s is not None]
            ranks = [r for r in student_data["timelines"]["gradeRank"] if r is not None]

            if len(scores) >= 2:
                score_change = scores[-1] - scores[0] if all(isinstance(x, (int, float)) for x in scores) else None
                rank_change = ranks[0] - ranks[-1] if all(isinstance(x, (int, float)) for x in ranks) else None
                student_data["progress"] = {
                    "score_change": score_change,
                    "rank_change": rank_change
                }

        comparison_report = db.query(AnalysisReport).filter(AnalysisReport.id == comparison_report_id).one()
        comparison_report.status = "completed"
        comparison_report.full_report_data = comparison_result
        db.commit()

    except Exception as e:
        db.rollback()
        report = db.query(AnalysisReport).filter(AnalysisReport.id == comparison_report_id).first()
        if report:
            report.status = "failed"
            report.error_message = f"对比分析任务失败: {type(e).__name__}: {str(e)}"
            db.commit()
    finally:
        db.close()

def run_ai_analysis_task(report_id: int):
    """
    在后台安全地执行AI分析的独立任务。

    此函数由API层的 BackgroundTasks 调用，负责处理AI分析的完整生命周期，
    包括状态更新和错误处理。

    :param report_id: 要进行AI分析的报告ID。
    """
    db: Session = SessionLocal()
    try:
        # 调用核心AI分析服务，该服务会处理所有逻辑（包括调用LLM和缓存）
        # 它也会在成功时将ai_analysis_status更新为'completed'
        ai_analyzer.get_or_generate_ai_analysis(report_id, db)

    except Exception as e:
        # 如果get_or_generate_ai_analysis过程中发生任何无法处理的异常
        db.rollback()
        # 重新获取报告对象以安全地更新其状态
        report_to_update = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
        if report_to_update:
            report_to_update.ai_analysis_status = 'failed'
            # 可以在主错误信息字段附加AI错误，或创建一个新字段
            # report_to_update.error_message = f"AI analysis failed: {str(e)}"
            db.commit()
        print(f"后台AI分析任务(报告ID: {report_id})失败: {e}")
    finally:
        db.close()
