import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, request
from threading import Thread
import requests, asyncio
import os

TOKEN = os.getenv("TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GUILD_ID = 1145654983216332840
ROLE_ID = 1398986494450077777
PORT = 8080
SUBSCRIPTION_API = os.getenv("SUBSCRIPTION_API")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

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
        "redirect_uri": f"https://superbullet-discord-bot.fly.dev/discord/callback",
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
        print(f"✅ Gave Early Access role to {member}")
        return f"✅ {username} connected and received Early Access role!"
    else:
        asyncio.run_coroutine_threadsafe(member.remove_roles(role), bot.loop)
        print(f"❌ Removed Early Access role from {member}")
        return f"❌ {username} connected but has no active subscription."

@app.route("/assign-role", methods=["POST"])
def assign_role():
    """Endpoint for website backend to trigger role assignment when Discord ID is set"""
    # Validate request
    data = request.get_json()
    if not data:
        return {"success": False, "error": "Invalid request body"}, 400
    
    # Check secret key for security
    secret = request.headers.get("X-Webhook-Secret") or data.get("secret")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        print(f"⚠️ Unauthorized assign-role request")
        return {"success": False, "error": "Unauthorized"}, 401
    
    discord_id = data.get("discord_id")
    if not discord_id:
        return {"success": False, "error": "Missing discord_id"}, 400
    
    try:
        discord_id = int(discord_id)
    except ValueError:
        return {"success": False, "error": "Invalid discord_id format"}, 400
    
    print(f"🔗 Website triggered role check for Discord ID: {discord_id}")
    
    # Check subscription status
    try:
        resp = requests.post(
            SUBSCRIPTION_API,
            json={"discord_id": str(discord_id)},
            timeout=10
        )
        if resp.status_code == 200:
            subscription_data = resp.json()
            is_subscribed = subscription_data.get("isSubscribed", False)
        else:
            print(f"⚠️ Subscription check failed ({resp.status_code}) for {discord_id}")
            return {"success": False, "error": "Failed to check subscription"}, 500
    except Exception as e:
        print(f"⚠️ Error checking subscription: {e}")
        return {"success": False, "error": "Subscription service error"}, 500
    
    # Get guild, member, and role
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return {"success": False, "error": "Guild not found"}, 404
    
    member = guild.get_member(discord_id)
    if not member:
        return {"success": False, "error": "User not found in Discord server", "message": "User must join the Discord server first"}, 404
    
    role = guild.get_role(ROLE_ID)
    if not role:
        return {"success": False, "error": "Role not found"}, 404
    
    # Assign or remove role based on subscription
    if is_subscribed:
        if role not in member.roles:
            asyncio.run_coroutine_threadsafe(member.add_roles(role), bot.loop)
            print(f"✅ Gave Early Access role to {member} via webhook")
            return {"success": True, "message": "Role assigned", "username": str(member)}, 200
        else:
            print(f"✓ {member} already has Early Access role")
            return {"success": True, "message": "User already has role", "username": str(member)}, 200
    else:
        if role in member.roles:
            asyncio.run_coroutine_threadsafe(member.remove_roles(role), bot.loop)
            print(f"❌ Removed Early Access role from {member} via webhook")
        return {"success": False, "error": "No active subscription", "message": "User does not have an active subscription"}, 403

def run_web():
    app.run(host="0.0.0.0", port=PORT)

Thread(target=run_web).start()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"🌐 OAuth2 callback: https://superbullet-discord-bot.fly.dev/discord/callback")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"🔄 Synced {len(synced)} command(s) to guild {GUILD_ID}")
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")

@bot.tree.command(name="checksubscription", description="Check your Superbullet subscription status", guild=discord.Object(id=GUILD_ID))
async def checksubscription(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        print(f"🔍 {interaction.user.name} ran /checksubscription")
        
        discord_id = interaction.user.id
        username = interaction.user.name
        
        # Check subscription status
        print(f"📡 Checking subscription for {discord_id}...")
        try:
            resp = requests.post(
                SUBSCRIPTION_API,
                json={"discord_id": str(discord_id)},
                timeout=10
            )
            print(f"📡 API response: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                is_subscribed = data.get("isSubscribed", False)
                print(f"✓ Subscription status: {is_subscribed}")
            else:
                await interaction.followup.send(
                    f"⚠️ Unable to check subscription status (error {resp.status_code}). Please try again later.",
                    ephemeral=True
                )
                return
        except requests.exceptions.Timeout:
            print(f"⚠️ Subscription API timeout for {discord_id}")
            await interaction.followup.send(
                f"⚠️ Connection timeout. Please try again later.",
                ephemeral=True
            )
            return
        except Exception as e:
            print(f"⚠️ Error checking subscription: {e}")
            await interaction.followup.send(
                f"⚠️ Error connecting to subscription service. Please try again later.",
                ephemeral=True
            )
            return
        
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("⚠️ This command must be used in a server.", ephemeral=True)
            return
        
        role = guild.get_role(ROLE_ID)
        if not role:
            await interaction.followup.send("⚠️ Early Access role not found. Please contact an admin.", ephemeral=True)
            return
        
        member = guild.get_member(discord_id)
        if not member:
            await interaction.followup.send("⚠️ Could not find your member info.", ephemeral=True)
            return
        
        if is_subscribed:
            if role not in member.roles:
                await member.add_roles(role)
                print(f"✅ Gave Early Access role to {member} via /checksubscription")
                await interaction.followup.send(
                    f"✅ **You have an active subscription!**\n\n"
                    f"You've been given the Early Access role.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ **You have an active subscription!**\n\n"
                    f"You already have the Early Access role.",
                    ephemeral=True
                )
        else:
            if role in member.roles:
                await member.remove_roles(role)
                print(f"❌ Removed Early Access role from {member} via /checksubscription")
            
            await interaction.followup.send(
                f"❌ **No active subscription found.**\n\n"
                f"**Your Discord User ID:** `{discord_id}`\n\n"
                f"Please copy your Discord ID and set it in your Superbullet dashboard:\n"
                f"🔗 https://ai.superbulletstudios.com/dashboard",
                ephemeral=True
            )
    except Exception as e:
        print(f"❌ Unexpected error in /checksubscription: {e}")
        try:
            await interaction.followup.send(
                f"⚠️ An unexpected error occurred. Please try again.",
                ephemeral=True
            )
        except:
            pass

bot.run(TOKEN)
