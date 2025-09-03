# bot.py
# Discord Moderations-Bot mit Slash-Commands (timeout/endtimeout/ban/endban/kick)
# + Blacklist (nur Server-Eigentümer darf verwalten)
#
# Voraussetzungen:
#   - Python 3.10+
#   - pip install -r requirements.txt
#   - Umgebungsvariable DISCORD_TOKEN setzen (Railway: Variables)
#
# Hinweise:
#   - Blacklist wird in blacklist.json gespeichert. Für persistente Speicherung auf Railway
#     kannst du stattdessen eine Railway-Variable BLACKLIST_IDS verwenden (Komma-getrennt).
#   - Die Slash-Commands sind per Permission abgesichert und erscheinen nur für berechtigte Nutzer.

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

def load_blacklist() -> set[int]:
    # 1) Aus Datei lesen, falls vorhanden
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(x) for x in data.get("blacklist", [])}
        except Exception:
            pass
    # 2) Fallback: Railway Variable (Komma-getrennte IDs)
    env_val = os.getenv("BLACKLIST_IDS", "").strip()
    if env_val:
        try:
            return {int(x) for x in env_val.split(",") if x.strip().isdigit()}
        except Exception:
            return set()
    return set()


def save_blacklist(bl_ids: set[int]):
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump({"blacklist": list(bl_ids)}, f, indent=2, ensure_ascii=False)
    except Exception:
        # Wenn Filesystem read-only o.ä., ignorieren (Railway-Variable weiterhin nutzbar)
        pass


BLACKLIST_IDS = load_blacklist()

# --------------------------- Utils ---------------------------

DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([a-zA-ZäöüÄÖÜ]+)?\s*$", re.IGNORECASE)

UNIT_MAP = {
    # Sekunden
    "s": "seconds", "sek": "seconds", "sekunde": "seconds", "sekunden": "seconds",
    # Minuten
    "m": "minutes", "min": "minutes", "minute": "minutes", "minuten": "minutes",
    # Stunden
    "h": "hours", "std": "hours", "stunde": "hours", "stunden": "hours",
    # Tage
    "d": "days", "tag": "days", "tage": "days",
}


def parse_duration_to_timedelta(text: str) -> timedelta:
    """Parst z.B. "1sek", "15 m", "2h", "3 tage" in timedelta."""
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
    # Auto-Kick, wenn auf Blacklist
    if member.id in BLACKLIST_IDS:
        try:
            await member.kick(reason="Automatischer Kick: Nutzer ist auf der Blacklist")
            print(f"Gekickt (Blacklist): {member} [{member.id}]")
        except Exception as e:
            print(f"Kick fehlgeschlagen für {member.id}: {e}")


# --------------------------- Slash-Commands ---------------------------

# /timeout – benötigt Recht: moderate_members (Timeout Mitglieder)
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


# /endtimeout – benötigt Recht: moderate_members
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


# /ban – benötigt Recht: ban_members
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


# /endban – benötigt Recht: ban_members
@bot.tree.command(name="endban", description="Entbannt einen Nutzer per Nutzer-ID")
@app_commands.describe(user_id="Discord Nutzer-ID des gebannten Nutzers")
@app_commands.checks.has_permissions(ban_members=True)
async def endban_cmd(inter: discord.Interaction, user_id: str):
    try:
        if not user_id.isdigit():
            await inter.response.send_message("❌ Bitte eine gültige numerische Nutzer-ID angeben.", ephemeral=True)
            return
        uid = int(user_id)
        # In Banliste suchen und entbannen
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


# /kick – benötigt Recht: kick_members
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


# /addblacklist – nur Server-Eigentümer
@bot.tree.command(name="addblacklist", description="Fügt eine Nutzer-ID zur Blacklist hinzu (nur Eigentümer)")
@app_commands.describe(user_id="Discord Nutzer-ID")
async def addblacklist_cmd(inter: discord.Interaction, user_id: str):
    try:
        await ensure_guild_owner(inter)
        if not user_id.isdigit():
            await inter.response.send_message("❌ Bitte eine gültige numerische Nutzer-ID angeben.", ephemeral=True)
            return
        uid = int(user_id)
        if uid in BLACKLIST_IDS:
            await inter.response.send_message(f"ℹ️ ID {uid} ist bereits auf der Blacklist.", ephemeral=True)
            return
        BLACKLIST_IDS.add(uid)
        save_blacklist(BLACKLIST_IDS)
        await inter.response.send_message(f"✅ ID **{uid}** zur Blacklist hinzugefügt. Nutzer wird beim Join automatisch gekickt.", ephemeral=True)
    except app_commands.AppCommandError as ace:
        await inter.response.send_message(f"❌ {ace}", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


# /removeblacklist – nur Server-Eigentümer
@bot.tree.command(name="removeblacklist", description="Entfernt eine Nutzer-ID von der Blacklist (nur Eigentümer)")
@app_commands.describe(user_id="Discord Nutzer-ID")
async def removeblacklist_cmd(inter: discord.Interaction, user_id: str):
    try:
        await ensure_guild_owner(inter)
        if not user_id.isdigit():
            await inter.response.send_message("❌ Bitte eine gültige numerische Nutzer-ID angeben.", ephemeral=True)
            return
        uid = int(user_id)
        if uid not in BLACKLIST_IDS:
            await inter.response.send_message(f"ℹ️ ID {uid} ist nicht auf der Blacklist.", ephemeral=True)
            return
        BLACKLIST_IDS.remove(uid)
        save_blacklist(BLACKLIST_IDS)
        await inter.response.send_message(f"✅ ID **{uid}** von der Blacklist entfernt.", ephemeral=True)
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

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Umgebungsvariable DISCORD_TOKEN ist nicht gesetzt.")
    bot.run(token)


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Umgebungsvariable DISCORD_TOKEN ist nicht gesetzt.")
    bot.run(TOKEN)
