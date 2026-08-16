# Kino-kod Telegram bot

Foydalanuvchi kod yuboradi (masalan `101`) — bot shu kodga bog'langan kinoni jo'natadi.
Kinolar Telegram serverida (`file_id` orqali) saqlanadi, shuning uchun hech qanday video fayl serveringizda joy egallamaydi.

## 1. O'rnatish

```bash
pip install -r requirements.txt
```

## 2. Bot yaratish

1. Telegramda [@BotFather](https://t.me/BotFather) ga yozing
2. `/newbot` buyrug'ini bering, nom va username tanlang
3. Sizga beriladigan **tokenni** saqlab qo'ying

## 3. O'zingizning Telegram ID raqamingizni bilish

[@userinfobot](https://t.me/userinfobot) ga yozing — u sizning ID raqamingizni beradi.

## 4. Sozlash

Terminalda quyidagilarni kiriting (Linux/Mac):

```bash
export BOT_TOKEN="123456:ABC-DEF..."
export ADMIN_IDS="123456789"
```

Windows (PowerShell):
```powershell
$env:BOT_TOKEN="123456:ABC-DEF..."
$env:ADMIN_IDS="123456789"
```

Bir nechta admin bo'lsa, vergul bilan ajrating: `ADMIN_IDS="111,222,333"`

## 5. Ishga tushirish

```bash
python bot.py
```

## 6. Foydalanish

**Kino qo'shish (faqat admin):**
1. Kino videosini botga to'g'ridan-to'g'ri yuboring (yoki kanalda joylab, botga forward qiling)
2. Shu xabarga reply qilib `/add 101` deb yozing — `101` o'rniga xohlagan kodni yozing

**Kino o'chirish:** `/del 101`

**Kinolar sonini ko'rish:** `/count`

**Foydalanuvchi tomonidan:** Botga shunchaki kod yuborilsa (masalan `101`), tegishli kino avtomatik keladi.

## Eslatma

- Bot ishlab turishi uchun serverni doim yoqib qo'yish kerak (VPS, PythonAnywhere, Railway, va h.k.)
- Ma'lumotlar `movies.db` faylida (SQLite) saqlanadi — uni yo'qotmang, aks holda kodlar o'chib ketadi
- Agar juda ko'p kino bo'lsa, kelajakda bu botga qidiruv, kategoriyalar yoki inline tugmalar qo'shish mumkin
