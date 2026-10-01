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
