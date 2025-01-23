import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from middlewares.antiflood import AntiFloodMiddleware
from middlewares.check_ban import BanCheckMiddleware
from middlewares.private_chat import PrivateChatMiddleware
from middlewares.work_set import WorkSetMiddleware
from handlers import main_handler
from handlers.main_function import support_handler, post_handler, watch_handler, profile_handler
from handlers.admin_function import create_new_type, get_complaints, start_newsletter
from handlers.main_function.functions import service_profile, create_complaints

load_dotenv()

default_setting = DefaultBotProperties(parse_mode='HTML')
bot = Bot(os.getenv("BOT_TOKEN"), default=default_setting)
dp = Dispatcher()

async def main():
    dp.message.middleware(PrivateChatMiddleware())
    dp.message.middleware(BanCheckMiddleware())
    # dp.message.middleware(WorkSetMiddleware())  # Устанавливаем тех. работы в боте
    dp.message.middleware(AntiFloodMiddleware(limit=0.5))  # Антифлуд можно включить по необходимости

    dp.include_router(main_handler.router)
    dp.include_router(support_handler.router)
    dp.include_router(post_handler.router)
    dp.include_router(watch_handler.router)
    dp.include_router(profile_handler.router)


    dp.include_router(create_new_type.router)
    dp.include_router(get_complaints.router)
    dp.include_router(start_newsletter.router)
    
    dp.include_router(service_profile.router)
    dp.include_router(create_complaints.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    try:
        print("Бот стартовал :)")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен :(")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
