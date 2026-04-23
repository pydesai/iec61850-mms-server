from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/connections")
async def get_connections(request: Request):
    mms = request.app.state.mms_server
    status = mms.get_status()
    count = status.get("connections", 0)
    return {
        "count": count,
        "connections": [
            {"id": i + 1, "label": f"MMS Client {i + 1}"}
            for i in range(count)
        ],
    }
