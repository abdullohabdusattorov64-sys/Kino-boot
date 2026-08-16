import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)

# ============ SOZLAMALAR ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = "movies.db"
VIP_DAYS = 30  # VIP necha kunga beriladi
# =====================================


def db():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            title TEXT,
            added_by INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            chat_id TEXT PRIMARY KEY,
            title TEXT,
            invite_link TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vip (
            user_id INTEGER PRIMARY KEY,
            expires_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payment_state (
            user_id INTEGER PRIMARY KEY,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()


# ---------- Kinolar ----------

def add_movie(code, file_id, file_type, title, added_by):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO movies (code, file_id, file_type, title, added_by) VALUES (?, ?, ?, ?, ?)",
        (code, file_id, file_type, title, added_by),
    )
    conn.commit()
    conn.close()


def get_movie(code):
    conn = db()
    cur = conn.execute("SELECT file_id, file_type, title FROM movies WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_movie(code):
    conn = db()
    cur = conn.execute("DELETE FROM movies WHERE code = ?", (code,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def count_movies():
    conn = db()
    cur = conn.execute("SELECT COUNT(*) FROM movies")
    n = cur.fetchone()[0]
    conn.close()
    return n


# ---------- Majburiy obuna kanallari ----------

def add_channel(chat_id, title, invite_link=None):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO channels (chat_id, title, invite_link) VALUES (?, ?, ?)",
        (chat_id, title, invite_link),
    )
    conn.commit()
    conn.close()


def delete_channel(chat_id):
    conn = db()
    cur = conn.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def list_channels():
    conn = db()
    cur = conn.execute("SELECT chat_id, title, invite_link FROM channels")
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Sozlamalar (VIP narx/karta) ----------

def set_setting(key, value):
    conn = db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_setting(key):
    conn = db()
    cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# ---------- VIP ----------

def set_vip(user_id, days=VIP_DAYS):
    expires = datetime.now() + timedelta(days=days)
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO vip (user_id, expires_at) VALUES (?, ?)",
        (user_id, expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return expires


def is_vip(user_id):
    conn = db()
    cur = conn.execute("SELECT expires_at FROM vip WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return datetime.fromisoformat(row[0]) > datetime.now()


def get_vip_expiry(user_id):
    conn = db()
    cur = conn.execute("SELECT expires_at FROM vip WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return datetime.fromisoformat(row[0]) if row else None


# ---------- To'lov holati ----------

def set_payment_state(user_id, status):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO payment_state (user_id, status) VALUES (?, ?)",
        (user_id, status),
    )
    conn.commit()
    conn.close()


def get_payment_state(user_id):
    conn = db()
    cur = conn.execute("SELECT status FROM payment_state WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def clear_payment_state(user_id):
    conn = db()
    conn.execute("DELETE FROM payment_state WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def channel_display_link(chat_id: str, invite_link: str | None) -> str:
    if invite_link:
        return invite_link
    if chat_id.startswith("@"):
        return f"https://t.me/{chat_id[1:]}"
    return "https://t.me/"  # noma'lum holat


async def get_unsubscribed_channels(bot: Bot, user_id: int):
    channels = list_channels()
    missing = []
    for chat_id, title, invite_link in channels:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append((chat_id, title, invite_link))
        except TelegramBadRequest:
            # Bot kanalda admin emas yoki chat_id noto'g'ri — bu kanalni tekshirib bo'lmaydi
            logging.warning(f"Kanalni tekshirib bo'lmadi: {chat_id}")
            continue
        except Exception:
            continue
    return missing


def force_sub_keyboard(missing):
    buttons = []
    for chat_id, title, invite_link in missing:
        url = channel_display_link(chat_id, invite_link)
        buttons.append([InlineKeyboardButton(text=f"➕ {title or chat_id}", url=url)])
    buttons.append([InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="checksub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_force_sub_message(message: Message, missing):
    await message.answer(
        "📢 Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling, "
        "so'ng <b>✅ A'zo bo'ldim</b> tugmasini bosing:",
        parse_mode=ParseMode.HTML,
        reply_markup=force_sub_keyboard(missing),
    )


# ================= START =================

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        missing = await get_unsubscribed_channels(bot, message.from_user.id)
        if missing:
            await send_force_sub_message(message, missing)
            return

    await message.answer(
        "Salom! 🎬\n\n"
        "Kino kodini yuboring, men sizga kinoni jo'nataman.\n"
        "Masalan: <code>101</code>\n\n"
        "Buyruqlar ro'yxati uchun /help yozing.",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "checksub")
async def cb_checksub(callback: CallbackQuery, bot: Bot):
    missing = await get_unsubscribed_channels(bot, callback.from_user.id)
    if missing:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz.", show_alert=True)
        return
    await callback.message.edit_text("✅ Rahmat! Endi botdan foydalanishingiz mumkin.\n\nKino kodini yuboring.")
    await callback.answer()


# ================= HELP =================

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = "🎬 Kino kodini yuboring — kino avtomatik keladi.\n\n💎 VIP olish uchun /vip yozing."
    if is_admin(message.from_user.id):
        text += (
            "\n\n👑 Admin buyruqlari:\n"
            "• Video/faylga reply qilib <code>/add kod</code>\n"
            "• <code>/del kod</code> — kodni o'chirish\n"
            "• <code>/count</code> — jami kinolar soni\n\n"
            "📢 Majburiy obuna:\n"
            "• <code>/addchannel @username Nomi</code>\n"
            "• <code>/addchannel -1001234567890 Nomi https://t.me/+invite</code>\n"
            "• <code>/delchannel @username</code>\n"
            "• <code>/channels</code> — ro'yxat\n\n"
            "💎 VIP sozlash:\n"
            "• <code>/setvip narx karta_raqami</code>\n"
            "  masalan: <code>/setvip 25000 8600123456789012 (F.I.Sh)</code>"
        )
    await message.answer(text, parse_mode=ParseMode.HTML)


# ================= KINO QO'SHISH/O'CHIRISH =================

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


# ================= MAJBURIY OBUNA BOSHQARUVI =================

@router.message(Command("addchannel"))
async def cmd_addchannel(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer(
            "Foydalanish:\n"
            "<code>/addchannel @username Nomi</code>\n"
            "yoki (yopiq kanal uchun)\n"
            "<code>/addchannel -1001234567890 Nomi https://t.me/+invite</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    chat_id = parts[1].strip()
    title = parts[2].strip()
    invite_link = None
    # Agar title ichida yana bo'sh joy bo'lsa va oxirida link bo'lsa ajratamiz
    title_parts = title.rsplit(maxsplit=1)
    if len(title_parts) == 2 and title_parts[1].startswith("http"):
        title, invite_link = title_parts

    add_channel(chat_id, title, invite_link)
    await message.answer(f"✅ Kanal qo'shildi: {title} ({chat_id})\n\n⚠️ Botni shu kanalga ADMIN qilib qo'yishni unutmang, aks holda obunani tekshira olmaydi.")


@router.message(Command("delchannel"))
async def cmd_delchannel(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: <code>/delchannel @username</code>", parse_mode=ParseMode.HTML)
        return
    chat_id = parts[1].strip()
    if delete_channel(chat_id):
        await message.answer(f"🗑 O'chirildi: {chat_id}")
    else:
        await message.answer("Bunday kanal topilmadi.")


@router.message(Command("channels"))
async def cmd_channels(message: Message):
    if not is_admin(message.from_user.id):
        return
    channels = list_channels()
    if not channels:
        await message.answer("Hozircha majburiy obuna kanallari yo'q.")
        return
    text = "📢 Majburiy obuna kanallari:\n\n"
    for chat_id, title, invite_link in channels:
        text += f"• {title} — <code>{chat_id}</code>\n"
    await message.answer(text, parse_mode=ParseMode.HTML)


# ================= VIP =================

@router.message(Command("setvip"))
async def cmd_setvip(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Foydalanish: <code>/setvip narx karta_raqami_va_ism</code>\n"
            "Masalan: <code>/setvip 25000 8600 1234 5678 9012 (Ism Familiya)</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    price = parts[1].strip()
    card = parts[2].strip()
    set_setting("vip_price", price)
    set_setting("vip_card", card)
    await message.answer(f"✅ VIP sozlandi:\nNarx: {price} so'm\nKarta: {card}")


@router.message(Command("vip"))
async def cmd_vip(message: Message):
    if is_vip(message.from_user.id):
        expiry = get_vip_expiry(message.from_user.id)
        await message.answer(f"💎 Siz allaqachon VIP foydalanuvchisiz.\nAmal qilish muddati: {expiry.strftime('%Y-%m-%d')} gacha")
        return

    price = get_setting("vip_price")
    card = get_setting("vip_card")
    if not price or not card:
        await message.answer("VIP hozircha sozlanmagan. Keyinroq urinib ko'ring.")
        return

    set_payment_state(message.from_user.id, "awaiting")
    await message.answer(
        f"💎 <b>VIP obuna</b>\n\n"
        f"Narxi: <b>{price} so'm</b>\n"
        f"Karta: <code>{card}</code>\n\n"
        f"To'lovni amalga oshirib, chekning (skrinshot) rasmini shu yerga yuboring. "
        f"Admin tasdiqlagach, VIP faollashadi.",
        parse_mode=ParseMode.HTML,
    )


@router.message(F.photo)
async def handle_payment_screenshot(message: Message, bot: Bot):
    state = get_payment_state(message.from_user.id)
    if state != "awaiting":
        return  # to'lov kutilmayotgan bo'lsa, e'tiborsiz qoldiramiz

    set_payment_state(message.from_user.id, "pending")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"vip_ok:{message.from_user.id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"vip_no:{message.from_user.id}"),
    ]])

    caption = (
        f"💳 Yangi VIP to'lov cheki\n"
        f"Foydalanuvchi: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"ID: <code>{message.from_user.id}</code>"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        except Exception as e:
            logging.warning(f"Adminga yuborib bo'lmadi {admin_id}: {e}")

    await message.answer("✅ Chek qabul qilindi. Admin tekshirib, tasdiqlagach xabar beramiz.")


@router.callback_query(F.data.startswith("vip_ok:"))
async def cb_vip_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizga ruxsat yo'q.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    expiry = set_vip(user_id)
    clear_payment_state(user_id)

    try:
        await bot.send_message(
            user_id,
            f"🎉 VIP obunangiz faollashtirildi!\nAmal qilish muddati: {expiry.strftime('%Y-%m-%d')} gacha",
        )
    except Exception:
        pass

    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ TASDIQLANDI")
    await callback.answer("VIP berildi.")


@router.callback_query(F.data.startswith("vip_no:"))
async def cb_vip_reject(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizga ruxsat yo'q.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    clear_payment_state(user_id)

    try:
        await bot.send_message(user_id, "❌ To'lov chekingiz tasdiqlanmadi. Qayta urinib ko'rish uchun /vip yozing.")
    except Exception:
        pass

    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ RAD ETILDI")
    await callback.answer("Rad etildi.")


# ================= KINO KODI =================

@router.message(F.text)
async def handle_code(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        missing = await get_unsubscribed_channels(bot, message.from_user.id)
        if missing:
            await send_force_sub_message(message, missing)
            return

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
