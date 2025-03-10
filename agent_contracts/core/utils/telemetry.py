import json
import logging
import os
import uuid
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Dict, Optional

from appdirs import user_data_dir
from loguru import logger
from posthog import Posthog

_USER_DATA_DIR_NAME = "agent_contracts"
_DO_NOT_TRACK = "AGENT_CONTRACTS_DO_NOT_TRACK"
_DEBUG_TELEMETRY = "AGENT_CONTRACTS_DEBUG_TELEMETRY"
_USER_ID_PREFIX = "ac-"


@lru_cache(maxsize=1)
def _do_not_track() -> bool:
    return os.environ.get(_DO_NOT_TRACK, "false").lower() == "true"


@lru_cache(maxsize=1)
def _debug_telemetry() -> bool:
    return os.environ.get(_DEBUG_TELEMETRY, "false").lower() == "true"


@lru_cache(maxsize=1)
def _get_or_generate_uid() -> str:
    user_id_path = Path(user_data_dir(appname=_USER_DATA_DIR_NAME))
    user_id_path.mkdir(parents=True, exist_ok=True)
    uuid_filepath = user_id_path / "config.json"
    user_id = None
    if uuid_filepath.is_file():
        # try reading the file first
        try:
            user_id = json.load(open(uuid_filepath))["userid"]
        except Exception:
            pass
    if user_id is None:
        user_id = _USER_ID_PREFIX + uuid.uuid4().hex
        try:
            with open(uuid_filepath, "w") as f:
                json.dump({"userid": user_id}, f)
        except Exception:
            pass
    return user_id


class AnonymousTelemetry:
    def __init__(self):
        self.uid = _get_or_generate_uid()
        self._client = Posthog(
            "phc_mTBBHrxJkEGCKNBJKSgSh3b8YIQ2996HIFhhXYZqlN6",
            host="https://us.i.posthog.com",
            debug=_debug_telemetry(),
        )
        if _do_not_track():
            logger.debug("Telemetry is disabled")
            self._client.disabled = True

    def log_event(self, name: str, info: Dict[str, Any] = {}):
        if _do_not_track():
            return
        try:
            self._client.capture(
                distinct_id=self.uid, event=name, properties=info
            )
            print(f"Telemetry event: {self.uid} {name} {info}")
        except Exception as e:
            # This way it silences all thread level logging as well
            if _debug_telemetry():
                logging.debug(f"Telemetry error: {e}")


telemetry = AnonymousTelemetry()

def telemetry_event(name: Optional[str] = None, info: Dict[str, Any] = {}):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            event_name = name or args[0].__class__.__name__
            info["__qualname__"] = func.__qualname__
            telemetry.log_event(name=event_name, info=info)

            return func(*args, **kwargs)

        return wrapper

    return decorator
