from dataclasses import dataclass

from utils import credits


KOKOMI_WOWS_COST = 10
TURTLE_SOUP_START_COST = 300
TAROT_COST = 10
TODAY_WAIFU_COST = 10
TODAY_WAIFU_FORCE_COST = 100
WHATEAT_PIC_COST = 10
NETEASE_MUSIC_COST = 10
PACKPIC_COST = 10
MEMES_COST = 10
MEME_STICKERS_COST = 10
POINT_SALAD_START_COST = 200
CHESS_START_COST = 100
CCHESS_START_COST = 100
MINESWEEPER_START_COST = 100
WISH_BOTTLE_COST = 10
ATTRWHICH_COST = 10


class ChargeRejected(RuntimeError):
    pass


@dataclass
class ChargeReceipt:
    user_id: str
    amount: int
    refunded: bool = False


async def charge(user_id: str, amount: int) -> ChargeReceipt:
    normalized = str(user_id).strip()
    if not await credits.has_account(normalized):
        raise ChargeRejected('❌ 账号未注册！\n请先签到一次！\n发送"签到"即可')
    try:
        await credits.debit(normalized, amount)
    except credits.InsufficientCreditsError:
        balance = await credits.get_balance(normalized)
        raise ChargeRejected(
            f"❌ 你的积分余额不足！\n现有积分：{balance}\n需要积分：{amount}"
        ) from None
    return ChargeReceipt(normalized, amount)


async def refund(receipt: ChargeReceipt | None) -> None:
    if receipt is None or receipt.refunded:
        return
    receipt.refunded = True
    try:
        await credits.credit(receipt.user_id, receipt.amount)
    except Exception:
        receipt.refunded = False
        raise


async def charge_or_finish(matcher, user_id: str, amount: int) -> ChargeReceipt:
    try:
        return await charge(user_id, amount)
    except ChargeRejected as error:
        await matcher.finish(str(error))
        raise
