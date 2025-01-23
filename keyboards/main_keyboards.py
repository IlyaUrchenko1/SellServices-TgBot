from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def to_home_keyboard():
    keyboard = InlineKeyboardBuilder()
    
    keyboard.add(InlineKeyboardButton(text="Вернуться домой 🏠", callback_data="go_to_home"))
    
    return keyboard.as_markup()

def back_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой Назад"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    return keyboard.as_markup()

def back_to_categories_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой возврата к категориям"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_categories"))
    return keyboard.as_markup()

def back_to_services_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой возврата к списку услуг"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 К списку услуг", callback_data="back_to_services"))
    return keyboard.as_markup()
