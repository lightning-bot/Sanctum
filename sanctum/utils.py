from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Tuple

def serialize_datetime(json):
    for key, value in list(json.items()):
        if isinstance(value, datetime.datetime):
            json[key] = value.isoformat()


def build_update_query(columns: List[str]) -> Tuple[int, str]:
    idx = 0
    builder = []

    for idx, col in enumerate(columns, idx):
        builder.append(f'{col}=${idx + 1}')
        idx += 1

    return idx, ', '.join(builder)
