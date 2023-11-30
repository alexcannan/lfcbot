"""
we use the rapidapi football api to get the fixtures for the next 5 games
"""

from datetime import datetime
import json
import os
from typing import Optional

from aiohttp import ClientSession
from pydantic import BaseModel, HttpUrl, NaiveDatetime


RADID_API_KEY = os.environ["RAPID_API_KEY"]


class Status(BaseModel):
    long: str
    short: str


class Venue(BaseModel):
    city: str
    name: str


class Fixture(BaseModel):
    date: datetime
    id: int
    periods: dict  # Keeping this as a simple dict since you did not specify a need for specific validation
    referee: Optional[str] = None
    status: Status
    timestamp: int
    timezone: str
    venue: Venue


class League(BaseModel):
    country: str
    flag: Optional[HttpUrl] = None
    id: int
    logo: HttpUrl
    name: str
    round: str
    season: int


class Team(BaseModel):
    id: int
    logo: HttpUrl
    name: str
    winner: Optional[bool] = None


class Teams(BaseModel):
    away: Team
    home: Team


class FixtureResponse(BaseModel):
    fixture: Fixture
    league: League
    teams: Teams

    def format_title(self) -> str:
        return f"[Match Thread] {self.teams.home.name} vs {self.teams.away.name} | {self.league.name} {self.league.round} | {self.fixture.date.strftime('%b %d, %Y')}"

    def format_body(self) -> str:
        lines = [
            f"*** {self.league.name} {self.league.round} ***",
            f"Referee: {self.fixture.referee}" if self.fixture.referee else "",
            f"Ground: {self.fixture.venue.name}, {self.fixture.venue.city}",
            f"Date: {self.fixture.date.strftime('%b %d, %Y')}",
            f"Kickoff time: {self.fixture.date.strftime('%H:%M %Z')}",
        ]
        return "\n\n".join([line for line in lines if line])


async def get_fixtures(team_id: int) -> list[FixtureResponse]:
    async with ClientSession() as session:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        querystring = {"team": team_id, "next": "3"}

        headers = {
            "X-RapidAPI-Key": RADID_API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

        async with session.get(url, headers=headers, params=querystring) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return [FixtureResponse(**match) for match in data["response"]]
