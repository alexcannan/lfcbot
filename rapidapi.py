"""
we use the rapidapi football api to get the fixtures for the next 5 games
"""

from datetime import datetime
import os
from typing import Optional, Union, List

from aiohttp import ClientSession
from pydantic import BaseModel, HttpUrl


RAPID_API_KEY = os.environ["RAPID_API_KEY"]


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

    def format_body(self,
                    home_team_form: Union[str, None],
                    away_team_form: Union[str, None],
                    lineup: Union[str, None],
                    ) -> str:
        """ formats match thread post body, given optional auxiliary information """
        lines = [
            "## Match Info",
            f"Round: {self.league.name} {self.league.round}",
            f"Referee: {self.fixture.referee}" if self.fixture.referee else "",
            f"Ground: {self.fixture.venue.name}, {self.fixture.venue.city}",
            f"Date: {self.fixture.date.strftime('%b %d, %Y')}",
            f"Kickoff time: {self.fixture.date.strftime('%H:%M %Z')}",
            "## Lineups",
            "Check back 30m before kickoff" if not lineup else lineup,
            "## Recent Form",
            f"#### {self.teams.home.name}\n\n{home_team_form}" if home_team_form else "",
            f"#### {self.teams.away.name}\n\n{away_team_form}" if away_team_form else "",
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


class Player(BaseModel):
    id: int
    name: str
    number: int
    pos: Optional[str]
    grid: Optional[str]

    @property
    def grid_row(self) -> Optional[int]:
        if self.grid is None:
            return None
        return int(self.grid.split(":")[0])

    @property
    def grid_col(self) -> Optional[int]:
        if self.grid is None:
            return None
        return int(self.grid.split(":")[1])


class Squad(BaseModel):
    player: Player


class Coach(BaseModel):
    id: int
    name: str
    photo: Optional[str]


class Lineup(BaseModel):
    team: Team
    coach: Coach
    formation: str
    startXI: List[Squad]
    substitutes: List[Squad]

    def format_lineup(self) -> str:
        """ formats lineup into a string """
        starting_strs: List[str] = []
        for grid_row in sorted(list(set([squad.player.grid_row or -1 for squad in self.startXI])), reverse=True):
            players = [squad.player for squad in self.startXI if squad.player.grid_row == grid_row]
            players.sort(key=lambda player: player.grid_col or -1)
            starting_strs.append(",  ".join([f"{player.name}" for player in players]) + ";")
        max_length = max(len(line) for line in starting_strs)
        starting_strs = [line.center(max_length) for line in starting_strs]
        starting_str = "\n\n".join(starting_strs)
        bench_str = "Bench: " + ", ".join([f"{squad.player.name}" for squad in self.substitutes])
        return "\n\n".join([starting_str, bench_str])


class LineupResponse(BaseModel):
    response: List[Lineup]

    def get_team_lineup(self, team_id: int) -> Lineup:
        """ get the lineup for a specific team """
        for lineup in self.response:
            if lineup.team.id == team_id:
                return lineup
        raise ValueError(f"no lineup for team {team_id}")


def format_form(fixtures: List[FixtureResponse], team_id: int) -> str:
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
    # fixtures come most recent first, reverse so it's chronological
    for fixture in reversed(fixtures):
        if fixture.fixture.status.short == "FT":
            if fixture.teams.home.id == team_id:
                if fixture.teams.home.winner:
                    form.append(f"W 🟢 [{fixture.goals.home}-{fixture.goals.away}] vs {fixture.teams.away.name}")
                elif fixture.teams.away.winner:
                    form.append(f"L 🔴 [{fixture.goals.home}-{fixture.goals.away}] vs {fixture.teams.away.name}")
                else:
                    form.append(f"D 🟡 [{fixture.goals.home}-{fixture.goals.away}] vs {fixture.teams.away.name}")
            elif fixture.teams.away.id == team_id:
                if fixture.teams.away.winner:
                    form.append(f"W 🟢 [{fixture.goals.away}-{fixture.goals.home}] at {fixture.teams.home.name}")
                elif fixture.teams.home.winner:
                    form.append(f"L 🔴 [{fixture.goals.away}-{fixture.goals.home}] at {fixture.teams.home.name}")
                else:
                    form.append(f"D 🟡 [{fixture.goals.away}-{fixture.goals.home}] at {fixture.teams.home.name}")
    form.append("```")
    return "\n".join(form)


async def get_previous_fixtures(team_id: int) -> List[FixtureResponse]:
    async with ClientSession() as session:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        querystring = {"team": team_id, "last": "8"}

        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

        async with session.get(url, headers=headers, params=querystring) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return [FixtureResponse(**match) for match in data["response"]]


async def get_next_fixtures(team_id: int) -> List[FixtureResponse]:
    async with ClientSession() as session:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        querystring = {"team": team_id, "next": "3"}

        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

        async with session.get(url, headers=headers, params=querystring) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return [FixtureResponse(**match) for match in data["response"]]


async def get_lineups(fixture_id: int) -> LineupResponse:
    async with ClientSession() as session:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/lineups"
        querystring = {"fixture": fixture_id}

        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        async with session.get(url, headers=headers, params=querystring) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return LineupResponse.model_validate(data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    lineup_parser = subparsers.add_parser("lineup")
    lineup_parser.add_argument("fixture_id", type=int)
    lineup_parser.add_argument("team_id", type=int)

    args = parser.parse_args()
    async def main():
        if args.command == "lineup":
            # with open("lfclineup.json", "r") as f:
            #     _lineup = LineupResponse.model_validate_json(f.read())
            lineups = await get_lineups(args.fixture_id)
            lineup = lineups.get_team_lineup(args.team_id)
            print(lineup.format_lineup())
    import asyncio
    asyncio.run(main())