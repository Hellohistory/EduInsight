import statistics
from typing import Dict, Optional, Any

from . import core


def perform_analysis(data: Dict, student_history_map: Optional[Dict[str, Any]] = None) -> Dict:
    """
    执行完整分析流程，生成结构化的深度分析报告。

    包括：
    - 学科及总分统计分析（年级与班级）
    - 各学生排名与T分/偏科等指标计算
    - 班级层次、群体结构性指标分析
    - 历史趋势分析（如提供历史数据）

    :param data: 标准输入结构，包含 fullMarks、tables 等信息
    :param student_history_map: （可选）学生历史成绩数据，用于趋势分析
    :return: 包含多层级统计和诊断的分析报告 dict
    """
    # 提取有效科目名（排除 totalScore）
    subjects = list(data['fullMarks'].keys())
    if 'totalScore' in subjects:
        subjects.remove('totalScore')

    total_full_marks = sum(data['fullMarks'].get(s, 0) for s in subjects)

    # 扁平化所有学生列表（来自各班）
    all_students_flat = [s for t in data['tables'] for s in t['students']]
    if not all_students_flat:
        return {
            "groupName": data['groupName'], "fullMarks": data['fullMarks'],
            "groupStats": {}, "tables": [],
            "error": "在指定范围内没有有效的学生成绩数据进行分析。"
        }

    # 为每位学生补充所在班级名和总分
    for student in all_students_flat:
        student['tableName'] = next((t['tableName'] for t in data['tables'] if student in t['students']), None)
        student['totalScore'] = sum(student['scores'].get(s, 0) for s in subjects)

    # --- 历史数据预处理（如果存在） ---
    if student_history_map:
        for s_name, history in student_history_map.items():
            # 稳定性增强：确保列表非空再访问索引
            if history.get("allExams") and len(history["allExams"]) > 0:
                last_exam_wrapper = history["allExams"][-1]
                if last_exam_wrapper.get("studentScores"):
                    history["lastExam"] = last_exam_wrapper["studentScores"][0]

    # --- 排名计算（年级 + 班级） ---
    all_students_flat.sort(key=lambda x: x['totalScore'], reverse=True)
    grade_count = len(all_students_flat)
    student_ranks = {s['studentName']: {"totalScore": {}} for s in all_students_flat}

    # 年级排名与百分位计算
    for i, student in enumerate(all_students_flat):
        rank = i + 1
        student_ranks[student['studentName']]['totalScore']['gradeRank'] = rank
        student_ranks[student['studentName']]['totalScore']['gradePercentileRank'] = round(
            (grade_count - rank + 1) / grade_count * 100, 2) if grade_count > 0 else 0

    # 班级内排名与百分位计算
    for table_name in {t['tableName'] for t in data['tables']}:
        class_students = sorted([s for s in all_students_flat if s['tableName'] == table_name],
                                key=lambda x: x['totalScore'], reverse=True)
        class_count = len(class_students)
        for i, student in enumerate(class_students):
            rank = i + 1
            student_ranks[student['studentName']]['totalScore']['classRank'] = rank
            student_ranks[student['studentName']]['totalScore']['classPercentileRank'] = round(
                (class_count - rank + 1) / class_count * 100, 2) if class_count > 0 else 0

    # 学科维度的班级与年级排名
    student_ranks_subjects = {s['studentName']: {} for s in all_students_flat}
    for subject in subjects:
        # 年级学科排名
        all_students_flat.sort(key=lambda x: x['scores'].get(subject, 0), reverse=True)
        for i, student in enumerate(all_students_flat):
            student_ranks_subjects[student['studentName']][subject] = {'gradeRank': i + 1}

        # 班级学科排名
        for table_name in {t['tableName'] for t in data['tables']}:
            class_students_subject = sorted(
                [s for s in all_students_flat if s['tableName'] == table_name],
                key=lambda x: x['scores'].get(subject, 0), reverse=True)
            for i, student in enumerate(class_students_subject):
                student_ranks_subjects[student['studentName']][subject]['classRank'] = i + 1

    # 整合进学生总排名结构中
    for s_name, s_data in student_ranks_subjects.items():
        student_ranks[s_name]['subjects'] = s_data

    # -----------------------------
    # 年级层级统计分析
    # -----------------------------
    group_stats = {}
    for subject in subjects:
        scores = [s['scores'].get(subject, 0) for s in all_students_flat]
        group_stats[subject] = core.calculate_descriptive_stats(scores, data['fullMarks'][subject])
        group_stats[subject]['discriminationIndex'] = core.calculate_discrimination_index(scores,
                                                                                          data['fullMarks'][subject])
        group_stats[subject]['_scores_cache'] = scores  # 用于后续群体结构分析

    total_scores_group = [s['totalScore'] for s in all_students_flat]
    group_stats['totalScore'] = core.calculate_descriptive_stats(total_scores_group, total_full_marks)
    group_stats['totalScore']['discriminationIndex'] = core.calculate_discrimination_index(total_scores_group,
                                                                                           total_full_marks)

    # 群体结构性指标分析
    core.calculate_advanced_group_metrics(total_scores_group, group_stats['totalScore'])
    for subject in subjects:
        core.calculate_advanced_group_metrics(group_stats[subject]['_scores_cache'], group_stats[subject])

    # 学科间相关性矩阵
    correlation_matrix = {
        s1: {
            s2: (1.0 if s1 == s2 else core.calculate_correlation(
                [s['scores'].get(s1, 0) for s in all_students_flat],
                [s['scores'].get(s2, 0) for s in all_students_flat]
            )) for s2 in subjects
        } for s1 in subjects
    }
    group_stats['correlationMatrix'] = correlation_matrix

    # 初始化分析结果结构
    analysis_results = {
        "groupName": data['groupName'],
        "fullMarks": data['fullMarks'],
        "groupStats": group_stats,
        "tables": []
    }

    # -----------------------------
    # 班级与学生级别分析
    # -----------------------------
    for table_data in data['tables']:
        class_students_data = [s for s in all_students_flat if s['tableName'] == table_data['tableName']]
        if not class_students_data:
            continue

        table_stats = {}
        class_scores_by_subject = {}

        # 班级各科统计指标
        for subject in subjects:
            scores = [s['scores'].get(subject, 0) for s in class_students_data]
            class_scores_by_subject[subject] = scores
            table_stats[subject] = core.calculate_descriptive_stats(scores, data['fullMarks'][subject])
            table_stats[subject]['discriminationIndex'] = core.calculate_discrimination_index(scores, data['fullMarks'][
                subject])
            core.calculate_advanced_group_metrics(scores, table_stats[subject])

        # 班级总分统计指标
        total_scores_table = [s['totalScore'] for s in class_students_data]
        table_stats['totalScore'] = core.calculate_descriptive_stats(total_scores_table, total_full_marks)
        table_stats['totalScore']['discriminationIndex'] = core.calculate_discrimination_index(total_scores_table,
                                                                                               total_full_marks)
        core.calculate_advanced_group_metrics(total_scores_table, table_stats['totalScore'])

        # 班级 VS 年级横向指标
        core.calculate_class_vs_group_metrics(table_stats, group_stats)

        # -----------------------
        # 学生画像与个体指标
        # -----------------------
        students_results_list = []
        all_table_t_scores = []

        for student_data in class_students_data:
            student_name = student_data['studentName']
            z_scores, t_scores, score_rates = {}, {}, {}
            subject_t_score_tuples = []

            # 计算每科 T 分、Z 分、得分率
            for subject, raw_score in student_data['scores'].items():
                gs_subj = group_stats.get(subject, {})
                mean = gs_subj.get('mean', 0)
                std_dev = gs_subj.get('stdDev', 0)
                fm_subj = data['fullMarks'].get(subject, 100)

                # 准确性与清晰度优化：分开计算 Z 分和 T 分
                if std_dev != 0:
                    z_score = (raw_score - mean) / std_dev
                    t_score = 50.0 + 10 * z_score
                else:
                    z_score = 0.0
                    t_score = 50.0

                z_scores[subject] = round(z_score, 3)
                t_scores[subject] = round(t_score, 2)
                score_rates[subject] = round(raw_score / fm_subj, 3) if fm_subj != 0 else 0.0
                subject_t_score_tuples.append((subject, t_score))

            # 总分 T 分
            total_score_mean = group_stats['totalScore'].get('mean', 0)
            total_score_std_dev = group_stats['totalScore'].get('stdDev', 0)
            total_t_score = 50.0 + 10 * ((student_data[
                                              'totalScore'] - total_score_mean) / total_score_std_dev) if total_score_std_dev != 0 else 50.0
            t_scores['totalScore'] = round(total_t_score, 2)

            # 画像指标：强弱科、T分波动、画像类型
            student_t_scores = [t for _, t in subject_t_score_tuples]
            all_table_t_scores.extend(student_t_scores)
            sorted_by_t = sorted(subject_t_score_tuples, key=lambda x: x[1], reverse=True)

            student_report = {
                "studentName": student_name,
                "tableName": student_data['tableName'],
                "totalScore": round(student_data['totalScore'], 2),
                "classRank": student_ranks[student_name]['totalScore']['classRank'],
                "gradeRank": student_ranks[student_name]['totalScore']['gradeRank'],
                "ranks": student_ranks.get(student_name, {}),
                "scores": {
                    "rawScores": student_data['scores'],
                    "zScores": z_scores,
                    "tScores": t_scores,
                    "scoreRates": score_rates
                },
                "metrics": {
                    "imbalanceIndex": round(statistics.pstdev(student_t_scores), 2) if len(
                        student_t_scores) > 1 else 0.0,
                    "strengthSubjects": [{"subject": s[0], "tScore": round(s[1], 2)} for s in
                                         sorted_by_t[:1]] if sorted_by_t else [],
                    "weaknessSubjects": [{"subject": s[0], "tScore": round(s[1], 2)} for s in
                                         sorted_by_t[-1:]] if sorted_by_t else [],
                }
            }

            # 补充：距离及格线/优秀线的差值
            PASS_THRESHOLD, EXCELLENT_THRESHOLD = 0.60, 0.85
            pass_score_line = total_full_marks * PASS_THRESHOLD
            excellent_score_line = total_full_marks * EXCELLENT_THRESHOLD
            if student_report['totalScore'] < pass_score_line:
                student_report["metrics"]["pointsToPass"] = round(pass_score_line - student_report['totalScore'], 2)
            if student_report['totalScore'] < excellent_score_line:
                student_report["metrics"]["pointsToExcellent"] = round(
                    excellent_score_line - student_report['totalScore'], 2)

            # 学生画像标签识别
            imbalance_index = student_report["metrics"]["imbalanceIndex"]
            profile = "潜力提升型"
            if total_t_score >= 62 and imbalance_index >= 12:
                profile = "拔尖偏科型"
            elif total_t_score >= 62 and imbalance_index < 12:
                profile = "拔尖均衡型"
            elif 55 <= total_t_score < 62 and imbalance_index < 8:
                profile = "稳健发展型"
            elif 45 <= total_t_score < 55:
                profile = "中坚力量型"
            elif total_t_score < 45 and imbalance_index >= 12:
                profile = "短板制约型"
            elif total_t_score < 45 and imbalance_index < 12:
                profile = "基础薄弱型"
            student_report["profile"] = profile

            # 个体贡献度 + 专业化指数
            core.calculate_advanced_student_metrics(student_report, class_scores_by_subject)

            # 历史趋势分析（如提供）
            if student_history_map and student_name in student_history_map:
                core.analyze_historical_trends(student_report, student_history_map[student_name])
                all_exams = student_history_map[student_name].get("allExams", [])
                if len(all_exams) >= 2:
                    historical_ranks = [exam.get('studentScores', [{}])[0].get('gradePercentileRank') for exam in
                                        all_exams]
                    rank_slope = core.analyze_trend_slope(historical_ranks)
                    student_report["metrics"].setdefault("history", {})["gradePercentileRankSlope"] = rank_slope

            students_results_list.append(student_report)

        # 班级 T 分 Gini 系数
        table_stats["tScoreGiniCoefficient"] = core.calculate_gini(all_table_t_scores)

        analysis_results["tables"].append({
            "tableName": table_data['tableName'],
            "tableStats": table_stats,
            "students": sorted(students_results_list, key=lambda x: x.get('classRank', 999))
        })

    # 清理临时缓存字段
    for subject in list(group_stats.keys()):
        if '_scores_cache' in group_stats[subject]:
            del group_stats[subject]['_scores_cache']

    return analysis_results
