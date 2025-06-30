# app/services/report_runner.py

from typing import List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import AnalysisReport
from app.analysis_engine.facade import create_single_exam_report


def run_single_exam_analysis_task(report_id: int, scope_level: str, scope_ids: List[int]):
    """
    执行单场考试的后台分析任务。

    步骤包括：
    1. 加载目标报告及其考试信息；
    2. 调用分析引擎生成分析报告；
    3. 将结果保存至数据库；
    4. 捕获异常并记录失败状态。

    :param report_id: 分析报告在数据库中的主键 ID。
    :param scope_level: 分析范围层级（例如 'GRADE' 或 'CLASS'）。
    :param scope_ids: 范围对应的 ID 列表。
    """
    db: Session = SessionLocal()
    try:
        # 查询目标报告对象
        report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).one_or_none()
        if not report or not report.exam:
            # 报告或考试不存在，无法进行分析
            return

        # 调用统一分析入口（使用 facade 封装）
        engine = create_single_exam_report(
            exam_id=report.exam_id,
            db=db,
            scope_level=scope_level,
            scope_ids=scope_ids
        )

        # 更新报告状态与分析结果
        report.status = "completed"
        report.full_report_data = engine.get_full_report()

        # 注意：图表数据将由前端请求时延迟生成，不在此处预生成
        # report.chart_data = engine.get_chart_data()

        # 若为整场考试分析，可标记考试整体状态为已完成
        if scope_level == 'FULL_EXAM':
            report.exam.status = "completed"

        db.commit()

    except Exception as e:
        # 出现异常时回滚事务，并标记报告为失败
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

    包括以下逻辑：
    1. 查询所有源报告；
    2. 聚合学生个人的考试表现；
    3. 计算进步趋势（如总分变化、排名变化）；
    4. 保存对比结果。

    :param comparison_report_id: 要生成的对比报告 ID。
    :param source_report_ids: 用于参与对比的多个单场报告 ID 列表。
    """
    db: Session = SessionLocal()
    try:
        # 加载所有来源报告（必须为单场考试，且有 exam 绑定）
        source_reports = db.query(AnalysisReport).filter(
            AnalysisReport.id.in_(source_report_ids),
            AnalysisReport.report_type == "single",
            AnalysisReport.exam_id.isnot(None)
        ).order_by(AnalysisReport.created_at).all()

        # 验证每份报告都绑定了考试
        if any(r.exam is None for r in source_reports):
            raise ValueError("一个或多个源报告缺少有效的考试关联。")

        exam_names_ordered = [r.exam.name for r in source_reports]

        # 初始化对比报告结构
        comparison_result = {
            "metadata": {
                "compared_exams": exam_names_ordered,
                "source_report_ids": source_report_ids
            },
            "students": {},       # 学生对比数据
            "class_trends": {},   # （保留结构）班级趋势分析
            "grade_trends": {}    # （保留结构）年级趋势分析
        }

        # 聚合各场考试中学生的核心数据（总分/排名）
        for report in source_reports:
            report_data = report.full_report_data
            if not report_data or 'tables' not in report_data:
                continue

            for table in report_data.get("tables", []):
                for student in table.get("students", []):
                    student_name = student["studentName"]
                    student_entry = comparison_result["students"].setdefault(student_name, {
                        "tableName": student["tableName"],
                        "timelines": {
                            "totalScore": [],
                            "classRank": [],
                            "gradeRank": []
                        }
                    })
                    timeline = student_entry["timelines"]
                    timeline["totalScore"].append(student.get("totalScore"))
                    timeline["classRank"].append(student.get("classRank"))
                    timeline["gradeRank"].append(student.get("gradeRank"))

        # 计算学生的进步/退步情况（分数与排名变化）
        for student_data in comparison_result["students"].values():
            scores = student_data["timelines"]["totalScore"]
            ranks = student_data["timelines"]["gradeRank"]
            if len(scores) >= 2:
                student_data["progress"] = {
                    "score_change": scores[-1] - scores[0] if all(isinstance(x, (int, float)) for x in scores) else None,
                    "rank_change": ranks[0] - ranks[-1] if all(isinstance(x, (int, float)) for x in ranks) else None
                }

        # 保存对比报告结果
        comparison_report = db.query(AnalysisReport).filter(AnalysisReport.id == comparison_report_id).one()
        comparison_report.status = "completed"
        comparison_report.full_report_data = comparison_result
        db.commit()

    except Exception as e:
        # 出错时标记报告为失败状态
        db.rollback()
        report = db.query(AnalysisReport).filter(AnalysisReport.id == comparison_report_id).first()
        if report:
            report.status = "failed"
            report.error_message = f"对比分析任务失败: {type(e).__name__}: {str(e)}"
            db.commit()
    finally:
        db.close()
