import discord
from discord.ext import commands


# =========================================================
# 기본 설정
# =========================================================

import os

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1517933702146166784

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
# 봇 실행
# =========================================================

bot.run(TOKEN)