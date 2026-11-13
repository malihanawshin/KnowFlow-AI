"""Local sign-in with opaque, revocable database sessions."""

import hashlib
import hmac
import os
import re
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .db import connect

COOKIE_NAME = "knowflow_session"
SESSION_SECONDS = 8 * 60 * 60
router = APIRouter()


class Credentials(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    return email


class SignupCredentials(Credentials):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class Member(BaseModel):
    email: str
    workspace_id: str


class AuthenticatedMember(Member):
    user_id: int


def password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=2**15, r=8, p=3, maxmem=64 * 1024 * 1024,
    )


def insert_user(connection, email: str, salt: bytes, digest: bytes, workspace: str) -> int:
    return connection.execute(
        """
        INSERT INTO users (email, password_salt, password_hash, workspace_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (email, salt, digest, workspace),
    ).fetchone()["id"]


def session_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


SessionCookie = Annotated[str | None, Cookie(alias=COOKIE_NAME, max_length=128)]


def current_member(token: SessionCookie = None) -> AuthenticatedMember:
    if token:
        with connect() as connection:
            member = connection.execute(
                """
                SELECT u.id AS user_id, u.email, u.workspace_id
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > now()
                """,
                (session_hash(token),),
            ).fetchone()
        if member:
            return AuthenticatedMember(**member)
    raise HTTPException(401, "Sign in to access your workspace.")


ActiveMember = Annotated[AuthenticatedMember, Depends(current_member)]


def cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "strict",
        "secure": os.getenv("KNOWFLOW_SECURE_COOKIE") == "1",
        "path": "/",
    }


def create_session(connection, user_id: int, previous_token: str | None) -> str:
    if previous_token:
        connection.execute("DELETE FROM sessions WHERE token_hash = %s", (session_hash(previous_token),))
    connection.execute("DELETE FROM sessions WHERE user_id = %s AND expires_at <= now()", (user_id,))
    token = secrets.token_urlsafe(32)
    connection.execute(
        """
        INSERT INTO sessions (token_hash, user_id, expires_at)
        VALUES (%s, %s, now() + %s * interval '1 second')
        """,
        (session_hash(token), user_id, SESSION_SECONDS),
    )
    return token


@router.post("/signup", status_code=201)
def signup(credentials: SignupCredentials, response: Response, token: SessionCookie = None) -> Member:
    workspace = f"personal-{secrets.token_hex(16)}"
    salt = secrets.token_bytes(16)
    digest = password_hash(credentials.password, salt)
    try:
        with connect() as connection:
            connection.execute("INSERT INTO workspaces (id) VALUES (%s)", (workspace,))
            user_id = insert_user(connection, credentials.email, salt, digest, workspace)
            new_token = create_session(connection, user_id, token)
    except UniqueViolation as error:
        if error.diag.constraint_name != "users_email_key":
            raise
        raise HTTPException(409, "An account with this email already exists. Sign in instead.") from error

    response.set_cookie(COOKIE_NAME, new_token, max_age=SESSION_SECONDS, **cookie_options())
    return Member(email=credentials.email, workspace_id=workspace)


@router.post("/login")
def login(credentials: Credentials, response: Response, token: SessionCookie = None) -> Member:
    with connect() as connection:
        user = connection.execute(
            "SELECT id, email, workspace_id, password_salt, password_hash FROM users WHERE email = %s",
            (credentials.email.strip().casefold(),),
        ).fetchone()
        salt = user["password_salt"] if user else bytes(16)
        candidate = password_hash(credentials.password, salt)
        expected = user["password_hash"] if user else bytes(64)
        if not hmac.compare_digest(candidate, expected) or user is None:
            raise HTTPException(401, "Invalid email or password.")

        new_token = create_session(connection, user["id"], token)

    response.set_cookie(COOKIE_NAME, new_token, max_age=SESSION_SECONDS, **cookie_options())
    response.headers["Cache-Control"] = "no-store"
    return Member(email=user["email"], workspace_id=user["workspace_id"])


@router.get("/session")
def session(member: ActiveMember, response: Response) -> Member:
    response.headers["Cache-Control"] = "no-store"
    return Member(email=member.email, workspace_id=member.workspace_id)


@router.post("/logout", status_code=204)
def logout(response: Response, token: SessionCookie = None) -> None:
    if token:
        with connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = %s", (session_hash(token),))
    response.delete_cookie(COOKIE_NAME, **cookie_options())
    response.headers["Cache-Control"] = "no-store"
