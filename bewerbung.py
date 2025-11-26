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
# DATA HANDLING
# -----------------------------
default_data = {
    "panic_channel": None,
    "panic_role": None,
    "whitelist": [],
    "webhook_attempts": {}
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
# PANIC MODAL
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
    information = discord.ui.TextInput(
        label="Additional Information",
        placeholder="Any extra info",
        required=False,
        max_length=200
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
        embed.add_field(name="Additional Information", value=self.information.value or "Keine", inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Panic alert sent!", ephemeral=True)

# -----------------------------
# PERSISTENT PANIC BUTTON
# -----------------------------
class PanicButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanicModal()
        await interaction.response.send_modal(modal)

# -----------------------------
# ADMIN / OWNER CHECK
# -----------------------------
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator

def is_owner(interaction: discord.Interaction):
    return interaction.user.id == interaction.guild.owner_id

# -----------------------------
# PANIC COMMANDS
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
@app_commands.describe(user="User")
async def add_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur der Server-Eigentümer darf diesen Command nutzen.", ephemeral=True)
        return
    if user.id not in data["whitelist"]:
        data["whitelist"].append(user.id)
        save_data()
    await interaction.response.send_message(f"{user} wurde zur Whitelist hinzugefügt.", ephemeral=True)

@bot.tree.command(name="remove-whitelist", description="Entfernt einen User von der Webhook-Whitelist")
@app_commands.describe(user="User")
async def remove_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Nur der Server-Eigentümer darf diesen Command nutzen.", ephemeral=True)
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
    names = []
    for uid in data["whitelist"]:
        member = guild.get_member(uid)
        names.append(member.display_name if member else str(uid))
    await interaction.response.send_message("Whitelist:\n" + "\n".join(names), ephemeral=False)

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
        creator = None
        try:
            creator = await guild.fetch_member(hook.user.id)
        except:
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
                    await creator.kick(reason="Zu viele nicht-whitelisted Webhook-Erstellungen")
                    del data["webhook_attempts"][str(user_id)]
                    save_data()
                except:
                    pass

# -----------------------------
# TICKET SYSTEM (3 Panels)
# -----------------------------
# Ticket Speicher (nur pro Server)
class TicketData:
    def __init__(self):
        self.ticket_count_1 = 0
        self.ticket_category_1 = None
        self.ticket_mod_1 = None
        self.ticket_count_2 = 0
        self.ticket_category_2 = None
        self.ticket_mod_2 = None
        self.embed_title_2 = "📨 Support Ticket"
        self.embed_text_2 = "Bitte erstelle ein Ticket, um deine Angelegenheiten mit dem Support zu besprechen."
        self.ticket_count_3 = 0
        self.ticket_category_3 = None
        self.ticket_mod_3 = None
        self.embed_title_3 = "📨 Support Ticket"
        self.embed_text_3 = "Bitte erstelle ein Ticket, um deine Angelegenheiten mit dem Support zu besprechen."

guild_ticket_data = {}  # guild_id: TicketData

def get_guild_data(guild_id):
    if guild_id not in guild_ticket_data:
        guild_ticket_data[guild_id] = TicketData()
    return guild_ticket_data[guild_id]

# -----------------------------
# Admin check for tickets
# -----------------------------
def ticket_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator

# -----------------------------
# HELPER: Check if user already has ticket
# -----------------------------
async def user_has_open_ticket(guild, user, category_id):
    category = guild.get_channel(category_id)
    if not category:
        return False
    for channel in category.text_channels:
        if channel.permissions_for(user).view_channel:
            if str(user.id) in [str(o.id) for o in channel.overwrites if isinstance(o, discord.Member)]:
                return True
    return False

# -----------------------------
# Ticket Views
# -----------------------------
class TicketOpenPersistentView(discord.ui.View):
    def __init__(self, panel_number=1):
        super().__init__(timeout=None)
        self.panel_number = panel_number

    @discord.ui.button(label="📨 Ticket erstellen", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def ticket_open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_data = get_guild_data(interaction.guild.id)
        if self.panel_number == 1:
            category_id = guild_data.ticket_category_1
            guild_data.ticket_count_1 += 1
            ticket_num = guild_data.ticket_count_1
        elif self.panel_number == 2:
            category_id = guild_data.ticket_category_2
            guild_data.ticket_count_2 += 1
            ticket_num = guild_data.ticket_count_2
        else:
            category_id = guild_data.ticket_category_3
            guild_data.ticket_count_3 += 1
            ticket_num = guild_data.ticket_count_3

        if category_id is None:
            await interaction.response.send_message("❌ Es wurde keine Ticket-Kategorie gesetzt!", ephemeral=True)
            return

        if await user_has_open_ticket(interaction.guild, interaction.user, category_id):
            await interaction.response.send_message("⚠️ Du hast bereits ein offenes Ticket in diesem Panel.", ephemeral=True)
            return

        guild = interaction.guild
        category = guild.get_channel(category_id)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        }

        channel = await guild.create_text_channel(
            name=f"cf-ticket-{ticket_num}",
            category=category,
            overwrites=overwrites
        )

        await channel.send(f"<@{interaction.user.id}>")

        embed = discord.Embed(
            description="Bitte haben Sie ein wenig Geduld, der Support wird sich um Sie kümmern.",
            color=discord.Color.white()
        )
        view = TicketClosePersistentView(channel)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)

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

# -----------------------------
# TICKET SLASH COMMANDS
# -----------------------------
@bot.tree.command(name="set-ticket-category", description="Setze die Kategorie für Tickets (Panel 1)")
@app_commands.check(ticket_admin)
async def set_ticket_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    data = get_guild_data(interaction.guild.id)
    data.ticket_category_1 = category.id
    await interaction.response.send_message(f"✅ Ticket Kategorie gesetzt: {category.mention}", ephemeral=True)

@bot.tree.command(name="set-ticket-mod", description="Setze die Ticket-Mod Rolle (Panel 1)")
@app_commands.check(ticket_admin)
async def set_ticket_mod(interaction: discord.Interaction, role: discord.Role):
    data = get_guild_data(interaction.guild.id)
    data.ticket_mod_1 = role.id
    await interaction.response.send_message(f"✅ Ticket Mod Rolle gesetzt: <@&{role.id}>", ephemeral=True)

@bot.tree.command(name="ticket-starten", description="Erstellt den Ticket Button (Panel 1)")
@app_commands.check(ticket_admin)
async def ticket_starten(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📨 Support Ticket",
        description="Bitte erstelle ein Ticket, um deine Angelegenheiten mit dem Support zu besprechen.",
        color=discord.Color.white()
    )
    view = TicketOpenPersistentView(panel_number=1)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Ticket-Nachricht wurde gesendet.", ephemeral=True)

# -----------------------------
# PREFIX COMMAND TO CLOSE
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
    bot.add_view(PanicButtonView())
    await bot.tree.sync()
    print(f"Bot logged in as {bot.user}")

bot.run(TOKEN)
