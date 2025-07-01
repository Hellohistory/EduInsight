# app/feature_classes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["班级管理"])


def get_class(db: Session, class_id: int):
    """根据班级ID获取班级实例。"""
    return db.query(models.Class).filter(models.Class.id == class_id).first()


def get_class_by_name(db: Session, name: str):
    """根据班级名称查询班级。"""
    return db.query(models.Class).filter(models.Class.name == name).first()


def get_classes(db: Session, skip: int = 0, limit: int = 100):
    """分页获取所有班级。"""
    return db.query(models.Class).offset(skip).limit(limit).all()


def create_class(db: Session, class_in: schemas.ClassCreate):
    """创建新班级的通用函数。"""
    db_class = models.Class(
        name=class_in.name,
        enrollment_year=class_in.enrollment_year,
        grade_id=class_in.grade_id
    )
    db.add(db_class)
    db.commit()
    db.refresh(db_class)
    return db_class


def get_class_by_grade_and_name(db: Session, *, grade_id: int, name: str):
    """按 (grade_id, name) 查询班级，确保年级下班级名唯一。"""
    return (
        db.query(models.Class)
        .filter(
            models.Class.grade_id == grade_id,
            models.Class.name == name,
        )
        .first()
    )


@router.post("/", response_model=schemas.ClassSchema, summary="创建新班级")
def handle_create_class(class_in: schemas.ClassCreate, db: Session = Depends(get_db)):
    """
    创建新班级。

    - 班级名称在同一个年级中必须唯一
    - 需验证年级是否存在
    """
    db_grade = db.query(models.Grade).filter(models.Grade.id == class_in.grade_id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="所属年级不存在")

    existed = get_class_by_grade_and_name(db, grade_id=class_in.grade_id, name=class_in.name)
    if existed:
        raise HTTPException(status_code=400, detail="该年级已存在同名班级")

    db_class = models.Class(
        name=class_in.name,
        enrollment_year=class_in.enrollment_year,
        grade_id=class_in.grade_id,
    )
    db.add(db_class)
    db.commit()
    db.refresh(db_class)
    return db_class


@router.get("/", response_model=List[schemas.ClassSchema], summary="获取所有班级列表")
def handle_read_classes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    获取所有班级的列表信息（支持分页）。
    """
    classes = get_classes(db, skip=skip, limit=limit)
    return classes


@router.get("/tree", response_model=List[schemas.GradeForTree], summary="获取年级-班级的树状结构")
def get_class_tree(db: Session = Depends(get_db)):
    """
    获取包含年级和班级的树状结构数据。

    - 每个年级下的班级列表按名称排序
    - 每个班级附带激活学生数量
    """
    grades = db.query(models.Grade).options(
        joinedload(models.Grade.classes).joinedload(models.Class.students)
    ).order_by(models.Grade.name).all()

    result = []
    for grade in grades:
        grade_data = schemas.GradeForTree(id=grade.id, name=grade.name, classes=[])

        # 班级排序
        sorted_classes = sorted(grade.classes, key=lambda c: c.name)

        for cls in sorted_classes:
            # 统计该班级中处于激活状态的学生数量
            active_student_count = sum(1 for s in cls.students if s.is_active)

            class_data = schemas.ClassForTree(
                id=cls.id,
                name=cls.name,
                student_count=active_student_count,
                enrollment_year=cls.enrollment_year
            )
            grade_data.classes.append(class_data)

        result.append(grade_data)

    return result


@router.get("/{class_id}", response_model=schemas.ClassSchema, summary="根据ID获取单个班级信息")
def handle_read_class(class_id: int, db: Session = Depends(get_db)):
    """
    根据班级 ID 获取单个班级的详细信息。
    """
    db_class = get_class(db, class_id=class_id)
    if db_class is None:
        raise HTTPException(status_code=404, detail="班级未找到")
    return db_class


@router.put("/{class_id}", response_model=schemas.ClassSchema, summary="更新班级信息")
def handle_update_class(class_id: int, class_in: schemas.ClassUpdate, db: Session = Depends(get_db)):
    """
    更新指定班级的名称或入学年份。

    - 若更新名称，需确保新名称在同年级中不重复
    """
    db_class = get_class(db, class_id=class_id)
    if not db_class:
        raise HTTPException(status_code=404, detail="班级未找到")

    update_data = class_in.model_dump(exclude_unset=True)

    # 校验班级名是否冲突
    if "name" in update_data and update_data["name"] != db_class.name:
        existed = get_class_by_grade_and_name(db, grade_id=db_class.grade_id, name=update_data["name"])
        if existed:
            raise HTTPException(status_code=400, detail="该年级下已存在同名班级")

    for key, value in update_data.items():
        setattr(db_class, key, value)

    db.commit()
    db.refresh(db_class)
    return db_class


@router.delete("/{class_id}", status_code=204, summary="删除班级")
def handle_delete_class(class_id: int, db: Session = Depends(get_db)):
    """
    删除一个指定的班级。

    - 若班级下仍存在学生，禁止删除
    """
    db_class = get_class(db, class_id=class_id)
    if not db_class:
        raise HTTPException(status_code=404, detail="班级未找到")

    # 安全限制：班级下若有学生，则禁止删除操作
    if db_class.students:
        raise HTTPException(
            status_code=400,
            detail=f"无法删除班级 '{db_class.name}'，因为它下面仍有 {len(db_class.students)} 名学生。请先转移学生。"
        )

    db.delete(db_class)
    db.commit()
    return
