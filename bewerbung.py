import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

panic_channel_id = None
member_role_id = None


# -------------------------------------------------------
# Modal für Panic Input
# -------------------------------------------------------
class PanicModal(discord.ui.Modal, title="🚨 Panic Details"):
    
    username = discord.ui.TextInput(
        label="Roblox Username",
        placeholder="Dein Roblox Name...",
        required=True,
        max_length=40
    )

    location = discord.ui.TextInput(
        label="Your Location",
        placeholder="Wo bist du auf der Map?",
        style=discord.TextStyle.long,
        required=True,
        max_length=200
    )

    def __init__(self, user, bot):
        super().__init__()
        self.user = user
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        global panic_channel_id, member_role_id

        if panic_channel_id is None or member_role_id is None:
            await interaction.response.send_message(
                "❌ Panic-Server oder Member-Rolle fehlen! Nutze /create-panic-server & /choose-member-role",
                ephemeral=True
            )
            return

        channel = self.bot.get_channel(panic_channel_id)
        role_ping = f"<@&{member_role_id}>"

        # Normale Warnung
        await channel.send(f"**__🚨{role_ping} panic!__🚨**")

        # Embed
        embed = discord.Embed(
            title=f"{self.user.name} pressed the panic button 🚨",
            color=discord.Color.red()
        )
        embed.add_field(name="Roblox Username", value=self.username.value, inline=False)
        embed.add_field(name="Location", value=self.location.value, inline=False)
        embed.set_footer(text=f"User ID: {self.user.id}")

        await channel.send(embed=embed)

        # Unsichtbare Antwort (wird NICHT angezeigt)
        await interaction.response.defer()


# -------------------------------------------------------
# Persistent Panic Button View
# -------------------------------------------------------
class PanicButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🚨 Panic",
        style=discord.ButtonStyle.danger,
        custom_id="panic_button_main"
    )
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanicModal(interaction.user, bot)
        await interaction.response.send_modal(modal)


# -------------------------------------------------------
# Bot Ready → persistent views
# -------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot eingeloggt als {bot.user}")
    bot.add_view(PanicButton())  # Wichtig für persistente Buttons
    await bot.tree.sync()


# -------------------------------------------------------
# Commands
# -------------------------------------------------------
@bot.tree.command(name="create-panic-server", description="Setze den Kanal für Panics.")
async def set_panic_server(interaction: discord.Interaction, channel_id: str):
    global panic_channel_id
    panic_channel_id = int(channel_id)
    await interaction.response.send_message(
        f"✅ Panic-Server gesetzt auf <#{channel_id}>", ephemeral=True
    )


@bot.tree.command(name="choose-member-role", description="Setze die Rolle, die gepingt werden soll.")
async def choose_member_role(interaction: discord.Interaction, role_id: str):
    global member_role_id
    member_role_id = int(role_id)
    await interaction.response.send_message(
        f"✅ Member-Rolle gesetzt auf <@&{role_id}>", ephemeral=True
    )


# -------------------------------------------------------
# COMMAND: Create Panic Button → ohne sichtbare Antwort!
# -------------------------------------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button.")
async def create_panic_button(interaction: discord.Interaction):

    # Unsichtbare Antwort (Discord zeigt NICHTS an!)
    await interaction.response.defer(ephemeral=False)

    embed = discord.Embed(
        title="🚨 Panic Button",
        description="If you need help from an emergency call server in Hamburg, press the button.",
        color=discord.Color.red()
    )

    # Nachricht editieren = kein Bot-Symbol sichtbar
    await interaction.followup.send(embed=embed, view=PanicButton())


# -------------------------------------------------------
# Run bot
# -------------------------------------------------------
bot.run(TOKEN)
