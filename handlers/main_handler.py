from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from typing import Optional
from keyboards.main_keyboards import to_home_keyboard
from keyboards.role_keyboards import seller_keyboard, user_keyboard, admin_keyboard

from utils.database import Database
from utils.variables import ADMIN_IDS

router = Router(name='main')
db = Database()

ITEMS_PER_PAGE = 5  

class FilterStates(StatesGroup):
    waiting_for_filter = State()
    waiting_for_field_input = State()

@router.message(CommandStart())
async def start_command(message: Message):
    telegram_id = str(message.from_user.id)
    
    # try:
    #     member = await message.bot.get_chat_member(chat_id=-1002272626379, user_id=message.from_user.id)
    #     if member.status == "left" or member.status == "kicked":
    #         from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
    #         keyboard = InlineKeyboardMarkup(inline_keyboard=[
    #             [InlineKeyboardButton(text="📢 Подписаться на группу", url="https://t.me/+fvSWdUdtzAczZDUy")]
    #         ])
            
    #         await message.answer(
    #             "🔒 <b>Доступ ограничен</b>\n\n"
    #             "Чтобы использовать все возможности бота, необходимо подписаться "
    #             "на нашу официальную группу. Там вы найдете:\n\n"
    #             "• Актуальные новости и обновления\n"
    #             "• Полезные советы и рекомендации\n"
    #             "• Эксклюзивные предложения\n\n"
    #             "👇 Нажмите на кнопку ниже, чтобы подписаться",
    #             reply_markup=keyboard,
    #             parse_mode="HTML"
    #         )
    #         return
    #     elif member.status in ["member", "administrator", "creator"]:
    #         pass
    #     else:
    #         print(f"Неизвестный статус участника: {member.status}")
    #         pass
            
    # except Exception as e:
    #     from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
    #     keyboard = InlineKeyboardMarkup(inline_keyboard=[
    #         [InlineKeyboardButton(text="📢 Подписаться на группу", url="https://t.me/+lMZWa6YQlkMyOWIy")]
    #     ])
        
    #     await message.answer(
    #         "🔒 <b>Доступ ограничен</b>\n\n"
    #         "Для использования бота требуется подписка на нашу группу.\n"
    #         "Пожалуйста, нажмите кнопку ниже 👇",
    #         reply_markup=keyboard,
    #         parse_mode="HTML"
    #     )
    #     print(f"Ошибка при проверке участника группы: {e}")
    #     return

    user = db.get_user(telegram_id=telegram_id)
    
    if not user:
        try:
            db.add_user(telegram_id=telegram_id, username=message.from_user.username, is_seller=True)
            user = db.get_user(telegram_id=telegram_id)
            
        except Exception as e:
            await message.answer(
                "❌ Произошла ошибка при создании вашего профиля. Попробуйте позже.",
                reply_markup=to_home_keyboard()
            )
            print(f"Ошибка в start_command: {e}")
            return

    await show_main_menu(message, user)
    
    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            "🌟 Панель администратора доступна:\n"
            "- Рассылка сообщений\n"
            "- Просмотр жалоб\n"
            "- Управление типами услуг",
            reply_markup=admin_keyboard()
        )

async def show_main_menu(message: Message, user, name: Optional[str] = None) -> None:
    """Показывает главное меню в зависимости от роли пользователя"""
    if not user:
        keyboard = user_keyboard()
    elif db.is_seller(telegram_id=str(user[1])):  # Используем индекс 1 для получения telegram_id из кортежа
        keyboard = seller_keyboard()
    else:
        keyboard = user_keyboard()

    if name:
        welcome_text = f"👋 Здравствуйте, {name}!\n\n"
    else:
        welcome_text = f"👋 Здравствуйте, {message.from_user.first_name}!\n\n"
    
    try:
        await message.answer(welcome_text, reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка отображения меню: {e}")
        await message.answer(
            "❌ Произошла ошибка при отображении меню. Попробуйте еще раз.",
            reply_markup=to_home_keyboard()
        )

@router.callback_query(F.data == "go_to_home")
async def go_to_home(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата в главное меню"""
    await callback.answer()
    await open_home(callback.message, callback.from_user, state, is_callback=True)
    
@router.message(F.text.in_(["Вернуться домой 🏠"]))
async def go_to_home_reply(message: Message, state: FSMContext):
    await open_home(message, message.from_user, state)
    
@router.message(F.text == "🏠 На главную")
async def go_to_home_reply(message: Message, state: FSMContext):
    await open_home(message, message.from_user, state)

async def open_home(message: Message, user, state: FSMContext, is_callback: bool = False):
    try:
        await state.clear()
        
        db_user = db.get_user(telegram_id=str(user.id))
        if not db_user:
            try:
                db.add_user(telegram_id=str(user.id), username=user.username, is_seller=True)
                db_user = db.get_user(telegram_id=str(user.id))
                if not db_user:
                    raise Exception("Не удалось создать пользователя")
            except Exception as e:
                error_text = "❌ Ошибка получения данных пользователя. Попробуйте перезапустить бота командой /start\nНикакие данные не будут потеряны"
                if is_callback:
                    try:
                        await message.edit_text(error_text, reply_markup=to_home_keyboard())
                    except:
                        await message.answer(error_text, reply_markup=to_home_keyboard())
                else:
                    await message.answer(error_text, reply_markup=to_home_keyboard())
                return
            
        if is_callback:
            try:
                await message.edit_text(
                    f"👋 Здравствуйте, {user.first_name}!",
                    reply_markup=seller_keyboard() if db.is_seller(telegram_id=str(db_user[1])) else user_keyboard()
                )
            except:
                await message.answer(
                    f"👋 Здравствуйте, {user.first_name}!",
                    reply_markup=seller_keyboard() if db.is_seller(telegram_id=str(db_user[1])) else user_keyboard()
                )
        else:
            await show_main_menu(message, db_user, name=user.first_name)
        
        if user.id in ADMIN_IDS:
            await message.answer(
                "🌟 Панель администратора доступна:\n"
                "- Рассылка сообщений\n"
                "- Просмотр жалоб\n"
                "- Управление типами услуг",
                reply_markup=admin_keyboard()
            )
            
    except Exception as e:
        print(f"Ошибка в go_to_home: {e}")
        error_text = "❌ Произошла ошибка. Попробуйте еще раз или перезапустите бота командой /start"
        if is_callback:
            try:
                await message.edit_text(error_text, reply_markup=to_home_keyboard())
            except:
                await message.answer(error_text, reply_markup=to_home_keyboard())
        else:
            await message.answer(error_text, reply_markup=to_home_keyboard())

@router.message(F.text == "/get_id")
async def get_id(message: Message):
    """Получение ID чата и пользователя"""
    await message.answer(
        f"🆔 ID чата: {message.chat.id}\n"
        f"👤 ID пользователя: {message.from_user.id}"
    )

