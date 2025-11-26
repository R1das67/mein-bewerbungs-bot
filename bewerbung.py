import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Speicher für Kanal & Rolle
panic_channel_id = None
member_role_id = None


# -------------------------------------------------------
# Persistent Panic Button View
# -------------------------------------------------------
class PanicButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistente View

    @discord.ui.button(label="🚨 Panic", style=discord.ButtonStyle.danger, custom_id="panic_button_main")
    async def panic_btn(self, button: discord.ui.Button, btn_interaction: discord.Interaction):

        # Step 1 – Roblox Username
        await btn_interaction.response.send_message("Your Roblox-Username:", ephemeral=True)

        def check_user(m):
            return m.author.id == btn_interaction.user.id and m.channel == btn_interaction.channel

        username_msg = await bot.wait_for("message", check=check_user)
        username = username_msg.content

        # Step 2 – Location
        await btn_interaction.followup.send("Where are you on the map?", ephemeral=True)

        location_msg = await bot.wait_for("message", check=check_user)
        location = location_msg.content

        # Check required settings
        if panic_channel_id is None or member_role_id is None:
            await btn_interaction.followup.send(
                "❌ Panic-Server oder Member-Rolle nicht gesetzt! Bitte zuerst **/create-panic-server** und **/choose-member-role** nutzen.",
                ephemeral=True
            )
            return

        channel = bot.get_channel(panic_channel_id)
        role_ping = f"<@&{member_role_id}>"

        # Normal message
        await channel.send(f"**__🚨{role_ping} panic!__🚨**")

        # Embed message
        embed2 = discord.Embed(
            title=f"{btn_interaction.user.name} pressed the panic button 🚨",
            color=discord.Color.red()
        )
        embed2.add_field(name="Roblox Username", value=username, inline=False)
        embed2.add_field(name="Location", value=location, inline=False)
        embed2.set_footer(text=f"User ID: {btn_interaction.user.id}")

        await channel.send(embed=embed2)

        await btn_interaction.followup.send("🚨 Panic wurde erfolgreich gesendet!", ephemeral=True)


# -------------------------------------------------------
# Bot Ready → persistent views laden
# -------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot eingeloggt als {bot.user}")
    bot.add_view(PanicButton())  # <- WICHTIG: Persistente Views registrieren
    try:
        await bot.tree.sync()
        print("Slash Commands synchronisiert.")
    except Exception as e:
        print(e)


# -------------------------------------------------------
# Slash Command: Set Panic Server
# -------------------------------------------------------
@bot.tree.command(name="create-panic-server", description="Setzt den Kanal, in dem Panics gesendet werden.")
async def set_panic_server(interaction: discord.Interaction, channel_id: str):
    global panic_channel_id
    panic_channel_id = int(channel_id)

    await interaction.response.send_message(
        f"✅ Panic-Server Kanal gesetzt auf <#{channel_id}>", ephemeral=True
    )


# -------------------------------------------------------
# Slash Command: Set Member Role
# -------------------------------------------------------
@bot.tree.command(name="choose-member-role", description="Legt die Member Rolle fest, die gepingt werden soll.")
async def choose_member_role(interaction: discord.Interaction, role_id: str):
    global member_role_id
    member_role_id = int(role_id)

    await interaction.response.send_message(
        f"✅ Member-Rolle gesetzt auf <@&{role_id}>", ephemeral=True
    )


# -------------------------------------------------------
# Slash Command: Create Panic Button
# -------------------------------------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button.")
async def create_panic_button(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🚨 Panic Button",
        description="If you need help from an emergency call server in Hamburg, press the button.",
        color=discord.Color.red()
    )

    # Sende persistenten Button
    await interaction.response.send_message(embed=embed, view=PanicButton())


# -------------------------------------------------------
# Start bot
# -------------------------------------------------------
bot.run(TOKEN)
