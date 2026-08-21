from ..base.matchers import vote, vote_choice
from ..render import output
from ..service import service
from nonebot.adapters.onebot.v11 import MessageEvent


@vote.handle()
async def handle_vote(event: MessageEvent):
    try:
        response = await service.vote_view(str(event.get_user_id()))
    except ValueError as exc:
        await vote.finish(output.render_response(str(exc)))
    await vote.finish(output.text_fallback(response.fallback_text) + response.image)


@vote_choice.handle()
async def handle_vote_choice(event: MessageEvent):
    try:
        choice = int(event.get_plaintext().strip().split()[-1])
        response = await service.vote_view(str(event.get_user_id()), choice)
    except (ValueError, IndexError):
        await vote_choice.finish(output.render_response("当前没有可用的投票选项"))
    await vote_choice.finish(output.text_fallback(response.fallback_text) + response.image)
