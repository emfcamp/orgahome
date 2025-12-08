import logging
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import aiohttp
from authlib.integrations.starlette_client import OAuth
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount, Route, Router
from starlette.templating import Jinja2Templates

from orgahome import staticfiles
from orgahome.config import Config
from orgahome.middleware import AuthMiddleware
from orgahome.services import MattermostClient, UFFDClient
from orgahome.views import auth, directory, proxy

logger = logging.getLogger(__name__)


class State(TypedDict):
    client_session: aiohttp.ClientSession
    uffd_client: UFFDClient
    mm_client: MattermostClient
    oauth: OAuth
    templates: Jinja2Templates


def lifespan_factory(static_files: staticfiles.StaticFilesBase):
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[State]:
        if not Config.MATTERMOST_API_URL or not Config.MATTERMOST_TOKEN:
            raise ValueError("MATTERMOST_API_URL and MATTERMOST_TOKEN must be set")

        if not Config.UFFD_URL or not Config.UFFD_API_URL or not Config.UFFD_USER or not Config.UFFD_PASSWORD:
            raise ValueError("UFFD_URL, UFFD_API_URL, UFFD_USER, and UFFD_PASSWORD must be set")

        if not Config.OIDC_CLIENT_ID or not Config.OIDC_CLIENT_SECRET:
            raise ValueError("OIDC_CLIENT_ID and OIDC_CLIENT_SECRET must be set")

        templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")
        static_files.register_template_functions(templates)

        async with aiohttp.ClientSession() as session:
            uffd_client = UFFDClient(session, Config.UFFD_API_URL, Config.UFFD_USER, Config.UFFD_PASSWORD)
            mm_client = MattermostClient(session, Config.MATTERMOST_API_URL, Config.MATTERMOST_TOKEN)

            oauth = OAuth()
            oauth.register(
                name="uffd",
                client_id=Config.OIDC_CLIENT_ID,
                client_secret=Config.OIDC_CLIENT_SECRET,
                client_kwargs={"scope": Config.OIDC_SCOPES},
                server_metadata_url=f"{Config.UFFD_URL}/.well-known/openid-configuration",
            )

            yield {
                "client_session": session,
                "uffd_client": uffd_client,
                "mm_client": mm_client,
                "oauth": oauth,
                "templates": templates,
            }

    return lifespan


def create_app(debug: bool = False) -> Starlette:
    protected_routes = [
        Route("/", endpoint=directory.index),
        Route("/team/{team_name}", endpoint=directory.index),
        Route("/user/{username}", endpoint=directory.user_detail),
        Route("/mm_emoji/{emoji_name}", endpoint=proxy.mm_emoji_proxy),
        Route("/mm_avatar/{user_id}", endpoint=proxy.mm_avatar_proxy),
    ]

    protected_router = Router(routes=protected_routes, middleware=[Middleware(AuthMiddleware)])  # ty: ignore[invalid-argument-type]

    static_files: staticfiles.StaticFilesBase
    if debug:
        static_files = staticfiles.DevelopmentStaticFiles()
    else:
        serving_dir = Config.ORGAHOME_DIST_ROOT or staticfiles.STATIC_COMPILED_PATH
        static_files = staticfiles.ManifestStaticFiles(serving_dir=pathlib.Path(serving_dir))

    routes = [
        Route("/authorize", endpoint=auth.authorize),
        Mount("/static", app=staticfiles.StaticFilesServer(static_files), name="static"),
        Mount("/", app=protected_router),
    ]

    middleware = [
        Middleware(SessionMiddleware, secret_key=Config.SECRET_KEY),  # ty: ignore[invalid-argument-type]
    ]

    return Starlette(debug=debug, routes=routes, middleware=middleware, lifespan=lifespan_factory(static_files))


app = create_app(debug=False)
debug_app = create_app(debug=True)
