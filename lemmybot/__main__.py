import asyncio

from lemmybot import LemmyAuthWrapper

async def main():
    # test lemmy login
    async with LemmyAuthWrapper() as lemmy:
        print(f"authentication successful for {lemmy.username}")


asyncio.run(main())