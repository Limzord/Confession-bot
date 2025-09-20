import discord
from discord import app_commands
from discord.ext import commands
import os, random
from random import randrange
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

intents = discord.Intents().all()
intents.members = True

bot = commands.Bot(command_prefix = '/', intents = intents)

default_settings = {
    "confession_channel" : 0,
    "confess_in_general" : True,
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
reply_to="the number of the confession you want to reply to\n or the link to the message you want to reply to",
ping_reply="whether or not to ping when replying",
image="an image to post with your confession")
async def confess(ctx: discord.Interaction,
message: str,
reply_to: str=None,
ping_reply: bool=False,
image: discord.Attachment=None):
    """write an anonymous confession"""
    if is_banned(ctx.guild.id,ctx.user.id):
        await ctx.response.send_message(content="Whoopsie, you did a stinky, beg the mods for forgiveness :3",ephemeral=True)
        return
    channel = await get_confession_channel(ctx.guild)
    if channel == 0:
        if not await is_moderator(guild=ctx.guild,user=ctx.user):
            await ctx.response.send_message(content="The mods forgot to set a confession channel. Please annoy them about this :3",ephemeral=True)
            return
        await bot_setup(ctx)
        return
    sidebarColor= discord.Color.from_rgb(randrange(255), randrange(255), randrange(255))
    confession_number = get_server_settings(ctx.guild.id)["confession_amount"] + 1
    embedVar = discord.Embed(
    title="💗 Silly Confession #" + (str)(confession_number), description=message, color=sidebarColor
            )
    imgURL = None
    if image:
        imgURL = image.url
        embedVar.set_image(url=imgURL)
    # if ctx.reference:
    #     channel = ctx.reference.channel
    #     await channel.send(embed=embedVar, reference=ctx.reference)
    reply_message = None
    reply_messageURL = None
    if reply_to:
        if reply_to.isdigit():
            reply_messageURL = json_get_confessionURL(number=reply_to, guild_id=ctx.guild_id)
            if reply_messageURL is None:
                await ctx.response.send_message(content="The confession you want to reply to doesn't exist or is too old😣",ephemeral=True)
                return
        else:
            reply_messageURL = reply_to
        reply_message = await get_message_from_URL(reply_messageURL)
        if reply_message is None:
            await ctx.response.send_message(content="The message URL you provided does not exist😣",ephemeral=True)
            return
    if reply_message:
        if reply_message.guild.id == ctx.guild_id:
            confession_channel = await get_confession_channel(ctx.guild)
            if reply_message.channel.id != confession_channel.id and not get_confess_in_general(ctx.guild_id):
                await ctx.response.send_message(content="You can only reply to messages in the confession channel😣",ephemeral=True)
                return
            bot_message = await reply_message.channel.send(embed=embedVar, reference=reply_message, mention_author=ping_reply)
            await send_message_to_log(ctx,message,confession_number,bot_message.id,channel.id,reply_messageURL,imgURL)
        else:
            await ctx.response.send_message(content="The message URL you provided is from a different server😣",ephemeral=True)
            return
    else:
        bot_message = await channel.send(embed=embedVar)
    await ctx.response.send_message(content="Your confession has been posted 🤫",ephemeral=True)
    if not reply_message:
        await send_message_to_log(ctx,message,confession_number,bot_message.id,channel.id,reply_messageURL,imgURL)

async def send_message_to_log(ctx: discord.Interaction, message: str, confession_number: int, message_id: int, channel_id: int, reply_messageURL: str, imgURL: str):
    user = ctx.user
    embedVar = discord.Embed(
    title="💗 Silly Confession #" + (str)(confession_number), description=message
            )
    embedVar.add_field(name="User", value="||" + user.mention + "||", inline=True)
    messageURL = get_URL_from_ids(guild_id=ctx.guild_id,channel_id=channel_id,message_id=message_id)
    embedVar.add_field(name="Message Link", value=messageURL, inline=True)
    if reply_messageURL:
        embedVar.add_field(name="In reply to", value=reply_messageURL, inline=True)
    if imgURL:
        embedVar.set_image(url=imgURL)
    channel = await get_log_channel(ctx.guild)
    if not channel == 0:
        await channel.send(embed=embedVar)
    add_message_to_log(confession_number,user.id,message, ctx.guild.id, message_id, channel_id, reply_messageURL, imgURL)

def add_message_to_log(number: int, user_id: int, message: str, guild_id: int, message_id: int, channel_id: int, reply_messageURL: str, imgURL: str):
    server_settings = get_server_settings(guild_id)
    server_settings["confession_amount"] += 1
    if reply_messageURL:
        if imgURL:
            server_settings["message_log"].append({"number": number, "user_id": user_id, "message": message, "message_id": message_id, "channel_id": channel_id, "reply_messageURL": reply_messageURL, "imgURL": imgURL})
        else:
            server_settings["message_log"].append({"number": number, "user_id": user_id, "message": message, "message_id": message_id, "channel_id": channel_id, "reply_messageURL": reply_messageURL})
    else:
        if imgURL:
            server_settings["message_log"].append({"number": number, "user_id": user_id, "message": message, "message_id": message_id, "channel_id": channel_id, "imgURL": imgURL})
        else:
            server_settings["message_log"].append({"number": number, "user_id": user_id, "message": message, "message_id": message_id, "channel_id": channel_id})
    write_server_settings(guild_id,server_settings)

@bot.tree.command(name='get-confession')
@app_commands.describe(number='the number of the confession')
async def get_confession(ctx: discord.Interaction,
number: int):
    """see the content of a confession from its number"""
    sidebarColor= discord.Color.from_rgb(randrange(255), randrange(255), randrange(255))
    confession = get_confession_from_number(number,ctx.guild_id)
    if confession == None:
        await ctx.response.send_message(content="This confession does not exist",ephemeral=True)
        return
    embedVar = discord.Embed(
    title="💗 Silly Confession #" + (str)(number), description=confession["message"], color=sidebarColor)
    if confession["user_id"] == ctx.user.id or await is_moderator(guild=ctx.guild,user=ctx.user):
        user = await bot.fetch_user(confession["user_id"])
        embedVar.add_field(name="User", value="||" + user.mention + "||", inline=True)
    if "message_id" in confession:
        messageURL = json_get_confessionURL(confession=confession,guild_id=ctx.guild_id)
        embedVar.add_field(name="Message Link", value=messageURL, inline=True)
    if "reply_messageURL" in confession:
        embedVar.add_field(name="In reply to", value=confession["reply_messageURL"], inline=True)
    if "imgURL" in confession:
        embedVar.set_image(url=confession["imgURL"])
    await ctx.response.send_message(embed=embedVar,ephemeral=True)

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

def get_confess_in_general(guild_id: int):
    server_settings = get_server_settings(guild_id)
    return server_settings["confess_in_general"]

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

def json_set_confess_in_general(guild_id: int, setting: bool):
    server_settings = get_server_settings(guild_id)
    server_settings["confess_in_general"] = setting
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

def json_get_confessionURL(guild_id: int, confession: dict=None, number: int=None, channel_id: int=None, message_id: int=None):
    try:
        if not confession:
            confession = get_confession_from_number(number,guild_id)
        if not channel_id:
            channel_id = confession["channel_id"]
        if not message_id:
            message_id = confession["message_id"]
        return get_URL_from_ids(guild_id=guild_id,channel_id=channel_id,message_id=message_id)
    except:
        return None

    
async def get_message_from_URL(URL: str):
    try:
        path = PurePosixPath(
            unquote(
                urlparse(
                    URL
                ).path
            )
        ).parts
        guild_id = int(path[2])
        channel_id = int(path[3])
        message_id = int(path[4])
        guild = await bot.fetch_guild(guild_id)
        channel = await guild.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)
        return message
    except:
        return None

def get_confession_from_number(number: int, guild_id: int):
    confessions = get_server_settings(guild_id)["message_log"]
    confession = next((item for item in confessions if (int)(item['number']) == (int)(number)), None)
    return confession

def get_URL_from_ids(guild_id: int, channel_id: int, message_id: int):
    return "https://discord.com/channels/" + (str)(guild_id) + "/" + (str)(channel_id) + "/" + (str)(message_id)

async def bot_setup(ctx: discord.Interaction):
    if await is_moderator(ctx.guild,ctx.user):
        server_settings = get_server_settings(ctx.guild_id)

        # Step 0: Introduce the concept of this menu
        view0 = StartupView()
        await ctx.response.send_message(
            "⚙️ Welcome to the setup process!\n\n"
            "Here you can select channels, roles, and settings\n"
            "For each option, click **Skip** to leave the option unchanged\n"
            "or select the value you would like and click **Confirm** to change the setting\n\n"
            "Press **Continue** to continue or **Cancel** to abort.",
            view=view0,
            ephemeral=True
        )
        await view0.wait()
        if view0.confirmed is False:
            await ctx.edit_original_response(
                content="❌ Setup has been cancelled",
                view=None
            )
            return

        # Step 1: Confession channel
        view1 = PaginatedSelector(guild=ctx.guild, label="Confession Channel", preselected=server_settings["confession_channel"], mode="channel")
        await ctx.edit_original_response(content="Set the channel anonymous confessions get sent into **⚠️REQUIRED⚠️**", view=view1)
        await view1.wait()
        new_confession_channel = view1.value

        # Step 2: Log channel
        view2 = PaginatedSelector(guild=ctx.guild, label="Log Channel", preselected=server_settings["log_channel"], mode="channel")
        await ctx.edit_original_response(content="Set the channel confession logs get sent into\n(this setting is optional and **⚠️SHOWS WHO WROTE CONFESSIONS⚠️**)", view=view2)
        await view2.wait()
        new_log_channel = view2.value

        # Step 3: Moderator role
        view3 = PaginatedSelector(guild=ctx.guild, label="Moderator Role", preselected=server_settings["moderator_role"], mode="role")
        await ctx.edit_original_response(content="Set the role which can use moderation features\n(change these settings, ban and unban people, see who wrote confessions)\nIf this is unset, only people with the Admin permission can use moderation features", view=view3)
        await view3.wait()
        new_moderator_role = view3.value

        # Step 4: General reply toggle
        view4 = SetupView(BoolSelect(server_settings["confess_in_general"]))
        await ctx.edit_original_response(content="Select whether or not users can reply with a confession to any message in the server\n(may cause chaos :3)", view=view4)
        await view4.wait()
        new_confess_in_general = view4.value

        # Final summary
        await ctx.edit_original_response(
            content=(
                "✅ Setup complete!\n\n"
                f"Confession Channel: {format_channel(new_confession_channel, server_settings["confession_channel"])}\n"
                f"Log Channel: {format_channel(new_log_channel, server_settings["log_channel"])}\n"
                f"Moderator Role: {format_role(new_moderator_role, server_settings["moderator_role"])}\n"
                f"Confession replies in all Channels: {format_bool(new_confess_in_general, server_settings["confess_in_general"])}"
            ),
            view=None,
        )

        # Here you would save to a database or config file
        if new_confession_channel is not None:
            json_set_confession_channel(ctx.guild.id, new_confession_channel)
        if new_log_channel is not None:
            json_set_log_channel(ctx.guild.id, new_log_channel)
        if new_moderator_role is not None:
            json_set_moderator_role(ctx.guild.id, new_moderator_role)
        if new_confess_in_general is not None:
            json_set_confess_in_general(ctx.guild.id, new_confess_in_general)
        return
    await ctx.response.send_message(content="Only moderators are allowed to change the bot settings",ephemeral=True)

def format_channel(value: int | None, previous_channel: int) -> str:
    if value is None:
        output = f"<#{previous_channel}>"
        return "Unchanged (" + output + ")"
    if value == 0:
        return "Unset"
    return f"<#{value}>"


def format_role(value: int | None, previous_role: int) -> str:
    if value is None:
        output = f"<@&{previous_role}>"
        return "Unchanged (" + output + ")"
    if value == 0:
        return "Unset"
    return f"<@&{value}>"


def format_bool(value: bool | None, previous_setting: bool) -> str:
    if value is None:
        output = "✅ Enabled" if previous_setting else "❌ Disabled"
        return "Unchanged (" + output + ")"
    return "✅ Enabled" if value else "❌ Disabled"

@bot.tree.command(name='setup')
async def bot_setup_command(ctx: discord.Interaction):
    """set up the bot settings"""
    await bot_setup(ctx)

def to_int_id(string):
    """Normalize saved values: accept int, numeric str, or discord objects with .id"""
    if string is None:
        return None
    if isinstance(string, int):
        return string
    if isinstance(string, str) and string.isdigit():
        return int(string)
    if hasattr(string, "id"):
        try:
            return int(string.id)
        except Exception:
            return None
    return None

def sort_channels(channels):
    # For channels inside categories, sort by (category_position, channel.position)
    # For channels without category, use category_position = -1
    def channel_key(c):
        cat_pos = c.category.position if c.category else -1
        return (cat_pos, c.position)
    return sorted(channels, key=channel_key)

def sort_roles(roles):
    sorted_roles = [r for r in roles if not r.is_default()]
    sorted_roles.reverse()
    return sorted_roles

# ------ alternate paginated selector -------
page_size = 24  # 24 items + 1 "None" option

class PaginatedSelector(discord.ui.View):
    def __init__(self, guild: discord.Guild, preselected: int | None = None,
                 mode: str = "channel", label: str = "Select"):
        preselected_id = to_int_id(preselected)
        super().__init__(timeout=120)

        self.guild = guild
        self.mode = mode
        self.label = label
        self.preselected = preselected_id
        self.value: int | None = preselected_id
        self.current_page = 0

        # prepare items list
        if self.mode == "channel":
            self.items = sort_channels(list(guild.text_channels))
        else:
            self.items = sort_roles(list(guild.roles))

        if self.preselected is not None and self.preselected != 0:
            found_idx = None
            for idx, item in enumerate(self.items):
                if item.id == self.preselected:
                    found_idx = idx
                    break
            if found_idx is not None:
                self.current_page = found_idx // page_size
            else:
                self.preselected = None
                self.value = None

        self._clamp_current_page()

        self.dropdown = self._get_dropdown()
        self.add_item(self.dropdown)

        if self._max_page() > 0:
            self.prev_btn = discord.ui.Button(label="Previous", style=discord.ButtonStyle.gray, row=1)
            self.next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.gray, row=1)
            self.prev_btn.callback = self.previous
            self.next_btn.callback = self.next
            self.add_item(self.prev_btn)
            self.add_item(self.next_btn)
            self._update_buttons()

        self.confirm_btn = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green, row=2)
        self.skip_btn = discord.ui.Button(label="Skip", style=discord.ButtonStyle.gray, row=2)
        self.confirm_btn.callback = self.confirm
        self.skip_btn.callback = self.skip
        self.add_item(self.confirm_btn)
        self.add_item(self.skip_btn)

    def _max_page(self) -> int:
        if not self.items:
            return 0
        return max(0, (len(self.items) - 1) // page_size)

    def _clamp_current_page(self):
        max_p = self._max_page()
        if self.current_page < 0:
            self.current_page = 0
        if self.current_page > max_p:
            self.current_page = max_p

    def _get_dropdown(self) -> discord.ui.Select:
        page_items = self.items[self.current_page * page_size:(self.current_page + 1) * page_size]

        options = [discord.SelectOption(label="None", value="0", default=(self.preselected == 0))]

        for item in page_items:
            label = f"#{item.name}" if self.mode == "channel" else item.name
            options.append(discord.SelectOption(label=label, value=str(item.id),
                                                default=(item.id == self.preselected)))

        select = discord.ui.Select(placeholder=self.label, min_values=1, max_values=1,
                                   options=options, row=0)
        select.callback = self.select_callback
        return select

    async def select_callback(self, interaction: discord.Interaction):
        try:
            self.value = int(self.dropdown.values[0])
        except Exception:
            pass
        await interaction.response.defer()

    async def previous(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await self._rebuild_view_and_edit(interaction)

    async def next(self, interaction: discord.Interaction):
        if self.current_page < self._max_page():
            self.current_page += 1
            await self._rebuild_view_and_edit(interaction)

    async def _rebuild_view_and_edit(self, interaction: discord.Interaction):
        self._clamp_current_page()

        self.clear_items()

        self.dropdown = self._get_dropdown()
        self.add_item(self.dropdown)

        if self._max_page() > 0 and hasattr(self, "prev_btn") and hasattr(self, "next_btn"):
            self.add_item(self.prev_btn)
            self.add_item(self.next_btn)
            self._update_buttons()

        self.add_item(self.confirm_btn)
        self.add_item(self.skip_btn)

        await interaction.response.edit_message(view=self)

    async def confirm(self, interaction: discord.Interaction):
        try:
            if getattr(self.dropdown, "values", None):
                self.value = int(self.dropdown.values[0])
            else:
                self.value = self.preselected
        except Exception:
            pass

        self.stop()
        await interaction.response.defer()

    async def skip(self, interaction: discord.Interaction):
        self.value = None
        self.stop()
        await interaction.response.defer()

    def _update_buttons(self):
        if hasattr(self, "prev_btn") and hasattr(self, "next_btn"):
            self.prev_btn.disabled = (self.current_page == 0)
            self.next_btn.disabled = (self.current_page >= self._max_page())

class BoolSelect(discord.ui.Select):
    def __init__(self, preselected: bool | None = None):
        options = [
            discord.SelectOption(label="Enabled", value="true", default=(preselected is True)),
            discord.SelectOption(label="Disabled", value="false", default=(preselected is False)),
        ]
        super().__init__(placeholder="Feature state...", min_values=1, max_values=1, options=options)
        # store boolean (or None if skipped)
        self.chosen: bool | None = preselected

    async def callback(self, interaction: discord.Interaction):
        self.chosen = (self.values[0] == "true")
        await interaction.response.defer()


# ---------- Reusable View with Skip/Confirm ----------

class SetupView(discord.ui.View):
    def __init__(self, dropdown: discord.ui.Select):
        super().__init__(timeout=60)
        self.dropdown = dropdown
        self.add_item(dropdown)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, row = 1)
    async def confirm(self, ctx: discord.Interaction, button: discord.ui.Button):
        self.value = self.dropdown.chosen
        self.stop()
        await ctx.response.defer()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray, row = 1)
    async def skip(self, ctx: discord.Interaction, button: discord.ui.Button):
        self.value = None
        self.stop()
        await ctx.response.defer()

# ---------- View for Startup ----------

class StartupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = None

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()



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
            name="/setup",
            value="Set up the bot or change existing settings", inline=True)
        # embedVar.add_field(
        #     name="/set-confession-channel",
        #     value="Set the channel anonymous confessions get sent into (⚠️REQUIRED⚠️)", inline=True)
        # embedVar.add_field(
        #     name="/set-log-channel",
        #     value="Set the channel confession logs get sent into (this setting is optional and ⚠️SHOWS WHO WROTE CONFESSIONS⚠️)", inline=True)
        # embedVar.add_field(
        #     name="/set-moderator-role",
        #     value="If this is unset, only people with the Admin permission can use moderation features\n USAGE: /set-moderator-role <role-id>", inline=True)
        # embedVar.add_field(
        #     name="/change-general",
        #     value="Change whether or not users can reply with a confession to any message in the server (default is off)", inline=True)
    else:
        embedVar.add_field(
            name="/get-confession",
            value="See a confession by its number", inline=True)
    embedVar.add_field(
        name="Disclaimer:",
        value="All moderators can see who wrote anonymous confessions", inline=True)
    embedVar.set_author(name="This bot was created by Alissa(@Limzord)",url="https://limzord.com",icon_url="https://limzord.com/pfp.png")


    await ctx.response.send_message(embed=embedVar,ephemeral=True)


# ------- deprecated commands --------

bot.remove_command("help")
@bot.command(pass_context=True,name='help')
async def old_help_command(ctx: discord.Interaction):
    await ctx.channel.send("Please use the proper /help command instead of writing it in chat")

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
                json_set_confession_channel(ctx.guild.id,(int)(channel_id))
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
                json_set_log_channel(ctx.guild.id,(int)(channel_id))
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
            json_set_moderator_role(ctx.guild.id,(int)(role_id))
            await ctx.channel.send("the moderator role was set to " + role.mention)
        except:
            await ctx.channel.send("Your message needs to be formatted like /set-moderator-role <role-id>")

@bot.command(pass_context=True,name='set-general-true')
async def set_confess_in_general_true(ctx: discord.Interaction):
    if not await is_moderator(guild=ctx.guild,user=ctx.message.author):
        await ctx.channel.send("Only moderators are allowed to use this command")
    else:
        json_set_confess_in_general(ctx.guild.id, True)
        await ctx.channel.send("members can now reply to any message")

@bot.command(pass_context=True,name='set-general-false')
async def set_confess_in_general_false(ctx: discord.Interaction):
    if not await is_moderator(guild=ctx.guild,user=ctx.message.author):
        await ctx.channel.send("Only moderators are allowed to use this command")
    else:
        json_set_confess_in_general(ctx.guild.id, False)
        await ctx.channel.send("members can no longer reply to any message")

@bot.command(pass_context=True,name='change-general')
async def change_confess_in_general(ctx: discord.Interaction):
    if not await is_moderator(guild=ctx.guild,user=ctx.message.author):
        await ctx.channel.send("Only moderators are allowed to use this command")
    else:
        if get_confess_in_general(ctx.guild.id):
            json_set_confess_in_general(ctx.guild.id, False)
            await ctx.channel.send("members can no longer reply to any message")
        else:
            json_set_confess_in_general(ctx.guild.id, True)
            await ctx.channel.send("members can no longer reply to any message")




file = open("bot-id.txt", "r")
bot_id = file.read()

bot.run(bot_id)