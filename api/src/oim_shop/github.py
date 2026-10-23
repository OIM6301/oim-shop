"""The three requests that signing in with GitHub needs: GitHub's own documentation,
"Authorizing OAuth apps", describes each one.

1. The browser goes to GitHub's authorize page with a random `state` and a PKCE challenge.
2. GitHub sends the browser back with a code, which the server trades for a token.
3. The server asks GitHub who the token belongs to, and then forgets the token.
"""

import base64
import hashlib
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx2


class GitHubError(Exception):
    """GitHub did not answer as expected."""


@dataclass(frozen=True)
class GitHubUser:
    id: int
    login: str


@dataclass(frozen=True)
class GitHub:
    client_id: str
    client_secret: str
    web_url: str = "https://github.com"
    api_url: str = "https://api.github.com"
    # Tests pass a transport that answers as GitHub would; None means the network.
    transport: httpx2.AsyncBaseTransport | None = None

    def authorize_url(self, redirect_uri: str, state: str, verifier: str) -> str:
        # No scope: the app reads only the public profile, and GitHub then shows no permissions to approve.
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        query = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "allow_signup": "false",
        }
        return f"{self.web_url}/login/oauth/authorize?{urlencode(query)}"

    async def user_for_code(self, code: str, redirect_uri: str, verifier: str) -> GitHubUser:
        async with httpx2.AsyncClient(transport=self.transport, timeout=10) as client:
            try:
                answer = await client.post(
                    f"{self.web_url}/login/oauth/access_token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "code_verifier": verifier,
                    },
                    headers={"Accept": "application/json"},
                )
                token = answer.json().get("access_token") if answer.is_success else None
                if not isinstance(token, str):
                    raise GitHubError(f"no token: HTTP {answer.status_code}")
                profile = await client.get(
                    f"{self.api_url}/user",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                )
            except (httpx2.HTTPError, ValueError) as error:
                raise GitHubError(str(error)) from error
        if not profile.is_success:
            raise GitHubError(f"no profile: HTTP {profile.status_code}")
        data = profile.json()
        if not isinstance(data.get("id"), int) or not isinstance(data.get("login"), str):
            raise GitHubError("the profile has no id or login")
        return GitHubUser(id=data["id"], login=data["login"])
