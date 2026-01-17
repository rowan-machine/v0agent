# src/app/api/chat.py

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from ..chat.models import (
    create_conversation,
    get_recent_messages,
)
from ..chat.turn import run_chat_turn

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/chat/new")
def new_chat(request: Request):
    cid = create_conversation()
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "conversation_id": cid,
            "messages": [],
            "answer": None,
        },
    )


@router.post("/chat/{conversation_id}")
def chat_turn(
    request: Request,
    conversation_id: int,
    message: str = Form(...),
):
    answer = run_chat_turn(conversation_id, message)
    messages = get_recent_messages(conversation_id, limit=20)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "conversation_id": conversation_id,
            "messages": messages,
            "answer": answer,
        },
    )

