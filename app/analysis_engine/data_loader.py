# app/analysis_engine/data_loader.py

from typing import Dict, List, Any, Tuple, Optional
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload, subqueryload
from app import models


def _format_historical_data(scores: List[models.Score]) -> Dict[str, Any]:
    """
    辅助函数：将历史成绩 Score 对象列表格式化为嵌套字典结构，
    便于后续分析模块按考试时间顺序使用历史数据。
    """
    history_map = {}
    if not scores:
        return {}

    for score in scores:
        # 跳过缺失关键关联对象的成绩记录
        if not (score.student and score.student.class_ and score.exam and score.subject):
            continue

        exam_name = score.exam.name
        exam_date = score.exam.exam_date.isoformat() if score.exam.exam_date else ''
        student_name = score.student.name
        subject_name = score.subject.name
        class_name = score.student.class_.name

        # 构建每位学生、每场考试的嵌套结构
        student_entry = history_map.setdefault(student_name, {})
        exam_entry = student_entry.setdefault(exam_name, {
            "examName": exam_name,
            "examDate": exam_date,
            "scores": {},
            "className": class_name
        })
        exam_entry["scores"][subject_name] = score.score

    # 将学生的所有考试按时间排序后打包成最终结构
    final_historical_data = {}
    for student_name, exams in history_map.items():
        all_exams_list = []
        for exam_name, exam_data in exams.items():
            student_scores_entry = {
                "studentName": student_name,
                "tableName": exam_data["className"],
                "totalScore": sum(exam_data["scores"].values()),
                "scores": exam_data["scores"]
            }
            exam_wrapper = {
                "examName": exam_name,
                "examDate": exam_data['examDate'],
                "studentScores": [student_scores_entry]
            }
            all_exams_list.append(exam_wrapper)

        if all_exams_list:
            final_historical_data[student_name] = {
                "allExams": sorted(all_exams_list, key=lambda x: x['examDate'])
            }

    return final_historical_data


def load_data_for_single_exam(exam_id: int, db: Session, scope_level: str, scope_ids: List[int]) -> Tuple[
    Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    为单场考试加载分析所需的所有数据。

    此函数查询当前考试的所有学生成绩、基本信息、所属班级与学科；
    并额外查找这些学生的所有历史考试记录（在当前考试时间点之前）。
    返回结构可直接传入分析引擎使用。

    :param exam_id: 要分析的考试ID。
    :param db: SQLAlchemy的数据库会话对象。
    :param scope_level: 分析范围层级，支持 'GRADE' 或 'CLASS'。
    :param scope_ids: 指定年级或班级的 ID 列表。
    :return: (analysis_input, student_history_map)
        - analysis_input：当前考试结构化数据
        - student_history_map：每位学生的历史考试成绩（可为空）
    """
    # 查询目标考试及其科目信息（使用 subqueryload 加速）
    exam = db.query(models.Exam).options(
        subqueryload(models.Exam.exam_subjects).joinedload(models.ExamSubject.subject)
    ).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise ValueError(f"ID为 {exam_id} 的考试未找到。")

    # 构建满分信息字典 {科目名: 满分}
    full_marks = {es.subject.name: es.full_mark for es in exam.exam_subjects}
    if not full_marks:
        raise ValueError(f"考试 '{exam.name}' 未定义任何科目或满分。")

    # 构建本场考试下指定范围内的成绩查询
    scores_query = db.query(models.Score).options(
        joinedload(models.Score.student).joinedload(models.Student.class_),
        joinedload(models.Score.subject),
        joinedload(models.Score.exam)
    ).filter(models.Score.exam_id == exam_id)

    if scope_level == 'GRADE':
        # 筛选指定年级内的学生
        scores_query = scores_query.join(models.Score.student).join(models.Student.class_).filter(
            models.Class.grade_id.in_(scope_ids))
    elif scope_level == 'CLASS':
        # 筛选指定班级内的学生
        scores_query = scores_query.join(models.Score.student).filter(
            models.Student.class_id.in_(scope_ids))

    all_scoped_scores = scores_query.all()

    # 若无有效成绩数据，则返回空结构
    if not all_scoped_scores:
        return {"groupName": exam.name, "fullMarks": full_marks, "tables": []}, None

    # 学生 ID 集合，用于后续历史成绩查询
    student_ids_in_scope = {score.student_id for score in all_scoped_scores if score.student_id}

    # 构建嵌套表结构（按班级、学生、科目分组）
    tables_dict: Dict[str, Dict[str, Any]] = {}
    for score in all_scoped_scores:
        if not (score.student and score.student.class_ and score.subject):
            continue
        class_name, student_name = score.student.class_.name, score.student.name
        subject_name = score.subject.name

        # 初始化班级结构
        if class_name not in tables_dict:
            tables_dict[class_name] = {'tableName': class_name, 'students': {}}

        # 初始化学生结构
        student_scores = tables_dict[class_name]['students'].setdefault(student_name, {
            'studentName': student_name,
            'scores': {s: 0.0 for s in full_marks.keys()}
        })

        # 写入实际成绩
        if score.score is not None:
            student_scores['scores'][subject_name] = score.score

    # 构建分析引擎所需的数据结构（当前考试）
    analysis_input = {
        "groupName": exam.name,
        "fullMarks": full_marks,
        "tables": [{
            'tableName': name,
            'students': list(data['students'].values())
        } for name, data in tables_dict.items()]
    }

    # 查询该考试前的所有历史成绩（只取参与本次考试的学生）
    historical_scores_query = db.query(models.Score).join(
        models.Exam, models.Score.exam_id == models.Exam.id
    ).options(
        joinedload(models.Score.student).joinedload(models.Student.class_),
        joinedload(models.Score.exam),
        joinedload(models.Score.subject)
    ).filter(
        and_(
            models.Score.student_id.in_(student_ids_in_scope),
            models.Score.exam_id != exam_id,
            models.Exam.exam_date < exam.exam_date
        )
    )

    historical_scores = historical_scores_query.all()

    # 格式化为历史考试结构（以学生为单位）
    student_history_map = _format_historical_data(historical_scores)

    return analysis_input, student_history_map
