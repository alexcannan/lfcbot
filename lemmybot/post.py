"""
module that posts to lemmy using their api
"""

import asyncio

from pydantic import BaseModel

from lemmybot import LemmyAuthWrapper, LEMMY_API_ROOT


class Post(BaseModel):
    name: str
    community_id: int
    body: str
    nsfw: bool = False


async def publish_post(law: LemmyAuthWrapper, post: Post):
    """
    publish a post to lemmy
    """
    url = f"{LEMMY_API_ROOT}/post"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {law.token}",
    }
    payload = post.model_dump()
    payload["auth"] = law.token  # not sure why this is necessary but it is (redundant?)
    async with law.session.post(url, json=payload, headers=headers) as resp:
        return await resp.json()


async def pin_post(law: LemmyAuthWrapper, post_id: int, featured: bool=True):
    """
    pin a post to lemmy
    """
    url = f"{LEMMY_API_ROOT}/post/feature"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {law.token}",
    }
    payload = {
        "post_id": post_id,
        "featured": featured,
        "feature_type": "Community",
        "auth": law.token,
    }
    async with law.session.post(url, json=payload, headers=headers) as resp:
        return await resp.json()


async def get_new_posts(law: LemmyAuthWrapper, community_id: int, limit: int=25):
    """
    get newest posts from community. pinned discussions should appear at the top
    """
    url = "https://programming.dev/api/v3/post/list"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {law.token}"
    }
    params = {
        "sort": "New",
        "limit": limit,
        "community_id": community_id,
    }
    async with law.session.get(url, headers=headers, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


if __name__ == "__main__":
    async def main():
        async with LemmyAuthWrapper() as law:
            # print(await pin_post(law, 6388578))
            posts = await get_new_posts(law, 11742)
    asyncio.run(main())