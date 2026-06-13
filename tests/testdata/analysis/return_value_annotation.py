# ruff: noqa
from typing import Optional
class Item: pass
def get_item(x: int) -> Optional[Item]:
    return None  # annotation means this IS a ReturnValue
