import json
from sqlalchemy.orm import Session
from app import models
from app.services import llm_service

PROMPT_TEMPLATE = """
# 角色
你是一位顶尖的教育数据科学家和资深教学策略顾问。

# 任务
请基于提供的考试分析统计摘要（仅包含年级和班级两个层面），进行深度解读，并提供一套数据驱动、可落地的教学改进方案。

# 输入数据解读指南
这份JSON报告不包含学生个体数据，但包含了极具价值的统计指标。请在分析时重点关注：

1.  **年级/群体层面 (`groupStats`)**:
    * **试卷质量评估**: 首先关注 `difficulty` (难度) 和 `discriminationIndex` (区分度)。这是后续分析有效性的基础。难度过高或过低，或区分度不足，都需要在报告中指出。
    * **整体学情结构**: 通过 `highAchieverPenetration` (高分层厚度), `academicCoreDensity` (中坚力量密度), 和 `strugglerSupportIndex` (后进生支撑力) 来判断学生群体是“橄榄型”、“哑铃型”还是其他分布。这直接关系到后续教学策略的重心。
    * **学科间关联**: 分析 `correlationMatrix`，寻找非预期的强/弱相关性。例如，如果物理和数学的相关性低于0.6，可能暗示了学生在知识迁移或逻辑能力上存在普遍性问题。

2.  **班级对比层面 (`tables[*].tableStats`)**:
    * **横向定位**: 不要只比较平均分 (`mean`)。更要比较 `excellentRate` (优秀率) 和 `passRate` (及格率) 来了解班级在高分段和基础段的表现。
    * **班级竞争力**: 重点解读 `quartileCompetitiveness`。它揭示了班级的高、中、低分段学生在年级中的具体位置，比单一的平均分排名信息量更大。
    * **内部教学有效性**: 分析 `homogeneityIndex` (内部一致性指数) 和 `stdDev` (标准差)。指数低、标准差小的班级，说明内部学生水平整齐，教学效果均衡；反之，则说明班级内部分化严重，亟需分层教学。

# 核心指令
-   **根本原因分析**: 任何结论都必须明确引用JSON中的一个或多个具体数据指标作为证据。例如：“由于三班的内部一致性指数(homogeneityIndex)高达1.5，远超年级平均，表明该班级存在严重的学业分化问题…”
-   **量化对比**: 在进行班级比较时，要使用具体数字进行对比，而不是模糊的“更高”或“更低”。

# 输出报告结构
请严格按照以下结构生成一份层次分明、逻辑清晰的专业分析报告：

### 1. 核心洞察与摘要
- 用2-3个要点，总结本次考试最关键的发现，例如试卷质量、整体学情结构、表现最突出的班级等。

### 2. 年级整体学情诊断
-   **试卷质量分析**: 本次考试的难度、区分度是否合理？对教学评估有何影响？
-   **整体表现与结构**:
    -   年级总体的平均分、优秀率、及格率如何？
    -   学生群体呈现何种分布形态？（引用高分层厚度、核心密度等指标）高分层力量是否雄厚？后进生群体基础如何？
-   **学科关联与能力迁移分析**: 各学科成绩的关联度如何？是否存在某些学科组合的协同学习效应不佳的情况？

### 3. 班级横向对比与特色分析
-   **综合表现排名**: 哪个班级在总分和各单科的平均分、优秀率、及格率上领先或落后？
-   **班级竞争力画像**:
    -   哪些班级属于“高分领跑型”（高分位竞争力强）？
    -   哪些班级属于“基础扎实型”（中低分位竞争力强）？
    -   哪些班级是“整体均衡型”？
    -   （请使用 `quartileCompetitiveness` 数据进行分析）
-   **教学有效性与内部均衡度**:
    -   哪些班级学生水平整齐划一，教学效果均衡？（`homogeneityIndex` 较低）
    -   哪些班级存在严重的两极分化，需要立即关注并实施分层教学？（`homogeneityIndex` 较高）

### 4. 数据驱动的教学策略建议
-   **面向全体年级**:
    -   基于试卷分析，对后续命题或复习重点提出建议。
    -   基于学科关联分析，建议开展跨学科主题教研活动。
    -   基于整体学情结构，提出本阶段教学重心应该是“培优”、“补差”还是“稳中”？
-   **面向特定班级**:
    -   为表现突出的班级总结可供分享的经验。
    -   为存在问题的班级（如两极分化严重、高分层薄弱等）提供针对性的管理和教学策略。
"""


def _prepare_data_for_llm(full_report: dict) -> dict:
    """
    从完整的报告JSON中，提取用于LLM分析的核心摘要数据。
    这个函数只提取宏观（年级）和中观（班级）的统计数据，完全移除了学生个体数据。
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


def _create_llm_prompt(report_summary: dict) -> str:
    json_data_string = json.dumps(report_summary, ensure_ascii=False, indent=2)

    final_prompt = f"""{PROMPT_TEMPLATE}

# 输入的核心数据
```json
{json_data_string}
```
"""
    return final_prompt


def get_or_generate_ai_analysis(report_id: int, db: Session) -> (str, str):
    """
    获取或生成AI分析报告的核心服务函数。
    返回一个元组: (分析结果, 数据来源 "cache" 或 "generated")
    """
    report = db.query(models.AnalysisReport).filter(
        models.AnalysisReport.id == report_id
    ).first()

    if not report:
        raise ValueError("报告未找到")

    if report.status != 'completed':
        raise ValueError(f"报告状态为 {report.status}，无法进行AI分析。请等待分析完成后再试。")

    if report.ai_analysis_cache:
        return report.ai_analysis_cache, "cache"

    if not report.full_report_data:
        raise ValueError("报告数据为空，无法进行AI分析。")

    try:
        llm_data = _prepare_data_for_llm(report.full_report_data)
        prompt = _create_llm_prompt(llm_data)
        ai_result = llm_service.get_completion(prompt)

        if not ai_result:
            raise RuntimeError("LLM服务调用失败或返回空结果")

        report.ai_analysis_cache = ai_result
        db.commit()
        db.refresh(report)

        return report.ai_analysis_cache, "generated"

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"生成AI分析时发生内部错误: {str(e)}")
