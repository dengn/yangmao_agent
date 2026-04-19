from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import agent, schemas
from app.db import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatOut)
def chat(payload: schemas.ChatIn, db: Session = Depends(get_db)):
    try:
        result = agent.run_chat(db, payload.message, payload.history)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return result
