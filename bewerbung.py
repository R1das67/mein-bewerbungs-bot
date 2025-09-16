import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

CONFIG_FILE = "guild_configs.json"

# --- Intents & Bot Setup ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Konfiguration laden/speichern ---
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        guild_configs = json.load(f)
else:
    guild_configs = {}

def save_configs():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(guild_configs, f, indent=4, ensure_ascii=False)

# --- Global Lock Dictionary ---
bewerbung_locks = {}  # {bewerber_id: user_id}

# --- Modal für Bewerber ---
class BewerbungModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        config = guild_configs.get(str(guild_id), {})
        title = config.get("title", "Bewerbungsformular")
        super().__init__(title=title)

        self.answers = []
        for q in config.get("questions", []):
            input_style = discord.TextStyle.short if q["style"] == "short" else discord.TextStyle.paragraph
            input_field = discord.ui.TextInput(label=q["label"], style=input_style, max_length=400)
            self.add_item(input_field)
            self.answers.append(input_field)

    async def on_submit(self, interaction: discord.Interaction):
        config = guild_configs.get(str(interaction.guild.id))
        if not config or "bewerbung_channel" not in config:
            await interaction.response.send_message(
                "❌ Kein Bewerbungskanal wurde von einem Admin gesetzt.", ephemeral=True
            )
            return

        kanal = bot.get_channel(config["bewerbung_channel"])
        embed = discord.Embed(
            title=config.get("title", "Bewerbung"),
            description=f"Von: {interaction.user.mention}",
            color=discord.Color.blue(),
        )

        for idx, answer in enumerate(self.answers, start=1):
            embed.add_field(name=f"Frage {idx}", value=answer.value, inline=False)

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
                        child.label = "Jemand bearbeitet bereits"
                    else:
                        child.disabled = False
                        child.label = "Bearbeite die Bewerbungsvorlage"
                else:
                    if self.result_text:
                        child.disabled = True
                    elif current_editor and current_editor != self.user_id:
                        child.disabled = True
                        child.label = "Gesperrt"
                    else:
                        child.disabled = False
                        labels = {"bewerbung_ja": "✅ Ja", "bewerbung_nein": "❌ Nein", "bewerbung_info": "ℹ Info"}
                        child.label = labels[child.custom_id]

    @discord.ui.button(label="Bearbeite die Bewerbungsvorlage", style=discord.ButtonStyle.primary, custom_id="start_edit")
    async def start_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id):
            await interaction.response.send_message("Jemand bearbeitet gerade diese Bewerbung.", ephemeral=True)
            return
        bewerbung_locks[self.bewerber_id] = interaction.user.id
        self.user_id = interaction.user.id
        self.update_buttons()
        try:
            await interaction.message.edit(view=self)
        except discord.NotFound:
            pass
        await interaction.response.send_message("Du bearbeitest nun die Bewerbung.", ephemeral=True)

    @discord.ui.button(label="✅ Ja", style=discord.ButtonStyle.green, custom_id="bewerbung_ja")
    async def ja_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du kannst diese Bewerbung nicht bearbeiten.", ephemeral=True)
            return

        config = guild_configs.get(str(interaction.guild.id), {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            roles_to_add = []
            if config.get("give_role"):
                roles_to_add.append(interaction.guild.get_role(config["give_role"]))
            for rid in config.get("add_roles", []):
                roles_to_add.append(interaction.guild.get_role(rid))
            roles_to_add = [r for r in roles_to_add if r]

            try:
                if roles_to_add:
                    await member.add_roles(*roles_to_add)
                if config.get("remove_role"):
                    role_remove = interaction.guild.get_role(config["remove_role"])
                    if role_remove:
                        await member.remove_roles(role_remove)
            except discord.Forbidden:
                pass

            if config.get("info_channel"):
                channel = bot.get_channel(config["info_channel"])
                accepted_embed = discord.Embed(
                    title="🎉 Bewerbung angenommen",
                    description=f"{member.mention} wurde erfolgreich aufgenommen!",
                    color=discord.Color.green(),
                )
                accepted_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
                accepted_embed.timestamp = datetime.utcnow()
                await channel.send(embed=accepted_embed)

        self.result_text = "✅ Bewerbung wurde angenommen"
        self.update_buttons()
        bewerbung_locks.pop(self.bewerber_id, None)
        try:
            await interaction.message.edit(view=self, content=self.result_text)
        except discord.NotFound:
            pass
        await interaction.response.send_message("Bewerbung angenommen.", ephemeral=True)

    @discord.ui.button(label="❌ Nein", style=discord.ButtonStyle.red, custom_id="bewerbung_nein")
    async def nein_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du kannst diese Bewerbung nicht bearbeiten.", ephemeral=True)
            return

        config = guild_configs.get(str(interaction.guild.id), {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member and config.get("info_channel"):
            channel = bot.get_channel(config["info_channel"])
            rejected_embed = discord.Embed(
                title="❌ Bewerbung abgelehnt",
                description=f"Die Bewerbung von {member.mention} wurde leider abgelehnt.",
                color=discord.Color.red(),
            )
            rejected_embed.add_field(name="Von wem entschieden", value=interaction.user.mention)
            rejected_embed.timestamp = datetime.utcnow()
            await channel.send(embed=rejected_embed)

        self.result_text = "❌ Bewerbung wurde abgelehnt"
        self.update_buttons()
        bewerbung_locks.pop(self.bewerber_id, None)
        try:
            await interaction.message.edit(view=self, content=self.result_text)
        except discord.NotFound:
            pass
        await interaction.response.send_message("Bewerbung abgelehnt.", ephemeral=True)

    @discord.ui.button(label="ℹ Info", style=discord.ButtonStyle.blurple, custom_id="bewerbung_info")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du kannst diese Bewerbung nicht bearbeiten.", ephemeral=True)
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
        config = guild_configs.get(str(interaction.guild.id), {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member and config.get("info_channel"):
            channel = bot.get_channel(config["info_channel"])
            info_embed = discord.Embed(
                title="ℹ Info zur Bewerbung",
                description=f"{member.mention}, es gibt eine neue Info zu deiner Bewerbung:",
                color=discord.Color.blue(),
            )
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
        await interaction.response.send_modal(BewerbungModal(interaction.guild.id))

# --- Commands für Admins ---
@bot.tree.command(name="bewerbung-starten", description="Sendet die Bewerbungsnachricht mit Button in diesen Kanal")
@app_commands.checks.has_permissions(administrator=True)
async def bewerbung_starten(interaction: discord.Interaction):
    view = StartBewerbungView()
    await interaction.channel.send(
        "Klicke unten auf den Button, um deine Bewerbung zu starten:", view=view
    )
    await interaction.response.send_message("✅ Bewerbungsnachricht wurde gesendet.", ephemeral=True)

@bot.tree.command(name="set-bewerbungsvorlagen", description="Setzt den Kanal für Bewerbungen (per ID)")
@app_commands.checks.has_permissions(administrator=True)
async def set_bewerbungsvorlagen(interaction: discord.Interaction, kanal_id: str):
    kanal = bot.get_channel(int(kanal_id))
    if not kanal or not isinstance(kanal, discord.TextChannel):
        await interaction.response.send_message("❌ Ungültige Kanal-ID.", ephemeral=True)
        return
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)]["bewerbung_channel"] = kanal.id
    save_configs()
    await interaction.response.send_message(f"✅ Bewerbungskanal gesetzt auf {kanal.mention}", ephemeral=True)

@bot.tree.command(name="set-info-kanal", description="Setzt den Info-Kanal für Bewerbungen (per ID)")
@app_commands.checks.has_permissions(administrator=True)
async def set_info_kanal(interaction: discord.Interaction, kanal_id: str):
    kanal = bot.get_channel(int(kanal_id))
    if not kanal or not isinstance(kanal, discord.TextChannel):
        await interaction.response.send_message("❌ Ungültige Kanal-ID.", ephemeral=True)
        return
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)]["info_channel"] = kanal.id
    save_configs()
    await interaction.response.send_message(f"✅ Info-Kanal gesetzt auf {kanal.mention}", ephemeral=True)

@bot.tree.command(name="give-role", description="Setzt die Hauptrolle, die Bewerber nach Annahme erhalten (per ID)")
@app_commands.checks.has_permissions(administrator=True)
async def give_role(interaction: discord.Interaction, role_id: str):
    role = interaction.guild.get_role(int(role_id))
    if not role:
        await interaction.response.send_message("❌ Ungültige Rollen-ID.", ephemeral=True)
        return
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)]["give_role"] = role.id
    save_configs()
    await interaction.response.send_message(f"✅ Hauptrolle {role.mention} wird vergeben.", ephemeral=True)

@bot.tree.command(name="add-role", description="Fügt eine zusätzliche Rolle hinzu, die Bewerber nach Annahme erhalten (per ID)")
@app_commands.checks.has_permissions(administrator=True)
async def add_role(interaction: discord.Interaction, role_id: str):
    role = interaction.guild.get_role(int(role_id))
    if not role:
        await interaction.response.send_message("❌ Ungültige Rollen-ID.", ephemeral=True)
        return
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)].setdefault("add_roles", [])
    if role.id not in guild_configs[str(interaction.guild.id)]["add_roles"]:
        guild_configs[str(interaction.guild.id)]["add_roles"].append(role.id)
    save_configs()
    await interaction.response.send_message(f"✅ Zusatzrolle {role.mention} wird vergeben.", ephemeral=True)

@bot.tree.command(name="remove-role", description="Setzt die Rolle, die Bewerber nach Annahme entfernt wird (per ID)")
@app_commands.checks.has_permissions(administrator=True)
async def remove_role(interaction: discord.Interaction, role_id: str):
    role = interaction.guild.get_role(int(role_id))
    if not role:
        await interaction.response.send_message("❌ Ungültige Rollen-ID.", ephemeral=True)
        return
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)]["remove_role"] = role.id
    save_configs()
    await interaction.response.send_message(f"✅ Rolle {role.mention} wird entfernt.", ephemeral=True)

# --- Neue Commands für Bewerbungsformular ---
@bot.tree.command(name="set-bewerbungs-titel", description="Setzt den Titel des Bewerbungsformulars")
@app_commands.checks.has_permissions(administrator=True)
async def set_bewerbungs_titel(interaction: discord.Interaction, titel: str):
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)]["title"] = titel
    save_configs()
    await interaction.response.send_message(f"✅ Bewerbungs-Titel gesetzt auf: **{titel}**", ephemeral=True)

@bot.tree.command(name="add-bewerbungs-frage", description="Fügt eine Frage ins Bewerbungsformular ein")
@app_commands.checks.has_permissions(administrator=True)
async def add_bewerbungs_frage(interaction: discord.Interaction, frage: str, style: str = "short"):
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)].setdefault("questions", [])
    if style not in ("short", "paragraph"):
        await interaction.response.send_message("❌ Style muss `short` oder `paragraph` sein.", ephemeral=True)
        return
    guild_configs[str(interaction.guild.id)]["questions"].append({"label": frage, "style": style})
    save_configs()
    await interaction.response.send_message(f"✅ Frage hinzugefügt: **{frage}** ({style})", ephemeral=True)

@bot.tree.command(name="clear-bewerbungsfragen", description="Löscht alle Bewerbungsfragen")
@app_commands.checks.has_permissions(administrator=True)
async def clear_bewerbungsfragen(interaction: discord.Interaction):
    guild_configs.setdefault(str(interaction.guild.id), {})
    guild_configs[str(interaction.guild.id)]["questions"] = []
    save_configs()
    await interaction.response.send_message("✅ Alle Bewerbungsfragen wurden gelöscht.", ephemeral=True)

# --- Bot Events ---
@bot.event
async def on_ready():
    bot.add_view(StartBewerbungView())  # Persistent Start Button
    await bot.tree.sync()
    print(f"✅ Eingeloggt als {bot.user}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
