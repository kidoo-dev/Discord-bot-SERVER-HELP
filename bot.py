import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import json
import datetime
import asyncio
import os
import time
from typing import Optional

# ─── Фикс SSL для Windows ────────────────────────────────── #
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════
#  ██████╗  ██████╗ ████████╗
#  ██╔══██╗██╔═══██╗╚══██╔══╝
#  ██████╔╝██║   ██║   ██║
#  ██╔══██╗██║   ██║   ██║
#  ██████╔╝╚██████╔╝   ██║
#  ╚═════╝  ╚═════╝    ╚═╝  Server Manager by dizansky
# ═══════════════════════════════════════════════════════════════

# ─── Загрузка конфига ─────────────────────────────────────── #

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["TOKEN"]
OWNER_IDS = config.get("OWNER_IDS", [])

# ─── База данных (JSON) ──────────────────────────────────── #

DB_FILE = "database.json"

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild_data(guild_id: int) -> dict:
    db = load_db()
    key = str(guild_id)
    if key not in db:
        db[key] = {
            "settings": {
                "color": "5865F2",
                "log_channel": None,
                "status_channel": None,
                "welcome_channel": None,
                "welcome_message": "Добро пожаловать на сервер, {user}! 🎉",
                "autorole": None,
            },
            "status": {
                "state": "none",
                "reason": "",
                "estimated_time": "",
                "additional_info": "",
                "updated_by": "",
                "updated_at": "",
            },
            "warns": {},
            "tickets": {
                "counter": 0,
                "category": None,
            },
            "notes": [],
        }
        save_db(db)
    return db[key]

def update_guild_data(guild_id: int, data: dict):
    db = load_db()
    db[str(guild_id)] = data
    save_db(db)

# ─── Стили и оформление ──────────────────────────────────── #

class Style:
    MAIN     = 0x5865F2   # Discord Blurple
    SUCCESS  = 0x57F287   # Зелёный
    ERROR    = 0xED4245   # Красный
    WARNING  = 0xFEE75C   # Жёлтый
    ORANGE   = 0xE67E22
    INFO     = 0x5865F2
    PREMIUM  = 0xF47FFF   # Розовый
    DARK     = 0x2F3136
    ONLINE   = 0x57F287
    OFFLINE  = 0xED4245
    MAINT    = 0xE67E22

    @staticmethod
    def embed(title="", desc="", color=None, guild=None):
        if color is None:
            if guild:
                gd = get_guild_data(guild.id)
                try:
                    color = int(gd["settings"]["color"], 16)
                except:
                    color = Style.MAIN
            else:
                color = Style.MAIN
        e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
        return e

    @staticmethod
    def footer(embed, user=None, text=None):
        if user:
            embed.set_footer(text=f"{'│ ' + text + ' ' if text else ''}│ {user.display_name}", icon_url=user.display_avatar.url)
        elif text:
            embed.set_footer(text=f"│ {text}")
        return embed


# ─── Бот ──────────────────────────────────────────────────── #

intents = discord.Intents.default()
intents.guilds = True
# Включи в Developer Portal для приветствий и авторолей:
# intents.members = True
# intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
start_time = time.time()

# ─── Проверки прав ────────────────────────────────────────── #

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if interaction.user.id in OWNER_IDS:
            return True
        try:
            if interaction.user.guild_permissions.administrator:
                return True
        except: pass
        try:
            if interaction.user.resolved_permissions and interaction.user.resolved_permissions.administrator:
                return True
        except: pass
        return False
    return app_commands.check(predicate)

def is_mod():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if interaction.user.id in OWNER_IDS:
            return True
        try:
            p = interaction.user.guild_permissions
            if p.administrator or p.manage_guild or p.manage_messages or p.kick_members or p.ban_members:
                return True
        except: pass
        try:
            p = interaction.user.resolved_permissions
            if p and (p.administrator or p.manage_guild or p.manage_messages):
                return True
        except: pass
        return False
    return app_commands.check(predicate)


# ╔═══════════════════════════════════════════════════════════╗
# ║                    SETUP / НАСТРОЙКИ                      ║
# ╚═══════════════════════════════════════════════════════════╝

class WelcomeModal(ui.Modal, title="👋 Настройка приветствия"):
    message = ui.TextInput(
        label="Текст приветствия",
        placeholder="Привет, {user}! Добро пожаловать на {server}! 🎉",
        style=discord.TextStyle.paragraph,
        default="Добро пожаловать на сервер, {user}! 🎉",
        max_length=1000,
    )
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        gd = get_guild_data(self.guild_id)
        gd["settings"]["welcome_message"] = self.message.value
        update_guild_data(self.guild_id, gd)
        e = Style.embed("✅ Приветствие обновлено", color=Style.SUCCESS, guild=interaction.guild)
        e.add_field(name="Текст", value=self.message.value, inline=False)
        e.add_field(name="Переменные", value="`{user}` — упоминание\n`{server}` — название\n`{count}` — номер участника", inline=False)
        Style.footer(e, interaction.user)
        await interaction.response.send_message(embed=e, ephemeral=True)


class ColorModal(ui.Modal, title="🎨 Цвет бота"):
    color = ui.TextInput(label="HEX цвет (без #)", placeholder="5865F2", style=discord.TextStyle.short, max_length=6, min_length=6)
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            int(self.color.value, 16)
        except ValueError:
            return await interaction.response.send_message("❌ Неверный HEX!", ephemeral=True)
        gd = get_guild_data(self.guild_id)
        gd["settings"]["color"] = self.color.value.upper()
        update_guild_data(self.guild_id, gd)
        c = int(self.color.value, 16)
        e = Style.embed("🎨 Цвет обновлён!", f"Новый цвет: `#{self.color.value.upper()}`", color=c)
        Style.footer(e, interaction.user)
        await interaction.response.send_message(embed=e, ephemeral=True)


class SetupView(ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @ui.button(label="📝 Логи", style=discord.ButtonStyle.secondary, row=0)
    async def log_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Используй `/settings logs #канал`", ephemeral=True)

    @ui.button(label="📊 Статус-канал", style=discord.ButtonStyle.secondary, row=0)
    async def status_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Используй `/settings status-channel #канал`", ephemeral=True)

    @ui.button(label="👋 Приветствие", style=discord.ButtonStyle.secondary, row=0)
    async def welcome_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(WelcomeModal(self.guild_id))

    @ui.button(label="🎨 Цвет", style=discord.ButtonStyle.secondary, row=1)
    async def color_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ColorModal(self.guild_id))

    @ui.button(label="🎭 Авто-роль", style=discord.ButtonStyle.secondary, row=1)
    async def autorole_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Используй `/settings autorole @роль`", ephemeral=True)


@bot.tree.command(name="setup", description="⚙️ Панель настроек бота")
@is_admin()
async def setup_cmd(interaction: discord.Interaction):
    gd = get_guild_data(interaction.guild.id)
    s = gd["settings"]

    e = Style.embed(guild=interaction.guild)
    e.title = "⚙️  Панель настроек"
    e.description = "Настрой бота под свой сервер.\nНажми кнопки или используй `/settings`"

    log_ch = f"<#{s['log_channel']}>" if s["log_channel"] else "`не установлен`"
    status_ch = f"<#{s['status_channel']}>" if s["status_channel"] else "`не установлен`"
    welcome_ch = f"<#{s['welcome_channel']}>" if s["welcome_channel"] else "`не установлен`"
    autorole = f"<@&{s['autorole']}>" if s["autorole"] else "`не установлена`"

    e.add_field(name="📝 Канал логов", value=log_ch, inline=True)
    e.add_field(name="📊 Канал статуса", value=status_ch, inline=True)
    e.add_field(name="👋 Приветствия", value=welcome_ch, inline=True)
    e.add_field(name="🎭 Авто-роль", value=autorole, inline=True)
    e.add_field(name="🎨 Цвет", value=f"`#{s['color']}`", inline=True)
    e.add_field(name="\u200b", value="\u200b", inline=True)

    if interaction.guild.icon:
        e.set_thumbnail(url=interaction.guild.icon.url)
    Style.footer(e, interaction.user, "Настройки")
    await interaction.response.send_message(embed=e, view=SetupView(interaction.guild.id), ephemeral=True)


# ─── /settings — Быстрая настройка ───────────────────────── #

settings_group = app_commands.Group(name="settings", description="⚙️ Настройки бота")

@settings_group.command(name="logs", description="📝 Канал логов")
@is_admin()
@app_commands.describe(channel="Канал для логов")
async def settings_logs(interaction: discord.Interaction, channel: discord.TextChannel):
    gd = get_guild_data(interaction.guild.id)
    gd["settings"]["log_channel"] = channel.id
    update_guild_data(interaction.guild.id, gd)
    e = Style.embed("✅ Канал логов", f"Логи → {channel.mention}", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e, ephemeral=True)

@settings_group.command(name="status-channel", description="📊 Канал статуса")
@is_admin()
@app_commands.describe(channel="Канал для статуса")
async def settings_status_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    gd = get_guild_data(interaction.guild.id)
    gd["settings"]["status_channel"] = channel.id
    update_guild_data(interaction.guild.id, gd)
    e = Style.embed("✅ Канал статуса", f"Уведомления → {channel.mention}", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e, ephemeral=True)

@settings_group.command(name="welcome-channel", description="👋 Канал приветствий")
@is_admin()
@app_commands.describe(channel="Канал для приветствий")
async def settings_welcome_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    gd = get_guild_data(interaction.guild.id)
    gd["settings"]["welcome_channel"] = channel.id
    update_guild_data(interaction.guild.id, gd)
    e = Style.embed("✅ Канал приветствий", f"Приветствия → {channel.mention}", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e, ephemeral=True)

@settings_group.command(name="autorole", description="🎭 Авто-роль для новых")
@is_admin()
@app_commands.describe(role="Роль")
async def settings_autorole(interaction: discord.Interaction, role: discord.Role):
    gd = get_guild_data(interaction.guild.id)
    gd["settings"]["autorole"] = role.id
    update_guild_data(interaction.guild.id, gd)
    e = Style.embed("✅ Авто-роль", f"Новым → {role.mention}", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e, ephemeral=True)

bot.tree.add_command(settings_group)


# ╔═══════════════════════════════════════════════════════════╗
# ║                   STATUS / СТАТУС                         ║
# ╚═══════════════════════════════════════════════════════════╝

class OfflineModal(ui.Modal, title="🔴 Сервер выключен"):
    reason = ui.TextInput(label="Причина", placeholder="Технические работы, обновление...", style=discord.TextStyle.paragraph, required=True, max_length=500)
    estimated = ui.TextInput(label="Когда вернётся?", placeholder="Через 2 часа, завтра утром...", style=discord.TextStyle.short, required=False, max_length=100)
    info = ui.TextInput(label="Доп. информация", placeholder="Заметки для участников...", style=discord.TextStyle.paragraph, required=False, max_length=300)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        gd = get_guild_data(self.guild_id)
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        gd["status"] = {"state": "offline", "reason": self.reason.value, "estimated_time": self.estimated.value or "Не указано", "additional_info": self.info.value or "—", "updated_by": str(interaction.user), "updated_at": now}
        update_guild_data(self.guild_id, gd)
        e = Style.embed(color=Style.OFFLINE, guild=interaction.guild)
        e.title = "🔴  Сервер — OFFLINE"
        e.description = "```\n⛔ Сервер был отключён\n```"
        e.add_field(name="📝 Причина", value=f">>> {self.reason.value}", inline=False)
        e.add_field(name="⏰ Возвращение", value=f"`{self.estimated.value or 'Не указано'}`", inline=True)
        e.add_field(name="👤 Обновил", value=interaction.user.mention, inline=True)
        if self.info.value:
            e.add_field(name="ℹ️ Дополнительно", value=self.info.value, inline=False)
        Style.footer(e, interaction.user, "Status Update")
        await interaction.response.send_message(embed=e)
        await _notify_status(interaction.guild, e)
        await _log_action(interaction.guild, "Status", f"Статус → **OFFLINE** — {self.reason.value}", interaction.user)


class MaintenanceModal(ui.Modal, title="🟠 Тех. обслуживание"):
    reason = ui.TextInput(label="Что происходит?", placeholder="Обновление, оптимизация...", style=discord.TextStyle.paragraph, required=True, max_length=500)
    estimated = ui.TextInput(label="Когда закончится?", placeholder="~30 минут, к вечеру...", style=discord.TextStyle.short, required=False, max_length=100)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        gd = get_guild_data(self.guild_id)
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        gd["status"] = {"state": "maintenance", "reason": self.reason.value, "estimated_time": self.estimated.value or "Не указано", "additional_info": "—", "updated_by": str(interaction.user), "updated_at": now}
        update_guild_data(self.guild_id, gd)
        e = Style.embed(color=Style.MAINT, guild=interaction.guild)
        e.title = "🟠  Сервер — MAINTENANCE"
        e.description = "```\n🔧 Проводятся технические работы\n```"
        e.add_field(name="🔧 Описание", value=f">>> {self.reason.value}", inline=False)
        e.add_field(name="⏰ Завершение", value=f"`{self.estimated.value or 'Не указано'}`", inline=True)
        e.add_field(name="👤 Обновил", value=interaction.user.mention, inline=True)
        Style.footer(e, interaction.user, "Status Update")
        await interaction.response.send_message(embed=e)
        await _notify_status(interaction.guild, e)
        await _log_action(interaction.guild, "Status", f"Статус → **MAINTENANCE** — {self.reason.value}", interaction.user)


class StatusSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Онлайн", description="Сервер работает", emoji="🟢", value="online"),
            discord.SelectOption(label="Выключен", description="Сервер не работает", emoji="🔴", value="offline"),
            discord.SelectOption(label="Тех. обслуживание", description="Технические работы", emoji="🟠", value="maintenance"),
        ]
        super().__init__(placeholder="Выбери статус сервера...", options=options)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "online":
            gd = get_guild_data(interaction.guild.id)
            now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            gd["status"] = {"state": "online", "reason": "—", "estimated_time": "—", "additional_info": "—", "updated_by": str(interaction.user), "updated_at": now}
            update_guild_data(interaction.guild.id, gd)
            e = Style.embed(color=Style.ONLINE, guild=interaction.guild)
            e.title = "🟢  Сервер — ONLINE"
            e.description = "```\n✅ Всё работает в штатном режиме\n```"
            e.add_field(name="👤 Обновил", value=interaction.user.mention, inline=True)
            Style.footer(e, interaction.user, "Status Update")
            await interaction.response.send_message(embed=e)
            await _notify_status(interaction.guild, e)
            await _log_action(interaction.guild, "Status", "Статус → **ONLINE**", interaction.user)
        elif val == "offline":
            await interaction.response.send_modal(OfflineModal(interaction.guild.id))
        elif val == "maintenance":
            await interaction.response.send_modal(MaintenanceModal(interaction.guild.id))


class StatusView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(StatusSelect())


@bot.tree.command(name="status", description="📊 Управление статусом сервера")
@is_admin()
async def status_cmd(interaction: discord.Interaction):
    gd = get_guild_data(interaction.guild.id)
    st = gd["status"]
    emojis = {"online": "🟢", "offline": "🔴", "maintenance": "🟠", "none": "⚪"}
    labels = {"online": "ONLINE", "offline": "OFFLINE", "maintenance": "MAINTENANCE", "none": "НЕ УСТАНОВЛЕН"}
    colors = {"online": Style.ONLINE, "offline": Style.OFFLINE, "maintenance": Style.MAINT, "none": Style.DARK}
    state = st.get("state", "none")

    e = Style.embed(color=colors.get(state, Style.DARK), guild=interaction.guild)
    e.title = "📊  Управление статусом"
    e.description = f"```\nТекущий статус: {emojis.get(state, '⚪')} {labels.get(state, '?')}\n```\nВыбери новый статус из меню ниже."
    if st.get("reason") and st["reason"] not in ("—", ""):
        e.add_field(name="📝 Причина", value=st["reason"], inline=False)
    if st.get("updated_at"):
        e.add_field(name="🕐 Обновлено", value=f"`{st['updated_at']}`", inline=True)
    if st.get("updated_by"):
        e.add_field(name="👤 Кем", value=st["updated_by"], inline=True)
    if interaction.guild.icon:
        e.set_thumbnail(url=interaction.guild.icon.url)
    Style.footer(e, interaction.user, "Server Manager")
    await interaction.response.send_message(embed=e, view=StatusView(), ephemeral=True)


@bot.tree.command(name="serverstatus", description="📡 Текущий статус сервера")
async def serverstatus_cmd(interaction: discord.Interaction):
    gd = get_guild_data(interaction.guild.id)
    st = gd["status"]
    state = st.get("state", "none")
    if state == "online":
        e = Style.embed("🟢  Сервер работает", "```\n✅ Всё в порядке, сервер онлайн!\n```", Style.ONLINE, interaction.guild)
    elif state == "offline":
        e = Style.embed("🔴  Сервер выключен", "```\n⛔ Сервер временно недоступен\n```", Style.OFFLINE, interaction.guild)
        e.add_field(name="📝 Причина", value=f">>> {st.get('reason', '?')}", inline=False)
        e.add_field(name="⏰ Возвращение", value=f"`{st.get('estimated_time', '?')}`", inline=True)
        if st.get("additional_info") and st["additional_info"] != "—":
            e.add_field(name="ℹ️ Доп. инфо", value=st["additional_info"], inline=False)
    elif state == "maintenance":
        e = Style.embed("🟠  Тех. обслуживание", "```\n🔧 Проводятся технические работы\n```", Style.MAINT, interaction.guild)
        e.add_field(name="🔧 Описание", value=f">>> {st.get('reason', '?')}", inline=False)
        e.add_field(name="⏰ Завершение", value=f"`{st.get('estimated_time', '?')}`", inline=True)
    else:
        e = Style.embed("⚪  Статус не установлен", "Администратор ещё не указал статус.", Style.DARK, interaction.guild)
    if st.get("updated_at"):
        Style.footer(e, text=f"Обновлено: {st['updated_at']}")
    await interaction.response.send_message(embed=e)


# ╔═══════════════════════════════════════════════════════════╗
# ║                  МОДЕРАЦИЯ / MOD                          ║
# ╚═══════════════════════════════════════════════════════════╝

@bot.tree.command(name="kick", description="🦶 Кикнуть участника")
@is_mod()
@app_commands.describe(member="Кого кикнуть", reason="Причина")
async def kick_cmd(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "Не указана"):
    if member.id == interaction.user.id:
        return await interaction.response.send_message("❌ Нельзя кикнуть себя.", ephemeral=True)
    if member.id == interaction.guild.owner_id:
        return await interaction.response.send_message("❌ Нельзя кикнуть владельца.", ephemeral=True)
    try:
        await member.kick(reason=reason)
        e = Style.embed(color=Style.ERROR, guild=interaction.guild)
        e.title = "🦶  Участник кикнут"
        e.add_field(name="Участник", value=f"{member.mention} (`{member}`)", inline=True)
        e.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        e.add_field(name="Причина", value=f">>> {reason}", inline=False)
        Style.footer(e, interaction.user, "Moderation")
        await interaction.response.send_message(embed=e)
        await _log_action(interaction.guild, "Kick", f"{member} кикнут — {reason}", interaction.user)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Нет прав для кика.", ephemeral=True)


@bot.tree.command(name="ban", description="🔨 Забанить участника")
@is_mod()
@app_commands.describe(member="Кого забанить", reason="Причина", delete_days="Удалить сообщения за X дней (0-7)")
async def ban_cmd(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "Не указана", delete_days: Optional[int] = 0):
    if member.id == interaction.user.id:
        return await interaction.response.send_message("❌ Нельзя забанить себя.", ephemeral=True)
    if member.id == interaction.guild.owner_id:
        return await interaction.response.send_message("❌ Нельзя забанить владельца.", ephemeral=True)
    try:
        await member.ban(reason=reason, delete_message_days=min(delete_days, 7))
        e = Style.embed(color=Style.ERROR, guild=interaction.guild)
        e.title = "🔨  Участник забанен"
        e.add_field(name="Участник", value=f"{member.mention} (`{member}`)", inline=True)
        e.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        e.add_field(name="Причина", value=f">>> {reason}", inline=False)
        Style.footer(e, interaction.user, "Moderation")
        await interaction.response.send_message(embed=e)
        await _log_action(interaction.guild, "Ban", f"{member} забанен — {reason}", interaction.user)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Нет прав для бана.", ephemeral=True)


@bot.tree.command(name="unban", description="🔓 Разбанить по ID")
@is_mod()
@app_commands.describe(user_id="ID пользователя")
async def unban_cmd(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        e = Style.embed("🔓  Разбанен", f"**{user}** разбанен.", Style.SUCCESS, interaction.guild)
        e.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        Style.footer(e, interaction.user, "Moderation")
        await interaction.response.send_message(embed=e)
        await _log_action(interaction.guild, "Unban", f"{user} разбанен", interaction.user)
    except discord.NotFound:
        await interaction.response.send_message("❌ Не найден или не забанен.", ephemeral=True)
    except:
        await interaction.response.send_message("❌ Ошибка. Проверь ID.", ephemeral=True)


@bot.tree.command(name="warn", description="⚠️ Варн участнику")
@is_mod()
@app_commands.describe(member="Кому", reason="Причина")
async def warn_cmd(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "Не указана"):
    gd = get_guild_data(interaction.guild.id)
    uid = str(member.id)
    if uid not in gd["warns"]:
        gd["warns"][uid] = []
    gd["warns"][uid].append({"reason": reason, "by": str(interaction.user), "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M")})
    update_guild_data(interaction.guild.id, gd)
    count = len(gd["warns"][uid])
    e = Style.embed(color=Style.WARNING, guild=interaction.guild)
    e.title = "⚠️  Предупреждение"
    e.add_field(name="Участник", value=f"{member.mention} (`{member}`)", inline=True)
    e.add_field(name="Модератор", value=interaction.user.mention, inline=True)
    e.add_field(name="Причина", value=f">>> {reason}", inline=False)
    e.add_field(name="Всего варнов", value=f"```{count}```", inline=True)
    Style.footer(e, interaction.user, "Moderation")
    await interaction.response.send_message(embed=e)
    await _log_action(interaction.guild, "Warn", f"{member} варн #{count} — {reason}", interaction.user)


@bot.tree.command(name="warns", description="📋 Варны участника")
@is_mod()
@app_commands.describe(member="Кого проверить")
async def warns_cmd(interaction: discord.Interaction, member: discord.Member):
    gd = get_guild_data(interaction.guild.id)
    warns = gd.get("warns", {}).get(str(member.id), [])
    e = Style.embed(guild=interaction.guild)
    e.title = f"📋  Варны — {member.display_name}"
    e.set_thumbnail(url=member.display_avatar.url)
    if not warns:
        e.description = "```\n✅ Предупреждений нет\n```"
    else:
        e.description = f"```\nВсего: {len(warns)}\n```"
        for i, w in enumerate(warns[-10:], 1):
            e.add_field(name=f"#{i} │ {w['date']}", value=f">>> {w['reason']}\n*— {w['by']}*", inline=False)
    Style.footer(e, interaction.user, "Moderation")
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="clearwarns", description="🗑️ Очистить варны участника")
@is_admin()
@app_commands.describe(member="У кого")
async def clearwarns_cmd(interaction: discord.Interaction, member: discord.Member):
    gd = get_guild_data(interaction.guild.id)
    uid = str(member.id)
    old = len(gd.get("warns", {}).get(uid, []))
    gd.setdefault("warns", {})[uid] = []
    update_guild_data(interaction.guild.id, gd)
    e = Style.embed("🗑️  Варны очищены", f"Удалено **{old}** варнов у {member.mention}", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user, "Moderation")
    await interaction.response.send_message(embed=e)
    await _log_action(interaction.guild, "ClearWarns", f"Варны {member} очищены ({old})", interaction.user)


@bot.tree.command(name="clear", description="🧹 Очистить сообщения")
@is_mod()
@app_commands.describe(amount="Кол-во (1-100)")
async def clear_cmd(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        return await interaction.response.send_message("❌ Число от 1 до 100.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    e = Style.embed("🧹  Очищено", f"Удалено **{len(deleted)}** сообщений.", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user, "Moderation")
    await interaction.followup.send(embed=e, ephemeral=True)
    await _log_action(interaction.guild, "Clear", f"{len(deleted)} сообщений в #{interaction.channel.name}", interaction.user)


@bot.tree.command(name="slowmode", description="🐌 Медленный режим")
@is_mod()
@app_commands.describe(seconds="Задержка в секундах (0 = выкл)")
async def slowmode_cmd(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        e = Style.embed("🐌  Слоумод выключен", f"В {interaction.channel.mention}", Style.SUCCESS, interaction.guild)
    else:
        e = Style.embed("🐌  Слоумод", f"**{seconds}с** в {interaction.channel.mention}", Style.WARNING, interaction.guild)
    Style.footer(e, interaction.user, "Moderation")
    await interaction.response.send_message(embed=e)


# ╔═══════════════════════════════════════════════════════════╗
# ║                    ТИКЕТЫ / TICKETS                       ║
# ╚═══════════════════════════════════════════════════════════╝

class TicketCreateView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📩 Создать тикет", style=discord.ButtonStyle.primary, custom_id="ticket_create")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        gd = get_guild_data(interaction.guild.id)
        gd["tickets"]["counter"] += 1
        num = gd["tickets"]["counter"]
        update_guild_data(interaction.guild.id, gd)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        category = None
        if gd["tickets"].get("category"):
            category = interaction.guild.get_channel(gd["tickets"]["category"])

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{num:04d}", overwrites=overwrites, category=category,
            topic=f"Тикет #{num} | {interaction.user}",
        )

        e = Style.embed(guild=interaction.guild)
        e.title = f"📩  Тикет #{num:04d}"
        e.description = f"Привет, {interaction.user.mention}!\n\nОпиши проблему и жди ответа.\nНажми 🔒 чтобы закрыть."
        Style.footer(e, interaction.user, "Ticket System")
        await channel.send(embed=e, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Тикет создан: {channel.mention}", ephemeral=True)
        await _log_action(interaction.guild, "Ticket", f"Тикет #{num} создан — {interaction.user}", interaction.user)


class TicketCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔒 Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        e = Style.embed("🔒  Тикет закрыт", f"Закрыл: {interaction.user.mention}\nУдаление через 5с...", Style.ERROR, interaction.guild)
        await interaction.response.send_message(embed=e)
        await _log_action(interaction.guild, "Ticket", f"Тикет закрыт — {interaction.user}", interaction.user)
        await asyncio.sleep(5)
        await interaction.channel.delete()


@bot.tree.command(name="ticket-setup", description="📩 Создать панель тикетов")
@is_admin()
@app_commands.describe(channel="Канал для панели", category="Категория для тикетов")
async def ticket_setup_cmd(interaction: discord.Interaction, channel: discord.TextChannel, category: Optional[discord.CategoryChannel] = None):
    gd = get_guild_data(interaction.guild.id)
    if category:
        gd["tickets"]["category"] = category.id
    update_guild_data(interaction.guild.id, gd)

    e = Style.embed(guild=interaction.guild)
    e.title = "📩  Система тикетов"
    e.description = "Нужна помощь? Есть вопрос?\n\nНажми кнопку ниже для **приватного тикета**.\nКоманда сервера ответит как можно скорее."
    if interaction.guild.icon:
        e.set_thumbnail(url=interaction.guild.icon.url)
    Style.footer(e, text="Ticket System")
    await channel.send(embed=e, view=TicketCreateView())
    await interaction.response.send_message(f"✅ Панель тикетов → {channel.mention}", ephemeral=True)


# ╔═══════════════════════════════════════════════════════════╗
# ║                    УТИЛИТЫ / TOOLS                        ║
# ╚═══════════════════════════════════════════════════════════╝

@bot.tree.command(name="serverinfo", description="📋 Информация о сервере")
async def serverinfo_cmd(interaction: discord.Interaction):
    g = interaction.guild
    gd = get_guild_data(g.id)
    state = gd["status"].get("state", "none")
    emojis = {"online": "🟢", "offline": "🔴", "maintenance": "🟠", "none": "⚪"}

    e = Style.embed(guild=g)
    e.title = f"📋  {g.name}"
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    if g.banner:
        e.set_image(url=g.banner.url)

    e.add_field(name="👑 Владелец", value=f"<@{g.owner_id}>", inline=True)
    e.add_field(name="👥 Участники", value=f"`{g.member_count}`", inline=True)
    e.add_field(name="📊 Статус", value=f"{emojis.get(state, '⚪')} `{state.upper()}`", inline=True)
    e.add_field(name="💬 Каналы", value=f"`{len(g.channels)}`", inline=True)
    e.add_field(name="🎭 Роли", value=f"`{len(g.roles)}`", inline=True)
    e.add_field(name="😀 Эмодзи", value=f"`{len(g.emojis)}`", inline=True)
    e.add_field(name="🔒 Верификация", value=f"`{g.verification_level}`", inline=True)
    e.add_field(name="📅 Создан", value=f"<t:{int(g.created_at.timestamp())}:R>", inline=True)
    e.add_field(name="🆔 ID", value=f"`{g.id}`", inline=True)
    Style.footer(e, interaction.user, "Server Info")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="userinfo", description="👤 Информация о пользователе")
@app_commands.describe(member="Пользователь")
async def userinfo_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    m = member or interaction.user
    e = Style.embed(guild=interaction.guild)
    e.title = f"👤  {m.display_name}"
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="📛 Имя", value=f"`{m}`", inline=True)
    e.add_field(name="🆔 ID", value=f"`{m.id}`", inline=True)
    e.add_field(name="🤖 Бот?", value=f"`{'Да' if m.bot else 'Нет'}`", inline=True)
    e.add_field(name="📅 Зарег.", value=f"<t:{int(m.created_at.timestamp())}:R>", inline=True)
    e.add_field(name="📥 Зашёл", value=f"<t:{int(m.joined_at.timestamp())}:R>" if m.joined_at else "`?`", inline=True)
    roles = [r.mention for r in m.roles if r.name != "@everyone"]
    e.add_field(name=f"🎭 Роли [{len(roles)}]", value=" ".join(roles[:10]) if roles else "`нет`", inline=False)
    gd = get_guild_data(interaction.guild.id)
    warns_count = len(gd.get("warns", {}).get(str(m.id), []))
    e.add_field(name="⚠️ Варны", value=f"`{warns_count}`", inline=True)
    Style.footer(e, interaction.user, "User Info")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="avatar", description="🖼️ Аватар")
@app_commands.describe(member="Пользователь")
async def avatar_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    m = member or interaction.user
    e = Style.embed(f"🖼️  {m.display_name}", guild=interaction.guild)
    e.set_image(url=m.display_avatar.url)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="announce", description="📢 Объявление")
@is_admin()
@app_commands.describe(channel="Канал", title="Заголовок", message="Текст", ping="@everyone?", image="URL картинки")
async def announce_cmd(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str, ping: Optional[bool] = False, image: Optional[str] = None):
    e = Style.embed(guild=interaction.guild, color=Style.PREMIUM)
    e.title = f"📢  {title}"
    e.description = message
    if image:
        e.set_image(url=image)
    if interaction.guild.icon:
        e.set_thumbnail(url=interaction.guild.icon.url)
    Style.footer(e, interaction.user, "Announcement")
    content = "@everyone" if ping else None
    await channel.send(content=content, embed=e)
    await interaction.response.send_message(f"✅ Отправлено → {channel.mention}", ephemeral=True)
    await _log_action(interaction.guild, "Announce", f"Объявление в #{channel.name}: {title}", interaction.user)


@bot.tree.command(name="embed", description="🎨 Кастомный embed")
@is_admin()
@app_commands.describe(channel="Канал", title="Заголовок", description="Описание", color="HEX цвет", image="URL картинки")
async def embed_cmd(interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str, color: Optional[str] = None, image: Optional[str] = None):
    c = Style.MAIN
    if color:
        try: c = int(color, 16)
        except: return await interaction.response.send_message("❌ Неверный HEX.", ephemeral=True)
    e = discord.Embed(title=title, description=description, color=c, timestamp=datetime.datetime.now(datetime.timezone.utc))
    if image:
        e.set_image(url=image)
    Style.footer(e, interaction.user)
    await channel.send(embed=e)
    await interaction.response.send_message(f"✅ Embed → {channel.mention}", ephemeral=True)


@bot.tree.command(name="poll", description="📊 Голосование")
@is_mod()
@app_commands.describe(question="Вопрос", option1="Вариант 1", option2="Вариант 2", option3="Вариант 3", option4="Вариант 4")
async def poll_cmd(interaction: discord.Interaction, question: str, option1: str, option2: str, option3: Optional[str] = None, option4: Optional[str] = None):
    nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4)
    desc = "\n".join([f"{nums[i]} {opt}" for i, opt in enumerate(options)])
    e = Style.embed(guild=interaction.guild, color=Style.PREMIUM)
    e.title = f"📊  {question}"
    e.description = desc
    Style.footer(e, interaction.user, "Poll")
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    for i in range(len(options)):
        await msg.add_reaction(nums[i])


@bot.tree.command(name="note", description="📝 Добавить заметку")
@is_admin()
@app_commands.describe(text="Текст")
async def note_cmd(interaction: discord.Interaction, text: str):
    gd = get_guild_data(interaction.guild.id)
    gd["notes"].append({"text": text, "by": str(interaction.user), "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M")})
    if len(gd["notes"]) > 25:
        gd["notes"] = gd["notes"][-25:]
    update_guild_data(interaction.guild.id, gd)
    e = Style.embed("📝  Заметка добавлена", f">>> {text}", Style.SUCCESS, interaction.guild)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="notes", description="📋 Заметки сервера")
@is_admin()
async def notes_cmd(interaction: discord.Interaction):
    gd = get_guild_data(interaction.guild.id)
    notes = gd.get("notes", [])
    e = Style.embed(guild=interaction.guild)
    e.title = "📋  Заметки сервера"
    if not notes:
        e.description = "```\nПусто. Используй /note\n```"
    else:
        e.description = f"```\nВсего: {len(notes)}\n```"
        for i, n in enumerate(notes[-10:], 1):
            e.add_field(name=f"#{i} │ {n['date']}", value=f">>> {n['text']}\n*— {n['by']}*", inline=False)
    Style.footer(e, interaction.user)
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="botinfo", description="🤖 Информация о боте")
async def botinfo_cmd(interaction: discord.Interaction):
    uptime = int(time.time() - start_time)
    h, r = divmod(uptime, 3600)
    m, s = divmod(r, 60)
    e = Style.embed(color=Style.PREMIUM)
    e.title = "🤖  Server Manager Bot"
    e.description = "Бот для управления Discord серверами."
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.add_field(name="⏱️ Аптайм", value=f"`{h}ч {m}м {s}с`", inline=True)
    e.add_field(name="🌐 Серверов", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="📡 Пинг", value=f"`{round(bot.latency * 1000)}мс`", inline=True)
    e.add_field(name="🐍 discord.py", value=f"`{discord.__version__}`", inline=True)
    e.add_field(name="🆔 Bot ID", value=f"`{bot.user.id}`", inline=True)
    invite = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    e.add_field(name="🔗 Пригласить", value=f"[Ссылка]({invite})", inline=True)
    Style.footer(e, interaction.user, "Bot Info")
    await interaction.response.send_message(embed=e)


# ╔═══════════════════════════════════════════════════════════╗
# ║                     HELP / ПОМОЩЬ                         ║
# ╚═══════════════════════════════════════════════════════════╝

class HelpSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Управление", emoji="⚙️", value="management", description="Статус, настройки, объявления"),
            discord.SelectOption(label="Модерация", emoji="🛡️", value="moderation", description="Кик, бан, варн, очистка"),
            discord.SelectOption(label="Тикеты", emoji="📩", value="tickets", description="Система тикетов"),
            discord.SelectOption(label="Утилиты", emoji="🔧", value="utility", description="Инфо, аватар, опросы"),
        ]
        super().__init__(placeholder="Выбери категорию...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        e = Style.embed(guild=interaction.guild)
        if cat == "management":
            e.title = "⚙️  Управление"
            e.description = (
                "**`/status`** — Установить статус сервера\n"
                "**`/serverstatus`** — Посмотреть статус\n"
                "**`/setup`** — Панель настроек\n"
                "**`/settings logs`** — Канал логов\n"
                "**`/settings status-channel`** — Канал статуса\n"
                "**`/settings welcome-channel`** — Канал приветствий\n"
                "**`/settings autorole`** — Авто-роль\n"
                "**`/announce`** — Объявление\n"
                "**`/embed`** — Кастомный embed\n"
                "**`/note`** / **`/notes`** — Заметки\n"
            )
        elif cat == "moderation":
            e.title = "🛡️  Модерация"
            e.description = (
                "**`/kick`** — Кикнуть участника\n"
                "**`/ban`** — Забанить участника\n"
                "**`/unban`** — Разбанить по ID\n"
                "**`/warn`** — Выдать варн\n"
                "**`/warns`** — Посмотреть варны\n"
                "**`/clearwarns`** — Очистить варны\n"
                "**`/clear`** — Очистить сообщения\n"
                "**`/slowmode`** — Медленный режим\n"
            )
        elif cat == "tickets":
            e.title = "📩  Тикеты"
            e.description = (
                "**`/ticket-setup`** — Создать панель тикетов\n\n"
                "Участники нажимают кнопку → приватный канал.\n"
                "Кнопка 🔒 закрывает тикет."
            )
        elif cat == "utility":
            e.title = "🔧  Утилиты"
            e.description = (
                "**`/serverinfo`** — Информация о сервере\n"
                "**`/userinfo`** — Информация о пользователе\n"
                "**`/avatar`** — Аватар\n"
                "**`/poll`** — Голосование\n"
                "**`/botinfo`** — Информация о боте\n"
            )
        Style.footer(e, interaction.user, "Help")
        await interaction.response.edit_message(embed=e)


class HelpView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())


@bot.tree.command(name="help", description="❓ Помощь")
async def help_cmd(interaction: discord.Interaction):
    e = Style.embed(guild=interaction.guild, color=Style.PREMIUM)
    e.title = "📚  Server Manager — Помощь"
    e.description = (
        "Выбери категорию из меню ниже.\n\n"
        "⚙️ **Управление** — статус, настройки, объявления\n"
        "🛡️ **Модерация** — кик, бан, варн, очистка\n"
        "📩 **Тикеты** — система поддержки\n"
        "🔧 **Утилиты** — инфо, аватар, опросы\n"
    )
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
    Style.footer(e, interaction.user, "Help")
    await interaction.response.send_message(embed=e, view=HelpView(), ephemeral=True)


# ╔═══════════════════════════════════════════════════════════╗
# ║                   ЛОГИРОВАНИЕ / LOGS                      ║
# ╚═══════════════════════════════════════════════════════════╝

async def _log_action(guild, action, description, user=None):
    gd = get_guild_data(guild.id)
    log_id = gd["settings"].get("log_channel")
    if not log_id:
        return
    channel = guild.get_channel(log_id)
    if not channel:
        return
    e = discord.Embed(description=f"**[{action}]** {description}", color=Style.DARK, timestamp=datetime.datetime.now(datetime.timezone.utc))
    if user:
        e.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    e.set_footer(text=f"Log │ {action}")
    try: await channel.send(embed=e)
    except: pass


async def _notify_status(guild, embed):
    gd = get_guild_data(guild.id)
    ch_id = gd["settings"].get("status_channel")
    if not ch_id:
        return
    channel = guild.get_channel(ch_id)
    if channel:
        try: await channel.send(embed=embed)
        except: pass


# ╔═══════════════════════════════════════════════════════════╗
# ║                    СОБЫТИЯ / EVENTS                       ║
# ╚═══════════════════════════════════════════════════════════╝

@bot.event
async def on_ready():
    print(f"\n{'═' * 50}")
    print(f"  🤖 {bot.user.name} запущен!")
    print(f"  📡 ID: {bot.user.id}")
    print(f"  🌐 Серверов: {len(bot.guilds)}")
    print(f"{'═' * 50}")

    bot.add_view(TicketCreateView())
    bot.add_view(TicketCloseView())

    try:
        synced = await bot.tree.sync()
        print(f"  ✅ Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"  ❌ Ошибка синхронизации: {e}")

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(bot.guilds)} серверов 👀"))
    print(f"{'═' * 50}\n")


@bot.event
async def on_member_join(member):
    gd = get_guild_data(member.guild.id)
    s = gd["settings"]
    # Приветствие
    if s.get("welcome_channel"):
        ch = member.guild.get_channel(s["welcome_channel"])
        if ch:
            msg = s.get("welcome_message", "Добро пожаловать, {user}!")
            msg = msg.replace("{user}", member.mention).replace("{server}", member.guild.name).replace("{count}", str(member.guild.member_count))
            e = Style.embed(color=Style.SUCCESS, guild=member.guild)
            e.title = "👋  Добро пожаловать!"
            e.description = msg
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_footer(text=f"Участник #{member.guild.member_count}")
            try: await ch.send(embed=e)
            except: pass
    # Авто-роль
    if s.get("autorole"):
        role = member.guild.get_role(s["autorole"])
        if role:
            try: await member.add_roles(role)
            except: pass


# ─── Обработка ошибок ─────────────────────────────────────── #

@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        e = Style.embed("❌  Нет доступа", "Нужны права **администратора** или **модератора**.", Style.ERROR)
        Style.footer(e, interaction.user)
        try: await interaction.response.send_message(embed=e, ephemeral=True)
        except: await interaction.followup.send(embed=e, ephemeral=True)
    else:
        e = Style.embed("❌  Ошибка", f"```\n{error}\n```", Style.ERROR)
        try: await interaction.response.send_message(embed=e, ephemeral=True)
        except: await interaction.followup.send(embed=e, ephemeral=True)
        print(f"[ERROR] {error}")


# ─── Запуск ───────────────────────────────────────────────── #

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("\n❌ ОШИБКА: Неверный токен бота!")
        print("   Проверь TOKEN в config.json")
        input("\nНажми Enter чтобы закрыть...")
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        input("\nНажми Enter чтобы закрыть...")
