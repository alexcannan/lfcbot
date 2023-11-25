"""
main bot script for the lfc community. runs once an hour and makes posts if appropriate.

should automatically post the following:
- weekly discussion threads at 00:00 UTC on Mondays
- match threads 4 hours before kickoff
"""


import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from aiohttp import ClientSession
from pydantic import BaseModel

from lemmybot import LemmyAuthWrapper
from lemmybot.post import Post, publish_post, pin_post
from rapidapi import get_fixtures


LFC_COMMUNITY_ID = 11742  # https://programming.dev/c/liverpoolfc@lemmy.world
RAPID_API_TEAM_ID = 40


class PostDeduper:
    """
    ensures we don't duplicate a post by checking the fixtureid or discussion date isn't in a file
    """
    dtstr: str = "%Y-%m-%d"
    filename: Path = Path("posted.txt")
    posted: set

    def __init__(self):
        self._load()

    def _load(self):
        try:
            with open(self.filename, "r") as f:
                self.posted = set([line.strip() for line in f])
        except FileNotFoundError:
            self.posted = set()

    def _save(self):
        with open(self.filename, "w") as f:
            f.write("\n".join(self.posted))

    def fixture_key(self, fixtureid: int):
        return f"fixture-{fixtureid}"

    def discussion_key(self, date: datetime):
        return date.strftime(self.dtstr)

    def fixture_published(self, fixtureid: int):
        return self.fixture_key(fixtureid) in self.posted

    def discussion_published(self, date: datetime):
        return self.discussion_key(date) in self.posted

    def add_fixture(self, fixtureid: int):
        self.posted.add(self.fixture_key(fixtureid))
        self._save()

    def add_discussion(self, date: datetime):
        self.posted.add(self.discussion_key(date))
        self._save()


async def main():
    post_deduper = PostDeduper()
    fixtures = await get_fixtures(RAPID_API_TEAM_ID)
    # if any fixture is in the next 4 hours, make a post
    for fixture in fixtures:
        if fixture.fixture.date.replace(tzinfo=timezone.utc) \
           < datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=4):
            print(f"making post for {fixture}")
            # make post
            post = Post(
                name=fixture.format_title(),
                community_id=LFC_COMMUNITY_ID,
                body=fixture.format_body(),
            )
            if not post_deduper.fixture_published(fixture.fixture.id):
                async with LemmyAuthWrapper() as lemmy:
                    _data = await publish_post(lemmy, post)
                post_deduper.add_fixture(fixture.fixture.id)
    # if it's monday and we haven't posted a discussion thread yet, make a post
    if datetime.utcnow().weekday() == 0:
        # get the date of the monday
        monday = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=datetime.utcnow().weekday())
        if not post_deduper.discussion_published(monday):
            print(f"making discussion post for {monday}")
            # make post
            post = Post(
                name=f"Weekly Discussion Thread - {monday.strftime('%b %d, %Y')}",
                community_id=LFC_COMMUNITY_ID,
                body="What's on your mind?",
            )
            async with LemmyAuthWrapper() as lemmy:
                post_data = await publish_post(lemmy, post)
                await pin_post(lemmy, post_data['post_view']['post']['id'])
            post_deduper.add_discussion(monday)


asyncio.run(main())