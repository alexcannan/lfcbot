"""
print user info
"""

from lemmybot import LemmyAuthWrapper, LEMMY_API_ROOT


async def get_user_info_self(law: LemmyAuthWrapper):
    url = f"{LEMMY_API_ROOT}/user?username={law.username}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {law.token}",
    }
    async with law.session.get(url, headers=headers) as resp:
        print(resp.status, await resp.text())
        return await resp.json()


if __name__ == "__main__":
    import asyncio
    async def main():
        async with LemmyAuthWrapper() as law:
            print(await get_user_info_self(law))
    asyncio.run(main())