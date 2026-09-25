import base64

from nonebot import get_driver, on_command, require
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.params import Command, CommandArg
from nonebot.plugin import PluginMetadata

require('nonebot_plugin_alconna')

from utils import credit
from utils.messaging import send_group_with_fallback
from utils.observability import get_logger
from utils.superuser_2fa import is_verified_superuser

from . import rendering
from .account_admin import AccountAdmin
from .credential_events import install, scrub_event
from .protocol import QueryError
from .runtime import run_operation, run_sync, shutdown, start_maintenance
from .service import QueryService, parse_command
from .whitelist import GroupWhitelist, group_id


__plugin_meta__ = PluginMetadata(
    name='吉星派对',
    description='以游戏原版素材查询玩家公开资料与对局',
    usage='发送“astral help”查看图片帮助；群内发送 astral watch 观战码 设置对局，astral card 查看手牌，astral unwatch 停止观战',
    type='application',
    supported_adapters={'~onebot.v11'},
)

logger = get_logger('吉星派对')
service = QueryService(run_sync=run_sync)
accounts = AccountAdmin(service.directory / 'config.json', service._lock, run_sync)
group_whitelist = GroupWhitelist(service.directory / 'group_whitelist.json')
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


async def prepare_whitelist(text, verified):
    try:
        if not verified:
            raise QueryError('需要超级用户权限及当前双重验证码：astral 验证码 whitelist 群号')
        parts = text.split()
        if len(parts) != 1:
            raise QueryError('指令格式：astral 验证码 whitelist 群号')
        group = group_id(parts[0])
        added = await run_sync(group_whitelist.add, group)
        lines = [f'已将群 {group} 加入吉星派对白名单' if added else f'群 {group} 已在吉星派对白名单中']
    except QueryError as error:
        lines = [str(error)]
    except Exception as error:
        logger.error(f'群白名单管理未完成（{type(error).__name__}），请检查数据文件与目录权限')
        lines = ['群白名单操作未完成，请稍后重试或检查数据文件']
    return await run_sync(rendering.render_notice, '群白名单管理', lines)


async def prepare(text, user, *, group=None, raise_errors=False):
    try:
        view = await service.handle(text, user, group=group)
    except QueryError as error:
        if raise_errors:
            raise
        view = {'kind': 'notice', 'title': '查询提示', 'lines': [str(error)]}
    except Exception as error:
        if raise_errors:
            raise
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
    if kind == 'hands':
        return await run_sync(rendering.render_hands, view['snapshot'])
    return await run_sync(rendering.render_detail, view['snapshot'])


def image_message(payload):
    return MessageSegment.image('base64://' + base64.b64encode(payload).decode('ascii'))


async def send_image(bot, event, payload):
    message = image_message(payload)
    if isinstance(event, GroupMessageEvent):
        result = await send_group_with_fallback(message, group_id=event.group_id, preferred=bot, tag='吉星派对图片')
        return result.sent
    await bot.send(event, message)
    return True


async def query_and_send(bot, event, text):
    receipt = None
    delivered = False
    succeeded = False
    try:
        try:
            command = parse_command(text)
            group = event.group_id if isinstance(event, GroupMessageEvent) else None
            if command.action in {'观战', '手牌', '停止观战'} and group is None:
                raise QueryError('watch、card 和 unwatch 仅支持群聊，请在需要观战的群内使用')
            if command.action in {'资料', '战绩', '对局', '手牌'}:
                receipt = await credit.charge(event.get_user_id(), credit.ASTRAL_PARTY_QUERY_COST)
            payload = await prepare(text, 'qq:' + event.get_user_id(), group=group, raise_errors=True)
            succeeded = True
        except (QueryError, credit.ChargeRejected) as error:
            payload = await run_sync(rendering.render_notice, '查询提示', [str(error)])
        except Exception as error:
            logger.error(f'查询处理失败（{type(error).__name__}），请检查插件配置与资源')
            payload = await run_sync(rendering.render_notice, '查询提示', ['查询暂时无法完成，请稍后重试或联系管理员'])
        sent = await send_image(bot, event, payload)
        delivered = succeeded and sent
    finally:
        if not delivered:
            await credit.refund(receipt)


@matcher.handle()
async def handle(bot: Bot, event: MessageEvent, command: tuple = Command(), args: Message = CommandArg()):
    if isinstance(event, GroupMessageEvent):
        try:
            if not await run_operation(run_sync(group_whitelist.allows, event.group_id)):
                return
        except QueryError as error:
            logger.warning(str(error))
            return
        except Exception as error:
            logger.error(f'群白名单检查失败（{type(error).__name__}），已停止处理群聊指令')
            return
    text = command[-1] + ' ' + args.extract_plain_text()
    try:
        account = args.extract_plain_text().split(maxsplit=1)
        if account and account[0] == 'whitelist':
            action = account[1] if len(account) > 1 else ''
            payload = await run_operation(prepare_whitelist(action, is_verified_superuser(event)))
        elif account and account[0] == 'account':
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
            await run_operation(query_and_send(bot, event, text))
            return
    except QueryError:
        return
    await send_image(bot, event, payload)
