import discord
from discord.ext import commands
from flask import Flask, request
from threading import Thread
import requests, asyncio
import os

TOKEN = os.getenv("TOKEN")
CLIENT_ID = "1427787647597809864"
CLIENT_SECRET = "Xuu9Gr3AcPQYTDijyA2P0QRUtJCnzJj1"
GUILD_ID = 123456789012345678
ROLE_ID = 1427128545649496126
PORT = 8080
SUBSCRIPTION_API = "https://superbullet.ai/discord_webhooks/check_subscription_of_user"

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is online!"

@app.route("/discord/callback")
def discord_callback():
    code = request.args.get("code")
    if not code:
        return "Missing ?code parameter", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"https://asd-dry-violet-6447.fly.dev/discord/callback",
        "scope": "identify"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_resp = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    if token_resp.status_code != 200:
        return f"Token exchange failed: {token_resp.text}", 400

    access_token = token_resp.json().get("access_token")
    if not access_token:
        return "No access token returned", 400

    user_resp = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if user_resp.status_code != 200:
        return f"Failed to fetch user info: {user_resp.text}", 400

    user = user_resp.json()
    discord_id = int(user["id"])
    username = user["username"]
    print(f"🔗 {username} connected ({discord_id})")

    try:
        resp = requests.post(
            SUBSCRIPTION_API,
            json={"discord_id": str(discord_id)},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            is_subscribed = data.get("isSubscribed", False)
        else:
            print(f"⚠️ Subscription check failed ({resp.status_code}) for {discord_id}")
            is_subscribed = False
    except Exception as e:
        print(f"⚠️ Error checking subscription: {e}")
        is_subscribed = False

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return "Guild not found", 404

    member = guild.get_member(discord_id)
    if not member:
        return f"User {username} not found on the Discord server.", 404

    role = guild.get_role(ROLE_ID)
    if not role:
        return "Role not found", 404

    if is_subscribed:
        asyncio.run_coroutine_threadsafe(member.add_roles(role), bot.loop)
        print(f"✅ Gave Pro role to {member}")
        return f"✅ {username} connected and received Pro role!"
    else:
        asyncio.run_coroutine_threadsafe(member.remove_roles(role), bot.loop)
        print(f"❌ Removed Pro role from {member}")
        return f"❌ {username} connected but has no active subscription."

def run_web():
    app.run(host="0.0.0.0", port=PORT)

Thread(target=run_web).start()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"🌐 OAuth2 callback: https://asd-dry-violet-6447.fly.dev/discord/callback")

bot.run(TOKEN)
