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
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🚨 Panic",
        style=discord.ButtonStyle.danger,
        custom_id="panic_button_main"
    )
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        # Step 1: Roblox Username
        await interaction.response.send_message("Your Roblox-Username:", ephemeral=True)

        def check_user(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel

        username_msg = await bot.wait_for("message", check=check_user)
        username = username_msg.content

        # Step 2: Location
        await interaction.followup.send("Where are you on the map?", ephemeral=True)

        location_msg = await bot.wait_for("message", check=check_user)
        location = location_msg.content

        # Validate settings
        if panic_channel_id is None or member_role_id is None:
            await interaction.followup.send(
                "❌ Panic-Server oder Member-Rolle nicht gesetzt! Nutze **/create-panic-server** und **/choose-member-role**.",
                ephemeral=True
            )
            return

        channel = bot.get_channel(panic_channel_id)
        role_ping = f"<@&{member_role_id}>"

        # Normal panic message
        await channel.send(f"**__🚨{role_ping} panic!__🚨**")

        # Embed details
        embed2 = discord.Embed(
            title=f"{interaction.user.name} pressed the panic button 🚨",
            color=discord.Color.red()
        )
        embed2.add_field(name="Roblox Username", value=username, inline=False)
        embed2.add_field(name="Location", value=location, inline=False)
        embed2.set_footer(text=f"User ID: {interaction.user.id}")

        await channel.send(embed=embed2)

        await interaction.followup.send("🚨 Panic wurde erfolgreich gesendet!", ephemeral=True)


# -------------------------------------------------------
# Bot Ready → load persistent views
# -------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot eingeloggt als {bot.user}")
    bot.add_view(PanicButton())
    try:
        await bot.tree.sync()
        print("Slash Commands synchronisiert.")
    except Exception as e:
        print(e)


# -------------------------------------------------------
# Commands
# -------------------------------------------------------
@bot.tree.command(name="create-panic-server", description="Setzt den Kanal, in dem Panics gesendet werden.")
async def set_panic_server(interaction: discord.Interaction, channel_id: str):
    global panic_channel_id
    panic_channel_id = int(channel_id)
    await interaction.response.send_message(
        f"✅ Panic-Server Kanal gesetzt auf <#{channel_id}>", ephemeral=True
    )


@bot.tree.command(name="choose-member-role", description="Legt die Member Rolle fest, die gepingt werden soll.")
async def choose_member_role(interaction: discord.Interaction, role_id: str):
    global member_role_id
    member_role_id = int(role_id)
    await interaction.response.send_message(
        f"✅ Member-Rolle gesetzt auf <@&{role_id}>", ephemeral=True
    )


# -------------------------------------------------------
# Create Panic Button (unsichtbare Antwort!)
# -------------------------------------------------------
@bot.tree.command(name="create-panic-button", description="Erstellt einen Panic Button.")
async def create_panic_button(interaction: discord.Interaction):

    # Unsichtbare Antwort (Discord zeigt NICHT an, dass der Bot geantwortet hat!)
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🚨 Panic Button",
        description="If you need help from an emergency call server in Hamburg, press the button.",
        color=discord.Color.red()
    )

    # Sichtbare Nachricht (Button + Embed)
    await interaction.followup.send(embed=embed, view=PanicButton())


# -------------------------------------------------------
# Run bot
# -------------------------------------------------------
bot.run(TOKEN)
