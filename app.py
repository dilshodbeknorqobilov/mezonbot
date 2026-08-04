import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.enums import ChatMemberStatus
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8502485759:AAFI162SX0G02OK7aPuEbmL0ubkrdQuRtH0")
PDF_DIR = "/pdftest"

CHANNEL_USERNAME = "@mezontest"  # bot shu kanalda admin bo'lishi shart
CHANNEL_LINK = "https://t.me/mezontest"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def format_metadata(metadata) -> str:
    if not metadata:
        return "Metadata topilmadi."

    lines = [f"{key.lstrip('/')}: {value}" for key, value in metadata.items()]
    return "\n".join(lines) if lines else "Metadata topilmadi."


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanalga a'zo bo'lish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
    ])


async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except Exception as e:
        logging.error(f"Obuna tekshirishda xato: {e}")
        return False


async def require_subscription(message: Message) -> bool:
    if await is_subscribed(message.from_user.id):
        return True
    await message.answer(
        "Botdan foydalanish uchun avval quyidagi kanalga a'zo bo'ling:",
        reply_markup=subscribe_keyboard(),
    )
    return False


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not await require_subscription(message):
        return
    await message.answer("Salom! PDF faylni olish uchun uning ID raqamini yuboring (masalan: 123).")


@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi. Endi ID raqamini yuboring.")
    else:
        await callback.answer("Siz hali kanalga a'zo bo'lmagansiz.", show_alert=True)


@dp.message(F.text.regexp(r"^\d+$"))
async def handle_id(message: Message):
    if not await require_subscription(message):
        return

    file_id = message.text.strip()
    filepath = os.path.join(PDF_DIR, f"{file_id}.pdf")

    if not os.path.exists(filepath):
        await message.answer(f"{file_id}.pdf topilmadi.")
        return

    try:
        with open(filepath, "rb") as f:
            reader = PdfReader(f)
            caption = format_metadata(reader.metadata)
    except Exception as e:
        await message.answer(f"Faylni o'qishda xato: {e}")
        return

    if len(caption) > 1024:
        # Telegram caption limiti 1024 belgi, shuning uchun uzun bo'lsa alohida xabar bilan yuboramiz
        await message.answer_document(document=FSInputFile(filepath))
        await message.answer(caption)
    else:
        await message.answer_document(document=FSInputFile(filepath), caption=caption)


@dp.message()
async def fallback(message: Message):
    if not await require_subscription(message):
        return
    await message.answer("Iltimos, fayl ID raqamini yuboring (masalan: 123).")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())