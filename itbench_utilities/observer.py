import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel

from itbench_utilities.app.utils import get_timestamp

logger = logging.getLogger(__name__)


class EventData(BaseModel):
    event: str
    timestamp: Optional[datetime] = None
    data: Dict[str, Any]


class Observer:
    def __init__(self):
        self.callbacks = []

    def register(self, callback: Callable[[EventData], None]):
        self.callbacks.append(callback)

    def notify(self, event: str, data: Dict[str, Any]):
        for callback in self.callbacks:
            try:
                event_data = EventData(event=event, data=data, timestamp=get_timestamp())
                callback(event_data)
            except Exception as e:
                logger.warning(f"Callback {callback.__name__} failed with exception for evant {event}: {e}")


def custom_serializer(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return obj.as_posix()
    raise TypeError(f"Type {type(obj)} not serializable")


def gen_json_logging_callback(logger: logging.Logger) -> Callable[[EventData], None]:
    def json_logging(event_data: EventData):
        json_str = json.dumps(event_data.data, default=custom_serializer)
        logger.info(json_str)

    return json_logging


DEFAULT_OBSERVER = Observer()
DEFAULT_OBSERVER.register(gen_json_logging_callback(logger))
