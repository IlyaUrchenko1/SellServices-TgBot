from aiogram import BaseMiddleware
from aiogram.types import Message
import time

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit
        self.user_timestamps = {}

    async def __call__(self, handler, event: Message, data):
        current_time = time.time()
        user_id = event.from_user.id

        if user_id in self.user_timestamps:
            last_message_time = self.user_timestamps[user_id]
            if current_time - last_message_time < self.limit:
                await event.answer("Вы отправляете сообщения слишком быстро.")
                return

        self.user_timestamps[user_id] = current_time

        return await handler(event, data)
