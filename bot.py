import os
import base64
import asyncio
from datetime import datetime, timezone, timedelta
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from groq import AsyncGroq

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

users_set = set()
total_messages = 0

MSK = timezone(timedelta(hours=3))

SCHEDULE_MON = [
    ("08:15", "09:00", "Классный час"),
    ("09:00", "09:20", "Завтрак (перемена 20 мин)"),
    ("09:20", "10:05", "1 урок (I пара)"),
    ("10:15", "11:00", "2 урок (I пара)"),
    ("11:10", "11:55", "3 урок (II пара)"),
    ("11:55", "12:35", "Обед (перемена 40 мин)"),
    ("12:35", "13:20", "4 урок (II пара)"),
    ("13:30", "14:15", "5 урок (III пара)"),
    ("14:25", "15:10", "6 урок (III пара)"),
    ("15:10", "15:30", "Полдник (перемена 20 мин)"),
    ("15:30", "16:15", "7 урок (IV пара)"),
    ("16:25", "17:10", "8 урок (IV пара)"),
]

SCHEDULE_TUE_FRI = [
    ("08:00", "08:10", "Десятиминутка для руководителей групп"),
    ("08:10", "08:55", "1 урок (I пара)"),
    ("08:55", "09:15", "Завтрак (перемена 20 мин)"),
    ("09:15", "10:00", "2 урок (I пара)"),
    ("10:10", "10:55", "3 урок (II пара)"),
    ("11:05", "11:50", "4 урок (II пара)"),
    ("11:50", "12:30", "Обед (перемена 40 мин)"),
    ("12:30", "13:15", "5 урок (III пара)"),
    ("13:25", "14:10", "6 урок (III пара)"),
    ("14:20", "15:05", "7 урок (IV пара)"),
    ("15:05", "15:25", "Полдник (перемена 20 мин)"),
    ("15:25", "16:10", "8 урок (IV пара)"),
    ("16:20", "17:05", "9 урок (V пара)"),
    ("17:15", "18:00", "10 урок (V пара)"),
    ("18:10", "18:55", "11 урок (VI пара)"),
    ("19:05", "19:50", "12 урок (VI пара)"),
]

def to_mins(t_str):
    h, m = map(int, t_str.split(":"))
    return h * 60 + m

def get_bell_status():
    now = datetime.now(MSK)
    weekday = now.weekday()
    cur_mins = now.hour * 60 + now.minute
    time_str = now.strftime("%H:%M")

    if weekday in (5, 6):
        return f"Сейчас {time_str} (выходной день), занятий по расписанию нет 🎉"

    sched = SCHEDULE_MON if weekday == 0 else SCHEDULE_TUE_FRI
    day_name = "понедельника" if weekday == 0 else "вторника–пятницы"

    first_item = next(iter(sched))
    last_item = next(reversed(sched))
    first_start = to_mins(first_item[0])
    last_end = to_mins(last_item[1])

    if cur_mins < first_start:
        diff = first_start - cur_mins
        return f"🕒 Сейчас {time_str} (расписание {day_name}).\nДо начала первого занятия ({first_item[0]}) осталось {diff} мин."

    if cur_mins >= last_end:
        return f"🕒 Сейчас {time_str}. Все занятия на сегодня уже закончились! 🎉"

    for i, (start_s, end_s, name) in enumerate(sched):
        s_m = to_mins(start_s)
        e_m = to_mins(end_s)
        if s_m <= cur_mins < e_m:
            left = e_m - cur_mins
            return f"🔔 Сейчас {time_str} ({day_name}).\nИдёт: {name} ({start_s}–{end_s}).\nДо звонка осталось: {left} мин."
        if i + 1 < len(sched):
            next_item = sched[i + 1]
            next_s = to_mins(next_item[0])
            if e_m <= cur_mins < next_s:
                left = next_s - cur_mins
                return f"☕ Сейчас {time_str} — перемена ({end_s}–{next_item[0]}).\nДо звонка на «{next_item[2]}» осталось: {left} мин."

    return f"🕒 Сейчас {time_str}."

SYSTEM_PROMPT = (
    "Ты — дружелюбный, весёлый и умный ИИ-помощник жителей Сыктывкара. "
    "Любишь поболтать, пошутить и поддержать разговор на любые темы — от учёбы до повседневных дел. "
    "Отвечай кратко, по делу, живым русским языком, без символов $ и **. "
    "СТРОГОЕ ПРАВИЛО ПО АВТОБУСАМ СЫКТЫВКАРА: когда спрашивают про транспорт или цены, никогда не выдумывай номера маршрутов и телефоны! "
    "Актуальная стоимость проезда в Сыктывкаре: "
    "маршруты Комиавтотранса (№ 1, 1м, 17м, 18м, 54м, 23, 23д, 25, 26) — 54 руб. по карте и 56 руб. наличными; "
    "остальные городские маршруты — 47-48 руб. по карте и 50 руб. наличными; "
    "безлимитный проездной на 30 дней — 2200 руб.; по карте/брелоку Бур туй! действует бесплатная пересадка в течение часа. "
    "Реальные основные маршруты Сыктывкара: "
    "В Эжву: № 18м (СЛПК — Ж/д вокзал — Центр — Пл. Габова), № 54м (СЛПК — Центр — Ж/д вокзал), № 108 (Автовокзал — Эжва — СЛПК), № 11 (Бумажников — Ухтинское шоссе — Дырнос). "
    "По городу: № 1 (ТЦ Макси — Центр — Лесозавод), № 3 (Орбита — Центр — Ж/д вокзал), № 4 (Орбита — Центр — Кировский парк), "
    "№ 5 (Ж/д вокзал — Центр — Дырнос), № 15 (Орбита — Центр — Красная Гора), № 17м (Орбита — Центр — Ж/д вокзал — Лесозавод), "
    "№ 19 (Орбита — Центр — В. Чов), № 20 (Орбита — Центр — Кочпон), № 23 (Орбита — Центр — Ж/д вокзал — Сосновая поляна), "
    "№ 25 (ТЦ Макси — Центр — Выльгорт), № 28 (Автостанция — Орбита — Центр — Автовокзал), № 44 (Орбита — Центр — ТРЦ Макси — Лесозавод), "
    "№ 101 (Автовокзал — Выльгорт), № 174 (Автовокзал — Выльгорт — Птицефабрика)."
)

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    await message.answer(
        f"📊 Статистика бота с момента запуска:\n\n"
        f"👥 Уникальных пользователей: {len(users_set)}\n"
        f"💬 Всего сообщений обработано: {total_messages}"
    )

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    global total_messages
    users_set.add(message.from_user.id)
    total_messages += 1
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔔 Сколько до звонка?", callback_data="bell")],
        [types.InlineKeyboardButton(text="📅 Расписание всех автобусов", url="https://komiavtotrans.ru")],
        [types.InlineKeyboardButton(text="📍 Автобусы на карте онлайн", url="https://yandex.ru")],
        [types.InlineKeyboardButton(text="💳 Стоимость проезда", callback_data="prices")],
        [types.InlineKeyboardButton(text="🛣 Междугородние и дальние рейсы", url="https://avtovokzaly.ru")]
    ])
    await message.answer(
        "Привет! Я твой умный городской помощник по Сыктывкару 🚌\n"
        "Жми на кнопки ниже или просто спроси меня про автобусы, звонок или любые дела!",
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data == "bell")
async def show_bell(callback: types.CallbackQuery):
    await callback.message.answer(get_bell_status())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "prices")
async def show_prices(callback: types.CallbackQuery):
    await callback.message.answer(
        "💳 Стоимость проезда в автобусах Сыктывкара:\n\n"
        "• Маршруты «Комиавтотранса» (№ 1, 1м, 17м, 18м, 54м, 23, 23д, 25, 26):\n"
        "  54 ₽ по карте / 56 ₽ наличными\n\n"
        "• Остальные городские маршруты:\n"
        "  47–48 ₽ по карте / 50 ₽ наличными\n\n"
        "• Безлимитный проездной на 30 дней: 2200 ₽\n"
        "• По карте/брелоку «Бур туй!» действует бесплатная пересадка в течение 1 часа."
    )
    await callback.answer()

@dp.message()
async def ai_reply(message: types.Message):
    global total_messages
    users_set.add(message.from_user.id)
    total_messages += 1

    text_lower = (message.text or "").lower()
    if any(w in text_lower for w in ("до звонка", "звонок", "какая пара", "какой урок", "когда перемена", "конец пары", "кончится пара")):
        await message.answer(get_bell_status())
        return

    try:
        models_list = await groq_client.models.list()
        all_ids = [m.id for m in models_list.data]
        bad_words = ("whisper", "guard", "tts", "orpheus", "canopylabs", "safeguard", "compound", "allam")

        if message.photo:
            photo = next(reversed(message.photo))
            file_info = await bot.get_file(photo.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            b64_img = base64.b64encode(file_bytes.read()).decode("utf-8")
            caption = message.caption or "Что на этом фото? Ответь кратко на русском языке."

            vision_models = [m for m in all_ids if "vision" in m.lower() or "maverick" in m.lower() or "scout" in m.lower()]
            if not vision_models:
                await message.answer("Сейчас Groq временно отключил распознавание картинок на бесплатном тарифе, но текстом я отвечу на любой вопрос! 😊")
                return
            chosen_model = next(iter(vision_models))

            user_content = [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
        else:
            if not message.text:
                await message.answer("Пока я понимаю только текстовые сообщения 😊")
                return
            good_models = [m for m in all_ids if any(k in m.lower() for k in ("gpt-oss-120b", "qwen", "70b", "llama")) and not any(w in m.lower() for w in bad_words)]
            if not good_models:
                good_models = [m for m in all_ids if not any(w in m.lower() for w in bad_words)]
            chosen_model = next(iter(good_models))
            user_content = message.text

        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            model=chosen_model,
            max_tokens=1000,
        )
        first_choice = next(iter(chat_completion.choices))
        clean_text = first_choice.message.content.replace("**", "").replace("$", "")
        await message.answer(clean_text[:4000])
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def handle(request):
