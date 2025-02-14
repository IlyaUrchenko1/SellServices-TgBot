from datetime import datetime

from aiogram import Router, F, types
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, Message,
    InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.database import Database
from handlers.main_function.functions.create_complaints import ComplaintStates, parse_complaint_data, validate_complaint_data
import json
from typing import List, Dict, Any, Optional, Union
from urllib.parse import quote

router = Router(name='watch_handler')
db = Database()

ITEMS_PER_PAGE = 15

class SearchStates(StatesGroup):
    browsing = State()
    filtering = State()
    viewing_service = State()

def build_service_types_keyboard(page: int = 1) -> Optional[InlineKeyboardMarkup]:
    """Создает клавиатуру с типами услуг"""
    # Получаем типы услуг, отсортированные по времени создания (старые сверху)
    service_types = db.get_service_types_by_creation_date()
    if not service_types:
        return

    keyboard = InlineKeyboardBuilder()

    start_idx = (page - 1) * ITEMS_PER_PAGE
    current_page_types = service_types[start_idx:start_idx + ITEMS_PER_PAGE]

    # Каждый тип услуги в отдельной строке
    for service_type in current_page_types:
        if service_type['is_active']:
            keyboard.row(InlineKeyboardButton(
                text=f"{service_type['name']}",
                callback_data=f"watch_type:{service_type['id']}"
            ))

    # Упрощенная пагинация
    if len(service_types) > ITEMS_PER_PAGE:
        pagination_row = []
        if page > 1:
            pagination_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"watch_page_{page-1}"))
        if len(service_types) > start_idx + ITEMS_PER_PAGE:
            pagination_row.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"watch_page_{page+1}"))
        if pagination_row:
            keyboard.row(*pagination_row)

    keyboard.row(InlineKeyboardButton(text="🏠 Вернуться на главную", callback_data="go_to_home"))

    return keyboard.as_markup()

def create_services_keyboard(services: List[Dict], page: int = 1, type_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком услуг, где каждая услуга представлена двумя кнопками:
       - с информацией об услуге
       - для показа фото услуги
    """
    keyboard = InlineKeyboardBuilder()

    if not services:
        print("Список услуг пуст")
        keyboard.row(InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_categories"))
        return keyboard.as_markup()

    start_idx = (page - 1) * ITEMS_PER_PAGE
    current_page_services = services[start_idx:start_idx + ITEMS_PER_PAGE]

    for service in current_page_services:
        service_info = f"{service.get('city', 'Город не указан')} - {service.get('price', 0)}₽"
        # if service.get('custom_fields'):
        #     try:
        #         custom_fields = service['custom_fields'] if isinstance(service['custom_fields'], dict) else json.loads(service['custom_fields'])
        #         for field, value in custom_fields.items():
        #             if field not in ['photo', 'adress', 'number_phone', 'price']:
        #                 service_info += f" - {value}"
        #     except (json.JSONDecodeError, TypeError):
        #         pass

        # Формируем строку с двумя кнопками:
        # Первая кнопка - с информацией об услуге, вторая - для показа фото услуги.
        keyboard.row(
            InlineKeyboardButton(
                text=service_info,
                callback_data=f"service:{service['id']}"
            ),
            InlineKeyboardButton(
                text="📸 Показать фото",
                callback_data=f"show_photos:{service['id']}"
            )
        )

    # Пагинация (если услуг больше, чем ITEMS_PER_PAGE)
    if len(services) > ITEMS_PER_PAGE:
        pagination_row = []
        if page > 1:
            pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"services_page_{page-1}"))
        if len(services) > start_idx + ITEMS_PER_PAGE:
            pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"services_page_{page+1}"))
        if pagination_row:
            keyboard.row(*pagination_row)

    keyboard.row(
        InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="reset_filters"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_services"),
        InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_categories")
    )

    return keyboard.as_markup()

def create_service_details_keyboard(service: Dict[str, Any], seller_id: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для детального просмотра услуги с кнопкой 'Показать фото'"""
    keyboard = InlineKeyboardBuilder()

    # Текущие кнопки: показать телефон и пожаловаться на услугу
    keyboard.row(
        InlineKeyboardButton(text="📞 Показать телефон", callback_data=f"call_{service['id']}"),
        InlineKeyboardButton(text="⚠️ Жалоба на услугу", callback_data=f"create_complaint_service_{seller_id}_{service['id']}")
    )
    
    # Кнопка возврата к списку
    keyboard.row(
        InlineKeyboardButton(text="🔙 К списку", callback_data="back_to_services")
    )

    return keyboard.as_markup()

def create_filter_webapp_keyboard(service_type_id: int) -> Optional[ReplyKeyboardMarkup]:
    service_type = db.get_service_type(service_type_id)
    if not service_type or "required_fields" not in service_type:
        return None

    base_url = "https://spontaneous-kashata-919d92.netlify.app/search"
    custom_fields = {}

    required_fields = service_type["required_fields"]
    if isinstance(required_fields, str):
        try:
            required_fields = json.loads(required_fields)
        except json.JSONDecodeError:
            return None

    for field_name, field_data in required_fields.items():
        if field_name in {'photo', 'number_phone', 'price'}:
            continue
        if isinstance(field_data, dict):
            description = field_data.get('description', '')
            if description:
                custom_fields[field_name] = description

    url_params = [f"{param}={quote(value)}" for param, value in custom_fields.items()]
    webapp_url = f"{base_url}?{'&'.join(url_params)}"

    keyboard = ReplyKeyboardBuilder()
    keyboard.row(
        KeyboardButton(
            text="🔍 Настроить фильтры",
            web_app=WebAppInfo(url=webapp_url)
        )
    )
    keyboard.row(KeyboardButton(text="Вернуться домой 🏠"))

    return keyboard.as_markup(resize_keyboard=True, one_time_keyboard=False)

@router.message(F.text.in_(["👁️ Смотреть услуги", "/search"]))
async def start_search(message: Message, state: FSMContext):
    """Начало поиска услуг"""
    keyboard = build_service_types_keyboard()
    if not keyboard:
        await message.answer(
            "❌ В данный момент нет доступных категорий услуг"
        )
        return

    await state.set_state(SearchStates.browsing)
    await state.set_data({})
    await message.answer("Доступные категории:", reply_markup=keyboard)

@router.callback_query(SearchStates.browsing, lambda c: c.data.startswith('watch_type:'))
async def show_services_by_type(callback: CallbackQuery, state: FSMContext):
    """Показывает услуги выбранного типа"""
    try:
        service_type_id = int(callback.data.split(':')[1])

        await callback.message.answer(
            "📋 Выберите категорию услуг для просмотра:\n"
            "Используйте кнопку «🔍 Настроить фильтры» для уточнения поиска",
            reply_markup=create_filter_webapp_keyboard(service_type_id)
        )
        # Получаем активные услуги выбранного типа
        services = db.filter_services(
            service_type_id=service_type_id,
            status='active',
            limit=100
        )

        if not services:
            await callback.message.edit_text(
                "❌ В данной категории пока нет услуг",
                reply_markup=build_service_types_keyboard()
            )
            
            await callback.answer()
            return

        # Фильтруем услуги по рабочему времени продавцов
        current_time = datetime.now().time()
        current_weekday = str(datetime.now().isoweekday()) 
        
        available_services = []
        
        for service in services:
            try:
                seller_id = service.get('user_id')
                if not seller_id:
                    continue
                    
                seller = db.get_user(telegram_id=str(seller_id))
                if not seller:
                    continue

                user_id, telegram_id, username, phone, is_seller, full_name, work_time_start, work_time_end, work_days = seller

                if not all([work_time_start, work_time_end, work_days]):
                    available_services.append(service)
                    continue

                try:
                    if not (work_time_start and work_time_end and ':' in work_time_start and ':' in work_time_end):
                        available_services.append(service)
                        continue

                    start_time = datetime.strptime(work_time_start, '%H:%M').time()
                    end_time = datetime.strptime(work_time_end, '%H:%M').time()
                    work_days_list = work_days.split(',')
                    
                    if current_weekday in work_days_list:
                        if start_time <= end_time:
                            if start_time <= current_time <= end_time:
                                available_services.append(service)
                        else:  # Если конец рабочего дня на следующий день
                            if current_time >= start_time or current_time <= end_time:
                                available_services.append(service)
                except (ValueError, TypeError):
                    available_services.append(service)
                    continue
                    
            except Exception:
                continue

        if not available_services:
            await callback.message.edit_text(
                "❌ В данный момент нет доступных услуг в этой категории",
                reply_markup=build_service_types_keyboard()
            )
            await callback.answer()
            return

        # Сохраняем данные в состояние
        await state.update_data({
            'current_type_id': service_type_id,
            'services': available_services
        })

        # Создаем клавиатуру и текст сообщения
        keyboard = create_services_keyboard(available_services, type_id=service_type_id)
        new_text = (
            f"📋 Найдено доступных услуг: {len(available_services)}\n"
            "Используйте кнопку «🔍 Настроить фильтры» для уточнения поиска"
        )

        # Обновляем сообщение
        try:
            await callback.message.edit_text(new_text, reply_markup=keyboard)
        except Exception as e:
            if "message is not modified" not in str(e):
                await callback.message.answer(new_text, reply_markup=keyboard)

    except Exception as e:
        try:
            await callback.message.edit_text(
                "❌ Произошла ошибка при загрузке услуг",
                reply_markup=build_service_types_keyboard()
            )
        except Exception as edit_error:
            await callback.message.answer(
                "❌ Произошла ошибка при загрузке услуг",
                reply_markup=build_service_types_keyboard()
            )
    finally:
        await callback.answer()
            

@router.callback_query(SearchStates.browsing, lambda c: c.data.startswith('service:'))
async def show_service_details(callback: CallbackQuery, state: FSMContext):
    """Показывает детальную информацию об услуге"""
    try:
        service_id = int(callback.data.split(':')[1])
        service = db.get_services(service_id=service_id)

        if not service:
            await callback.answer("❌ Услуга не найдена")
            return

        # Получаем информацию о продавце
        seller = db.get_user(telegram_id=service['user_id'])
        if not seller:
            await callback.answer("❌ Информация о продавце недоступна")
            return

        seller_id = seller[1]  # id из кортежа пользователя
        
        # Проверяем рабочее время продавца
        current_time = datetime.now().time()
        current_weekday = str(datetime.now().isoweekday())  # Получаем номер дня недели (1-7)
        
        work_time_start = seller[5]  # work_time_start из кортежа
        work_time_end = seller[6]    # work_time_end из кортежа
        work_days = seller[7]        # work_days из кортежа
        
        if work_time_start and work_time_end and work_days:
            try:
                # Проверяем корректность формата времени
                if not isinstance(work_time_start, str) or not isinstance(work_time_end, str):
                    raise ValueError("Некорректный формат времени")
                
                # Конвертируем строки времени в объекты time
                start_time = datetime.strptime(work_time_start, '%H:%M').time()
                end_time = datetime.strptime(work_time_end, '%H:%M').time()
                
                # Проверяем корректность рабочих дней
                work_days_list = work_days.split(',') if isinstance(work_days, str) else []
                work_days_list = [day.strip() for day in work_days_list]
                
                # Проверяем, является ли текущий день рабочим
                if current_weekday not in work_days_list:
                    await callback.answer("⚠️ Услуга недоступна: сегодня нерабочий день")
                    return
                    
                # Проверяем, находится ли текущее время в рабочем диапазоне
                if not (start_time <= current_time <= end_time):
                    await callback.answer(
                        f"⚠️ Услуга недоступна: время работы с {work_time_start} до {work_time_end}"
                    )
                    return
                    
            except ValueError as e:
                #print(f"Ошибка при проверке рабочего времени: {e}")
                # Продолжаем выполнение даже при ошибке проверки времени
                pass

        db.increment_service_views(service_id)

        details = await format_service_info(service)

        await state.set_state(SearchStates.viewing_service)

        # Сохраняем ID сообщений для последующего удаления
        sent_messages = []

        # Удаляем предыдущее сообщение
        await callback.message.delete()

        # Если есть фотографии
        if service['photo_id']:
            photo_ids = service['photo_id'].split(',') if ',' in service['photo_id'] else [service['photo_id']]

            # Отправляем альбом фотографий
            media_group = []
            for photo_id in photo_ids:
                media_group.append(InputMediaPhoto(media=photo_id))

            if media_group:
                photos_messages = await callback.message.answer_media_group(media=media_group)
                sent_messages.extend([msg.message_id for msg in photos_messages])

        # Отправляем описание с кнопками
        details_message = await callback.message.answer(
            details,
            reply_markup=create_service_details_keyboard(service, seller_id)
        )
        sent_messages.append(details_message.message_id)

        # Сохраняем ID сообщений в состоянии
        await state.update_data(service_messages=sent_messages)

    except Exception as e:
        print(f"Ошибка при показе деталей услуги: {e}")
        await callback.answer("❌ Ошибка при загрузке информации")
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data == "reset_filters")
async def reset_filters(callback: CallbackQuery, state: FSMContext):
    """Сброс всех примененных фильтров"""
    try:
        state_data = await state.get_data()
        service_type_id = state_data.get('current_type_id')

        if service_type_id:
            services = db.filter_services(
                service_type_id=service_type_id,
                status='active'
            )
            await state.update_data(services=services)
            keyboard = create_services_keyboard(services)

            await callback.message.edit_text(
                f"🔄 Фильтры сброшены\n📋 Найдено услуг: {len(services)}",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                "❌ Не удалось сбросить фильтры",
                reply_markup=build_service_types_keyboard()
            )
    except Exception as e:
        print(f"Ошибка при сбросе фильтров: {e}")
        await callback.answer("❌ Произошла ошибка")
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data == "refresh_services")
async def refresh_services(callback: CallbackQuery, state: FSMContext):
    """Обновление списка услуг"""
    try:
        state_data = await state.get_data()
        service_type_id = state_data.get('current_type_id')
        last_filters = state_data.get('last_filters', {})

        if not service_type_id:
            await callback.answer("❌ Не удалось обновить список")
            return

        services = db.filter_services(
            service_type_id=service_type_id,
            city=last_filters.get('city'),
            price_min=last_filters.get('price_min'),
            price_max=last_filters.get('price_max'),
            custom_fields=last_filters.get('custom_fields'),
            sort_by=last_filters.get('sort_by', 'created_at'),
            sort_direction=last_filters.get('sort_direction', 'DESC'),
            status='active'
        )

        await state.update_data(services=services)
        keyboard = create_services_keyboard(services)

        filter_text = ["🔄 Список обновлен"]

        if last_filters:
            filter_text.append("Применены фильтры:")
            if last_filters.get('city'):
                filter_text.append(f"📍 Город: {last_filters['city']}")
            if last_filters.get('price_min') or last_filters.get('price_max'):
                price_text = "💰 Цена: "
                if last_filters.get('price_min') and last_filters.get('price_max'):
                    price_text += f"от {last_filters['price_min']}₽ до {last_filters['price_max']}₽"
                elif last_filters.get('price_min'):
                    price_text += f"от {last_filters['price_min']}₽"
                else:
                    price_text += f"до {last_filters['price_max']}₽"
                filter_text.append(price_text)
            if custom_fields := last_filters.get('custom_fields'):
                filter_text.append("📌 Дополнительные фильтры:")
                for field, value in custom_fields.items():
                    filter_text.append(f"   • {field}: {value}")

        filter_text.append(f"📋 Найдено услуг: {len(services)}")

        await callback.message.edit_text(
            "\n".join(filter_text),
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка при обновлении списка: {e}")
        await callback.answer("❌ Произошла ошибка")
    finally:
        await callback.answer()

@router.message(SearchStates.browsing, lambda message: message.web_app_data and message.web_app_data.button_text == "🔍 Настроить фильтры")
async def process_filter_webapp_data(message: Message, state: FSMContext):
    """Обработка данных фильтров из веб-приложения"""
    try:
        filter_data = json.loads(message.web_app_data.data)
        state_data = await state.get_data()
        service_type_id = state_data.get('current_type_id')

        if not service_type_id:
            await message.answer(
                "❌ Не выбрана категория услуг",
                reply_markup=build_service_types_keyboard()
            )
            return

        # Подготавливаем фильтры
        filters = {
            'service_type_id': service_type_id,
            'status': 'active'
        }

        # Обработка города
        if city := filter_data.get('city', '').strip():
            if city != "Не указан":
                filters['city'] = city

        # Обработка цены
        if price_str := filter_data.get('price', '').strip():
            try:
                if price_str.startswith('до'):
                    filters['price_max'] = float(price_str.split()[1].replace('₽', '').replace(' ', ''))
                elif price_str.startswith('от'):
                    filters['price_min'] = float(price_str.split()[1].replace('₽', '').replace(' ', ''))
                else:
                    price_parts = price_str.split('-')
                    if len(price_parts) == 2:
                        filters['price_min'] = float(price_parts[0].replace('₽', '').replace(' ', ''))
                        filters['price_max'] = float(price_parts[1].replace('₽', '').replace(' ', ''))
            except (ValueError, IndexError):
                print("Ошибка при парсинге цены")

        # Обработка сортировки
        sort_by = 'created_at'
        sort_direction = 'DESC'
        
        if filter_data.get('sortOld'):
            sort_direction = 'ASC'
        elif filter_data.get('sortPopular'):
            sort_by = 'views'

        filters['sort_by'] = sort_by
        filters['sort_direction'] = sort_direction

        # Обработка дополнительных полей
        custom_fields = {}
        service_type = db.get_service_type(service_type_id)
        
        if service_type and "required_fields" in service_type:
            required_fields = service_type["required_fields"]
            if isinstance(required_fields, str):
                required_fields = json.loads(required_fields)
                
            for field_name, field_value in filter_data.items():
                # Пропускаем служебные поля и пустые значения
                if (field_name not in ['city', 'price', 'sortNew', 'sortOld', 'sortPopular'] and 
                    field_value and 
                    field_value != "Не указан" and 
                    field_value != "Не указана"):
                    custom_fields[field_name] = field_value

        if custom_fields:
            filters['custom_fields'] = custom_fields

        # Получаем отфильтрованные услуги
        services = db.filter_services(**filters)

        # Сохраняем примененные фильтры в состоянии
        await state.update_data(
            services=services,
            last_filters={
                'city': filters.get('city'),
                'price_min': filters.get('price_min'),
                'price_max': filters.get('price_max'),
                'custom_fields': filters.get('custom_fields'),
                'sort_by': sort_by,
                'sort_direction': sort_direction
            }
        )

        if not services:
            await message.answer(
                "🔍 По вашему запросу ничего не найдено\n"
                "Попробуйте изменить параметры поиска",
                reply_markup=create_filter_webapp_keyboard(service_type_id)
            )
            return

        # Формируем текст с примененными фильтрами
        filter_text = ["🔍 Результаты поиска:"]
        
        if filters.get('city'):
            filter_text.append(f"📍 Город: {filters['city']}")
            
        if filters.get('price_min') or filters.get('price_max'):
            price_text = "💰 Цена: "
            if filters.get('price_min') and filters.get('price_max'):
                price_text += f"от {filters['price_min']}₽ до {filters['price_max']}₽"
            elif filters.get('price_min'):
                price_text += f"от {filters['price_min']}₽"
            else:
                price_text += f"до {filters['price_max']}₽"
            filter_text.append(price_text)

        if custom_fields:
            filter_text.append("📌 Дополнительные фильтры:")
            for field, value in custom_fields.items():
                filter_text.append(f"   • {field}: {value}")

        filter_text.append(f"📋 Найдено услуг: {len(services)}")

        # Отправляем результаты
        keyboard = create_services_keyboard(services)
        await message.answer(
            "\n".join(filter_text),
            reply_markup=keyboard
        )

    except json.JSONDecodeError:
        await message.answer(
            "❌ Ошибка обработки данных фильтров\n"
            "Пожалуйста, попробуйте еще раз",
            reply_markup=create_filter_webapp_keyboard(service_type_id)
        )
    except Exception as e:
        print(f"Ошибка при обработке фильтров: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске\n"
            "Попробуйте позже или измените параметры поиска",
            reply_markup=create_filter_webapp_keyboard(service_type_id)
        )

@router.callback_query(lambda c: c.data.startswith('call_'))
async def handle_call_button(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки показать телефон"""
    try:
        # Получаем ID услуги из callback data
        service_id = int(callback.data.split('_')[1])
        
        # Получаем информацию об услуге
        service = db.get_services(service_id=service_id)
        if not service:
            await callback.answer("❌ Услуга не найдена", show_alert=True)
            return

        # Получаем информацию о продавце
        user_id = service.get('user_id')
        seller = db.get_user(telegram_id=user_id)
        if not seller:
            await callback.answer("❌ Информация о продавце недоступна", show_alert=True)
            return

        # Проверяем, не является ли пользователь владельцем услуги
        # if str(callback.from_user.id) == str(user_id):
        #     await callback.answer("❌ Это ваша услуга", show_alert=True)
        #     return

        # Проверяем наличие номера телефона
        number_phone = service.get('number_phone', 'Не указан')
        if not number_phone:
            await callback.answer("❌ Номер телефона не указан", show_alert=True)
            return

        # Создаем клавиатуру
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📞 Телефон для связи", callback_data=f"call_{service_id}"),
            InlineKeyboardButton(text="✅ Забронировать", callback_data=f"book_{service_id}")
        )
        keyboard.row(
            InlineKeyboardButton(
                text="⚠️ Жалоба на услугу", 
                callback_data=f"create_complaint_service_{user_id}_{service_id}"
            )
        )
        keyboard.row(
            InlineKeyboardButton(text="🔙 К списку", callback_data="back_to_services")
        )

        # Обновляем клавиатуру и показываем номер телефона
        # Проверяем, изменилась ли клавиатура
        current_markup = callback.message.reply_markup
        new_markup = keyboard.as_markup()
        
        if str(current_markup) != str(new_markup):
            await callback.message.edit_reply_markup(reply_markup=new_markup)
            
        await callback.message.answer(
            f"📞 Телефон для связи: {number_phone}",
            show_alert=True
        )

    except ValueError:
        await callback.answer("❌ Некорректный ID услуги", show_alert=True)
    except Exception as e:
        print(f"Ошибка при показе номера телефона: {str(e)}")
        await callback.answer(
            "❌ Произошла ошибка. Попробуйте позже", 
            show_alert=True
        )

@router.callback_query(lambda c: c.data.startswith('book_'))
async def handle_book_button(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки забронировать"""
    try:
        service_id = int(callback.data.split('_')[1])
        service = db.get_services(service_id=service_id)

        if not service or not isinstance(service, dict):
            print(f"Услуга {service_id} не найдена при бронировании или неверный формат данных")
            await callback.answer("❌ Услуга не найдена")
            return

        user_id = service.get('user_id')
        if not user_id:
            print(f"ID пользователя не найден в данных услуги {service_id}")
            await callback.answer("❌ Ошибка при бронировании - некорректные данные услуги")
            return

        # Проверяем, не является ли пользователь владельцем услуги
        # if str(callback.from_user.id) == str(user_id):
        #     await callback.answer("❌ Вы не можете забронировать свою собственную услугу")
        #     return

        owner = db.get_user(telegram_id=user_id)
        if not owner or not isinstance(owner, tuple):
            print(f"Владелец услуги {service_id} не найден или неверный формат данных")
            await callback.answer("❌ Ошибка при бронировании - владелец не найден")
            return

        # Проверяем статус услуги перед бронированием
        if service.get('status') == 'booked':
            await callback.answer("❌ Услуга уже забронирована")
            return

        db.update_service_status(service_id, 'booked')

        owner_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel_book_{service_id}"),
                InlineKeyboardButton(text="⚠️ Жалоба", callback_data=f"create_complaint_user_{user_id}")
            ]
        ])

        # Безопасное получение данных услуги
        title = service.get('title', 'Без названия')
        price = service.get('price', 0)
        
        try:
            price_formatted = "{:,}".format(int(float(price))).replace(',', ' ')
        except (ValueError, TypeError):
            price_formatted = "0"

        username = callback.from_user.username or "Пользователь"

        await callback.bot.send_message(
            chat_id=owner[1],  # telegram_id из кортежа пользователя
            text=(
                f"🔔 Ваша услуга была забронирована!\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📝 Услуга: {title}\n"
                f"💰 Стоимость: {price_formatted}₽\n\n"
                "ℹ️ Если вы еще не связались с клиентом, сделайте это в ближайшее время."
            ),
            reply_markup=owner_keyboard
        )

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(
            "✅ Услуга успешно забронирована!\n\n"
            "ℹ️ Владелец получил уведомление и свяжется с вами в ближайшее время.\n"
            "📞 Вы также можете связаться с владельцем самостоятельно по указанному номеру телефона."
        )

    except ValueError as ve:
        print(f"Ошибка преобразования данных при бронировании: {ve}")
        await callback.answer("❌ Некорректные данные услуги")
    except Exception as e:
        print(f"Ошибка при бронировании услуги: {str(e)}")
        await callback.answer("❌ Произошла ошибка при бронировании")
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data.startswith('cancel_book_'))
async def handle_cancel_book_button(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены бронирования"""
    try:
        # Проверяем корректность callback данных
        callback_parts = callback.data.split('_')
        if len(callback_parts) != 3:
            await callback.answer("❌ Некорректный формат данных")
            return
            
        try:
            service_id = int(callback_parts[2])
        except ValueError:
            await callback.answer("❌ Некорректный ID услуги")
            return

        # Получаем информацию об услуге
        service = db.get_services(service_id=service_id)
        if not service:
            print(f"Услуга {service_id} не найдена при отмене брони")
            await callback.answer("❌ Услуга не найдена", show_alert=True)
            return

        # Проверяем, что услуга действительно забронирована
        if service[11] != 'booked':  # status field
            await callback.answer("❌ Услуга не находится в статусе бронирования", show_alert=True)
            return

        # Проверяем права на отмену брони
        if str(callback.from_user.id) != str(service[1]):  # user_id field
            await callback.answer("❌ У вас нет прав на отмену этой брони", show_alert=True)
            return

        # Обновляем статус услуги
        try:
            db.update_service_status(service_id, 'active')
        except Exception as db_error:
            print(f"Ошибка при обновлении статуса услуги: {db_error}")
            await callback.answer("❌ Ошибка при обновлении статуса", show_alert=True)
            return

        # Уведомляем пользователя, забронировавшего услугу
        booked_user = db.get_user(user_id=service[1])
        if booked_user and booked_user[1]:  # Проверяем наличие telegram_id
            try:
                await callback.bot.send_message(
                    chat_id=booked_user[1],
                    text=(
                        f"❌ Бронирование услуги «{service[3]}» было отменено владельцем.\n"
                        f"ℹ️ Услуга снова доступна для бронирования."
                    )
                )
            except Exception as msg_error:
                print(f"Ошибка при отправке уведомления пользователю: {msg_error}")

        # Обновляем сообщение и отправляем подтверждение
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("✅ Бронирование успешно отменено", show_alert=True)
        except Exception as edit_error:
            print(f"Ошибка при обновлении сообщения: {edit_error}")

    except Exception as e:
        print(f"Критическая ошибка при отмене бронирования: {e}")
        await callback.answer(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже", 
            show_alert=True
        )

@router.callback_query(lambda c: c.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку услуг"""
    try:
        state_data = await state.get_data()
        services = state_data.get('services', [])
        service_messages = state_data.get('service_messages', [])
        current_page = state_data.get('current_page', 1)

        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            print(f"Ошибка при удалении текущего сообщения: {e}")

        # Удаляем предыдущие сообщения с фото
        for message_id in service_messages:
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=message_id
                )
            except Exception as e:
                print(f"Ошибка при удалении сообщения {message_id}: {e}")

        # Очищаем список сообщений в состоянии
        await state.update_data(service_messages=[])

        if services:
            await state.set_state(SearchStates.browsing)
            keyboard = create_services_keyboard(services, page=current_page)

            new_message = await callback.message.answer(
                f"📋 Найдено услуг: {len(services)}\n"
                "Используйте кнопку «🔍 Настроить фильтры» для уточнения поиска",
                reply_markup=keyboard
            )

            # Сохраняем ID нового сообщения
            await state.update_data(current_message_id=new_message.message_id)
        else:
            print("Нет сохраненных услуг в состоянии")
            await callback.message.answer(
                "❌ Ошибка при возврате к списку услуг",
                reply_markup=build_service_types_keyboard()
            )
    except Exception as e:
        print(f"Ошибка при возврате к списку услуг: {e}")
        await callback.message.answer(
            "❌ Ошибка при возврате к списку услуг",
            reply_markup=build_service_types_keyboard()
        )
        await callback.answer("❌ Произошла ошибка")
    finally:
        await callback.answer()

@router.callback_query(SearchStates.browsing, lambda c: c.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку категорий"""
    try:
        await state.set_data({})
        keyboard = build_service_types_keyboard()
        
        await callback.message.delete()
        await callback.message.answer(
            "📋 Выберите категорию услуг для просмотра:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка при возврате к категориям: {e}")
        await callback.answer("❌ Произошла ошибка")
    finally:
        await callback.answer()

@router.callback_query(SearchStates.browsing, lambda c: c.data.startswith('watch_page_'))
async def handle_category_pagination(callback: CallbackQuery):
    """Обработка пагинации категорий"""
    try:
        page = int(callback.data.split('_')[2])
        keyboard = build_service_types_keyboard(page)
        
        if keyboard:
            try:
                await callback.message.edit_reply_markup(reply_markup=keyboard)
            except Exception as e:
                if "message is not modified" not in str(e):
                    print(f"Ошибка при обновлении клавиатуры: {e}")
                    raise
        else:
            print(f"Не удалось создать клавиатуру для страницы {page}")
            await callback.message.edit_text(
                "❌ Ошибка загрузки категорий",
                reply_markup=types.ReplyKeyboardRemove()
            )
    except Exception as e:
        print(f"Ошибка пагинации: {e}")
        await callback.answer("❌ Ошибка при переключении страницы")
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data.startswith("show_photos:"))
async def handle_show_photos(callback: CallbackQuery, state: FSMContext):
    try:
        service_id = int(callback.data.split(':')[1])
        service = db.get_services(service_id=service_id)

        if not service:
            await callback.answer("❌ Услуга не найдена")
            return

        if not service.get('photo_id'):
            await callback.answer("❌ У этой услуги нет фотографий", show_alert=True)
            return

        photo_ids = [pid.strip() for pid in service['photo_id'].split(',') if pid.strip()]
        if not photo_ids:
            await callback.answer("❌ Ошибка загрузки фотографий", show_alert=True)
            return

        try:
            await callback.answer("⌛ Загружаем фотографии...", show_alert=False)
            
            # Сохраняем ID сообщений для последующего удаления
            state_data = await state.get_data()
            service_messages = state_data.get('service_messages', [])
            
            # Удаляем предыдущие сообщения
            for message_id in service_messages:
                try:
                    await callback.bot.delete_message(
                        chat_id=callback.message.chat.id,
                        message_id=message_id
                    )
                except Exception as e:
                    print(f"Ошибка при удалении сообщения {message_id}: {e}")
            
            # Очищаем список сообщений
            service_messages = []
            
            # Создаем клавиатуру с кнопкой "Назад к услуге"
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(
                text="🔙 Назад к списку услуг",
                callback_data=f"back_to_services"
            ))

            try:
                await callback.message.delete()
            except Exception as e:
                print(f"Ошибка при удалении исходного сообщения: {e}")

            if len(photo_ids) == 1:
                # Отправляем одно фото
                sent_message = await callback.message.answer_photo(
                    photo=photo_ids[0],
                    caption="📸 Фото услуги",
                    reply_markup=keyboard.as_markup()
                )
                service_messages.append(sent_message.message_id)
            else:
                # Отправляем группу фото
                media_group = []
                for i, photo_id in enumerate(photo_ids):
                    media = InputMediaPhoto(
                        media=photo_id,
                        caption=f"📸 Фото {i+1}/{len(photo_ids)}" if i == 0 else None
                    )
                    media_group.append(media)
                
                sent_messages = await callback.message.answer_media_group(media=media_group)
                service_messages.extend([msg.message_id for msg in sent_messages])
                
                # Отправляем сообщение с кнопкой
                nav_message = await callback.message.answer(
                    "Используйте кнопку ниже для возврата к списку услуг",
                    reply_markup=keyboard.as_markup()
                )
                service_messages.append(nav_message.message_id)
            
            # Сохраняем новые ID сообщений
            await state.update_data(service_messages=service_messages)

        except Exception as media_error:
            print(f"Ошибка при отправке медиа: {media_error}")
            await callback.answer(
                "❌ Не удалось загрузить фотографии. Попробуйте позже", 
                show_alert=True
            )
            return

    except ValueError:
        await callback.answer("❌ Некорректный ID услуги", show_alert=True)
    except Exception as e:
        print(f"Критическая ошибка при показе фото: {e}")
        await callback.answer(
            "❌ Произошла ошибка при загрузке фотографий",
            show_alert=True
        )

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
            #f"📱 {service.get('number_phone', 'Не указан')}\n"
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
