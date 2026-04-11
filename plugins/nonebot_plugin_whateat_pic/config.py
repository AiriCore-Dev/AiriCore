import time
from typing import Optional
from pydantic import Extra, BaseModel

class Config(BaseModel, extra=Extra.ignore):
    whateat_cd: Optional[int] = 20
    whateat_max: Optional[int] = 20
