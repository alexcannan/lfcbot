"""
we use the rapidapi football api to get the fixtures for the next 5 games
"""

from datetime import datetime
import json
import os
from typing import Optional, Union

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


class Goals(BaseModel):
    away: Optional[int]
    home: Optional[int]

class FixtureResponse(BaseModel):
    fixture: Fixture
    league: League
    teams: Teams
    goals: Goals

    def format_title(self) -> str:
        return f"[Match Thread] {self.teams.home.name} vs {self.teams.away.name} | {self.league.name} {self.league.round} | {self.fixture.date.strftime('%b %d, %Y')}"

    def format_body(self, home_team_form: Union[str, None], away_team_form: Union[str, None]) -> str:
        lines = [
            f"*** {self.league.name} {self.league.round} ***",
            f"Referee: {self.fixture.referee}" if self.fixture.referee else "",
            f"Ground: {self.fixture.venue.name}, {self.fixture.venue.city}",
            f"Date: {self.fixture.date.strftime('%b %d, %Y')}",
            f"Kickoff time: {self.fixture.date.strftime('%H:%M %Z')}",
            f"{self.teams.home.name} recent form:\n{home_team_form}" if home_team_form else "",
            f"{self.teams.away.name} recent form:\n{away_team_form}" if away_team_form else "",
        ]
        return "\n\n".join([line for line in lines if line])

    def winner_id(self) -> Optional[int]:
        """ return the team id of the winner, or None if no winner """
        if self.fixture.status.short == "FT":
            if self.teams.home.winner:
                return self.teams.home.id
            elif self.teams.away.winner:
                return self.teams.away.id
        return None


def format_form(fixtures: list[FixtureResponse], team_id: int) -> str:
    """
    formats a list of fixtures into a form string for a specific team

    Creates format:
    ```
    W [3-1] vs Chelsea
    D [1-1] at Newcastle
    L [0-1] vs Arsenal
    ```
    """
    form = ["```"]
    for fixture in fixtures:
        if fixture.fixture.status.short == "FT":
            if fixture.teams.home.id == team_id:
                if fixture.teams.home.winner:
                    form.append(f"W [{fixture.goals.home}-{fixture.goals.away}] vs {fixture.teams.away.name}")
                elif fixture.teams.away.winner:
                    form.append(f"L [{fixture.goals.home}-{fixture.goals.away}] vs {fixture.teams.away.name}")
                else:
                    form.append(f"D [{fixture.goals.home}-{fixture.goals.away}] vs {fixture.teams.away.name}")
            elif fixture.teams.away.id == team_id:
                if fixture.teams.away.winner:
                    form.append(f"W [{fixture.goals.away}-{fixture.goals.home}] at {fixture.teams.home.name}")
                elif fixture.teams.home.winner:
                    form.append(f"L [{fixture.goals.away}-{fixture.goals.home}] at {fixture.teams.home.name}")
                else:
                    form.append(f"D [{fixture.goals.away}-{fixture.goals.home}] at {fixture.teams.home.name}")
    form.append("```")
    return "\n".join(form)


async def get_previous_fixtures(team_id: int) -> list[FixtureResponse]:
    async with ClientSession() as session:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        querystring = {"team": team_id, "last": "8"}

        headers = {
            "X-RapidAPI-Key": RADID_API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

        async with session.get(url, headers=headers, params=querystring) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return [FixtureResponse(**match) for match in data["response"]]


async def get_next_fixtures(team_id: int) -> list[FixtureResponse]:
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
