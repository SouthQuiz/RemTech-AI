"""Роутер файлов: загрузка и скачивание (с проверкой владения — IDOR)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import repositories as repo
from app import storage
from app.database import get_db
from app.deps import _read_upload_limited, current_user
from services import filecheck
from services.extract import detect_kind

router = APIRouter()


@router.post("/api/upload")
async def api_upload(file: UploadFile = File(...), conversation_id: int | None = Form(None),
                     user: dict = Depends(current_user), db: AsyncSession = Depends(get_db)):
    data = await _read_upload_limited(file)
    if err := filecheck.ensure_allowed(file.filename, data):
        raise HTTPException(400, err)
    kind = detect_kind(file.filename)
    rec = await storage.save_bytes(db, user["user_id"], conversation_id, file.filename,
                                   data, kind=kind, direction="upload")
    await db.commit()
    return {"file_id": rec.id, "name": file.filename, "kind": kind}


@router.get("/api/files/{file_id}")
async def api_download(file_id: int, u: dict = Depends(current_user),
                       db: AsyncSession = Depends(get_db)):
    # #4 — авторизация по заголовку Authorization (фронт грузит файл через fetch/blob),
    # токен больше не передаётся в URL.
    rec = await repo.get_file_record(db, file_id)
    if not rec:
        raise HTTPException(404, "Файл не найден")
    if rec.user_id != u["user_id"] and u.get("role") != "admin":
        raise HTTPException(403, "Нет доступа к файлу")
    res = storage.read_record_bytes(rec)
    if not res:
        raise HTTPException(404, "Файл не найден")
    data, name = res
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": filecheck.content_disposition(name)})
