"""
Varalokam - Configuration Module
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # ── Server ──────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # ── Redis ───────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── AWS DynamoDB ────────────────────────────────────────
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    DYNAMODB_USERS_TABLE: str = os.getenv("DYNAMODB_USERS_TABLE", "varalokam-users")
    DYNAMODB_LEADERBOARD_TABLE: str = os.getenv(
        "DYNAMODB_LEADERBOARD_TABLE", "varalokam-leaderboard"
    )

    # ── Auth ────────────────────────────────────────────────
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")

    # ── Game Settings ───────────────────────────────────────
    MAX_PLAYERS_PER_ROOM: int = int(os.getenv("MAX_PLAYERS_PER_ROOM", "8"))
    DEFAULT_ROUNDS: int = int(os.getenv("DEFAULT_ROUNDS", "3"))
    DEFAULT_TURN_DURATION: int = int(os.getenv("DEFAULT_TURN_DURATION", "80"))
    WORD_CHOICE_COUNT: int = int(os.getenv("WORD_CHOICE_COUNT", "3"))
    WORD_CHOICE_TIMEOUT: int = int(os.getenv("WORD_CHOICE_TIMEOUT", "15"))
    HINT_INTERVAL: int = int(os.getenv("HINT_INTERVAL", "20"))


config = Config()
