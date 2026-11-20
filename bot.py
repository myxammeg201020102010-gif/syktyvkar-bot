import os
import base64
import asyncio
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from groq import AsyncGroq

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = (
    "Ты — дружелюбный, весёлый и умный ИИ-помощник жителей Сыктывкара. "
    "Отвечай строго на грамотном русском языке, кратко, по делу, с лёгким юмором и без воды. "
    "Никогда не используй символы $ и ** в ответах."
)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📅 Расписание всех автобусов", url="https://komiavtotrans.ru")],
        [types.InlineKeyboardButton(text="📍 Автобусы на карте онлайн", url="https://yandex.ru")],
        [types.InlineKeyboardButton(text="🛣 Междугородние и дальние рейсы", url="https://avtovokzaly.ru")]
    ])
    await message.answer(
        "Привет! Я твой умный городской помощник по Сыктывкару 🚌\n"
        "Жми на кнопки с расписанием ниже, напиши любой вопрос или пришли фото — во всём разберёмся!",
        reply_markup=kb
    )

@dp.message()
async def ai_reply(message: types.Message):
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
