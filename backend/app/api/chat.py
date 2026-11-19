"""POST /chat: grounded flood Q&A in Urdu, English or Roman Urdu."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.contracts import Language

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=64)
    language: Language | None = None  # override the detected language
    tehsil_id: str | None = None  # e.g. the user's subscribed tehsil
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    as_of: dt.datetime | None = None  # replay: answer as if it were this moment


class Citation(BaseModel):
    ref: str
    label: str
    kind: str


class ChatAction(BaseModel):
    text: str
    refs: list[str]


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    actions: list[ChatAction]
    language: Language
    intent: str
    tehsil_id: str | None
    place: str | None
    level: str | None  # from the risk model, never from the LLM
    citations: list[Citation]
    checked: bool  # passed the grounding checks
    fallback: bool  # template answer used because the LLM output failed the checks


def get_agent():  # separate function so tests can override it
    from backend.app.agent.service import get_agent as _get

    return _get()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    from backend.app.llm import LLMError

    agent = get_agent()
    try:
        result = agent.ask(request.message, request.session_id,
                           language=request.language.value if request.language else None,
                           tehsil_id=request.tehsil_id, lat=request.lat, lon=request.lon, as_of=request.as_of)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail="The assistant is busy. Please try again shortly.") from exc
    return ChatResponse(**{k: v for k, v in result.items() if k in ChatResponse.model_fields})
