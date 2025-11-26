import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta

# -----------------------------
# CONFIG & TOKEN
# -----------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN ist nicht gesetzt! Bitte als Umgebungsvariable hinzufügen.")

DATA_FILE = "bot_data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.webhooks = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# DATA HANDLING
# -----------------------------
default_data = {
    "panic_channel": None,
    "panic_role": None,
    "whitelist": [],
    "webhook_attempts": {}  # user_id : [timestamps]
}

# Lade oder erstelle JSON
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


# -----------------------------
# MODAL FÜR PANIC BUTTON
# -----------------------------
class PanicModal(discord.ui.Modal, title="🚨 Panic Request"):
    username = discord.ui.TextInput(
        label="Your Roblox Username",
        placeholder="Enter your username",
        required=True,
        max_length=50
    )

    location = discord.ui.TextInput(
        label="Where are you?",
        placeholder="Describe your location",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        panic_channel_id = data.get("panic_channel")
        panic_role_id = data.get("panic_role")
        if panic_channel_id is None or panic_role_id is None:
            await interaction.response.send_message(
                "❌ Panic-Channel oder Member-Rolle nicht gesetzt! Nutze /set-panic-channel & /set-panic-role",
                ephemeral=True
            )
            return

        channel = interaction.client.get_channel(panic_channel_id)
        role_ping = f"<@&{panic_role_id}>"

        await channel.send(f"**__🚨{role_ping} panic!__🚨**")
        embed = discord.Embed(
            title=f"{interaction.user} pressed the panic button 🚨",
            color=discord.Color.red()
        )
        embed.add_field(name="Roblox Username", value=self.username.value, inline=False)
        embed.add_field(name="Location", value=self.location.value, inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Panic alert sent!", ephemeral=True)


# -----------------------------
# PERSISTENTER PANIC BUTTON
# -----------------------------
class PanicButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanicModal()
        await interaction.response.send_modal(modal)


# -----------------------------
# HELPER: Admin check
# -----------------------------
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator


def is_owner(interaction: discord.Interaction):
    return interaction.user.id == interaction.guild.owner_id


# -----------------------------
# SLASH COMMANDS
# -----------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button.")
async def create_panic_button(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🚨 Panic Button",
        description="If you need help from an emergency call server in Hamburg, press the button.",
        color=discord.Color.red()
    )
    view = PanicButtonView()

    await interaction.channel.send(embed=embed, view=view)
    await interaction.followup.send("✅ Panic button created!", ephemeral=True)


@bot.tree.command(name="set-panic-channel", description="Set the channel for panic alerts")
@app_commands.describe(channel="Channel where panic alerts will be sent")
async def set_panic_server(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return

    data["panic_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"Panic alert channel set to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="set-panic-role", description="Set the role to ping on panic")
@app_commands.describe(role="Role that will be pinged when someone presses the panic button")
async def set_panic_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return

    data["panic_role"] = role.id
    save_data()
    await interaction.response.send_message(f"Panic role set to {role.mention}.", ephemeral=True)


# -----------------------------
# WHITELIST COMMANDS
# -----------------------------
@bot.tree.command(name="add-whitelist", description="Fügt einen User zur Webhook-Whitelist hinzu")
@app_commands.describe(user="User ID")
async def add_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur der Server-Eigentümer darf diesen Command nutzen.", ephemeral=True)
        return

    if user.id not in data["whitelist"]:
        data["whitelist"].append(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde zur Whitelist hinzugefügt.", ephemeral=True)


@bot.tree.command(name="remove-whitelist", description="Entfernt einen User von der Webhook-Whitelist")
@app_commands.describe(user="User ID")
async def remove_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur der Server-Eigentümer darf diesen Command nutzen.", ephemeral=True)
        return

    if user.id in data["whitelist"]:
        data["whitelist"].remove(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde von der Whitelist entfernt.", ephemeral=True)


@bot.tree.command(name="show-whitelist", description="Zeigt die Whitelist an")
async def show_whitelist(interaction: discord.Interaction):
    if not data["whitelist"]:
        await interaction.response.send_message("Whitelist ist leer.", ephemeral=False)
        return
    guild = interaction.guild
    names = []
    for uid in data["whitelist"]:
        member = guild.get_member(uid)
        if member:
            names.append(member.display_name)
        else:
            names.append(str(uid))
    await interaction.response.send_message("Whitelist:\n" + "\n".join(names), ephemeral=False)


# -----------------------------
# ANTI-WEBHOOK SYSTEM
# -----------------------------
@bot.event
async def on_webhooks_update(channel):
    guild = channel.guild
    current_hooks = await channel.webhooks()
    now = datetime.utcnow()

    # Alte Hooks merken
    if not hasattr(bot, "existing_hooks"):
        bot.existing_hooks = {}
    old_hooks = bot.existing_hooks.get(channel.id, [])
    bot.existing_hooks[channel.id] = [h.id for h in current_hooks]

    for hook in current_hooks:
        if hook.id in old_hooks:
            continue  # schon vorher vorhanden

        # Nicht whitelisted
        creator = None
        try:
            creator = await guild.fetch_member(hook.user.id)
        except:
            continue  # keine info

        if creator.id not in data["whitelist"]:
            await hook.delete()
            user_id = creator.id
            timestamps = data["webhook_attempts"].get(str(user_id), [])
            timestamps = [ts for ts in timestamps if datetime.fromisoformat(ts) > now - timedelta(seconds=30)]
            timestamps.append(now.isoformat())
            data["webhook_attempts"][str(user_id)] = timestamps
            save_data()

            if len(timestamps) >= 2:
                # Kick user
                try:
                    await creator.kick(reason="Zu viele nicht-whitelisted Webhook-Erstellungen")
                    del data["webhook_attempts"][str(user_id)]
                    save_data()
                except:
                    pass


# -----------------------------
# BOT READY
# -----------------------------
@bot.event
async def on_ready():
    bot.add_view(PanicButtonView())
    # Alte Hooks merken
    bot.existing_hooks = {}
    for g in bot.guilds:
        for ch in g.text_channels:
            hooks = await ch.webhooks()
            bot.existing_hooks[ch.id] = [h.id for h in hooks]
    await bot.tree.sync()
    print(f"Bot logged in as {bot.user}")


bot.run(TOKEN)

