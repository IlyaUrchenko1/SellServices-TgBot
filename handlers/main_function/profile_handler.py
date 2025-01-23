import random

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Optional
from utils.database import Database
from dotenv import load_dotenv

load_dotenv()

router = Router()
db = Database()

class ProfileStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_name = State()
    waiting_for_work_time = State()
    waiting_for_work_days = State()

@router.message(F.text.in_(["👤 Профиль", "/profile"]))
async def show_profile(message: Message, telegram_id: Optional[int] = None):
    """Показывает профиль пользователя"""
    if telegram_id is None:
        user = db.get_user(telegram_id=str(message.from_user.id))
    else:
        user = db.get_user(telegram_id=str(telegram_id))
    
    if user is None:
        await message.answer("Ошибка: пользователь не найден")
        return
        
    # Распаковываем данные пользователя согласно структуре БД
    user_id, telegram_id, username, phone, is_seller, full_name, work_time_start, work_time_end, work_days = user
    
    # Получаем статистику жалоб через новый метод get_complaints
    received_complaints = db.get_complaints(accused_telegram_id=telegram_id)
    sent_complaints = db.get_complaints(creator_telegram_id=telegram_id)
    
    complaints_stats = {
        'received_total': len(received_complaints),
        'sent_total': len(sent_complaints),
        'received_pending': len([c for c in received_complaints if c['status'] == 'pending'])
    }
    
    # Если пользователь продавец, получаем его активные услуги
    active_services_count = 0
    if is_seller:
        services = db.get_services(telegram_id=telegram_id, status='active')
        active_services_count = len(services) if services else 0
    
    # Форматируем рабочие дни
    days_map = {
        '1': 'Пн', '2': 'Вт', '3': 'Ср', '4': 'Чт',
        '5': 'Пт', '6': 'Сб', '7': 'Вс'
    }
    work_days_formatted = ', '.join(days_map[d] for d in work_days.split(',')) if work_days else 'Не указаны'
    
    # Формируем текст профиля
    profile_text = f"👤 <b>Ваш профиль</b>\n\n"
    profile_text += f"🆔 ID: {user_id}\n"
    profile_text += f"🆔 Telegram ID: {telegram_id}\n"
    profile_text += f"👤 Username: @{username}\n"
    profile_text += f"👨‍💼 Имя: {full_name or 'Не указано'}\n"
    profile_text += f"📱 Телефон: {phone or 'Не указан'}\n"
    profile_text += f"📊 Статус: {'Продавец' if is_seller else 'Покупатель'}\n"
    
    if is_seller:
        profile_text += f"\n⏰ Время работы: {work_time_start} - {work_time_end}\n"
        profile_text += f"📅 Рабочие дни: {work_days_formatted}\n"
        profile_text += f"📦 Активных услуг: {active_services_count}\n"
    
    profile_text += f"\n📝 Жалоб получено: {complaints_stats['received_total']}\n"
    profile_text += f"📝 Жалоб отправлено: {complaints_stats['sent_total']}\n"
    profile_text += f"📝 Жалоб в обработке: {complaints_stats['received_pending']}\n"

    # Создаем клавиатуру с действиями профиля
    keyboard = InlineKeyboardBuilder()
    
    # Добавляем кнопки в зависимости от заполненности полей
    if not phone:
        keyboard.button(text="📱 Указать телефон", callback_data="add_phone")
    else:
        keyboard.button(text="📱 Изменить телефон", callback_data="change_phone")
        
    if not full_name:
        keyboard.button(text="👤 Указать имя", callback_data="add_name")
    else:
        keyboard.button(text="👤 Изменить имя", callback_data="change_name")

    if is_seller:
        keyboard.button(text="⏰ Изменить время работы", callback_data="change_work_time")
        keyboard.button(text="📅 Изменить рабочие дни", callback_data="change_work_days")
    
    keyboard.adjust(2)  # Размещаем кнопки в два столбца
    
    await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard.as_markup())

@router.callback_query(F.data.in_(["add_phone", "change_phone"]))
async def request_phone(callback: CallbackQuery, state: FSMContext):
    """Запрос на добавление/изменение номера телефона"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_input")
    
    await state.set_state(ProfileStates.waiting_for_phone)
    await callback.message.edit_text(
        "📱 Введите номер телефона в формате +7XXXXXXXXXX:",
        reply_markup=keyboard.as_markup()
    )

@router.message(ProfileStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка ввода номера телефона"""
    phone = message.text.strip()
    
    # Валидация номера телефона
    if not (phone.startswith('+7') and len(phone) == 12 and phone[1:].isdigit()):
        await message.answer(
            "❌ Неверный формат номера телефона. Пожалуйста, используйте формат +7XXXXXXXXXX"
        )
        return
        
    try:
        user = db.get_user(telegram_id=str(message.from_user.id))
        if not user:
            raise Exception("Пользователь не найден")
            
        # Обновляем телефон в БД
        db.update_user(
            user_id=user[0],
            number_phone=phone
        )
        
        await state.clear()
        await message.answer("✅ Номер телефона успешно сохранен!")
        
        # Отправляем новое сообщение с обновленным профилем
        await show_profile(message, message.from_user.id)
        
    except Exception as e:
        print(f"Ошибка при обновлении номера телефона: {e}")
        await message.answer("❌ Произошла ошибка при сохранении номера телефона")
        await state.clear()

@router.callback_query(F.data == "change_work_time")
async def work_time_request(callback: CallbackQuery, state: FSMContext):
    """Запрос на изменение времени работы"""
    keyboard = InlineKeyboardBuilder()

    # Добавляем кнопку для круглосуточной работы в отдельную строку
    keyboard.row(InlineKeyboardButton(text="🔄 Круглосуточный режим работы", callback_data="work_24h"))
    
    # Создаем кнопки для выбора времени начала работы
    hours = ['05', '06', '07', '08', '09', '10', '11', '12']
    row = []
    for hour in hours:
        row.append(InlineKeyboardButton(
            text=f"Начало работы в {hour}:00",
            callback_data=f"start_time_{hour}"
        ))
        if len(row) == 2:  # Размещаем по 2 кнопки в ряд
            keyboard.row(*row)
            row = []
    if row:  # Добавляем оставшиеся кнопки
        keyboard.row(*row)
    
    # Кнопка отмены в отдельной строке внизу
    keyboard.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_input"))
    
    await state.set_state(ProfileStates.waiting_for_work_time)
    await callback.message.edit_text(
        "⏰ Выберите время начала работы или режим работы:",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data == "work_24h")
async def set_24h_work(callback: CallbackQuery, state: FSMContext):
    """Установка круглосуточного режима работы"""
    try:
        user = db.get_user(telegram_id=str(callback.from_user.id))
        if not user:
            raise ValueError("Пользователь не найден")
            
        # Обновляем время работы в БД на круглосуточный режим
        db.update_user(
            user_id=user[0],
            work_time_start="00:00",
            work_time_end="23:59"
        )
        
        await state.clear()
        await callback.message.edit_text("✅ Установлен круглосуточный режим работы!")
        
        # Обновляем профиль
        await show_profile(callback.message, callback.from_user.id)
        
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
        await state.clear()
    except Exception as e:
        print(f"Ошибка при установке круглосуточного режима: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при обновлении режима работы")
        await state.clear()

@router.callback_query(lambda c: c.data.startswith("start_time_"))
async def process_start_time(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора времени начала работы"""
    try:
        start_time = callback.data.split('_')[2]
        await state.update_data(start_time=start_time)
        
        keyboard = InlineKeyboardBuilder()
        hours = ['16', '17', '18', '19', '20', '21', '22', '23', '00', '01', '02', '03', '04']
        row = []
        for hour in hours:
            row.append(InlineKeyboardButton(
                text=f"Окончание в {hour}:00",
                callback_data=f"end_time_{hour}"
            ))
            if len(row) == 2:  # Размещаем по 2 кнопки в ряд
                keyboard.row(*row)
                row = []
        if row:  # Добавляем оставшиеся кнопки
            keyboard.row(*row)
            
        # Кнопка отмены в отдельной строке внизу
        keyboard.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_input"))
        
        await callback.message.edit_text(
            f"⏰ Начало работы: {start_time}:00\n"
            f"Выберите время окончания работы:",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        print(f"Ошибка при выборе времени начала: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при выборе времени")
        await state.clear()

@router.callback_query(lambda c: c.data.startswith("end_time_"))
async def process_end_time(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора времени окончания работы"""
    try:
        end_time = callback.data.split('_')[2]
        data = await state.get_data()
        start_time = data.get('start_time')
        
        if not start_time:
            raise ValueError("Не выбрано время начала работы")
            
        user = db.get_user(telegram_id=str(callback.from_user.id))
        if not user:
            raise ValueError("Пользователь не найден")
            
        # Обновляем время работы в БД
        db.update_user(
            user_id=user[0],
            work_time_start=f"{start_time}:00",
            work_time_end=f"{end_time}:00"
        )
        
        await state.clear()
        await callback.message.edit_text(
            f"✅ Время работы успешно обновлено!\n"
            f"⏰ {start_time}:00 - {end_time}:00"
        )
        
        # Отправляем новое сообщение с обновленным профилем
        await show_profile(callback.message, callback.from_user.id)
        
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
        await state.clear()
    except Exception as e:
        print(f"Ошибка при обновлении времени работы: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при обновлении времени работы")
        await state.clear()

@router.callback_query(F.data == "change_work_days")
async def work_days_request(callback: CallbackQuery, state: FSMContext):
    """Запрос на изменение рабочих дней"""
    user = db.get_user(telegram_id=str(callback.from_user.id))
    current_days = set(user[8].split(',')) if user[8] else set()
    
    keyboard = InlineKeyboardBuilder()
    days = {
        '1': 'Пн', '2': 'Вт', '3': 'Ср', '4': 'Чт',
        '5': 'Пт', '6': 'Сб', '7': 'Вс'
    }
    
    for day_num, day_name in days.items():
        status = '✅' if day_num in current_days else '⬜️'
        keyboard.button(
            text=f"{status} {day_name}",
            callback_data=f"toggle_day_{day_num}"
        )
    
    keyboard.button(text="✅ Готово", callback_data="save_work_days")
    keyboard.button(text="🔙 Отмена", callback_data="cancel_input")
    
    keyboard.adjust(4, 3, 2)  # 4 кнопки в первом ряду, 3 во втором, 2 в третьем
    
    await state.set_state(ProfileStates.waiting_for_work_days)
    await state.update_data(selected_days=list(current_days))
    
    await callback.message.edit_text(
        "📅 Выберите рабочие дни:\n"
        "Нажмите на день для выбора/отмены",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(lambda c: c.data.startswith("toggle_day_"))
async def toggle_work_day(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора/отмены рабочего дня"""
    day = callback.data.split('_')[2]
    data = await state.get_data()
    selected_days = set(data.get('selected_days', []))
    
    if day in selected_days:
        selected_days.remove(day)
    else:
        selected_days.add(day)
    
    await state.update_data(selected_days=list(selected_days))
    
    # Обновляем клавиатуру
    keyboard = InlineKeyboardBuilder()
    days = {
        '1': 'Пн', '2': 'Вт', '3': 'Ср', '4': 'Чт',
        '5': 'Пт', '6': 'Сб', '7': 'Вс'
    }
    
    for day_num, day_name in days.items():
        status = '✅' if day_num in selected_days else '⬜️'
        keyboard.button(
            text=f"{status} {day_name}",
            callback_data=f"toggle_day_{day_num}"
        )
    
    keyboard.button(text="✅ Готово", callback_data="save_work_days")
    keyboard.button(text="🔙 Отмена", callback_data="cancel_input")
    
    keyboard.adjust(4, 3, 2)
    
    await callback.message.edit_text(
        "📅 Выберите рабочие дни:\n"
        "Нажмите на день для выбора/отмены",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data == "save_work_days")
async def save_work_days(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранных рабочих дней"""
    try:
        data = await state.get_data()
        selected_days = data.get('selected_days', [])
        
        if not selected_days:
            await callback.message.edit_text(
                "❌ Необходимо выбрать хотя бы один рабочий день"
            )
            return
            
        user = db.get_user(telegram_id=str(callback.from_user.id))
        if not user:
            raise Exception("Пользователь не найден")
            
        # Сортируем дни и преобразуем в строку
        work_days = ','.join(sorted(selected_days))
        
        # Обновляем рабочие дни в БД
        db.update_user(
            user_id=user[0],
            work_days=work_days
        )
        
        await state.clear()
        await callback.message.edit_text("✅ Рабочие дни успешно обновлены!")
        
        # Отправляем новое сообщение с обновленным профилем
        await show_profile(callback.message, callback.from_user.id)
        
    except Exception as e:
        print(f"Ошибка при обновлении рабочих дней: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при обновлении рабочих дней")
        await state.clear()

@router.callback_query(F.data.in_(["add_name", "change_name"]))
async def request_name(callback: CallbackQuery, state: FSMContext):
    """Запрос на добавление/изменение имени"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_input")
    
    await state.set_state(ProfileStates.waiting_for_name)
    await callback.message.edit_text(
        "👤 Введите ваше полное имя:",
        reply_markup=keyboard.as_markup()
    )

@router.message(ProfileStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка ввода имени"""
    name = message.text.strip()
    
    # Простая валидация имени
    if len(name) < 2 or len(name) > 50:
        await message.answer(
            "❌ Имя должно содержать от 2 до 50 символов"
        )
        return
        
    try:
        user = db.get_user(telegram_id=str(message.from_user.id))
        if not user:
            raise Exception("Пользователь не найден")
            
        # Обновляем имя в БД
        db.update_user(
            user_id=user[0],
            full_name=name
        )
        
        await state.clear()
        await message.answer("✅ Имя успешно обновлено!")
        
        # Отправляем новое сообщение с обновленным профилем
        await show_profile(message, message.from_user.id)
        
    except Exception as e:
        print(f"Ошибка при обновлении имени: {e}")
        await message.answer("❌ Произошла ошибка при обновлении имени")
        await state.clear()

@router.callback_query(F.data == "cancel_input")
async def cancel_input(callback: CallbackQuery, state: FSMContext):
    """Отмена ввода данных"""
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено")
    await show_profile(callback.message, callback.from_user.id)