import asyncio
import logging
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

# --- ENV ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PRIVACY_URL = os.getenv("PRIVACY_URL", "#").strip()
CONSENT_URL = os.getenv("CONSENT_URL", "#").strip()
OFFER_URL = os.getenv("OFFER_URL", "#").strip()
PAYMENT_URL = os.getenv("PAYMENT_URL", "#").strip()
MATERIALS_URL = os.getenv("MATERIALS_URL", "#").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0").strip() or 0)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Добавь BOT_TOKEN в .env")

# --- Helpers ---
PHONE_RE = re.compile(r"^\+?\d[\d\s\-\(\)]{7,}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def normalize_phone(s: str) -> str:
    return re.sub(r"[^\d+]", "", s.strip())

# --- Keyboards ---
kb_consent = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Даю согласие")]],
    resize_keyboard=True
)

kb_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Посмотреть программы")],
        [KeyboardButton(text="💳 Оформить подписку")],
        [KeyboardButton(text="🔁 В начало")],
    ],
    resize_keyboard=True
)

kb_programs = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💇‍♀️ Трихология и восстановление волос")],
        [KeyboardButton(text="🌺 Женское здоровье и гормональный баланс")],
        [KeyboardButton(text="🧒 Детское здоровье")],
        [KeyboardButton(text="🧠 Развитие речи и мозга у детей")],
        [KeyboardButton(text="🛡️ Кожа и иммунитет")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True
)

kb_subscribe = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💳 Оформить подписку")], [KeyboardButton(text="⬅️ В меню")]],
    resize_keyboard=True
)

kb_pay = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔗 Перейти к оплате")], [KeyboardButton(text="⬅️ В меню")]],
    resize_keyboard=True
)

kb_after_pay = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📎 Перейти к материалам")], [KeyboardButton(text="⬅️ В меню")]],
    resize_keyboard=True
)

# --- Scenario texts (из файла) ---
WELCOME_TEXT = (
    "Привет!\n"
    "Добро пожаловать в сообщество «Режим здоровья» — пространство, где специалисты и семьи объединяются ради главного — "
    "осознанного подхода к здоровью своей семьи.\n\n"
    "Здесь мы говорим простым языком о сложном: как сохранить здоровье, внутренний баланс и помочь детям развиваться гармонично.\n\n"
    "Ведущие проекта:\n"
    "Анна Абдуллина — врач-нутрициолог, трихолог, эксперт по женскому и детскому здоровью.\n"
    "Оксана Сафина — психолог, нейропедагог (нейропсихолог, логопед для детей раннего возраста), автор программ по развитию речи "
    "и мозга для детей.\n\n"
    "В сообществии вас ждут практические программы, разборы, поддержка и вдохновение — всё, чтобы здоровье стало вашей системой, "
    "а не случайностью."
)

CONSENT_TEXT = (
    "Чтобы мы могли записать ваши ответы и в дальнейшем иметь возможность связаться с вами,\n"
    "нам необходимо получить ваше согласие с:\n"
    f"• Политикой конфиденциальности: {PRIVACY_URL}\n"
    f"• Согласием на обработку персональных данных: {CONSENT_URL}\n\n"
    "Нажмите кнопку ниже:"
)

ABOUT_TEXT = (
    "Сообщество «Режим здоровья» — это безопасное пространство, где можно разобраться в вопросах здоровья, развития и воспитания детей — "
    "без хаоса, рекламы и лишней информации.\n\n"
    "Мы собрали всё, что помогает поддерживать баланс тела и эмоций, укреплять здоровье всей семьи и растить детей осознанно — системно, "
    "с научным подходом и человеческим языком.\n\n"
    "В подписке вы получите:\n"
    "• доступ к обучающим программам и записям курсов\n"
    "• практические гайды, схемы и чек-листы\n"
    "• разборы вопросов и материалы по темам сообщества\n\n"
    "Всё это — в одном месте, без спешки, с любовью к телу и здоровью."
)

SUBSCRIBE_TEXT = (
    "Нажмите кнопку «Оформить подписку», чтобы получить доступ к сообществу «Режим здоровья» — ко всем материалам, программам и поддержке специалистов.\n\n"
    "Для кого это сообщество:\n"
    "• для женщин, которые хотят восстановить здоровье, энергию и внутренний баланс\n"
    "• для мам, которые хотят помочь детям развиваться гармонично\n"
    "• для специалистов, которые стремятся помогать клиентам комплексно\n\n"
    "Подписка — ежемесячная.\n"
    "Отписаться можно в любой момент, без ограничений."
)

PAY_TEXT = (
    "Стоимость подписки:\n"
    "1 месяц — 1 499 ₽\n\n"
    "Перейдите к оплате по кнопке ниже.\n\n"
    "Оплачивая подписку, вы подтверждаете, что ознакомлены и соглашаетесь с условиями Публичной оферты и Политики конфиденциальности.\n"
    f"Оферта: {OFFER_URL}\n"
    f"Политика: {PRIVACY_URL}"
)

AFTER_PAY_TEXT = (
    "Добро пожаловать в сообщество «Режим здоровья»!\n\n"
    "Нажмите кнопку ниже:"
)

# Программы: описания можно заполнить позже
PROGRAM_DESCRIPTIONS = {
    "💇‍♀️ Трихология и восстановление волос": "Описание программы «Трихология и восстановление волос» (добавим текст вручную).",
    "🌺 Женское здоровье и гормональный баланс": "Описание программы «Женское здоровье и гормональный баланс» (добавим текст вручную).",
    "🧒 Детское здоровье": "Описание программы «Детское здоровье» (добавим текст вручную).",
    "🧠 Развитие речи и мозга у детей": "Описание программы «Развитие речи и мозга у детей» (добавим текст вручную).",
    "🛡️ Кожа и иммунитет": "Описание программы «Кожа и иммунитет» (добавим текст вручную).",
}

# --- FSM ---
class Flow(StatesGroup):
    waiting_consent = State()
    ask_name = State()
    ask_phone = State()
    ask_email = State()
    in_menu = State()


async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    async def go_to_start(m: Message, state: FSMContext):
        await state.clear()
        await m.answer(WELCOME_TEXT, reply_markup=ReplyKeyboardRemove())
        await m.answer(CONSENT_TEXT, reply_markup=kb_consent)
        await state.set_state(Flow.waiting_consent)

    @dp.message(CommandStart())
    async def start(m: Message, state: FSMContext):
        await go_to_start(m, state)

    @dp.message(F.text == "🔁 В начало")
    async def restart(m: Message, state: FSMContext):
        await go_to_start(m, state)

    # --- Consent ---
    @dp.message(Flow.waiting_consent, F.text == "✅ Даю согласие")
    async def consent_ok(m: Message, state: FSMContext):
        await state.set_state(Flow.ask_name)
        await m.answer(
            "Ответьте, пожалуйста, на несколько вопросов.\n"
            "Пожалуйста, будьте внимательными к правильности заполняемых данных.\n\n"
            "1 вопрос из 3:\nКак вас зовут?",
            reply_markup=ReplyKeyboardRemove()
        )

    @dp.message(Flow.waiting_consent)
    async def consent_only_button(m: Message):
        await m.answer("Пожалуйста, нажмите кнопку «✅ Даю согласие», чтобы продолжить.", reply_markup=kb_consent)

    # --- Contacts: name ---
    @dp.message(Flow.ask_name)
    async def got_name(m: Message, state: FSMContext):
        name = (m.text or "").strip()
        if len(name) < 2:
            await m.answer("Напишите, пожалуйста, имя (минимум 2 символа).")
            return
        await state.update_data(name=name)
        await state.set_state(Flow.ask_phone)
        await m.answer("Приятно познакомиться!\n\n2 вопрос из 3:\nВведите ваш номер телефона.")

    # --- Contacts: phone ---
    @dp.message(Flow.ask_phone)
    async def got_phone(m: Message, state: FSMContext):
        raw = (m.text or "").strip()
        if not PHONE_RE.match(raw):
            await m.answer("Похоже, номер введён некорректно. Пример: +7 999 123-45-67. Попробуйте ещё раз.")
            return
        phone = normalize_phone(raw)
        await state.update_data(phone=phone)
        await state.set_state(Flow.ask_email)
        await m.answer("Отлично, записали.\n\n3 вопрос из 3:\nВведите вашу почту.")

    # --- Contacts: email ---
    @dp.message(Flow.ask_email)
    async def got_email(m: Message, state: FSMContext):
        email = (m.text or "").strip()
        if not EMAIL_RE.match(email):
            await m.answer("Похоже, e-mail введён некорректно. Пример: name@gmail.com. Попробуйте ещё раз.")
            return

        await state.update_data(email=email)

        # Notify admin if needed
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
            data = await state.get_data()
            try:
                await bot.send_message(
                    ADMIN_CHAT_ID,
                    "🆕 Новая заявка (Режим здоровья)\n"
                    f"Имя: {data.get('name')}\n"
                    f"Телефон: {data.get('phone')}\n"
                    f"Email: {data.get('email')}\n"
                    f"TG: @{m.from_user.username or '—'} | id={m.from_user.id}"
                )
            except Exception as e:
                logging.warning(f"Не смог отправить админу: {e}")

        await state.set_state(Flow.in_menu)
        await m.answer(ABOUT_TEXT, reply_markup=kb_main)

    # --- Menu: programs ---
    @dp.message(Flow.in_menu, F.text == "📚 Посмотреть программы")
    async def programs(m: Message):
        await m.answer("Выберите направление 👇", reply_markup=kb_programs)

    @dp.message(Flow.in_menu, F.text.in_(list(PROGRAM_DESCRIPTIONS.keys())))
    async def program_detail(m: Message):
        await m.answer(PROGRAM_DESCRIPTIONS[m.text], reply_markup=kb_programs)

    @dp.message(Flow.in_menu, F.text == "⬅️ Назад")
    async def programs_back(m: Message):
        await m.answer("Возвращаю в меню 👇", reply_markup=kb_main)

    # --- Menu: subscribe ---
    @dp.message(Flow.in_menu, F.text == "💳 Оформить подписку")
    async def subscribe(m: Message):
        await m.answer(SUBSCRIBE_TEXT, reply_markup=kb_subscribe)

    @dp.message(Flow.in_menu, F.text == "⬅️ В меню")
    async def back_to_menu(m: Message):
        await m.answer("Меню 👇", reply_markup=kb_main)

    # --- Payment step ---
    @dp.message(Flow.in_menu, F.text == "💳 Оформить подписку")
    async def subscribe_again(m: Message):
        # (на случай повторного нажатия)
        await m.answer(SUBSCRIBE_TEXT, reply_markup=kb_subscribe)

    @dp.message(F.text == "💳 Оформить подписку")
    async def pay_info(m: Message, state: FSMContext):
        # Разрешаем нажимать из любых мест, но корректнее — из меню
        current = await state.get_state()
        if current != Flow.in_menu.state:
            await state.set_state(Flow.in_menu)

        await m.answer(PAY_TEXT, reply_markup=kb_pay)

    @dp.message(F.text == "🔗 Перейти к оплате")
    async def payment_link(m: Message, state: FSMContext):
        # Здесь можно заменить на Telegram Payments / ЮKassa / CloudPayments и т.п.
        await m.answer(f"Оплата по ссылке: {PAYMENT_URL}\n\nПосле оплаты нажмите «✅ Я оплатил(а)».", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅ Я оплатил(а)")], [KeyboardButton(text="⬅️ В меню")]],
            resize_keyboard=True
        ))
        if await state.get_state() != Flow.in_menu.state:
            await state.set_state(Flow.in_menu)

    @dp.message(F.text == "✅ Я оплатил(а)")
    async def after_payment(m: Message, state: FSMContext):
        await m.answer(AFTER_PAY_TEXT, reply_markup=kb_after_pay)
        if await state.get_state() != Flow.in_menu.state:
            await state.set_state(Flow.in_menu)

    @dp.message(F.text == "📎 Перейти к материалам")
    async def materials(m: Message, state: FSMContext):
        await m.answer(f"Материалы: {MATERIALS_URL}", reply_markup=kb_main)
        if await state.get_state() != Flow.in_menu.state:
            await state.set_state(Flow.in_menu)

    # --- Fallback ---
    @dp.message()
    async def fallback(m: Message, state: FSMContext):
        st = await state.get_state()
        if st == Flow.in_menu.state:
            await m.answer("Выберите действие кнопкой 👇", reply_markup=kb_main)
        elif st == Flow.waiting_consent.state:
            await m.answer("Пожалуйста, нажмите «✅ Даю согласие».", reply_markup=kb_consent)
        else:
            await m.answer("Напишите /start, чтобы начать заново.")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
