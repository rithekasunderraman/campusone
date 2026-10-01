from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    username: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    # Which intent answered, and whether the text came straight from the database,
    # was rephrased by the LLM, was an LLM best-effort answer, or is the help text.
    intent: str = "none"
    source: str = "database"
