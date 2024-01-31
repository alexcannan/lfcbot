import argparse
import asyncio
from pathlib import Path
import subprocess
import tempfile

from lemmybot import LemmyAuthWrapper
from lemmybot.post import get_post, edit_post, PostEdit

async def main(args):
    async with LemmyAuthWrapper() as lemmy:
        print(f"authentication successful for {lemmy.username}")
        if args.subcommand == "edit":
            print(f"editing post {args.post_id}")
            post_response = await get_post(lemmy, args.post_id)
            post = post_response.post_view.post
            assert post.body and post.id, f"post {post} is not valid"
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpfile = Path(f"{tmpdir}/post.md")
                tmpfile.write_text(post.body)
                subprocess.run(["vim", tmpfile])
                new_post = PostEdit(
                    post_id=post.id,
                    body=tmpfile.read_text(),
                )
            edit_response = await edit_post(lemmy, new_post)
            print(f"edit successful -- {edit_response}")


parser = argparse.ArgumentParser(description="basic lemmy cli tooling")
subcommands = parser.add_subparsers(dest="subcommand", required=True)

edit_parser = subcommands.add_parser("edit", help="edit a post")
edit_parser.add_argument("post_id", type=int, help="id of the post to edit")

args = parser.parse_args()

asyncio.run(main(args))
