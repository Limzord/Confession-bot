import discord
from discord import app_commands
from discord.ext import commands
import os, random
from random import randrange
import json
import re
from pathlib import Path

intents = discord.Intents().all()
intents.members = True

bot = commands.Bot(command_prefix = '/', intents = intents)

default_settings = {
    "confession_channel" : 0,
    "log_channel" : 0,
    "moderator_role" : 0,
    "confession_amount" : 0,
    "banned_user_ids" : [],
    "message_log" : [
        {
            "number" : 0,
            "user_id" : 842473705145106492,
            "message" : "thanks for using my bot :)"
        }
    ]
}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    # await bot.tree.sync(guild=None)
    for server in bot.guilds:
        bot.tree.copy_global_to(guild=server)
        await bot.tree.sync(guild=server)
    print("ready and willing to freak")
    print('------')

@bot.event
async def on_guild_join():
    for server in bot.guilds:
        bot.tree.copy_global_to(guild=server)
        await bot.tree.sync(guild=server)
    print("added slash commands to new server\n server list:\n" + bot.guilds)

@bot.tree.command(name='akb')
async def akb(ctx: discord.Interaction):
    """get a silly picture"""
    await ctx.response.send_message(file=discord.File('./pictures/' + random.choice(os.listdir("./pictures"))))

@bot.tree.command()
@app_commands.describe(message='your confession',
image="an image to post with your confession")
async def confess(ctx: discord.Interaction,
message: str,
image: discord.Attachment=None):
    """write an anonymous confession"""
    if is_banned(ctx.guild.id,ctx.user.id):
        await ctx.response.send_message(content="Whoopsie, you did a stinky, beg the mods for forgiveness :3",ephemeral=True)
        return
    channel = await get_confession_channel(ctx.guild)
    if channel == 0:
        await ctx.response.send_message(content="The mods forgot to set a confession channel. Please annoy them about this :3",ephemeral=True)
        return
    sidebarColor= discord.Color.from_rgb(randrange(255), randrange(255), randrange(255))
    confession_number = get_server_settings(ctx.guild.id)["confession_amount"] + 1
    embedVar = discord.Embed(
    title="💗 Silly Confession #" + (str)(confession_number), description=message, color=sidebarColor
            )
    if image:
        imgURL = image.url
        embedVar.set_image(url=imgURL)
    # if ctx.reference:
    #     channel = ctx.reference.channel
    #     await channel.send(embed=embedVar, reference=ctx.reference)
    await channel.send(embed=embedVar)
    await ctx.response.send_message(content="Your confession has been posted 🤫",ephemeral=True)
    await send_message_to_log(ctx,message,confession_number,imgURL)

async def send_message_to_log(ctx: discord.Interaction, message: str, confession_number: int, imgURL: str):
    user = ctx.user
    embedVar = discord.Embed(
    title="💗 Silly Confession #" + (str)(confession_number), description=message
            )
    embedVar.add_field(name="User", value="||" + user.mention + "||", inline=True)
    if imgURL:
        embedVar.set_image(url=imgURL)
    channel = await get_log_channel(ctx.guild)
    if not channel == 0:
        await channel.send(embed=embedVar)
    add_message_to_log(confession_number,user.id,message, ctx.guild.id, imgURL)

def add_message_to_log(number: int, user_id: int, message: str, guild_id: int, imgURL: str):
    server_settings = get_server_settings(guild_id)
    if imgURL:
        server_settings["message_log"].append({"number": number, "user_id": user_id, "message": message, "imgURL": imgURL})
    else:
        server_settings["message_log"].append({"number": number, "user_id": user_id, "message": message})
    server_settings["confession_amount"] += 1
    write_server_settings(guild_id,server_settings)

@bot.tree.command(name='get-confession')
@app_commands.describe(number='the number of the confession')
async def get_confession(ctx: discord.Interaction,
number: int):
    """see the content of a confession from its number"""
    sidebarColor= discord.Color.from_rgb(randrange(255), randrange(255), randrange(255))
    confessions = get_server_settings(ctx.guild.id)["message_log"]
    confession = next((item for item in confessions if item['number'] == number), None)
    if confession == None:
        await ctx.response.send_message(content="This confession does not exist",ephemeral=True)
        return
    embedVar = discord.Embed(
    title="💗 Silly Confession #" + (str)(number), description=confession["message"], color=sidebarColor)
    if confession["user_id"] == ctx.user.id or await is_moderator(guild=ctx.guild,user=ctx.user):
        user = await bot.fetch_user(confession["user_id"])
        embedVar.add_field(name="User", value="||" + user.mention + "||", inline=True)
    if "imgURL" in confession:
        embedVar.set_image(url=confession["imgURL"])
    await ctx.response.send_message(embed=embedVar,ephemeral=True)

@bot.command(pass_context=True,name='set-confession-channel')
async def set_confession_channel(ctx: discord.Interaction):
    if not await is_moderator(guild=ctx.guild,user=ctx.message.author):
        await ctx.channel.send("Only moderators are allowed to use this command")
    else:
        channel_id = ctx.message.content.replace("/set-confession-channel ", "").replace(" ", "")
        r = re.compile('<#.*>')
        if r.match(channel_id) is None:
            await ctx.channel.send("Your message needs to be formatted like /set-confession-channel #<channel>")
        else:
            channel_id = channel_id.replace("<#","").replace(">","")
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
                json_set_confession_channel(ctx.guild.id,channel_id)
                await ctx.channel.send("the confession channel was set to " + channel.mention)
            except:
                await ctx.channel.send("the channel was not found (incorrect formatting?)")

@bot.command(pass_context=True,name='set-log-channel')
async def set_log_channel(ctx: discord.Interaction):
    if not await is_moderator(guild=ctx.guild,user=ctx.message.author):
        await ctx.channel.send("Only moderators are allowed to use this command")
    else:
        channel_id = ctx.message.content.replace("/set-log-channel ", "").replace(" ", "")
        r = re.compile('<#.*>')
        if r.match(channel_id) is None:
            await ctx.channel.send("Your message needs to be formatted like /set-log-channel #<channel>")
        else:
            channel_id = channel_id.replace("<#","").replace(">","")
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
                json_set_log_channel(ctx.guild.id,channel_id)
                await ctx.channel.send("the log channel was set to " + channel.mention)
            except:
                await ctx.channel.send("the channel was not found (incorrect formatting?)")

@bot.command(pass_context=True,name='set-moderator-role')
async def set_moderator_role(ctx: discord.Interaction):
    if not await is_moderator(guild=ctx.guild,user=ctx.message.author):
        await ctx.channel.send("Only moderators are allowed to use this command")
    else:
        role_id = ctx.message.content.replace("/set-moderator-role ", "").replace(" ", "")
        try:
            role = await ctx.guild.fetch_role(role_id)
            json_set_moderator_role(ctx.guild.id,role_id)
            await ctx.channel.send("the moderator role was set to " + role.mention)
        except:
            await ctx.channel.send("Your message needs to be formatted like /set-moderator-role <role-id>")

async def is_moderator(guild: discord.Guild, user: discord.User):
    if is_admin(user):
        return True
    moderator_role = await get_moderator_role(guild)
    if moderator_role in user.roles:
        return True
    return False

def is_admin(user: discord.User):
    if user.guild_permissions.administrator:
        return True
    return False

async def get_moderator_role(guild: discord.Guild):
    server_settings = get_server_settings(guild.id)
    role_id = server_settings["moderator_role"]
    try:
        return await guild.fetch_role(role_id)
    except:
        return 0

async def get_confession_channel(guild: discord.Guild):
    server_settings = get_server_settings(guild.id)
    channel_id = server_settings["confession_channel"]
    try:
        return await guild.fetch_channel(channel_id)
    except:
        return 0

async def get_log_channel(guild: discord.Guild):
    server_settings = get_server_settings(guild.id)
    channel_id = server_settings["log_channel"]
    try:
        return await guild.fetch_channel(channel_id)
    except:
        return 0

def get_server_settings(guild_id: int):
    if Path((str)(guild_id) + '.json').exists():
        with open((str)(guild_id) + '.json', 'r') as file:
            return json.load(file)
    create_server_settings(guild_id)
    return get_server_settings(guild_id)

def create_server_settings(guild_id: int):
    json_str = json.dumps(default_settings, indent=4)
    with open((str)(guild_id) + '.json', 'w') as file:
        file.write(json_str)

def write_server_settings(guild_id: int, settings: dict):
    json_str = json.dumps(settings, indent=4)
    with open((str)(guild_id) + '.json', 'w') as file:
        file.write(json_str)


def json_set_confession_channel(guild_id: int,channel_id: int):
    server_settings = get_server_settings(guild_id)
    server_settings["confession_channel"] = channel_id
    write_server_settings(guild_id,server_settings)

def json_set_log_channel(guild_id: int,channel_id: int):
    server_settings = get_server_settings(guild_id)
    server_settings["log_channel"] = channel_id
    write_server_settings(guild_id,server_settings)

def json_set_moderator_role(guild_id: int,role_id: int):
    server_settings = get_server_settings(guild_id)
    server_settings["moderator_role"] = role_id
    write_server_settings(guild_id,server_settings)

@bot.tree.command(name='ban')
@app_commands.describe(user='the user to be banned')
async def ban_from_confessions(ctx: discord.Interaction,
user: discord.User):
    """ban someone from writing confessions"""
    if await is_moderator(ctx.guild,ctx.user):
        if is_banned(ctx.guild.id,user.id):
            await ctx.response.send_message(content="This user is already banned",ephemeral=True)
            return
        json_ban_user(ctx.guild.id,user.id)
        await ctx.response.send_message(content="Banned " + user.mention + " from writing confessions",ephemeral=True)
        return
    await ctx.response.send_message(content="Only moderators are allowed to use this command",ephemeral=True)

@bot.tree.command(name='unban')
@app_commands.describe(user='the user to be unbanned')
async def unban_from_confessions(ctx: discord.Interaction,
user: discord.User):
    """unban someone from writing confessions"""
    if await is_moderator(ctx.guild,ctx.user):
        if not is_banned(ctx.guild.id,user.id):
            await ctx.response.send_message(content="This user is not banned",ephemeral=True)
            return
        json_unban_user(ctx.guild.id,user.id)
        await ctx.response.send_message(content="Unbanned " + user.mention + " from writing confessions",ephemeral=True)
        return
    await ctx.response.send_message(content="Only moderators are allowed to use this command",ephemeral=True)

def is_banned(guild_id : int, user_id : int):
    server_settings = get_server_settings(guild_id)
    if user_id in server_settings["banned_user_ids"]:
        return True
    return False

def json_ban_user(guild_id : int, user_id : int):
    server_settings = get_server_settings(guild_id)
    server_settings["banned_user_ids"].append(user_id)
    write_server_settings(guild_id,server_settings)

def json_unban_user(guild_id : int, user_id : int):
    server_settings = get_server_settings(guild_id)
    server_settings["banned_user_ids"].remove(user_id)
    write_server_settings(guild_id,server_settings)


@bot.tree.command(name='help')
async def help(ctx: discord.Interaction):
    """learn how to use the bot"""
    embedVar = discord.Embed(
        title="💗 How to use the bot 💗",
        description="Here is a list of all commands and what they do :D"
            )
    embedVar.add_field(
        name="/confess",
        value="Write an anonymous confession", inline=True)
    embedVar.add_field(
        name="/akb",
        value="Get a random picture of AKB48!!", inline=True)
    if await is_moderator(ctx.guild,ctx.user):
        embedVar.add_field(
            name="/get-confession",
            value="See a confession by its number (moderators can see who wrote it)", inline=True)
        embedVar.add_field(
            name="/ban",
            value="Ban someone from confessing", inline=True)
        embedVar.add_field(
            name="/unban",
            value="Unban someone who was previously banned from confessing", inline=True)
        embedVar.add_field(
            name="Bot Setup",
            value="These settings should be set before the bot is used", inline=True)
        embedVar.add_field(
            name="/set-confession-channel",
            value="Set the channel anonymous confessions get sent into (⚠️REQUIRED⚠️)", inline=True)
        embedVar.add_field(
            name="/set-log-channel",
            value="Set the channel confession logs get sent into (this setting is optional and ⚠️SHOWS WHO WROTE CONFESSIONS⚠️)", inline=True)
        embedVar.add_field(
            name="/set-moderator-role",
            value="If this is unset, only people with the Admin permission can use moderation features\n USAGE: /set-moderator-role <role-id>", inline=True)
    else:
        embedVar.add_field(
            name="/get-confession",
            value="See a confession by its number", inline=True)
    embedVar.add_field(
        name="Disclaimer:",
        value="All moderators can see who wrote anonymous confessions", inline=True)
    embedVar.set_author(name="This bot was created by Alissa(@Limzord)",url="https://gravatar.com/limzord",icon_url="https://2.gravatar.com/avatar/61b77b4c14bebabe890bf098f2bfcbdb88cf435a26c4f75dbdb3b7a97e998a1f?size=256&d=initials")


    await ctx.response.send_message(embed=embedVar,ephemeral=True)




file = open("bot-id.txt", "r")
bot_id = file.read()

bot.run(bot_id)