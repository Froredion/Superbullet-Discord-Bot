import discord
from discord.ext import commands, tasks
import asyncio, json, os, requests
from datetime import datetime

TOKEN = "Yessir"
GUILD_ID = 1427098932785446914 #change with 1145654983216332840
ROLE_ID = 1427128545649496126 #Create a new role (Buyer/Pro Version | or just anything like that)
VERIFY_CHANNEL_ID = 1427789754837242007 #Create a new channel and enter the id here 
LOG_CHANNEL_ID = 1427099016264683540 #Create a new channel and enter the id here
ERROR_CHANNEL_ID = 1427139755757535272 #Create a new channel and enter the id here
USER_LINKS_FILE = "user_links.json" 
BACKEND_URL = "https://superbullet-backend-3948693.superbulletstudios.com/discord_webhooks/check_subscription_of_user"

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

class VerifyModal(discord.ui.Modal, title="Email Verification"):
    email = discord.ui.TextInput(
        label="Enter your SuperBullet email",
        placeholder="example@gmail.com",
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        email_value = str(self.email.value).strip()
        user_links[str(interaction.user.id)] = email_value
        save_links(user_links)
        await interaction.response.send_message(
            f"✅ Your email **{email_value}** has been linked! "
            f"The bot will automatically verify your Pro subscription soon.",
            ephemeral=True
        )
        log_ch = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_ch:
            await log_ch.send(f"📩 {interaction.user.mention} linked email `{email_value}`")

class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal())

async def check_subscription(email: str):
    try:
        resp = requests.post(BACKEND_URL, json={"email": email}, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

@tasks.loop(hours=6)
async def auto_check():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    err_ch = guild.get_channel(ERROR_CHANNEL_ID)
    role = guild.get_role(ROLE_ID)

    checked = active = expired = errors = 0

    for discord_id, email in user_links.items():
        member = guild.get_member(int(discord_id))
        if not member:
            continue
        checked += 1
        data = await check_subscription(email)
        if "error" in data:
            errors += 1
            await err_ch.send(f"⚠️ Error checking {email}: `{data['error']}`")
            continue

        if data.get("isSubscribed"):
            if role not in member.roles:
                await member.add_roles(role)
                await log_ch.send(f"✅ {member.mention} ({email}) got **Pro** role.")
            active += 1
        else:
            if role in member.roles:
                await member.remove_roles(role)
                await log_ch.send(f"⚠️ {member.mention} ({email}) lost **Pro** role.")
            expired += 1

    now = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
    await log_ch.send(
        f"🔁 **Auto-check completed**\n"
        f"📅 {now}\n"
        f"Checked: **{checked}** | Active: **{active}** | Expired: **{expired}** | Errors: **{errors}**"
    )

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    verify_ch = bot.get_channel(VERIFY_CHANNEL_ID)
    if verify_ch:
        async for msg in verify_ch.history(limit=100):
            try:
                await msg.delete()
            except:
                pass

        embed = discord.Embed(
            title="🔒 Sync Your Account",
            description="To unlock **Pro features**, please verify your email below.\n\n"
                        "After verification, if your SuperBullet subscription is active, "
                        "you'll automatically get the **@Pro Version** role.",
            color=0x2ecc71
        )
        embed.set_footer(text="SuperBullet AI | Automated Role Sync")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/847/847969.png") #SupperBullets AI logo needs to be here

        await verify_ch.send(embed=embed, view=VerifyButton())

    auto_check.start()

bot.run(TOKEN)
