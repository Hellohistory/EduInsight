# app/feature_classes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from . import models, schemas
from .database import get_db

router = APIRouter(tags=["班级管理"])


def get_class(db: Session, class_id: int):
    return db.query(models.Class).filter(models.Class.id == class_id).first()


def get_class_by_name(db: Session, name: str):
    return db.query(models.Class).filter(models.Class.name == name).first()


def get_classes(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Class).offset(skip).limit(limit).all()


def create_class(db: Session, class_in: schemas.ClassCreate):
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
    """按 (grade_id, name) 查询班级。"""
    return (
        db.query(models.Class)
        .filter(
            models.Class.grade_id == grade_id,
            models.Class.name == name,
        )
        .first()
    )


@router.post("/", response_model=schemas.ClassSchema, summary="创建新班级")
def handle_create_class(
        class_in: schemas.ClassCreate, db: Session = Depends(get_db)
):
    db_grade = (
        db.query(models.Grade).filter(models.Grade.id == class_in.grade_id).first()
    )
    if not db_grade:
        raise HTTPException(status_code=404, detail="所属年级不存在")

    existed = get_class_by_grade_and_name(
        db, grade_id=class_in.grade_id, name=class_in.name
    )
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
    classes = get_classes(db, skip=skip, limit=limit)
    return classes


@router.get("/tree", response_model=List[schemas.GradeForTree], summary="获取年级-班级的树状结构")
def get_class_tree(db: Session = Depends(get_db)):
    grades = db.query(models.Grade).options(
        joinedload(models.Grade.classes).joinedload(models.Class.students)
    ).order_by(models.Grade.name).all()

    result = []
    for grade in grades:
        grade_data = schemas.GradeForTree(id=grade.id, name=grade.name, classes=[])
        for cls in grade.classes:
            active_student_count = sum(1 for s in cls.students if s.is_active)
            class_data = schemas.ClassForTree(id=cls.id, name=cls.name, student_count=active_student_count)
            grade_data.classes.append(class_data)
        result.append(grade_data)

    return result


@router.get("/{class_id}", response_model=schemas.ClassSchema, summary="根据ID获取单个班级信息")
def handle_read_class(class_id: int, db: Session = Depends(get_db)):
    db_class = get_class(db, class_id=class_id)
    if db_class is None:
        raise HTTPException(status_code=404, detail="班级未找到")
    return db_class
