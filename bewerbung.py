import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Speicher für Panic-Channel & Role
PANIC_CHANNEL = None
PANIC_ROLE = None


# -----------------------------------------
#         MODAL FÜR PANIC BUTTON
# -----------------------------------------
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

        global PANIC_CHANNEL, PANIC_ROLE

        if PANIC_CHANNEL is None or PANIC_ROLE is None:
            await interaction.response.send_message(
                "❌ Panic-Server oder Member-Rolle nicht gesetzt! Nutze /set-panic-server & /set-panic-role",
                ephemeral=True
            )
            return

        channel = interaction.client.get_channel(PANIC_CHANNEL)
        role_ping = f"<@&{PANIC_ROLE}>"

        # Normale Nachricht
        await channel.send(f"**__🚨{role_ping} panic!__🚨**")

        # Embed
        embed = discord.Embed(
            title=f"{interaction.user} pressed the panic button 🚨",
            color=discord.Color.red()
        )
        embed.add_field(name="Roblox Username", value=self.username.value, inline=False)
        embed.add_field(name="Location", value=self.location.value, inline=False)
        await channel.send(embed=embed)

        # Ephemeral Bestätigung an User
        await interaction.response.send_message("✅ Panic alert sent!", ephemeral=True)


# -----------------------------------------
#        PERSISTENTER PANIC BUTTON
# -----------------------------------------
class PanicButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanicModal()
        await interaction.response.send_modal(modal)


# -----------------------------------------
#        SLASH: CREATE PANIC BUTTON
# -----------------------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button.")
async def create_panic_button(interaction: discord.Interaction):

    # ⚡ Verhindert, dass Discord die Slash-Command-Blase zeigt
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🚨 Panic Button",
        description="If you need help from an emergency call server in Hamburg, press the button.",
        color=discord.Color.red()
    )
    view = PanicButtonView()

    # Button + Embed als eigene Nachricht posten
    await interaction.channel.send(embed=embed, view=view)

    # Optionale kurze Bestätigung (privat)
    await interaction.followup.send("✅ Panic button created!", ephemeral=True)


# -----------------------------------------
#        SLASH: PANIC CHANNEL SETZEN
# -----------------------------------------
@bot.tree.command(name="set-panic-server", description="Set the channel for panic alerts")
@app_commands.describe(channel="Channel where panic alerts will be sent")
async def set_panic_server(interaction: discord.Interaction, channel: discord.TextChannel):
    global PANIC_CHANNEL
    PANIC_CHANNEL = channel.id
    await interaction.response.send_message(f"Panic alert channel set to {channel.mention}.", ephemeral=True)


# -----------------------------------------
#        SLASH: PANIC ROLE SETZEN
# -----------------------------------------
@bot.tree.command(name="set-panic-role", description="Set the role to ping on panic")
@app_commands.describe(role="Role that will be pinged when someone presses the panic button")
async def set_panic_role(interaction: discord.Interaction, role: discord.Role):
    global PANIC_ROLE
    PANIC_ROLE = role.id
    await interaction.response.send_message(f"Panic role set to {role.mention}.", ephemeral=True)


# -----------------------------------------
#       PERSISTENTE BUTTONS AKTIVIEREN
# -----------------------------------------
@bot.event
async def on_ready():
    bot.add_view(PanicButtonView())  # Wichtig für persistente Buttons
    await bot.tree.sync()
    print(f"Bot logged in as {bot.user}")


bot.run(TOKEN)

