import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from groq import AsyncGroq

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = (
    "Ты — дружелюбный, весёлый и отзывчивый ИИ-помощник жителей Сыктывкара. "
    "Общайся просто, живо, тепло и с лёгким юмором, без занудства и длинных лекций. "
    "Помогай пользователю с любыми вопросами: от автобусов Сыктывкара до учёбы и повседневных дел."
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
        "Жми на кнопки ниже или просто напиши мне любой вопрос — поболтаем и во всём разберёмся!",
        reply_markup=kb
    )

@dp.message()
async def ai_reply(message: types.Message):
    try:
        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            model="llama-3.3-70b-versatile",
        )
        await message.answer(chat_completion.choices[0].message.content)
    except Exception:
        await message.answer("Ой, я немного задумался 😅 Попробуй написать свой вопрос ещё раз чуть позже!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
