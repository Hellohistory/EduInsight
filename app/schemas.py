# app/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import date, datetime

# =============================================================================
# --- 通用与任务请求响应模型 ---
# =============================================================================

class AnalysisScope(BaseModel):
    """
    分析范围模型：指定本次分析是针对整场考试、年级，还是某些班级。
    """
    level: str = Field(
        ...,
        pattern="^(FULL_EXAM|GRADE|CLASS)$",
        description="分析层级: FULL_EXAM (全校), GRADE (年级), CLASS (班级)"
    )
    ids: List[int] = Field(
        default=[],
        description="分析对象的ID列表（年级ID或班级ID）"
    )


class AnalysisSubmissionRequest(BaseModel):
    """
    提交分析任务的请求体
    """
    exam_id: int = Field(..., gt=0, description="要分析的考试ID")
    report_name: str = Field(..., min_length=1, description="用户自定义的报告名称")
    scope: AnalysisScope = Field(..., description="分析范围")


class ReportSubmissionResponse(BaseModel):
    """
    分析任务提交后的响应体
    """
    message: str = Field(..., description="成功提示消息")
    report_id: int = Field(..., description="生成的报告ID")


class StudentBatchStatusUpdate(BaseModel):
    """
    批量更新学生状态（启用/停用）
    """
    student_ids: List[int] = Field(..., min_length=1)
    is_active: bool


# =============================================================================
# --- 学生表现与历史记录模型 ---
# =============================================================================

class StudentDetailSchema(BaseModel):
    """
    单个学生的详细信息，用于展示与分析
    """
    id: int
    student_no: str
    name: str
    class_id: int
    is_active: bool
    grade_name: str
    class_name: str
    enrollment_year: int

    model_config = ConfigDict(from_attributes=True)


class PerformanceRecordSchema(BaseModel):
    """
    一次考试中的学生表现摘要
    """
    exam_id: int
    exam_name: str
    exam_date: date
    total_score: Optional[float] = None
    class_rank: Optional[int] = None
    grade_rank: Optional[int] = None


class StudentPerformanceHistorySchema(BaseModel):
    """
    学生历次考试表现记录
    """
    records: List[PerformanceRecordSchema]


# =============================================================================
# --- 年级与班级模型 ---
# =============================================================================

class GradeBase(BaseModel):
    name: str


class GradeCreate(GradeBase):
    pass


class GradeSchema(GradeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class GradeUpdate(BaseModel):
    name: Optional[str] = None


class ClassBase(BaseModel):
    name: str
    enrollment_year: int


class ClassCreate(ClassBase):
    grade_id: int


class ClassSchema(ClassBase):
    id: int
    grade_id: int
    model_config = ConfigDict(from_attributes=True)


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    enrollment_year: Optional[int] = None


class ClassForTree(BaseModel):
    """
    树状结构中的班级节点
    """
    id: int
    name: str
    student_count: int
    enrollment_year: int
    model_config = ConfigDict(from_attributes=True)


class GradeForTree(BaseModel):
    """
    树状结构中的年级节点，包含多个班级
    """
    id: int
    name: str
    classes: List[ClassForTree] = []
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# --- 学生模型 ---
# =============================================================================

class StudentBase(BaseModel):
    student_no: str
    name: str
    class_id: int


class StudentCreate(BaseModel):
    name: str
    class_id: int


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None


class StudentSchema(StudentBase):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class StudentBatchClassUpdate(BaseModel):
    """
    学生批量分班或升学请求
    """
    student_ids: List[int] = Field(..., min_length=1)
    target_class_id: int


class StudentCreateBatch(BaseModel):
    """
    批量创建学生请求体
    """
    students: List[StudentCreate]


# =============================================================================
# --- 考试与学科模型 ---
# =============================================================================

class SubjectInExamCreate(BaseModel):
    name: str
    full_mark: float = Field(..., gt=0)


class SingleScoreUpdate(BaseModel):
    """
    单个学生某科成绩录入请求
    """
    exam_id: int
    student_id: int
    subject_name: str
    score: Optional[float]


class ExamWithSubjectsCreate(BaseModel):
    """
    创建考试时附带学科列表
    """
    name: str
    exam_date: date
    subjects: List[SubjectInExamCreate]


class ExamSchema(BaseModel):
    id: int
    name: str
    exam_date: date
    status: str
    model_config = ConfigDict(from_attributes=True)


class ExamSubjectDetailSchema(BaseModel):
    name: str
    full_mark: float
    model_config = ConfigDict(from_attributes=True)


class ExamDetailSchema(ExamSchema):
    subjects: List[ExamSubjectDetailSchema]
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# --- 成绩录入与批量上传 ---
# =============================================================================

class ScoreInput(BaseModel):
    student_id: int = Field(..., description="学生唯一标识")
    subject_scores: Dict[str, Optional[float]] = Field(
        ..., description="学科名称与成绩的映射，如 {'语文': 110.5, '数学': null}"
    )
    model_config = ConfigDict(from_attributes=True)


class ScoresBatchInput(BaseModel):
    exam_id: int = Field(..., description="考试唯一标识")
    scores: List[ScoreInput] = Field(..., min_length=1)
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# --- 对比分析与报告展示 ---
# =============================================================================

class ComparisonReportRequest(BaseModel):
    """
    创建对比分析报告的请求体
    """
    report_ids: List[int] = Field(
        ..., min_length=2,
        description="用于对比的报告ID列表，至少2个"
    )
    report_name: Optional[str] = None


class AnalysisReport(BaseModel):
    """
    分析报告完整结构，用于 API 返回
    """
    id: int
    report_name: str
    exam_id: Optional[int] = None
    status: str
    report_type: str
    error_message: Optional[str] = None
    full_report_data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    exam: Optional[ExamSchema] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedAnalysisReportResponse(BaseModel):
    """
    分页分析报告返回模型
    """
    items: List[AnalysisReport]
    total: int
    page: int
    pageSize: int
