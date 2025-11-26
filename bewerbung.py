import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta

# ================= CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ Discord Token nicht gesetzt!")

DATA_FILE = "bot_data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.webhooks = True

bot = commands.Bot(command_prefix="$", intents=intents)

# ================= DATA HANDLING =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ================= HELPERS =================
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator


def is_owner(interaction: discord.Interaction):
    return interaction.user.id == interaction.guild.owner_id


def get_guild_data(guild_id):
    if str(guild_id) not in data:
        data[str(guild_id)] = {
            "panic_channel": None,
            "panic_role": None,
            "whitelist": [],
            "webhook_attempts": {},
            "ticket_count": 0,
            "ticket_panels": {
                "1": {"category": None, "mod_role": None, "embed_title": "📨 Support Ticket", "embed_text": "Bitte erstelle ein Ticket."},
                "2": {"category": None, "mod_role": None, "embed_title": "📨 Support Ticket (Panel 2)", "embed_text": "Bitte erstelle ein Ticket."},
                "3": {"category": None, "mod_role": None, "embed_title": "📨 Support Ticket (Panel 3)", "embed_text": "Bitte erstelle ein Ticket."},
            }
        }
    return data[str(guild_id)]


# ================= PANIC SYSTEM =================
class PanicModal(discord.ui.Modal, title="🚨 Panic Request"):
    username = discord.ui.TextInput(label="Roblox Username", placeholder="Enter your username", required=True, max_length=50)
    location = discord.ui.TextInput(label="Location", placeholder="Describe your location", required=True, max_length=100)
    information = discord.ui.TextInput(label="Additional Info", placeholder="Any extra information", required=False, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        guild_data = get_guild_data(interaction.guild.id)
        panic_channel_id = guild_data.get("panic_channel")
        panic_role_id = guild_data.get("panic_role")

        if panic_channel_id is None or panic_role_id is None:
            await interaction.response.send_message("❌ Panic-Channel oder Role nicht gesetzt!", ephemeral=True)
            return

        channel = interaction.client.get_channel(panic_channel_id)
        role_ping = f"<@&{panic_role_id}>"

        await channel.send(f"**__🚨 {role_ping} panic! __🚨**")
        embed = discord.Embed(title=f"{interaction.user} pressed the panic button 🚨", color=discord.Color.red())
        embed.add_field(name="Roblox Username", value=self.username.value, inline=False)
        embed.add_field(name="Location", value=self.location.value, inline=False)
        embed.add_field(name="Information", value=self.information.value or "Keine zusätzlichen Infos", inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Panic alert sent!", ephemeral=True)


class PanicButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanicModal()
        await interaction.response.send_modal(modal)


@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button")
async def create_panic_button(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return
    embed = discord.Embed(title="🚨 Panic Button", description="Drücke den Button im Notfall.", color=discord.Color.red())
    view = PanicButtonView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panic Button erstellt!", ephemeral=True)


@bot.tree.command(name="set-panic-channel", description="Setze den Channel für Panic Alerts")
@app_commands.describe(channel="Channel für Panic Alerts")
async def set_panic_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["panic_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"Panic-Channel gesetzt: {channel.mention}", ephemeral=True)


@bot.tree.command(name="set-panic-role", description="Setze die Role für Panic Alerts")
@app_commands.describe(role="Role die gepingt wird")
async def set_panic_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Nur Admins dürfen diesen Command nutzen.", ephemeral=True)
        return
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["panic_role"] = role.id
    save_data()
    await interaction.response.send_message(f"Panic-Role gesetzt: {role.mention}", ephemeral=True)


# ================= WHITELIST SYSTEM =================
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
    await interaction.response.send_message(f"{user} zur Whitelist hinzugefügt.", ephemeral=True)


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
    await interaction.response.send_message(f"{user} von Whitelist entfernt.", ephemeral=True)


@bot.tree.command(name="show-whitelist", description="Zeigt die Webhook-Whitelist an")
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


# ================= ANTI-WEBHOOK =================
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
            ts = guild_data["webhook_attempts"].get(str(creator.id), [])
            ts = [t for t in ts if datetime.fromisoformat(t) > now - timedelta(seconds=30)]
            ts.append(now.isoformat())
            guild_data["webhook_attempts"][str(creator.id)] = ts
            save_data()
            if len(ts) >= 2:
                try:
                    await creator.kick(reason="Zu viele nicht-whitelisted Webhook-Erstellungen")
                    del guild_data["webhook_attempts"][str(creator.id)]
                    save_data()
                except:
                    pass


# ================= TICKET SYSTEM =================
async def user_has_open_ticket(user, category_id):
    category = user.guild.get_channel(category_id)
    if not category:
        return False
    for ch in category.text_channels:
        if user in ch.members:
            return True
    return False


class ConfirmCloseView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=30)
        self.channel = channel
        self.add_item(ConfirmYesButton(channel))
        self.add_item(ConfirmNoButton())


class ConfirmYesButton(discord.ui.Button):
    def __init__(self, channel):
        super().__init__(label="Ja", style=discord.ButtonStyle.success)
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Ticket wird geschlossen...", ephemeral=True)
        await asyncio.sleep(2)
        await self.channel.delete()


class ConfirmNoButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Nein", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("❌ Ticket bleibt geöffnet.", ephemeral=True)


class TicketOpenView(discord.ui.View):
    def __init__(self, guild_id, panel):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.panel = str(panel)

    @discord.ui.button(label="📨 Ticket erstellen", style=discord.ButtonStyle.primary)
    async def ticket_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_data = get_guild_data(interaction.guild.id)
        panel_data = guild_data["ticket_panels"][self.panel]
        category_id = panel_data["category"]
        if category_id is None:
            await interaction.response.send_message("❌ Keine Ticket-Kategorie gesetzt!", ephemeral=True)
            return
        if await user_has_open_ticket(interaction.user, category_id):
            await interaction.response.send_message("⚠️ Du hast bereits ein offenes Ticket.", ephemeral=True)
            return
        guild_data["ticket_count"] += 1
        save_data()
        channel_name = f"cf-ticket-{guild_data['ticket_count']}"
        category = interaction.guild.get_channel(category_id)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        }
        ch = await interaction.guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        embed = discord.Embed(description="Bitte haben Sie etwas Geduld, der Support meldet sich.", color=discord.Color.white())
        view = ConfirmCloseView(ch)
        await ch.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ticket erstellt: {ch.mention}", ephemeral=True)


def register_ticket_commands(panel):
    panel_str = str(panel)

    @bot.tree.command(name=f"set-ticket-category-{panel}", description=f"Setze Ticket Kategorie Panel {panel}")
    @app_commands.check(is_admin)
    async def set_category(interaction: discord.Interaction, category: discord.TextChannel):
        guild_data = get_guild_data(interaction.guild.id)
        guild_data["ticket_panels"][panel_str]["category"] = category.id
        save_data()
        await interaction.response.send_message(f"✅ Kategorie Panel {panel} gesetzt: {category.mention}", ephemeral=True)

    @bot.tree.command(name=f"set-ticket-mod-{panel}", description=f"Setze Ticket Mod Role Panel {panel}")
    @app_commands.check(is_admin)
    async def set_mod(interaction: discord.Interaction, role: discord.Role):
        guild_data = get_guild_data(interaction.guild.id)
        guild_data["ticket_panels"][panel_str]["mod_role"] = role.id
        save_data()
        await interaction.response.send_message(f"✅ Mod Rolle Panel {panel} gesetzt: {role.mention}", ephemeral=True)

    @bot.tree.command(name=f"set-embed-title-{panel}", description=f"Setze Embed Überschrift Panel {panel}")
    @app_commands.check(is_admin)
    async def set_title(interaction: discord.Interaction, title: str):
        guild_data = get_guild_data(interaction.guild.id)
        guild_data["ticket_panels"][panel_str]["embed_title"] = title
        save_data()
        await interaction.response.send_message(f"✅ Embed Titel Panel {panel} gesetzt: **{title}**", ephemeral=True)

    @bot.tree.command(name=f"set-embed-text-{panel}", description=f"Setze Embed Text Panel {panel}")
    @app_commands.check(is_admin)
    async def set_text(interaction: discord.Interaction, text: str):
        guild_data = get_guild_data(interaction.guild.id)
        guild_data["ticket_panels"][panel_str]["embed_text"] = text
        save_data()
        await interaction.response.send_message(f"✅ Embed Text Panel {panel} gesetzt.", ephemeral=True)

    @bot.tree.command(name=f"ticket-send-{panel}", description=f"Erstellt den Ticket Button Panel {panel}")
    @app_commands.check(is_admin)
    async def ticket_send(interaction: discord.Interaction):
        guild_data = get_guild_data(interaction.guild.id)
        panel_data = guild_data["ticket_panels"][panel_str]
        if panel_data["category"] is None:
            await interaction.response.send_message("❌ Keine Kategorie gesetzt!", ephemeral=True)
            return
        embed = discord.Embed(title=panel_data["embed_title"], description=panel_data["embed_text"], color=discord.Color.white())
        view = TicketOpenView(interaction.guild.id, panel)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ticket Button Panel {panel} gesendet.", ephemeral=True)


for i in range(1, 4):
    register_ticket_commands(i)


# ================= $close COMMAND =================
@bot.command(name="close")
async def close_ticket(ctx):
    if isinstance(ctx.channel, discord.TextChannel):
        if ctx.channel.name.startswith("cf-ticket-"):
            await ctx.send("✅ Ticket wird geschlossen...")
            await asyncio.sleep(2)
            await ctx.channel.delete()
        else:
            await ctx.send("❌ Dieser Befehl kann nur in einem Ticket-Channel verwendet werden.")
    else:
        await ctx.send("❌ Dieser Befehl kann nur in einem Textkanal verwendet werden.")


# ================= BOT READY =================
@bot.event
async def on_ready():
    bot.add_view(PanicButtonView())
    await bot.tree.sync()
    print(f"Bot online als {bot.user}")


bot.run(TOKEN)
