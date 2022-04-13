"""
Global setting of Binance Grid Trader.
"""

from logging import CRITICAL, INFO
from typing import Dict, Any

from .utility import load_json

SETTINGS: Dict[str, Any] = {
    "font.family": "Arial",
    "font.size": 12,
    "order_update_interval": 120,
    "position_update_interval": 120,
    "account_update_interval": 120,
    "log.active": True,
    "log.level": INFO,
    "log.console": True,
    "log.file": True
}

# Load global setting from json file.
SETTING_FILENAME: str = "vt_setting.json"
SETTINGS.update(load_json(SETTING_FILENAME))


def get_settings(prefix: str = "") -> Dict[str, Any]:
    prefix_length = len(prefix)
    return {k[prefix_length:]: v for k, v in SETTINGS.items() if k.startswith(prefix)}
