import os
import base64
import asyncio
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from groq import AsyncGroq

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

users_set = set()
total_messages = 0

SYSTEM_PROMPT = (
    "Ты — дружелюбный, весёлый и умный ИИ-помощник жителей Сыктывкара. "
    "Любишь поболтать, пошутить и поддержать разговор на любые темы — от учёбы до повседневных дел. "
    "Отвечай кратко, по делу, живым русским языком, без символов $ и **. "
    "СТРОГОЕ ПРАВИЛО ПО АВТОБУСАМ СЫКТЫВКАРА: когда спрашивают про транспорт или цены, никогда не выдумывай номера маршрутов и телефоны! "
    "Актуальная стоимость проезда в Сыктывкаре (с 1 ноября 2026 года): "
    "маршруты Комиавтотранса (№ 1, 1м, 17м, 18м, 54м, 23, 23д, 25, 26) — 54 руб. по карте и 56 руб. наличными; "
    "остальные городские маршруты — 47-48 руб. по карте и 50 руб. наличными; "
    "безлимитный проездной на 30 дней — 2200 руб.; при оплате картой или брелоком Бур туй! действует бесплатная пересадка в течение часа на магистральных маршрутах. "
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
        [types.InlineKeyboardButton(text="📅 Расписание всех автобусов", url="https://komiavtotrans.ru")],
        [types.InlineKeyboardButton(text="📍 Автобусы на карте онлайн", url="https://yandex.ru")],
        [types.InlineKeyboardButton(text="💳 Стоимость проезда", callback_data="prices")],
        [types.InlineKeyboardButton(text="🛣 Междугородние и дальние рейсы", url="https://avtovokzaly.ru")]
    ])
    await message.answer(
        "Привет! Я твой умный городской помощник по Сыктывкару 🚌\n"
        "Жми на кнопки ниже, напиши любой вопрос или пришли фото — поболтаем и во всём разберёмся!",
        reply_markup=kb
    )

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

            vision_models = [m for m in all_ids if "llama-4" in m.lower() or "vision" in m.lower()]
            chosen_model = next(iter(vision_models), "meta-llama/llama-4-scout-17b-16e-instruct")

            user_content = [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
        else:
            if not message.text:
                await message.answer("Пока я понимаю только текстовые сообщения и фотографии 😊")
                return
            good_models = [m for m in all_ids if any(k in m.lower() for k in ("gpt-oss-120b", "llama-4", "qwen", "70b")) and not any(w in m.lower() for w in bad_words)]
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
    return web.Response(text="Bot is running!")

async def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        return
    async with ClientSession() as session:
        while True:
            await asyncio.sleep(600)
            try:
                async with session.get(url) as resp:
                    pass
            except Exception:
                pass

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    asyncio.create_task(keep_alive())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
