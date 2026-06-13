import json
import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    AskRequest,
    MessageResponse,
    SessionCreate,
    SessionResponse,
    SessionUpdateTitle,
    SessionWithMessages,
)
from app.core.auth import get_current_user
from app.db.mongodb import get_db

logger = logging.getLogger("ttapi")
router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_session(doc: dict) -> SessionResponse:
    return SessionResponse(
        id=str(doc["_id"]),
        title=doc["title"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        message_count=doc.get("message_count", 0),
    )


def _to_message(doc: dict) -> MessageResponse:
    return MessageResponse(
        id=str(doc["_id"]),
        role=doc["role"],
        content=doc["content"],
        sources=doc.get("sources"),
        grounded=doc.get("grounded"),
        latency_ms=doc.get("latency_ms"),
        model=doc.get("model"),
        created_at=doc["created_at"],
    )


def _oid(session_id: str) -> ObjectId:
    try:
        return ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("", response_model=list[SessionResponse])
async def list_sessions(current_user: str = Depends(get_current_user)) -> list[SessionResponse]:
    db = get_db()
    docs = await db.sessions.find({"user": current_user}).sort("updated_at", -1).to_list(100)
    return [_to_session(d) for d in docs]


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    current_user: str = Depends(get_current_user),
) -> SessionResponse:
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "user": current_user,
        "title": body.title,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    result = await db.sessions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_session(doc)


@router.get("/{session_id}", response_model=SessionWithMessages)
async def get_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
) -> SessionWithMessages:
    db = get_db()
    session_doc = await db.sessions.find_one({"_id": _oid(session_id), "user": current_user})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_docs = await db.messages.find({"session_id": session_id}).sort("created_at", 1).to_list(1000)
    return SessionWithMessages(
        id=str(session_doc["_id"]),
        title=session_doc["title"],
        created_at=session_doc["created_at"],
        updated_at=session_doc["updated_at"],
        messages=[_to_message(m) for m in msg_docs],
    )


@router.patch("/{session_id}", response_model=SessionResponse)
async def rename_session(
    session_id: str,
    body: SessionUpdateTitle,
    current_user: str = Depends(get_current_user),
) -> SessionResponse:
    db = get_db()
    now = datetime.now(timezone.utc)
    updated = await db.sessions.find_one_and_update(
        {"_id": _oid(session_id), "user": current_user},
        {"$set": {"title": body.title, "updated_at": now}},
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_session(updated)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
) -> None:
    db = get_db()
    result = await db.sessions.delete_one({"_id": _oid(session_id), "user": current_user})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.messages.delete_many({"session_id": session_id})


@router.post("/{session_id}/ask")
async def ask_stream(
    session_id: str,
    request: Request,
    body: AskRequest,
    current_user: str = Depends(get_current_user),
) -> StreamingResponse:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline is not initialised.")

    db = get_db()
    session_doc = await db.sessions.find_one({"_id": _oid(session_id), "user": current_user})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch recent conversation history before persisting the new user message
    # (last 10 messages = up to 5 back-and-forth exchanges for LLM context)
    history_docs = await db.messages.find(
        {"session_id": session_id},
        {"role": 1, "content": 1},
    ).sort("created_at", -1).limit(10).to_list(10)
    history = [
        {"role": d["role"], "content": d["content"]}
        for d in reversed(history_docs)
    ]

    # Persist user message
    now = datetime.now(timezone.utc)
    await db.messages.insert_one({
        "session_id": session_id,
        "role": "user",
        "content": body.question,
        "created_at": now,
    })

    # Auto-title the session from the first question
    is_first = session_doc.get("message_count", 0) == 0
    if is_first:
        title = body.question[:60] + ("…" if len(body.question) > 60 else "")
        await db.sessions.update_one(
            {"_id": _oid(session_id)},
            {"$set": {"title": title, "updated_at": now}, "$inc": {"message_count": 1}},
        )
    else:
        await db.sessions.update_one(
            {"_id": _oid(session_id)},
            {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
        )

    async def event_stream():
        tokens: list[str] = []
        meta: dict = {}
        try:
            async for event in pipeline.astream(body.question, history=history):
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] == "token":
                    tokens.append(event["content"])
                elif event["type"] == "metadata":
                    meta = event
        except Exception:
            logger.exception("Streaming error for session %s", session_id)
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Streaming failed'})}\n\n"
            return

        # Persist completed assistant message
        await db.messages.insert_one({
            "session_id": session_id,
            "role": "assistant",
            "content": "".join(tokens),
            "sources": meta.get("sources", []),
            "grounded": meta.get("grounded", False),
            "latency_ms": meta.get("latency_ms"),
            "model": meta.get("model"),
            "created_at": datetime.now(timezone.utc),
        })
        await db.sessions.update_one(
            {"_id": _oid(session_id)},
            {"$set": {"updated_at": datetime.now(timezone.utc)}, "$inc": {"message_count": 1}},
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
