from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from auth_utils import get_current_user
import models, uuid, os

router = APIRouter()
UPLOAD_DIR = "uploads/media"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED = {
    "jpg": "image", "jpeg": "image", "png": "image", "webp": "image", "gif": "image",
    "pdf": "file", "txt": "file", "zip": "file", "mp4": "video", "mp3": "audio",
}


@router.post("/upload")
async def upload_media(file: UploadFile = File(...),
                       current_user: models.User = Depends(get_current_user)):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed")
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
    filename = f"{uuid.uuid4()}.{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(contents)
    return {
        "url": f"/uploads/media/{filename}",
        "media_type": ALLOWED[ext],
        "filename": file.filename,
        "size_kb": round(len(contents) / 1024, 1),
    }