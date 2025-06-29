# app/models.py
from sqlalchemy import (Column, Integer, String, Boolean, Float, Date,
                        ForeignKey, UniqueConstraint, DateTime, Text, JSON)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # 关联关系
    classes = relationship("Class", back_populates="grade")


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, index=True, nullable=False)

    enrollment_year = Column(Integer, nullable=False)

    grade_id = Column(Integer, ForeignKey("grades.id"), nullable=False, index=True)

    grade = relationship("Grade", back_populates="classes")
    students = relationship("Student", back_populates="class_")

    __table_args__ = (
        UniqueConstraint("grade_id", "name", name="uix_grade_id_name"),
    )


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    student_no = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    class_ = relationship("Class", back_populates="students")
    scores = relationship("Score", back_populates="student", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    exam_associations = relationship("ExamSubject", back_populates="subject")
    scores = relationship("Score", back_populates="subject")


class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    exam_date = Column(Date, nullable=False)
    status = Column(String, default="draft", nullable=False)
    exam_subjects = relationship("ExamSubject", back_populates="exam", cascade="all, delete-orphan")
    reports = relationship("AnalysisReport", back_populates="exam")


class ExamSubject(Base):
    __tablename__ = "exam_subjects"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    full_mark = Column(Float, nullable=False, default=100.0)
    __table_args__ = (UniqueConstraint('exam_id', 'subject_id', name='_exam_subject_uc'),)
    exam = relationship("Exam", back_populates="exam_subjects")
    subject = relationship("Subject", back_populates="exam_associations")


class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    score = Column(Float, nullable=True)
    student = relationship("Student", back_populates="scores")
    subject = relationship("Subject", back_populates="scores")
    __table_args__ = (UniqueConstraint('student_id', 'exam_id', 'subject_id', name='_student_exam_subject_uc'),)


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    id = Column(Integer, primary_key=True, index=True)
    report_name = Column(String, index=True, nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=True)
    exam = relationship("Exam", back_populates="reports")
    report_type = Column(String, default="single", nullable=False)
    ai_analysis_cache = Column(Text, nullable=True)
    source_description = Column(Text)
    status = Column(String, default="processing", nullable=False)
    error_message = Column(Text, nullable=True)
    full_report_data = Column(JSON, nullable=True)
    chart_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
