# app/analysis_engine/chart_generator.py

from itertools import combinations
from typing import Dict, Any


def generate_chart_data(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    将详细报告数据二次处理，转换为适合前端图表库使用的格式。

    :param analysis_results: 来自 perform_analysis 的完整分析报告。
    :return: 一个包含多层级、为图表优化的数据字典。
    """
    # 初始化图表数据容器
    chart_data = {
        "grade_level_charts": {},         # 年级整体层级图表
        "class_comparison_charts": {},    # 班级对比层级图表
        "student_level_charts": {}        # 学生个体层级图表
    }

    group_stats = analysis_results.get("groupStats", {})
    tables = analysis_results.get("tables", [])

    # 若缺失必要数据，直接返回空结构
    if not group_stats or not tables:
        return chart_data

    subjects = list(group_stats.get("correlationMatrix", {}).keys())  # 所有学科列表
    class_names = [t['tableName'] for t in tables]  # 所有班级名称

    # -----------------------------
    # 年级整体图表数据生成
    # -----------------------------
    grade_charts = chart_data["grade_level_charts"]
    grade_charts["score_distribution_histogram"] = {}

    # 构建每个学科及总分的频率直方图数据
    for subject in subjects + ['totalScore']:
        if subject in group_stats and "frequencyDistribution" in group_stats[subject]:
            freq_dist = group_stats[subject]["frequencyDistribution"]
            grade_charts["score_distribution_histogram"][subject] = {
                "categories": list(freq_dist.keys()),
                "series_data": list(freq_dist.values()),
                "series_name": f"年级{subject}分数分布"
            }

    # 构建相关性热力图数据
    if "correlationMatrix" in group_stats:
        corr_matrix = group_stats["correlationMatrix"]
        heatmap_data = [
            [j, i, corr_matrix[s1].get(s2, 0)]
            for i, s1 in enumerate(subjects) for j, s2 in enumerate(subjects)
        ]
        grade_charts["subject_correlation_heatmap"] = {
            "x_axis_labels": subjects,
            "y_axis_labels": subjects,
            "data": heatmap_data,
            "title": "学科成绩相关性热力图"
        }

    # 构建难度-区分度散点图数据
    difficulty_discrimination_data = []
    for subject in subjects:
        if (stats := group_stats.get(subject)):
            difficulty_discrimination_data.append([
                stats.get("difficulty", 0),
                stats.get("discriminationIndex", 0),
                subject
            ])
    grade_charts["subject_difficulty_discrimination_scatter"] = {
        "data": difficulty_discrimination_data,
        "x_axis_name": "难度",
        "y_axis_name": "区分度",
        "title": "学科难度-区分度分析"
    }

    # -----------------------------
    # 班级对比图表数据生成
    # -----------------------------
    class_charts = chart_data["class_comparison_charts"]
    metrics_to_compare = [
        "mean", "passRate", "excellentRate",
        "highAchieverPenetration", "academicCoreDensity"
    ]

    # 构建柱状图数据（各指标对比）
    class_charts["metrics_bar_chart"] = {metric: {} for metric in metrics_to_compare}
    for metric in metrics_to_compare:
        for subject in subjects + ['totalScore']:
            series_data = [table['tableStats'][subject].get(metric, 0) for table in tables]
            series_data_with_grade = series_data + [group_stats[subject].get(metric, 0)]
            class_charts["metrics_bar_chart"][metric][subject] = {
                "categories": class_names + ['年级平均'],
                "series_data": series_data_with_grade,
                "series_name": f"{subject} - {metric}"
            }

    # 构建箱线图数据（成绩分布）
    class_charts["score_distribution_boxplot"] = {}
    for subject in subjects + ['totalScore']:
        series_data = [[
            table['tableStats'][subject]['boxPlotData']['min'],
            table['tableStats'][subject]['boxPlotData']['q1'],
            table['tableStats'][subject]['boxPlotData']['median'],
            table['tableStats'][subject]['boxPlotData']['q3'],
            table['tableStats'][subject]['boxPlotData']['max']
        ] for table in tables]

        gp_bp = group_stats[subject]['boxPlotData']
        series_data.append([
            gp_bp['min'], gp_bp['q1'], gp_bp['median'], gp_bp['q3'], gp_bp['max']
        ])
        class_charts["score_distribution_boxplot"][subject] = {
            "categories": class_names + ['年级整体'],
            "data": series_data,
            "title": f"{subject} 成绩分布箱线图"
        }

    # 构建班级学科雷达图数据（学科平均画像）
    class_charts["class_profile_radar"] = {}
    full_marks_map = analysis_results.get('fullMarks', {})
    radar_indicator = [{"name": s, "max": full_marks_map.get(s, 150)} for s in subjects]
    grade_mean_series = {
        "name": "年级平均",
        "value": [group_stats[s].get('mean', 0) for s in subjects]
    }
    for table in tables:
        class_name = table['tableName']
        class_mean_series = {
            "name": class_name,
            "value": [table['tableStats'][s].get('mean', 0) for s in subjects]
        }
        class_charts["class_profile_radar"][class_name] = {
            "indicator": radar_indicator,
            "series": [class_mean_series, grade_mean_series],
            "title": f"{class_name} 学科平均分画像"
        }

    # -----------------------------
    # 学生个体层级图表（散点图）
    # -----------------------------
    student_charts = chart_data["student_level_charts"]
    student_charts["subject_vs_subject_scatter"] = {}

    # 展平所有学生数据
    all_students_flat = [student for table in tables for student in table['students']]

    # 构建学科对学科的散点图数据
    for sub1, sub2 in combinations(subjects, 2):
        scatter_data = [[
            s['scores']['rawScores'].get(sub1, 0),
            s['scores']['rawScores'].get(sub2, 0),
            s['studentName'],
            s['tableName']
        ] for s in all_students_flat]
        key = f"{sub1}_vs_{sub2}"
        student_charts["subject_vs_subject_scatter"][key] = {
            "data": scatter_data,
            "x_axis_name": sub1,
            "y_axis_name": sub2,
            "title": f"{sub1} vs {sub2} 成绩散点图"
        }

    return chart_data
