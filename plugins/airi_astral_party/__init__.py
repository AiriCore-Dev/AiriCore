import base64

from nonebot import get_driver, on_command, require
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.params import Command, CommandArg
from nonebot.plugin import PluginMetadata

require('nonebot_plugin_alconna')

from utils.messaging import send_group_with_fallback
from utils.observability import get_logger
from utils.superuser_2fa import is_verified_superuser

from . import rendering
from .account_admin import AccountAdmin
from .credential_events import install, scrub_event
from .protocol import QueryError
from .runtime import run_operation, run_sync, shutdown, start_maintenance
from .service import QueryService


__plugin_meta__ = PluginMetadata(
    name='吉星派对',
    description='以游戏原版素材查询玩家公开资料与对局',
    usage='发送“astral help”查看图片帮助；astral bind UID、astral me、astral UID recent、astral UID battle 序号',
    type='application',
    supported_adapters={'~onebot.v11'},
)

logger = get_logger('吉星派对')
service = QueryService(run_sync=run_sync)
accounts = AccountAdmin(service.directory / 'config.json', service._lock, run_sync)
matcher = on_command('astral', force_whitespace=True, block=True)
install()
get_driver().on_shutdown(shutdown)


@get_driver().on_startup
async def startup():
    start_maintenance(accounts.maintain)


async def prepare_account(text, private, verified, credentials, recall_failed=False):
    try:
        view = await accounts.handle(text, private, verified, credentials)
    except QueryError as error:
        view = accounts.notice('账号管理提示', [str(error)])
    except Exception as error:
        logger.error(f'账号管理未完成（{type(error).__name__}），未输出凭据')
        view = accounts.notice('账号管理提示', ['操作未完成，请检查网络或配置，原凭据不会出现在回复中'])
    if recall_failed:
        view['lines'] = list(view['lines']) + ['输入消息未能撤回，请自行删除；上游仍可能留存记录']
    return await run_sync(rendering.render_notice, view['title'], view['lines'])


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
        account = args.extract_plain_text().split(maxsplit=1)
        if account and account[0] == 'account':
            scrub_event(event)
            credentials = getattr(event, '_astral_credentials', None)
            event._astral_credentials = None
            action = account[1] if len(account) > 1 else 'help'
            recall_failed = False
            if action.split(maxsplit=1)[0] == 'login':
                action = 'login'
                try:
                    await bot.delete_msg(message_id=event.message_id)
                except Exception:
                    recall_failed = True
            payload = await run_operation(prepare_account(action, isinstance(event, PrivateMessageEvent),
                                                          is_verified_superuser(event), credentials, recall_failed))
            credentials = None
        else:
            payload = await run_operation(prepare(text, 'qq:' + event.get_user_id()))
    except QueryError:
        return
    message = image_message(payload)
    if isinstance(event, GroupMessageEvent):
        await send_group_with_fallback(message, group_id=event.group_id, preferred=bot, tag='吉星派对图片')
    else:
        await bot.send(event, message)
