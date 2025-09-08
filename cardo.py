import os
import json
import re
from datetime import timedelta

import discord
from discord.ext import commands

# --------------------------- Konfiguration ---------------------------
INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True 

bot = commands.Bot(command_prefix="$", intents=INTENTS)

BLACKLIST_FILE = "blacklist.json"
TRUST_FILE = "trust.json"

# --------------------------- Blacklist-Storage ---------------------------

def load_blacklists() -> dict[int, set[int]]:
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(gid): {int(uid) for uid in uids} for gid, uids in data.get("guilds", {}).items()}
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

# --------------------------- Trust-Storage ---------------------------

def load_trusts() -> dict[int, set[int]]:
    if os.path.exists(TRUST_FILE):
        try:
            with open(TRUST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(gid): {int(uid) for uid in uids} for gid, uids in data.get("guilds", {}).items()}
        except Exception:
            pass
    return {}

def save_trusts(trusts: dict[int, set[int]]):
    try:
        with open(TRUST_FILE, "w", encoding="utf-8") as f:
            data = {gid: list(uids) for gid, uids in trusts.items()}
            json.dump({"guilds": data}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

TRUSTS: dict[int, set[int]] = load_trusts()

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

async def ensure_owner_or_trusted(ctx: commands.Context):
    """Prüfen ob User Guild Owner oder Trusted ist"""
    if not ctx.guild:
        raise commands.CheckFailure("Dieser Command muss in einem Server genutzt werden.")
    if ctx.author.id == ctx.guild.owner_id:
        return
    if ctx.guild.id in TRUSTS and ctx.author.id in TRUSTS[ctx.guild.id]:
        return
    raise commands.CheckFailure("Nur der Server-Eigentümer oder vertrauenswürdige Nutzer dürfen diese Aktion ausführen.")

# --------------------------- Events ---------------------------

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user} (ID: {bot.user.id}) – Prefix-Commands aktiv.")

@bot.event
async def on_member_join(member: discord.Member):
    guild_id = member.guild.id
    if guild_id in BLACKLISTS and member.id in BLACKLISTS[guild_id]:
        try:
            await member.kick(reason="Automatischer Kick: Nutzer ist auf der Blacklist")
            print(f"Gekickt (Blacklist): {member} [{member.id}] in Guild {guild_id}")
        except Exception as e:
            print(f"Kick fehlgeschlagen für {member.id}: {e}")

# --------------------------- Moderation Commands ---------------------------

@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_cmd(ctx: commands.Context, member: discord.Member, dauer: str):
    try:
        delta = parse_duration_to_timedelta(dauer)
        await member.timeout(delta, reason=f"Timeout von {ctx.author}")
        await ctx.send(f"⏱️ {member.mention} wurde für **{dauer}** in den Timeout gesetzt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="endtimeout")
@commands.has_permissions(moderate_members=True)
async def endtimeout_cmd(ctx: commands.Context, member: discord.Member):
    try:
        await member.timeout(None, reason=f"Timeout beendet von {ctx.author}")
        await ctx.send(f"✅ Timeout von {member.mention} wurde beendet.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_cmd(ctx: commands.Context, member: discord.Member, *, grund: str = None):
    try:
        await member.ban(reason=grund or f"Ban von {ctx.author}")
        await ctx.send(f"🔨 {member.mention} wurde gebannt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="endban")
@commands.has_permissions(ban_members=True)
async def endban_cmd(ctx: commands.Context, user_id: int):
    try:
        bans = await ctx.guild.bans()
        target = next((entry.user for entry in bans if entry.user.id == user_id), None)
        if not target:
            await ctx.send("ℹ️ Nutzer-ID nicht in der Banliste gefunden.")
            return
        await ctx.guild.unban(target, reason=f"Entbannt von {ctx.author}")
        await ctx.send(f"✅ Nutzer **{target}** ({user_id}) wurde entbannt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_cmd(ctx: commands.Context, member: discord.Member, *, grund: str = None):
    try:
        await member.kick(reason=grund or f"Kick von {ctx.author}")
        await ctx.send(f"👢 {member.mention} wurde gekickt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

# --------------------------- Rollen Commands ---------------------------

def normalize_role_name(name: str) -> str:
    """Entfernt Sonderzeichen und macht alles lowercase"""
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

def find_role_exact(guild: discord.Guild, role_name: str):
    """Sucht die Rolle exakt nach Buchstaben/Zahlen (Sonderzeichen ignoriert)"""
    norm_input = normalize_role_name(role_name)
    for role in guild.roles:
        if normalize_role_name(role.name) == norm_input:
            return role
    return None

@bot.command(name="addrole")
@commands.has_permissions(manage_roles=True)
async def addrole_cmd(ctx: commands.Context, member: discord.Member, *, role_name: str):
    try:
        role = find_role_exact(ctx.guild, role_name)
        if not role:
            await ctx.send(f"❌ Keine Rolle gefunden, die **{role_name}** entspricht.")
            return
        await member.add_roles(role, reason=f"Rolle hinzugefügt von {ctx.author}")
        await ctx.send(f"✅ {member.mention} hat die Rolle **{role.name}** erhalten.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="stealrole")
@commands.has_permissions(manage_roles=True)
async def stealrole_cmd(ctx: commands.Context, member: discord.Member, *, role_name: str):
    try:
        role = find_role_exact(ctx.guild, role_name)
        if not role:
            await ctx.send(f"❌ Keine Rolle gefunden, die **{role_name}** entspricht.")
            return
        if role not in member.roles:
            await ctx.send(f"ℹ️ {member.mention} hat die Rolle **{role.name}** nicht.")
            return
        await member.remove_roles(role, reason=f"Rolle entfernt von {ctx.author}")
        await ctx.send(f"✅ {member.mention} wurde die Rolle **{role.name}** entfernt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

# --------------------------- Blacklist + Trust Commands ---------------------------

@bot.command(name="addblacklist")
async def addblacklist_cmd(ctx: commands.Context, user_id: int):
    try:
        await ensure_owner_or_trusted(ctx)
        gid = ctx.guild.id
        if gid not in BLACKLISTS:
            BLACKLISTS[gid] = set()
        if user_id in BLACKLISTS[gid]:
            await ctx.send(f"ℹ️ ID {user_id} ist bereits auf der Blacklist.")
            return
        BLACKLISTS[gid].add(user_id)
        save_blacklists(BLACKLISTS)
        await ctx.send(f"✅ ID **{user_id}** zur Blacklist hinzugefügt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="removeblacklist")
async def removeblacklist_cmd(ctx: commands.Context, user_id: int):
    try:
        await ensure_owner_or_trusted(ctx)
        gid = ctx.guild.id
        if gid not in BLACKLISTS or user_id not in BLACKLISTS[gid]:
            await ctx.send(f"ℹ️ ID {user_id} ist nicht auf der Blacklist.")
            return
        BLACKLISTS[gid].remove(user_id)
        save_blacklists(BLACKLISTS)
        await ctx.send(f"✅ ID **{user_id}** von der Blacklist entfernt.")
    except Exception as e:
        await ctx.send(f"❌ Fehler: {e}")

@bot.command(name="blacklisttrust")
async def blacklisttrust_cmd(ctx: commands.Context, user_id: int):
    if ctx.author.id != ctx.guild.owner_id:
        await ctx.send("❌ Nur der Server-Eigentümer darf Trusted-User hinzufügen.")
        return
    gid = ctx.guild.id
    if gid not in TRUSTS:
        TRUSTS[gid] = set()
    TRUSTS[gid].add(user_id)
    save_trusts(TRUSTS)
    await ctx.send(f"✅ ID **{user_id}** wurde als Trusted für Blacklist hinzugefügt.")

@bot.command(name="removeblacklisttrust")
async def removeblacklisttrust_cmd(ctx: commands.Context, user_id: int):
    if ctx.author.id != ctx.guild.owner_id:
        await ctx.send("❌ Nur der Server-Eigentümer darf Trusted-User entfernen.")
        return
    gid = ctx.guild.id
    if gid in TRUSTS and user_id in TRUSTS[gid]:
        TRUSTS[gid].remove(user_id)
        save_trusts(TRUSTS)
        await ctx.send(f"✅ ID **{user_id}** wurde aus den Trusted-Usern entfernt.")
    else:
        await ctx.send(f"ℹ️ ID {user_id} ist kein Trusted-User.")

# --------------------------- Start ---------------------------

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Umgebungsvariable DISCORD_TOKEN ist nicht gesetzt.")
    bot.run(TOKEN)
