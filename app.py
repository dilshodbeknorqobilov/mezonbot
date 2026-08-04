import asyncio
import os
import shutil
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
PDF_DIR = "./pdftest"
TODAY_DIR = "./today"

CHANNEL_USERNAME = "@mezontest"  # bot shu kanalda admin bo'lishi shart
CHANNEL_LINK = "https://t.me/mezontest"

os.makedirs(TODAY_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def parse_custom_caption(raw: str) -> tuple[str, str]:
    """
    "ID:101033,SHERMAMATOVA MOHLAROYIM G'IYOSIDDIN QIZI" -> ("101033", "SHERMAMATOVA ...")
    """
    id_part, _, fio_part = raw.partition(",")
    id_value = id_part.split(":", 1)[-1].strip()
    fio_value = fio_part.strip()
    return id_value, fio_value


def sanitize_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join(ch for ch in name if ch not in invalid_chars)
    return cleaned.strip() or "fayl"


def format_caption(id_value: str, fio_value: str) -> str:
    if not id_value and not fio_value:
        return "Qo'shimcha ma'lumotlar topilmadi"
    return f"ID: {id_value}\nFIO: {fio_value}"


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
        await message.answer(f"{file_id} ID bilan ma'lumot topilmadi.")
        return

    try:
        with open(filepath, "rb") as f:
            reader = PdfReader(f)
            raw_caption = reader.metadata.get("/Custom_Caption", "") if reader.metadata else ""
    except Exception as e:
        await message.answer(f"Faylni o'qishda xato: {e}")
        return

    id_value, fio_value = parse_custom_caption(str(raw_caption)) if raw_caption else ("", "")
    caption = format_caption(id_value, fio_value)

    # today papkasiga FIO nomi bilan nusxa saqlash
    fio_filename = sanitize_filename(fio_value) if fio_value else file_id
    dest_path = os.path.join(TODAY_DIR, f"{fio_filename}.pdf")
    shutil.copyfile(filepath, dest_path)

    if len(caption) > 1024:
        # Telegram caption limiti 1024 belgi, shuning uchun uzun bo'lsa alohida xabar bilan yuboramiz
        await message.answer_document(document=FSInputFile(dest_path))
        await message.answer(caption)
    else:
        await message.answer_document(document=FSInputFile(dest_path), caption=caption)


@dp.message()
async def fallback(message: Message):
    if not await require_subscription(message):
        return
    await message.answer("Iltimos, fayl ID raqamini yuboring (masalan: 123).")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())