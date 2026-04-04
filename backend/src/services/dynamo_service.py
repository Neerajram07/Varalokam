"""
DynamoDB Service — handles persistent data storage for user profiles and leaderboards.

This is optional for MVP — the game works without it using anonymous play.
Enable when you want persistent user accounts and global leaderboards.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from ..config import config

logger = logging.getLogger(__name__)


class DynamoService:
    """Handles DynamoDB operations for persistent game data."""

    def __init__(self):
        self._client = None
        self._users_table = None
        self._leaderboard_table = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize DynamoDB client and table references."""
        if self._initialized:
            return

        try:
            kwargs = {"region_name": config.AWS_REGION}
            if config.AWS_ACCESS_KEY_ID:
                kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
                kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY

            dynamodb = boto3.resource("dynamodb", **kwargs)
            self._users_table = dynamodb.Table(config.DYNAMODB_USERS_TABLE)
            self._leaderboard_table = dynamodb.Table(config.DYNAMODB_LEADERBOARD_TABLE)
            self._initialized = True
            logger.info("DynamoDB service initialized")
        except Exception as e:
            logger.warning(f"DynamoDB initialization failed (non-critical): {e}")
            logger.warning("Running without persistent storage — anonymous play only")

    # ── User Operations ───────────────────────────────────

    async def create_user(self, user_id: str, username: str, email: str = "") -> Optional[dict]:
        """Create a new user profile."""
        if not self._initialized:
            return None

        try:
            item = {
                "userId": user_id,
                "username": username,
                "email": email,
                "avatarUrl": "",
                "totalGames": 0,
                "totalWins": 0,
                "totalScore": 0,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            self._users_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(userId)",
            )
            logger.info(f"Created user: {username} ({user_id})")
            return item
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"User {user_id} already exists")
            else:
                logger.error(f"Error creating user: {e}")
            return None

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get a user profile by ID."""
        if not self._initialized:
            return None

        try:
            response = self._users_table.get_item(Key={"userId": user_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Error getting user: {e}")
            return None

    async def update_user_stats(
        self, user_id: str, score_earned: int, won: bool = False
    ) -> None:
        """Update user stats after a game."""
        if not self._initialized:
            return

        try:
            update_expr = "SET totalGames = totalGames + :one, totalScore = totalScore + :score"
            expr_values = {":one": 1, ":score": score_earned}

            if won:
                update_expr += ", totalWins = totalWins + :one"

            self._users_table.update_item(
                Key={"userId": user_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            logger.error(f"Error updating user stats: {e}")

    # ── Leaderboard Operations ────────────────────────────

    async def update_leaderboard(
        self, user_id: str, username: str, score: int, timeframe: str = "alltime"
    ) -> None:
        """Update or insert a leaderboard entry."""
        if not self._initialized:
            return

        try:
            self._leaderboard_table.put_item(
                Item={
                    "timeframe": timeframe,
                    "score": score,
                    "userId": user_id,
                    "username": username,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
        except ClientError as e:
            logger.error(f"Error updating leaderboard: {e}")

    async def get_leaderboard(
        self, timeframe: str = "alltime", limit: int = 20
    ) -> list[dict]:
        """Get top players from the leaderboard."""
        if not self._initialized:
            return []

        try:
            response = self._leaderboard_table.query(
                KeyConditionExpression="timeframe = :tf",
                ExpressionAttributeValues={":tf": timeframe},
                ScanIndexForward=False,  # Descending order
                Limit=limit,
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []


# Singleton instance
dynamo_service = DynamoService()
