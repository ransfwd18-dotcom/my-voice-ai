import os
import re
import hmac
import hashlib
import secrets
import sqlite3

from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env.local")

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "accounts.db")))

FREE_DAILY_LIMIT = 10
PASSWORD_ITERATIONS = 310_000

router = APIRouter()


@contextmanager
def get_db():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        db = sqlite3.connect(DB_PATH, timeout=15)
        db.row_factory = sqlite3.Row

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def execute(db, sql, params=()):
    if DATABASE_URL:
        sql = sql.replace("?", "%s")
    return db.execute(sql, params)


def initialize_database():
    with get_db() as db:
        if DATABASE_URL:
            db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    usage_date TEXT NOT NULL,
                    generations INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date)
                )
            """)
        else:
            db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    user_id INTEGER NOT NULL,
                    usage_date TEXT NOT NULL,
                    generations INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)


initialize_database()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"{PASSWORD_ITERATIONS}${salt.hex()}${password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        iterations, salt_hex, hash_hex = stored_hash.split("$")
        calculated = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(calculated.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


@router.post("/auth/register")
async def register(data: RegisterRequest):
    email = data.email.strip().lower()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Enter a valid email address.")

    password_hash = hash_password(data.password)

    try:
        with get_db() as db:
            if DATABASE_URL:
                row = execute(
                    db,
                    """INSERT INTO users (email, password_hash, created_at)
                       VALUES (?, ?, ?) RETURNING id""",
                    (email, password_hash, datetime.now(timezone.utc).isoformat())
                ).fetchone()
                user_id = row["id"]
            else:
                cursor = execute(
                    db,
                    """INSERT INTO users (email, password_hash, created_at)
                       VALUES (?, ?, ?)""",
                    (email, password_hash, datetime.now(timezone.utc).isoformat())
                )
                user_id = cursor.lastrowid

        return {
            "success": True,
            "message": "Account created successfully.",
            "user_id": user_id
        }

    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists.")
    except Exception as exc:
        if DATABASE_URL:
            import psycopg
            if isinstance(exc, psycopg.errors.UniqueViolation):
                raise HTTPException(409, "An account with this email already exists.")
        raise


@router.post("/auth/login")
async def login(data: LoginRequest, request: Request):
    email = data.email.strip().lower()

    with get_db() as db:
        user = execute(
            db, "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")

    request.session.clear()
    request.session["user_id"] = user["id"]

    return {
        "success": True,
        "message": "Login successful.",
        "user": {"id": user["id"], "email": user["email"]}
    }


async def require_user(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(401, "Please log in to continue.")

    with get_db() as db:
        user = execute(
            db, "SELECT id, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    if not user:
        request.session.clear()
        raise HTTPException(401, "Your session is no longer valid.")

    return dict(user)


@router.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"success": True, "message": "Logged out successfully."}


@router.get("/auth/me")
async def account_information(user: dict = Depends(require_user)):
    return {"authenticated": True, "user": user}


def get_daily_usage(user_id: int):
    today = datetime.now(timezone.utc).date().isoformat()

    with get_db() as db:
        row = execute(
            db,
            """SELECT generations FROM usage
               WHERE user_id = ? AND usage_date = ?""",
            (user_id, today)
        ).fetchone()

    used = row["generations"] if row else 0

    return {
        "used": used,
        "limit": FREE_DAILY_LIMIT,
        "remaining": max(0, FREE_DAILY_LIMIT - used),
        "date": today
    }


def consume_generation(user_id: int):
    today = datetime.now(timezone.utc).date().isoformat()

    with get_db() as db:
        if DATABASE_URL:
            row = execute(
                db,
                """
                INSERT INTO usage (user_id, usage_date, generations)
                VALUES (?, ?, 1)
                ON CONFLICT (user_id, usage_date)
                DO UPDATE SET generations = usage.generations + 1
                WHERE usage.generations < ?
                RETURNING generations
                """,
                (user_id, today, FREE_DAILY_LIMIT)
            ).fetchone()

            if row is None:
                raise HTTPException(
                    429, "You have reached your daily free generation limit."
                )

        else:
            db.execute("BEGIN IMMEDIATE")

            execute(
                db,
                """INSERT OR IGNORE INTO usage
                   (user_id, usage_date, generations) VALUES (?, ?, 0)""",
                (user_id, today)
            )

            row = execute(
                db,
                """SELECT generations FROM usage
                   WHERE user_id = ? AND usage_date = ?""",
                (user_id, today)
            ).fetchone()

            if row["generations"] >= FREE_DAILY_LIMIT:
                raise HTTPException(
                    429, "You have reached your daily free generation limit."
                )

            execute(
                db,
                """UPDATE usage SET generations = generations + 1
                   WHERE user_id = ? AND usage_date = ?""",
                (user_id, today)
            )

    return get_daily_usage(user_id)


@router.get("/auth/usage")
async def account_usage(user: dict = Depends(require_user)):
    return get_daily_usage(user["id"])
