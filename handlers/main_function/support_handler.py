from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.main_keyboards import to_home_keyboard, back_keyboard

router = Router(name='support_handler')

class SupportState(StatesGroup):
    waiting_for_question = State()
    waiting_for_answer_for_user = State()

@router.message(F.text == "👨‍🦰 Поддержка")
async def support_command(message: Message):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Связаться", callback_data='ask_a_issue'))
    keyboard.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="go_to_home"))
    
    await message.answer(
        """
        🧑‍💻 Часто задаваемые вопросы:

        **Сюда можно вставить любой текст по вашему желанию**
        """,
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        "Если у вас остались вопросы, нажмите на кнопку ниже, чтобы связаться с поддержкой.",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data == "ask_a_issue")
async def ask_to_helper(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="go_to_home"))
    
    await callback.message.edit_text(
        "Введите ваш вопрос, и он будет передан в службу поддержки.",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(SupportState.waiting_for_question)
    await callback.answer()

@router.message(SupportState.waiting_for_question)
async def process_question(message: Message, state: FSMContext):
    group_chat_id = -1002464551959  # ID группы для пересылки вопросов
    
    if message.photo:
        await message.answer(
            "К сожалению, нельзя пока-что отправлять фото. Отправьте только текст, пожалуйста.",
            reply_markup=back_keyboard()
        )
        return

    issue_text = message.text if message.text else "None"
    
    try:
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="Ответить", callback_data=f"answer_{message.from_user.id}"))
        
        await message.bot.send_message(
            chat_id=group_chat_id,
            text=f"Вопрос от пользователя {message.from_user.full_name} (@{message.from_user.username}):\n\n{issue_text}",
            reply_markup=keyboard.as_markup()
        )
        
        await message.answer(
            "Ваш вопрос был отправлен в службу поддержки. Мы ответим вам в ближайшее время.",
            reply_markup=to_home_keyboard()
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(
            "🤖 Упс! Произошла ошибка. Мы уже ее исправляем, спасибо за понимание! ❤️",
            reply_markup=to_home_keyboard()
        )
        print(f"Ошибка в process_question: {e}")

@router.callback_query(F.data.startswith("answer_"))
async def handle_admin_answer_callback(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.data.split("_")[1]
        await state.update_data(id_for_answer=user_id)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="back"))
        
        await callback.message.edit_text(
            "Введите ответ для пользователя",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(SupportState.waiting_for_answer_for_user)
        await callback.answer()
        
    except Exception as e:
        await callback.message.edit_text(
            "🤖 Упс! Произошла ошибка. Мы уже ее исправляем, спасибо за понимание! ❤️",
            reply_markup=to_home_keyboard()
        )
        print(f"Ошибка в handle_admin_answer_callback: {e}")

@router.message(SupportState.waiting_for_answer_for_user)
async def process_answer(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        user_id = data.get("id_for_answer")

        if not user_id:
            await message.answer(
                "❌ Не удалось получить ID пользователя для ответа.",
                reply_markup=to_home_keyboard()
            )
            return

        await message.bot.send_message(
            chat_id=user_id,
            text=f"Ответ от поддержки:\n{message.text}"
        )
        
        await message.answer(
            "✅ Ответ успешно отправлен пользователю.",
            reply_markup=to_home_keyboard()
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(
            "🤖 Упс! Произошла ошибка при отправке ответа.",
            reply_markup=to_home_keyboard()
        )
        print(f"Ошибка в process_answer: {e}")
