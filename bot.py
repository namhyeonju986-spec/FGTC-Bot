import asyncio
import json
from html import unescape
from urllib.parse import urljoin
from html.parser import HTMLParser

import aiohttp
import discord
from discord.ext import commands


# =========================================================
# 기본 설정
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = 1517933702146166784

VERIFIED_ROLE_ID = 1517944396446830693

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

NOTICE_CONFIG_FILE = "notice_config.json"
NOTICE_CHECK_INTERVAL = 300

KR_NOTICE_URL = "https://forum.nexon.com/bluearchive/board_list?board=1018"
JP_NOTICE_URL = "https://bluearchive.jp/news"


# =========================================================
# 디스코드
# =========================================================

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

notice_task = None


# =========================================================
# 공지 설정
# =========================================================

def load_notice_config():
    try:
        with open(NOTICE_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"channel_id": None}


def save_notice_config():
    with open(NOTICE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            notice_config,
            f,
            ensure_ascii=False,
            indent=2
        )


notice_config = load_notice_config()


# =========================================================
# HTML 파서
# =========================================================

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

        if tag.lower() == "a" and self.current_href:

            title = " ".join(
                "".join(self.current_text).split()
            )

            if title:
                self.links.append(
                    (
                        self.current_href,
                        unescape(title)
                    )
                )

            self.current_href = None
            self.current_text = []


# =========================================================
# 웹페이지 가져오기
# =========================================================

async def fetch_page(session, url):

    headers = {
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/140.0 Safari/537.36"
    }

    async with session.get(
        url,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=30)
    ) as response:

        response.raise_for_status()

        return await response.text()


# =========================================================
# 한국 공지 찾기
# =========================================================

def find_kr_notice(html):

    parser = LinkParser()
    parser.feed(html)

    for href, title in parser.links:

        if not href or not title:
            continue

        href_lower = href.lower()

        if (
            "board_view" in href_lower
            or "thread=" in href_lower
            or "board/view" in href_lower
        ):

            return (
                urljoin(KR_NOTICE_URL, href),
                title
            )

    return None


# =========================================================
# 일본 공지 찾기
# =========================================================

def find_jp_notice(html):

    parser = LinkParser()
    parser.feed(html)

    for href, title in parser.links:

        if not href or not title:
            continue

        href_lower = href.lower()

        if "/news/newsjump/" in href_lower:

            return (
                urljoin(JP_NOTICE_URL, href),
                title
            )

    return None


# =========================================================
# 공지 전송
# =========================================================

async def send_notice(source, title, url):

    channel_id = notice_config.get("channel_id")

    if not channel_id:
        return

    channel = bot.get_channel(int(channel_id))

    if channel is None:

        try:
            channel = await bot.fetch_channel(
                int(channel_id)
            )

        except:
            print("[공지] 채널을 찾을 수 없습니다.")
            return

    if source == "kr":

        footer = "🇰🇷 블루 아카이브 한국 공식 공지"

    else:

        footer = "🇯🇵 ブルーアーカイブ 일본 공식 공지"

    embed = discord.Embed(
        title=title[:256],
        description="새로운 공식 공지가 등록되었습니다.",
        url=url,
        color=discord.Color.blue()
    )

    embed.add_field(
        name="공지 보기",
        value=f"[공식 공지 바로가기]({url})",
        inline=False
    )

    embed.set_footer(
        text=footer
    )

    try:

        await channel.send(
            embed=embed
        )

        print(
            f"[공지] 전송 완료: {title}"
        )

    except discord.Forbidden:

        print(
            "[공지] 봇에게 메시지 전송 권한이 없습니다."
        )

    except Exception as e:

        print(
            f"[공지] 전송 실패: {e}"
        )


# =========================================================
# 공지 감시
# =========================================================

async def notice_loop():

    await bot.wait_until_ready()

    print("[공지] 공지 감시 시작")

    cache = {
        "kr": "",
        "jp": ""
    }

    first_run = True

    async with aiohttp.ClientSession() as session:

        while not bot.is_closed():

            try:

                kr_html = await fetch_page(
                    session,
                    KR_NOTICE_URL
                )

                jp_html = await fetch_page(
                    session,
                    JP_NOTICE_URL
                )

                kr = find_kr_notice(
                    kr_html
                )

                jp = find_jp_notice(
                    jp_html
                )

                # 최초 실행
                if first_run:

                    if kr:
                        cache["kr"] = kr[0]

                        print(
                            f"[공지] 한국 현재 공지: {kr[1]}"
                        )

                    if jp:
                        cache["jp"] = jp[0]

                        print(
                            f"[공지] 일본 현재 공지: {jp[1]}"
                        )

                    first_run = False

                else:

                    # 한국
                    if kr:

                        url, title = kr

                        if url != cache["kr"]:

                            cache["kr"] = url

                            await send_notice(
                                "kr",
                                title,
                                url
                            )

                    # 일본
                    if jp:

                        url, title = jp

                        if url != cache["jp"]:

                            cache["jp"] = url

                            await send_notice(
                                "jp",
                                title,
                                url
                            )

            except asyncio.CancelledError:

                raise

            except Exception as e:

                print(
                    f"[공지] 확인 오류: {e}"
                )

            await asyncio.sleep(
                NOTICE_CHECK_INTERVAL
            )


# =========================================================
# 역할 지급
# =========================================================

async def give_role(member, role_id):

    guild = member.guild

    role = guild.get_role(
        role_id
    )

    if role is None:

        return False, "역할을 찾을 수 없습니다."

    if role in member.roles:

        return True, "이미 가지고 있는 역할입니다."

    bot_member = guild.me

    if bot_member is None:

        return False, "봇 정보를 가져올 수 없습니다."

    if not bot_member.guild_permissions.manage_roles:

        return False, "봇에게 역할 관리 권한이 없습니다."

    if role >= bot_member.top_role:

        return (
            False,
            f"'{role.name}' 역할이 봇보다 위에 있습니다."
        )

    try:

        await member.add_roles(
            role,
            reason="FGTC 봇 역할 지급"
        )

        return True, "역할 지급 완료"

    except discord.Forbidden:

        return False, "역할을 지급할 권한이 없습니다."

    except Exception as e:

        return False, str(e)


# =========================================================
# 인증 버튼
# =========================================================

class VerifyView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="🔐 서버 인증",
        style=discord.ButtonStyle.green,
        custom_id="fgtc_verify_button"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        member = interaction.user

        if not isinstance(
            member,
            discord.Member
        ):

            await interaction.response.send_message(
                "서버 멤버 정보를 가져올 수 없습니다.",
                ephemeral=True
            )

            return

        success, message = await give_role(
            member,
            VERIFIED_ROLE_ID
        )

        if not success:

            await interaction.response.send_message(
                f"❌ 인증 실패\n{message}",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "✅ 서버 인증이 완료되었습니다!",
            ephemeral=True
        )


# =========================================================
# 학원 버튼
# =========================================================

class FactionButton(discord.ui.Button):

    def __init__(
        self,
        faction_name,
        role_id
    ):

        super().__init__(
            label=faction_name,
            style=discord.ButtonStyle.secondary,
            custom_id=f"fgtc_faction_{role_id}"
        )

        self.faction_name = faction_name
        self.role_id = role_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.user

        if not isinstance(
            member,
            discord.Member
        ):

            await interaction.response.send_message(
                "서버 멤버 정보를 가져올 수 없습니다.",
                ephemeral=True
            )

            return

        success, message = await give_role(
            member,
            self.role_id
        )

        if not success:

            await interaction.response.send_message(
                f"❌ 학원 선택 실패\n{message}",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"🏫 **{self.faction_name}** 역할이 지급되었습니다!",
            ephemeral=True
        )


class FactionView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        for name, role_id in FACTION_ROLES.items():

            self.add_item(
                FactionButton(
                    name,
                    role_id
                )
            )


# =========================================================
# 봇 시작
# =========================================================

@bot.event
async def on_ready():

    global notice_task

    print("=" * 50)
    print(f"✅ 로그인 성공: {bot.user}")
    print(f"🆔 봇 ID: {bot.user.id}")
    print("=" * 50)

    # 버튼 유지
    bot.add_view(
        VerifyView()
    )

    bot.add_view(
        FactionView()
    )

    # 슬래시 명령어 동기화
    guild = discord.Object(
        id=GUILD_ID
    )

    try:

        synced = await bot.tree.sync(
            guild=guild
        )

        print(
            f"✅ 슬래시 명령어 동기화: {len(synced)}개"
        )

    except Exception as e:

        print(
            f"❌ 명령어 동기화 실패: {e}"
        )

    # 공지 감시 시작
    if (
        notice_task is None
        or notice_task.done()
    ):

        notice_task = asyncio.create_task(
            notice_loop()
        )


# =========================================================
# /인증
# =========================================================

@bot.tree.command(
    name="인증",
    description="FGTC 서버 인증 패널",
    guild=discord.Object(id=GUILD_ID)
)
async def 인증(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🔐 FGTC 서버 인증",
        description=(
            "아래 버튼을 눌러 서버 인증을 진행해주세요.\n\n"
            "인증이 완료되면 **인증 회원** 역할이 지급됩니다."
        ),
        color=discord.Color.green()
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
    description="소속 학원 선택",
    guild=discord.Object(id=GUILD_ID)
)
async def 학원(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🏫 소속 학원 선택",
        description=(
            "자신이 원하는 학원을 선택해주세요.\n"
            "버튼을 누르면 해당 학원 역할이 지급됩니다."
        ),
        color=discord.Color.blue()
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
    description="현재 채널을 공식 공지 알림 채널로 설정",
    guild=discord.Object(id=GUILD_ID)
)
async def 공지채널설정(
    interaction: discord.Interaction
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ 서버 관리 권한이 필요합니다.",
            ephemeral=True
        )

        return

    notice_config["channel_id"] = interaction.channel.id

    save_notice_config()

    await interaction.response.send_message(
        "✅ 현재 채널이 공식 공지 알림 채널로 설정되었습니다.",
        ephemeral=True
    )

    print(
        f"[공지] 채널 설정: {interaction.channel.id}"
    )


# =========================================================
# /공지상태
# =========================================================

@bot.tree.command(
    name="공지상태",
    description="공식 공지 알림 설정 확인",
    guild=discord.Object(id=GUILD_ID)
)
async def 공지상태(
    interaction: discord.Interaction
):

    channel_id = notice_config.get(
        "channel_id"
    )

    if channel_id:

        channel = interaction.guild.get_channel(
            int(channel_id)
        )

        if channel:

            text = (
                f"📢 공지 채널: {channel.mention}"
            )

        else:

            text = (
                f"📢 설정된 채널 ID: `{channel_id}`"
            )

    else:

        text = (
            "❌ 공지 채널이 설정되지 않았습니다."
        )

    await interaction.response.send_message(
        text,
        ephemeral=True
    )


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    if (
        not TOKEN
        or TOKEN == "여기에_디스코드_봇_토큰"
    ):

        print()
        print("❌ 봇 토큰이 없습니다.")
        print()
        print('bot.py의 TOKEN = "..." 부분에')
        print("본인의 디스코드 봇 토큰을 넣어주세요.")
        print()

        raise SystemExit

    print("🚀 FGTC 봇 시작...")

    try:

        bot.run(TOKEN)

    except discord.LoginFailure:

        print()
        print("❌ 디스코드 로그인 실패")
        print("토큰이 잘못되었거나 만료되었습니다.")
        print()

    except Exception as e:

        print()
        print(f"❌ 실행 오류: {e}")
        print()