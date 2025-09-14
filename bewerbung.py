import os
import discord
from discord.ext import commands
from datetime import datetime

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- IDs ---
BEWERBUNGS_KANAL_ID = 1410687834615971969
SEPARATER_KANAL_ID = 1416506000864841880
MEMBER1_ID = 1394071445125992639
MEMBER2_ID = 1398301896967454862
REMOVE_ROLE_ID = 1394071445713457284

# --- Global Lock Dictionary ---
bewerbung_locks = {}  # {bewerber_id: user_id}

# --- Modal für Bewerber ---
class BewerbungModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Bewerbungs Vorlage Atrax")
        self.roblox_name = discord.ui.TextInput(label="Frage 1: Roblox Name?", max_length=100)
        self.warum_du_entdeckt = discord.ui.TextInput(label="Frage 2+3: Warum du? & Woher kennst du uns?", style=discord.TextStyle.paragraph, max_length=400)
        self.aim = discord.ui.TextInput(label="Frage 4: Aim 1-10?", max_length=50)
        self.kleidung = discord.ui.TextInput(label="Frage 5: Kleidung kaufbar?", max_length=50)
        self.plattform = discord.ui.TextInput(label="Frage 6: Auf welcher Plattform spielst du?", max_length=50)
        self.add_item(self.roblox_name)
        self.add_item(self.warum_du_entdeckt)
        self.add_item(self.aim)
        self.add_item(self.kleidung)
        self.add_item(self.plattform)

    async def on_submit(self, interaction: discord.Interaction):
        kanal = bot.get_channel(BEWERBUNGS_KANAL_ID)
        embed = discord.Embed(title="Bewerbungs Vorlage Atrax",
                              description=f"Von: {interaction.user.mention}",
                              color=discord.Color.blue())
        embed.add_field(name="Frage 1: Roblox Name?", value=self.roblox_name.value, inline=False)
        embed.add_field(name="Frage 2+3: Warum du? & Wo hast du uns entdeckt?", value=self.warum_du_entdeckt.value, inline=False)
        embed.add_field(name="Frage 4: Aim 1-10?", value=self.aim.value, inline=False)
        embed.add_field(name="Frage 5: Kleidung kaufbar?", value=self.kleidung.value, inline=False)
        embed.add_field(name="Frage 6: Auf welcher Plattform spielst du?", value=self.plattform.value, inline=False)
        embed.set_footer(text=f"LG {interaction.user.display_name}")

        view = BewerbungsBearbeitenView(interaction.user.id)
        msg = await kanal.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Deine Bewerbung wurde eingereicht!", ephemeral=True)

# --- Persistent View für Bewerter: Lock + Review ---
class BewerbungsBearbeitenView(discord.ui.View):
    def __init__(self, bewerber_id: int):
        super().__init__(timeout=None)
        self.bewerber_id = bewerber_id
        # Buttons korrekt initialisieren
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False
        self.user_id = None
        self.result_text = None  # Zeigt Status nach Ja/Nein

    def update_buttons(self):
        """Aktualisiert Buttons je nachdem, wer gerade die Bewerbung bearbeitet"""
        current_editor = bewerbung_locks.get(self.bewerber_id)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "start_edit":
                    if current_editor and current_editor != self.user_id:
                        child.disabled = True
                        child.label = f"Jemand bearbeitet bereits die Bewerbung"
                    else:
                        child.disabled = False
                        child.label = "Bearbeite die Bewerbungsvorlage"
                else:  # Ja/Nein/Info Buttons
                    if self.result_text:  # Bewerbung abgeschlossen
                        child.disabled = True
                    elif current_editor and current_editor != self.user_id:
                        child.disabled = True
                        child.label = f"Jemand bearbeitet bereits die Bewerbung"
                    else:
                        child.disabled = False
                        child.label = {"bewerbung_ja": "✅ Ja", "bewerbung_nein": "❌ Nein", "bewerbung_info": "ℹ Info"}[child.custom_id]

    @discord.ui.button(label="Bearbeite die Bewerbungsvorlage", style=discord.ButtonStyle.primary, custom_id="start_edit")
    async def start_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id):
            await interaction.response.send_message("Jemand bearbeitet gerade diese Bewerbung.", ephemeral=True)
            return
        bewerbung_locks[self.bewerber_id] = interaction.user.id
        self.user_id = interaction.user.id
        self.update_buttons()
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Du bearbeitest nun die Bewerbung. Du kannst jetzt Info/Ja/Nein nutzen.", ephemeral=True)

    @discord.ui.button(label="✅ Ja", style=discord.ButtonStyle.green, custom_id="bewerbung_ja")
    async def ja_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.user_id:
            await interaction.response.send_message('Klick auf den Knopf "Bearbeite die Bewerbungsvorlage", um die Knöpfe Ja, Nein, Info zu nutzen.', ephemeral=True)
            return
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Jemand anderes bearbeitet gerade diese Bewerbung.", ephemeral=True)
            return
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            await member.add_roles(interaction.guild.get_role(MEMBER1_ID), interaction.guild.get_role(MEMBER2_ID))
            await member.remove_roles(interaction.guild.get_role(REMOVE_ROLE_ID))
            channel = bot.get_channel(SEPARATER_KANAL_ID)
            accepted_embed = discord.Embed(title="🎉 Bewerbung angenommen",
                                           description=f"{member.mention} wurde erfolgreich aufgenommen!",
                                           color=discord.Color.green())
            accepted_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            accepted_embed.timestamp = datetime.utcnow()
            await channel.send(embed=accepted_embed)
        self.result_text = "✅ Bewerbung wurde angenommen"
        self.update_buttons()
        bewerbung_locks.pop(self.bewerber_id, None)
        await interaction.message.edit(view=self, content=self.result_text)
        await interaction.response.send_message("Bewerbung angenommen.", ephemeral=True)

    @discord.ui.button(label="❌ Nein", style=discord.ButtonStyle.red, custom_id="bewerbung_nein")
    async def nein_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.user_id:
            await interaction.response.send_message('Klick auf den Knopf "Bearbeite die Bewerbungsvorlage", um die Knöpfe Ja, Nein, Info zu nutzen.', ephemeral=True)
            return
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Jemand anderes bearbeitet gerade diese Bewerbung.", ephemeral=True)
            return
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            channel = bot.get_channel(SEPARATER_KANAL_ID)
            rejected_embed = discord.Embed(title="❌ Bewerbung abgelehnt",
                                           description=f"Die Bewerbung von {member.mention} wurde leider abgelehnt.",
                                           color=discord.Color.red())
            rejected_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            rejected_embed.timestamp = datetime.utcnow()
            await channel.send(embed=rejected_embed)
        self.result_text = "❌ Bewerbung wurde abgelehnt"
        self.update_buttons()
        bewerbung_locks.pop(self.bewerber_id, None)
        await interaction.message.edit(view=self, content=self.result_text)
        await interaction.response.send_message("Bewerbung abgelehnt.", ephemeral=True)

    @discord.ui.button(label="ℹ Info", style=discord.ButtonStyle.blurple, custom_id="bewerbung_info")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.user_id:
            await interaction.response.send_message('Klick auf den Knopf "Bearbeite die Bewerbungsvorlage", um die Knöpfe Ja, Nein, Info zu nutzen.', ephemeral=True)
            return
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Jemand anderes bearbeitet gerade diese Bewerbung.", ephemeral=True)
            return
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
            info_embed = discord.Embed(title="ℹ Info zur Bewerbung",
                                       description=f"{member.mention}, es gibt eine neue Info zu deiner Bewerbung:",
                                       color=discord.Color.blue())
            info_embed.add_field(name="Kommentar", value=self.info.value, inline=False)
            info_embed.add_field(name="Von wem", value=interaction.user.mention, inline=False)
            info_embed.timestamp = datetime.utcnow()
            await channel.send(embed=info_embed)
        await interaction.response.send_message("Info gesendet.", ephemeral=True)

# --- Command zum Starten ---
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

# --- Bot Events ---
@bot.event
async def on_ready():
    bot.add_view(StartBewerbungView())  # Persistent Start
    print(f"✅ Eingeloggt als {bot.user}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))


