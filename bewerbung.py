import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta

# -----------------------------
# CONFIG
# -----------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_GUILD_ID = int(os.getenv("GUILD_ID"))  # nur für diesen Server

if not TOKEN or not ALLOWED_GUILD_ID:
    raise ValueError("❌ TOKEN oder GUILD_ID nicht gesetzt!")

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
    "ticket_counts": {
        "panel1": 0,
        "panel2": 0,
        "panel3": 0
    },
    "ticket_category": {
        "panel1": None,
        "panel2": None,
        "panel3": None
    },
    "ticket_mod_role": {
        "panel1": None,
        "panel2": None,
        "panel3": None
    },
    "embed_titles": {
        "panel2": "📨 Support Ticket",
        "panel3": "📨 Support Ticket (Panel 3)"
    },
    "embed_texts": {
        "panel2": "Bitte erstelle ein Ticket, um deine Angelegenheiten mit dem Support zu besprechen.",
        "panel3": "Bitte erstelle ein Ticket, um deine Angelegenheiten mit dem Support zu besprechen."
    }
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

# -----------------------------
# COLORS
# -----------------------------
WEISS = discord.Color.from_rgb(255, 255, 255)

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
            await interaction.response.send_message("❌ Panic-Channel oder Panic-Rolle nicht gesetzt! Nutze /set-panic-channel & /set-panic-role", ephemeral=True)
            return

        channel = interaction.client.get_channel(panic_channel_id)
        role_ping = f"<@&{panic_role_id}>"

        embed = discord.Embed(
            title=f"🚨 Panic Button pressed by {interaction.user}",
            color=discord.Color.red()
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
    return interaction.user.guild_permissions.administrator and interaction.guild.id == ALLOWED_GUILD_ID

def is_owner(interaction: discord.Interaction):
    return interaction.user.id == interaction.guild.owner_id and interaction.guild.id == ALLOWED_GUILD_ID

# -----------------------------
# TICKET HELPERS
# -----------------------------
async def user_has_open_ticket(guild, user, category_id):
    category = guild.get_channel(category_id)
    if not category:
        return False
    for channel in category.text_channels:
        if user in channel.members:
            return True
    return False

# -----------------------------
# TICKET VIEWS
# -----------------------------
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
        self.channel = channel
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

# Funktion, um Ticket-Open-Views für Panels zu erzeugen
def make_ticket_open_view(panel_name):
    class TicketOpenView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="📨 Ticket erstellen", style=discord.ButtonStyle.primary, custom_id=f"ticket_open_{panel_name}")
        async def ticket_open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if data["ticket_category"][panel_name] is None:
                await interaction.response.send_message("❌ Es wurde keine Ticket-Kategorie gesetzt!", ephemeral=True)
                return
            if await user_has_open_ticket(interaction.guild, interaction.user, data["ticket_category"][panel_name]):
                await interaction.response.send_message("⚠️ Du hast bereits ein offenes Ticket in diesem Panel.", ephemeral=True)
                return

            data["ticket_counts"][panel_name] += 1
            ticket_number = data["ticket_counts"][panel_name]
            category = interaction.guild.get_channel(data["ticket_category"][panel_name])
            if category is None:
                await interaction.response.send_message("❌ Die angegebene Kategorie existiert nicht oder ist ungültig.", ephemeral=True)
                return

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)
            }

            channel = await interaction.guild.create_text_channel(
                name=f"cf-ticket-{ticket_number}",
                category=category,
                overwrites=overwrites
            )
            embed = discord.Embed(description="Bitte haben Sie ein wenig Geduld, der Support wird sich um Sie kümmern.", color=WEISS)
            view = TicketClosePersistentView(channel)
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)
    return TicketOpenView

TicketOpenPersistentView1 = make_ticket_open_view("panel1")
TicketOpenPersistentView2 = make_ticket_open_view("panel2")
TicketOpenPersistentView3 = make_ticket_open_view("panel3")

# -----------------------------
# PANIC & WHITELIST SLASH COMMANDS
# -----------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt den Panic Button")
@app_commands.check(is_admin)
async def create_panic_button(interaction: discord.Interaction):
    embed = discord.Embed(title="🚨 Panic Button", description="Wenn du Hilfe benötigst, drücke den Panic Button.", color=discord.Color.red())
    view = PanicButtonView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panic Button erstellt!", ephemeral=True)

@bot.tree.command(name="set-panic-channel", description="Setze den Panic Channel")
@app_commands.describe(channel="Textkanal für Panic Alerts")
@app_commands.check(is_admin)
async def set_panic_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    data["panic_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"Panic Channel gesetzt auf {channel.mention}", ephemeral=True)

@bot.tree.command(name="set-panic-role", description="Setze die Rolle die beim Panic gepingt wird")
@app_commands.describe(role="Rolle die gepingt wird")
@app_commands.check(is_admin)
async def set_panic_role(interaction: discord.Interaction, role: discord.Role):
    data["panic_role"] = role.id
    save_data()
    await interaction.response.send_message(f"Panic Rolle gesetzt auf {role.mention}", ephemeral=True)

@bot.tree.command(name="add-whitelist", description="Fügt einen User zur Webhook-Whitelist hinzu")
@app_commands.describe(user="User")
@app_commands.check(is_owner)
async def add_whitelist(interaction: discord.Interaction, user: discord.User):
    if user.id not in data["whitelist"]:
        data["whitelist"].append(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde zur Whitelist hinzugefügt.", ephemeral=True)

@bot.tree.command(name="remove-whitelist", description="Entfernt einen User von der Webhook-Whitelist")
@app_commands.describe(user="User")
@app_commands.check(is_owner)
async def remove_whitelist(interaction: discord.Interaction, user: discord.User):
    if user.id in data["whitelist"]:
        data["whitelist"].remove(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde von der Whitelist entfernt.", ephemeral=True)

@bot.tree.command(name="show-whitelist", description="Zeigt die Webhook-Whitelist an")
@app_commands.check(is_owner)
async def show_whitelist(interaction: discord.Interaction):
    if not data["whitelist"]:
        await interaction.response.send_message("Whitelist ist leer.", ephemeral=True)
        return
    guild = interaction.guild
    members = []
    for uid in data["whitelist"]:
        member = guild.get_member(uid)
        members.append(member.display_name if member else str(uid))
    await interaction.response.send_message("Whitelist:\n" + "\n".join(members), ephemeral=False)

# -----------------------------
# TICKET CATEGORY & MOD ROLE SETTER
# -----------------------------
def create_ticket_commands(panel):
    @bot.tree.command(name=f"create-ticket-in-{panel}" if panel != "panel1" else "create-ticket-in", description=f"Setze die Kategorie für Tickets ({panel})")
    @app_commands.check(is_admin)
    async def create_ticket_category(interaction: discord.Interaction, category: discord.TextChannel):
        data["ticket_category"][panel] = category.id
        save_data()
        await interaction.response.send_message(f"✅ Ticket Kategorie ({panel}) gesetzt: {category.mention}", ephemeral=True)

    @bot.tree.command(name=f"set-ticket-mod-{panel}" if panel != "panel1" else "set-ticket-mod", description=f"Setze die Ticket-Mod Rolle ({panel})")
    @app_commands.check(is_admin)
    async def set_ticket_mod(interaction: discord.Interaction, role: discord.Role):
        data["ticket_mod_role"][panel] = role.id
        save_data()
        await interaction.response.send_message(f"✅ Ticket Mod Rolle ({panel}) gesetzt: {role.mention}", ephemeral=True)

for p in ["panel1", "panel2", "panel3"]:
    create_ticket_commands(p)

# -----------------------------
# TICKET START COMMANDS
# -----------------------------
def create_ticket_start(panel, view_class, title_key=None, text_key=None):
    @bot.tree.command(name=f"ticket-starten-{panel}" if panel != "panel1" else "ticket-starten", description=f"Erstellt den Ticket Button ({panel})")
    @app_commands.check(is_admin)
    async def start_ticket(interaction: discord.Interaction):
        title = data["embed_titles"][panel] if title_key else "📨 Support Ticket"
        text = data["embed_texts"][panel] if text_key else "Bitte erstelle ein Ticket, um deine Angelegenheiten mit dem Support zu besprechen."
        embed = discord.Embed(title=title, description=text, color=WEISS)
        await interaction.channel.send(embed=embed, view=view_class())
        await interaction.response.send_message(f"✅ Ticket-Nachricht ({panel}) wurde gesendet.", ephemeral=True)

create_ticket_start("panel1", TicketOpenPersistentView1)
create_ticket_start("panel2", TicketOpenPersistentView2, "embed_titles", "embed_texts")
create_ticket_start("panel3", TicketOpenPersistentView3, "embed_titles", "embed_texts")

# -----------------------------
# ANTI-WEBHOOK
# -----------------------------
@bot.event
async def on_webhooks_update(channel):
    if channel.guild.id != ALLOWED_GUILD_ID:
        return
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

# -----------------------------
# $close COMMAND
# -----------------------------
@bot.command(name="close")
async def close_ticket(ctx):
    if isinstance(ctx.channel, discord.TextChannel):
        if ctx.channel.name.lower().startswith("cf-ticket-"):
            await ctx.send("✅ Ticket wird geschlossen...")
            await asyncio.sleep(2)
            await ctx.channel.delete()
        else:
            await ctx.send("❌ Dieser Befehl kann nur in einem Ticket-Channel verwendet werden.")
    else:
        await ctx.send("❌ Dieser Befehl kann nur in einem Textkanal verwendet werden.")

# -----------------------------
# BOT READY
# -----------------------------
@bot.event
async def on_ready():
    if bot.get_guild(ALLOWED_GUILD_ID):
        bot.add_view(PanicButtonView())
        bot.add_view(TicketOpenPersistentView1())
        bot.add_view(TicketOpenPersistentView2())
        bot.add_view(TicketOpenPersistentView3())
    await bot.tree.sync()
    print(f"Bot ist online als {bot.user}")

# -----------------------------
# RUN BOT
# -----------------------------
bot.run(TOKEN)
