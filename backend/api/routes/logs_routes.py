from typing import Optional
from fastapi import APIRouter, Request, Query

router = APIRouter()


@router.get("/logs")
async def get_logs(
    request: Request,
    level: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    since: Optional[str] = Query(None),
):
    log_buf = request.app.state.log_buffer
    entries = log_buf.get_all(level=level, limit=limit, since=since)
    return {
        "count": len(entries),
        "entries": [e.model_dump() for e in entries],
    }


@router.delete("/logs")
async def clear_logs(request: Request):
    request.app.state.log_buffer.clear()
    return {"success": True}
