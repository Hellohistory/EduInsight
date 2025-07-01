from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["考试与学科管理"])


def get_or_create_subject(db: Session, name: str) -> models.Subject:
    """
    根据名称获取已存在的学科，若不存在则新建一个。

    用于考试创建过程中动态绑定科目。
    """
    subject = db.query(models.Subject).filter(models.Subject.name == name).first()
    if not subject:
        subject = models.Subject(name=name)
        db.add(subject)
        db.flush()  # 提前写入以获取 ID
        db.refresh(subject)
    return subject


@router.get("/", response_model=List[schemas.ExamSchema], summary="获取所有考试列表（含状态）")
def handle_get_exams(db: Session = Depends(get_db)):
    """
    获取所有考试的基本信息，按时间倒序排列。
    """
    return db.query(models.Exam).order_by(models.Exam.exam_date.desc()).all()


@router.post("/", response_model=schemas.ExamSchema, summary="创建一场新考试（草稿状态）")
def handle_create_exam_with_subjects(exam_in: schemas.ExamWithSubjectsCreate, db: Session = Depends(get_db)):
    """
    创建考试，并关联多个科目。
    初始状态为 'draft'，适用于后续逐步录入成绩。
    """
    if db.query(models.Exam).filter(models.Exam.name == exam_in.name).first():
        raise HTTPException(status_code=400, detail=f"考试名称 '{exam_in.name}' 已存在。")

    try:
        # 创建考试记录
        db_exam = models.Exam(
            name=exam_in.name,
            exam_date=exam_in.exam_date,
            status='draft'
        )
        db.add(db_exam)
        db.flush()  # 为了获取考试 ID

        # 绑定学科与满分
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
    """
    获取考试详情，包括所有绑定的科目及其满分。
    """
    exam = db.query(models.Exam).options(
        joinedload(models.Exam.exam_subjects).joinedload(models.ExamSubject.subject)
    ).filter(models.Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    # 手动构造响应数据（可选用 Pydantic 自动映射）
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


@router.put("/{exam_id}/unlock", response_model=schemas.ExamSchema, summary="解锁已完成的考试以便重新编辑")
def handle_unlock_exam(exam_id: int, db: Session = Depends(get_db)):
    """
    将考试状态重置为 'draft'，用于重新录入或更正成绩。
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    if exam.status == 'draft':
        return exam  # 无需重复解锁

    exam.status = 'draft'
    db.commit()
    db.refresh(exam)
    return exam


@router.put("/{exam_id}/finalize", response_model=schemas.ExamSchema, summary="完成录入并定稿考试")
def handle_finalize_exam(exam_id: int, db: Session = Depends(get_db)):
    """
    将考试状态更新为 'completed'，锁定后不可修改成绩。
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    if exam.status != 'draft':
        raise HTTPException(status_code=400, detail=f"只有草稿状态的考试才能被定稿。当前状态: {exam.status}")

    # 可选：在此加入对成绩完整性的校验

    exam.status = 'completed'
    db.commit()
    db.refresh(exam)
    return exam


@router.delete("/{exam_id}", status_code=204, summary="删除一场考试")
def handle_delete_exam(exam_id: int, db: Session = Depends(get_db)):
    """
    删除指定 ID 的考试，仅限状态为 'draft' 且未录入成绩的情况。

    安全约束：
    - 非草稿状态考试不可删除；
    - 已有成绩记录的考试不可删除；
    - 关联的 ExamSubject 会通过 ORM 级联自动清理。
    """
    exam = db.query(models.Exam).options(joinedload(models.Exam.scores)).filter(models.Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")

    if exam.status != 'draft':
        raise HTTPException(status_code=400, detail=f"无法删除，考试 '{exam.name}' 已锁定或已提交分析。")

    if exam.scores:
        raise HTTPException(status_code=400, detail=f"无法删除，考试 '{exam.name}' 已录入部分成绩。请先清空所有成绩。")

    db.delete(exam)
    db.commit()
    return
