"""Technical locations only: never format exception messages, locals or SQL parameters."""

import json
import logging
import re
import traceback
from pathlib import Path


def log_failure(exc, **correlation):
    frames = traceback.extract_tb(exc.__traceback__)
    cause = getattr(exc, "orig", None) or exc.__cause__
    sqlstate = getattr(cause, "sqlstate", None)
    logging.getLogger("deliveryguard").error(
        json.dumps(
            {
                "event": "unexpected_error",
                **correlation,
                "error_type": f"{type(exc).__module__}.{type(exc).__name__}",
                "cause_type": f"{type(cause).__module__}.{type(cause).__name__}" if cause else None,
                "sqlstate": sqlstate
                if isinstance(sqlstate, str) and re.fullmatch(r"[0-9A-Z]{5}", sqlstate)
                else None,
                "locations": [
                    {"file": Path(f.filename).name, "function": f.name, "line": f.lineno}
                    for f in frames
                    if Path(f.filename).parent.name == "deliveryguard" or f in frames[-6:]
                ],
            }
        )
    )
