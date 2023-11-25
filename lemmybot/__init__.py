"""
lemmybot root
"""

import hashlib
import os

from aiohttp import ClientSession


LEMMY_API_ROOT = os.environ["LEMMY_API_ROOT"]
LEMMY_USERNAME = os.environ["LEMMY_USERNAME"]
LEMMY_PASSWORD = os.environ["LEMMY_PASSWORD"]


class LemmyAuthWrapper:
    """
    async context manager that handles login, scrambling jwt on exit for HIGH SECURITY!
    """
    async def __aenter__(self, username: str=LEMMY_USERNAME, password: str=LEMMY_PASSWORD):
        self.session = await ClientSession().__aenter__()
        await self._login(username, password)
        return self

    async def __aexit__(self, *args, **kwargs):
        self.token = hashlib.sha256().hexdigest()
        await self.session.__aexit__(*args, **kwargs)

    async def _login(self, username: str, password: str):
        url = f"{LEMMY_API_ROOT}/user/login"
        data = {
            "username_or_email": username,
            "password": password,
        }
        async with self.session.post(url, json=data) as resp:
            resp.raise_for_status()
            data = await resp.json()
        # set self.token to the token from the response
        self.token = data["jwt"]
        self.username = username
