"""
main bot script for the lfc community. runs once an hour and makes posts if appropriate.

should automatically post the following:
- weekly discussion threads at 00:00 UTC on Mondays
- match threads 4 hours before kickoff
"""


import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from loguru import logger
from pydantic import BaseModel

from lemmybot import LemmyAuthWrapper
from lemmybot.post import Post, PostEdit, PostResponse, edit_post, publish_post, pin_post, get_new_posts
from rapidapi import FixtureResponse, get_lineups, get_next_fixtures, get_previous_fixtures, format_form, LINEUP_MINUTES_BEFORE_KICKOFF


LFC_COMMUNITY_ID = 11742  # https://programming.dev/c/liverpoolfc@lemmy.world
RAPID_API_TEAM_ID = 40


class FixtureCache(BaseModel):
    fixtures: List[FixtureResponse]
    date_fetched: datetime


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
    logger.info("lfcbot waking up")
    post_deduper = PostDeduper()

    fixtures_from_today = Path("fixtures_from_today.json")
    if fixtures_from_today.exists():
        fixture_cache = FixtureCache.model_validate_json(fixtures_from_today.read_text())
        fixtures = fixture_cache.fixtures
        if fixture_cache.date_fetched.date() != datetime.utcnow().date():
            logger.info("fixture cache out of date, fetching new ones")
            fixtures = await get_next_fixtures(RAPID_API_TEAM_ID)
            fixture_cache = FixtureCache(fixtures=fixtures, date_fetched=datetime.utcnow())
            fixtures_from_today.write_text(fixture_cache.model_dump_json())
    else:
        fixtures = await get_next_fixtures(RAPID_API_TEAM_ID)
        fixture_cache = FixtureCache(fixtures=fixtures, date_fetched=datetime.utcnow())
        fixtures_from_today.write_text(fixture_cache.model_dump_json())

    lineup_tasks: List[asyncio.Task] = []
    # if any fixture is in the next 4 hours, make a post
    for fixture in fixtures:
        if fixture.fixture.date.replace(tzinfo=timezone.utc) \
           < datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=4):
            if not post_deduper.fixture_published(fixture.fixture.id):
                logger.info(f"making post for {fixture=}")
                # get form of teams
                home_team_form: str | None = None
                away_team_form: str | None = None
                try:
                    home_previous_fixtures = await get_previous_fixtures(fixture.teams.home.id)
                    home_team_form = format_form(home_previous_fixtures, fixture.teams.home.id)
                    away_previous_fixtures = await get_previous_fixtures(fixture.teams.away.id)
                    away_team_form = format_form(away_previous_fixtures, fixture.teams.away.id)
                except Exception as e:
                    logger.info(f"error getting form: [{e.__class__.__name__}] {e}")
                # make post
                post = Post(
                    name=fixture.format_title(),
                    community_id=LFC_COMMUNITY_ID,
                    body=fixture.format_body(home_team_form, away_team_form, lineup=None)+"\n\n~posted~ ~by~ ~lfcbot~",
                )
                async with LemmyAuthWrapper() as lemmy:
                    post_response: PostResponse = await publish_post(lemmy, post)
                post_deduper.add_fixture(fixture.fixture.id)
                # spawn task to update post with lineups until some time before kickoff
                kickoff = fixture.fixture.date.replace(tzinfo=timezone.utc)
                async def update_task():
                    logger.info("waiting for lineup update")
                    await asyncio.sleep((kickoff - datetime.utcnow().replace(tzinfo=timezone.utc)).total_seconds() - LINEUP_MINUTES_BEFORE_KICKOFF*60)
                    logger.debug("proceeding with lineup grab")
                    for _ in range(5):
                        lineup_response = await get_lineups(fixture.fixture.id)
                        try:
                            lfc_lineup = lineup_response.get_team_lineup(RAPID_API_TEAM_ID)
                            logger.debug(f"got lineup: {lfc_lineup=}")
                        except ValueError:
                            logger.debug("no lineup yet, trying again in 2 minutes")
                            await asyncio.sleep(120)  # wait 2 minutes and try again
                            continue
                        async with LemmyAuthWrapper() as lemmy:
                            post_edit = PostEdit(
                                post_id=post_response.post_view.post.id,
                                body=fixture.format_body(
                                    home_team_form,
                                    away_team_form,
                                    lfc_lineup.format_lineup()
                                )+"\n\n~posted~ ~by~ ~lfcbot~"
                            )
                            logger.debug(f"updating post: {post_edit=}")
                            await edit_post(lemmy, post_edit)
                            return
                lineup_tasks.append(asyncio.create_task(update_task()))
    # if we haven't posted monday's discussion thread yet, make a post
    monday = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=datetime.utcnow().weekday())
    if not post_deduper.discussion_published(monday):
        logger.info(f"making discussion post for {monday}")
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
            for post_obj in posts_response.posts:
                is_discussion = post_obj.post.name.startswith(discussion_title)
                is_from_bot = post_obj.creator.name == lemmy.username
                if is_discussion and is_from_bot:
                    await pin_post(lemmy, post_obj.post.id, False)
            # post and pin new discussion post
            post_data = await publish_post(lemmy, post)
            await pin_post(lemmy, post_data.post_view.post.id, True)
        post_deduper.add_discussion(monday)
    # don't go to sleep until lineup tasks are complete
    if lineup_tasks:
        logger.debug(f"waiting for {len(lineup_tasks)} lineup tasks to complete")
        await asyncio.gather(*lineup_tasks)
    logger.info("lfcbot going to sleep")


if __name__ == "__main__":
    asyncio.run(main())
