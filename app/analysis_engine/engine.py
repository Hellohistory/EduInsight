# app/analysis_engine/engine.py

import statistics
from itertools import combinations
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session, joinedload
from app import models
from . import core


def _perform_analysis(data: Dict, historical_data: Optional[List[Dict]] = None) -> Dict:
    """
    执行完整分析流程，生成结构化的深度分析报告。
    """
    subjects = list(data['fullMarks'].keys())
    if 'totalScore' in subjects:
        subjects.remove('totalScore')

    total_full_marks = sum(data['fullMarks'].get(s, 0) for s in subjects)
    all_students_flat = [s for t in data['tables'] for s in t['students']]

    if not all_students_flat:
        return {
            "groupName": data['groupName'], "fullMarks": data['fullMarks'],
            "groupStats": {}, "tables": [], "error": "在指定范围内没有有效的学生成绩数据进行分析。"
        }

    for table in data['tables']:
        for student in table['students']:
            student['tableName'] = table['tableName']
            student['totalScore'] = sum(student['scores'].get(s, 0) for s in subjects)

    all_students_flat.sort(key=lambda x: x['totalScore'], reverse=True)
    grade_count = len(all_students_flat)
    student_ranks = {s['studentName']: {"totalScore": {}} for s in all_students_flat}
    for i, student in enumerate(all_students_flat):
        rank = i + 1
        student_ranks[student['studentName']]['totalScore']['gradeRank'] = rank
        student_ranks[student['studentName']]['totalScore']['gradePercentileRank'] = round(
            (grade_count - rank + 1) / grade_count * 100, 2) if grade_count > 0 else 0

    for table_name in {t['tableName'] for t in data['tables']}:
        class_students = sorted([s for s in all_students_flat if s['tableName'] == table_name],
                                key=lambda x: x['totalScore'], reverse=True)
        class_count = len(class_students)
        for i, student in enumerate(class_students):
            rank = i + 1
            student_ranks[student['studentName']]['totalScore']['classRank'] = rank
            student_ranks[student['studentName']]['totalScore']['classPercentileRank'] = round(
                (class_count - rank + 1) / class_count * 100, 2) if class_count > 0 else 0

    student_ranks_subjects = {s['studentName']: {} for s in all_students_flat}
    for subject in subjects:
        all_students_flat.sort(key=lambda x: x['scores'].get(subject, 0), reverse=True)
        for i, student in enumerate(all_students_flat):
            if subject not in student_ranks_subjects[student['studentName']]:
                student_ranks_subjects[student['studentName']][subject] = {}
            student_ranks_subjects[student['studentName']][subject]['gradeRank'] = i + 1
        for table_name in {t['tableName'] for t in data['tables']}:
            class_students_subject = sorted([s for s in all_students_flat if s['tableName'] == table_name],
                                            key=lambda x: x['scores'].get(subject, 0), reverse=True)
            for i, student in enumerate(class_students_subject):
                student_ranks_subjects[student['studentName']][subject]['classRank'] = i + 1
    for s_name, s_data in student_ranks_subjects.items():
        student_ranks[s_name]['subjects'] = s_data

    group_stats = {}
    for subject in subjects:
        scores = [s['scores'].get(subject, 0) for s in all_students_flat]
        group_stats[subject] = core.calculate_descriptive_stats(scores, data['fullMarks'][subject])
        group_stats[subject]['discriminationIndex'] = core.calculate_discrimination_index(scores, data['fullMarks'][
            subject])
        group_stats[subject]['_scores_cache'] = scores
    total_scores_group = [s['totalScore'] for s in all_students_flat]
    group_stats['totalScore'] = core.calculate_descriptive_stats(total_scores_group, total_full_marks)
    group_stats['totalScore']['discriminationIndex'] = core.calculate_discrimination_index(total_scores_group,
                                                                                           total_full_marks)

    core.calculate_advanced_group_metrics(total_scores_group, group_stats['totalScore'])
    for subject in subjects:
        core.calculate_advanced_group_metrics(group_stats[subject]['_scores_cache'], group_stats[subject])

    correlation_matrix = {s1: {s2: (1.0 if s1 == s2 else core.calculate_correlation(
        [s['scores'].get(s1, 0) for s in all_students_flat],
        [s['scores'].get(s2, 0) for s in all_students_flat])) for s2 in subjects} for s1 in subjects}
    group_stats['correlationMatrix'] = correlation_matrix

    student_history_map = {}
    if historical_data:
        for exam in sorted(historical_data, key=lambda x: x.get('examDate', '')):
            for student_scores in exam.get('studentScores', []):
                s_name = student_scores['studentName']
                if s_name not in student_history_map: student_history_map[s_name] = {"allExams": []}
                student_history_map[s_name]["allExams"].append(student_scores)
        for s_name in student_history_map:
            if student_history_map[s_name]["allExams"]:
                student_history_map[s_name]["lastExam"] = student_history_map[s_name]["allExams"][-1]

    analysis_results = {"groupName": data['groupName'], "fullMarks": data['fullMarks'], "groupStats": group_stats,
                        "tables": []}

    for table_data in data['tables']:
        class_students_data = [s for s in all_students_flat if s['tableName'] == table_data['tableName']]
        table_stats = {}
        class_scores_by_subject = {}
        for subject in subjects:
            scores = [s['scores'].get(subject, 0) for s in class_students_data]
            class_scores_by_subject[subject] = scores
            table_stats[subject] = core.calculate_descriptive_stats(scores, data['fullMarks'][subject])
            table_stats[subject]['discriminationIndex'] = core.calculate_discrimination_index(scores,
                                                                                              data['fullMarks'][
                                                                                                  subject])
            core.calculate_advanced_group_metrics(scores, table_stats[subject])

        total_scores_table = [s['totalScore'] for s in class_students_data]
        table_stats['totalScore'] = core.calculate_descriptive_stats(total_scores_table, total_full_marks)
        table_stats['totalScore']['discriminationIndex'] = core.calculate_discrimination_index(total_scores_table,
                                                                                               total_full_marks)
        core.calculate_advanced_group_metrics(total_scores_table, table_stats['totalScore'])

        core.calculate_class_vs_group_metrics(table_stats, group_stats)

        students_results_list = []
        all_table_t_scores = []
        for student_data in class_students_data:
            student_name = student_data['studentName']
            z_scores, t_scores, score_rates = {}, {}, {}
            subject_t_score_tuples = []
            for subject, raw_score in student_data['scores'].items():
                gs_subj, fm_subj = group_stats.get(subject, {}), data['fullMarks'].get(subject, 0)
                mean, std_dev = gs_subj.get('mean', 0), gs_subj.get('stdDev', 0)
                t_score = 50.0 + 10 * ((raw_score - mean) / std_dev) if std_dev != 0 else 50.0
                z_scores[subject] = round((t_score - 50) / 10, 3) if std_dev != 0 else 0.0
                t_scores[subject] = round(t_score, 2)
                subject_t_score_tuples.append((subject, t_score))
                score_rates[subject] = round(raw_score / fm_subj, 3) if fm_subj != 0 else 0

            total_score_mean = group_stats['totalScore'].get('mean', 0)
            total_score_std_dev = group_stats['totalScore'].get('stdDev', 0)

            if total_score_std_dev != 0:
                # T-Score 标准计算公式
                total_t_score = 50.0 + 10 * ((student_data['totalScore'] - total_score_mean) / total_score_std_dev)
                t_scores['totalScore'] = round(total_t_score, 2)
            else:
                # 如果标准差为0，说明所有学生总分都一样，T-Score就是中位数50
                t_scores['totalScore'] = 50.0

            student_t_scores = [t for _, t in subject_t_score_tuples]
            all_table_t_scores.extend(student_t_scores)
            sorted_by_t = sorted(subject_t_score_tuples, key=lambda x: x[1], reverse=True)

            student_report = {
                "studentName": student_name, "tableName": student_data['tableName'],
                "totalScore": round(student_data['totalScore'], 2),
                "classRank": student_ranks[student_name]['totalScore']['classRank'],
                "gradeRank": student_ranks[student_name]['totalScore']['gradeRank'],
                "ranks": student_ranks.get(student_name, {}),
                "scores": {"rawScores": student_data['scores'], "zScores": z_scores, "tScores": t_scores,
                           "scoreRates": score_rates},
                "metrics": {
                    "imbalanceIndex": round(statistics.pstdev(student_t_scores), 2) if len(
                        student_t_scores) > 1 else 0.0,
                    "strengthSubjects": [{"subject": s[0], "tScore": round(s[1], 2)} for s in
                                         sorted_by_t[:1]] if sorted_by_t else [],
                    "weaknessSubjects": [{"subject": s[0], "tScore": round(s[1], 2)} for s in
                                         sorted_by_t[-1:]] if sorted_by_t else [],
                }
            }

            core.calculate_advanced_student_metrics(student_report, class_scores_by_subject)
            if student_name in student_history_map:
                core.analyze_historical_trends(student_report, student_history_map[student_name])
            students_results_list.append(student_report)

        table_stats["tScoreGiniCoefficient"] = core.calculate_gini(all_table_t_scores)
        analysis_results["tables"].append({
            "tableName": table_data['tableName'], "tableStats": table_stats,
            "students": sorted(students_results_list, key=lambda x: x.get('classRank', 999))
        })

    for subject in list(group_stats.keys()):
        if '_scores_cache' in group_stats[subject]:
            del group_stats[subject]['_scores_cache']

    return analysis_results


def _load_data_from_db(exam_id: int, db: Session, scope_level: str, scope_ids: List[int]) -> Dict[str, Any]:

    exam = db.query(models.Exam).options(
        joinedload(models.Exam.exam_subjects).joinedload(models.ExamSubject.subject)
    ).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise ValueError(f"ID为 {exam_id} 的考试未找到。")

    full_marks = {es.subject.name: es.full_mark for es in exam.exam_subjects}
    if not full_marks:
        raise ValueError(f"考试 '{exam.name}' 未定义任何科目或满分。")

    scores_query = db.query(models.Score).options(
        joinedload(models.Score.student).joinedload(models.Student.class_),
        joinedload(models.Score.subject)
    ).filter(models.Score.exam_id == exam_id)

    if scope_level == 'GRADE':
        if not scope_ids:
            raise ValueError("按年级分析时，必须提供年级ID。")
        # 通过 Student -> Class -> Grade 的关系进行过滤
        scores_query = scores_query.join(models.Score.student).join(models.Student.class_).filter(
            models.Class.grade_id.in_(scope_ids)
        )
    elif scope_level == 'CLASS':
        if not scope_ids:
            raise ValueError("按班级分析时，必须提供班级ID。")

        scores_query = scores_query.join(models.Score.student).filter(
            models.Student.class_id.in_(scope_ids)
        )

    all_scoped_scores = scores_query.all()

    if not all_scoped_scores:

        return {
            "groupName": exam.name,
            "fullMarks": full_marks,
            "tables": []
        }


    tables_dict: Dict[str, Dict[str, Any]] = {}
    for score in all_scoped_scores:
        if not score.student or not score.student.class_ or not score.subject:
            continue

        class_name = score.student.class_.name
        student_name = score.student.name
        subject_name = score.subject.name

        if class_name not in tables_dict:
            tables_dict[class_name] = {'tableName': class_name, 'students': {}}

        if student_name not in tables_dict[class_name]['students']:
            tables_dict[class_name]['students'][student_name] = {
                'studentName': student_name,
                'scores': {subject: 0.0 for subject in full_marks.keys()}
            }
        if score.score is not None:
            tables_dict[class_name]['students'][student_name]['scores'][subject_name] = score.score

    tables = [
        {'tableName': name, 'students': list(s_data['students'].values())}
        for name, s_data in tables_dict.items()
    ]

    return {
        "groupName": exam.name,
        "fullMarks": full_marks,
        "tables": tables
    }


class AnalysisEngine:

    def __init__(self, exam_id: int, db: Session, scope_level: str, scope_ids: List[int],
                 historical_data: Optional[List[Dict]] = None):
        """
        初始化分析引擎。

        :param exam_id: 要分析的考试的ID。
        :param db: SQLAlchemy的数据库会话。
        :param scope_level: 分析层级 ('FULL_EXAM', 'GRADE', 'CLASS').
        :param scope_ids: 对应层级的ID列表。
        :param historical_data: (可选) 历史考试数据列表。
        """
        analysis_input = _load_data_from_db(exam_id, db, scope_level, scope_ids)
        self._analysis_results: Dict = _perform_analysis(analysis_input, historical_data)
        self._chart_data: Dict = self._generate_chart_data()

    def get_full_report(self) -> Dict:
        """获取完整的、详细的分析报告。"""
        return self._analysis_results

    def get_chart_data(self) -> Dict:
        """获取为前端图表优化的数据结构。"""
        return self._chart_data

    def get_group_stats(self) -> Dict:
        """获取年级级别的整体统计数据。"""
        return self._analysis_results.get("groupStats", {})

    def get_class_report(self, class_name: str) -> Optional[Dict]:
        """
        根据班级名称获取指定班级的详细报告。
        """
        for table in self._analysis_results.get("tables", []):
            if table.get("tableName") == class_name:
                return table
        return None

    def get_student_report(self, student_name: str) -> Optional[Dict]:
        """
        根据学生姓名获取指定学生的详细报告。
        """
        for table in self._analysis_results.get("tables", []):
            for student in table.get("students", []):
                if student.get("studentName") == student_name:
                    return student
        return None

    def _generate_chart_data(self) -> Dict:
        """
        将详细报告数据二次处理，转换为适合前端图表库使用的格式。
        """
        analysis_results = self._analysis_results
        chart_data = {"grade_level_charts": {}, "class_comparison_charts": {}, "student_level_charts": {}}
        group_stats = analysis_results.get("groupStats", {})
        tables = analysis_results.get("tables", [])
        if not group_stats or not tables:
            return chart_data

        subjects = list(group_stats.get("correlationMatrix", {}).keys())
        class_names = [t['tableName'] for t in tables]

        # --- 年级整体图表数据 ---
        grade_charts = chart_data["grade_level_charts"]
        grade_charts["score_distribution_histogram"] = {}
        for subject in subjects + ['totalScore']:
            if subject in group_stats and "frequencyDistribution" in group_stats[subject]:
                freq_dist = group_stats[subject]["frequencyDistribution"]
                grade_charts["score_distribution_histogram"][subject] = {
                    "categories": list(freq_dist.keys()), "series_data": list(freq_dist.values()),
                    "series_name": f"年级{subject}分数分布"
                }
        if "correlationMatrix" in group_stats:
            corr_matrix = group_stats["correlationMatrix"]
            heatmap_data = [[j, i, corr_matrix[s1].get(s2, 0)] for i, s1 in enumerate(subjects) for j, s2 in
                            enumerate(subjects)]
            grade_charts["subject_correlation_heatmap"] = {
                "x_axis_labels": subjects, "y_axis_labels": subjects, "data": heatmap_data, "title": "学科成绩相关性热力图"
            }
        difficulty_discrimination_data = [[stats.get("difficulty", 0), stats.get("discriminationIndex", 0), subject] for
                                          subject in subjects if (stats := group_stats.get(subject))]
        grade_charts["subject_difficulty_discrimination_scatter"] = {
            "data": difficulty_discrimination_data, "x_axis_name": "难度", "y_axis_name": "区分度",
            "title": "学科难度-区分度分析"
        }

        # --- 班级对比图表数据 ---
        class_charts = chart_data["class_comparison_charts"]
        metrics_to_compare = ["mean", "passRate", "excellentRate", "highAchieverPenetration", "academicCoreDensity"]
        class_charts["metrics_bar_chart"] = {metric: {} for metric in metrics_to_compare}
        for metric in metrics_to_compare:
            for subject in subjects + ['totalScore']:
                series_data = [table['tableStats'][subject].get(metric, 0) for table in tables]
                series_data_with_grade = series_data + [group_stats[subject].get(metric, 0)]
                class_charts["metrics_bar_chart"][metric][subject] = {
                    "categories": class_names + ['年级平均'], "series_data": series_data_with_grade,
                    "series_name": f"{subject} - {metric}"
                }
        class_charts["score_distribution_boxplot"] = {}
        for subject in subjects + ['totalScore']:
            series_data = []
            for table in tables:
                bp = table['tableStats'][subject]['boxPlotData']
                series_data.append([bp['min'], bp['q1'], bp['median'], bp['q3'], bp['max']])
            gp_bp = group_stats[subject]['boxPlotData']
            series_data.append([gp_bp['min'], gp_bp['q1'], gp_bp['median'], gp_bp['q3'], gp_bp['max']])
            class_charts["score_distribution_boxplot"][subject] = {
                "categories": class_names + ['年级整体'], "data": series_data, "title": f"{subject} 成绩分布箱线图"
            }
        class_charts["class_profile_radar"] = {}
        full_marks_map = analysis_results.get('fullMarks', {})
        radar_indicator = [{"name": s, "max": full_marks_map.get(s, 150)} for s in subjects]
        grade_mean_series = {"name": "年级平均", "value": [group_stats[s].get('mean', 0) for s in subjects]}
        for table in tables:
            class_name = table['tableName']
            class_mean_series = {"name": class_name, "value": [table['tableStats'][s].get('mean', 0) for s in subjects]}
            class_charts["class_profile_radar"][class_name] = {
                "indicator": radar_indicator, "series": [class_mean_series, grade_mean_series],
                "title": f"{class_name} 学科平均分画像"
            }

        # --- 学生个体/散点图数据 ---
        student_charts = chart_data["student_level_charts"]
        student_charts["subject_vs_subject_scatter"] = {}
        all_students_flat = [student for table in tables for student in table['students']]
        for sub1, sub2 in combinations(subjects, 2):
            scatter_data = [
                [s['scores']['rawScores'].get(sub1, 0), s['scores']['rawScores'].get(sub2, 0), s['studentName'],
                 s['tableName']] for s in all_students_flat]
            key = f"{sub1}_vs_{sub2}"
            student_charts["subject_vs_subject_scatter"][key] = {
                "data": scatter_data, "x_axis_name": sub1, "y_axis_name": sub2, "title": f"{sub1} vs {sub2} 成绩散点图"
            }

        return chart_data
