"""Provision a local account and assign it to a workspace."""

import argparse
from getpass import getpass
from pathlib import Path
import re
import secrets

from dotenv import load_dotenv
from psycopg.errors import UniqueViolation

from .auth import insert_user, normalize_email, password_hash
from .db import connect


def create_user(email: str, password: str, workspace: str) -> None:
    salt = secrets.token_bytes(16)
    digest = password_hash(password, salt)
    with connect() as connection:
        connection.execute("INSERT INTO workspaces (id) VALUES (%s) ON CONFLICT DO NOTHING", (workspace,))
        insert_user(connection, email, salt, digest, workspace)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("workspace", help="Workspace ID, such as local or finance")
    args = parser.parse_args()
    try:
        email = normalize_email(args.email)
    except ValueError as error:
        parser.error(str(error))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", args.workspace):
        parser.error("Workspace IDs must use lowercase letters, digits, or hyphens.")
    password = getpass("Password: ")
    if not 12 <= len(password) <= 256:
        parser.error("Use a password between 12 and 256 characters.")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match.")

    load_dotenv(Path(__file__).with_name(".env"))
    try:
        create_user(email, password, args.workspace)
    except UniqueViolation:
        parser.exit(1, "An account with that email already exists.\n")
    print(f"Created {email} in workspace {args.workspace}.")


if __name__ == "__main__":
    main()
