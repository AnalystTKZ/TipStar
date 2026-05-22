from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import (
    get_db,
    get_posts_by_status,
    get_post_history,
    update_post_status,
    delete_post,
)

router = APIRouter(prefix="/posts", tags=["posts"])


class EditBody(BaseModel):
    content: str


@router.get("/pending")
async def pending_posts(db: AsyncSession = Depends(get_db)):
    return await get_posts_by_status(db, "pending")


@router.get("/approved")
async def approved_posts(db: AsyncSession = Depends(get_db)):
    return await get_posts_by_status(db, "approved")


@router.get("/history")
async def post_history(db: AsyncSession = Depends(get_db)):
    return await get_post_history(db)


@router.patch("/{post_id}/approve")
async def approve_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await update_post_status(db, post_id, "approved")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return result


@router.patch("/{post_id}/reject")
async def reject_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await update_post_status(db, post_id, "rejected")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return result


@router.patch("/{post_id}/edit")
async def edit_and_approve(post_id: str, body: EditBody, db: AsyncSession = Depends(get_db)):
    """Edit post content and approve in one step."""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    result = await update_post_status(db, post_id, "approved", content=body.content)
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return result


@router.delete("/{post_id}")
async def remove_post(post_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_post(db, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return {"deleted": post_id}
