# app/schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import date, datetime


class AnalysisScope(BaseModel):
    level: str = Field(
        ...,
        pattern="^(FULL_EXAM|GRADE|CLASS)$",
        description="分析层级: FULL_EXAM (全校/整场考试), GRADE (按年级), CLASS (按班级)"
    )
    ids: List[int] = Field(
        default=[],
        description="分析对象的ID列表。当 level=GRADE 时为年级ID列表，当 level=CLASS 时为班级ID列表"
    )


class AnalysisSubmissionRequest(BaseModel):
    exam_id: int = Field(..., gt=0, description="要分析的考试ID")
    report_name: str = Field(..., min_length=1, description="用户自定义的报告名称")
    scope: AnalysisScope = Field(..., description="定义的分析范围")


class StudentDetailSchema(BaseModel):
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
    exam_id: int
    exam_name: str
    exam_date: date
    total_score: Optional[float] = None
    class_rank: Optional[int] = None
    grade_rank: Optional[int] = None


class StudentPerformanceHistorySchema(BaseModel):
    records: List[PerformanceRecordSchema]


class StudentBatchStatusUpdate(BaseModel):
    student_ids: List[int] = Field(..., min_length=1)
    is_active: bool


# --- 年级模型 ---
class GradeBase(BaseModel):
    name: str


class GradeCreate(GradeBase):
    pass


class GradeSchema(GradeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- 班级模型 ---
class ClassBase(BaseModel):
    name: str
    enrollment_year: int


class ClassCreate(ClassBase):
    grade_id: int


class ClassSchema(ClassBase):
    id: int
    grade_id: int
    model_config = ConfigDict(from_attributes=True)


class ClassForTree(BaseModel):
    id: int
    name: str
    # 【新增】增加班级学生总数统计
    student_count: int
    model_config = ConfigDict(from_attributes=True)


class GradeForTree(BaseModel):
    id: int
    name: str
    classes: List[ClassForTree] = []
    model_config = ConfigDict(from_attributes=True)


# --- 学生管理模型 ---
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
    student_ids: List[int] = Field(..., min_length=1)
    target_class_id: int


class StudentCreateBatch(BaseModel):
    students: List[StudentCreate]


# --- 考试与学科模型 ---
class SubjectInExamCreate(BaseModel):
    name: str
    full_mark: float = Field(..., gt=0)


class ExamWithSubjectsCreate(BaseModel):
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


# --- 成绩录入模型 ---
class ScoreInput(BaseModel):
    student_id: int = Field(..., description="学生唯一标识")
    subject_scores: Dict[str, Optional[float]] = Field(
        ..., description="学科名称与对应分数的映射，如 {\"语文\": 120, \"数学\": null}"
    )
    model_config = ConfigDict(from_attributes=True)


class ScoresBatchInput(BaseModel):
    exam_id: int = Field(..., description="考试唯一标识")
    scores: List[ScoreInput] = Field(..., min_length=1)
    model_config = ConfigDict(from_attributes=True)


# --- 对比分析模型 ---
class ComparisonReportRequest(BaseModel):
    report_ids: List[int] = Field(
        ...,
        min_length=2,
        description="至少选择两个已完成的报告ID进行对比"
    )
    report_name: Optional[str] = None


class AnalysisReport(BaseModel):
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
    items: List[AnalysisReport]
    total: int
    page: int
    pageSize: int
