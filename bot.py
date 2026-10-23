import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    Update,
)

# ---------- Настройки ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])
PORT = int(os.environ.get("PORT", 10000))
# Публичный адрес сервиса на Render, например:
# https://neurointelegence-bot.onrender.com
BASE_URL = os.environ["BASE_URL"].rstrip("/")
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "render-webhook")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

WELCOME_TEXT = (
    "Здравствуйте! Это бот «Neurointelegence» — разработка Telegram-ботов, "
    "AI-агентов и практических ИИ-решений для бизнеса.\n\n"
    "Выберите, что вас интересует, ниже."
)

MENU_TEXT = (
    "📋 Что могу реализовать:\n"
    "• Разработка чат-ботов Telegram, AI-агентов\n"
    "• Приём заявок от клиентов через Telegram\n"
    "• Меню с услугами, описанием и контактами\n"
    "• Ответы на частые вопросы\n"
    "• Запись клиентов и приём заказов\n"
    "• Уведомления о новых заявках\n"
    "• Подключение ИИ для работы с базой знаний — по согласованию\n"
    "• Интеграции с внешними сервисами — в зависимости от задачи\n\n"
    "Чтобы обсудить вашу задачу — нажмите /start и оставьте заявку."
)

FAQ_TEXT = (
    "📋 Порядок работы, сроки, стоимость:\n\n"
    "Сначала обсуждаем вашу задачу, затем согласуем функции, стоимость "
    "и сроки. После этого разрабатываю и тестирую решение, показываю "
    "результат и передаю готового бота. Условия дальнейшей поддержки "
    "согласуем отдельно.\n\n"
    "По срокам: простой бот — от пары дней, с ИИ и интеграциями — "
    "зависит от сложности и обсуждается отдельно.\n\n"
    "По стоимости: согласуем после обсуждения задачи и объёма работ, "
    "до старта разработки.\n\n"
    "Остались вопросы — жмите /start и пишите в заявке."
)

PROJECT_TYPES = [
    "Чат-бот Telegram",
    "AI-агент",
    "Интеграция с CRM/сервисами",
    "Другое",
]


class Lead(StatesGroup):
    name = State()
    contact = State()
    project_type = State()
    task = State()


def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="new_lead")],
            [
                InlineKeyboardButton(text="📋 Услуги", callback_data="show_menu"),
                InlineKeyboardButton(text="❓ Частые вопросы", callback_data="show_faq"),
            ],
        ]
    )


def project_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t)] for t in PROJECT_TYPES],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    source = command.args
    if source:
        await state.update_data(source=source)
    await message.answer(WELCOME_TEXT, reply_markup=start_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(MENU_TEXT)


@router.message(Command("faq"))
async def cmd_faq(message: Message):
    await message.answer(FAQ_TEXT)


@router.callback_query(F.data == "new_lead")
async def start_lead(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Lead.name)
    await callback.message.answer("Как к вам обращаться? Напишите имя.")
    await callback.answer()


@router.callback_query(F.data == "show_menu")
async def show_menu(callback: CallbackQuery):
    await callback.message.answer(MENU_TEXT)
    await callback.answer()


@router.callback_query(F.data == "show_faq")
async def show_faq(callback: CallbackQuery):
    await callback.message.answer(FAQ_TEXT)
    await callback.answer()


@router.message(Lead.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Lead.contact)
    await message.answer(
        "Укажите телефон или username в Telegram для связи "
        "(или отправьте контакт кнопкой).",
        reply_markup=contact_kb(),
    )


@router.message(Lead.contact, F.contact)
async def get_contact_phone(message: Message, state: FSMContext):
    await state.update_data(contact=message.contact.phone_number)
    await ask_project_type(message, state)


@router.message(Lead.contact)
async def get_contact_text(message: Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await ask_project_type(message, state)


async def ask_project_type(message: Message, state: FSMContext):
    await state.set_state(Lead.project_type)
    await message.answer("Какой продукт нужен?", reply_markup=project_type_kb())


@router.message(Lead.project_type)
async def get_project_type(message: Message, state: FSMContext):
    await state.update_data(project_type=message.text)
    await state.set_state(Lead.task)
    await message.answer(
        "Опишите кратко, какую задачу хотите автоматизировать.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Lead.task)
async def get_task(message: Message, state: FSMContext):
    data = await state.update_data(task=message.text)
    await state.clear()

    user = message.from_user
    source_line = f"\nИсточник: {data.get('source')}" if data.get("source") else ""
    summary = (
        "🆕 Новая заявка — Neurointelegence\n"
        f"Имя: {data.get('name')}\n"
        f"Контакт: {data.get('contact')}\n"
        f"Продукт: {data.get('project_type')}\n"
        f"Задача: {data.get('task')}\n"
        f"Telegram: @{user.username} (id {user.id})"
        f"{source_line}"
    )
    await bot.send_message(ADMIN_CHAT_ID, summary)

    await message.answer(
        "Спасибо! Заявка принята. Обычно отвечаю в течение дня — "
        "обсудим функции, стоимость и сроки."
    )


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена.", reply_markup=ReplyKeyboardRemove())


# ---------- Webhook ----------
async def handle_webhook(request: web.Request):
    # Проверка секрета Telegram (защита от чужих запросов на этот URL)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        return web.Response(status=403, text="forbidden")

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


async def handle_ping(request: web.Request):
    return web.Response(text="Bot is running")


async def on_startup(app: web.Application):
    await bot.set_webhook(
        url=f"{BASE_URL}{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )
    logging.info("Webhook set to %s%s", BASE_URL, WEBHOOK_PATH)


async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await bot.session.close()


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
