from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from auth_utils import get_current_user
from ws_manager import manager
import models

router = APIRouter()


class SenderOut(BaseModel):
    id: int
    username: str
    avatar_url: str | None
    class Config:
        from_attributes = True

class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    sender: SenderOut
    content: str | None
    media_url: str | None
    media_type: str | None
    is_read: bool
    created_at: str
    class Config:
        from_attributes = True

class ChatOut(BaseModel):
    id: int
    name: str | None
    is_group: bool
    avatar_url: str | None
    members: list[SenderOut]
    last_message: MessageOut | None = None
    class Config:
        from_attributes = True

class CreateDMRequest(BaseModel):
    user_id: int

class CreateGroupRequest(BaseModel):
    name: str
    member_ids: list[int]

class SendMessageRequest(BaseModel):
    content: str | None = None
    media_url: str | None = None
    media_type: str | None = None


def get_chat_or_404(chat_id, db, user):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if user not in chat.members:
        raise HTTPException(status_code=403, detail="Not a member")
    return chat


@router.get("/", response_model=list[ChatOut])
def list_chats(db: Session = Depends(get_db),
               current_user: models.User = Depends(get_current_user)):
    result = []
    for chat in current_user.chats:
        last_msg = (db.query(models.Message)
                      .filter(models.Message.chat_id == chat.id)
                      .order_by(models.Message.created_at.desc()).first())
        out = ChatOut.model_validate(chat)
        if last_msg:
            out.last_message = MessageOut(
                id=last_msg.id, chat_id=last_msg.chat_id,
                sender_id=last_msg.sender_id,
                sender=SenderOut.model_validate(last_msg.sender),
                content=last_msg.content, media_url=last_msg.media_url,
                media_type=last_msg.media_type, is_read=last_msg.is_read,
                created_at=last_msg.created_at.isoformat()
            )
        result.append(out)
    return result


@router.post("/dm", response_model=ChatOut, status_code=201)
def create_dm(body: CreateDMRequest, db: Session = Depends(get_db),
              current_user: models.User = Depends(get_current_user)):
    other = db.query(models.User).filter(models.User.id == body.user_id).first()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    for chat in current_user.chats:
        if not chat.is_group and other in chat.members:
            return chat
    chat = models.Chat(is_group=False, created_by=current_user.id)
    chat.members = [current_user, other]
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.post("/group", response_model=ChatOut, status_code=201)
def create_group(body: CreateGroupRequest, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    members = [current_user]
    for uid in body.member_ids:
        u = db.query(models.User).filter(models.User.id == uid).first()
        if u and u not in members:
            members.append(u)
    chat = models.Chat(name=body.name, is_group=True, created_by=current_user.id)
    chat.members = members
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
def get_messages(chat_id: int, skip: int = 0, limit: int = 50,
                 db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    get_chat_or_404(chat_id, db, current_user)
    msgs = (db.query(models.Message)
              .filter(models.Message.chat_id == chat_id)
              .order_by(models.Message.created_at.desc())
              .offset(skip).limit(limit).all())
    return [MessageOut(
        id=m.id, chat_id=m.chat_id, sender_id=m.sender_id,
        sender=SenderOut.model_validate(m.sender),
        content=m.content, media_url=m.media_url, media_type=m.media_type,
        is_read=m.is_read, created_at=m.created_at.isoformat()
    ) for m in reversed(msgs)]


@router.post("/{chat_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(chat_id: int, body: SendMessageRequest,
                       db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)):
    chat = get_chat_or_404(chat_id, db, current_user)
    if not body.content and not body.media_url:
        raise HTTPException(status_code=400, detail="Message must have content or media")
    msg = models.Message(chat_id=chat_id, sender_id=current_user.id,
                         content=body.content, media_url=body.media_url,
                         media_type=body.media_type)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    member_ids = [m.id for m in chat.members if m.id != current_user.id]
    await manager.broadcast_to_users(member_ids, {
        "event": "new_message",
        "chat_id": chat_id,
        "message": {
            "id": msg.id, "chat_id": msg.chat_id, "sender_id": msg.sender_id,
            "sender": {"id": current_user.id, "username": current_user.username,
                       "avatar_url": current_user.avatar_url},
            "content": msg.content, "media_url": msg.media_url,
            "media_type": msg.media_type, "is_read": msg.is_read,
            "created_at": msg.created_at.isoformat(),
        }
    })
    return MessageOut(
        id=msg.id, chat_id=msg.chat_id, sender_id=msg.sender_id,
        sender=SenderOut.model_validate(current_user),
        content=msg.content, media_url=msg.media_url, media_type=msg.media_type,
        is_read=msg.is_read, created_at=msg.created_at.isoformat()
    )


@router.patch("/{chat_id}/messages/{message_id}/read")
def mark_read(chat_id: int, message_id: int, db: Session = Depends(get_db),
              current_user: models.User = Depends(get_current_user)):
    get_chat_or_404(chat_id, db, current_user)
    msg = db.query(models.Message).filter(models.Message.id == message_id).first()
    if msg:
        msg.is_read = True
        db.commit()
    return {"ok": True}