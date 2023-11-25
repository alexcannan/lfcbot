"""
module that posts to lemmy using their api
"""

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


async def pin_post(law: LemmyAuthWrapper, post_id: int):
    """
    pin a post to lemmy
    """
    url = f"{LEMMY_API_ROOT}/post/pin"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {law.token}",
    }
    payload = {
        "post_id": post_id,
        "featured": True,
        "feature_type": "Community",
    }
    async with law.session.post(url, json=payload, headers=headers) as resp:
        return await resp.json()