import math
import statistics
from typing import Dict, List, Any


# ==============================================================================
# --- 核心辅助与统计函数模块 ---
# ==============================================================================

def calculate_gini(arr: List[float]) -> float:
    """
    计算基尼系数，用于衡量分数分布的均衡性。
    值越接近 0 表示分布越平均，越接近 1 表示差异越大。
    """
    if not arr or sum(arr) == 0:
        return 0.0
    sorted_arr = sorted(arr)
    n = len(sorted_arr)
    numerator = sum((2 * (i + 1) - n - 1) * val for i, val in enumerate(sorted_arr))
    denominator = n * sum(sorted_arr)
    return float(numerator / denominator) if denominator != 0 else 0.0


def calculate_skewness_kurtosis(arr: List[float]) -> Dict[str, float]:
    """
    计算偏度（Skewness）和峰度（Kurtosis）指标。
    偏度反映分布的对称性，峰度反映分布的尖峭程度。
    """
    n = len(arr)
    if n < 4:
        return {"skewness": 0.0, "kurtosis": 0.0}
    mean = statistics.mean(arr)
    try:
        std_dev = statistics.pstdev(arr)
    except statistics.StatisticsError:
        return {"skewness": 0.0, "kurtosis": 0.0}
    if std_dev == 0:
        return {"skewness": 0.0, "kurtosis": 0.0}
    m3 = sum((x - mean) ** 3 for x in arr) / n
    m4 = sum((x - mean) ** 4 for x in arr) / n
    skewness = m3 / (std_dev ** 3)
    kurtosis = m4 / (std_dev ** 4) - 3
    return {"skewness": round(skewness, 3), "kurtosis": round(kurtosis, 3)}


def calculate_correlation(arr1: List[float], arr2: List[float]) -> float:
    """
    计算两组分数的皮尔逊相关系数（Pearson Correlation Coefficient）。
    用于度量两个变量之间的线性相关性。
    """
    n = len(arr1)
    if n < 2 or len(arr2) != n:
        return 0.0
    try:
        mean1, mean2 = statistics.mean(arr1), statistics.mean(arr2)
        std1, std2 = statistics.pstdev(arr1), statistics.pstdev(arr2)
    except statistics.StatisticsError:
        return 0.0
    if std1 == 0 or std2 == 0:
        return 0.0
    covariance = sum((x1 - mean1) * (x2 - mean2) for x1, x2 in zip(arr1, arr2)) / n
    correlation = covariance / (std1 * std2)
    return round(correlation, 3)


def calculate_frequency_distribution(scores: List[float], full_mark: float, bin_size: int = 10) -> Dict[str, int]:
    """
    计算分数频率分布，用于生成直方图数据。

    :param scores: 学生原始分数列表
    :param full_mark: 满分值
    :param bin_size: 每个分数段的跨度（默认10分一档）
    :return: 字典结构，键为分数段，值为该段人数
    """
    # 稳定性增强：防止 bin_size 为 0 导致崩溃
    if bin_size <= 0:
        return {}
    if not scores:
        return {}

    bins = {}
    int_full_mark = int(math.ceil(full_mark))

    # 初始化分数段容器
    for i in range(0, int_full_mark, bin_size):
        upper_bound = min(i + bin_size, int_full_mark)
        bins[f"{i}-{upper_bound}"] = 0

    # 获取最后一个分段的 key，用于处理满分边界
    last_key = ""
    if bins:
        last_key = sorted(bins.keys())[-1]

    # 遍历分数分配到对应的 bin 中
    for score in scores:
        if score == full_mark and last_key:
            bins[last_key] += 1
            continue
        bin_index = int(score // bin_size)
        lower_bound = bin_index * bin_size
        upper_bound = min(lower_bound + bin_size, int_full_mark)
        key = f"{lower_bound}-{upper_bound}"
        if key in bins:
            bins[key] += 1

    # 按数值顺序返回排序结果
    return {k: v for k, v in sorted(bins.items(), key=lambda item: int(item[0].split('-')[0]))}


def calculate_descriptive_stats(scores_arr: List[float], full_mark: float) -> Dict[str, Any]:
    """
    计算一组分数的所有描述性统计量，包括均值、方差、箱线图数据、频率分布等。
    （已重构以提升稳定性和计算精度）
    """
    count = len(scores_arr)
    # 基础校验：如果没有任何分数，返回一个空的、结构一致的统计字典
    if count == 0:
        return {
            "count": 0, "mean": 0, "stdDev": 0, "variance": 0, "min": 0, "q1": 0,
            "median": 0, "q3": 0, "max": 0, "range": 0, "excellentRate": 0,
            "goodRate": 0, "passRate": 0, "lowScoreRate": 0, "difficulty": 0,
            "skewness": 0, "kurtosis": 0, "fullMarkCount": 0, "zeroMarkCount": 0,
            "boxPlotData": {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0},
            "frequencyDistribution": {}
        }

    # --- 核心统计量计算 ---
    mean = statistics.mean(scores_arr)
    std_dev = statistics.pstdev(scores_arr) if count > 1 else 0.0
    variance = statistics.pvariance(scores_arr) if count > 1 else 0.0
    min_val, max_val = min(scores_arr), max(scores_arr)
    skew_kurt = calculate_skewness_kurtosis(scores_arr)

    if count > 1:
        quantiles = statistics.quantiles(scores_arr, n=4)
        q1, median, q3 = quantiles[0], quantiles[1], quantiles[2]
    else:
        q1 = median = q3 = scores_arr[0]

    # --- 比率性指标计算（增强稳定性与准确性） ---
    pass_count = 0
    excellent_count = 0
    good_count = 0
    difficulty = 0

    # 稳定性增强：仅在满分有效时，才计算依赖于满分的比率和难度指标
    if full_mark > 0:
        PASS_THRESHOLD = 0.60
        GOOD_THRESHOLD_LOWER = 0.70
        EXCELLENT_THRESHOLD = 0.85

        pass_count = sum(1 for s in scores_arr if s >= full_mark * PASS_THRESHOLD)
        excellent_count = sum(1 for s in scores_arr if s >= full_mark * EXCELLENT_THRESHOLD)
        good_count = sum(
            1 for s in scores_arr if full_mark * GOOD_THRESHOLD_LOWER <= s < full_mark * EXCELLENT_THRESHOLD
        )
        difficulty = round(mean / full_mark, 3)

    # 准确性提升：直接通过人数计算比率，避免浮点数减法误差
    passRate = round(pass_count / count, 3)
    excellentRate = round(excellent_count / count, 3)
    goodRate = round(good_count / count, 3)

    # 使用数值稳定的方法计算不合格率
    low_score_count = count - pass_count
    lowScoreRate = round(low_score_count / count, 3)

    # --- 整合最终结果 ---
    stats = {
        "count": count,
        "mean": round(mean, 2),
        "stdDev": round(std_dev, 2),
        "variance": round(variance, 2),
        "min": float(min_val),
        "q1": round(q1, 2),
        "median": round(median, 2),
        "q3": round(q3, 2),
        "max": float(max_val),
        "range": round(max_val - min_val, 2),
        "excellentRate": excellentRate,
        "goodRate": goodRate,
        "passRate": passRate,
        "lowScoreRate": lowScoreRate,
        "difficulty": difficulty,
        "skewness": skew_kurt['skewness'],
        "kurtosis": skew_kurt['kurtosis'],
        "fullMarkCount": sum(1 for s in scores_arr if s == full_mark),
        "zeroMarkCount": sum(1 for s in scores_arr if s == 0),
        "boxPlotData": {
            "min": float(min_val), "q1": round(q1, 2), "median": round(median, 2),
            "q3": round(q3, 2), "max": float(max_val)
        },
        "frequencyDistribution": calculate_frequency_distribution(scores_arr, full_mark)
    }
    return stats


def calculate_discrimination_index(scores_arr: List[float], full_mark: float) -> float:
    """
    计算区分度指数，用于衡量题目或考试对学生成绩高低的区分能力。
    """
    n = len(scores_arr)
    if n < 10:
        return 0.0
    sorted_scores = sorted(scores_arr)
    top_n = max(1, int(n * 0.27))
    high_scores, low_scores = sorted_scores[n - top_n:], sorted_scores[:top_n]
    if not high_scores or not low_scores:
        return 0.0
    high_avg, low_avg = statistics.mean(high_scores), statistics.mean(low_scores)
    return round((high_avg - low_avg) / full_mark, 3) if full_mark != 0 else 0.0


def calculate_advanced_student_metrics(student_report: Dict, class_scores: Dict[str, List[float]]) -> None:
    """
    计算学生个体的高级指标：学科贡献度、专业化指数。
    结果直接写入 student_report["metrics"]
    """
    student_name = student_report["studentName"]
    metrics = student_report["metrics"]
    contribution = {}
    for subject, scores in class_scores.items():
        student_score = student_report["scores"]["rawScores"].get(subject)
        if student_score is None or len(scores) < 2:
            contribution[subject] = 0
            continue
        class_total = sum(scores)
        class_count = len(scores)
        others_mean = (class_total - student_score) / (class_count - 1)
        contribution[subject] = round(student_score - others_mean, 2)
    metrics["contributionScore"] = contribution

    # 使用 T 分数计算专业化指数（基尼系数）
    t_scores_list = list(student_report["scores"]["tScores"].values())
    if len(t_scores_list) > 1:
        metrics["specializationIndex"] = round(calculate_gini(t_scores_list), 3)
    else:
        metrics["specializationIndex"] = 0.0


def calculate_advanced_group_metrics(group_scores: List[float], group_stats: Dict) -> None:
    """
    计算群体结构性指标：高分层厚度、后进生支撑力、学术核心密度。
    结果原地更新 group_stats
    """
    n = len(group_scores)
    if n < 10:
        group_stats.update({
            "highAchieverPenetration": 0,
            "strugglerSupportIndex": 0,
            "academicCoreDensity": 0
        })
        return

    sorted_scores = sorted(group_scores)
    top_n = max(1, int(n * 0.27))
    bottom_n = max(1, int(n * 0.27))
    mean, std_dev = group_stats.get('mean', 0), group_stats.get('stdDev', 0)

    group_stats["highAchieverPenetration"] = round(statistics.mean(sorted_scores[n - top_n:]), 2)
    group_stats["strugglerSupportIndex"] = round(statistics.mean(sorted_scores[:bottom_n]), 2)

    if std_dev and std_dev > 0:
        core_students = [s for s in sorted_scores if (mean - 0.5 * std_dev) <= s <= (mean + 0.5 * std_dev)]
        group_stats["academicCoreDensity"] = round(len(core_students) / n, 3)
    else:
        group_stats["academicCoreDensity"] = 1.0


def calculate_class_vs_group_metrics(table_stats: Dict, group_stats: Dict) -> None:
    """
    计算班级 vs 年级的对比性指标：内部一致性、四分位竞争力。
    """
    for subject in table_stats:
        if subject == 'totalScore' or subject not in group_stats:
            continue
        ts_subj = table_stats[subject]
        gs_subj = group_stats.get(subject)
        if not gs_subj or gs_subj.get("stdDev") is None or gs_subj["stdDev"] == 0:
            ts_subj["homogeneityIndex"] = 1.0
            continue
        ts_subj["homogeneityIndex"] = round(ts_subj.get("stdDev", 0) / gs_subj["stdDev"], 3)

        group_scores = gs_subj.get("_scores_cache")
        if not group_scores:
            continue
        group_len = len(group_scores)
        if group_len == 0:
            continue

        quartiles_competitiveness = {}
        for q_name in ["q1", "median", "q3"]:
            class_q_score = ts_subj.get(q_name, 0)
            percentile_rank = round(
                sum(1 for s in group_scores if s < class_q_score) / group_len * 100, 2
            )
            quartiles_competitiveness[q_name] = percentile_rank

        ts_subj["quartileCompetitiveness"] = quartiles_competitiveness


def analyze_historical_trends(student_report: Dict, student_history: Dict) -> None:
    """
    分析学生历次考试的成绩变化趋势与波动稳定性。
    包括总分趋势、名次变化、波动度等。
    """
    history_metrics = {"trend": {}, "stability": {}}
    last_exam = student_history.get("lastExam")

    # 趋势分析：与上次考试对比
    if last_exam:
        current_total_score = student_report.get("totalScore")
        last_total_score = last_exam.get("totalScore")
        if current_total_score is not None and last_total_score is not None:
            history_metrics["trend"]["totalScore"] = round(current_total_score - last_total_score, 2)
        for rank_type in ["classRank", "gradeRank"]:
            current_rank, last_rank = student_report.get(rank_type), last_exam.get(rank_type)
            if current_rank is not None and last_rank is not None:
                history_metrics["trend"][rank_type] = last_rank - current_rank

    # 稳定性分析：多次考试的波动性
    all_exams = student_history.get("allExams", [])
    if len(all_exams) >= 2:
        percentile_ranks = [exam['gradePercentileRank'] for exam in all_exams if 'gradePercentileRank' in exam]
        if len(percentile_ranks) >= 2:
            history_metrics["stability"]["gradePercentileRankVolatility"] = round(statistics.pstdev(percentile_ranks),
                                                                                  2)
        total_t_scores = [exam['totalTScore'] for exam in all_exams if 'totalTScore' in exam]
        if len(total_t_scores) >= 2:
            history_metrics["stability"]["totalTScoreVolatility"] = round(statistics.pstdev(total_t_scores), 2)

    student_report["metrics"]["history"] = history_metrics


def analyze_trend_slope(historical_values: List[float]) -> float:
    """
    使用最小二乘法拟合线性趋势，计算分数序列的趋势斜率。
    趋势上升为正，下降为负，平稳为零。
    """
    valid_points = [(i + 1, y) for i, y in enumerate(historical_values) if y is not None]
    n = len(valid_points)
    if n < 2:
        return 0.0

    sum_x = sum(p[0] for p in valid_points)
    sum_y = sum(p[1] for p in valid_points)
    sum_xy = sum(p[0] * p[1] for p in valid_points)
    sum_xx = sum(p[0] * p[0] for p in valid_points)

    denominator = n * sum_xx - sum_x * sum_x
    if denominator == 0:
        return 0.0

    numerator = n * sum_xy - sum_x * sum_y
    slope = numerator / denominator
    return round(slope, 3)