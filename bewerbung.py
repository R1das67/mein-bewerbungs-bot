import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Guild Configs ---
# Struktur: { guild_id: {"bewerbungs_kanal": int, "separater_kanal": int, "give_roles": [int], "remove_roles": [int]} }
guild_configs = {}

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
        config = guild_configs.get(interaction.guild.id, {})
        kanal = bot.get_channel(config.get("bewerbungs_kanal"))
        if not kanal:
            await interaction.response.send_message("❌ Kein Bewerbungskanal gesetzt! Bitte Admin fragen.", ephemeral=True)
            return

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
        await kanal.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Deine Bewerbung wurde eingereicht!", ephemeral=True)

# --- Persistent View für Bewerter ---
class BewerbungsBearbeitenView(discord.ui.View):
    def __init__(self, bewerber_id: int):
        super().__init__(timeout=None)
        self.bewerber_id = bewerber_id
        self.user_id = None
        self.result_text = None

    def update_buttons(self):
        current_editor = bewerbung_locks.get(self.bewerber_id)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "start_edit":
                    if current_editor and current_editor != self.user_id:
                        child.disabled = True
                        child.label = "Jemand bearbeitet bereits die Bewerbung"
                    else:
                        child.disabled = False
                        child.label = "Bearbeite die Bewerbungsvorlage"
                else:
                    if self.result_text:
                        child.disabled = True
                    elif current_editor and current_editor != self.user_id:
                        child.disabled = True
                        child.label = "Jemand bearbeitet bereits die Bewerbung"
                    else:
                        labels = {"bewerbung_ja": "✅ Ja", "bewerbung_nein": "❌ Nein", "bewerbung_info": "ℹ Info"}
                        child.disabled = False
                        child.label = labels[child.custom_id]

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
        if not self.user_id or bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du musst zuerst die Bewerbung bearbeiten.", ephemeral=True)
            return

        config = guild_configs.get(interaction.guild.id, {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            for rid in config.get("give_roles", []):
                role = interaction.guild.get_role(rid)
                if role:
                    await member.add_roles(role)
            for rid in config.get("remove_roles", []):
                role = interaction.guild.get_role(rid)
                if role:
                    await member.remove_roles(role)

            channel = bot.get_channel(config.get("separater_kanal"))
            if channel:
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
        if not self.user_id or bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du musst zuerst die Bewerbung bearbeiten.", ephemeral=True)
            return

        config = guild_configs.get(interaction.guild.id, {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            channel = bot.get_channel(config.get("separater_kanal"))
            if channel:
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
        if not self.user_id or bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du musst zuerst die Bewerbung bearbeiten.", ephemeral=True)
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
        config = guild_configs.get(interaction.guild.id, {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            channel = bot.get_channel(config.get("separater_kanal"))
            if channel:
                info_embed = discord.Embed(title="ℹ Info zur Bewerbung",
                                           description=f"{member.mention}, es gibt eine neue Info zu deiner Bewerbung:",
                                           color=discord.Color.blue())
                info_embed.add_field(name="Kommentar", value=self.info.value, inline=False)
                info_embed.add_field(name="Von wem", value=interaction.user.mention, inline=False)
                info_embed.timestamp = datetime.utcnow()
                await channel.send(embed=info_embed)
        await interaction.response.send_message("Info gesendet.", ephemeral=True)

# --- Start-Button View ---
class StartBewerbungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Bewerbung starten", style=discord.ButtonStyle.primary, custom_id="start_bewerbung")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BewerbungModal()
        await interaction.response.send_modal(modal)

# --- Slash Commands für Admin Config ---
@bot.tree.command(name="bewerbungsvorlagen", description="Setzt den Kanal für Bewerbungen")
@app_commands.checks.has_permissions(administrator=True)
async def bewerbungsvorlagen(interaction: discord.Interaction, kanal: discord.TextChannel):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["bewerbungs_kanal"] = kanal.id
    await interaction.response.send_message(f"✅ Bewerbungen werden ab jetzt nach {kanal.mention} gesendet.", ephemeral=True)

@bot.tree.command(name="info-zur-bewerbung", description="Setzt den Kanal für Infos zur Bewerbung")
@app_commands.checks.has_permissions(administrator=True)
async def info_zur_bewerbung(interaction: discord.Interaction, kanal: discord.TextChannel):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["separater_kanal"] = kanal.id
    await interaction.response.send_message(f"✅ Infos werden ab jetzt nach {kanal.mention} gesendet.", ephemeral=True)

@bot.tree.command(name="give-role", description="Setzt Rollen, die Bewerber nach Annahme erhalten")
@app_commands.checks.has_permissions(administrator=True)
async def give_role(interaction: discord.Interaction, *rollen: discord.Role):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["give_roles"] = [r.id for r in rollen]
    rollen_namen = ", ".join([r.mention for r in rollen])
    await interaction.response.send_message(f"✅ Folgende Rollen werden vergeben: {rollen_namen}", ephemeral=True)

@bot.tree.command(name="remove-role", description="Setzt Rollen, die nach Annahme entfernt werden")
@app_commands.checks.has_permissions(administrator=True)
async def remove_role(interaction: discord.Interaction, *rollen: discord.Role):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["remove_roles"] = [r.id for r in rollen]
    rollen_namen = ", ".join([r.mention for r in rollen])
    await interaction.response.send_message(f"✅ Folgende Rollen werden entfernt: {rollen_namen}", ephemeral=True)

# --- Bot Events ---
@bot.event
async def on_ready():
    bot.add_view(StartBewerbungView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash-Commands synchronisiert: {len(synced)}")
    except Exception as e:
        print(f"Fehler beim Sync: {e}")
    print(f"✅ Eingeloggt als {bot.user}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
