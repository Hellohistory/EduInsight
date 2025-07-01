from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional  # 确保引入 Optional

from app import models, schemas
from app.database import get_db


class GradeBase(BaseModel):
    name: str


class GradeCreate(GradeBase):
    pass


class GradeUpdate(BaseModel):
    name: Optional[str] = None


class GradeSchema(GradeBase):
    id: int

    class Config:
        from_attributes = True


def get_grade(db: Session, grade_id: int):
    return db.query(models.Grade).filter(models.Grade.id == grade_id).first()


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


# --- 【新增代码块 START】 ---
@router.put("/{grade_id}", response_model=GradeSchema, summary="更新年级信息")
def handle_update_grade(
        grade_id: int, grade_in: GradeUpdate, db: Session = Depends(get_db)
):
    db_grade = get_grade(db, grade_id=grade_id)
    if not db_grade:
        raise HTTPException(status_code=404, detail="年级未找到")

    update_data = grade_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != db_grade.name:
        existed = get_grade_by_name(db, name=update_data["name"])
        if existed:
            raise HTTPException(status_code=400, detail="该年级名称已存在")

    for key, value in update_data.items():
        setattr(db_grade, key, value)

    db.commit()
    db.refresh(db_grade)
    return db_grade


@router.delete("/{grade_id}", status_code=204, summary="删除年级")
def handle_delete_grade(grade_id: int, db: Session = Depends(get_db)):
    db_grade = db.query(models.Grade).options(
        joinedload(models.Grade.classes).joinedload(models.Class.students)
    ).filter(models.Grade.id == grade_id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="年级未找到")
    for cls in db_grade.classes:
        if cls.students:
            raise HTTPException(
                status_code=400,
                detail=f"无法删除年级 '{db_grade.name}'，因为它下属的班级 '{cls.name}' 中仍有学生。"
            )
    db.delete(db_grade)
    db.commit()
    return
# --- 【新增代码块 END】 ---