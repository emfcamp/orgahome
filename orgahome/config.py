import os

import dotenv

dotenv.load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_key")
    ORGAHOME_DIST_ROOT = os.environ.get("ORGAHOME_DIST_ROOT")

    # OIDC Configuration
    OIDC_CLIENT_SECRETS = os.environ.get("OIDC_CLIENT_SECRETS", "client_secrets.json")
    OIDC_SCOPES = "openid email profile groups"
    OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "orgahome")
    OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET")

    # UFFD API Configuration
    UFFD_URL = os.environ.get("UFFD_URL", "https://identity.emfcamp.org")
    UFFD_API_URL = os.environ.get("UFFD_API_URL", f"{UFFD_URL}/api/v1")
    UFFD_USER = os.environ.get("UFFD_USER")
    UFFD_PASSWORD = os.environ.get("UFFD_PASSWORD")

    # Mattermost API Configuration
    MATTERMOST_API_URL = os.environ.get("MATTERMOST_API_URL", "https://chat.orga.emfcamp.org/api/v4")
    MATTERMOST_TOKEN = os.environ.get("MATTERMOST_TOKEN")
