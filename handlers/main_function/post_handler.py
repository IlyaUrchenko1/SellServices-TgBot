from aiogram import Router, F
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
from utils.database import Database
from keyboards.role_keyboards import seller_keyboard
from keyboards.main_keyboards import to_home_keyboard
from urllib.parse import quote, unquote
from typing import Dict, Any, Optional
import asyncio
from utils.variables import ADMIN_IDS

router = Router(name='post_handler')
db = Database()

ITEMS_PER_PAGE = 8

class ServiceStates(StatesGroup):
    selecting_type = State()
    filling_form = State()
    waiting_for_photo = State()

def create_pagination_keyboard(total_items: int, current_page: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру пагинации"""
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    keyboard = InlineKeyboardBuilder()
    
    row_buttons = []
    
    if current_page > 1:
        row_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{current_page-1}"))
    
    if current_page < total_pages:
        row_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{current_page+1}"))
    
    if row_buttons:
        keyboard.row(*row_buttons)
        
    keyboard.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="go_to_home"))
    
    return keyboard.as_markup()

def build_service_types_keyboard(page: int = 1) -> Optional[InlineKeyboardMarkup]:
    """Создает клавиатуру типов услуг с пагинацией"""
    service_types = db.get_service_types_by_creation_date()
    if not service_types:
        return None
        
    keyboard = InlineKeyboardBuilder()
    
    start_idx = (page - 1) * ITEMS_PER_PAGE
    current_page_types = service_types[start_idx:start_idx + ITEMS_PER_PAGE]
    
    for i in range(0, len(current_page_types), 2):
        row_buttons = []
        for service_type in current_page_types[i:i+2]:
            row_buttons.append(InlineKeyboardButton(
                text=service_type["header"],
                callback_data=f"service_type:{service_type['id']}"
            ))
        keyboard.row(*row_buttons)
    
    pagination = create_pagination_keyboard(len(service_types), page)
    keyboard.attach(InlineKeyboardBuilder.from_markup(pagination))
    
    return keyboard.as_markup()

def create_webapp_form(service_type_id: int, need_enter_phone: Optional[bool] = True) -> Optional[ReplyKeyboardMarkup]:
    """Создает форму веб-приложения для услуги с дополнительными полями"""
    try:    
        service_type = db.get_service_type(service_type_id)
        if not service_type:    
            return None
        
        additional_fields = db.get_service_type_fields(service_type_id)

        # Формируем базовый URL
        base_url = "https://spontaneous-kashata-919d92.netlify.app/create"
        params = [
            f"price=Введите+цену",
            f"header={service_type['header'].replace(' ', '+')}"
        ]

        # Добавляем дополнительные поля в URL
        for field in additional_fields:
            if field['field_type'] in ['select', 'multiselect']:
                # Форматируем строку для select/multiselect полей
                field_value = f"{field['name_for_user']}+|+{'+'.join(field['item_for_select'].split(','))}"
                params.append(f"{field['name']}={field_value.replace(' ', '+')}")
            else:
                # Для других типов полей просто добавляем имя поля
                params.append(f"{field['name']}={field['name_for_user'].replace(' ', '+')}")

        # Собираем полный URL
        full_url = f"{base_url}?{'&'.join(params)}"
        print(full_url)

        keyboard = ReplyKeyboardBuilder()
        keyboard.row(KeyboardButton(text="📝 Заполнить форму", web_app=WebAppInfo(url=full_url)))
        keyboard.row(KeyboardButton(text="Вернуться домой 🏠"))

        return keyboard.as_markup(resize_keyboard=True, one_time_keyboard=False, is_persistent=True,
                                  input_field_placeholder="Нажмите кнопку для заполнения формы")
    except Exception:
        return None

@router.message(F.text.in_(["📈 Выставить свою услугу", "/add_service"]))
async def start_post_service(message: Message, state: FSMContext):
    """Начало публикации услуги"""

    user = db.get_user(telegram_id=str(message.from_user.id))
    if not user or not user[4]:
        await message.answer(
            "❌ Для публикации услуг необходимо быть продавцом",
            reply_markup=to_home_keyboard()
        )
        return

    keyboard = build_service_types_keyboard()
    if not keyboard:
        await message.answer(
            "❌ В данный момент нет доступных категорий услуг",
            reply_markup=to_home_keyboard()
        )
        return

    await state.set_state(ServiceStates.selecting_type)
    await message.answer(
        "📋 Выберите категорию услуги:\n"
        "❗️ Выбор категории влияет на видимость вашей услуги для клиентов",
        reply_markup=keyboard
    )

@router.callback_query(ServiceStates.selecting_type, lambda c: c.data.startswith('service_type:'))
async def handle_service_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа услуги"""
    try:
        service_type_id = int(callback.data.split(':')[1])
        await state.update_data(service_type_id=service_type_id)
        
        user = db.get_user(telegram_id=str(callback.from_user.id))
        keyboard = create_webapp_form(service_type_id, need_enter_phone=not bool(user[3]))
        
        if keyboard:
            await callback.message.delete()
            await callback.message.answer(
                "🖥 Нажмите «Заполнить форму» для создания объявления",
                reply_markup=keyboard
            )
            await state.set_state(ServiceStates.filling_form)
        else:
            await callback.message.edit_text(
                "❌ Ошибка получения формы",
                reply_markup=build_service_types_keyboard()
            )
    except Exception as e:
        print(f"Ошибка выбора типа услуги: {e}")
        await callback.message.edit_text(
            "❌ Ошибка выбора категории",
            reply_markup=build_service_types_keyboard()
        )
    finally:
        await callback.answer()

@router.callback_query(ServiceStates.selecting_type, F.data.startswith('page_'))
async def handle_pagination(callback: CallbackQuery):
    """Обработка пагинации"""
    try:
        page = int(callback.data.split('_')[1])
        keyboard = build_service_types_keyboard(page)
        if keyboard:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        else:
            await callback.message.edit_text(
                "❌ Ошибка загрузки категорий",
                reply_markup=build_service_types_keyboard()
            )
    except Exception as e:
        print(f"Ошибка пагинации: {e}")
        await callback.answer("❌ Ошибка пагинации")
    await callback.answer()

@router.message(ServiceStates.filling_form, lambda message: message.web_app_data and message.web_app_data.button_text == "📝 Заполнить форму")
async def process_create_webapp_data(message: Message, state: FSMContext):
    """Обработка данных формы для создания услуги"""
    print(message.web_app_data.data)
    try:
        form_data = json.loads(message.web_app_data.data)

        # Получаем пользователя и его телефон
        user = db.get_user(telegram_id=str(message.from_user.id))
        if not user[3] and not form_data.get('number_phone'):
            raise ValueError("Не указан номер телефона")
            
        form_data['number_phone'] = form_data.get('number_phone') or user[3]
        
        # Сохраняем данные в состояние
        await state.update_data(form_data=form_data)
        await state.set_state(ServiceStates.waiting_for_photo)
        
        await message.answer(
            "📸 <b>Добавьте фото вашей услуги</b>\n\n"
            "• Нажмите на значок 📎 (скрепка) внизу, около поля ввода текста\n"
            "• Выберите 'Фото' или 'Галерея'\n" 
            "• Отправьте до 10 качественных фотографий\n",
            parse_mode="HTML"
        )
    except json.JSONDecodeError:
        await message.answer(
            "❌ Ошибка обработки данных формы",
            reply_markup=to_home_keyboard()
        )
        await state.clear()
    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=to_home_keyboard()
        )
        await state.clear()
    except Exception as e:
        print(f"Ошибка обработки формы: {e}")
        await message.answer(
            "❌ Произошла неизвестная ошибка",
            reply_markup=to_home_keyboard()
        )
        await state.clear()

@router.message(ServiceStates.waiting_for_photo, F.media_group_id)
async def process_service_photo_album(message: Message, state: FSMContext):
    """Обработка альбома фотографий услуги"""
    try:
        media_group_id = message.media_group_id
        current_data = await state.get_data()
        
        if current_data.get('media_group_id') == media_group_id:
            photo_ids = current_data.get('photo_ids', [])
        else:
            photo_ids = []
            await state.update_data(media_group_id=media_group_id)
            
        if message.photo:
            photo_ids.append(message.photo[-1].file_id)
            await state.update_data(photo_ids=photo_ids)
            
            # Показываем прогресс загрузки
            await message.answer(f"✅ Фото {len(photo_ids)}/10 загружено")
            
        await asyncio.sleep(0.5)
        
        if len(photo_ids) >= 10:
            await message.answer("📸 Достигнут максимум фотографий (10 шт)")
            await process_service_data(message, state)
        elif len(photo_ids) >= 1:
            await asyncio.sleep(1)
            final_data = await state.get_data()
            if len(final_data.get('photo_ids', [])) == len(photo_ids):
                await process_service_data(message, state)

    except Exception as e:
        print(f"Ошибка обработки альбома: {e}")
        await message.answer(
            "❌ Не удалось загрузить фотографии\n"
            "Попробуйте загрузить по одной",
            reply_markup=to_home_keyboard()
        )
        await state.clear()

@router.message(ServiceStates.waiting_for_photo, F.photo)
async def process_service_photo(message: Message, state: FSMContext):
    """Обработка одиночного фото услуги"""
    try:
        if not message.media_group_id:
            await state.update_data(photo_ids=[message.photo[-1].file_id])
            await message.answer("✅ Фото успешно загружено!")
            await process_service_data(message, state)
            
    except Exception as e:
        print(f"Ошибка обработки фото: {e}")
        await message.answer(
            "❌ Не удалось загрузить фотографию\n"
            "Попробуйте еще раз или выберите другое фото",
            reply_markup=to_home_keyboard()
        )
        await state.clear()

async def process_service_data(message: Message, state: FSMContext):
    """Обработка данных услуги и сохранение в БД"""
    try:
        data = await state.get_data()
        form_data = data.get('form_data')
        service_type_id = data.get('service_type_id')
        photo_ids = data.get('photo_ids', [])

        if not all([form_data, service_type_id, photo_ids]):
            raise ValueError("Отсутствуют необходимые данные")

        service_type = db.get_service_type(service_type_id)
        if not service_type:
            raise ValueError("Неверный тип услуги")

        user = db.get_user(telegram_id=str(message.from_user.id))
        if not user:
            raise ValueError("Пользователь не найден")

        # Проверяем, не заблокирован ли пользователь
        ban_info = db.get_ban_info('user', accused_telegram_id=str(message.from_user.id))
        if ban_info:
            raise ValueError("Вы заблокированы и не можете создавать услуги")

        # Проверяем обязательные поля формы
        required_fields = ['city', 'district', 'street', 'price']
        missing_fields = [f for f in required_fields if not form_data.get(f)]
        if missing_fields:
            raise ValueError(f"Не заполнены обязательные поля: {', '.join(missing_fields)}")


        price = form_data.get('price', 0)

        # Формируем данные услуги
        service_data = {
            "user_id": user[1],
            "service_type_id": service_type_id,
            "title": service_type["header"],
            "photo_id": ','.join(photo_ids),
            "city": form_data['city'].strip(),
            "district": form_data['district'].strip(),
            "street": form_data['street'].strip(),
            "house": form_data.get('house', 'Не указано').strip(),
            "number_phone": form_data.get('number_phone', user[3] or '').strip(),
            "price": price,
            "custom_fields": {
                k: v.strip() if isinstance(v, str) else v
                for k, v in form_data.items()
                if k not in ['city', 'district', 'street', 'house', 'number_phone', 'price']
                and v is not None
            }
        }

        service_id = db.add_service(**service_data)
        if not service_id:
            raise Exception("Ошибка при создании услуги")

        await state.clear()
        await message.answer(
            "✅ Поздравляем! Ваша услуга успешно создана!\n"
            "Теперь она доступна для поиска и просмотра другим пользователям",
            reply_markup=seller_keyboard()
        )

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=to_home_keyboard()
        )
        await state.clear()

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        await message.answer(
            "❌ К сожалению, произошла ошибка при публикации услуги\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку",
            reply_markup=to_home_keyboard()
        )
        await state.clear()
