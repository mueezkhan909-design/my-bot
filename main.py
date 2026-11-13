import asyncio
from datetime import datetime, timedelta
import re
import discord
from discord import app_commands
from discord.ext import commands

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=["!", "."], intents=intents)

# Configurations
YOUR_USER_ID = 1200742018494763019
JAIL_ROLE_NAME = "JAILED"
VERDICT_VC_ID = 123456789012345678  # Yahan apna Verdict VC ID daal dein
DEFAULT_VC_MUTE_QUOTA = 5
CAT_IMAGE_URL = (
    "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?auto=format&fit=crop&w=500&q=80"
)

# Memory Databases
user_warns = {}
warn_id_counter = 100
deleted_messages = {}
setup_db = {}
user_vc_quotas = {}
jailed_users = {}  # {user_id: {"release_time": datetime_obj / None, "guild_id": id}}


def parse_duration(duration_str: str):
  """Parses strings like '2h', '30m', '1d', '10s' into seconds."""
  match = re.match(r"^(\d+)([smhd])$", duration_str.lower())
  if not match:
    return None
  amount, unit = int(match.group(1)), match.group(2)
  if unit == "s":
    return amount
  elif unit == "m":
    return amount * 60
  elif unit == "h":
    return amount * 3600
  elif unit == "d":
    return amount * 86400
  return None


@bot.event
async def on_ready():
  print(f"✅ Bot Online Hai! Logged in as: {bot.user.name}")
  bot.loop.create_task(auto_unjail_loop())
  try:
    synced = await bot.tree.sync()
    print(f"✅ Synced {len(synced)} Slash Commands Successfully!")
  except Exception as e:
    print(f"❌ Slash Command Sync Error: {e}")


async def auto_unjail_loop():
  """Background loop to check and automatically release jailed members."""
  await bot.wait_until_ready()
  while not bot.is_closed():
    now = datetime.utcnow()
    to_release = []

    for user_id, data in list(jailed_users.items()):
      release_time = data.get("release_time")
      if release_time and now >= release_time:
        to_release.append((user_id, data["guild_id"]))

    for user_id, guild_id in to_release:
      guild = bot.get_guild(guild_id)
      if guild:
        member = guild.get_member(user_id)
        role = discord.utils.get(guild.roles, name=JAIL_ROLE_NAME)
        if member and role and role in member.roles:
          try:
            await member.remove_roles(role)
          except Exception:
            pass
      jailed_users.pop(user_id, None)

    await asyncio.sleep(10)


def get_guild_setup(guild_id):
  if guild_id not in setup_db:
    setup_db[guild_id] = {"categories": {}}
  return setup_db[guild_id]
# ==========================================
# 3. MODERATION COMMANDS (MUTE, JAIL, ETC.)
# ==========================================
@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute_user(
    ctx, target: str = None, *, reason: str = "No reason provided."
):
  if not target:
    return await ctx.send(
        "⚠️ Sahi format: `.mute <@user/ID> [reason]` (e.g., `.mute @user spamming`)"
    )

  try:
    user_id = int(re.sub(r"\D", "", target))
    member = ctx.guild.get_member(user_id) or await ctx.guild.fetch_member(
        user_id
    )
  except Exception:
    return await ctx.send(
        "❌ User nahi mila! Valid User ID ya Mention ka istemal karein."
    )

  try:
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if mute_role:
      await member.add_roles(mute_role, reason=reason)
    else:
      await member.timeout(timedelta(hours=24), reason=reason)

    embed = discord.Embed(
        title="🔨 Moderation\nAction — Mute", color=discord.Color.red()
    )
    embed.add_field(
        name="👤 Target", value=f"{member.mention}\n({member.id})", inline=False
    )
    embed.add_field(
        name="🛡️ Moderator",
        value=f"{ctx.author.mention}\n({ctx.author.id})",
        inline=False,
    )
    embed.add_field(name="📋 Reason", value=reason, inline=False)

    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)

  except discord.Forbidden:
    await ctx.send("❌ Bot hierarchy issue! Permissions check karein.")


@bot.command(name="jail")
@commands.has_permissions(manage_roles=True)
async def jail_user(
    ctx,
    target: str = None,
    duration: str = None,
    *,
    reason: str = "No reason provided.",
):
  if not target:
    return await ctx.send(
        "⚠️ Sahi format: `.jail <@user/ID> <duration> [reason]` (e.g., `.jail"
        " @user 2h bad behavior`)"
    )

  try:
    user_id = int(re.sub(r"\D", "", target))
    member = ctx.guild.get_member(user_id) or await ctx.guild.fetch_member(
        user_id
    )
  except Exception:
    return await ctx.send(
        "❌ User nahi mila! Valid User ID ya Mention ka istemal karein."
    )

  role = discord.utils.get(ctx.guild.roles, name=JAIL_ROLE_NAME)
  if role is None:
    return await ctx.send(f"❌ Server me **{JAIL_ROLE_NAME}** role nahi mila!")

  seconds = parse_duration(duration) if duration else None
  if duration and seconds is None:
    reason = f"{duration} {reason}".strip()
    seconds = None

  try:
    await member.add_roles(role)

    release_time = None
    duration_text = "Not specified"
    auto_release_text = "Manual Release"

    if seconds:
      release_time = datetime.utcnow() + timedelta(seconds=seconds)
      jailed_users[member.id] = {
          "release_time": release_time,
          "guild_id": ctx.guild.id,
      }
      duration_text = duration
      timestamp_unix = int(release_time.timestamp())
      auto_release_text = f"<t:{timestamp_unix}:R>"

    embed = discord.Embed(
        title="🔨 Moderation\nAction — Jail", color=discord.Color.orange()
    )
    embed.add_field(
        name="👤 Target", value=f"{member.mention}\n({member.id})", inline=False
    )
    embed.add_field(
        name="🛡️ Moderator",
        value=f"{ctx.author.mention}\n({ctx.author.id})",
        inline=False,
    )
    embed.add_field(name="📋 Reason", value=reason, inline=False)
    embed.add_field(name="⏰ Duration", value=duration_text, inline=False)
    embed.add_field(
        name="🔓 Auto-release", value=auto_release_text, inline=False
    )

    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)

  except discord.Forbidden:
    await ctx.send("❌ Bot hierarchy issue! Check permissions.")


@bot.command(name="pjail")
@commands.has_permissions(manage_roles=True)
async def permanent_jail_user(
    ctx, target: str = None, *, reason: str = "No reason provided."
):
  if not target:
    return await ctx.send("⚠️ Sahi format: `.pjail <@user/ID> [reason]`")

  try:
    user_id = int(re.sub(r"\D", "", target))
    member = ctx.guild.get_member(user_id) or await ctx.guild.fetch_member(
        user_id
    )
  except Exception:
    return await ctx.send(
        "❌ User nahi mila! Valid User ID ya Mention ka istemal karein."
    )

  role = discord.utils.get(ctx.guild.roles, name=JAIL_ROLE_NAME)
  if role is None:
    return await ctx.send(f"❌ Server me **{JAIL_ROLE_NAME}** role nahi mila!")

  try:
    await member.add_roles(role)
    jailed_users.pop(member.id, None)

    embed = discord.Embed(
        title="🔨 Moderation\nAction — Permanent\nJail",
        color=discord.Color.red(),
    )
    embed.add_field(
        name="👤 Target", value=f"<@{member.id}>\n({member.id})", inline=False
    )
    embed.add_field(
        name="🛡️ Moderator",
        value=f"<@{ctx.author.id}>\n({ctx.author.id})",
        inline=False,
    )
    embed.add_field(name="📋 Reason", value=reason, inline=False)
    embed.add_field(
        name="⚠️ Notice", value="This is a permanent jail.", inline=False
    )

    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)

  except discord.Forbidden:
    await ctx.send("❌ Bot hierarchy issue!")


@bot.command(name="unjail")
@commands.has_permissions(manage_roles=True)
async def unjail_user(ctx, target: str = None):
  if not target:
    return await ctx.send("⚠️ Format: `.unjail <@user/ID>`")

  try:
    user_id = int(re.sub(r"\D", "", target))
    member = ctx.guild.get_member(user_id) or await ctx.guild.fetch_member(
        user_id
    )
  except Exception:
    return await ctx.send("❌ User nahi mila!")

  role = discord.utils.get(ctx.guild.roles, name=JAIL_ROLE_NAME)
  if role is None:
    return await ctx.send(f"❌ Server me **{JAIL_ROLE_NAME}** role nahi mila!")

  try:
    if role in member.roles:
      await member.remove_roles(role)
      jailed_users.pop(member.id, None)

      embed = discord.Embed(
          title="🔓 Member Unjailed!",
          description=f"Successfully released {member.mention} from Jail! 🎉",
          color=discord.Color.green(),
      )
      embed.set_thumbnail(url=CAT_IMAGE_URL)
      embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
      await ctx.send(embed=embed)
    else:
      await ctx.send(f"⚠️ {member.mention} jailed nahi hai!")
  except discord.Forbidden:
    await ctx.send("❌ Bot Hierarchy Issue!")


# ==========================================
# 2. SLASH COMMANDS GROUP (/setup)
# ==========================================
setup_group = app_commands.Group(
    name="setup", description="Role Configuration Commands"
)


@setup_group.command(name="category", description="Create a new role category")
@app_commands.checks.has_permissions(administrator=True)
async def setup_category(interaction: discord.Interaction, category_name: str):
  db = get_guild_setup(interaction.guild_id)
  cat_key = category_name.lower().strip()

  if cat_key in db["categories"]:
    await interaction.response.send_message(
        f"❌ Category **{category_name}** pehle se bani hui hai!",
        ephemeral=True,
    )
    return

  db["categories"][cat_key] = {"name": category_name, "req_role": None, "roles": []}

  embed = discord.Embed(
      title="✅ Category Created",
      description=f"New category **{category_name}** has been successfully created!",
      color=discord.Color.green(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="addrole", description="Add a role command to a category"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_addrole(
    interaction: discord.Interaction, category_name: str, role: discord.Role
):
  db = get_guild_setup(interaction.guild_id)
  cat_key = category_name.lower().strip()

  if cat_key not in db["categories"]:
    await interaction.response.send_message(
        f"❌ Category **{category_name}** nahi mili!", ephemeral=True
    )
    return

  if role.id in db["categories"][cat_key]["roles"]:
    await interaction.response.send_message(
        f"⚠️ Role {role.mention} is category me pehle se added hai!",
        ephemeral=True,
    )
    return

  db["categories"][cat_key]["roles"].append(role.id)

  embed = discord.Embed(
      title="✅ Role Added",
      description=(
          f"Added {role.mention} to category"
          f" **{db['categories'][cat_key]['name']}**."
      ),
      color=discord.Color.green(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="removerole", description="Remove a role command from a category"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_removerole(
    interaction: discord.Interaction, category_name: str, role: discord.Role
):
  db = get_guild_setup(interaction.guild_id)
  cat_key = category_name.lower().strip()

  if cat_key not in db["categories"]:
    await interaction.response.send_message(
        f"❌ Category **{category_name}** nahi mili!", ephemeral=True
    )
    return

  if role.id not in db["categories"][cat_key]["roles"]:
    await interaction.response.send_message(
        f"⚠️ Role {role.mention} is category me nahi hai!", ephemeral=True
    )
    return

  db["categories"][cat_key]["roles"].remove(role.id)

  embed = discord.Embed(
      title="❌ Role Removed",
      description=(
          f"Removed {role.mention} from category"
          f" **{db['categories'][cat_key]['name']}**."
      ),
      color=discord.Color.red(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="reqrole", description="Set the required role for a category"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_reqrole(
    interaction: discord.Interaction,
    category_name: str,
    required_role: discord.Role,
):
  db = get_guild_setup(interaction.guild_id)
  cat_key = category_name.lower().strip()

  if cat_key not in db["categories"]:
    await interaction.response.send_message(
        f"❌ Category **{category_name}** nahi mili!", ephemeral=True
    )
    return

  db["categories"][cat_key]["req_role"] = required_role.id

  embed = discord.Embed(
      title="⚙️ Required Role Updated",
      description=(
          f"Category **{db['categories'][cat_key]['name']}** ke roles dene ke"
          f" liye ab {required_role.mention} zaroori hai!"
      ),
      color=discord.Color.gold(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="delcategory", description="Delete an entire category"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_delcategory(
    interaction: discord.Interaction, category_name: str
):
  db = get_guild_setup(interaction.guild_id)
  cat_key = category_name.lower().strip()

  if cat_key not in db["categories"]:
    await interaction.response.send_message(
        f"❌ Category **{category_name}** nahi mili!", ephemeral=True
    )
    return

  del db["categories"][cat_key]

  embed = discord.Embed(
      title="🗑️ Category Deleted",
      description=f"Category **{category_name}** has been deleted.",
      color=discord.Color.red(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="config", description="Shows full configuration overview"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_config(interaction: discord.Interaction):
  db = get_guild_setup(interaction.guild_id)
  categories = db["categories"]

  if not categories:
    await interaction.response.send_message(
        "⚠️ Koi configurations/categories nahi bani hui hain!", ephemeral=True
    )
    return

  embed = discord.Embed(
      title="⚙️ Full Configuration Overview", color=discord.Color.blue()
  )

  for cat_key, data in categories.items():
    req_role_mention = (
        f"<@&{data['req_role']}>" if data["req_role"] else "None"
    )
    roles_mentions = (
        ", ".join([f"<@&{r}>" for r in data["roles"]])
        if data["roles"]
        else "No Roles Added"
    )

    field_value = (
        f"**Required Role:** {req_role_mention}\n**Roles:** {roles_mentions}"
    )
    embed.add_field(name=f"📁 {data['name']}", value=field_value, inline=False)

  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="list", description="List all categories or roles in a category"
)
async def setup_list(
    interaction: discord.Interaction, category_name: str = None
):
  db = get_guild_setup(interaction.guild_id)
  categories = db["categories"]

  if not categories:
    await interaction.response.send_message(
        "⚠️ Server me koi category setup nahi hai!", ephemeral=True
    )
    return

  if category_name:
    cat_key = category_name.lower().strip()
    if cat_key not in categories:
      await interaction.response.send_message(
          f"❌ Category **{category_name}** nahi mili!", ephemeral=True
      )
      return

    data = categories[cat_key]
    req_role = f"<@&{data['req_role']}>" if data["req_role"] else "None"
    roles_list = (
        "\n".join([f"• <@&{r}>" for r in data["roles"]])
        if data["roles"]
        else "No roles in this category."
    )

    embed = discord.Embed(
        title=f"📋 Category Details — {data['name']}",
        color=discord.Color.purple(),
    )
    embed.add_field(name="Required Role", value=req_role, inline=False)
    embed.add_field(name="Roles List", value=roles_list, inline=False)
  else:
    cat_list = "\n".join([f"• **{v['name']}**" for v in categories.values()])
    embed = discord.Embed(
        title="📋 All Configured Categories",
        description=cat_list,
        color=discord.Color.purple(),
    )

  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="guide", description="Step-by-step guide for setting up"
)
async def setup_guide(interaction: discord.Interaction):
  embed = discord.Embed(
      title="📖 Setup Guide",
      description=(
          "Follow these steps to configure role assignments:\n\n"
          "1️⃣ **Create Category:** `/setup category <name>`\n"
          "2️⃣ **Set Required Role:** `/setup reqrole <category> <role>`\n"
          "3️⃣ **Add Roles:** `/setup addrole <category> <role>`\n"
          "4️⃣ **Check Config:** `/setup config`\n"
          "5️⃣ **Remove Role:** `/setup removerole <category> <role>`\n"
          "6️⃣ **Delete Category:** `/setup delcategory <category>`"
      ),
      color=discord.Color.gold(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


@setup_group.command(
    name="reset", description="Reset all custom role configuration"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_reset(interaction: discord.Interaction):
  guild_id = interaction.guild_id
  if guild_id in setup_db:
    setup_db[guild_id] = {"categories": {}}

  embed = discord.Embed(
      title="⚠️ Configuration Reset",
      description=(
          "All custom role categories and configurations have been completely"
          " reset!"
      ),
      color=discord.Color.red(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed)


bot.tree.add_command(setup_group)
# ==========================================
# 4. VOICE, EVENTS, SCAN & EXTRA COMMANDS
# ==========================================


@bot.command(name="vchelp")
async def vchelp_command(ctx):
  if not ctx.author.voice or not ctx.author.voice.channel:
    return await ctx.send(
        "⚠️ Pehle aapko kisi voice channel me join karna hoga!"
    )

  vc_channel = ctx.author.voice.channel
  vc_help_role = discord.utils.get(ctx.guild.roles, name="VC HELP")

  role_mention = vc_help_role.mention if vc_help_role else "@VC HELP"

  await ctx.send(
      f"{role_mention} {ctx.author.mention} needs help in **{vc_channel.name}**!"
      " A mod can use `.wv` to jump to their VC."
  )


@bot.command(name="wv")
@commands.has_permissions(move_members=True)
async def warp_to_vc(ctx, target_member: discord.Member = None):
  if not ctx.author.voice:
    return await ctx.send(
        "⚠️ Pehle aapko kisi voice channel me connect hona padega!"
    )

  if target_member is None:
    if ctx.message.reference:
      try:
        ref_msg = await ctx.channel.fetch_message(
            ctx.message.reference.message_id
        )
        if ref_msg.mentions:
          target_member = ref_msg.mentions[0]
      except Exception:
        pass

  if target_member is None or not target_member.voice:
    return await ctx.send(
        "❌ User nahi mila ya woh kisi voice channel me nahi hai! (Kripya reply"
        " karein ya mention karein)"
    )

  mod_vc = ctx.author.voice.channel
  try:
    await target_member.move_to(mod_vc)
    embed = discord.Embed(
        title="✅ Warped to VC",
        description=(
            f"Moved you to **{mod_vc.name}** to help"
            f" {target_member.mention}."
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
  except Exception as e:
    await ctx.send(f"❌ Error moving user: {e}")


@bot.command(name="vvc")
@commands.has_permissions(move_members=True)
async def vvc(ctx, target: str = None):
  if target is None:
    return await ctx.send("⚠️ Sahi format: `.vvc @user` ya `.vvc all`")

  verdict_vc = ctx.guild.get_channel(VERDICT_VC_ID)
  if not verdict_vc:
    return await ctx.send("❌ Verdict VC Channel nahi mila! Config check karein.")

  if target.lower() == "all":
    if not ctx.author.voice or not ctx.author.voice.channel:
      return await ctx.send(
          "⚠️ Pehle kisi voice channel me join karke command use karein!"
      )

    current_vc = ctx.author.voice.channel
    members_to_move = [
        m for m in current_vc.members if m.id != ctx.author.id and not m.bot
    ]

    if not members_to_move:
      return await ctx.send("❌ Channel me drag karne ke liye members nahi hain.")

    for member in members_to_move:
      try:
        await member.move_to(verdict_vc)
      except Exception:
        pass

    embed = discord.Embed(
        title="🎙️ Voice Mass Drag",
        description=(
            f"All members from **{current_vc.name}** moved to"
            f" **{verdict_vc.name}**!"
        ),
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)

  else:
    try:
      member = await commands.MemberConverter().convert(ctx, target)
      if member.voice:
        await member.move_to(verdict_vc)
        embed = discord.Embed(
            title="🎙️ Voice Move",
            description=(
                f"Moved {member.mention} to Verdict VC (**{verdict_vc.name}**)."
            ),
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=CAT_IMAGE_URL)
        embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
        await ctx.send(embed=embed)
      else:
        await ctx.send(f"⚠️ {member.mention} kisi voice channel me nahi hai!")
    except commands.BadArgument:
      await ctx.send("❌ User nahi mila! `@mention` karein ya `all` likhein.")


@bot.command(name="drag")
@commands.has_permissions(move_members=True)
async def drag_user(ctx, member: discord.Member = None):
  if member is None:
    return await ctx.send("⚠️ Sahi format: `.drag @user`")

  if not ctx.author.voice or not ctx.author.voice.channel:
    return await ctx.send("⚠️ Pehle aapko kisi voice channel me hona padega!")

  if member.voice:
    target_vc = ctx.author.voice.channel
    await member.move_to(target_vc)
    embed = discord.Embed(
        title="🎙️ Voice Drag",
        description=f"Dragged {member.mention} to **{target_vc.name}**.",
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
  else:
    await ctx.send(f"⚠️ {member.mention} kisi voice channel me nahi hai!")


@bot.command(name="dc", aliases=["disconnect"])
@commands.has_permissions(move_members=True)
async def disconnect_user(ctx, member: discord.Member = None):
  if member is None:
    return await ctx.send("⚠️ Sahi format: `.dc @user`")

  if member.voice:
    await member.move_to(None)
    embed = discord.Embed(
        title="🔌 Voice Disconnect",
        description=f"Disconnected {member.mention} from voice channel.",
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
  else:
    await ctx.send(f"⚠️ {member.mention} kisi voice channel me nahi hai!")


@bot.command(name="vcmute")
@commands.has_permissions(mute_members=True)
async def vcmute_user(ctx, member: discord.Member = None):
  if member is None:
    return await ctx.send("⚠️ Sahi format: `.vcmute @user`")

  user_id = ctx.author.id
  current_quota = user_vc_quotas.get(user_id, DEFAULT_VC_MUTE_QUOTA)

  if current_quota <= 0:
    return await ctx.send(
        "❌ Aapka daily **vcmute quota** khatam ho gaya hai! (0 Remaining)"
    )

  if member.voice:
    await member.edit(mute=True)
    user_vc_quotas[user_id] = current_quota - 1

    embed = discord.Embed(
        title="🔇 Voice Server Muted",
        description=(
            f"{member.mention} was server-muted for 12 hours!\n**Remaining"
            f" Quota:** {user_vc_quotas[user_id]}/{DEFAULT_VC_MUTE_QUOTA}"
        ),
        color=discord.Color.dark_red(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)

    await asyncio.sleep(12 * 3600)
    if member.voice and member.voice.mute:
      await member.edit(mute=False)
  else:
    await ctx.send(f"⚠️ {member.mention} kisi voice channel me nahi hai!")


@bot.command(name="vcunmute")
@commands.has_permissions(mute_members=True)
async def vcunmute_user(ctx, member: discord.Member = None):
  if member is None:
    return await ctx.send("⚠️ Sahi format: `.vcunmute @user`")

  if member.voice:
    await member.edit(mute=False)
    embed = discord.Embed(
        title="🔊 Voice Server Unmuted",
        description=f"Server-mute removed from {member.mention}.",
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
  else:
    await ctx.send(f"⚠️ {member.mention} kisi voice channel me nahi hai!")


@bot.command(name="vcstatus")
async def vcstatus(ctx):
  quota = user_vc_quotas.get(ctx.author.id, DEFAULT_VC_MUTE_QUOTA)
  embed = discord.Embed(
      title="📊 VC Mute Quota Status",
      description=(
          f"User: {ctx.author.mention}\nRemaining VC Mute Quota:"
          f" **{quota}/{DEFAULT_VC_MUTE_QUOTA}**"
      ),
      color=discord.Color.gold(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed)


@bot.event
async def on_message_delete(message):
  if message.author and message.author.bot:
    return

  content = message.content if message.content else "*(No text / Only Media)*"
  attachment_url = (
      message.attachments[0].url if message.attachments else None
  )

  deleted_messages[message.channel.id] = {
      "content": content,
      "author": message.author,
      "time": message.created_at,
      "attachment": attachment_url,
  }


@bot.event
async def on_message(message):
  if message.author.bot:
    return

  is_mentioned = any(user.id == YOUR_USER_ID for user in message.mentions)
  is_reply_to_you = False

  if message.reference and message.reference.message_id:
    try:
      ref_msg = await message.channel.fetch_message(
          message.reference.message_id
      )
      if ref_msg.author.id == YOUR_USER_ID:
        is_reply_to_you = True
    except Exception:
      pass

  if is_mentioned or is_reply_to_you:
    try:
      await message.add_reaction("👑")
    except Exception as e:
      print(f"Reaction Error: {e}")

  # Handle shortcut reply commands (tcm, cm, og)
  msg_content = message.content.strip().lower()
  if msg_content in ["tcm", "cm", "og"] and message.reference:
    try:
      referenced_msg = await message.channel.fetch_message(
          message.reference.message_id
      )
      target_member = referenced_msg.author

      if isinstance(target_member, discord.Member):
        role_name_to_toggle = (
            "TRIAL CHAT MOD"
            if msg_content == "tcm"
            else ("CHAT MOD" if msg_content == "cm" else "OGz") 
        )
        role = discord.utils.get(message.guild.roles, name=role_name_to_toggle)

        if role is None:
          await message.channel.send(
              f"❌ Server me **{role_name_to_toggle}** role nahi mila!"
          )
          return

        if role in target_member.roles:
          await target_member.remove_roles(role)
          embed = discord.Embed(
              title="❌ Role Removed",
              description=(
                  f"Successfully removed {role.mention} from"
                  f" {target_member.mention}."
              ),
              color=discord.Color.red(),
          )
        else:
          await target_member.add_roles(role)
          embed = discord.Embed(
              title="✅ Role Added",
              description=(
                  f"Successfully gave {role.mention} to {target_member.mention}."
              ),
              color=discord.Color.green(),
          )

        embed.set_thumbnail(url=CAT_IMAGE_URL)
        embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
        await message.channel.send(embed=embed)
    except Exception as e:
      await message.channel.send(f"❌ Error: {e}")

  await bot.process_commands(message)


@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn_user(
    ctx, member: discord.Member = None, *, reason="No reason provided"
):
  global warn_id_counter
  if member is None:
    await ctx.send("⚠️ Format: `.warn @user <reason>`")
    return

  guild_id = ctx.guild.id
  user_id = member.id

  if guild_id not in user_warns:
    user_warns[guild_id] = {}
  if user_id not in user_warns[guild_id]:
    user_warns[guild_id][user_id] = []

  warn_id_counter += 1
  user_warns[guild_id][user_id].append({
      "id": warn_id_counter,
      "reason": reason,
      "mod": ctx.author.mention,
  })

  warn_count = len(user_warns[guild_id][user_id])
  action_taken = "⚠️ 1st Warning (No Offense)"

  try:
    if warn_count == 1:
      action_taken = "⚠️ 1st Warning (No Offense)"
    elif warn_count == 2:
      await member.timeout(timedelta(hours=2), reason=f"2nd Warn: {reason}")
      action_taken = "⏳ 2 Hours Timeout"
    elif warn_count == 3:
      await member.timeout(timedelta(days=1), reason=f"3rd Warn: {reason}")
      action_taken = "⏳ 1 Day Timeout"
    elif warn_count == 4:
      jail_role = discord.utils.get(ctx.guild.roles, name=JAIL_ROLE_NAME)
      if jail_role:
        await member.add_roles(jail_role)
        action_taken = f"🔒 Sent to Jail ({JAIL_ROLE_NAME} role applied)"
      else:
        action_taken = f"🔒 4th Warn (No {JAIL_ROLE_NAME} Role Found)"
    elif warn_count >= 5:
      await member.ban(reason=f"Reached 5 warnings. Last reason: {reason}")
      action_taken = "⛔ Banned from Server"
  except discord.Forbidden:
    action_taken += " (Hierarchy Error)"

  embed1 = discord.Embed(
      title="⚠️ Member Warned", color=discord.Color.dark_gold()
  )
  embed1.add_field(name="👤 User", value=member.mention, inline=False)
  embed1.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=False)
  embed1.add_field(
      name="📊 Warn Count", value=f"**{warn_count}/5**", inline=False
  )
  embed1.add_field(name="⚡ Action Taken", value=action_taken, inline=False)
  embed1.add_field(name="📄 Reason", value=reason, inline=False)

  embed1.set_thumbnail(url=CAT_IMAGE_URL)
  embed1.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed1)


@bot.command(name="scan")
async def scan_user(ctx, member: discord.Member = None):
  member = member or ctx.author
  warns_list = user_warns.get(ctx.guild.id, {}).get(member.id, [])

  joined_unix = int(member.joined_at.timestamp()) if member.joined_at else None
  joined_text = (
      f"<t:{joined_unix}:F> (<t:{joined_unix}:R>)" if joined_unix else "Unknown"
  )

  embed = discord.Embed(
      title=f"📋 Moderation History — {member.display_name}",
      color=discord.Color.orange(),
  )
  embed.add_field(
      name="👤 User", value=f"{member.mention}\n`{member.id}`", inline=False
  )
  embed.add_field(name="📅 Joined Server", value=joined_text, inline=False)
  embed.add_field(
      name="📊 Total Warnings", value=f"**{len(warns_list)}**", inline=False
  )

  if warns_list:
    recent_text = "".join(
        f"#{i['id']} ✅ {i['reason']} — {i['mod']}\n"
        for i in reversed(warns_list[-5:])
    )
    embed.add_field(name="⚠️ Recent Warnings", value=recent_text, inline=False)
  else:
    embed.add_field(
        name="⚠️ Recent Warnings", value="No warnings recorded.", inline=False
    )

  embed.set_thumbnail(url=member.display_avatar.url)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed)


@bot.command(name="snipe")
async def snipe_message(ctx):
  snipe_data = deleted_messages.get(ctx.channel.id)
  if not snipe_data:
    await ctx.send("❌ Is channel me koi deleted message nahi mila!")
    return

  author = snipe_data["author"]
  embed = discord.Embed(
      title="🗑️ Message Sniped!",
      description=snipe_data["content"],
      color=discord.Color.gold(),
      timestamp=snipe_data["time"],
  )
  embed.set_author(
      name=f"Sent by: {author.display_name if author else 'Unknown'}",
      icon_url=author.display_avatar.url if author else None,
  )
  if snipe_data["attachment"]:
    embed.set_image(url=snipe_data["attachment"])

  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed)


async def toggle_role(ctx, member: discord.Member, role_name: str):
  if member is None:
    await ctx.send(f"⚠️cutie pie sahi formart use krSahi format: `{ctx.prefix}{ctx.command.name} @user`")
    return

  role = discord.utils.get(ctx.guild.roles, name=role_name)
  if not role:
    await ctx.send(f"❌ Server me **{role_name}** role nahi mila!")
    return

  try:
    if role in member.roles:
      await member.remove_roles(role)
      embed = discord.Embed(
          title="❌ Role Removed",
          description=f"Removed {role.mention} from {member.mention}.",
          color=discord.Color.red(),
      )
    else:
      await member.add_roles(role)
      embed = discord.Embed(
          title="✅ Role Added",
          description=f"Gave {role.mention} to {member.mention}.",
          color=discord.Color.green(),
      )

    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
  except discord.Forbidden:
    await ctx.send("❌ Bot Hierarchy Issue!")


@bot.command(name="trialchatmod")
@commands.has_permissions(manage_roles=True)
async def trial_chat_mod(ctx, member: discord.Member = None):
  await toggle_role(ctx, member, "TRIAL CHAT MOD")


@bot.command(name="chatmod", aliases=["cm"])
@commands.has_permissions(manage_roles=True)
async def chat_mod_role(ctx, member: discord.Member = None):
  await toggle_role(ctx, member, "CHAT MOD")


@bot.command(name="og", aliases=["ogz"])
@commands.has_permissions(manage_roles=True)
async def og_role(ctx, member: discord.Member = None):
  await toggle_role(ctx, member, "OGz")


@bot.command(name="🔫")
@commands.has_permissions(manage_roles=True)
async def gun_role(ctx, member: discord.Member = None):
  await toggle_role(ctx, member, "🔫")


@bot.command(name="bindlist")
async def bind_list(ctx):
  embed = discord.Embed(
      title="📋 All Commands List",
      description=(
          "**Moderation & Jail:**\n"
          "`.mute <@user/ID> [reason]` | `.jail <@user/ID> <duration> [reason]`"
          " | `.pjail` | `.unjail`\n"
          "`.warn` | `.scan` | `.snipe` | `.trialchatmod` | `.cm` | `.og` |"
          " `.🔫`\n\n"
          "**Voice Activity & Moderation:**\n"
          "`.vchelp` | `.wv` | `.vvc @user` | `.vvc all` | `.drag @user` |"
          " `.dc @user`\n"
          "`.vcmute @user` | `.vcunmute @user` | `.vcstatus`"
      ),
      color=discord.Color.gold(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed)
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    
    # Status set karne ka code jo pehle banaya tha:
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="OVER SHADOWS SERVER (PREFIX !"))
    
    # --- Mueez Support VC me join karne ka code ---
    channel_id = 1546051220806836305
    channel = bot.get_channel(channel_id)
    if channel:
        try:
            await channel.connect()
            print(f"Connected to voice channel: {channel.name}")
        except Exception as e:
            print(f"Failed to connect to VC: {e}")
    # ---------------------------------------------
# ==========================================
# LOUNGE MOD (LM) SEPARATE COMMAND & EVENT
# ==========================================


@bot.command(name="loungemod", aliases=["lm"])
@commands.has_permissions(manage_roles=True)
async def lounge_mod_role(ctx, member: discord.Member = None):
  await toggle_role(ctx, member, "LOUNGE MOD")


@bot.event
async def on_message(message):
  if message.author.bot:
    await bot.process_commands(message)
    return

  msg_content = message.content.strip().lower()

  # Agar kisi ne reply karke 'lm' likha hai
  if msg_content == "lm" and message.reference:
    try:
      referenced_msg = await message.channel.fetch_message(
          message.reference.message_id
      )
      target_member = referenced_msg.author
      if isinstance(target_member, discord.Member):
        role_name_to_toggle = "LOUNGE MOD"
        role = discord.utils.get(message.guild.roles, name=role_name_to_toggle)

        if role is None:
          await message.channel.send(
              f"❌ Server me **{role_name_to_toggle}** role nahi mila!"
          )
          return

        if role in target_member.roles:
          await target_member.remove_roles(role)
          embed = discord.Embed(
              title="❌ Role Removed",
              description=(
                  f"Successfully removed {role.mention} from"
                  f" {target_member.mention}."
              ),
              color=discord.Color.red(),
          )
        else:
          await target_member.add_roles(role)
          embed = discord.Embed(
              title="✅ Role Added",
              description=(
                  f"Successfully gave {role.mention} to {target_member.mention}."
              ),
              color=discord.Color.green(),
          )

        embed.set_thumbnail(url=CAT_IMAGE_URL)
        embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
        await message.channel.send(embed=embed)
    except Exception as e:
      await message.channel.send(f"❌ Error: {e}")

  await bot.process_commands(message)
# ==========================================
# WORKING REMOVE WARN COMMAND (.rwarn)
# ==========================================


@bot.command(name="rwarn", aliases=["removewarn", "delwarn"])
@commands.has_permissions(manage_messages=True)
async def remove_warning(
    ctx, member: discord.Member, warning_id: str = None
):
  if not warning_id:
    embed = discord.Embed(
        title="❌ Invalid Usage",
        description=(
            "Kripya warning ID dein!\n**Usage:** `.rwarn @user 101` (ya `#101`)"
        ),
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
    return

  # '#' hata kar clean ID aur integer bana lo taaki match ho sake
  clean_id_str = warning_id.replace("#", "").strip()
  if not clean_id_str.isdigit():
    return await ctx.send("❌ Warning ID sirf numbers me honi chahiye!")

  target_warn_id = int(clean_id_str)
  guild_id = ctx.guild.id
  user_id = member.id

  # Check karo ki server aur user ki warnings exist karti hain ya nahi
  if (
      guild_id not in user_warns
      or user_id not in user_warns[guild_id]
      or not user_warns[guild_id][user_id]
  ):
    return await ctx.send(
        f"❌ {member.mention} ke pas koi warnings nahi hain!"
    )

  # List me se us ID wali warning ko dhoond kar remove karo
  user_warnings_list = user_warns[guild_id][user_id]
  found_warning = None
  for w in user_warnings_list:
    if w["id"] == target_warn_id:
      found_warning = w
      break

  if not found_warning:
    return await ctx.send(
        f"❌ #{target_warn_id} ID wali warning nahi mili is user ke pas!"
    )

  # Asli deletion yahan ho rahi hai database se
  user_warnings_list.remove(found_warning)

  # Success Embed
  embed = discord.Embed(
      title="✅ Warning Removed Successfully",
      description=(
          f"Successfully deleted warning ID **#{target_warn_id}** from"
          f" {member.mention}."
      ),
      color=discord.Color.green(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZSUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed)

@bot.event
async def on_message(message):
  if message.author.bot:
    await bot.process_commands(message)
    return
# ==========================================
# DYNAMIC BIND SYSTEM (ADD BIND FROM DISCORD)
# ==========================================

dynamic_role_binds = {}


@bot.tree.command(
    name="addbindrole", description="Add a new custom role bind keyword"
)
@app_commands.describe(
    keyword="The shortcut word (e.g. dm)", role_name="The exact Discord role name"
)
@commands.has_permissions(manage_roles=True)
async def addbindrole(
    interaction: discord.Interaction, keyword: str, role_name: str
):
  clean_key = keyword.lower().strip()
  dynamic_role_binds[clean_key] = role_name
  embed = discord.Embed(
      title="✅ New Bind Added!",
      description=(
          f"Successfully bound keyword **`{clean_key}`** to role"
          f" **{role_name}**!"
      ),
      color=discord.Color.green(),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_message(message):
  if message.author.bot:
    await bot.process_commands(message)
    return

  msg_content = message.content.strip().lower()
  role_name_to_toggle = None

  if msg_content == "tcm":
    role_name_to_toggle = "TRIAL CHAT MOD"
  elif msg_content == "cm":
    role_name_to_toggle = "CHAT MOD"
  elif msg_content == "og":
    role_name_to_toggle = "OGz"
  elif msg_content == "lm":
    role_name_to_toggle = "LOUNGE MOD"
  elif msg_content in dynamic_role_binds:
    role_name_to_toggle = dynamic_role_binds[msg_content]

  if role_name_to_toggle and message.reference:
    try:
      referenced_msg = await message.channel.fetch_message(
          message.reference.message_id
      )
      target_member = referenced_msg.author
      if isinstance(target_member, discord.Member):
        role = discord.utils.get(message.guild.roles, name=role_name_to_toggle)
        if role is None:
          await message.channel.send(
              f"❌ Server me **{role_name_to_toggle}** role nahi mila!"
          )
          return

        if role in target_member.roles:
          await target_member.remove_roles(role)
          embed = discord.Embed(
              title="❌ Role Removed",
              description=(
                  f"Successfully removed {role.mention} from"
                  f" {target_member.mention}."
              ),
              color=discord.Color.red(),
          )
        else:
          await target_member.add_roles(role)
          embed = discord.Embed(
              title="✅ Role Added",
              description=(
                  f"Successfully gave {role.mention} to {target_member.mention}."
              ),
              color=discord.Color.green(),
          )

        embed.set_thumbnail(url=CAT_IMAGE_URL)
        embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
        await message.channel.send(embed=embed)
    except Exception as e:
      await message.channel.send(f"❌ Error: {e}")

  await bot.process_commands(message)
# ==========================================
# STFU COMMAND (TIMEOUT WITH CUSTOM EMBED)
# ==========================================

import datetime


@bot.command(name="stfu")
@commands.has_permissions(moderate_members=True)
async def stfu_command(
    ctx, member: discord.Member, duration_str: str = "1h", *, reason="ntg"
):
  # Time conversion (s, m, h, d)
  seconds = 0
  if duration_str.endswith("s"):
    seconds = int(duration_str[:-1])
  elif duration_str.endswith("m"):
    seconds = int(duration_str[:-1]) * 60
  elif duration_str.endswith("h"):
    seconds = int(duration_str[:-1]) * 3600
  elif duration_str.endswith("d"):
    seconds = int(duration_str[:-1]) * 86400
  else:
    # Agar sirf number diya ho toh minutes maan lo
    try:
      seconds = int(duration_str) * 60
      duration_str = f"{duration_str}m"
    except:
      seconds = 3600  # Default 1 hour
      duration_str = "1h"

  timeout_duration = datetime.timedelta(seconds=seconds)
  expires_time = datetime.datetime.now(datetime.timezone.utc) + timeout_duration

  try:
    await member.timeout(timeout_duration, reason=reason)
  except Exception as e:
    return await ctx.send(f"❌ Timeout lagane me error aaya: {e}")

  embed = discord.Embed(
      title="🔨 Moderation\nAction — STFU 🤫", color=discord.Color.orange()
  )
  embed.add_field(
      name="👤 Target",
      value=f"{member.mention}\n(`{member.id}`)",
      inline=False,
  )
  embed.add_field(
      name="🛡️ Moderator",
      value=f"{ctx.author.mention}\n(`{ctx.author.id}`)",
      inline=False,
  )
  embed.add_field(name="📋 Reason", value=reason, inline=False)
  embed.add_field(name="⏱️ Duration", value=duration_str, inline=False)
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")

  await ctx.send(embed=embed)
# ==========================================
# AUTO / TEST MESSAGE SYSTEM WITH EMOJI
# ==========================================

import random
from discord.ext import tasks

# Bot ke random idle messages ki list (wahi desi style)
IDLE_MESSAGES = [
    "betiii choddddd koi use kyu nah kar raha mera madarchoddoodd log 🐸",
    "bhai koi toh command chala lo, akela betha hu yahan 😭",
    "zinda ho ya sab mar gaye? koi toh kuch bolo bc 👀",
]


@bot.tree.command(
    name="testmessage", description="Test the bot's custom idle/funny message"
)
@commands.has_permissions(manage_messages=True)
async def test_message(interaction: discord.Interaction):
  selected_msg = random.choice(IDLE_MESSAGES)
  await interaction.response.send_message(selected_msg)


# Background loop jo thodi-thodi der me (jaise 30 minutes me) check karega
@tasks.loop(minutes=30)
async def send_auto_idle_message():
  # Yahan apni us channel ki ID daal dena jahan bot ko aisi baatein karni hain
  # Ya phir bot jis bhi pehle text channel me mile wahan bhej dega
  for guild in bot.guilds:
    for channel in guild.text_channels:
      if channel.permissions_for(guild.me).send_messages:
        selected_msg = random.choice(IDLE_MESSAGES)
        await channel.send(selected_msg)
        break  # Har server ke ek main channel me bhej kar ruk jayega


@send_auto_idle_message.before_loop
async def before_auto_message():
  await bot.wait_until_ready()


# Agar loop ko chalu rakhna hai toh on_ready me 'send_auto_idle_message.start()' likhna padega
# Jo ki niche add kar diya gaya hai.
  # on_ready ke andar yeh line dal dena:
  if not send_auto_idle_message.is_running():
    send_auto_idle_message.start()
# ==========================================
# TEST MESSAGE COMMAND (!testmessage)
# ==========================================

import random

IDLE_MESSAGES = [
    "betiii choddddd koi use kyu nah kar raha mera madarchoddoodd log 🐸",
    "bhai koi toh command chala lo, akela betha hu yahan 😭",
    "zinda ho ya sab mar gaye? koi toh kuch bolo bc 👀",
]


@bot.command(name="testmessage")
async def test_message(ctx):
  selected_msg = random.choice(IDLE_MESSAGES)
  await ctx.send(selected_msg)
# ==========================================
# WORKING CUSTOM ROLE COMMANDS SYSTEM
# ==========================================

# Server wise custom commands store karne ke liye dictionary
server_custom_commands = (
    {}
)  # guild_id -> {cmd_name: {"role_id": ..., "allowed_role_id": ...}}


class CreateCommandModal(discord.ui.Modal, title="Create Custom Command"):
  cmd_name = discord.ui.TextInput(
      label="Command Name (jaise: vip ya giveowner)",
      placeholder="jaise: vip",
      max_length=20,
  )
  role_id = discord.ui.TextInput(
      label="Role ID to GIVE (jo role dena hai)",
      placeholder="Role ki numeric ID daalein",
  )
  allowed_role_id = discord.ui.TextInput(
      label="Allowed Role ID (kaun use kar sakta hai)",
      placeholder="Staff role ki ID daalein",
  )

  async def on_submit(self, interaction: discord.Interaction):
    guild_id = interaction.guild.id
    name = self.cmd_name.value.strip().lower()

    try:
      r_id = int(self.role_id.value.strip())
      a_id = int(self.allowed_role_id.value.strip())
    except ValueError:
      return await interaction.response.send_message(
          "❌ Role ID aur Allowed Role ID sirf numbers me honi chahiye!",
          ephemeral=True,
      )

    if guild_id not in server_custom_commands:
      server_custom_commands[guild_id] = {}

    server_custom_commands[guild_id][name] = {
        "role_id": r_id,
        "allowed_role_id": a_id,
    }

    embed = discord.Embed(
        title="✅ Custom Command Created!",
        description=(
            f"Successfully command **`.{name}`** ban chuki hai!\nJab isko"
            f" use karoge toh Role ID `{r_id}` assign hoga."
        ),
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await interaction.response.send_message(embed=embed, ephemeral=True)


class CustomPanelButtons(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="Create Command",
      style=discord.ButtonStyle.green,
      emoji="➕",
      custom_id="create_cmd_btn_real",
  )
  async def create_cmd(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.manage_roles:
      return await interaction.response.send_message(
          "❌ Administrators/Staff only.", ephemeral=True
      )
    # Form kholne ke liye Modal popup bhej rahe hain
    await interaction.response.send_modal(CreateCommandModal())

  @discord.ui.button(
      label="Delete Command",
      style=discord.ButtonStyle.red,
      emoji="🗑️",
      custom_id="delete_cmd_btn_real",
  )
  async def delete_cmd(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.manage_roles:
      return await interaction.response.send_message(
          "❌ Administrators only.", ephemeral=True
      )
    await interaction.response.send_message(
        "🗑️ Kisi command ko hatane ke liye code me update kar sakte ho bhai.",
        ephemeral=True,
    )

  @discord.ui.button(
      label="List Commands",
      style=discord.ButtonStyle.secondary,
      emoji="📋",
      custom_id="list_cmd_btn_real",
  )
  async def list_cmd(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    guild_id = interaction.guild.id
    commands_dict = server_custom_commands.get(guild_id, {})

    if not commands_dict:
      desc = "Is server par abhi koi custom command nahi bani hai."
    else:
      desc = "\n".join(
          [
              f"• **`.{cmd}`** (Give Role ID: `{info['role_id']}`)"
              for cmd, info in commands_dict.items()
          ]
      )

    embed = discord.Embed(
        title="📋 Active Custom Commands",
        description=desc,
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.command(name="custom", aliases=["customroles", "custam"])
@commands.has_permissions(manage_roles=True)
async def custom_panel(ctx):
  embed = discord.Embed(
      title="🛠️ Custom Role Commands Panel",
      description=(
          "Create commands that let specific roles give other roles!\n\n"
          "➕ **Create Command:** Click karke pop-up form bharein.\n"
          "🗑️ **Delete Command:** Remove an existing command.\n"
          "📋 **List Commands:** View all custom commands on this server."
      ),
      color=discord.Color.from_rgb(40, 45, 55),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")

  view = CustomPanelButtons()
  await ctx.send(embed=embed, view=view)


# Yeh message listener check karega jab koi custom command chalayega
@bot.event
async def on_message(message):
  if message.author.bot:
    await bot.process_commands(message)
    return

  guild_id = message.guild.id if message.guild else None
  if guild_id and guild_id in server_custom_commands:
    # Check karo agar message '.' se start ho raha hai
    if message.content.startswith("."):
      parts = message.content[1:].strip().split()
      if parts:
        cmd_name = parts[0].lower()
        if cmd_name in server_custom_commands[guild_id]:
          cmd_data = server_custom_commands[guild_id][cmd_name]
          target_role_id = cmd_data["role_id"]
          allowed_role_id = cmd_data["allowed_role_id"]

          # Check karo ki message bhejne wale ke paas allowed role hai ya nahi
          author_role_ids = [r.id for r in message.author.roles]
          if (
              allowed_role_id not in author_role_ids
              and not message.author.guild_permissions.administrator
          ):
            await message.channel.send(
                "❌ Aapke paas yeh custom command use karne ki permission nahi"
                " hai!"
            )
            return

          # Target member dhoondo (reply karke ya mention karke)
          target_member = None
          if message.reference:
            try:
              ref_msg = await message.channel.fetch_message(
                  message.reference.message_id
              )
              target_member = ref_msg.author
            except:
              pass
          elif message.mentions:
            target_member = message.mentions[0]

          if not target_member or not isinstance(target_member, discord.Member):
            await message.channel.send(
                "❌ Kripya kisi user ko mention karein ya uske message par reply"
                " karein!"
            )
            return

          role = message.guild.get_role(target_role_id)
          if not role:
            await message.channel.send("❌ Jo role dena hai woh server me nahi mila!")
            return

          # Role toggle karo (do toh hata do, nahi hai toh de do)
          if role in target_member.roles:
            await target_member.remove_roles(role)
            embed = discord.Embed(
                title="❌ Custom Role Removed",
                description=(
                    f"Successfully removed {role.mention} from"
                    f" {target_member.mention}."
                ),
                color=discord.Color.red(),
            )
          else:
            await target_member.add_roles(role)
            embed = discord.Embed(
                title="✅ Custom Role Added",
                description=(
                    f"Successfully gave {role.mention} to {target_member.mention}."
                ),
                color=discord.Color.green(),
            )

          embed.set_thumbnail(url=CAT_IMAGE_URL)
          embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
          await message.channel.send(embed=embed)
          return

  await bot.process_commands(message)
# ==========================================
# CUSTOM PERMISSION DENIED EMBED FUNCTION
# ==========================================


async def send_permission_denied(ctx):
  embed = discord.Embed(
      title="❌ Permission Denied",
      description=(
          f"{ctx.author.mention} you don't have permissions do RR to Mueez"
          " for permissions"
      ),
      color=discord.Color.red(),
  )
  # Agar cat thumbnail aur footer bhi chahiye toh yeh unke sath aayega:
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
  await ctx.send(embed=embed)
@bot.command(name="kisi_bhi_command_ka_naam")
async def sample_command(ctx):
  # Agar user ke paas manage_messages permission nahi hai:
  if not ctx.author.guild_permissions.manage_messages:
    await send_permission_denied(ctx)
    return

  # Baaki ka command ka code yahan aayega...
  await ctx.send("Command successfully chal gayi!")
# ==========================================
# GLOBAL COMMAND ERROR HANDLER (MISSING ARGUMENT)
# ==========================================


@bot.event
async def on_command_error(ctx, error):
  # Agar koi command nahi milti (command not found), toh ignore kar do
  if isinstance(error, commands.CommandNotFound):
    return

  # Agar missing argument (jaise member ya reason bhul gaya) error aata hai:
  if isinstance(error, commands.MissingRequiredArgument):
    cmd_name = ctx.command.name if ctx.command else "command"

    embed = discord.Embed(
        title="❌ Missing Argument",
        description=(
            f"**{ctx.author.display_name} PUT THE REASON (or missing"
            " argument)**\n\n"
            f"You missed a required argument: `{error.param.name}`\n"
            f"**Usage:** `.{cmd_name} <{error.param.name}>`\n*(Make sure"
            " you provided all required arguments!)*"
        ),
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
    return

  # Agar permission nahi hai:
  if isinstance(error, commands.MissingPermissions):
    embed = discord.Embed(
        title="❌ Permission Denied",
        description=(
            f"{ctx.author.mention} you don't have permissions do RR to Mueez"
            " for permissions"
        ),
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await ctx.send(embed=embed)
    return
# ==========================================
# CUSTOM PUNISH COMMANDS PANEL & SYSTEM
# ==========================================

# Server wise custom punish commands store karne ke liye
server_punish_commands = (
    {}
)  # guild_id -> {cmd_name: {"action": "timeout/ban", "allowed_role_id": ...}}


class CreatePunishModal(discord.ui.Modal, title="Create Custom Punish Command"):
  cmd_name = discord.ui.TextInput(
      label="Command Name (jaise: suiii ya smash)",
      placeholder="jaise: suiii",
      max_length=20,
  )
  action_type = discord.ui.TextInput(
      label="Action Type (timeout ya ban)", placeholder="timeout ya ban likhein"
  )
  allowed_role_id = discord.ui.TextInput(
      label="Allowed Role ID (kaun use kar sakta hai)",
      placeholder="Staff role ki ID daalein",
  )

  async def on_submit(self, interaction: discord.Interaction):
    guild_id = interaction.guild.id
    name = self.cmd_name.value.strip().lower()
    action = self.action_type.value.strip().lower()

    if action not in ["timeout", "ban"]:
      return await interaction.response.send_message(
          "❌ Action type sirf `timeout` ya `ban` ho sakta hai!", ephemeral=True
      )

    try:
      a_id = int(self.allowed_role_id.value.strip())
    except ValueError:
      return await interaction.response.send_message(
          "❌ Allowed Role ID sirf numbers me honi chahiye!", ephemeral=True
      )

    if guild_id not in server_punish_commands:
      server_punish_commands[guild_id] = {}

    server_punish_commands[guild_id][name] = {
        "action": action,
        "allowed_role_id": a_id,
    }

    embed = discord.Embed(
        title="✅ Custom Punish Command Created!",
        description=(
            f"Successfully command **`.{name}`** ban chuki hai!\nAction:"
            f" `{action}`"
        ),
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await interaction.response.send_message(embed=embed, ephemeral=True)


class PunishPanelButtons(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="Create Punish Cmd",
      style=discord.ButtonStyle.green,
      emoji="➕",
      custom_id="create_punish_btn",
  )
  async def create_cmd(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      return await interaction.response.send_message(
          "❌ Administrators only.", ephemeral=True
      )
    await interaction.response.send_modal(CreatePunishModal())

  @discord.ui.button(
      label="Delete Punish Cmd",
      style=discord.ButtonStyle.red,
      emoji="🗑️",
      custom_id="delete_punish_btn",
  )
  async def delete_cmd(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      return await interaction.response.send_message(
          "❌ Administrators only.", ephemeral=True
      )
    await interaction.response.send_message(
        "🗑️ Kisi command ko hatane ke liye list dekh kar code se manage kar"
        " sakte ho bhai.",
        ephemeral=True,
    )

  @discord.ui.button(
      label="List Punish Cmds",
      style=discord.ButtonStyle.secondary,
      emoji="📋",
      custom_id="list_punish_btn",
  )
  async def list_cmd(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    guild_id = interaction.guild.id
    commands_dict = server_punish_commands.get(guild_id, {})

    if not commands_dict:
      desc = "Is server par abhi koi custom punish command nahi bani hai."
    else:
      desc = "\n".join(
          [
              f"• **`.{cmd}`** (Action: `{info['action']}`)"
              for cmd, info in commands_dict.items()
          ]
      )

    embed = discord.Embed(
        title="📋 Active Custom Punish Commands",
        description=desc,
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=CAT_IMAGE_URL)
    embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.command(name="custampunish", aliases=["punishpanel"])
@commands.has_permissions(administrator=True)
async def custampunish_panel(ctx):
  embed = discord.Embed(
      title="🔨 Custom Punish Commands Panel",
      description=(
          "Create custom punishment commands directly from Discord!\n\n"
          "➕ **Create Punish Cmd:** Click karke pop-up form bharein.\n"
          "🗑️ **Delete Punish Cmd:** Remove an existing command.\n"
          "📋 **List Punish Cmds:** View all active punish commands."
      ),
      color=discord.Color.from_rgb(40, 45, 55),
  )
  embed.set_thumbnail(url=CAT_IMAGE_URL)
  embed.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")

  view = PunishPanelButtons()
  await ctx.send(embed=embed, view=view)


# Message listener jo custom punish commands ko execute karega aur Missing Argument handle karega
@bot.event
async def on_message(message):
  if message.author.bot:
    await bot.process_commands(message)
    return

  guild_id = message.guild.id if message.guild else None
  if guild_id and guild_id in server_punish_commands:
    if message.content.startswith("."):
      parts = message.content[1:].strip().split()
      if parts:
        cmd_name = parts[0].lower()
        if cmd_name in server_punish_commands[guild_id]:
          cmd_data = server_punish_commands[guild_id][cmd_name]
          action_type = cmd_data["action"]
          allowed_role_id = cmd_data["allowed_role_id"]

          # Permission Check (Agar user ke paas allowed role ya admin nahi hai)
          author_role_ids = [r.id for r in message.author.roles]
          if (
              allowed_role_id not in author_role_ids
              and not message.author.guild_permissions.administrator
          ):
            embed_perm = discord.Embed(
                title="❌ Permission Denied",
                description=(
                    f"{message.author.mention} you don't have permissions do RR"
                    " to Mueez for permissions"
                ),
                color=discord.Color.red(),
            )
            embed_perm.set_thumbnail(url=CAT_IMAGE_URL)
            embed_perm.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
            await message.channel.send(embed=embed_perm)
            return

          # Missing Argument Check (Agar user mention karna bhul gaya)
          if len(parts) < 2 or not message.mentions:
            embed_err = discord.Embed(
                title="❌ Missing Argument",
                description=(
                    f"**{message.author.display_name} PUT THE REASON (or missing"
                    " argument)**\n\n"
                    f"You missed a required argument: `user`\n"
                    f"**Format:** `.{cmd_name} @user <reason>`\n*(Make sure you"
                    " provided all required arguments!)*"
                ),
                color=discord.Color.red(),
            )
            embed_err.set_thumbnail(url=CAT_IMAGE_URL)
            embed_err.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
            await message.channel.send(embed=embed_err)
            return

          target_member = message.mentions[0]
          reason = (
              " ".join(parts[2:]) if len(parts) > 2 else "No reason provided"
          )

          try:
            if action_type == "ban":
              await target_member.ban(reason=reason)
              action_title = "🔨 Banned Member"
              action_desc = f"Successfully banned {target_member.mention} for: `{reason}`"
            else:
              # Default timeout for 1 hour agar duration na ho
              import datetime

              await target_member.timeout(
                  datetime.timedelta(hours=1), reason=reason
              )
              action_title = "⏰ Timeout Member"
              action_desc = f"Successfully timed out {target_member.mention} for: `{reason}`"

            embed_success = discord.Embed(
                title=action_title,
                description=action_desc,
                color=discord.Color.green(),
            )
            embed_success.set_thumbnail(url=CAT_IMAGE_URL)
            embed_success.set_footer(text="MUEEZ SUPPORT • Made by Cutie Mueez")
            await message.channel.send(embed=embed_success)
          except Exception as e:
            await message.channel.send(f"❌ Error execution me: {e}")
          return

  await bot.process_commands(message)
# --- Professional Management Command Suite ---

# Apni Management Team ke role ki ID yahan daal do (jiske paas yeh powers hongi)
MANAGEMENT_ROLE_ID = 1540741369855746200 # Wahi role ID jo tumne pehle di thi

@bot.group(name="mgm", invoke_without_command=True)
async def mgm(ctx):
    # Check karega ki user ke paas Management role hai ya nahi
    role = ctx.guild.get_role(MANAGEMENT_ROLE_ID)
    if not role or role not in ctx.author.roles:
        await ctx.send("❌ Is command ko use karne ke liye aapke paas **Management Team** role hona zaroori hai!", delete_after=5)
        return

    embed = discord.Embed(
        title="⚡ SHADOWZ MANAGEMENT CONTROL CENTER",
        description="Management team ke liye exclusive command panel. Niche di gayi commands ka istemal karein:",
        color=discord.Color.dark_embed()
    )
    embed.add_field(name="`!mgm broadcast <message>`", value="Sabhi members ko official management announcement bhejne ke liye.", inline=False)
    embed.add_field(name="`!mgm lockdown`", value="Emergency me current channel ko temporarily lock karne ke liye.", inline=False)
    embed.add_field(name="`!mgm stats`", value="Server ki total activity aur members ka overview dekhne ke liye.", inline=False)
    embed.set_footer(text="SHADOWZ MANAGEMENT • Elite Security")
    await ctx.send(embed=embed)

# 1. Broadcast Command (Professional Announcement)
@mgm.command(name="broadcast")
async def mgm_broadcast(ctx, *, message: str):
    role = ctx.guild.get_role(MANAGEMENT_ROLE_ID)
    if not role or role not in ctx.author.roles:
        return

    await ctx.message.delete() # User ka command message delete kar dega taaki clean lage
    
    embed = discord.Embed(
        title="📢 OFFICIAL MANAGEMENT ANNOUNCEMENT",
        description=message,
        color=discord.Color.gold()
    )
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="SHADOWZ MANAGEMENT SYSTEM")
    await ctx.send(embed=embed)

# 2. Server Stats Command (Professional Overview)
@mgm.command(name="stats")
async def mgm_stats(ctx):
    role = ctx.guild.get_role(MANAGEMENT_ROLE_ID)
    if not role or role not in ctx.author.roles:
        return

    guild = ctx.guild
    embed = discord.Embed(title=f"📊 {guild.name} - Management Overview", color=discord.Color.blurple())
    embed.add_field(name="👥 Total Members", value=guild.member_count, inline=True)
    embed.add_field(name="💬 Text Channels", value=len(guild.text_channels), inline=True)
    embed.add_field(name="🔊 Voice Channels", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="👑 Server Owner", value=guild.owner.mention, inline=False)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

# 3. Lockdown Command (Channel Secure karne ke liye)
@mgm.command(name="lockdown")
async def mgm_lockdown(ctx):
    role = ctx.guild.get_role(MANAGEMENT_ROLE_ID)
    if not role or role not in ctx.author.roles:
        return

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    if overwrite.send_messages is False:
        overwrite.send_messages = None
        status = "🔓 Channel unlock kar diya gaya hai."
    else:
        overwrite.send_messages = False
        status = "🔒 Channel lockdown kar diya gaya hai! Ab koi message nahi bhej sakega."

    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(status)
# ---------------------------------------------
# --- SHADOWZ Automatic Tracker & Management System ---
MOD_STATS = {}

# Yeh event automatically tumhare purane .warn aur .jail commands ko track kar lega
@bot.event
async def on_command_completion(ctx):
    if not ctx.guild:
        return
        
    mod_id = ctx.author.id
    if mod_id not in MOD_STATS:
        MOD_STATS[mod_id] = {"warns": 0, "jails": 0, "details_warns": [], "details_jails": []}
        
    cmd_name = ctx.command.name.lower()
    content = ctx.message.content.strip()
    parts = content.split(" ", 2)
    
    if cmd_name == "warn":
        if ctx.message.mentions:
            target = ctx.message.mentions[0]
            reason = parts[2] if len(parts) > 2 else "Koi wajah nahi di gayi"
            MOD_STATS[mod_id]["warns"] += 1
            MOD_STATS[mod_id]["details_warns"].append(f"• Warned **{target.name}** | Reason: *{reason}*")
            
    elif cmd_name == "jail":
        if ctx.message.mentions:
            target = ctx.message.mentions[0]
            reason = parts[2] if len(parts) > 2 else "Koi wajah nahi di gayi"
            MOD_STATS[mod_id]["jails"] += 1
            MOD_STATS[mod_id]["details_jails"].append(f"• Jailed **{target.name}** | Reason: *{reason}*")

# 1. Mwarn Command (.mwarn ya .mwarn @Moderator) - History dekhne ke liye
@bot.command(name="mwarn")
async def check_mwarn(ctx, member: discord.Member = None):
    target = member or ctx.author
    mod_id = target.id
    
    if mod_id not in MOD_STATS or not MOD_STATS[mod_id]["details_warns"]:
        await ctx.send(f"❌ {target.mention} ne abhi tak kisi ko warn nahi kiya hai.")
        return
        
    history = "\n".join(MOD_STATS[mod_id]["details_warns"])
    embed = discord.Embed(
        title=f"⚠️ Warn History: {target.display_name}", 
        description=history, 
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Total Warns Given: {MOD_STATS[mod_id]['warns']}")
    await ctx.send(embed=embed)

# 2. Mjail Command (.mjail ya .mjail @Moderator) - History dekhne ke liye
@bot.command(name="mjail")
async def check_mjail(ctx, member: discord.Member = None):
    target = member or ctx.author
    mod_id = target.id
    
    if mod_id not in MOD_STATS or not MOD_STATS[mod_id]["details_jails"]:
        await ctx.send(f"❌ {target.mention} ne abhi tak kisi ko jail nahi kiya hai.")
        return
        
    history = "\n".join(MOD_STATS[mod_id]["details_jails"])
    embed = discord.Embed(
        title=f"🔒 Jail History: {target.display_name}", 
        description=history, 
        color=discord.Color.dark_red()
    )
    embed.set_footer(text=f"Total Jails Given: {MOD_STATS[mod_id]['jails']}")
    await ctx.send(embed=embed)

# 3. MLB Command (.mlb) - Leaderboard 1st se 10th tak
@bot.command(name="mlb")
async def check_mlb(ctx):
    if not MOD_STATS:
        await ctx.send("❌ Abhi tak koi moderation data record nahi hua hai.")
        return
        
    # Sort moderators by total actions (warns + jails) highest to lowest
    sorted_mods = sorted(MOD_STATS.items(), key=lambda x: x[1]["warns"] + x[1]["jails"], reverse=True)
    
    embed = discord.Embed(
        title="🏆 SHADOWZ MANAGEMENT LEADERBOARD (.mlb)", 
        description="Top Active Moderators (1st to 10th)", 
        color=discord.Color.blue()
    )
    
    for i, (mod_id, data) in enumerate(sorted_mods[:10], 1):
        user = ctx.guild.get_member(mod_id)
        name = user.display_name if user else f"User ID: {mod_id}"
        total = data["warns"] + data["jails"]
        
        field_value = f"⚠️ Warns: **{data['warns']}** | 🔒 Jails: **{data['jails']}** | **Total Actions: {total}**"
        embed.add_field(name=f"#{i} {name}", value=field_value, inline=False)
        
    embed.set_footer(text="SHADOWZ MANAGEMENT SYSTEM")
    await ctx.send(embed=embed)
# -------------------------------------------------------------
# --- Simple Custom Message System ---

# 1. Bot se jo marzi bulwane ke liye: .say <tumhara message>
@bot.command(name="say")
async def say_anything(ctx, *, text: str):
    await ctx.message.delete()  # Tera command wala message gayab ho jayega
    await ctx.send(text)        # Bot wahi boldega jo tune likha hoga

# 2. Jab koi naya member aaye toh automatic message
@bot.event
async def on_member_join(member):
    # Yahan channel set ho jayega jahan welcome message aayega
    channel = member.guild.system_channel
    if channel:
        await channel.send(f"Welcome {member.mention} bhai! 🔥 Server me aane ke liye shukriya. Maza karo!")


TOKEN = "MTU0OTc1NDA5MjI0NTQ4Nzc2OA.G1zXtO.26kwynXOzT2wgMS06sI0cgqbJTIdFd7eUqxkKw"

if __name__ == "__main__":
  bot.run(TOKEN)
