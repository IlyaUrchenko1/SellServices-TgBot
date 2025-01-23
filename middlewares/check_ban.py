from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from utils.database import Database
from datetime import datetime, timedelta

db = Database()

class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, (Message, CallbackQuery)):
            telegram_id = str(event.from_user.id)
            
            # Получаем информацию о бане пользователя
            ban_info = db.get_ban_info('user', accused_telegram_id=telegram_id)
            
            if ban_info:
                ban_date = datetime.strptime(ban_info['ban_date'], "%Y-%m-%d %H:%M:%S")
                
                # Проверяем постоянный бан
                if ban_info['is_permanent']:
                    message = (
                        "❌ Вы заблокированы навсегда\n"
                        f"Причина: {ban_info['reason']}\n"
                        "Если вы заблокированы по ошибке, пожалуйста, обратитесь в поддержку"
                    )
                    
                    if isinstance(event, Message):
                        await event.answer(message)
                    else:
                        await event.answer(message, show_alert=True)
                    return
                
                # Проверяем временный бан
                ban_duration = timedelta(hours=ban_info['ban_duration_hours'])
                ban_end_date = ban_date + ban_duration
                remaining_time = ban_end_date - datetime.now()
                
                if remaining_time.total_seconds() > 0:
                    remaining_hours = int(remaining_time.total_seconds() // 3600)
                    remaining_minutes = int((remaining_time.total_seconds() % 3600) // 60)
                    
                    message = (
                        f"❌ Вы заблокированы на {remaining_hours} часов и {remaining_minutes} минут\n"
                        f"Причина: {ban_info['reason']}\n"
                        "Если вы заблокированы по ошибке, пожалуйста, обратитесь в поддержку"
                    )
                    
                    if isinstance(event, Message):
                        await event.answer(message)
                    else:
                        await event.answer(
                            f"❌ Вы заблокированы на {remaining_hours}ч {remaining_minutes}мин. "
                            f"Причина: {ban_info['reason']}", 
                            show_alert=True
                        )
                    return
                else:
                    # Если бан истек, разбаниваем пользователя
                    db.unban_entity('user', accused_telegram_id=telegram_id)
                    
        return await handler(event, data)