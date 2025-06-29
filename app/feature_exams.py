# app/feature_exams.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from . import models, schemas
from .database import get_db

router = APIRouter(tags=["考试与学科管理"])


def get_or_create_subject(db: Session, name: str) -> models.Subject:
    subject = db.query(models.Subject).filter(models.Subject.name == name).first()
    if not subject:
        subject = models.Subject(name=name)
        db.add(subject)
        db.flush()
        db.refresh(subject)
    return subject


@router.get("/", response_model=List[schemas.ExamSchema], summary="获取所有考试列表（含状态）")
def handle_get_exams(db: Session = Depends(get_db)):
    return db.query(models.Exam).order_by(models.Exam.exam_date.desc()).all()


@router.post("/", response_model=schemas.ExamSchema, summary="创建一场新考试（草稿状态）")
def handle_create_exam_with_subjects(exam_in: schemas.ExamWithSubjectsCreate, db: Session = Depends(get_db)):
    if db.query(models.Exam).filter(models.Exam.name == exam_in.name).first():
        raise HTTPException(status_code=400, detail=f"考试名称 '{exam_in.name}' 已存在。")

    db_exam = None
    try:
        db_exam = models.Exam(
            name=exam_in.name,
            exam_date=exam_in.exam_date,
            status='draft'
        )
        db.add(db_exam)
        db.flush()

        for subject_data in exam_in.subjects:
            subject = get_or_create_subject(db, name=subject_data.name)
            exam_subject = models.ExamSubject(
                exam_id=db_exam.id,
                subject_id=subject.id,
                full_mark=subject_data.full_mark
            )
            db.add(exam_subject)

        db.commit()
        db.refresh(db_exam)
        return db_exam
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建考试时发生错误: {str(e)}")


@router.get("/{exam_id}", response_model=schemas.ExamDetailSchema, summary="获取单场考试的详细信息")
def handle_get_exam_details(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(models.Exam).options(
        joinedload(models.Exam.exam_subjects).joinedload(models.ExamSubject.subject)
    ).filter(models.Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    response_data = {
        "id": exam.id,
        "name": exam.name,
        "exam_date": exam.exam_date,
        "status": exam.status,
        "subjects": [
            {"name": es.subject.name, "full_mark": es.full_mark}
            for es in exam.exam_subjects
        ]
    }

    return schemas.ExamDetailSchema(**response_data)
