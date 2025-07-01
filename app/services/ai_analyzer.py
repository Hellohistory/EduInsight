import json
from sqlalchemy.orm import Session
from app import models
from app.services import llm_service
from app.services.ai_prompt import PROMPT_TEMPLATE, COMPARISON_PROMPT_TEMPLATE


def _prepare_single_report_data_for_llm(full_report: dict) -> dict:
    """
    为单场考试报告准备LLM输入数据。

    此函数从完整的报告JSON中提取宏观（年级）和中观（班级）的统计摘要，
    完全移除了学生个体数据，以聚焦于整体和集体的表现。

    Args:
        full_report: 包含完整分析数据的字典。

    Returns:
        一个精简后的字典，仅包含用于LLM分析的摘要数据。
    """
    tables_summary = []
    # 遍历每个班级的数据
    for table in full_report.get('tables', []):
        # 确保班级名和班级统计数据存在
        if 'tableName' in table and 'tableStats' in table:
            # 只将班级名和班级统计数据加入摘要列表
            tables_summary.append({
                "tableName": table['tableName'],
                "tableStats": table['tableStats']
            })

    llm_data = {
        "groupName": full_report.get('groupName'),
        "fullMarks": full_report.get('fullMarks'),
        "groupStats": full_report.get('groupStats'),
        "tables": tables_summary,
    }
    return llm_data


def _prepare_comparison_data_for_llm(full_report: dict) -> dict:
    """
    为多场对比分析报告准备LLM输入数据。

    此函数提取学生在多次考试中的表现变化数据，让LLM能够聚焦于
    分析进步、退步和趋势。

    Args:
        full_report: 包含完整对比分析数据的字典。

    Returns:
        一个精简后的字典，包含用于LLM分析的核心对比数据。
    """
    # 对比报告的数据结构已经很精炼，主要是提取核心部分
    return {
        "compared_exams": full_report.get("metadata", {}).get("compared_exams", []),
        "students_progress": full_report.get("students", {})
    }


def _create_llm_prompt(report_summary: dict, prompt_template: str) -> str:
    """
    根据报告摘要和指定的Prompt模板，创建一个完整的LLM输入Prompt。

    Args:
        report_summary: 经过预处理的报告摘要数据。
        prompt_template: 用于指导LLM分析的特定任务模板。

    Returns:
        一个包含角色定义、任务指令和JSON数据的完整字符串。
    """
    json_data_string = json.dumps(report_summary, ensure_ascii=False, indent=2)

    final_prompt = f"""{prompt_template}

# 输入的核心数据
```json
{json_data_string}
```
"""
    return final_prompt


def get_or_generate_ai_analysis(report_id: int, db: Session) -> tuple[str, str]:
    """
    获取或生成AI分析报告的核心服务函数。

    该函数能智能识别报告类型（单场或对比），并调用相应的分析逻辑。
    如果已有缓存且状态为完成，则直接返回缓存结果，否则调用LLM服务生成新的分析。
    此函数现在是后台任务的核心执行者。

    Args:
        report_id: 目标报告在数据库中的ID。
        db: SQLAlchemy的数据库会话实例。

    Returns:
        一个元组，包含两个元素:
        - analysis (str): AI生成的分析报告文本。
        - source (str): 数据来源，"cache" 或 "generated"。

    Raises:
        ValueError: 如果报告未找到、状态不正确或数据为空。
        NotImplementedError: 如果遇到不支持的报告类型。
        RuntimeError: 如果LLM服务调用失败或发生其他内部错误。
    """
    report = db.query(models.AnalysisReport).filter(
        models.AnalysisReport.id == report_id
    ).first()

    if not report:
        raise ValueError("报告未找到")

    if report.status != 'completed':
        raise ValueError(f"主报告状态为 {report.status}，无法进行AI分析。请等待主报告分析完成后再试。")

    if report.ai_analysis_cache and report.ai_analysis_status == 'completed':
        return report.ai_analysis_cache, "cache"

    if not report.full_report_data:
        raise ValueError("报告数据为空，无法进行AI分析。")

    try:
        if report.report_type == 'single':
            llm_data = _prepare_single_report_data_for_llm(report.full_report_data)
            prompt = _create_llm_prompt(llm_data, PROMPT_TEMPLATE)

        elif report.report_type == 'comparison':
            llm_data = _prepare_comparison_data_for_llm(report.full_report_data)
            prompt = _create_llm_prompt(llm_data, COMPARISON_PROMPT_TEMPLATE)

        else:
            raise NotImplementedError(f"不支持的报告类型: '{report.report_type}'")

        ai_result = llm_service.get_completion(prompt)

        if not ai_result:
            raise RuntimeError("LLM服务调用失败或返回空结果")

        report.ai_analysis_cache = ai_result
        report.ai_analysis_status = 'completed'
        db.commit()
        db.refresh(report)

        return report.ai_analysis_cache, "generated"

    except Exception as e:
        raise RuntimeError(f"生成AI分析时发生内部错误 (报告ID: {report_id}, 类型: {report.report_type}): {str(e)}")
