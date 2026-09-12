import discord
from discord.ext import commands


# =========================================================
# 기본 설정
# =========================================================

import os
import json
import asyncio
import re
from html import unescape
from urllib.parse import urljoin

import aiohttp
from html.parser import HTMLParser

TOKEN = os.getenv("DISCORD_TOKEN", "")

GUILD_ID = 1517933702146166784

# =========================================================
# 블루 아카이브 공지 자동 알림
# =========================================================

NOTICE_CONFIG_FILE = "notice_config.json"
NOTICE_CHECK_INTERVAL = 300  # 5분마다 확인

KR_NOTICE_URL = "https://forum.nexon.com/bluearchive/board_list?board=1018"
JP_NOTICE_URL = "https://bluearchive.jp/news"

notice_cache = {"kr": "", "jp": ""}
notice_task = None


def load_notice_config():
    try:
        with open(NOTICE_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"channel_id": None}


def save_notice_config(config):
    with open(NOTICE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


notice_config = load_notice_config()
if os.getenv("NOTICE_CHANNEL_ID"):
    notice_config["channel_id"] = int(os.getenv("NOTICE_CHANNEL_ID"))


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            self.current_href = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href is not None:
            text = " ".join("".join(self.current_text).split())
            self.links.append((self.current_href, unescape(text)))
            self.current_href = None
            self.current_text = []


async def fetch_text(session, url):
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=20),
        headers={"User-Agent": "Mozilla/5.0 FGTC-NoticeBot/1.0"},
    ) as response:
        response.raise_for_status()
        return await response.text()


def find_kr_notice(html):
    parser = LinkParser()
    parser.feed(html)

    candidates = []
    for href, title in parser.links:
        if not href or not title:
            continue
        if "board_view" in href and "thread=" in href:
            full_url = urljoin(KR_NOTICE_URL, href)
            candidates.append((full_url, title))

    # 중복 제거
    seen = set()
    result = []
    for url, title in candidates:
        if url not in seen:
            seen.add(url)
            result.append((url, title))

    return result[0] if result else None


def find_jp_notice(html):
    parser = LinkParser()
    parser.feed(html)

    candidates = []
    for href, title in parser.links:
        if not href or not title:
            continue
        if "/news/newsJump/" in href:
            full_url = urljoin(JP_NOTICE_URL, href)
            candidates.append((full_url, title))

    seen = set()
    result = []
    for url, title in candidates:
        if url not in seen:
            seen.add(url)
            result.append((url, title))

    return result[0] if result else None


async def post_notice(source, title, url):
    channel_id = notice_config.get("channel_id")
    if not channel_id:
        return

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        print(f"[공지] 채널을 찾을 수 없습니다: {channel_id}")
        return

    if source == "kr":
        label = "🇰🇷 블루 아카이브 한국 공지"
    else:
        label = "🇯🇵 ブルーアーカイブ 일본 공지"

    embed = discord.Embed(
        title=title[:256],
        url=url,
        description=f"새로운 공식 공지가 등록되었습니다.\n\n{url}",
    )
    embed.set_footer(text=label)

    try:
        await channel.send(embed=embed)
        print(f"[공지] 전송 완료: {label} / {title}")
    except discord.Forbidden:
        print("[공지] 해당 채널에 메시지를 보낼 권한이 없습니다.")
    except Exception as e:
        print(f"[공지] 전송 실패: {e}")


async def notice_loop():
    global notice_cache

    await bot.wait_until_ready()

    async with aiohttp.ClientSession() as session:
        # 첫 실행에서는 현재 최신 공지를 기억만 하고, 과거 공지를 한꺼번에 보내지 않음
        first_run = True

        while not bot.is_closed():
            try:
                kr_html = await fetch_text(session, KR_NOTICE_URL)
                jp_html = await fetch_text(session, JP_NOTICE_URL)

                kr = find_kr_notice(kr_html)
                jp = find_jp_notice(jp_html)

                if first_run:
                    notice_cache["kr"] = kr[0] if kr else ""
                    notice_cache["jp"] = jp[0] if jp else ""
                    first_run = False
                else:
                    if kr and kr[0] != notice_cache["kr"]:
                        notice_cache["kr"] = kr[0]
                        await post_notice("kr", kr[1], kr[0])

                    if jp and jp[0] != notice_cache["jp"]:
                        notice_cache["jp"] = jp[0]
                        await post_notice("jp", jp[1], jp[0])

            except Exception as e:
                print(f"[공지] 확인 중 오류: {e}")

            await asyncio.sleep(NOTICE_CHECK_INTERVAL)

# 인증 회원 역할
VERIFIED_ROLE_ID = 1517944396446830693


# =========================================================
# 학원 역할 ID
# =========================================================

FACTION_ROLES = {
    "아비도스 고등학교": 1517944653737885828,
    "게헨나 학원": 1517944772042559528,
    "밀레니엄 사이언스 스쿨": 1517944730145521725,
    "트리니티 종합학원": 1517944606182871172,
    "백귀야행 연합학원": 1517944904008073236,
    "산해경 고급중학교": 1517944854108176548,
    "붉은겨울 연방학원": 1517944948505317498,
    "발키리 경찰학교": 1517946484635467816,
    "와일드 헌트 예술학원": 1517945110464041173,
    "하이랜더 철도학원": 1533395503948234802,
    "오디세이아 해양 고등학교": 1517945031963447436,
}


# =========================================================
# Discord 봇 설정
# =========================================================

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# 인증 버튼
# =========================================================

class VerifyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔐 서버 인증",
        style=discord.ButtonStyle.green,
        custom_id="verify_button"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        role = interaction.guild.get_role(VERIFIED_ROLE_ID)

        if role is None:
            await interaction.response.send_message(
                "❌ 인증 회원 역할을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if member is None:
            await interaction.response.send_message(
                "❌ 서버에서 회원 정보를 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        # 이미 인증된 경우
        if role in member.roles:
            await interaction.response.send_message(
                "이미 인증이 완료되어 있습니다! ✅",
                ephemeral=True
            )
            return

        try:

            await member.add_roles(role)

            await interaction.response.send_message(
                "인증이 완료되었습니다! ✅\n"
                "이제 학원을 선택할 수 있습니다.",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ 봇에게 역할을 지급할 권한이 없습니다.\n"
                "봇의 역할 위치를 확인해주세요.",
                ephemeral=True
            )


# =========================================================
# 학원 선택 버튼
# =========================================================

class FactionButton(discord.ui.Button):

    def __init__(self, faction_name, role_id):

        super().__init__(
            label=faction_name,
            style=discord.ButtonStyle.secondary,
            custom_id=f"faction_{role_id}"
        )

        self.faction_name = faction_name
        self.role_id = role_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if member is None:
            await interaction.response.send_message(
                "❌ 서버에서 회원 정보를 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        # =================================================
        # 인증 여부 확인
        # =================================================

        verified_role = interaction.guild.get_role(
            VERIFIED_ROLE_ID
        )

        if verified_role not in member.roles:

            await interaction.response.send_message(
                "❌ 먼저 서버 인증을 완료해주세요.",
                ephemeral=True
            )

            return

        # =================================================
        # 선택한 역할 가져오기
        # =================================================

        new_role = interaction.guild.get_role(
            self.role_id
        )

        if new_role is None:

            await interaction.response.send_message(
                "❌ 해당 학원 역할을 찾을 수 없습니다.",
                ephemeral=True
            )

            return

        # =================================================
        # 이미 같은 학원을 선택한 경우
        # =================================================

        if new_role in member.roles:

            await interaction.response.send_message(
                f"이미 **{self.faction_name}** 소속입니다! 🏫",
                ephemeral=True
            )

            return

        # =================================================
        # 기존 학원 역할 제거
        # =================================================

        old_roles = []

        for faction_name, role_id in FACTION_ROLES.items():

            role = interaction.guild.get_role(role_id)

            if role is not None and role in member.roles:

                old_roles.append(role)

        try:

            if old_roles:

                await member.remove_roles(*old_roles)

            # =================================================
            # 새로운 학원 역할 지급
            # =================================================

            await member.add_roles(new_role)

            await interaction.response.send_message(
                f"🏫 **{self.faction_name}**으로 소속이 변경되었습니다!",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ 역할을 변경할 권한이 없습니다.\n"
                "봇의 역할이 학원 역할보다 높은지 확인해주세요.",
                ephemeral=True
            )


# =========================================================
# 학원 선택 View
# =========================================================

class FactionView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        for faction_name, role_id in FACTION_ROLES.items():

            self.add_item(
                FactionButton(
                    faction_name,
                    role_id
                )
            )


# =========================================================
# 봇 로그인
# =========================================================

@bot.event
async def on_ready():

    print(f"{bot.user} 로그인 완료!")
    print(f"서버 {len(bot.guilds)}개에 연결됨")

    # 버튼을 봇 재시작 후에도 유지
    bot.add_view(VerifyView())
    bot.add_view(FactionView())

    # 서버 전용 슬래시 명령어 동기화
    guild = discord.Object(id=GUILD_ID)

    try:

        synced = await bot.tree.sync(
            guild=guild
        )

        print(
            f"슬래시 명령어 "
            f"{len(synced)}개 동기화 완료!"
        )

    except Exception as e:

        print(
            f"슬래시 명령어 동기화 실패: {e}"
        )

    global notice_task
    if notice_task is None or notice_task.done():
        notice_task = asyncio.create_task(notice_loop())



# =========================================================
# /인증
# =========================================================

@bot.tree.command(
    name="인증",
    description="서버 인증 패널을 표시합니다.",
    guild=discord.Object(id=GUILD_ID)
)
async def verify_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🔐 서버 인증",
        description=(
            "FGTC 서버를 이용하려면 "
            "아래 버튼을 눌러 인증해주세요.\n\n"
            "**[🔐 서버 인증]** 버튼을 누르면 "
            "`인증 회원` 역할이 자동으로 지급됩니다."
        )
    )

    await interaction.response.send_message(
        embed=embed,
        view=VerifyView()
    )


# =========================================================
# /학원
# =========================================================

@bot.tree.command(
    name="학원",
    description="소속 학원을 선택할 수 있는 패널을 표시합니다.",
    guild=discord.Object(id=GUILD_ID)
)
async def faction_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🏫 소속 학원 선택",
        description=(
            "자신이 소속되기를 원하는 학원을 선택해주세요.\n\n"
            "⚠️ 학원 역할은 **하나만 선택할 수 있습니다.**\n"
            "다른 학원을 선택하면 기존 학원 역할이 자동으로 변경됩니다."
        )
    )

    await interaction.response.send_message(
        embed=embed,
        view=FactionView()
    )


# =========================================================
# /공지채널설정
# =========================================================

@bot.tree.command(
    name="공지채널설정",
    description="현재 채널을 블루 아카이브 공지 알림 채널로 설정합니다.",
    guild=discord.Object(id=GUILD_ID)
)
async def set_notice_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ 서버 관리 권한이 필요합니다.",
            ephemeral=True
        )
        return

    notice_config["channel_id"] = interaction.channel.id
    save_notice_config(notice_config)

    await interaction.response.send_message(
        "✅ 이 채널을 블루 아카이브 한국 + 일본 공식 공지 알림 채널로 설정했습니다!",
        ephemeral=True
    )


# =========================================================
# 호스팅용 상태 확인 서버
# =========================================================

from aiohttp import web

async def health(request):
    return web.Response(text="FGTC Bot is running.")

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"상태 확인 서버 시작: 0.0.0.0:{port}")


# =========================================================
# 봇 실행
# =========================================================

bot.run(TOKEN)