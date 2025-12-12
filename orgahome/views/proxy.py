import logging

import aiohttp
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, StreamingResponse

from orgahome import gif, services

logger = logging.getLogger(__name__)


async def mm_url_proxy(request: Request, url: str, remove_animation: bool = False) -> Response:
    session: aiohttp.ClientSession = request.state.client_session
    try:
        resp = await session.get(url, headers=request.state.mm_client.headers)
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return Response("Error fetching image", status_code=502)

    if resp.status != 200:
        resp.close()
        return Response("Error fetching image", status_code=resp.status)

    excluded_headers = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    }
    headers = {k.lower(): v for k, v in resp.headers.items() if k.lower() not in excluded_headers}

    async def content_iter():
        try:
            stream = resp.content.iter_chunked(1024)

            if remove_animation and headers.get("content-type", "").startswith("image/gif"):
                stream = gif.deanimate(stream)

            async for chunk in stream:
                yield chunk
        finally:
            resp.close()
            # Do not close the shared session

    return StreamingResponse(content_iter(), status_code=resp.status, headers=headers)


async def mm_emoji_proxy(request: Request) -> Response:
    mm_client = services.MattermostClient.from_request(request)
    emoji_name = request.path_params.get("emoji_name")
    if not emoji_name or not isinstance(emoji_name, str):
        return Response("Invalid emoji name", status_code=400)
    try:
        emoji_id = await mm_client.get_emoji_id_by_name(emoji_name)
        if not emoji_id:
            return Response("Not found", status_code=404)

        url = mm_client.get_custom_emoji_image_url(emoji_id)
        return await mm_url_proxy(request, url, request.query_params.get("remove_animation") == "true")
    except Exception as e:
        logger.error(f"Failed to proxy emoji {emoji_name}: {e}")
        return Response("Error", status_code=500)


async def mm_avatar_proxy(request: Request) -> Response:
    mm_client = services.MattermostClient.from_request(request)
    user_id = request.path_params.get("user_id")
    if not user_id or not isinstance(user_id, str):
        return Response("Invalid user ID", status_code=400)
    try:
        url = mm_client.get_user_image_url(user_id)
        return await mm_url_proxy(request, url)
    except Exception as e:
        logger.error(f"Failed to proxy image for {user_id}: {e}")
        # Redirect to default
        return RedirectResponse(request.url_for("static", path="default_profile.svg"))
