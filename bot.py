import asyncio
import logging
import os
import sqlite3

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

# ============ SOZLAMALAR ============
# Bot tokenini @BotFather dan oling va shu yerga yozing
# (yoki BOT_TOKEN environment variable orqali bering)
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")

# Admin(lar)ning Telegram ID raqami(lari), vergul bilan ajratilgan
# ID ni bilish uchun @userinfobot ga yozing
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

DB_PATH = "movies.db"
# =====================================


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            title TEXT,
            added_by INTEGER
        )
    """)
    conn.commit()
    conn.close()


def add_movie(code, file_id, file_type, title, added_by):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO movies (code, file_id, file_type, title, added_by) VALUES (?, ?, ?, ?, ?)",
        (code, file_id, file_type, title, added_by),
    )
    conn.commit()
    conn.close()


def get_movie(code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT file_id, file_type, title FROM movies WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_movie(code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM movies WHERE code = ?", (code,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def count_movies():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT COUNT(*) FROM movies")
    n = cur.fetchone()[0]
    conn.close()
    return n


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Salom! 🎬\n\n"
        "Kino kodini yuboring, men sizga kinoni jo'nataman.\n"
        "Masalan: <code>101</code>\n\n"
        "Buyruqlar ro'yxati uchun /help yozing.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = "🎬 Kino kodini yuboring — kino avtomatik keladi.\n"
    if is_admin(message.from_user.id):
        text += (
            "\n👑 Admin buyruqlari:\n"
            "• Video/fayl yuboring (yoki shunday xabarga reply qiling) va "
            "<code>/add kod</code> deb yozing — kod bilan saqlanadi\n"
            "• <code>/del kod</code> — kodni o'chirish\n"
            "• <code>/count</code> — jami kinolar soni"
        )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("add"))
async def cmd_add(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Kod kiriting: <code>/add 101</code> (video/faylga reply qilib)", parse_mode=ParseMode.HTML)
        return
    code = parts[1].strip()

    source = message.reply_to_message or message
    file_id = None
    file_type = None
    title = None

    if source.video:
        file_id, file_type = source.video.file_id, "video"
        title = source.caption or source.video.file_name
    elif source.document:
        file_id, file_type = source.document.file_id, "document"
        title = source.caption or source.document.file_name
    elif source.animation:
        file_id, file_type = source.animation.file_id, "animation"
        title = source.caption

    if not file_id:
        await message.answer("Video/fayl topilmadi. Video yuboring yoki videoli xabarga reply qiling.")
        return

    add_movie(code, file_id, file_type, title, message.from_user.id)
    await message.answer(f"✅ Saqlandi: kod <b>{code}</b>", parse_mode=ParseMode.HTML)


@router.message(Command("del"))
async def cmd_del(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Kod kiriting: <code>/del 101</code>", parse_mode=ParseMode.HTML)
        return
    code = parts[1].strip()
    if delete_movie(code):
        await message.answer(f"🗑 O'chirildi: {code}")
    else:
        await message.answer("Bunday kod topilmadi.")


@router.message(Command("count"))
async def cmd_count(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(f"Jami kinolar: {count_movies()}")


@router.message(F.text)
async def handle_code(message: Message):
    code = message.text.strip()
    row = get_movie(code)
    if not row:
        await message.answer("❌ Bunday kod topilmadi. Kodni tekshirib qayta yuboring.")
        return

    file_id, file_type, title = row
    caption = title or f"Kod: {code}"

    if file_type == "video":
        await message.answer_video(video=file_id, caption=caption)
    elif file_type == "document":
        await message.answer_document(document=file_id, caption=caption)
    elif file_type == "animation":
        await message.answer_animation(animation=file_id, caption=caption)


async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
