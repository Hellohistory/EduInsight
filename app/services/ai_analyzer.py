# app/services/ai_analyzer.py
import json

from sqlalchemy.orm import Session

from app import models
from app.services import llm_service

PROMPT_SUMMARY = """
# 角色: 顶尖教育数据科学家
# 任务: 基于年级整体统计数据，生成一份高度浓缩的核心洞察摘要。
# 核心指令:
1.  **试卷质量评估**: 首先对 `difficulty` 和 `discriminationIndex` 做出明确判断，这决定了后续分析的价值。
2.  **学情结构诊断**: 使用 `highAchieverPenetration`, `academicCoreDensity`, `strugglerSupportIndex` 判断学生群体是“橄榄型”、“哑铃型”还是其他分布，并解释其教学意义。
3.  **学科关联洞察**: 从 `correlationMatrix` 中找出最值得关注的一两个关联（或不关联）现象，并提出可能的解释。
4.  **语言风格**: 必须精炼、专业，直接切入要点，总字数控制在300字以内。
# 输入数据: (仅包含 groupStats 和 fullMarks)
```json
{json_data_string}
```"""

PROMPT_COMPARISON = """

角色: 资深教学策略顾问
任务: 基于所有班级的统计数据，进行横向对比，识别出各班的特色和关键差异。
核心指令:
找出领跑者和落后者: 对比各班在总分和核心学科上的平均分、优秀率、及格率，直接点名。

分析班级画像: 结合 quartileCompetitiveness (四分位竞争力) 和 homogeneityIndex (内部均衡度)，为每个班级打上“画像标签”，例如：

“(1)班：高分领跑型” (高分位竞争力强，但可能内部均衡度不高)

“(2)班：基础扎实型” (中低分位竞争力强，及格率有保障)

“(3)班：整体均衡型” (各项指标接近年级平均，内部均衡度好)

聚焦差异: 重点分析班级之间差异最大的指标，并推测可能的原因（如教学风格、班级管理等）。

输入数据: (包含 groupStats 和所有班级的 tableStats)
JSON

{json_data_string}
"""

PROMPT_SINGLE_CLASS = """

角色: 经验丰富的班主任和诊断专家
任务: 为指定的这一个班级，提供一份详细、可落地的深度诊断报告。
核心指令:
自我定位: 首先，将本班的各项核心指标（平均分、优秀率、标准差等）与年级平均水平进行全面对比，明确本班在年级中的位置。

内部问题诊断:

分析本班的 highAchieverPenetration 和 strugglerSupportIndex，判断班级的优势是在于“拔尖”还是“兜底”。

解读 stdDev 和 homogeneityIndex，评估班内学业分化的严重程度。

提出针对性建议:

如果分化严重，提出分层教学或“一生一策”辅导的具体建议。

如果高分层薄弱，提出如何“拔尖”的策略。

如果后进生问题突出，提出如何“补差”的方案。

建议必须具体、可行，直接面向班主任的日常工作。

输入数据: (仅包含指定班级的 tableStats 和年级的 groupStats 作为对比基准)
JSON

{json_data_string}
"""


def _create_llm_prompt(report_summary: dict, prompt_template: str) -> str:
    """辅助函数：创建最终的Prompt字符串"""
    json_data_string = json.dumps(report_summary, ensure_ascii=False, indent=2)
    return prompt_template.replace("{json_data_string}", json_data_string)


def get_or_generate_ai_analysis(report_id: int, db: Session) -> tuple[str, str]:
    """
    分步调用LLM，为报告的不同部分生成分析，最后组装成一个JSON对象。
    """
    report = db.query(models.AnalysisReport).filter(models.AnalysisReport.id == report_id).first()
    if not report: raise ValueError("报告未找到")
    if report.status != 'completed': raise ValueError(f"主报告状态为 {report.status}，无法分析。")
    if report.ai_analysis_cache and report.ai_analysis_status == 'completed':
        return report.ai_analysis_cache, "cache"
    if not report.full_report_data: raise ValueError("报告数据为空，无法分析。")

    full_report = report.full_report_data
    report_type = report.report_type

    # 目前仅为 'single' 类型报告实现新的结构化AI分析
    if report_type != 'single':
        raise NotImplementedError(f"结构化AI分析暂不支持 '{report_type}' 类型的报告。")

    try:
        # --- 核心改造：分步生成，最后组装 ---
        ai_result_json = {
            "summary": "",
            "comparison": "",
            "diagnostics": {}
        }

        # 1. 生成年级摘要
        summary_data = {"groupStats": full_report.get('groupStats'), "fullMarks": full_report.get('fullMarks')}
        summary_prompt = _create_llm_prompt(summary_data, PROMPT_SUMMARY)
        ai_result_json["summary"] = llm_service.get_completion(summary_prompt)

        # 2. 生成班级横向对比
        comparison_data = {
            "groupStats": full_report.get('groupStats'),
            "tables": [{
                "tableName": t.get('tableName'),
                "tableStats": t.get('tableStats')
            } for t in full_report.get('tables', [])]
        }
        comparison_prompt = _create_llm_prompt(comparison_data, PROMPT_COMPARISON)
        ai_result_json["comparison"] = llm_service.get_completion(comparison_prompt)

        # 3. 循环为每个班级生成深度诊断
        for table in full_report.get('tables', []):
            class_name = table.get('tableName')
            if not class_name: continue

            single_class_data = {
                "className": class_name,
                "classStats": table.get('tableStats'),
                "gradeStats": full_report.get('groupStats')  # 传入年级数据作为对比
            }
            single_class_prompt = _create_llm_prompt(single_class_data, PROMPT_SINGLE_CLASS)
            ai_result_json["diagnostics"][class_name] = llm_service.get_completion(single_class_prompt)

        # 将最终的JSON对象转为字符串存入数据库
        final_result_str = json.dumps(ai_result_json, ensure_ascii=False)
        report.ai_analysis_cache = final_result_str
        report.ai_analysis_status = 'completed'
        db.commit()
        db.refresh(report)

        return report.ai_analysis_cache, "generated"

    except Exception as e:
        # 更新：在最外层捕获异常，确保任何一步失败都能正确标记
        report.ai_analysis_status = 'failed'
        db.commit()
        raise RuntimeError(f"生成结构化AI分析时发生内部错误 (报告ID: {report_id}): {str(e)}")
