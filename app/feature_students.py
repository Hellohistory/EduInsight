# app/feature_students.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import date
from sqlalchemy.sql.functions import func

from . import models, schemas
from .database import get_db

# 创建路由器，归类到“学生管理”模块
router = APIRouter(tags=["学生管理"])


# ------------------ 辅助函数 ------------------

def _generate_student_no_for_batch(db: Session, class_id: int, batch_size: int) -> List[str]:
    """
    为指定班级生成一批连续的新学号。

    :param db: 数据库会话
    :param class_id: 班级ID
    :param batch_size: 生成的学号数量
    :return: 学号字符串列表
    """
    target_class = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not target_class:
        raise HTTPException(status_code=404, detail=f"ID为 {class_id} 的班级不存在。")

    enrollment_year = target_class.enrollment_year
    year_prefix = str(enrollment_year)

    # 找出当前最大学号作为起始序号
    latest_student_no = db.query(func.max(models.Student.student_no)) \
        .filter(models.Student.student_no.like(f"{year_prefix}%")) \
        .scalar()

    start_sequence = 1
    if latest_student_no and len(latest_student_no) > 4:
        try:
            start_sequence = int(latest_student_no[4:]) + 1
        except (ValueError, TypeError):
            start_sequence = 1

    # 生成连续的新学号
    new_student_nos = []
    for i in range(batch_size):
        current_sequence = start_sequence + i
        sequence_str = str(current_sequence).zfill(4)
        new_student_nos.append(f"{year_prefix}{sequence_str}")

    return new_student_nos


def get_students_by_class(db: Session, class_id: int, include_inactive: bool = False):
    """
    获取某个班级的学生列表，可选是否包含已停用的学生。
    """
    query = db.query(models.Student).filter(models.Student.class_id == class_id)
    if not include_inactive:
        query = query.filter(models.Student.is_active == True)
    return query.order_by(models.Student.student_no).all()


def activate_student(db: Session, student_id: int):
    """激活指定学生。"""
    db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not db_student:
        return None
    db_student.is_active = True
    db.commit()
    db.refresh(db_student)
    return db_student


def deactivate_student(db: Session, student_id: int):
    """停用指定学生。"""
    db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not db_student:
        return None
    db_student.is_active = False
    db.commit()
    db.refresh(db_student)
    return db_student


def update_student(db: Session, student_id: int, student_in: schemas.StudentUpdate):
    """更新学生的基本信息。"""
    db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not db_student:
        return None
    update_data = student_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_student, key, value)
    db.commit()
    db.refresh(db_student)
    return db_student


def batch_update_student_class(db: Session, update_info: schemas.StudentBatchClassUpdate):
    """批量更新学生所属班级（如升学）。"""
    db.query(models.Student).filter(
        models.Student.id.in_(update_info.student_ids)
    ).update({"class_id": update_info.target_class_id}, synchronize_session=False)
    db.commit()
    return {"message": f"成功为 {len(update_info.student_ids)} 名学生更新了班级。"}


def batch_update_student_status(db: Session, update_info: schemas.StudentBatchStatusUpdate):
    """批量修改学生是否在读状态（激活或停用）。"""
    db.query(models.Student).filter(
        models.Student.id.in_(update_info.student_ids)
    ).update({"is_active": update_info.is_active}, synchronize_session=False)
    db.commit()
    return {"message": f"成功为 {len(update_info.student_ids)} 名学生更新了在读状态。"}


# ------------------ 接口实现 ------------------

@router.post("/", response_model=schemas.StudentSchema, summary="新增单个学生")
def handle_create_student(student_in: schemas.StudentCreate, db: Session = Depends(get_db)):
    """
    创建新学生，并自动生成学号。
    """
    try:
        generated_no = _generate_student_no_for_batch(db, student_in.class_id, 1)[0]
        db_student = models.Student(
            name=student_in.name,
            class_id=student_in.class_id,
            student_no=generated_no
        )
        db.add(db_student)
        db.commit()
        db.refresh(db_student)
        return db_student
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="学号生成冲突，请重试。")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建学生时发生错误: {e}")


@router.post("/batch", response_model=List[schemas.StudentSchema], summary="批量新增学生")
def handle_create_students_batch(batch_in: schemas.StudentCreateBatch, db: Session = Depends(get_db)):
    """
    批量新增学生，并为每人分配唯一学号。
    """
    if not batch_in.students:
        return []

    class_id = batch_in.students[0].class_id
    try:
        generated_nos = _generate_student_no_for_batch(db, class_id, len(batch_in.students))
        new_students = []
        for i, student_data in enumerate(batch_in.students):
            new_student = models.Student(
                name=student_data.name,
                class_id=class_id,
                student_no=generated_nos[i]
            )
            new_students.append(new_student)
        db.add_all(new_students)
        db.commit()
        for student in new_students:
            db.refresh(student)
        return new_students
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="批量创建失败，生成学号时发生冲突，请重试。")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建学生时发生未知错误: {e}")


@router.get("/by_class/{class_id}", response_model=List[schemas.StudentSchema], summary="获取班级学生列表")
def handle_read_students_by_class(class_id: int, include_inactive: bool = False, db: Session = Depends(get_db)):
    """
    获取指定班级的所有学生（可选是否包含已停用学生）。
    """
    return get_students_by_class(db=db, class_id=class_id, include_inactive=include_inactive)


@router.put("/{student_id}/activate", response_model=schemas.StudentSchema, summary="激活学生账户")
def handle_activate_student(student_id: int, db: Session = Depends(get_db)):
    """将指定学生账户设为在读状态。"""
    student = activate_student(db=db, student_id=student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="学生未找到")
    return student


@router.put("/{student_id}/deactivate", response_model=schemas.StudentSchema, summary="停用学生账户")
def handle_deactivate_student(student_id: int, db: Session = Depends(get_db)):
    """将指定学生账户设为停用状态。"""
    student = deactivate_student(db=db, student_id=student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="学生未找到")
    return student


@router.put("/{student_id}", response_model=schemas.StudentSchema, summary="更新学生信息（如改名、换班）")
def handle_update_student(student_id: int, student_in: schemas.StudentUpdate, db: Session = Depends(get_db)):
    """更新学生的姓名、班级等信息。"""
    updated_student = update_student(db, student_id, student_in)
    if updated_student is None:
        raise HTTPException(status_code=404, detail="学生未找到")
    return updated_student


@router.post("/batch-update-status", summary="批量激活或停用学生")
def handle_batch_update_status(update_info: schemas.StudentBatchStatusUpdate, db: Session = Depends(get_db)):
    """批量设置学生状态（是否在读）。"""
    return batch_update_student_status(db, update_info)


@router.post("/batch-update-class", summary="批量分班或升学")
def handle_batch_update_class(update_info: schemas.StudentBatchClassUpdate, db: Session = Depends(get_db)):
    """将多名学生分配到新班级。"""
    target_class = db.query(models.Class).filter(models.Class.id == update_info.target_class_id).first()
    if not target_class:
        raise HTTPException(status_code=404, detail=f"ID为 {update_info.target_class_id} 的目标班级未找到")
    return batch_update_student_class(db, update_info)


@router.get("/{student_id}/details", response_model=schemas.StudentDetailSchema, summary="获取单个学生详细信息")
def get_student_details(student_id: int, db: Session = Depends(get_db)):
    """
    获取学生的完整信息（包括班级和年级）。
    """
    student = db.query(models.Student).options(
        joinedload(models.Student.class_).joinedload(models.Class.grade)
    ).filter(models.Student.id == student_id).first()
    if not student or not student.class_ or not student.class_.grade:
        raise HTTPException(status_code=404, detail="学生或其关联的班级/年级信息未找到")
    return schemas.StudentDetailSchema(
        id=student.id,
        student_no=student.student_no,
        name=student.name,
        class_id=student.class_id,
        is_active=student.is_active,
        class_name=student.class_.name,
        grade_name=student.class_.grade.name,
        enrollment_year=student.class_.enrollment_year
    )


@router.get("/{student_id}/performance", response_model=schemas.StudentPerformanceHistorySchema,
            summary="获取学生个人表现历史")
def get_student_performance_history(student_id: int, db: Session = Depends(get_db)):
    """
    获取指定学生在多个报告中的总分、排名等历史表现记录。
    """
    reports = db.query(models.AnalysisReport).filter(
        models.AnalysisReport.status == "completed",
        models.AnalysisReport.report_type == "single",
        models.AnalysisReport.full_report_data.op('->')('tables').isnot(None)
    ).all()

    reports.sort(key=lambda r: r.exam.exam_date if r.exam else date.min)
    performance_records = []

    for report in reports:
        if not report.exam:
            continue

        # 遍历每份报告查找学生成绩记录
        student_found_in_report = False
        for table in report.full_report_data.get("tables", []):
            for student_data in table.get("students", []):
                if student_data.get("studentId") == student_id:
                    performance_records.append(
                        schemas.PerformanceRecordSchema(
                            exam_id=report.exam_id,
                            exam_name=report.exam.name,
                            exam_date=report.exam.exam_date,
                            total_score=student_data.get("totalScore"),
                            class_rank=student_data.get("classRank"),
                            grade_rank=student_data.get("gradeRank")
                        )
                    )
                    student_found_in_report = True
                    break
            if student_found_in_report:
                break

    return {"records": performance_records}
