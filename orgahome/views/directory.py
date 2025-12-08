from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from orgahome.services import EnhancedUser, fetch_directory_data


async def index(request: Request) -> Response:
    team_name = request.path_params.get("team_name")
    user_map = await fetch_directory_data(request.state.uffd_client, request.state.mm_client)
    enhanced_users = list(user_map.values())
    all_teams: set[str] = set()

    for user in enhanced_users:
        for team in user.teams:
            all_teams.add(team.team_name)

    # Sort users alphabetically by default
    enhanced_users.sort(key=lambda u: u.display_name.lower())

    sorted_teams = sorted(list(all_teams))

    leads: list[EnhancedUser] = []
    members: list[EnhancedUser] = []
    others: list[EnhancedUser] = []

    if team_name:
        for user in enhanced_users:
            # Check if user is in the team
            team_info = next((t for t in user.teams if t.team_name == team_name), None)
            if team_info:
                if team_info.is_lead:
                    leads.append(user)
                else:
                    members.append(user)
            else:
                others.append(user)
    else:
        leads = []
        members = []
        others = enhanced_users

    return request.state.templates.TemplateResponse(
        request,
        "index.html",
        {
            "users": enhanced_users,
            "leads": leads,
            "members": members,
            "others": others,
            "teams": sorted_teams,
            "selected_team": team_name,
        },
    )


async def user_detail(request: Request) -> Response:
    username = request.path_params.get("username")
    if not username or not isinstance(username, str):
        raise HTTPException(status_code=404)

    user_map = await fetch_directory_data(request.state.uffd_client, request.state.mm_client)
    user = user_map.get(username)
    if not user:
        raise HTTPException(status_code=404)

    return request.state.templates.TemplateResponse(request, "user.html", {"user": user})
