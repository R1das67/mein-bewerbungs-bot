import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta
import aiohttp

# -----------------------------
# CONFIG
# -----------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN nicht gesetzt!")

DATA_FILE = "bot_data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.webhooks = True
intents.guilds = True

bot = commands.Bot(command_prefix="$", intents=intents)

# -----------------------------
# DATA HANDLING
# -----------------------------
default_data = {
    "panic_channel": None,
    "panic_role": None,
    "whitelist": [],
    "webhook_attempts": {},
    "agentblox_channel": None,
    "agentblox_users": {}
}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = default_data
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ================== COLORS ==================
WEISS = discord.Color.from_rgb(255, 255, 255)
RED = discord.Color.red()
GREEN = discord.Color.green()

# -----------------------------
# PANIC MODAL
# -----------------------------
class PanicModal(discord.ui.Modal, title="🚨 Panic Request"):
    username = discord.ui.TextInput(label="Roblox Username", placeholder="Dein Roblox Username", required=True, max_length=50)
    location = discord.ui.TextInput(label="Location", placeholder="Wo befindest du dich?", required=True, max_length=100)
    additional_info = discord.ui.TextInput(label="Additional Information", placeholder="Zusätzliche Informationen", required=False, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        panic_channel_id = data.get("panic_channel")
        panic_role_id = data.get("panic_role")
        if panic_channel_id is None or panic_role_id is None:
            await interaction.response.send_message(
                "❌ Panic-Channel oder Panic-Rolle nicht gesetzt! Nutze /set-panic-channel & /set-panic-role",
                ephemeral=True
            )
            return

        channel = interaction.client.get_channel(panic_channel_id)
        role_ping = f"<@&{panic_role_id}>"

        embed = discord.Embed(
            title=f"🚨 Panic Button pressed by {interaction.user}",
            color=RED
        )
        embed.add_field(name="Roblox Username", value=self.username.value, inline=False)
        embed.add_field(name="Location", value=self.location.value, inline=False)
        embed.add_field(name="Additional Information", value=self.additional_info.value or "Keine", inline=False)

        await channel.send(f"**{role_ping} Panic Alert!**", embed=embed)
        await interaction.response.send_message("✅ Panic Alert gesendet!", ephemeral=True)

# -----------------------------
# PANIC BUTTON
# -----------------------------
class PanicButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button")
    async def panic_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanicModal()
        await interaction.response.send_modal(modal)

# -----------------------------
# ADMIN CHECKS
# -----------------------------
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator

def is_owner(interaction: discord.Interaction):
    return interaction.user.id == interaction.guild.owner_id

# -----------------------------
# SLASH COMMANDS: PANIC
# -----------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt den Panic Button")
async def create_panic_button(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Befehl nutzen.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🚨 Panic Button",
        description="Wenn du Hilfe benötigst, drücke den Panic Button.",
        color=RED
    )
    view = PanicButtonView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panic Button erstellt!", ephemeral=True)

@bot.tree.command(name="set-panic-channel", description="Setze den Panic Channel")
@app_commands.describe(channel="Textkanal für Panic Alerts")
async def set_panic_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Befehl nutzen.", ephemeral=True)
        return
    data["panic_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"Panic Channel gesetzt auf {channel.mention}", ephemeral=True)

@bot.tree.command(name="set-panic-role", description="Setze die Rolle die beim Panic gepingt wird")
@app_commands.describe(role="Rolle die gepingt wird")
async def set_panic_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Befehl nutzen.", ephemeral=True)
        return
    data["panic_role"] = role.id
    save_data()
    await interaction.response.send_message(f"Panic Rolle gesetzt auf {role.mention}", ephemeral=True)

# -----------------------------
# SLASH COMMANDS: WHITELIST
# -----------------------------
@bot.tree.command(name="add-whitelist", description="Fügt einen User zur Webhook-Whitelist hinzu")
@app_commands.describe(user="User")
async def add_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur Server-Eigentümer darf diesen Befehl nutzen.", ephemeral=True)
        return
    if user.id not in data["whitelist"]:
        data["whitelist"].append(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde zur Whitelist hinzugefügt.", ephemeral=True)

@bot.tree.command(name="remove-whitelist", description="Entfernt einen User von der Webhook-Whitelist")
@app_commands.describe(user="User")
async def remove_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur Server-Eigentümer darf diesen Befehl nutzen.", ephemeral=True)
        return
    if user.id in data["whitelist"]:
        data["whitelist"].remove(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde von der Whitelist entfernt.", ephemeral=True)

@bot.tree.command(name="show-whitelist", description="Zeigt die Webhook-Whitelist an")
async def show_whitelist(interaction: discord.Interaction):
    if not data["whitelist"]:
        await interaction.response.send_message("Whitelist ist leer.", ephemeral=False)
        return
    guild = interaction.guild
    members = []
    for uid in data["whitelist"]:
        member = guild.get_member(uid)
        members.append(member.display_name if member else str(uid))
    await interaction.response.send_message("Whitelist:\n" + "\n".join(members), ephemeral=False)

# -----------------------------
# ANTI-WEBHOOK
# -----------------------------
@bot.event
async def on_webhooks_update(channel):
    guild = channel.guild
    current_hooks = await channel.webhooks()
    now = datetime.utcnow()
    if not hasattr(bot, "existing_hooks"):
        bot.existing_hooks = {}
    old_hooks = bot.existing_hooks.get(channel.id, [])
    bot.existing_hooks[channel.id] = [h.id for h in current_hooks]

    for hook in current_hooks:
        if hook.id in old_hooks:
            continue
        creator = getattr(hook, "user", None)
        if not creator:
            continue
        if creator.id not in data["whitelist"]:
            await hook.delete()
            user_id = creator.id
            timestamps = data["webhook_attempts"].get(str(user_id), [])
            timestamps = [ts for ts in timestamps if datetime.fromisoformat(ts) > now - timedelta(seconds=30)]
            timestamps.append(now.isoformat())
            data["webhook_attempts"][str(user_id)] = timestamps
            save_data()
            if len(timestamps) >= 2:
                try:
                    member = await guild.fetch_member(user_id)
                    await member.kick(reason="Zu viele nicht-whitelisted Webhook-Erstellungen")
                    del data["webhook_attempts"][str(user_id)]
                    save_data()
                except:
                    pass

# ================= AGENT BLOX =================
async def fetch_roblox_user(usernames):
    async with aiohttp.ClientSession() as session:
        users = {}
        for username in usernames:
            url = f"https://api.roblox.com/users/get-by-username?username={username}"
            async with session.get(url) as r:
                if r.status == 200:
                    json_data = await r.json()
                    if "Id" in json_data:
                        users[username] = json_data
        return users

async def fetch_avatar_thumbnail(user_id):
    return f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png"

@bot.tree.command(name="add-user", description="Fügt einen Roblox-Spieler zur Überwachung hinzu")
async def add_user(interaction: discord.Interaction, username: str):
    if username in data["agentblox_users"]:
        await interaction.response.send_message("Benutzer ist bereits überwacht.", ephemeral=True)
        return
    data["agentblox_users"][username] = {"status": None, "join_time": None}
    save_data()
    await interaction.response.send_message(f"{username} wurde zur AgentBlox-Liste hinzugefügt.", ephemeral=True)

@bot.tree.command(name="remove-user", description="Entfernt einen Roblox-Spieler von der Überwachung")
async def remove_user(interaction: discord.Interaction, username: str):
    if username in data["agentblox_users"]:
        del data["agentblox_users"][username]
        save_data()
        await interaction.response.send_message(f"{username} wurde entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{username} ist nicht in der Liste.", ephemeral=True)

@bot.tree.command(name="choose-channel", description="Wählt den Kanal für AgentBlox Nachrichten")
async def choose_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    data["agentblox_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"AgentBlox Kanal gesetzt auf {channel.mention}", ephemeral=True)

async def check_agentblox_status():
    if not data["agentblox_users"] or not data["agentblox_channel"]:
        return
    usernames = list(data["agentblox_users"].keys())
    users = await fetch_roblox_user(usernames)
    channel = bot.get_channel(data["agentblox_channel"])
    if channel is None:
        return
    for username, info in data["agentblox_users"].items():
        user_info = users.get(username)
        if not user_info:
            continue
        user_id = user_info["Id"]
        display_name = user_info["Username"]
        # Beispiel Status: Online/Offline zufällig (da Roblox API das nicht direkt liefert)
        import random
        status = random.choice(["online", "offline"])
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        avatar_url = await fetch_avatar_thumbnail(user_id)
        if status == "online":
            embed = discord.Embed(title=f"**__{display_name} ({username})__**", description="🟢Is right now online!", color=GREEN)
            embed.add_field(name="Date", value=now, inline=True)
            embed.set_thumbnail(url=avatar_url)
        else:
            embed = discord.Embed(title=f"**__{display_name} ({username})__**", description="🔴Is right now offline!", color=RED)
            embed.add_field(name="Date", value=now, inline=True)
            embed.add_field(name="Played for", value="N/A", inline=True)
            embed.set_thumbnail(url=avatar_url)
        await channel.send(embed=embed)
        data["agentblox_users"][username]["status"] = status
    save_data()

@tasks.loop(seconds=30)
async def agentblox_loop():
    await check_agentblox_status()

# -----------------------------
# BOT READY
# -----------------------------
@bot.event
async def on_ready():
    bot.add_view(PanicButtonView())
    agentblox_loop.start()
    await bot.tree.sync()
    print(f"Bot ist online als {bot.user}")

bot.run(TOKEN)
