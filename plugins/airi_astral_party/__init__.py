import base64

from nonebot import get_driver, on_command, require
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment
from nonebot.params import Command, CommandArg
from nonebot.plugin import PluginMetadata

require('nonebot_plugin_alconna')

from utils.messaging import send_group_with_fallback
from utils.observability import get_logger

from . import rendering
from .protocol import QueryError
from .runtime import run_operation, run_sync, shutdown
from .service import QueryService


__plugin_meta__ = PluginMetadata(
    name='吉星派对',
    description='以游戏原版素材查询玩家公开资料与对局',
    usage='发送“吉星帮助”查看图片帮助；吉星绑定 UID、吉星资料、吉星战绩、吉星对局 序号',
    type='application',
    supported_adapters={'~onebot.v11'},
)

logger = get_logger('吉星派对')
service = QueryService(run_sync=run_sync)
matcher = on_command('吉星', aliases={'吉星派对', '吉星帮助', '吉星绑定', '吉星解绑',
                                    '吉星资料', '吉星战绩', '吉星对局', '吉星状态'}, block=True)
get_driver().on_shutdown(shutdown)


async def prepare(text, user):
    try:
        view = await service.handle(text, user)
    except QueryError as error:
        view = {'kind': 'notice', 'title': '查询提示', 'lines': [str(error)]}
    except Exception as error:
        logger.error(f'查询处理失败（{type(error).__name__}），请检查插件配置与资源')
        view = {'kind': 'notice', 'title': '查询提示', 'lines': ['查询暂时无法完成，请稍后重试或联系管理员']}
    kind = view['kind']
    if kind == 'help':
        return await run_sync(rendering.render_help)
    if kind == 'notice':
        return await run_sync(rendering.render_notice, view['title'], view['lines'])
    if kind == 'profile':
        return await run_sync(rendering.render_profile, view['snapshot'])
    if kind == 'records':
        return await run_sync(rendering.render_records, view['snapshot'], view['page'])
    return await run_sync(rendering.render_detail, view['snapshot'])


def image_message(payload):
    return MessageSegment.image('base64://' + base64.b64encode(payload).decode('ascii'))


@matcher.handle()
async def handle(bot: Bot, event: MessageEvent, command: tuple = Command(), args: Message = CommandArg()):
    text = command[-1] + ' ' + args.extract_plain_text()
    try:
        payload = await run_operation(prepare(text, 'qq:' + event.get_user_id()))
    except QueryError:
        return
    message = image_message(payload)
    if isinstance(event, GroupMessageEvent):
        await send_group_with_fallback(message, group_id=event.group_id, preferred=bot, tag='吉星派对图片')
    else:
        await bot.send(event, message)
