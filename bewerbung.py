import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Konfiguration pro Server ---
# guild_id: {
#   "bewerbung_channel": int,
#   "info_channel": int,
#   "give_role": int,
#   "add_roles": [int, ...],
#   "remove_role": int
# }
guild_configs = {}

# --- Global Lock Dictionary ---
bewerbung_locks = {}  # {bewerber_id: user_id}


# --- Modal für Bewerber ---
class BewerbungModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Bewerbungs Vorlage Atrax")
        self.roblox_name = discord.ui.TextInput(label="Frage 1: Roblox Name?", max_length=100)
        self.warum_du_entdeckt = discord.ui.TextInput(
            label="Frage 2+3: Warum du? & Woher kennst du uns?",
            style=discord.TextStyle.paragraph,
            max_length=400,
        )
        self.aim = discord.ui.TextInput(label="Frage 4: Aim 1-10?", max_length=50)
        self.kleidung = discord.ui.TextInput(label="Frage 5: Kleidung kaufbar?", max_length=50)
        self.plattform = discord.ui.TextInput(label="Frage 6: Auf welcher Plattform spielst du?", max_length=50)

        self.add_item(self.roblox_name)
        self.add_item(self.warum_du_entdeckt)
        self.add_item(self.aim)
        self.add_item(self.kleidung)
        self.add_item(self.plattform)

    async def on_submit(self, interaction: discord.Interaction):
        config = guild_configs.get(interaction.guild.id)
        if not config or "bewerbung_channel" not in config:
            await interaction.response.send_message(
                "❌ Kein Bewerbungskanal wurde von einem Admin gesetzt.", ephemeral=True
            )
            return

        kanal = bot.get_channel(config["bewerbung_channel"])
        embed = discord.Embed(
            title="Bewerbungs Vorlage Atrax",
            description=f"Von: {interaction.user.mention}",
            color=discord.Color.blue(),
        )
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
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Du bearbeitest nun die Bewerbung.", ephemeral=True)

    @discord.ui.button(label="✅ Ja", style=discord.ButtonStyle.green, custom_id="bewerbung_ja")
    async def ja_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du kannst diese Bewerbung nicht bearbeiten.", ephemeral=True)
            return

        config = guild_configs.get(interaction.guild.id, {})
        member = interaction.guild.get_member(self.bewerber_id)
        if member:
            roles_to_add = []
            if config.get("give_role"):
                roles_to_add.append(interaction.guild.get_role(config["give_role"]))
            for rid in config.get("add_roles", []):
                roles_to_add.append(interaction.guild.get_role(rid))
            roles_to_add = [r for r in roles_to_add if r]

            if roles_to_add:
                await member.add_roles(*roles_to_add)

            if config.get("remove_role"):
                role_remove = interaction.guild.get_role(config["remove_role"])
                if role_remove:
                    await member.remove_roles(role_remove)

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
        await interaction.message.edit(view=self, content=self.result_text)
        await interaction.response.send_message("Bewerbung angenommen.", ephemeral=True)

    @discord.ui.button(label="❌ Nein", style=discord.ButtonStyle.red, custom_id="bewerbung_nein")
    async def nein_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if bewerbung_locks.get(self.bewerber_id) != interaction.user.id:
            await interaction.response.send_message("Du kannst diese Bewerbung nicht bearbeiten.", ephemeral=True)
            return

        config = guild_configs.get(interaction.guild.id, {})
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
        await interaction.message.edit(view=self, content=self.result_text)
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
        config = guild_configs.get(interaction.guild.id, {})
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
        await interaction.response.send_modal(BewerbungModal())


# --- Commands für Admins ---
@bot.tree.command(name="set-bewerbungsvorlagen", description="Setzt den Kanal für Bewerbungen")
@app_commands.checks.has_permissions(administrator=True)
async def set_bewerbungsvorlagen(interaction: discord.Interaction, kanal: discord.TextChannel):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["bewerbung_channel"] = kanal.id
    await interaction.response.send_message(f"✅ Bewerbungskanal gesetzt auf {kanal.mention}", ephemeral=True)


@bot.tree.command(name="set-info-kanal", description="Setzt den Info/Seperater-Kanal für Bewerbungen")
@app_commands.checks.has_permissions(administrator=True)
async def set_info_kanal(interaction: discord.Interaction, kanal: discord.TextChannel):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["info_channel"] = kanal.id
    await interaction.response.send_message(f"✅ Info-Kanal gesetzt auf {kanal.mention}", ephemeral=True)


@bot.tree.command(name="give-role", description="Setzt die Hauptrolle, die Bewerber nach Annahme erhalten")
@app_commands.checks.has_permissions(administrator=True)
async def give_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["give_role"] = rolle.id
    await interaction.response.send_message(f"✅ Hauptrolle {rolle.mention} wird vergeben.", ephemeral=True)


@bot.tree.command(name="add-role", description="Fügt eine zusätzliche Rolle hinzu, die Bewerber nach Annahme erhalten")
@app_commands.checks.has_permissions(administrator=True)
async def add_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id].setdefault("add_roles", [])
    if rolle.id not in guild_configs[interaction.guild.id]["add_roles"]:
        guild_configs[interaction.guild.id]["add_roles"].append(rolle.id)
    await interaction.response.send_message(f"✅ Zusatzrolle {rolle.mention} wird vergeben.", ephemeral=True)


@bot.tree.command(name="remove-role", description="Setzt die Rolle, die Bewerber nach Annahme entfernt wird")
@app_commands.checks.has_permissions(administrator=True)
async def remove_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_configs.setdefault(interaction.guild.id, {})
    guild_configs[interaction.guild.id]["remove_role"] = rolle.id
    await interaction.response.send_message(f"✅ Rolle {rolle.mention} wird entfernt.", ephemeral=True)


# --- Bot Events ---
@bot.event
async def on_ready():
    bot.add_view(StartBewerbungView())  # Persistent Start Button
    await bot.tree.sync()
    print(f"✅ Eingeloggt als {bot.user}")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
