from aiogram import BaseMiddleware
from aiogram.types import Message
from utils.variables import ADMIN_IDS
class PrivateChatMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        # Разрешаем админам команды отовсюду
        if event.from_user.id in ADMIN_IDS:
            return await handler(event, data)
            
        # Остальные команды только в приватных чатах
        if event.chat.type != 'private':
            await event.answer("Эта команда доступна только в личных сообщениях.")
            return
            
        return await handler(event, data)