"""Check sign-up and document isolation on a dedicated KnowFlow preview database."""

import argparse
import hashlib
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse

import httpx

from backend import db
from backend.main import INSUFFICIENT_EVIDENCE

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "employee-handbook.pdf"
VECTOR = [1.0, 0.0]
PASSAGE = "Employees receive 20 working days of paid parental leave."


def signup(client: httpx.Client, email: str, password: str) -> str:
    response = client.post("/signup", json={"email": email, "password": password})
    response.raise_for_status()
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    if client.base_url.scheme == "https":
        assert "; secure" in cookie
    session = client.get("/session")
    session.raise_for_status()
    assert session.json() == response.json()
    return session.json()["workspace_id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Preview deployment origin, without /api")
    parser.add_argument("--direct-api", action="store_true", help="Check the FastAPI deployment directly")
    parser.add_argument("--embedding-model", default="text-embedding-3-small",
                        help="Model namespace on the API; defaults to the keyless preview setting")
    args = parser.parse_args()
    if not os.getenv("DATABASE_URL"):
        parser.error("Set DATABASE_URL to the dedicated preview database.")
    origin = urlparse(args.url)
    oidc = os.getenv("VERCEL_OIDC_TOKEN")
    headers = {}
    if oidc and origin.scheme == "https" and (origin.hostname or "").endswith(".vercel.app"):
        headers["x-vercel-trusted-oidc-idp-token"] = oidc
    root = args.url.rstrip("/") + ("" if args.direct_api else "/api")
    nonce = secrets.token_hex(8)
    emails = [f"preview-{nonce}-{suffix}@example.test" for suffix in ("a", "b")]
    password = secrets.token_urlsafe(24)
    pdf = FIXTURE.read_bytes()

    try:
        with (
            httpx.Client(base_url=root, headers=headers, timeout=60) as owner,
            httpx.Client(base_url=root, headers=headers, timeout=60) as visitor,
        ):
            assert visitor.get("/session").status_code == 401
            a = signup(owner, emails[0], password)
            b = signup(visitor, emails[1], password)
            assert a != b

            document_id, created = db.save_document(
                a, FIXTURE.name, hashlib.sha256(pdf).hexdigest(),
                args.embedding_model, [(2, PASSAGE)], [VECTOR],
            )
            assert created
            assert db.search(a, VECTOR, args.embedding_model, 5)[0]["document_id"] == document_id
            assert db.search(b, VECTOR, args.embedding_model, 5) == []

            upload = owner.post("/documents", files={"file": (FIXTURE.name, pdf, "application/pdf")})
            upload.raise_for_status()
            assert upload.status_code == 200
            assert upload.json() == {"document_id": document_id, "created": False}

            query = {"question": "How much paid parental leave is available?", "workspace_id": a}
            search = visitor.post("/search", json=query)
            search.raise_for_status()
            assert search.json()["passages"] == []
            answer = visitor.post("/ask", json=query)
            answer.raise_for_status()
            assert answer.json() == {"answer": INSUFFICIENT_EVIDENCE, "citations": []}

            assert owner.post("/logout").status_code == 204
            assert owner.get("/session").status_code == 401
    finally:
        with db.connect() as connection:
            members = connection.execute(
                "DELETE FROM users WHERE email = ANY(%s) RETURNING workspace_id",
                (emails,),
            ).fetchall()
            workspaces = [member["workspace_id"] for member in members]
            connection.execute("DELETE FROM documents WHERE workspace_id = ANY(%s)", (workspaces,))
            connection.execute("DELETE FROM workspaces WHERE id = ANY(%s)", (workspaces,))

    print("Passed sign-up, session cookies, owner PDF lookup, workspace isolation, and sign-out.")


if __name__ == "__main__":
    main()
