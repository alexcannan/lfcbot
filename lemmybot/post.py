"""
module that posts to lemmy using their api
"""

import asyncio
from typing import Optional, List

from pydantic import BaseModel

from lemmybot import LemmyAuthWrapper, LEMMY_API_ROOT


class Post(BaseModel):
    id: Optional[int] = None
    name: str
    community_id: int
    body: Optional[str] = None
    nsfw: bool = False


class Creator(BaseModel):
    id: int
    name: str


class PostView(BaseModel):
    post: Post
    creator: Creator


class PostResponse(BaseModel):
    post_view: PostView


class PostListResponse(BaseModel):
    posts: List[PostView]


class PostEdit(BaseModel):
    post_id: int
    name: Optional[str] = None
    url: Optional[str] = None
    body: Optional[str] = None
    nsfw: Optional[bool] = None
    language_id: Optional[int] = None


async def publish_post(law: LemmyAuthWrapper, post: Post) -> PostResponse:
    """
    publish a post to lemmy
    """
    if not post.body:
        raise ValueError("post must have a body")
    url = f"{LEMMY_API_ROOT}/post"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {law.token}",
    }
    payload = post.model_dump()
    payload["auth"] = law.token  # not sure why this is necessary but it is (redundant?)
    async with law.session.post(url, json=payload, headers=headers) as resp:
        return PostResponse.model_validate(await resp.json())


async def edit_post(law: LemmyAuthWrapper, post_edit: PostEdit) -> PostResponse:
    """
    update a post on lemmy
    """
    url = f"{LEMMY_API_ROOT}/post"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {law.token}",
    }
    payload = post_edit.model_dump()
    payload["auth"] = law.token
    async with law.session.put(url, json=payload, headers=headers) as resp:
        resp.raise_for_status()
        return PostResponse.model_validate(await resp.json())


async def pin_post(law: LemmyAuthWrapper, post_id: int, featured: bool=True) -> PostResponse:
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
        return PostResponse.model_validate(await resp.json())


async def get_new_posts(law: LemmyAuthWrapper, community_id: int, limit: int=25) -> PostListResponse:
    """
    get newest posts from community. pinned discussions should appear at the top
    """
    url = f"{LEMMY_API_ROOT}/post/list"
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
        return PostListResponse.model_validate(await resp.json())


if __name__ == "__main__":
    async def main():
        async with LemmyAuthWrapper() as law:
            # print(await pin_post(law, 6388578))
            post_list_response = await get_new_posts(law, 11742)
            print(post_list_response.posts[-1].model_dump())
    asyncio.run(main())
