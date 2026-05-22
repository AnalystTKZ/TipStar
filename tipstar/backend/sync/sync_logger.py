"""
Writes sync run records to the Supabase sync_logs table.
Imported by all sync modules -- kept separate to avoid circular imports.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_sync_run(
    sync_type: str,
    api_used: str,
    records_updated: int,
    errors: int,
    notes: str = "",
) -> None:
    """Insert one row into sync_logs. Silently swallows errors so it never blocks a sync."""
    try:
        from backend.database.db import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    """INSERT INTO sync_logs (sync_type, api_used, records_updated, errors, notes, created_at)
                    VALUES (:sync_type, :api_used, :records_updated, :errors, :notes, :created_at)"""
                ).bindparams(
                    sync_type=sync_type,
                    api_used=api_used,
                    records_updated=records_updated,
                    errors=errors,
                    notes=notes[:2000] if notes else "",
                    created_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Could not write sync log: %s", exc)
