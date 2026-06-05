from sqlalchemy import (Column, Integer, String, Boolean, DateTime,
                        ForeignKey, Text, Table)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

chat_members = Table(
    "chat_members", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("chat_id", Integer, ForeignKey("chats.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String, unique=True, index=True, nullable=False)
    email      = Column(String, unique=True, index=True, nullable=False)
    phone      = Column(String, unique=True, nullable=True)
    password   = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    bio        = Column(String, nullable=True)
    is_online  = Column(Boolean, default=False)
    last_seen  = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    messages   = relationship("Message", back_populates="sender")
    chats      = relationship("Chat", secondary=chat_members, back_populates="members")


class Chat(Base):
    __tablename__ = "chats"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=True)
    is_group   = Column(Boolean, default=False)
    avatar_url = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    members    = relationship("User", secondary=chat_members, back_populates="chats")
    messages   = relationship("Message", back_populates="chat",
                              order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    id          = Column(Integer, primary_key=True, index=True)
    chat_id     = Column(Integer, ForeignKey("chats.id"), nullable=False)
    sender_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    content     = Column(Text, nullable=True)
    media_url   = Column(String, nullable=True)
    media_type  = Column(String, nullable=True)
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    chat        = relationship("Chat", back_populates="messages")
    sender      = relationship("User", back_populates="messages")