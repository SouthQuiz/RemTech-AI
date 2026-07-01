"""TASK-0104 — Модели данных по ER-диаграмме
(02_Техническая архитектура/Схемы/Remtechnika_AI_ER_Database.svg).

Таблицы: users, conversations, chat_history, uploaded_files, activity_log,
kb_documents, kb_chunks (embedding vector(1024)), agents, model_configs.
Индекс HNSW для kb_chunks.embedding выносится в EPIC-03 (после ингеста).
"""
import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base

EMBED_DIM = get_settings().embed_dim


def _now_col() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    active: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[dt.datetime] = _now_col()

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Новый чат")
    created_at: Mapped[dt.datetime] = _now_col()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ChatHistory"]] = relationship(back_populates="conversation")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[dict | list | str] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = _now_col()

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str | None] = mapped_column(String(30))
    file_name: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(20), default="upload")  # upload | output
    created_at: Mapped[dt.datetime] = _now_col()


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    owner_role: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[dt.datetime] = _now_col()

    chunks: Mapped[list["KBChunk"]] = relationship(back_populates="document")


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"), index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    # 'metadata' зарезервировано в DeclarativeBase → атрибут meta, колонка metadata
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)

    document: Mapped["KBDocument"] = relationship(back_populates="chunks")


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String(50), unique=True)
    provider: Mapped[str] = mapped_column(String(50))
    endpoint: Mapped[str | None] = mapped_column(Text)
    fallback_to: Mapped[str | None] = mapped_column(String(50))


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    tools: Mapped[list | None] = mapped_column(JSON)
    default_model: Mapped[int | None] = mapped_column(
        ForeignKey("model_configs.id"), index=True
    )
    allowed_roles: Mapped[str | None] = mapped_column(Text)

    model: Mapped["ModelConfig"] = relationship()
