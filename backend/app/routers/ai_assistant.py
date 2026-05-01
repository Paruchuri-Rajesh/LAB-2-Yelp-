from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.ai_assistant import AIChatRequest, AIChatResponse
from app.services.ai_recommender import (
    generate_recommendations_payload,
    stream_recommendations,
)


router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _build_history(payload: AIChatRequest, assistant_text: str, recommendations, parsed_filters, route):
    base = payload.conversation_history or []
    return base + [
        {"role": "user", "content": payload.message, "parsed_filters": parsed_filters or {}},
        {"role": "assistant", "content": assistant_text, "recommendations": recommendations, "route": route or {}},
    ]


@router.post("/chat", response_model=AIChatResponse)
async def chat_endpoint(payload: AIChatRequest) -> AIChatResponse:
    if not (payload.message or "").strip():
        greeting = "Hi there! Ask me for restaurant ideas like 'cheap sushi' or 'Italian places'."
        return AIChatResponse(
            assistant_text=greeting,
            recommendations=[],
            conversation_history=(payload.conversation_history or []) + [{"role": "assistant", "content": greeting}],
            route=None,
            used_current_context=False,
        )

    result = await generate_recommendations_payload(
        payload.message,
        payload.conversation_history,
        client_location=payload.client_location.model_dump() if payload.client_location else None,
    )
    history = _build_history(payload, result["assistant_text"], result["recommendations"], result.get("parsed_filters"), result.get("route"))
    return AIChatResponse(
        assistant_text=result["assistant_text"],
        recommendations=result["recommendations"],
        conversation_history=history,
        route=result.get("route"),
        used_current_context=result.get("used_current_context"),
    )


@router.post("/chat/json", response_model=AIChatResponse)
async def chat_json_endpoint(payload: AIChatRequest) -> AIChatResponse:
    return await chat_endpoint(payload)


@router.post("/chat/stream")
async def chat_stream_endpoint(payload: AIChatRequest) -> StreamingResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        yield _sse({"type": "start", "message": "stream_start"})

        if not (payload.message or "").strip():
            greeting = "Hi there! Ask me for restaurant ideas like 'cheap sushi' or 'Italian places'."
            history = (payload.conversation_history or []) + [{"role": "assistant", "content": greeting}]
            yield _sse({"type": "assistant_chunk", "text": greeting})
            yield _sse({"type": "done", "conversation_history": history})
            return

        result = await generate_recommendations_payload(
            payload.message,
            payload.conversation_history,
            client_location=payload.client_location.model_dump() if payload.client_location else None,
        )
        try:
            async for event_type, value in stream_recommendations(
                payload.message,
                payload.conversation_history,
                client_location=payload.client_location.model_dump() if payload.client_location else None,
            ):
                if event_type == "assistant_chunk":
                    yield _sse({"type": "assistant_chunk", "text": value})
                elif event_type == "recommendation":
                    yield _sse({"type": "recommendation", "item": value})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "assistant_chunk", "text": f"Sorry, something went wrong: {exc}"})

        history = _build_history(
            payload,
            result["assistant_text"],
            result["recommendations"],
            result.get("parsed_filters"),
            result.get("route"),
        )
        yield _sse({
            "type": "done",
            "conversation_history": history,
            "route": result.get("route"),
            "used_current_context": result.get("used_current_context"),
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")
