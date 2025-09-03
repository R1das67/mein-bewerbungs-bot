# Discord Moderations-Bot mit Slash-Commands (timeout/endtimeout/ban/endban/kick)
# + Pro-Server-Blacklist (nur Server-Eigentümer darf verwalten)
#
# Voraussetzungen:
#   - Python 3.10+
#   - pip install -r requirements.txt
#   - Umgebungsvariable DISCORD_TOKEN setzen (Railway: Variables)

import os
import json
import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

# --------------------------- Konfiguration ---------------------------
INTENTS = discord.Intents.default()
INTENTS.members = True  # benötigt für on_member_join & Member-Infos

bot = commands.Bot(command_prefix="!", intents=INTENTS)

BLACKLIST_FILE = "blacklist.json"

# --------------------------- Blacklist-Storage ---------------------------

def load_blacklists() -> dict[int, set[int]]:
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    int(gid): {int(uid) for uid in uids}
                    for gid, uids in data.get("guilds", {}).items()
                }
        except Exception:
            pass
    return {}


def save_blacklists(blists: dict[int, set[int]]):
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            data = {gid: list(uids) for gid, uids in blists.items()}
            json.dump({"guilds": data}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


BLACKLISTS: dict[int, set[int]] = load_blacklists()

# --------------------------- Utils ---------------------------

DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([a-zA-ZäöüÄÖÜ]+)?\s*$", re.IGNORECASE)

UNIT_MAP = {
    "s": "seconds", "sek": "seconds", "sekunde": "seconds", "sekunden": "seconds",
    "m": "minutes", "min": "minutes", "minute": "minutes", "minuten": "minutes",
    "h": "hours", "std": "hours", "stunde": "hours", "stunden": "hours",
    "d": "days", "tag": "days", "tage": "days",
}


def parse_duration_to_timedelta(text: str) -> timedelta:
    if not text:
        raise ValueError("Bitte gib eine Dauer an, z.B. '30min' oder '1h'.")
    m = DURATION_PATTERN.match(text)
    if not m:
        raise ValueError("Ungültiges Format. Beispiel: '45s', '30min', '2h', '3tage'.")
    amount = int(m.group(1))
    unit = (m.group(2) or "s").lower()
    unit = UNIT_MAP.get(unit, None)
    if not unit:
        raise ValueError("Unbekannte Einheit. Erlaubt: s/sek, min, h/std, d/tage.")
    return timedelta(**{unit: amount})


async def ensure_guild_owner(inter: discord.Interaction):
    if not inter.guild:
        raise app_commands.AppCommandError("Dieser Command muss in einem Server genutzt werden.")
    if inter.user.id != inter.guild.owner_id:
        raise app_commands.AppCommandError("Nur der Server-Eigentümer darf diese Aktion ausführen.")


# --------------------------- Events ---------------------------

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"Eingeloggt als {bot.user} (ID: {bot.user.id}) – Slash-Commands synchronisiert.")
    except Exception as e:
        print("Fehler beim Sync:", e)


@bot.event
async def on_member_join(member: discord.Member):
    guild_id = member.guild.id
    if guild_id in BLACKLISTS and member.id in BLACKLISTS[guild_id]:
        try:
            await member.kick(reason="Automatischer Kick: Nutzer ist auf der Blacklist")
            print(f"Gekickt (Blacklist): {member} [{member.id}] in Guild {guild_id}")
        except Exception as e:
            print(f"Kick fehlgeschlagen für {member.id}: {e}")


# --------------------------- Slash-Commands ---------------------------

@bot.tree.command(name="timeout", description="Setzt einen Timeout für einen Nutzer (z.B. 30min, 2h, 3tage)")
@app_commands.describe(user="Zu timeoutender Nutzer", dauer="Dauer, z.B. 30min / 2h / 1tag")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_cmd(inter: discord.Interaction, user: discord.Member, dauer: str):
    try:
        delta = parse_duration_to_timedelta(dauer)
        await user.timeout(delta, reason=f"Timeout von {inter.user} per Slash-Command")
        await inter.response.send_message(f"⏱️ {user.mention} wurde für **{dauer}** in den Timeout gesetzt.", ephemeral=True)
    except ValueError as ve:
        await inter.response.send_message(f"❌ {ve}", ephemeral=True)
    except discord.Forbidden:
        await inter.response.send_message("❌ Keine Berechtigung, diesen Nutzer zu timeouten.", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="endtimeout", description="Beendet den Timeout eines Nutzers")
@app_commands.describe(user="Nutzer, dessen Timeout beendet werden soll")
@app_commands.checks.has_permissions(moderate_members=True)
async def endtimeout_cmd(inter: discord.Interaction, user: discord.Member):
    try:
        await user.timeout(None, reason=f"Timeout beendet von {inter.user}")
        await inter.response.send_message(f"✅ Timeout von {user.mention} wurde beendet.", ephemeral=True)
    except discord.Forbidden:
        await inter.response.send_message("❌ Keine Berechtigung, Timeout zu beenden.", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="ban", description="Bannt einen Nutzer")
@app_commands.describe(user="Zu bannender Nutzer", grund="(optional) Grund")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_cmd(inter: discord.Interaction, user: discord.Member, grund: str | None = None):
    try:
        await user.ban(reason=grund or f"Ban von {inter.user}")
        await inter.response.send_message(f"🔨 {user.mention} wurde gebannt.", ephemeral=True)
    except discord.Forbidden:
        await inter.response.send_message("❌ Keine Berechtigung, diesen Nutzer zu bannen.", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="endban", description="Entbannt einen Nutzer per Nutzer-ID")
@app_commands.describe(user_id="Discord Nutzer-ID des gebannten Nutzers")
@app_commands.checks.has_permissions(ban_members=True)
async def endban_cmd(inter: discord.Interaction, user_id: str):
    try:
        if not user_id.isdigit():
            await inter.response.send_message("❌ Bitte eine gültige numerische Nutzer-ID angeben.", ephemeral=True)
            return
        uid = int(user_id)
        bans = await inter.guild.bans(limit=None)
        target = next((entry.user for entry in bans if entry.user.id == uid), None)
        if not target:
            await inter.response.send_message("ℹ️ Nutzer-ID nicht in der Banliste gefunden.", ephemeral=True)
            return
        await inter.guild.unban(target, reason=f"Entbannt von {inter.user}")
        await inter.response.send_message(f"✅ Nutzer **{target}** ({uid}) wurde entbannt.", ephemeral=True)
    except discord.Forbidden:
        await inter.response.send_message("❌ Keine Berechtigung zum Entbannen.", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="kick", description="Kickt einen Nutzer")
@app_commands.describe(user="Zu kickender Nutzer", grund="(optional) Grund")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_cmd(inter: discord.Interaction, user: discord.Member, grund: str | None = None):
    try:
        await user.kick(reason=grund or f"Kick von {inter.user}")
        await inter.response.send_message(f"👢 {user.mention} wurde gekickt.", ephemeral=True)
    except discord.Forbidden:
        await inter.response.send_message("❌ Keine Berechtigung, diesen Nutzer zu kicken.", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="addblacklist", description="Fügt eine Nutzer-ID zur Blacklist dieses Servers hinzu (nur Eigentümer)")
@app_commands.describe(user_id="Discord Nutzer-ID")
async def addblacklist_cmd(inter: discord.Interaction, user_id: str):
    try:
        await ensure_guild_owner(inter)
        if not user_id.isdigit():
            await inter.response.send_message("❌ Bitte eine gültige numerische Nutzer-ID angeben.", ephemeral=True)
            return
        uid = int(user_id)
        gid = inter.guild.id
        if gid not in BLACKLISTS:
            BLACKLISTS[gid] = set()
        if uid in BLACKLISTS[gid]:
            await inter.response.send_message(f"ℹ️ ID {uid} ist bereits auf der Blacklist dieses Servers.", ephemeral=True)
            return
        BLACKLISTS[gid].add(uid)
        save_blacklists(BLACKLISTS)
        await inter.response.send_message(f"✅ ID **{uid}** zur Blacklist dieses Servers hinzugefügt.", ephemeral=True)
    except app_commands.AppCommandError as ace:
        await inter.response.send_message(f"❌ {ace}", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="removeblacklist", description="Entfernt eine Nutzer-ID von der Blacklist dieses Servers (nur Eigentümer)")
@app_commands.describe(user_id="Discord Nutzer-ID")
async def removeblacklist_cmd(inter: discord.Interaction, user_id: str):
    try:
        await ensure_guild_owner(inter)
        if not user_id.isdigit():
            await inter.response.send_message("❌ Bitte eine gültige numerische Nutzer-ID angeben.", ephemeral=True)
            return
        uid = int(user_id)
        gid = inter.guild.id
        if gid not in BLACKLISTS or uid not in BLACKLISTS[gid]:
            await inter.response.send_message(f"ℹ️ ID {uid} ist nicht auf der Blacklist dieses Servers.", ephemeral=True)
            return
        BLACKLISTS[gid].remove(uid)
        save_blacklists(BLACKLISTS)
        await inter.response.send_message(f"✅ ID **{uid}** von der Blacklist dieses Servers entfernt.", ephemeral=True)
    except app_commands.AppCommandError as ace:
        await inter.response.send_message(f"❌ {ace}", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


# --------------------------- Fehler-Handler ---------------------------

@timeout_cmd.error
@endtimeout_cmd.error
@ban_cmd.error
@endban_cmd.error
@kick_cmd.error
async def perms_error_handler(inter: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await inter.response.send_message(
            "❌ Dir fehlen die benötigten Rechte für diesen Command.", ephemeral=True
        )
    else:
        try:
            await inter.response.send_message(f"❌ Fehler: {error}", ephemeral=True)
        except discord.InteractionResponded:
            await inter.followup.send(f"❌ Fehler: {error}", ephemeral=True)


# --------------------------- Start ---------------------------

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Umgebungsvariable DISCORD_TOKEN ist nicht gesetzt.")
    bot.run(TOKEN)
