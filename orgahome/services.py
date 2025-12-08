import asyncio
import datetime
import functools
import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import TypedDict

import aiohttp

logger = logging.getLogger(__name__)


@functools.cache
def get_system_emoji_map() -> dict[str, str]:
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        emoji_path = os.path.join(base_dir, "emoji.json")
        with open(emoji_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Map short_name/underscores -> unicode codepoint
        mapping = {}
        for item in data:
            unified = item.get("unified")
            if unified:
                for name in item.get("short_names", []):
                    mapping[name] = unified
                if "short_name" in item:
                    mapping[item["short_name"]] = unified
        return mapping
    except Exception as e:
        logger.error(f"Failed to fetch system emoji map: {e}")
        return {}


class UFFDUser(TypedDict):
    id: int
    loginname: str
    email: str
    displayname: str
    groups: list[str]


class UFFDClient:
    def __init__(self, session: aiohttp.ClientSession, api_url: str, username: str, password: str) -> None:
        self.session = session
        self.api_url: str = api_url.rstrip("/")
        self.auth = aiohttp.BasicAuth(username, password)

    async def get_users(self) -> list[UFFDUser]:
        try:
            async with self.session.get(f"{self.api_url}/getusers", auth=self.auth) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching users from UFFD: {e}")
            return []


MattermostUserProps = TypedDict(
    "MattermostUserProps",
    {
        "idp/userid": str,
        "customStatus": str,
    },
    total=False,
)


class MattermostUser(TypedDict):
    id: str
    username: str
    first_name: str
    last_name: str
    email: str
    position: str
    props: MattermostUserProps


class MattermostClient:
    def __init__(self, session: aiohttp.ClientSession, api_url: str, token: str) -> None:
        self.session = session
        self.api_url: str = api_url.rstrip("/")
        self.headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

    async def get_all_active_users(self) -> list[MattermostUser]:
        users: list[MattermostUser] = []
        page = 0
        per_page = 200
        while True:
            try:
                async with self.session.get(
                    f"{self.api_url}/users",
                    headers=self.headers,
                    params={"page": str(page), "per_page": str(per_page), "active": "true"},
                ) as response:
                    response.raise_for_status()
                    batch = await response.json()
                    if not batch:
                        break
                    users.extend(batch)
                    if len(batch) < per_page:
                        break
                    page += 1
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching users page {page}: {e}")
                break
        return users

    def get_user_image_url(self, user_id: str) -> str:
        return f"{self.api_url}/users/{user_id}/image"

    async def get_emoji_id_by_name(self, session: aiohttp.ClientSession, emoji_name: str) -> str | None:
        try:
            async with session.get(f"{self.api_url}/emoji/name/{emoji_name}", headers=self.headers) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return data.get("id")
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching emoji {emoji_name}: {e}")
            return None

    def get_custom_emoji_image_url(self, emoji_id: str) -> str:
        return f"{self.api_url}/emoji/{emoji_id}/image"


class MattermostCustomStatus(TypedDict):
    emoji: str
    text: str
    duration: str
    expires_at: str


@dataclass(frozen=True)
class TeamMembership:
    team_name: str
    is_lead: bool


@dataclass(frozen=True)
class EnhancedUser:
    uffd: UFFDUser
    mm: MattermostUser

    @property
    def display_name(self) -> str:
        first = self.mm.get("first_name")
        last = self.mm.get("last_name")
        if first and last:
            return f"{first} {last}"
        if first:
            return first
        if last:
            return last
        return self.uffd.get("displayname") or self.uffd.get("loginname")

    @property
    def image_url(self) -> str:
        return f"/mm_avatar/{self.mm['id']}"

    @property
    def username(self) -> str:
        return self.uffd.get("loginname")

    @property
    def email(self) -> str:
        return self.uffd.get("email")

    @property
    def groups(self) -> list[str]:
        return self.uffd.get("groups", [])

    @property
    def teams(self) -> list[TeamMembership]:
        teams = []
        user_groups = set(self.groups)
        for group in self.groups:
            if group.startswith("team_"):
                team_name = group[5:]
                is_lead = f"moderation_{team_name}" in user_groups
                teams.append(TeamMembership(team_name=team_name, is_lead=is_lead))
        teams.sort(key=lambda x: x.team_name)
        return teams

    @property
    def teams_json(self) -> str:
        return json.dumps([asdict(team) for team in self.teams])

    @property
    def position(self) -> str | None:
        return self.mm.get("position")

    @property
    def custom_status(self) -> MattermostCustomStatus | None:
        props = self.mm.get("props", {})
        cs_str = props.get("customStatus")
        if not cs_str:
            return None

        try:
            cs = json.loads(cs_str)
            expires_at_str = cs.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.datetime.fromisoformat(expires_at_str)
                    if expires_at.year > 2000 and expires_at < datetime.datetime.now(datetime.timezone.utc):
                        return None
                except ValueError:
                    return None
            return cs
        except json.JSONDecodeError:
            return None

    @property
    def custom_status_emoji_url(self) -> str | None:
        cs = self.custom_status
        if not cs or not cs.get("emoji"):
            return None

        emoji_name = cs["emoji"]

        system_map = get_system_emoji_map()
        if emoji_name in system_map:
            unified = system_map[emoji_name]
            return f"https://chat.orga.emfcamp.org/static/emoji/{unified.lower()}.png"

        return f"/mm_emoji/{emoji_name}"


async def fetch_directory_data(uffd_client: UFFDClient, mm_client: MattermostClient) -> dict[str, EnhancedUser]:
    # Run async calls
    uffd_task = uffd_client.get_users()
    mm_task = mm_client.get_all_active_users()

    uffd_users, mm_users = await asyncio.gather(uffd_task, mm_task)

    mm_map: dict[str, MattermostUser] = {}
    for mm_user in mm_users:
        props = mm_user.get("props", {})
        idp_id = props.get("idp/userid")
        if idp_id:
            mm_map[idp_id] = mm_user

    user_map: dict[str, EnhancedUser] = {}
    for uffd_user in uffd_users:
        uffd_id_str = str(uffd_user.get("id"))
        mm_user = mm_map.get(uffd_id_str)
        if not mm_user:
            continue

        user = EnhancedUser(uffd=uffd_user, mm=mm_user)
        user_map[uffd_user["loginname"]] = user

    return user_map
