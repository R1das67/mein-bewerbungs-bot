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
PROTOKOLL_KANAL_ID = 1416458225552851065
MEMBER1_ID = 1416459765130723631
MEMBER2_ID = 1416459872278675567

# --- Modal für Bewerber ---
class BewerbungModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Bewerbungs Vorlage El Salvador")
        self.roblox_name = discord.ui.TextInput(label="Frage 1: Dein Roblox Name?")
        self.warum_du = discord.ui.TextInput(label="Frage 2: Warum ausgerechnet du?", style=discord.TextStyle.paragraph)
        self.entdeckt = discord.ui.TextInput(label="Frage 3: Wo hast du uns entdeckt?")
        self.aim = discord.ui.TextInput(label="Frage 4: Dein Aim 1-10?")
        self.kleidung = discord.ui.TextInput(label="Frage 5: Kannst du unsere Kleidung kaufen?")
        self.plattform = discord.ui.TextInput(label="Frage 6: Auf welcher Plattform spielst du?")
        self.add_item(self.roblox_name)
        self.add_item(self.warum_du)
        self.add_item(self.entdeckt)
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
        embed.add_field(name="Frage 1: Dein Roblox Name?", value=self.roblox_name.value, inline=False)
        embed.add_field(name="Frage 2: Warum ausgerechnet du?", value=self.warum_du.value, inline=False)
        embed.add_field(name="Frage 3: Wo hast du uns entdeckt?", value=self.entdeckt.value, inline=False)
        embed.add_field(name="Frage 4: Dein Aim 1-10?", value=self.aim.value, inline=False)
        embed.add_field(name="Frage 5: Kannst du unsere Kleidung kaufen?", value=self.kleidung.value, inline=False)
        embed.add_field(name="Frage 6: Auf welcher Plattform spielst du?", value=self.plattform.value, inline=False)
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
            await member.add_roles(interaction.guild.get_role(MEMBER1_ID), interaction.guild.get_role(MEMBER2_ID))
            accepted_embed = discord.Embed(
                title="🎉 Bewerbung angenommen",
                description=f"{member.mention} wurde erfolgreich aufgenommen!",
                color=discord.Color.green()
            )
            accepted_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            accepted_embed.timestamp = datetime.utcnow()
            await interaction.channel.send(embed=accepted_embed)
            log_channel = bot.get_channel(PROTOKOLL_KANAL_ID)
            log_embed = discord.Embed(title="📋 Bewerbungs-Protokoll", color=discord.Color.green)
            log_embed.add_field(name="Wer", value=member.mention, inline=False)
            log_embed.add_field(name="Wann", value=datetime.now().strftime("%d.%m.%Y %H:%M:%S"), inline=False)
            log_embed.add_field(name="Von wem angenommen", value=interaction.user.mention, inline=False)
            await log_channel.send(embed=log_embed)
        await interaction.response.send_message("Bewerbung angenommen.", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="❌ Nein", style=discord.ButtonStyle.red, custom_id="bewerbung_nein")
    async def nein_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            rejected_embed = discord.Embed(
                title="❌ Bewerbung abgelehnt",
                description=f"Die Bewerbung von {member.mention} wurde leider abgelehnt.",
                color=discord.Color.red()
            )
            rejected_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            rejected_embed.timestamp = datetime.utcnow()
            await interaction.channel.send(embed=rejected_embed)
            log_channel = bot.get_channel(PROTOKOLL_KANAL_ID)
            log_embed = discord.Embed(title="📋 Bewerbungs-Protokoll", color=discord.Color.red)
            log_embed.add_field(name="Wer", value=member.mention, inline=False)
            log_embed.add_field(name="Wann", value=datetime.now().strftime("%d.%m.%Y %H:%M:%S"), inline=False)
            log_embed.add_field(name="Von wem abgelehnt", value=interaction.user.mention, inline=False)
            await log_channel.send(embed=log_embed)
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
        self.info = discord.ui.TextInput(label="Kommentar", style=discord.TextStyle.paragraph)
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            info_embed = discord.Embed(
                title="ℹ Info zur Bewerbung",
                description=f"{member.mention}, es gibt eine neue Info zu deiner Bewerbung:",
                color=discord.Color.blue()
            )
            info_embed.add_field(name="Kommentar", value=self.info.value, inline=False)
            info_embed.add_field(name="Von wem", value=interaction.user.mention, inline=False)
            info_embed.timestamp = datetime.utcnow()
            await interaction.channel.send(embed=info_embed)
        await interaction.response.send_message("Info gesendet.", ephemeral=True)

# --- Command zum Starten der Bewerbung ---
@bot.command()
async def bewerben(ctx):
    await ctx.send("📋 Klicke auf den Button, um die Bewerbung zu starten:", view=StartBewerbungView())

class StartBewerbungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Bewerbung starten", style=discord.ButtonStyle.primary, custom_id="start_bewerbung")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BewerbungModal()
        await interaction.response.send_modal(modal)

@bot.event
async def on_ready():
    bot.add_view(StartBewerbungView())
    print(f"✅ Eingeloggt als {bot.user}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
