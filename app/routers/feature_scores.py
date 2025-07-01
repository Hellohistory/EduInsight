# app/feature_scores.py

from collections import defaultdict
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from app import models, schemas
from app.database import get_db


def record_scores_batch(db: Session, batch_in: schemas.ScoresBatchInput):
    try:
        exam = db.query(models.Exam).filter(models.Exam.id == batch_in.exam_id).one()
        if exam.status != 'draft':
            raise HTTPException(status_code=403, detail=f"考试 '{exam.name}' 已提交，无法修改成绩。")
    except NoResultFound:
        raise HTTPException(status_code=404, detail=f"ID为 {batch_in.exam_id} 的考试未找到。")

    subjects_in_batch = {subj for s in batch_in.scores for subj in s.subject_scores.keys()}
    subject_map = {s.name: s.id for s in
                   db.query(models.Subject).filter(models.Subject.name.in_(subjects_in_batch)).all()}

    student_ids_in_batch = {s.student_id for s in batch_in.scores}
    valid_student_ids_query = db.query(models.Student.id).filter(models.Student.id.in_(student_ids_in_batch))
    valid_student_ids = {s_id for s_id, in valid_student_ids_query.all()}

    scores_to_merge = []
    for score_input in batch_in.scores:
        if score_input.student_id not in valid_student_ids:
            continue

        for subj_name, score_val in score_input.subject_scores.items():
            if subj_name not in subject_map:
                continue

            existing_score = db.query(models.Score).filter_by(
                student_id=score_input.student_id,
                exam_id=batch_in.exam_id,
                subject_id=subject_map[subj_name]
            ).first()

            if existing_score:
                existing_score.score = score_val
                scores_to_merge.append(existing_score)
            else:
                scores_to_merge.append(
                    models.Score(
                        student_id=score_input.student_id,
                        exam_id=batch_in.exam_id,
                        subject_id=subject_map[subj_name],
                        score=score_val
                    )
                )

    if not scores_to_merge:
        raise HTTPException(status_code=400, detail="没有有效的成绩数据可以录入。")

    try:
        db.add_all(scores_to_merge)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {e}")

    return {"message": f"成功为 {len(batch_in.scores)} 名学生保存或更新了成绩。"}


router = APIRouter(tags=["成绩管理"])


@router.post(
    "/batch",
    summary="批量录入或更新成绩（仅限草稿考试）",
)
def handle_record_scores_batch(
        batch_in: schemas.ScoresBatchInput,
        db: Session = Depends(get_db)
):
    return record_scores_batch(db=db, batch_in=batch_in)


@router.get(
    "/exam/{exam_id}/class/{class_id}",
    response_model=List[schemas.ScoreInput],
    summary="获取指定班级在某场考试中的所有成绩"
)
def handle_get_scores_for_class(exam_id: int, class_id: int, db: Session = Depends(get_db)):
    student_ids = db.query(models.Student.id).filter(
        models.Student.class_id == class_id,
        models.Student.is_active == True
    ).all()
    student_ids = [s_id for s_id, in student_ids]

    if not student_ids:
        return []

    scores_query = db.query(
        models.Score.student_id,
        models.Subject.name,
        models.Score.score
    ).join(models.Subject).filter(
        models.Score.exam_id == exam_id,
        models.Score.student_id.in_(student_ids)
    ).all()

    scores_by_student = defaultdict(dict)
    for student_id, subject_name, score in scores_query:
        scores_by_student[student_id][subject_name] = score

    response_data = []
    for student_id in student_ids:
        response_data.append({
            "student_id": student_id,
            "subject_scores": scores_by_student.get(student_id, {})
        })

    return response_data


@router.put("/single", status_code=200, summary="录入或更新单个成绩")
def handle_record_single_score(
        score_in: schemas.SingleScoreUpdate,
        db: Session = Depends(get_db)
):
    """
    为单个学生、单个科目记录或更新分数。
    这是前端实现“自动保存”功能的核心API。
    """
    # 校验考试和学生是否存在
    exam = db.query(models.Exam).filter(models.Exam.id == score_in.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试未找到")
    if exam.status != 'draft':
        raise HTTPException(status_code=403, detail=f"考试 '{exam.name}' 已锁定，无法修改成绩。")

    student = db.query(models.Student).filter(models.Student.id == score_in.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生未找到")

    subject = db.query(models.Subject).filter(models.Subject.name == score_in.subject_name).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"科目 '{score_in.subject_name}' 未找到")

    # 查找或创建成绩记录
    db_score = db.query(models.Score).filter_by(
        exam_id=score_in.exam_id,
        student_id=score_in.student_id,
        subject_id=subject.id
    ).first()

    if db_score:
        db_score.score = score_in.score
    else:
        db_score = models.Score(
            exam_id=score_in.exam_id,
            student_id=score_in.student_id,
            subject_id=subject.id,
            score=score_in.score
        )
        db.add(db_score)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库保存失败: {str(e)}")

    return {"message": "成绩已保存"}