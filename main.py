import asyncio
import json
import os
import random
from easy_pil import Canvas, Editor, Font, load_image
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# .env файлаас нууц түлхүүрүүдийг ачаалах
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Discord Bot Intents тохируулга
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== DATA ХАДГАЛАХ СИСТЕМ ====================
USERS_FILE = "users_data.json"
CLANS_FILE = "clans_data.json"
TREASURY_FILE = "treasury_data.json"


def load_json(filepath, default_value):
  if os.path.exists(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
      return json.load(f)
  return default_value


def save_json(filepath, data):
  with open(filepath, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)


users = load_json(USERS_FILE, {})
clans = load_json(CLANS_FILE, {})
treasury = load_json(TREASURY_FILE, {"mayor_id": None, "total_tax": 0})


def get_user_data(user_id):
  str_id = str(user_id)
  if str_id not in users:
    users[str_id] = {
        "coins": 100,
        "exp": 0,
        "level": 1,
        "messages": 0,
        "inventory": [],
        "can_create_clan": False,
    }
    save_json(USERS_FILE, users)

  if "inventory" not in users[str_id]:
    users[str_id]["inventory"] = []
  if "can_create_clan" not in users[str_id]:
    users[str_id]["can_create_clan"] = False

  return users[str_id]


# Түвшинд тохирох ажлын байрыг тодорхойлох функц
def get_user_job(level):
  if level < 3:
    return "Худалдагч / Цэвэрлэгч 🧹"
  elif level < 6:
    return "Хоол хүргэлт / Оффисын туслах 🛵"
  elif level < 10:
    return "Программист / Дизайнер 💻"
  else:
    return "Компанийн захирал / AI Инженер 👑"


# ==================== BOT EVENT-ҮҮД ====================
@bot.event
async def on_ready():
  print(f"🎮 AIM Clan Bot амжилттай асаалаа: {bot.user.name}")
  give_voice_xp.start()


@bot.event
async def on_message(message):
  if message.author.bot:
    return

  user_data = get_user_data(message.author.id)
  user_data["messages"] += 1
  user_data["exp"] += 15

  next_level_exp = user_data["level"] * 100
  if user_data["exp"] >= next_level_exp:
    user_data["level"] += 1
    user_data["exp"] -= next_level_exp
    await message.channel.send(
        f"🎉 Баяр хүргэе {message.author.mention}! Та **Level"
        f" {user_data['level']}** боллоо!"
    )

  save_json(USERS_FILE, users)
  await bot.process_commands(message)


# ==================== VOICE CHANNEL XP ====================
@tasks.loop(minutes=10)
async def give_voice_xp():
  for guild in bot.guilds:
    for vc in guild.voice_channels:
      for member in vc.members:
        if not member.bot:
          user_data = get_user_data(member.id)
          user_data["exp"] += 50
          user_data["coins"] += 20
          save_json(USERS_FILE, users)


# ==================== PLAYER CARD (!profile) ====================
@bot.command(name="profile", aliases=["rank", "card"])
async def profile(ctx, member: discord.Member = None):
  member = member or ctx.author
  data = get_user_data(member.id)
  user_job = get_user_job(data["level"])

  try:
    background = Canvas((600, 220), color="#1e1f22")
    editor = Editor(background)

    avatar_image = await load_image.async_open(member.display_avatar.url)
    profile_avatar = Editor(avatar_image).resize((120, 120)).circle_image()
    editor.paste(profile_avatar, (30, 40))

    font_large = Font.poppins(size=22, bold=True)
    font_small = Font.poppins(size=15)

    editor.text(
        (170, 30), str(member.name), font=font_large, color="#FFFFFF"
    )
    editor.text(
        (170, 60),
        f"Level: {data['level']}  |  Coins: ${data['coins']}",
        font=font_small,
        color="#5865F2",
    )
    editor.text((170, 85), f"Ажил: {user_job}", font=font_small, color="#57F287")
    editor.text(
        (170, 110), f"Мессеж: {data['messages']}", font=font_small, color="#B5BAC1"
    )

    max_exp = data["level"] * 100
    current_exp = data["exp"]
    percentage = min(current_exp / max_exp, 1.0)

    editor.rectangle(
        (170, 150), width=380, height=20, fill="#2b2d31", radius=10
    )
    if percentage > 0:
      editor.rectangle(
          (170, 150),
          width=int(380 * percentage),
          height=20,
          fill="#5865F2",
          radius=10,
      )

    file = discord.File(fp=editor.image_bytes, filename="profile_card.png")
    await ctx.send(file=file)

  except Exception:
    embed = discord.Embed(
        title=f"👤 {member.name}-ийн Профайл", color=discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="📊 Level", value=f"Level {data['level']}", inline=True)
    embed.add_field(name="💼 Одоогийн ажил", value=user_job, inline=True)
    embed.add_field(name="💰 Коин", value=f"${data['coins']}", inline=True)
    embed.add_field(
        name="💬 Мессеж", value=f"{data['messages']} мессеж", inline=True
    )
    embed.add_field(
        name="✨ EXP",
        value=f"{data['exp']} / {data['level'] * 100}",
        inline=False,
    )
    items = ", ".join(data.get("inventory", [])) or "Хоосон"
    embed.add_field(name="🎒 Цүнх (Inventory)", value=items, inline=False)
    await ctx.send(embed=embed)


# ==================== ДЭЛГҮҮР БА ХУДАЛДАН АВАЛТ ====================
@bot.command()
async def shop(ctx):
  embed = discord.Embed(
      title="🛒 AIMZONE Дэлгүүр",
      description="Цуглуулсан коиноороо гоё зүйлс аваарай!",
      color=discord.Color.green(),
  )
  embed.add_field(
      name="1. 🛡️ Клан үүсгэх эрх (`clan`)",
      value="Үнэ: **$500** | Команд: `!buy clan`",
      inline=False,
  )
  embed.add_field(
      name="2. ⚡ Энержи ундаа (`energy`)",
      value="Үнэ: **$30** | Команд: `!buy energy`",
      inline=False,
  )
  embed.add_field(
      name="3. 🏆 VIP Роль (`vip`)",
      value="Үнэ: **$2,000** | Команд: `!buy vip`",
      inline=False,
  )
  embed.add_field(
      name="4. 👑 Pro Gamer Роль (`progamer`)",
      value="Үнэ: **$5,000** | Команд: `!buy progamer`",
      inline=False,
  )
  await ctx.send(embed=embed)


@bot.command()
async def buy(ctx, item: str):
  user_data = get_user_data(ctx.author.id)
  item = item.lower().strip()

  if item in ["clan", "клан"]:
    price = 500
    if user_data["coins"] < price:
      await ctx.send(f"❌ Танд хангалттай мөнгө байхгүй! Үнэ: **${price}**")
      return
    user_data["coins"] -= price
    user_data["can_create_clan"] = True
    save_json(USERS_FILE, users)
    await ctx.send(
        f"🎉 Баяр хүргэе {ctx.author.mention}! Та Клан үүсгэх эрх авлаа. Одоо"
        " `!createclan [Нэр]` гэж бичиж кланаа үүсгээрэй!"
    )

  elif item in ["energy", "энержи"]:
    price = 30
    if user_data["coins"] < price:
      await ctx.send(f"❌ Танд хангалттай мөнгө байхгүй! Үнэ: **${price}**")
      return
    user_data["coins"] -= price
    user_data["inventory"].append("⚡ Энержи ундаа")
    save_json(USERS_FILE, users)
    await ctx.send(f"⚡ {ctx.author.mention}, та Энержи ундаа худалдаж авлаа!")

  elif item == "vip":
    price = 2000
    if user_data["coins"] < price:
      await ctx.send(f"❌ Танд хангалттай мөнгө байхгүй! Үнэ: **${price}**")
      return
    user_data["coins"] -= price
    save_json(USERS_FILE, users)
    role = discord.utils.get(ctx.guild.roles, name="🔥 VIP")
    if role:
      await ctx.author.add_roles(role)
    await ctx.send(f"🎉 {ctx.author.mention}, та VIP роль авлаа!")

  elif item in ["progamer", "pro"]:
    price = 5000
    if user_data["coins"] < price:
      await ctx.send(f"❌ Танд хангалттай мөнгө байхгүй! Үнэ: **${price}**")
      return
    user_data["coins"] -= price
    save_json(USERS_FILE, users)
    role = discord.utils.get(ctx.guild.roles, name="👑 Pro Gamer")
    if role:
      await ctx.author.add_roles(role)
    await ctx.send(f"🎉 {ctx.author.mention}, та Pro Gamer роль авлаа!")

  else:
    await ctx.send("❌ Ийм бараа дэлгүүрт байхгүй байна! `!shop` гэж хараарай.")


# ==================== АЖИЛ БА ДЭЭРЭМ ====================
@bot.command()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work(ctx):
  user_data = get_user_data(ctx.author.id)
  user_level = user_data.get("level", 1)

  if user_level < 3:
    jobs = [
        "дэлгүүрийн худалдагч хийж",
        "өрөө болон гудамж цэвэрлэж",
        "аяга таваг угааж",
    ]
    base_min, base_max = 50, 150
  elif user_level < 6:
    jobs = [
        "хоол хүргэлтэд ажиллаж",
        "оффисын туслахаар ажиллаж",
        "кофе шопд бариста хийж",
    ]
    base_min, base_max = 150, 350
  elif user_level < 10:
    jobs = ["программист хийж", "график дизайнер хийж", "нягтлан бодогчоор ажиллаж"]
    base_min, base_max = 350, 700
  else:
    jobs = [
        "компанийн захирал (CEO) хийж",
        "хөрөнгө оруулагчаар ажиллаж",
        "AI инженер хийж",
    ]
    base_min, base_max = 700, 1500

  earned = random.randint(base_min, base_max)
  user_data["coins"] += earned
  save_json(USERS_FILE, users)

  job = random.choice(jobs)
  await ctx.send(
      f"💼 {ctx.author.mention}, та **Level {user_level}** түвшинд **{job}**"
      f" **${earned}** коин оллоо!"
  )


@work.error
async def work_error(ctx, error):
  if isinstance(error, commands.CommandOnCooldown):
    mins = int(error.retry_after // 60)
    await ctx.send(
        f"⏳ Та ядарсан байна! Дахин ажиллах хүртэл **{mins} минут** хүлээнэ үү."
    )


@bot.command()
@commands.cooldown(1, 7200, commands.BucketType.user)
async def rob(ctx, member: discord.Member):
  if member.id == ctx.author.id:
    await ctx.send("❌ Өөрийгөө дээрэмдэх боломжгүй!")
    return

  thief_data = get_user_data(ctx.author.id)
  victim_data = get_user_data(member.id)

  if victim_data["coins"] < 100:
    await ctx.send("❌ Энэ гишүүнд дээрэмдэх хангалттай мөнгө байхгүй байна!")
    return

  if thief_data["coins"] < 200:
    await ctx.send(
        "❌ Баригдвал торгууль төлөх $200 барьцаа мөнгө танд байх шаардлагатай!"
    )
    return

  success = random.random() < 0.40

  if success:
    stolen = random.randint(30, int(victim_data["coins"] * 0.3))
    victim_data["coins"] -= stolen
    thief_data["coins"] += stolen
    save_json(USERS_FILE, users)
    await ctx.send(
        f"🥷 🎉 {ctx.author.mention}, та {member.mention}-ийн хэтэвчнээс"
        f" **${stolen}** коин дээрэмдлээ!"
    )
  else:
    fine = 200
    thief_data["coins"] -= fine
    treasury["total_tax"] += fine
    save_json(USERS_FILE, users)
    save_json(TREASURY_FILE, treasury)
    await ctx.send(
        f"🚨 {ctx.author.mention}, цагдаад баригдлаа! **${fine}** торгууль төлж"
        " Хотын даргын санд орлоо."
    )


# ==================== ЭДИЙН ЗАСАГ БА ХОТЫН ДАРГА ====================
@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily(ctx):
  data = get_user_data(ctx.author.id)
  reward = 250
  data["coins"] += reward
  save_json(USERS_FILE, users)
  await ctx.send(f"🎁 {ctx.author.mention}, та өдрийн бэлэгний **${reward}** коин авлаа!")


@daily.error
async def daily_error(ctx, error):
  if isinstance(error, commands.CommandOnCooldown):
    hours = int(error.retry_after // 3600)
    minutes = int((error.retry_after % 3600) // 60)
    await ctx.send(
        f"⏳ Та өдрийн бонусаа авсан байна! Дахин автал **{hours} цаг {minutes}"
        " минут** хүлээнэ үү."
    )


@bot.command()
async def setmayor(ctx, member: discord.Member):
  treasury["mayor_id"] = str(member.id)
  save_json(TREASURY_FILE, treasury)
  await ctx.send(f"👑 **{member.mention}** амжилттай **ХОТЫН ДАРГА**-аар сонгогдлоо!")


@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
  if member.id == ctx.author.id:
    await ctx.send("❌ Та өөр рүүгээ мөнгө шилжүүлэх боломжгүй!")
    return

  if amount < 10:
    await ctx.send("❌ Хамгийн багадаа $10 шилжүүлэх боломжтой!")
    return

  sender = get_user_data(ctx.author.id)
  receiver = get_user_data(member.id)

  if sender["coins"] < amount:
    await ctx.send("❌ Танд хангалттай мөнгө байхгүй байна!")
    return

  fee = int(amount * 0.03)
  final_amount = amount - fee

  treasury["total_tax"] += fee
  save_json(TREASURY_FILE, treasury)

  if treasury["mayor_id"]:
    mayor_data = get_user_data(treasury["mayor_id"])
    mayor_data["coins"] += fee

  sender["coins"] -= amount
  receiver["coins"] += final_amount
  save_json(USERS_FILE, users)

  await ctx.send(
      f"💸 {ctx.author.mention} гишүүн {member.mention} руу **${final_amount}**"
      f" коин шилжүүллээ!\n🏛️ *(3%-ийн татвар **${fee}** Хотын дарга руу"
      " очлоо)*"
  )


@bot.command(name="treasury", aliases=["tax"])
async def show_treasury(ctx):
  mayor_id = treasury.get("mayor_id")
  mayor_name = "Тохируулаагүй"

  if mayor_id:
    try:
      mayor_user = await bot.fetch_user(int(mayor_id))
      mayor_name = mayor_user.name
    except Exception:
      mayor_name = f"ID: {mayor_id}"

  embed = discord.Embed(
      title="🏛️ AIMZONE - Хотын Даргын Сан & Татвар", color=discord.Color.blue()
  )
  embed.add_field(name="👑 Хотын Дарга", value=mayor_name, inline=False)
  embed.add_field(
      name="💰 Цугласан Татвар", value=f"${treasury['total_tax']}", inline=False
  )
  await ctx.send(embed=embed)


@bot.command()
async def grant(ctx, member: discord.Member, amount: int):
  user_id = str(ctx.author.id)
  if user_id != treasury.get("mayor_id") and not ctx.author.guild_permissions.administrator:
    await ctx.send("❌ Энэ коммандыг зөвхөн **Хотын дарга** ашиглах эрхтэй!")
    return

  mayor_data = get_user_data(user_id)
  if mayor_data["coins"] < amount or amount <= 0:
    await ctx.send("❌ Хотын даргын санд хангалттай мөнгө байхгүй байна!")
    return

  mayor_data["coins"] -= amount
  receiver_data = get_user_data(member.id)
  receiver_data["coins"] += amount
  save_json(USERS_FILE, users)

  await ctx.send(
      f"🏛️ **Хотын дарга {ctx.author.mention}** {member.mention} гишүүнд"
      f" **${amount}** коин олгож шагналаа! 🎁"
  )


# ==================== КЛАН СИСТЕМ ====================
@bot.command()
async def createclan(ctx, *, clan_name: str):
  user_id = str(ctx.author.id)
  user_data = get_user_data(user_id)

  if not user_data.get("can_create_clan", False):
    await ctx.send(
        "❌ Та Клан үүсгэх эрх аваагүй байна! Дэлгүүрээс `!buy clan` гэж"
        " аваарай ($500)."
    )
    return

  for c_name, c_info in clans.items():
    if user_id in c_info["members"]:
      await ctx.send("❌ Та аль хэдийн өөр кланы гишүүн байна!")
      return

  if clan_name in clans:
    await ctx.send("❌ Энэ нэртэй клан аль хэдийн үүссэн байна!")
    return

  user_data["can_create_clan"] = False
  clans[clan_name] = {
      "leader": user_id,
      "members": [user_id],
      "max_members": 5,
      "bank": 0,
  }
  save_json(USERS_FILE, users)
  save_json(CLANS_FILE, clans)
  await ctx.send(
      f"🛡️ **{clan_name}** клан амжилттай үүслээ! (Ахлагч: {ctx.author.mention})"
  )


@bot.command()
async def inviteclan(ctx, member: discord.Member):
  user_id = str(ctx.author.id)
  target_id = str(member.id)

  my_clan = None
  for c_name, c_info in clans.items():
    if c_info["leader"] == user_id:
      my_clan = c_name
      break

  if not my_clan:
    await ctx.send("❌ Та аль нэг кланы ахлагч биш байна!")
    return

  clan_info = clans[my_clan]
  if len(clan_info["members"]) >= clan_info["max_members"]:
    await ctx.send("❌ Танай кланы 5 хүний орон тоо дүүрсэн байна!")
    return

  if target_id in clan_info["members"]:
    await ctx.send("❌ Энэ гишүүн аль хэдийн танай кланд байна!")
    return

  clan_info["members"].append(target_id)
  save_json(CLANS_FILE, clans)
  await ctx.send(
      f"🎉 {member.mention} гишүүн **{my_clan}** кланд амжилттай нэгдлээ!"
      f" ({len(clan_info['members'])}/5)"
  )


@bot.command()
async def clan(ctx, *, clan_name: str = None):
  user_id = str(ctx.author.id)

  if not clan_name:
    for c_name, c_info in clans.items():
      if user_id in c_info["members"]:
        clan_name = c_name
        break

  if not clan_name or clan_name not in clans:
    await ctx.send("❌ Кланы мэдээлэл олдсонгүй!")
    return

  c_info = clans[clan_name]
  leader_user = await bot.fetch_user(int(c_info["leader"]))

  member_mentions = []
  for m_id in c_info["members"]:
    m_user = await bot.fetch_user(int(m_id))
    member_mentions.append(m_user.name)

  embed = discord.Embed(
      title=f"🛡️ Clan: {clan_name}", color=discord.Color.gold()
  )
  embed.add_field(name="👑 Ахлагч", value=leader_user.name, inline=True)
  embed.add_field(
      name="👥 Бүрэлдэхүүн", value=f"{len(c_info['members'])}/5", inline=True
  )
  embed.add_field(name="🏦 Банк", value=f"${c_info['bank']}", inline=True)
  embed.add_field(
      name="📜 Гишүүд", value=", ".join(member_mentions), inline=False
  )
  await ctx.send(embed=embed)


@bot.command()
async def depositclan(ctx, amount: int):
  user_id = str(ctx.author.id)
  user_data = get_user_data(user_id)

  my_clan = None
  for c_name, c_info in clans.items():
    if user_id in c_info["members"]:
      my_clan = c_name
      break

  if not my_clan:
    await ctx.send("❌ Та ямар ч кланд харьяалагдаагүй байна!")
    return

  if user_data["coins"] < amount or amount <= 0:
    await ctx.send("❌ Танд хангалттай мөнгө байхгүй байна!")
    return

  user_data["coins"] -= amount
  clans[my_clan]["bank"] += amount
  save_json(USERS_FILE, users)
  save_json(CLANS_FILE, clans)

  await ctx.send(
      f"🏦 {ctx.author.mention} **{my_clan}** кланы банк руу **${amount}**"
      " шилжүүллээ!"
  )


# ==================== МИНИ ТОГЛООМУУД ====================
@bot.command(name="cf", aliases=["coinflip"])
async def coinflip(ctx, amount: int, choice: str):
  choice = choice.lower().strip()

  if choice in ["f", "s", "sulde", "сүлдэ", "front"]:
    user_choice = "сүлдэ"
  elif choice in ["h", "t", "toon", "тоон", "heads", "tails"]:
    user_choice = "тоон"
  else:
    await ctx.send("❌ Сонголтоо зөв хийнэ үү! (`!cf 500 f` эсвэл `!cf 500 h`)")
    return

  user_data = get_user_data(ctx.author.id)
  if amount <= 0 or user_data["coins"] < amount:
    await ctx.send("❌ Хангалттай мөнгө байхгүй байна!")
    return

  result = random.choice(["сүлдэ", "тоон"])
  if user_choice == result:
    win_amount = amount * 2
    user_data["coins"] += amount
    save_json(USERS_FILE, users)
    await ctx.send(
        f"🪙 Зоос буулаа: **{result.upper()}**!\n🎉 Баяр хүргэе"
        f" {ctx.author.mention}, та хожиж **${win_amount}** коин авлаа!"
    )
  else:
    user_data["coins"] -= amount
    save_json(USERS_FILE, users)
    await ctx.send(
        f"🪙 Зоос буулаа: **{result.upper()}**!\n💸 Харамсалтай нь"
        f" {ctx.author.mention}, та ялагдаж **${amount}** коиноо алдлаа."
    )


@bot.command(name="slots", aliases=["slot"])
async def slots(ctx, amount: int):
  user_data = get_user_data(ctx.author.id)
  if amount <= 0 or user_data["coins"] < amount:
    await ctx.send("❌ Хангалттай мөнгө байхгүй байна!")
    return

  emojis = ["🍎", "🔔", "🍋", "💎", "🎰", "7️⃣"]
  slot1, slot2, slot3 = (
      random.choice(emojis),
      random.choice(emojis),
      random.choice(emojis),
  )

  msg = await ctx.send(
      f"🎰 **[ 🔄 | 🔄 | 🔄 ]**\n{ctx.author.mention} слот ажиллуулж байна..."
  )
  await asyncio.sleep(1)
  await msg.edit(
      content=(
          f"🎰 **[ {slot1} | {slot2} | {slot3} ]**\n{ctx.author.mention} слот"
          " эргэлдлээ!"
      )
  )

  if slot1 == slot2 == slot3:
    win_amount = amount * 5
    user_data["coins"] += win_amount - amount
    save_json(USERS_FILE, users)
    await ctx.send(f"🔥 **JACKPOT!** Та **${win_amount}** коин авлаа!")
  elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
    win_amount = amount * 2
    user_data["coins"] += amount
    save_json(USERS_FILE, users)
    await ctx.send(f"🎉 **2 ижил буулаа!** Та **${win_amount}** коин авлаа!")
  else:
    user_data["coins"] -= amount
    save_json(USERS_FILE, users)
    await ctx.send(f"💸 Ялагдлаа! Та **${amount}** коин алдлаа.")


@bot.command(name="top", aliases=["leaderboard", "lb"])
async def leaderboard(ctx):
  if not users:
    await ctx.send("Одоогоор ямар ч дата байхгүй байна.")
    return

  sorted_users = sorted(
      users.items(),
      key=lambda x: (x[1].get("level", 1), x[1].get("exp", 0)),
      reverse=True,
  )[:10]
  embed = discord.Embed(
      title="🏆 AIMZONE - Шилдэг 10 Тоглогч", color=discord.Color.gold()
  )

  medals = ["🥇", "🥈", "🥉"]
  for idx, (user_id, data) in enumerate(sorted_users, start=1):
    try:
      member = await bot.fetch_user(int(user_id))
      name = member.name
    except Exception:
      name = f"Хэрэглэгч ({user_id})"

    prefix = medals[idx - 1] if idx <= 3 else f"**#{idx}**"
    embed.add_field(
        name=f"{prefix} {name}",
        value=(
            f"📊 Level: **{data.get('level', 1)}** | 💰 Coins:"
            f" **${data.get('coins', 0)}**"
        ),
        inline=False,
    )

  await ctx.send(embed=embed)


# ==================== БОСС ТУЛААН ====================
boss_data = {"hp": 0, "max_hp": 0, "is_alive": False, "participants": []}


@bot.command(name="boss")
async def boss(ctx, action: str = "attack"):
  global boss_data

  if action.lower() == "spawn":
    if boss_data["is_alive"]:
      await ctx.send(
          f"⚠️ Аль хэдийн Босс амилсан байна! (HP:"
          f" **{boss_data['hp']}/{boss_data['max_hp']}**)"
      )
      return

    boss_data = {"hp": 1000, "max_hp": 1000, "is_alive": True, "participants": []}
    embed = discord.Embed(
        title="👹 ДОМОГТ БОСС АМИЛЛАА!",
        description="`!boss` гэж бичиж довтолно уу.",
        color=discord.Color.red