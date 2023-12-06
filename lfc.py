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
from lemmybot.post import Post, publish_post, pin_post, get_new_posts
from rapidapi import get_next_fixtures, get_previous_fixtures, format_form


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
        return f"discussion-{date.strftime(self.dtstr)}"

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
    print("lfcbot waking up")
    post_deduper = PostDeduper()
    fixtures = await get_next_fixtures(RAPID_API_TEAM_ID)
    print(f"received {len(fixtures)} fixtures")
    # if any fixture is in the next 4 hours, make a post
    for fixture in fixtures:
        if fixture.fixture.date.replace(tzinfo=timezone.utc) \
           < datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=4):
            if not post_deduper.fixture_published(fixture.fixture.id):
                print(f"making post for {fixture=}")
                # get form of teams
                home_team_form: str | None = None
                away_team_form: str | None = None
                try:
                    home_previous_fixtures = await get_previous_fixtures(fixture.teams.home.id)
                    home_team_form = format_form(home_previous_fixtures, fixture.teams.home.id)
                    away_previous_fixtures = await get_previous_fixtures(fixture.teams.away.id)
                    away_team_form = format_form(away_previous_fixtures, fixture.teams.away.id)
                except Exception as e:
                    print(f"error getting form: [{e.__class__.__name__}] {e}")
                # make post
                post = Post(
                    name=fixture.format_title(),
                    community_id=LFC_COMMUNITY_ID,
                    body=fixture.format_body(home_team_form, away_team_form)+"\n\n~posted~ ~by~ ~lfcbot~",
                )
                async with LemmyAuthWrapper() as lemmy:
                    _data = await publish_post(lemmy, post)
                post_deduper.add_fixture(fixture.fixture.id)
    # if we haven't posted monday's discussion thread yet, make a post
    # get the date of the monday
    monday = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=datetime.utcnow().weekday())
    if not post_deduper.discussion_published(monday):
        print(f"making discussion post for {monday}")
        discussion_title = "Weekly Discussion Thread"
        # make post
        post = Post(
            name=f"{discussion_title} - {monday.strftime('%b %d, %Y')}",
            community_id=LFC_COMMUNITY_ID,
        body="What's on your mind?\n\n~posted~ ~by~ ~lfcbot~",
        )
        async with LemmyAuthWrapper() as lemmy:
            # unpin old discussion post(s)
            posts_response = await get_new_posts(lemmy, LFC_COMMUNITY_ID)
            for post_obj in posts_response['posts']:
                post_name: str = post_obj['post']['name']
                creator_name: str = post_obj['creator']['name']
                post_id = int(post_obj['post']['id'])
                is_discussion = post_name.startswith(discussion_title)
                is_from_bot = creator_name == lemmy.username
                if is_discussion and is_from_bot:
                    await pin_post(lemmy, int(post_obj['post']['id']), False)
            # post and pin new discussion post
            post_data = await publish_post(lemmy, post)
            post_id = int(post_data['post_view']['post']['id'])
            await pin_post(lemmy, post_id, True)
        post_deduper.add_discussion(monday)


if __name__ == "__main__":
    asyncio.run(main())
