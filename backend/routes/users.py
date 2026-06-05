from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from auth_utils import get_current_user
import models, shutil, uuid, os

router = APIRouter()
UPLOAD_DIR = "uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    phone: str | None
    avatar_url: str | None
    bio: str | None
    is_online: bool
    class Config:
        from_attributes = True


class UpdateProfile(BaseModel):
    bio: str | None = None
    phone: str | None = None


@router.get("/me", response_model=UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=UserOut)
def update_profile(body: UpdateProfile, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    if body.bio is not None:
        current_user.bio = body.bio
    if body.phone is not None:
        current_user.phone = body.phone
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/avatar", response_model=UserOut)
def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise HTTPException(status_code=400, detail="Only jpg/png/webp allowed")
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/search", response_model=list[UserOut])
def search_users(q: str, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    return (db.query(models.User)
              .filter(models.User.username.ilike(f"%{q}%"),
                      models.User.id != current_user.id)
              .limit(20).all())

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db),
             current_user: models.User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user