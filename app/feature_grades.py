# app/feature_grades.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from . import models
from .database import get_db


class GradeBase(BaseModel):
    name: str


class GradeCreate(GradeBase):
    pass


class GradeSchema(GradeBase):
    id: int

    class Config:
        from_attributes = True


def get_grade_by_name(db: Session, name: str):
    return db.query(models.Grade).filter(models.Grade.name == name).first()


def create_grade(db: Session, grade: GradeCreate):
    db_grade = models.Grade(**grade.dict())
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)
    return db_grade


def get_grades(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Grade).offset(skip).limit(limit).all()


router = APIRouter()


@router.post("/", response_model=GradeSchema, summary="创建新年级")
def handle_create_grade(grade_in: GradeCreate, db: Session = Depends(get_db)):
    db_grade = get_grade_by_name(db, name=grade_in.name)
    if db_grade:
        raise HTTPException(status_code=400, detail="年级名称已存在")
    return create_grade(db=db, grade=grade_in)


@router.get("/", response_model=List[GradeSchema], summary="获取所有年级列表")
def handle_read_grades(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    grades = get_grades(db, skip=skip, limit=limit)
    return grades
