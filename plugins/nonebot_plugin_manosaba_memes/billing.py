from contextlib import asynccontextmanager

from utils import credit


@asynccontextmanager
async def production_charge(user_id: str, *, paid: bool = True):
    receipt = await credit.charge(user_id, credit.MANOSABA_MEMES_COST) if paid else None
    try:
        yield
    except BaseException:
        if receipt is not None:
            await credit.refund(receipt)
        raise
