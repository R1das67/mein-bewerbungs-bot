import os
import discord
from discord.ext import commands
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
intents.guilds = True

bot = commands.Bot(command_prefix="$", intents=intents)

# -----------------------------
# DEFAULT DATA
# -----------------------------
default_data = {
    "guilds": {}
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


def get_guild_data(guild_id: int):
    if str(guild_id) not in data["guilds"]:
        data["guilds"][str(guild_id)] = {
            "panic_channel": None,
            "panic_role": None,
            "whitelist": [],
            "webhook_attempts": {},
            "tickets": {
                "panel1": {"category": None, "mod_role": None, "title": "📨 Support Ticket", "text": "Bitte erstelle ein Ticket.", "count": 0},
                "panel2": {"category": None, "mod_role": None, "title": "📨 Support Ticket", "text": "Bitte erstelle ein Ticket.", "count": 0},
                "panel3": {"category": None, "mod_role": None, "title": "📨 Support Ticket", "text": "Bitte erstelle ein Ticket.", "count": 0}
            }
        }
    return data["guilds"][str(guild_id)]


# -----------------------------
# HELPER CHECKS
# -----------------------------
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator


def is_owner(interaction: discord.Interaction):
    return interaction.user.id == interaction.guild.owner_id


# -----------------------------
# PANIC BUTTON
# -----------------------------
class PanicModal(discord.ui.Modal, title="🚨 Panic Request"):
    username = discord.ui.TextInput(label="Roblox Username", placeholder="Enter your username", required=True, max_length=50)
    location = discord.ui.TextInput(label="Location", placeholder="Where are you?", required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        guild_data = get_guild_data(interaction.guild.id)
        panic_channel_id = guild_data["panic_channel"]
        panic_role_id = guild_data["panic_role"]
        if not panic_channel_id or not panic_role_id:
            await interaction.response.send_message("❌ Panic-Channel oder Role nicht gesetzt!", ephemeral=True)
            return
        channel = interaction.guild.get_channel(panic_channel_id)
        role_ping = f"<@&{panic_role_id}>"
        await channel.send(f"**__🚨 {role_ping} panic!__🚨**")
        embed = discord.Embed(title=f"{interaction.user} pressed the panic button 🚨", color=discord.Color.red())
        embed.add_field(name="Roblox Username", value=self.username.value, inline=False)
        embed.add_field(name="Location", value=self.location.value, inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Panic alert sent!", ephemeral=True)


class PanicButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PanicModal())


@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button.")
async def create_panic_button(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return
    embed = discord.Embed(title="🚨 Panic Button", description="If you need help, press the button.", color=discord.Color.red())
    view = PanicButtonView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panic button created!", ephemeral=True)


@bot.tree.command(name="set-panic-channel", description="Set the channel for panic alerts")
@app_commands.describe(channel="Channel where panic alerts will be sent")
async def set_panic_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["panic_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"Panic alert channel set to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="set-panic-role", description="Set the role to ping on panic")
@app_commands.describe(role="Role that will be pinged")
async def set_panic_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["panic_role"] = role.id
    save_data()
    await interaction.response.send_message(f"Panic role set to {role.mention}.", ephemeral=True)


# -----------------------------
# WHITELIST COMMANDS
# -----------------------------
@bot.tree.command(name="add-whitelist", description="Fügt einen User zur Webhook-Whitelist hinzu")
@app_commands.describe(user="User")
async def add_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur der Server-Eigentümer darf diesen Command nutzen.", ephemeral=True)
        return
    guild_data = get_guild_data(interaction.guild.id)
    if user.id not in guild_data["whitelist"]:
        guild_data["whitelist"].append(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde zur Whitelist hinzugefügt.", ephemeral=True)


@bot.tree.command(name="remove-whitelist", description="Entfernt einen User von der Webhook-Whitelist")
@app_commands.describe(user="User")
async def remove_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur der Server-Eigentümer darf diesen Command nutzen.", ephemeral=True)
        return
    guild_data = get_guild_data(interaction.guild.id)
    if user.id in guild_data["whitelist"]:
        guild_data["whitelist"].remove(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde von der Whitelist entfernt.", ephemeral=True)


@bot.tree.command(name="show-whitelist", description="Zeigt die Whitelist an")
async def show_whitelist(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    if not guild_data["whitelist"]:
        await interaction.response.send_message("Whitelist ist leer.", ephemeral=False)
        return
    names = []
    for uid in guild_data["whitelist"]:
        member = interaction.guild.get_member(uid)
        names.append(member.display_name if member else str(uid))
    await interaction.response.send_message("Whitelist:\n" + "\n".join(names), ephemeral=False)


# -----------------------------
# ANTI-WEBHOOK SYSTEM
# -----------------------------
@bot.event
async def on_webhooks_update(channel):
    guild_data = get_guild_data(channel.guild.id)
    current_hooks = await channel.webhooks()
    now = datetime.utcnow()
    if not hasattr(bot, "existing_hooks"):
        bot.existing_hooks = {}
    old_hooks = bot.existing_hooks.get(channel.id, [])
    bot.existing_hooks[channel.id] = [h.id for h in current_hooks]

    for hook in current_hooks:
        if hook.id in old_hooks:
            continue
        creator = None
        try:
            creator = await channel.guild.fetch_member(hook.user.id)
        except:
            continue
        if creator.id not in guild_data["whitelist"]:
            await hook.delete()
            user_id = creator.id
            timestamps = guild_data["webhook_attempts"].get(str(user_id), [])
            timestamps = [ts for ts in timestamps if datetime.fromisoformat(ts) > now - timedelta(seconds=30)]
            timestamps.append(now.isoformat())
            guild_data["webhook_attempts"][str(user_id)] = timestamps
            save_data()
            if len(timestamps) >= 2:
                try:
                    await creator.kick(reason="Zu viele nicht-whitelisted Webhook-Erstellungen")
                    del guild_data["webhook_attempts"][str(user_id)]
                    save_data()
                except:
                    pass


# -----------------------------
# TICKET SYSTEM
# -----------------------------
WEISS = discord.Color.from_rgb(255, 255, 255)


async def user_has_open_ticket(guild, user, category_id):
    category = guild.get_channel(category_id)
    if not category:
        return False
    for ch in category.text_channels:
        if str(user.id) in [str(o.id) for o in ch.overwrites if isinstance(o, discord.Member)]:
            return True
    return False


async def create_ticket(interaction, panel_name):
    guild_data = get_guild_data(interaction.guild.id)
    panel = guild_data["tickets"][panel_name]
    category_id = panel["category"]
    if not category_id:
        await interaction.response.send_message("❌ Ticket-Kategorie nicht gesetzt!", ephemeral=True)
        return
    if await user_has_open_ticket(interaction.guild, interaction.user, category_id):
        await interaction.response.send_message("⚠️ Du hast bereits ein offenes Ticket in diesem Panel.", ephemeral=True)
        return

    panel["count"] += 1
    ticket_name = f"cf-ticket-{panel['count']}"
    category = interaction.guild.get_channel(category_id)
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)
    }
    channel = await interaction.guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
    embed = discord.Embed(description="Bitte haben Sie ein wenig Geduld, der Support wird sich um Sie kümmern.", color=WEISS)
    view = TicketClosePersistentView(channel)
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)
    save_data()


class TicketOpenPersistentView(discord.ui.View):
    def __init__(self, panel_name):
        super().__init__(timeout=None)
        self.panel_name = panel_name

    @discord.ui.button(label="📨 Ticket erstellen", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def ticket_open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket(interaction, self.panel_name)


class TicketClosePersistentView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="❌ Ticket schließen", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def ticket_close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmCloseView(self.channel)
        await interaction.response.send_message("Möchtest du das Ticket wirklich schließen?", view=view, ephemeral=True)


class ConfirmCloseView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=30)
        self.add_item(ConfirmYesButton(channel))
        self.add_item(ConfirmNoButton())


class ConfirmYesButton(discord.ui.Button):
    def __init__(self, channel):
        super().__init__(label="Ja", style=discord.ButtonStyle.success, custom_id="confirm_yes")
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Ticket wird geschlossen...", ephemeral=True)
        await asyncio.sleep(2)
        await self.channel.delete()


class ConfirmNoButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Nein", style=discord.ButtonStyle.secondary, custom_id="confirm_no")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("❌ Ticket bleibt geöffnet.", ephemeral=True)


# -----------------------------
# CLOSE COMMAND
# -----------------------------
@bot.command(name="close")
async def close_ticket(ctx):
    if ctx.channel.name.startswith("cf-ticket-"):
        await ctx.send("✅ Ticket wird geschlossen...")
        await asyncio.sleep(2)
        await ctx.channel.delete()
    else:
        await ctx.send("❌ Dieser Befehl kann nur in einem Ticket-Channel verwendet werden.")


# -----------------------------
# BOT READY
# -----------------------------
@bot.event
async def on_ready():
    # Persistente Views registrieren
    bot.add_view(PanicButtonView())
    for guild_id, guild_data in data["guilds"].items():
        for panel_name in ["panel1", "panel2", "panel3"]:
            bot.add_view(TicketOpenPersistentView(panel_name))
    # Alte Hooks merken
    bot.existing_hooks = {}
    for g in bot.guilds:
        for ch in g.text_channels:
            hooks = await ch.webhooks()
            bot.existing_hooks[ch.id] = [h.id for h in hooks]
    await bot.tree.sync()
    print(f"✅ Bot online als {bot.user}")


bot.run(TOKEN)
