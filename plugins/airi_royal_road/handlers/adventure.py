from ..base.matchers import adventure, choice, partner, recall
from ..service import service
from ..render import output
from nonebot.adapters.onebot.v11 import MessageEvent


@adventure.handle()
async def handle_adventure(event: MessageEvent):
    try:
        response = await service.start_or_resume(str(event.get_user_id()))
    except ValueError as exc:
        await adventure.finish(output.render_response(str(exc)))
    await adventure.finish(output.text_fallback(response.fallback_text) + response.image)


@choice.handle()
async def handle_choice(event: MessageEvent):
    text = event.get_plaintext().strip().split()
    try:
        response = await service.choose(str(event.get_user_id()), int(text[-1]))
    except (ValueError, IndexError):
        await choice.finish(output.render_response("当前还没有可确认的征途选项"))
    await choice.finish(output.text_fallback(response.fallback_text) + response.image)


@partner.handle()
async def handle_partner(event: MessageEvent):
    try:
        response = await service.partner_talk(str(event.get_user_id()), event.get_plaintext().split(" ", 1)[1])
    except (ValueError, IndexError):
        await partner.finish(output.render_response("伙伴对话格式无效"))
    await partner.finish(output.text_fallback(response.fallback_text) + response.image)


@recall.handle()
async def handle_recall(event: MessageEvent):
    try:
        historical_date = event.get_plaintext().strip().split()[-1]
        response = await service.recall(str(event.get_user_id()), historical_date)
    except (ValueError, IndexError) as exc:
        await recall.finish(output.render_response(str(exc)))
    await recall.finish(output.text_fallback(response.fallback_text) + response.image)
