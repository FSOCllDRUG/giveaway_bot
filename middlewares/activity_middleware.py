from datetime import datetime
from datetime import timezone
from typing import Dict, Callable, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message

from db.r_engine import redis_conn


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        timestamp = int(datetime.now(timezone.utc).timestamp())
        await redis_conn.hset("user_activity", user_id, timestamp)
        return await handler(event, data)
