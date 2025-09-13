import os
import discord
from discord.ext import commands
from datetime import datetime

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# IDs anpassen
BEWERBUNGS_KANAL_ID = 1416458225552851066
SEPARATER_KANAL_ID = 1416491466053652481
MEMBER1_ID = 1416459765130723631
MEMBER2_ID = 1416459872278675567
REMOVE_ROLE_ID = 1416459681643106504

# --- Modal für Bewerber ---
class BewerbungModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Bewerbungs Vorlage El Salvador")
        self.roblox_name = discord.ui.TextInput(
            label="Frage 1: Roblox Name?", max_length=100
        )
        self.warum_du_entdeckt = discord.ui.TextInput(
            label="Frage 2+3: Warum du? & Wo hast du uns entdeckt?",
            style=discord.TextStyle.paragraph,
            max_length=400
        )
        self.aim = discord.ui.TextInput(label="Frage 4: Aim 1-10?", max_length=50)
        self.kleidung = discord.ui.TextInput(label="Frage 5: Kleidung kaufbar?", max_length=50)
        self.plattform = discord.ui.TextInput(
            label="Frage 6: Auf welcher Plattform spielst du?", max_length=50
        )

        self.add_item(self.roblox_name)
        self.add_item(self.warum_du_entdeckt)
        self.add_item(self.aim)
        self.add_item(self.kleidung)
        self.add_item(self.plattform)

    async def on_submit(self, interaction: discord.Interaction):
        kanal = bot.get_channel(BEWERBUNGS_KANAL_ID)
        embed = discord.Embed(
            title="Bewerbungs Vorlage El Salvador",
            description=f"Von: {interaction.user.mention}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Frage 1: Roblox Name?", value=self.roblox_name.value, inline=False)
        embed.add_field(
            name="Frage 2+3: Warum du? & Wo hast du uns entdeckt?", 
            value=self.warum_du_entdeckt.value, inline=False
        )
        embed.add_field(name="Frage 4: Aim 1-10?", value=self.aim.value, inline=False)
        embed.add_field(name="Frage 5: Kleidung kaufbar?", value=self.kleidung.value, inline=False)
        embed.add_field(
            name="Frage 6: Auf welcher Plattform spielst du?", 
            value=self.plattform.value, inline=False
        )
        embed.set_footer(text=f"LG {interaction.user.display_name}")

        view = BewerbungReviewView(interaction.user.id)
        await kanal.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Deine Bewerbung wurde eingereicht!", ephemeral=True)

# --- View für Bewerter ---
class BewerbungReviewView(discord.ui.View):
    def __init__(self, bewerber_id: int):
        super().__init__(timeout=None)
        self.bewerber_id = bewerber_id

    @discord.ui.button(label="✅ Ja", style=discord.ButtonStyle.green, custom_id="bewerbung_ja")
    async def ja_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            # Rollen vergeben
            await member.add_roles(interaction.guild.get_role(MEMBER1_ID), interaction.guild.get_role(MEMBER2_ID))
            # Rolle entfernen
            await member.remove_roles(interaction.guild.get_role(REMOVE_ROLE_ID))

            # Nachricht in separatem Kanal
            channel = bot.get_channel(SEPARATER_KANAL_ID)
            accepted_embed = discord.Embed(
                title="🎉 Bewerbung angenommen",
                description=f"{member.mention} wurde erfolgreich aufgenommen!",
                color=discord.Color.green()
            )
            accepted_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            accepted_embed.timestamp = datetime.utcnow()
            await channel.send(embed=accepted_embed)

        await interaction.response.send_message("Bewerbung angenommen.", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="❌ Nein", style=discord.ButtonStyle.red, custom_id="bewerbung_nein")
    async def nein_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            channel = bot.get_channel(SEPARATER_KANAL_ID)
            rejected_embed = discord.Embed(
                title="❌ Bewerbung abgelehnt",
                description=f"Die Bewerbung von {member.mention} wurde leider abgelehnt.",
                color=discord.Color.red()
            )
            rejected_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            rejected_embed.timestamp = datetime.utcnow()
            await channel.send(embed=rejected_embed)

        await interaction.response.send_message("Bewerbung abgelehnt.", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="ℹ Info", style=discord.ButtonStyle.blurple, custom_id="bewerbung_info")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InfoModal(self.bewerber_id))

# --- Modal für Info ---
class InfoModal(discord.ui.Modal):
    def __init__(self, bewerber_id: int):
        super().__init__(title="Zusatzinfo")
        self.bewerber_id = bewerber_id
        self.info = discord.ui.TextInput(label="Kommentar", style=discord.TextStyle.paragraph, max_length=400)
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            channel = bot.get_channel(SEPARATER_KANAL_ID)
            info_embed = discord.Embed(
                title="ℹ Info zur Bewerbung",
                description=f"{member.mention}, es gibt eine neue Info zu deiner Bewerbung:",
                color=discord.Color.blue()
            )
            info_embed.add_field(name="Kommentar", value=self.info.value, inline=False)
            info_embed.add_field(name="Von wem", value=interaction.user.mention, inline=False)
            info_embed.timestamp = datetime.utcnow()
            await channel.send(embed=info_embed)
        await interaction.response.send_message("Info gesendet.", ephemeral=True)

# --- Command zum Starten der Bewerbung ---
@bot.command()
async def bewerben(ctx):
    await ctx.send("📋 Klicke auf den Button, um die Bewerbung zu starten:", view=StartBewerbungView())

# --- Start-Button View ---
class StartBewerbungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Bewerbung starten", style=discord.ButtonStyle.primary, custom_id="start_bewerbung")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BewerbungModal()
        await interaction.response.send_modal(modal)

@bot.event
async def on_ready():
    bot.add_view(StartBewerbungView())  # persistent
    print(f"✅ Eingeloggt als {bot.user}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
