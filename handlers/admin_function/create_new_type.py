from aiogram import Router, F
from aiogram.fsm.context import FSMContext 
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.database import Database
from utils.variables import ADMIN_IDS
from keyboards.role_keyboards import admin_keyboard
import re
from typing import Dict, Any, List

router = Router(name='admin')
db = Database()

RESERVED_FIELDS = {"title", "photo", "address", "price", "district", "number_phone", "city", "house", "street"}
MAX_FIELD_NAME_LENGTH = 50
MAX_FIELD_LABEL_LENGTH = 100
MAX_FIELD_DESCRIPTION_LENGTH = 500
MAX_SELECT_OPTIONS = 20
MAX_FIELDS_PER_TYPE = 15

class CreateServiceType(StatesGroup):
    waiting_for_name = State()
    waiting_for_price_level = State()
    waiting_for_field_name = State()
    waiting_for_field_type = State() 
    waiting_for_field_label = State()
    waiting_for_field_description = State()
    waiting_for_field_required = State()
    waiting_for_select_options = State()
    waiting_for_confirmation = State()
    management = State()  # Состояние панели управления уже созданным типом услуги

def get_back_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    keyboard.row(InlineKeyboardButton(text="🏠 В админ меню", callback_data="admin_menu"))
    return keyboard.as_markup()

def get_fields_summary(fields: List[Dict[str, Any]]) -> str:
    if not fields:
        return "Поля еще не добавлены"
    
    summary = "📋 Текущие поля:\n\n"
    for i, field in enumerate(fields, 1):
        required = "✅" if field.get("required") else "❌"
        summary += f"{i}. {field.get('label', 'Без метки')} ({field.get('name')})\n"
        summary += f"   Тип: {field.get('type', 'Не указан')}\n"
        summary += f"   Обязательное: {required}\n"
        if field.get("options"):
            summary += f"   Варианты: {', '.join(field['options'])}\n"
        if field.get("description"):
            summary += f"   Описание: {field.get('description')}\n"
        summary += "\n"
    return summary

def get_fields_keyboard(fields_count: int, service_type_id: int):
    keyboard = InlineKeyboardBuilder()
    if fields_count < MAX_FIELDS_PER_TYPE:
        keyboard.row(InlineKeyboardButton(text="➕ Добавить поле", callback_data=f"add_field_{service_type_id}"))
    if fields_count > 0:
        keyboard.row(InlineKeyboardButton(text="🗑 Удалить последнее поле", callback_data=f"delete_last_field_{service_type_id}"))
    keyboard.row(InlineKeyboardButton(text="✅ Завершить редактирование", callback_data="finish_editing"))
    keyboard.row(InlineKeyboardButton(text="🏠 В админ меню", callback_data="admin_menu"))
    return keyboard.as_markup()

def validate_field_name(name: str) -> tuple[bool, str]:
    if not name:
        return False, "❌ Название поля не может быть пустым"
    if name in RESERVED_FIELDS:
        return False, "❌ Это зарезервированное название поля"
    if len(name) > MAX_FIELD_NAME_LENGTH:
        return False, f"❌ Название поля не может быть длиннее {MAX_FIELD_NAME_LENGTH} символов"
    if not re.match("^[a-z][a-z0-9_]*$", name):
        return False, "❌ Название поля должно начинаться с буквы и содержать только латинские буквы, цифры и знак подчеркивания"
    return True, ""

@router.callback_query(F.data == "create_service_type")
async def start_create_service_type(callback: CallbackQuery, state: FSMContext):
    try:
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("❌ У вас нет прав администратора", show_alert=True)
            return

        await state.clear()
        await state.set_state(CreateServiceType.waiting_for_name)
        await state.update_data(current_field={})
        
        await callback.message.edit_text(
            "📝 Создание нового типа услуги\n\n"
            "Введите название для нового типа услуги.\n"
            "Это название будут видеть пользователи при выборе категории.\n\n"
            "🎯 Примеры:\n"
            "- Репетитор английского языка\n"
            "- Мастер маникюра\n"
            "- Фотограф\n\n"
            "❗️ Название должно быть от 3 до 100 символов",
            reply_markup=get_back_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.message(CreateServiceType.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    try:
        name = message.text.strip()
        
        if len(name) < 3:
            await message.answer("❌ Название слишком короткое. Минимум 3 символа.")
            return
        
        if len(name) > 100:
            await message.answer("❌ Название слишком длинное. Максимум 100 символов.")
            return

        if db.get_service_type_by_name(name):
            await message.answer("❌ Тип услуги с таким названием уже существует!")
            return
            
        await state.update_data(name=name)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="Тысячи рублей", callback_data="price_level_0"),
            InlineKeyboardButton(text="Десятки тысяч рублей", callback_data="price_level_1")
        )
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
        
        await state.set_state(CreateServiceType.waiting_for_price_level)
        await message.answer(
            "Выберите уровень цены для данного типа услуг:",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

@router.callback_query(CreateServiceType.waiting_for_price_level, F.data.startswith("price_level_"))
async def process_price_level(callback: CallbackQuery, state: FSMContext):
    try:
        price_level = int(callback.data.split("_")[2])
        data = await state.get_data()
        name = data.get("name")
        type_id = db.add_service_type(
            header=name,
            created_by_telegram_id=str(callback.from_user.id),
            price_level=price_level
        )
        
        if not type_id:
            raise Exception("Не удалось создать тип услуги")
            
        # Обновляем данные с ID созданного типа услуги и переходим в режим управления
        await state.update_data(name=name, price_level=price_level, service_type_id=type_id)
        await state.set_state(CreateServiceType.management)
        
        fields = db.get_service_type_fields(type_id)
        price_str = "Десятки тысяч рублей" if price_level == 1 else "Тысячи рублей"
        await callback.message.edit_text(
            f"🛠 Панель управления типом услуги:\n"
            f"Название: {name}\n"
            f"Уровень цены: {price_str}\n\n"
            f"{get_fields_summary(fields)}",
            reply_markup=get_fields_keyboard(len(fields), type_id)
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("add_field_"))
async def start_add_field(callback: CallbackQuery, state: FSMContext):
    try:
        service_type_id = int(callback.data.split("_")[2])
        # Проверяем, не достигнуто ли максимальное число полей для данного типа услуги (запрос из БД)
        fields = db.get_service_type_fields(service_type_id)
        if len(fields) >= MAX_FIELDS_PER_TYPE:
            await callback.answer(f"❌ Достигнуто максимальное количество полей ({MAX_FIELDS_PER_TYPE})", show_alert=True)
            return
        
        await state.update_data(current_field={})
        await state.set_state(CreateServiceType.waiting_for_field_name)
        await callback.message.edit_text(
            "🔑 Добавление нового поля\n\n"
            "Введите техническое название поля (английскими буквами):\n"
            "Например: experience, education, skills\n\n"
            "❗️ Поля не должны быть из списка зарезервированных:\n"
            f"{', '.join(RESERVED_FIELDS)}\n\n"
            "Требования к названию поля:\n"
            "- Только английские буквы, цифры и _\n"
            "- Начинается с буквы\n"
            f"- Не длиннее {MAX_FIELD_NAME_LENGTH} символов",
            reply_markup=get_back_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.message(CreateServiceType.waiting_for_field_name)
async def process_field_name(message: Message, state: FSMContext):
    try:
        field_name = message.text.strip()
        is_valid, error_message = validate_field_name(field_name)
        
        if not is_valid:
            await message.answer(error_message)
            return
        
        data = await state.get_data()
        current_field = data.get("current_field", {})
        current_field["name"] = field_name
        await state.update_data(current_field=current_field)
        
        # Переходим к выбору типа поля
        await state.set_state(CreateServiceType.waiting_for_field_type)
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="Текст", callback_data="field_type_text"),
            InlineKeyboardButton(text="Число", callback_data="field_type_number")
        )
        keyboard.row(
            InlineKeyboardButton(text="Выбор из списка", callback_data="field_type_select"),
            InlineKeyboardButton(text="Дата", callback_data="field_type_date")
        )
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
        await message.answer(
            "Выберите тип поля:",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

@router.callback_query(CreateServiceType.waiting_for_field_type, F.data.startswith("field_type_"))
async def process_field_type(callback: CallbackQuery, state: FSMContext):
    try:
        field_type = callback.data.replace("field_type_", "")
        data = await state.get_data()
        current_field = data.get("current_field", {})
        current_field["type"] = field_type
        await state.update_data(current_field=current_field)
        
        await state.set_state(CreateServiceType.waiting_for_field_label)
        await callback.message.edit_text(
            "Введите метку поля (то, что будет отображаться пользователям):",
            reply_markup=get_back_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.message(CreateServiceType.waiting_for_field_label)
async def process_field_label(message: Message, state: FSMContext):
    try:
        label = message.text.strip()
        if len(label) > MAX_FIELD_LABEL_LENGTH:
            await message.answer(f"❌ Метка поля не может быть длиннее {MAX_FIELD_LABEL_LENGTH} символов")
            return
        
        data = await state.get_data()
        current_field = data.get("current_field", {})
        current_field["label"] = label
        await state.update_data(current_field=current_field)
        
        await state.set_state(CreateServiceType.waiting_for_field_description)
        await message.answer(
            "Введите описание поля (опционально, можно оставить пустым):",
            reply_markup=get_back_keyboard()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

@router.message(CreateServiceType.waiting_for_field_description)
async def process_field_description(message: Message, state: FSMContext):
    try:
        description = message.text.strip()
        if description and len(description) > MAX_FIELD_DESCRIPTION_LENGTH:
            await message.answer(f"❌ Описание поля не может быть длиннее {MAX_FIELD_DESCRIPTION_LENGTH} символов")
            return
        
        data = await state.get_data()
        current_field = data.get("current_field", {})
        current_field["description"] = description
        await state.update_data(current_field=current_field)
        
        await state.set_state(CreateServiceType.waiting_for_field_required)
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="✅ Да", callback_data="field_required_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="field_required_no")
        )
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
        await message.answer(
            "Поле является обязательным?",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

@router.callback_query(CreateServiceType.waiting_for_field_required, F.data.startswith("field_required_"))
async def process_field_required(callback: CallbackQuery, state: FSMContext):
    try:
        required = True if callback.data.endswith("yes") else False
        data = await state.get_data()
        current_field = data.get("current_field", {})
        current_field["required"] = required
        await state.update_data(current_field=current_field)
        
        if current_field.get("type") == "select":
            await state.set_state(CreateServiceType.waiting_for_select_options)
            await callback.message.edit_text(
                "Введите варианты выбора, разделенные запятыми:\n"
                f"(Не более {MAX_SELECT_OPTIONS} вариантов)",
                reply_markup=get_back_keyboard()
            )
        else:
            await state.set_state(CreateServiceType.waiting_for_confirmation)
            summary = (
                f"Название: {current_field.get('name')}\n"
                f"Метка: {current_field.get('label')}\n"
                f"Тип: {current_field.get('type')}\n"
                f"Обязательное: {'✅' if current_field.get('required') else '❌'}\n"
                f"Описание: {current_field.get('description', '')}"
            )
            keyboard = InlineKeyboardBuilder()
            keyboard.row(
                InlineKeyboardButton(text="Подтвердить", callback_data="confirm_field"),
                InlineKeyboardButton(text="Отмена", callback_data="cancel_field")
            )
            keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
            await callback.message.edit_text(
                f"Подтверждение добавления поля:\n\n{summary}",
                reply_markup=keyboard.as_markup()
            )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.message(CreateServiceType.waiting_for_select_options)
async def process_select_options(message: Message, state: FSMContext):
    try:
        options = [opt.strip() for opt in message.text.split(",") if opt.strip()]
        if len(options) > MAX_SELECT_OPTIONS:
            await message.answer(f"❌ Количество вариантов не может превышать {MAX_SELECT_OPTIONS}")
            return
        
        data = await state.get_data()
        current_field = data.get("current_field", {})
        current_field["options"] = options
        await state.update_data(current_field=current_field)
        
        await state.set_state(CreateServiceType.waiting_for_confirmation)
        summary = (
            f"Название: {current_field.get('name')}\n"
            f"Метка: {current_field.get('label')}\n"
            f"Тип: {current_field.get('type')}\n"
            f"Обязательное: {'✅' if current_field.get('required') else '❌'}\n"
            f"Варианты: {', '.join(options)}\n"
            f"Описание: {current_field.get('description', '')}"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="Подтвердить", callback_data="confirm_field"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel_field")
        )
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
        await message.answer(
            f"Подтверждение добавления поля:\n\n{summary}",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

@router.callback_query(CreateServiceType.waiting_for_confirmation, F.data.in_(["confirm_field", "cancel_field"]))
async def process_field_confirmation(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        service_type_id = data.get("service_type_id")
        if callback.data == "confirm_field":
            current_field = data.get("current_field", {})
            fields = db.get_service_type_fields(service_type_id)
            order_position = len(fields) + 1
            db.add_service_type_field(
                service_type_id=service_type_id,
                name=current_field.get("name"),
                name_for_user=current_field.get("label"),
                field_type=current_field.get("type"),
                item_for_select=",".join(current_field.get("options", [])),
                is_required=current_field.get("required", False),
                order_position=order_position
            )
            await callback.message.edit_text("✅ Поле успешно добавлено!")
        else:
            await callback.message.edit_text("❌ Добавление поля отменено.")
        
        data = await state.get_data()
        service_type_id = data.get("service_type_id")
        name = data.get("name")
        price_level = data.get("price_level")
        fields = db.get_service_type_fields(service_type_id)
        price_str = "Десятки тысяч рублей" if price_level == 1 else "Тысячи рублей"
        await state.update_data(current_field={})
        await state.set_state(CreateServiceType.management)
        await callback.message.answer(
            f"🛠 Панель управления типом услуги:\n"
            f"Название: {name}\n"
            f"Уровень цены: {price_str}\n\n"
            f"{get_fields_summary(fields)}",
            reply_markup=get_fields_keyboard(len(fields), service_type_id)
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("delete_last_field_"))
async def delete_last_field(callback: CallbackQuery, state: FSMContext):
    try:
        service_type_id = int(callback.data.split("_")[2])
        fields = db.get_service_type_fields(service_type_id)
        
        if fields:
            # Предполагается, что в базе реализована функция для удаления последнего поля
            if db.delete_last_service_type_field(service_type_id):
                fields = db.get_service_type_fields(service_type_id)
                data = await state.get_data()
                await callback.message.edit_text(
                    f"🛠 Панель управления типом услуги:\n"
                    f"Название: {data.get('name')}\n"
                    f"Уровень цены: {'Десятки тысяч рублей' if data.get('price_level') == 1 else 'Тысячи рублей'}\n\n"
                    f"{get_fields_summary(fields)}",
                    reply_markup=get_fields_keyboard(len(fields), service_type_id)
                )
            else:
                await callback.answer("❌ Не удалось удалить поле", show_alert=True)
        else:
            await callback.answer("❌ Нет полей для удаления", show_alert=True)
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "finish_editing")
async def finish_editing(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.edit_text(
            "✅ Редактирование типа услуги завершено.",
            reply_markup=admin_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "back")
async def handle_back(callback: CallbackQuery, state: FSMContext):
    try:
        current_state = await state.get_state()
        data = await state.get_data()
        service_type_id = data.get("service_type_id")
        if current_state in [CreateServiceType.waiting_for_name]:
            await state.clear()
            await callback.message.edit_text(
                "Действие отменено",
                reply_markup=admin_keyboard()
            )
        else:
            if service_type_id:
                name = data.get("name")
                price_level = data.get("price_level")
                fields = db.get_service_type_fields(service_type_id)
                price_str = "Десятки тысяч рублей" if price_level == 1 else "Тысячи рублей"
                await state.set_state(CreateServiceType.management)
                await callback.message.edit_text(
                    f"🛠 Панель управления типом услуги:\n"
                    f"Название: {name}\n"
                    f"Уровень цены: {price_str}\n\n"
                    f"{get_fields_summary(fields)}",
                    reply_markup=get_fields_keyboard(len(fields), service_type_id)
                )
            else:
                await state.clear()
                await callback.message.edit_text(
                    "Действие отменено",
                    reply_markup=admin_keyboard()
                )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "admin_menu")
async def return_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.edit_text(
            "👨‍💼 Админ-панель",
            reply_markup=admin_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Произошла ошибка: {str(e)}", show_alert=True)