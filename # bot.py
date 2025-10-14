import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio, json, os, requests
from datetime import datetime

TOKEN = "Check DM for the token =)"
GUILD_ID = 1427098932785446914 #needs to be replaced with 1145654983216332840 (SuperBullet AI discord server id)
ROLE_ID = 1427128545649496126 #the @Pro Version role id
LOG_CHANNEL_ID = 1427099016264683540 #need to make a new channel
ERROR_CHANNEL_ID = 1427139755757535272 #need to make a new channel
USER_LINKS_FILE = "user_links.json"
LOG_FILE = "purchases.json"

BACKEND_URL = "https://superbullet-backend-3948693.superbulletstudios.com/discord_webhooks/check_subscription_of_user"

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

def load_links():
    if os.path.exists(USER_LINKS_FILE):
        try:
            with open(USER_LINKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_links(data):
    with open(USER_LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

user_links = load_links()

def log_action(member_id, email, status):
    entry = {
        "discord_id": member_id,
        "email": email,
        "status": status,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    data.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def check_subscription(email: str):
    try:
        resp = requests.post(BACKEND_URL, json={"email": email}, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

async def handle_user(member: discord.Member, email: str, data: dict):
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID)
    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    err_ch = guild.get_channel(ERROR_CHANNEL_ID)

    if "error" in data:
        await err_ch.send(f"⚠️ Error checking {member.mention} ({email}): `{data['error']}`")
        return "error"

    subscribed = data.get("isSubscribed", False)
    if subscribed:
        if role not in member.roles:
            await member.add_roles(role)
            await log_ch.send(f"✅ {member.mention} ({email}) got **Pro** role.")
        log_action(member.id, email, "active")
        return "active"
    else:
        if role in member.roles:
            await member.remove_roles(role)
            await log_ch.send(f"⚠️ {member.mention} ({email}) lost **Pro** role.")
        log_action(member.id, email, "expired")
        return "expired"

@tasks.loop(hours=6)
async def auto_check():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    err_ch = guild.get_channel(ERROR_CHANNEL_ID)

    checked = active = expired = errors = 0

    for discord_id, email in user_links.items():
        member = guild.get_member(int(discord_id))
        if not member:
            continue
        checked += 1
        data = await check_subscription(email)
        result = await handle_user(member, email, data)
        if result == "active":
            active += 1
        elif result == "expired":
            expired += 1
        elif result == "error":
            errors += 1

    now = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
    await log_ch.send(
        f"✅ **Auto-check completed**\n"
        f"📅 Time: **{now}**\n"
        f"Checked: **{checked}** | Active: **{active}** | Expired: **{expired}** | Errors: **{errors}**"
    )

@tree.command(name="link", description="Link your SuperBullet email to your Discord account")
async def link(interaction: discord.Interaction, email: str):
    user_links[str(interaction.user.id)] = email
    save_links(user_links)
    await interaction.response.send_message(f"✅ Your email `{email}` has been linked!", ephemeral=True)

@tree.command(name="status", description="Show how many users are linked and when the next check is")
async def status(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"📊 Currently **{len(user_links)}** users are linked.\n"
        "🔁 Auto-check runs every 6 hours.",
        ephemeral=True
    )

@tree.command(name="procount", description="Show number of users with Pro role")
async def procount(interaction: discord.Interaction):
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID)
    await interaction.response.send_message(
        f"💎 There are currently **{len(role.members)}** users with the **Pro** role.",
        ephemeral=True
    )

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user}")
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send("Bot restarted and ready.\nNext auto-check in 6 hours.")
    auto_check.start()

bot.run(TOKEN)

