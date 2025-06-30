# app/analysis_engine/facade.py

from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from .data_loader import load_data_for_single_exam
from .main_analyzer import perform_analysis
from .chart_generator import generate_chart_data


class AnalysisEngine:
    """
    学情分析引擎的封装类。

    用于包装分析结果，并提供便捷方法访问分析内容。
    本类不负责计算，核心分析逻辑由外部 perform_analysis 完成。
    支持延迟图表数据生成（懒加载）以优化性能。
    """

    def __init__(self, analysis_results: Dict[str, Any]):
        # 保存完整分析报告数据
        self._analysis_results = analysis_results
        # 图表数据缓存，首次访问时生成
        self._chart_data: Optional[Dict[str, Any]] = None

    def get_full_report(self) -> Dict[str, Any]:
        """
        获取完整分析报告。
        包括群体统计、各班数据、学生个体数据等。
        """
        return self._analysis_results

    def get_chart_data(self) -> Dict[str, Any]:
        """
        获取为前端图表准备的结构化数据。

        本方法采用懒加载机制（首次调用才计算），
        避免重复处理，提升整体性能。
        """
        if self._chart_data is None:
            self._chart_data = generate_chart_data(self._analysis_results)
        return self._chart_data

    def get_group_stats(self) -> Dict[str, Any]:
        """
        获取年级或群体的总体统计数据。
        包括各科目均值、标准差、区分度等。
        """
        return self._analysis_results.get("groupStats", {})

    def get_class_report(self, class_name: str) -> Optional[Dict[str, Any]]:
        """
        根据班级名称获取该班的详细分析结果。
        若找不到对应班级，返回 None。
        """
        for table in self._analysis_results.get("tables", []):
            if table.get("tableName") == class_name:
                return table
        return None

    def get_student_report(self, student_name: str) -> Optional[Dict[str, Any]]:
        """
        根据学生姓名获取该学生的分析结果。
        若找不到该学生，返回 None。
        """
        for table in self._analysis_results.get("tables", []):
            for student in table.get("students", []):
                if student.get("studentName") == student_name:
                    return student
        return None


# ------------------------------------------------------------------------------
# 场景函数（Use Case Function）：面向外部调用的统一接口
# ------------------------------------------------------------------------------

def create_single_exam_report(exam_id: int, db: Session, scope_level: str, scope_ids: List[int]) -> AnalysisEngine:
    """
    创建单场考试的完整分析报告。

    外部使用时调用此函数即可完成：
      - 数据加载（含历史成绩）
      - 核心分析计算
      - 结果封装为 AnalysisEngine

    :param exam_id: 考试 ID
    :param db: 数据库会话（SQLAlchemy）
    :param scope_level: 分析范围（'GRADE' 或 'CLASS'）
    :param scope_ids: 指定年级或班级 ID 列表
    :return: 封装后的 AnalysisEngine 实例，可按需获取报告各部分内容
    """
    # 步骤 1: 加载考试成绩与历史数据
    analysis_input, student_history_map = load_data_for_single_exam(exam_id, db, scope_level, scope_ids)

    # 步骤 2: 执行核心学情分析逻辑
    analysis_results = perform_analysis(analysis_input, student_history_map)

    # 步骤 3: 封装为分析引擎对象返回
    engine = AnalysisEngine(analysis_results)

    return engine
