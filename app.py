import asyncio
import os
import glob
import sqlite3
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.enums import ChatMemberStatus
from pypdf import PdfReader
from openpyxl import Workbook

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8502485759:AAFI162SX0G02OK7aPuEbmL0ubkrdQuRtH0")
PDF_DIR = "./pdftest"
DB_PATH = "./users.db"
EXPORT_PATH = "./users_export.xlsx"

CHANNEL_USERNAME = "@mezontest"  # bot shu kanalda admin bo'lishi shart
CHANNEL_LINK = "https://t.me/mezontest"

# Admin qilib belgilamoqchi bo'lgan Telegram ID'laringizni shu yerga yozing
# .env orqali: ADMIN_IDS=111111,222222
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "8258695928,1743070073").split(",") if x.strip().isdigit()}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------------------------------------------------------------------
# Baza
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            phone_number TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_user(user_id: int, full_name: str, username: str, phone_number: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO users (user_id, full_name, username, phone_number, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = excluded.full_name,
            username = excluded.username,
            phone_number = excluded.phone_number
    """, (user_id, full_name, username or "", phone_number, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def has_phone(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0])


def get_all_users() -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT user_id, full_name, username, phone_number, created_at FROM users ORDER BY created_at"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def export_users_to_excel() -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Users"
    ws.append(["User ID", "F.I.Sh", "Username", "Telefon raqam", "Sana"])

    for user_id, full_name, username, phone_number, created_at in get_all_users():
        ws.append([user_id, full_name, f"@{username}" if username else "", phone_number, created_at])

    wb.save(EXPORT_PATH)
    return EXPORT_PATH


# ---------------------------------------------------------------------------
# PDF / metadata
# ---------------------------------------------------------------------------

def find_pdf_file(file_id: str) -> str | None:
    """
    Fayl nomi ikki xil formatda bo'lishi mumkin:
    123456.pdf yoki 123456-FIO.pdf
    """
    exact = os.path.join(PDF_DIR, f"{file_id}.pdf")
    if os.path.exists(exact):
        return exact

    matches = glob.glob(os.path.join(PDF_DIR, f"{file_id}-*.pdf"))
    return matches[0] if matches else None


def parse_custom_caption(raw: str) -> tuple[str, str]:
    """
    "ID:101033,SHERMAMATOVA MOHLAROYIM G'IYOSIDDIN QIZI" -> ("101033", "SHERMAMATOVA ...")
    """
    id_part, _, fio_part = raw.partition(",")
    id_value = id_part.split(":", 1)[-1].strip()
    fio_value = fio_part.strip()
    return id_value, fio_value


def format_caption(id_value: str, fio_value: str) -> str:
    if not id_value and not fio_value:
        return "Qo'shimcha ma'lumotlar topilmadi"
    return f"ID: {id_value}\nFIO: {fio_value}"


# ---------------------------------------------------------------------------
# Klaviaturalar
# ---------------------------------------------------------------------------

def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanalga a'zo bo'lish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
    ])


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Bazani Excelga yuklab olish", callback_data="export_excel")],
    ])


# ---------------------------------------------------------------------------
# Yordamchi tekshiruvlar
# ---------------------------------------------------------------------------

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


async def require_contact(message: Message) -> bool:
    if has_phone(message.from_user.id):
        return True
    await message.answer(
        "Davom etish uchun telefon raqamingizni ulashing:",
        reply_markup=contact_keyboard(),
    )
    return False


# ---------------------------------------------------------------------------
# Handlerlar
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not await require_subscription(message):
        return
    if not await require_contact(message):
        return
    await message.answer(
        "Salom! PDF faylni olish uchun uning ID raqamini yuboring (masalan: 123456).",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi.")
        if not has_phone(callback.from_user.id):
            await callback.message.answer(
                "Davom etish uchun telefon raqamingizni ulashing:",
                reply_markup=contact_keyboard(),
            )
        else:
            await callback.message.answer("Endi ID raqamini yuboring.")
    else:
        await callback.answer("Siz hali kanalga a'zo bo'lmagansiz.", show_alert=True)


@dp.message(F.contact)
async def handle_contact(message: Message):
    contact = message.contact

    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer("Iltimos, faqat o'zingizning raqamingizni yuboring.")
        return

    save_user(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        phone_number=contact.phone_number,
    )

    await message.answer(
        "Rahmat! Endi PDF faylni olish uchun ID raqamini yuboring (masalan: 123456).",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Admin panel:", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "export_excel")
async def export_excel_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Sizga ruxsat yo'q.", show_alert=True)
        return

    path = export_users_to_excel()
    await callback.message.answer_document(
        document=FSInputFile(path),
        caption=f"Jami foydalanuvchilar: {len(get_all_users())}",
    )
    await callback.answer()


@dp.message(F.text.regexp(r"^\d+$"))
async def handle_id(message: Message):
    if not await require_subscription(message):
        return
    if not await require_contact(message):
        return

    file_id = message.text.strip()
    filepath = find_pdf_file(file_id)

    if not filepath:
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
    if not await require_contact(message):
        return
    await message.answer("Iltimos, fayl ID raqamini yuboring (masalan: 123456).")


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())