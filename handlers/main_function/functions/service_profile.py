from aiogram import Router, F, types
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, Message, InputMediaPhoto
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.database import Database
from urllib.parse import quote
import json
from typing import List, Tuple, Dict, Any, Optional
from handlers.main_function.post_handler import to_home_keyboard


router = Router(name='service_profile')
db = Database()
ITEMS_PER_PAGE = 5

class EditServiceStates(StatesGroup):
    waiting_for_photo = State()
    confirm_delete = State()

def create_webapp_form_for_edit(service: dict) -> Optional[ReplyKeyboardMarkup]:
    """Создает форму веб-приложения для редактирования услуги"""
    try:
        service_type = db.get_service_type(service["service_type_id"])
        if not service_type or "required_fields" not in service_type:
            return None
            
        fields = {}
        
        for name, data in service_type["required_fields"].items():
            if name != "photo" and isinstance(data, dict):
                current_value = ""
                if name == "adress":
                    address_parts = []
                    if service.get("city"):
                        address_parts.append(f"г {service['city']}")
                    if service.get("street"): 
                        address_parts.append(f"ул {service['street']}")
                    if service.get("house"):
                        address_parts.append(f"д {service['house']}")
                    current_value = ", ".join(address_parts)
                elif name in service:
                    current_value = service[name]
                elif name in service.get("custom_fields", {}):
                    current_value = service["custom_fields"][name]

                fields[name] = current_value

        field_params = []
        for name, value in fields.items():
            encoded_name = quote(str(name))
            encoded_value = quote(str(value))
            param = f"{encoded_name}={encoded_value}"
            field_params.append(param)

        base_url = "https://spontaneous-kashata-919d92.netlify.app/update"
        full_url = f"{base_url}?{('&').join(field_params)}"
        
        keyboard = ReplyKeyboardBuilder()
        keyboard.row(
            KeyboardButton(
                text="📝 Редактировать", 
                web_app=WebAppInfo(url=full_url)
            )
        )
        keyboard.row(
            KeyboardButton(text="🔙 Отмена"),
            KeyboardButton(text="📸 Изменить фото")
        )
        
        return keyboard.as_markup(resize_keyboard=True)
        
    except Exception as e:
        print(f"Ошибка создания формы редактирования: {e}")
        return None

@router.callback_query(F.data.startswith("edit_service_"))
async def start_edit_service(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования услуги"""
    try:
        service_id, page = map(int, callback.data.split("_")[2:])
        service = db.get_services(service_id=service_id)
        
        if not service:
            await callback.answer("❌ Услуга не найдена")
            return
            
        await state.update_data(edit_service_id=service_id, page=page, last_message_id=callback.message.message_id)
        
        keyboard = create_webapp_form_for_edit(service)
        if keyboard:
            await callback.message.answer(
                "🖥 Выберите действие:\n"
                "• «Редактировать» - изменить данные услуги\n"
                "• «Изменить фото» - загрузить новое изображение\n"
                "• «Отмена» - вернуться назад",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer("❌ Ошибка получения формы")
            
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка редактирования: {e}")
    finally:
        await callback.answer()

@router.message(lambda message: message.web_app_data and message.web_app_data.button_text == "📝 Редактировать")
async def process_edit_webapp_data(message: Message, state: FSMContext):
    """Обработка данных формы редактирования услуги"""
    try:
        data = json.loads(message.web_app_data.data)
        state_data = await state.get_data()
        service_id = state_data.get('edit_service_id')
        last_message_id = state_data.get('last_message_id')
        
        if not service_id:
            raise ValueError("Услуга не найдена")
            
        service = db.get_services(service_id=service_id)
        if not service:
            raise ValueError("Услуга не найдена")
            
        service_type = db.get_service_type(service["service_type_id"])
        if not service_type:
            raise ValueError("Тип услуги не найден")

        # Обновляем только непустые поля
        update_data = {}
        
        # Основные поля
        base_fields = ['title', 'district', 'number_phone', 'price']
        for field in base_fields:
            if data.get(field) is not None and data[field] != '':
                update_data[field] = data[field]

        # Обработка адреса
        if data.get('adress'):
            address_parts = data['adress'].split(',')
            if len(address_parts) >= 1:
                update_data['city'] = address_parts[0].replace('г ', '').strip()
            if len(address_parts) >= 2:
                update_data['street'] = address_parts[1].replace('ул ', '').strip()
            if len(address_parts) >= 3:
                update_data['house'] = address_parts[2].replace('д ', '').strip()

        # Обработка custom fields
        custom_fields = {}
        for key, value in data.items():
            if (key not in base_fields + ['adress', 'service_type_id'] and 
                value is not None and value != ''):
                custom_fields[key] = value

        if custom_fields:
            update_data['custom_fields'] = {
                **service.get('custom_fields', {}),
                **custom_fields
            }

        # Сохраняем данные в состояние
        await state.update_data(form_data=update_data)
        
        keyboard = ReplyKeyboardBuilder()
        keyboard.row(
            KeyboardButton(text="⏩ Пропустить фото"),
            KeyboardButton(text="🔙 Отмена")
        )
        
        await message.answer(
            "📸 Отправьте новое фото услуги или нажмите «Пропустить» чтобы оставить текущее",
            reply_markup=keyboard.as_markup(resize_keyboard=True)
        )
        
        await state.set_state(EditServiceStates.waiting_for_photo)
        
    except json.JSONDecodeError:
        await message.answer("❌ Ошибка обработки данных формы")
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    except Exception as e:
        await message.answer("❌ Произошла неизвестная ошибка")
        print(f"Ошибка обработки формы: {e}")

@router.message(EditServiceStates.waiting_for_photo)
async def process_edit_photo(message: Message, state: FSMContext):
    """Обработка фото при редактировании"""
    try:
        data = await state.get_data()
        form_data = data.get('form_data', {})
        service_id = data.get('edit_service_id')
        page = data.get('page', 0)

        if not service_id:
            raise ValueError("Отсутствуют необходимые данные")

        service = db.get_services(service_id=service_id)
        if not service:
            raise ValueError("Услуга не найдена")

        # Обновляем фото если оно было отправлено
        if message.photo:
            form_data["photo_id"] = message.photo[-1].file_id
        elif message.text != "⏩ Пропустить фото":
            await message.answer("❌ Отправьте фото или нажмите «Пропустить»")
            return
    
        # Обновляем услугу
        if db.update_service(service_id, **form_data):
            updated_service = db.get_services(service_id=service_id)
            caption = await format_service_info(updated_service)
            keyboard = await get_service_keyboard(service_id, updated_service['status'], page)
            
            if updated_service.get('photo_id'):
                photo_ids = updated_service['photo_id'].split(',')
                if len(photo_ids) == 1:
                    await message.answer_photo(
                        photo=photo_ids[0],
                        caption=caption,
                        reply_markup=keyboard
                    )
                else:
                    media = [InputMediaPhoto(media=photo_ids[0], caption=caption)]
                    media.extend([InputMediaPhoto(media=photo_id) for photo_id in photo_ids[1:]])
                    await message.answer_media_group(media=media)
                    await message.answer(text="Управление услугой:", reply_markup=keyboard)
            else:
                await message.answer(caption, reply_markup=keyboard)
                        
            await message.answer("✅ Услуга успешно обновлена", reply_markup=to_home_keyboard())
        else:
            raise Exception("Ошибка при обновлении услуги")

        await state.clear()

    except ValueError as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        await message.answer("❌ Ошибка обновления услуги\nПопробуйте позже или обратитесь в поддержку")
        print(f"Критическая ошибка: {e}")

async def format_service_info(service: dict) -> str:
    """Форматирует информацию об услуге"""
    try:
        address_parts = []
        for field, prefix in {
            'city': 'г. ',
            'district': '',
            'street': 'ул. ',
            'house': 'д. '
        }.items():
            if service.get(field):
                address_parts.append(f"{prefix}{service[field]}")
        
        address_str = ", ".join(filter(None, address_parts))

        try:
            price = "{:,}".format(int(float(service.get('price', 0)))).replace(',', ' ')
        except (ValueError, TypeError):
            price = "0"

        status_emoji = "🟢" if service.get('status') == 'active' else "🔴"
        
        caption = (
            f"{status_emoji} {service.get('title', 'Без названия')}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📍 {address_str}\n"
            f"📱 {service.get('number_phone', 'Не указан')}\n"
            f"💰 {price}₽\n"
            f"👁 Просмотров: {service.get('views', 0)}\n"
            f"📅 Создано: {service.get('created_at', 'Не указано')}\n"
            f"━━━━━━━━━━━━━━━\n"
        )

        service_type = db.get_service_type(service['service_type_id'])
        if not service_type:
            print(f"Тип услуги не найден: {service['service_type_id']}")
            return caption

        custom_fields = service.get('custom_fields', {})
        required_fields = service_type.get('required_fields', {})
        
        if isinstance(custom_fields, dict) and isinstance(required_fields, dict):
            for field, value in custom_fields.items():
                if field in required_fields and value:
                    field_label = required_fields[field].get('label', field)
                    caption += f"📌 {field_label}: {value}\n"

        return caption

    except Exception as e:
        print(f"Ошибка при форматировании услуги: {e}")
        return "Ошибка отображения информации"

async def get_service_keyboard(service_id: int, status: str, page: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру управления услугой"""
    kb = InlineKeyboardBuilder()
    
    status_text = "🔴 Выключить" if status == 'active' else "🟢 Включить"
    status_data = f"toggle_service_{service_id}_{page}"
    
    buttons = [
        (status_text, status_data),
        ("✏️ Редактировать", f"edit_service_{service_id}_{page}"),
        ("📸 Изменить фото", f"change_photo_{service_id}_{page}"),
        ("❌ Удалить", f"delete_service_{service_id}_{page}")
    ]
    
    for text, callback_data in buttons:
        kb.row(InlineKeyboardButton(text=text, callback_data=callback_data))

    return kb.as_markup()

async def get_navigation_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру навигации"""
    kb = InlineKeyboardBuilder()
    
    buttons = []
    if page > 0:
        buttons.append(("⬅️", f"services_page_{page-1}"))
    
    buttons.append((f"📄 {page+1}/{total_pages}", "ignore"))
    
    if page < total_pages - 1:
        buttons.append(("➡️", f"services_page_{page+1}"))
        
    kb.row(*[InlineKeyboardButton(text=text, callback_data=data) for text, data in buttons])
    
    return kb.as_markup()

@router.message(F.text.in_(["📋 Все мои услуги", "my_services"]))
async def show_services(message: types.Message):
    """Показывает список услуг пользователя"""
    try:
        user = db.get_user(telegram_id=str(message.from_user.id))
        if not user or not user[4]:  # user[4] - поле is_seller
            await message.answer(
                "❌ Для просмотра услуг необходимо быть продавцом",
                reply_markup=to_home_keyboard()
            )
            return

        # Исправлено: используем telegram_id вместо user_id
        services = db.get_services(telegram_id=str(message.from_user.id))
        
        if not services:
            await message.answer(
                "📋 У вас пока нет опубликованных услуг\n"
                "Введите /add_service чтобы добавить новую услугу"
            )
            return

        if isinstance(services, dict):
            services = [services]

        total_pages = (len(services) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        for service in services[:ITEMS_PER_PAGE]:
            caption = await format_service_info(service)
            keyboard = await get_service_keyboard(service['id'], service['status'], 0)
            
            if service.get('photo_id'):
                photo_ids = service['photo_id'].split(',')
                if len(photo_ids) == 1:
                    await message.answer_photo(
                        photo=photo_ids[0],
                        caption=caption,
                        reply_markup=keyboard
                    )
                else:
                    media = [InputMediaPhoto(media=photo_ids[0], caption=caption)]
                    media.extend([InputMediaPhoto(media=photo_id) for photo_id in photo_ids[1:]])
                    await message.answer_media_group(media=media)
                    await message.answer(text="Управление услугой:", reply_markup=keyboard)
            else:
                await message.answer(caption, reply_markup=keyboard)

        if total_pages > 1:
            nav_markup = await get_navigation_keyboard(0, total_pages)
            await message.answer("Навигация:", reply_markup=nav_markup)

    except Exception as e:
        print(f"Ошибка при отображении услуг: {e}")
        await message.answer("❌ Произошла ошибка при загрузке услуг")

@router.callback_query(F.data.startswith("services_page_"))
async def handle_pagination(callback: CallbackQuery):
    """Обработка пагинации"""
    try:
        page = int(callback.data.split("_")[2])
        user = db.get_user(telegram_id=str(callback.from_user.id))
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
            
        services = db.get_services(user_id=user[0])
        
        if not services:
            await callback.answer("❌ У вас нет услуг")
            return
        
        if isinstance(services, dict):
            services = [services]
            
        total_pages = (len(services) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        
        for service in services[start_idx:end_idx]:
            caption = await format_service_info(service)
            keyboard = await get_service_keyboard(service['id'], service['status'], page)
            
            if service.get('photo_id'):
                photo_ids = service['photo_id'].split(',')
                if len(photo_ids) == 1:
                    await callback.message.answer_photo(
                        photo=photo_ids[0],
                        caption=caption,
                        reply_markup=keyboard
                    )
                else:
                    media = [InputMediaPhoto(media=photo_ids[0], caption=caption)]
                    media.extend([InputMediaPhoto(media=photo_id) for photo_id in photo_ids[1:]])
                    await callback.message.answer_media_group(media=media)
                    await callback.message.answer(text="Управление услугой:", reply_markup=keyboard)
            else:
                await callback.message.answer(caption, reply_markup=keyboard)

        if total_pages > 1:
            nav_markup = await get_navigation_keyboard(page, total_pages)
            await callback.message.answer("Навигация:", reply_markup=nav_markup)
            
    except Exception as e:
        print(f"Ошибка при пагинации: {e}")
        await callback.answer("❌ Ошибка при обновлении страницы")

@router.callback_query(F.data.startswith("toggle_service_"))
async def toggle_service_status(callback: CallbackQuery):
    """Переключение статуса услуги"""
    try:
        service_id, page = map(int, callback.data.split("_")[2:])
        service = db.get_services(service_id=service_id)
        
        if not service:
            await callback.answer("❌ Услуга не найдена")
            return
            
        new_status = 'deactive' if service.get('status') == 'active' else 'active'
        if db.update_service(service_id, status=new_status):
            status_text = "включена ✅" if new_status == 'active' else "отключена ⭕"
            await callback.answer(f"Услуга успешно {status_text}")
            
            updated_service = db.get_services(service_id=service_id)
            if not updated_service:
                await callback.answer("❌ Ошибка при обновлении данных")
                return
                
            caption = await format_service_info(updated_service)
            keyboard = await get_service_keyboard(service_id, new_status, page)
            
            if updated_service.get('photo_id'):
                photo_ids = updated_service['photo_id'].split(',')
                if len(photo_ids) == 1:
                    await callback.message.answer_photo(
                        photo=photo_ids[0],
                        caption=caption,
                        reply_markup=keyboard
                    )
                else:
                    media = [InputMediaPhoto(media=photo_ids[0], caption=caption)]
                    media.extend([InputMediaPhoto(media=photo_id) for photo_id in photo_ids[1:]])
                    await callback.message.answer_media_group(media=media)
                    await callback.message.answer(text="Управление услугой:", reply_markup=keyboard)
            else:
                await callback.message.answer(caption, reply_markup=keyboard)
                
        else:
            await callback.answer("❌ Ошибка при изменении статуса")
            
    except Exception as e:
        print(f"Ошибка при изменении статуса: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("delete_service_"))
async def delete_service(callback: CallbackQuery):
    """Удаление услуги"""
    try:
        service_id = int(callback.data.split("_")[2])
        
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{service_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_delete_{service_id}")
        )
        
        await callback.message.answer(
            "⚠️ Вы уверены, что хотите удалить эту услугу?\n"
            "Это действие нельзя отменить.",
            reply_markup=kb.as_markup()
        )
        
    except Exception as e:
        print(f"Ошибка при удалении услуги: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_service(callback: CallbackQuery):
    """Подтверждение удаления услуги"""
    try:
        service_id = int(callback.data.split("_")[2])
        if db.delete_service(service_id, hard_delete=True):
            await callback.answer("✅ Услуга успешно удалена")
            await callback.message.answer("✅ Услуга успешно удалена")
            
            # Показываем обновленный список
            await show_services(callback.message)
        else:
            await callback.answer("❌ Ошибка при удалении услуги")
    except Exception as e:
        print(f"Ошибка при удалении услуги: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_service(callback: CallbackQuery):
    """Отмена удаления услуги"""
    try:
        service_id = int(callback.data.split("_")[2])
        service = db.get_services(service_id=service_id)
        
        if service:
            caption = await format_service_info(service)
            keyboard = await get_service_keyboard(service_id, service['status'], 0)
            
            if service.get('photo_id'):
                photo_ids = service['photo_id'].split(',')
                if len(photo_ids) == 1:
                    await callback.message.answer_photo(
                        photo=photo_ids[0],
                        caption=caption,
                        reply_markup=keyboard
                    )
                else:
                    media = [InputMediaPhoto(media=photo_ids[0], caption=caption)]
                    media.extend([InputMediaPhoto(media=photo_id) for photo_id in photo_ids[1:]])
                    await callback.message.answer_media_group(media=media)
                    await callback.message.answer(text="Управление услугой:", reply_markup=keyboard)
            else:
                await callback.message.answer(caption, reply_markup=keyboard)
            
        await callback.answer("Удаление отменено")
    except Exception as e:
        print(f"Ошибка при отмене удаления: {e}")
        await callback.answer("❌ Произошла ошибка")

def validate_form_data(data: Dict[str, Any], required_fields: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """
    Проверяет данные формы на соответствие обязательным полям
    Returns:
        None если валидация успешна, или строку с описанием ошибки
    """
    for field_name, field_info in required_fields.items():
        if field_info.get('required') and field_name != 'photo':
            if field_name not in data or not data[field_name]:
                return f"Поле '{field_info.get('label', field_name)}' обязательно для заполнения"
    return None


@router.callback_query(F.data.startswith("view_service_"))
async def view_service(callback: CallbackQuery):
    await callback.answer()
    """Просмотр услуги"""
    try:
        service_id = int(callback.data.split("_")[2])
        service = db.get_services(service_id=service_id)
        
        if not service:
            await callback.answer("❌ Услуга не найдена")
            return
            
        caption = await format_service_info(service)
        keyboard = InlineKeyboardBuilder()
        
        # Добавляем кнопку возврата к жалобам
        keyboard.row(InlineKeyboardButton(
            text="🔙 Вернуться к жалобам",
            callback_data="get_all_reports"
        ))
        
        if service.get('photo_id'):
            photo_ids = service['photo_id'].split(',')
            if len(photo_ids) == 1:
                await callback.message.edit_media(
                    media=InputMediaPhoto(media=photo_ids[0], caption=caption),
                    reply_markup=keyboard.as_markup()
                )
            else:
                media = [InputMediaPhoto(media=photo_ids[0], caption=caption)]
                media.extend([InputMediaPhoto(media=photo_id) for photo_id in photo_ids[1:]])
                await callback.message.edit_media(
                    media=media,
                    reply_markup=keyboard.as_markup()
                )
        else:
            await callback.message.edit_text(
                caption,
                reply_markup=keyboard.as_markup()
            )
            
        # Увеличиваем счетчик просмотров
        db.update_service(service_id, views=service.get('views', 0) + 1)
        
    except Exception as e:
        print(f"Ошибка при просмотре услуги: {e}")
        await callback.answer("❌ Произошла ошибка при просмотре услуги")
