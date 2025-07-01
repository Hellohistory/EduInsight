# app/models.py

from sqlalchemy import (Column, Integer, String, Boolean, Float, Date,
                        ForeignKey, UniqueConstraint, DateTime, Text, JSON)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Grade(Base):
    """
    年级表：表示一个年级（如初一、初二...）
    """
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # 年级名称，如“初一”

    classes = relationship("Class", back_populates="grade")  # 一个年级下有多个班级


class Class(Base):
    """
    班级表：隶属于某个年级，包含若干学生
    """
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)  # 班级名称（如“一班”）
    enrollment_year = Column(Integer, nullable=False)  # 入学年份（用于学号生成）
    grade_id = Column(Integer, ForeignKey("grades.id"), nullable=False, index=True)  # 所属年级ID

    grade = relationship("Grade", back_populates="classes")  # 班级所属年级
    students = relationship("Student", back_populates="class_")  # 班级包含的学生列表

    __table_args__ = (
        UniqueConstraint("grade_id", "name", name="uix_grade_id_name"),  # 同一年的班级名唯一
    )


class Student(Base):
    """
    学生表：属于某个班级，可以参与考试，有成绩信息
    """
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_no = Column(String, unique=True, index=True, nullable=False)  # 唯一学号（例如20230001）
    name = Column(String, index=True, nullable=False)  # 学生姓名
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)  # 所属班级
    is_active = Column(Boolean, default=True, nullable=False)  # 是否在读

    class_ = relationship("Class", back_populates="students")  # 所属班级
    scores = relationship("Score", back_populates="student", cascade="all, delete-orphan")  # 成绩列表


class Subject(Base):
    """
    学科表：如数学、语文等
    """
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # 学科名称

    exam_associations = relationship("ExamSubject", back_populates="subject")  # 所参与的考试-学科关联
    scores = relationship("Score", back_populates="subject")  # 学科成绩


class Exam(Base):
    """
    考试表：一次考试记录，可包含多个学科和成绩
    """
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # 考试名称
    exam_date = Column(Date, nullable=False)  # 考试日期
    status = Column(String, default="draft", nullable=False)  # 状态（draft/submitted/completed）

    exam_subjects = relationship("ExamSubject", back_populates="exam", cascade="all, delete-orphan")  # 学科关联
    reports = relationship("AnalysisReport", back_populates="exam")  # 分析报告
    scores = relationship("Score", back_populates="exam", cascade="all, delete-orphan")  # 所有成绩


class ExamSubject(Base):
    """
    考试-学科关联表：记录某场考试包含哪些学科
    """
    __tablename__ = "exam_subjects"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)  # 考试ID
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)  # 学科ID
    full_mark = Column(Float, nullable=False, default=100.0)  # 该学科的满分

    __table_args__ = (
        UniqueConstraint('exam_id', 'subject_id', name='_exam_subject_uc'),  # 防止重复添加相同学科
    )

    exam = relationship("Exam", back_populates="exam_subjects")  # 所属考试
    subject = relationship("Subject", back_populates="exam_associations")  # 对应学科


class Score(Base):
    """
    成绩表：记录某个学生在某场考试、某个学科中的成绩
    """
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)  # 学生ID
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)  # 考试ID
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)  # 学科ID
    score = Column(Float, nullable=True)  # 实际得分（允许为空，表示缺考）

    student = relationship("Student", back_populates="scores")  # 所属学生
    subject = relationship("Subject", back_populates="scores")  # 对应学科
    exam = relationship("Exam", back_populates="scores")  # 对应考试

    __table_args__ = (
        UniqueConstraint('student_id', 'exam_id', 'subject_id', name='_student_exam_subject_uc'),  # 唯一约束
    )


class AnalysisReport(Base):
    """
    分析报告表：记录每次分析任务的输入范围、结果、状态等信息
    """
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_name = Column(String, index=True, nullable=False)  # 报告名称
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=True)  # 关联考试（仅单场报告有）
    report_type = Column(String, default="single", nullable=False)  # 报告类型（single/comparison）
    source_description = Column(Text)  # 源描述（记录分析范围）
    status = Column(String, default="processing", nullable=False)  # 主报告状态（processing/completed/failed）
    error_message = Column(Text, nullable=True)  # 错误信息
    full_report_data = Column(JSON, nullable=True)  # 分析报告的原始数据结构
    chart_data = Column(JSON, nullable=True)  # 图表数据（可惰性生成）

    ai_analysis_cache = Column(Text, nullable=True)  # AI分析结果缓存

    ai_analysis_status = Column(String, default="not_started", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())  # 更新时间

    exam = relationship("Exam", back_populates="reports")  # 所属考试（可为空）
