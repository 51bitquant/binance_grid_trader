"""
General utility functions.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Tuple
from decimal import Decimal, ROUND_DOWN

from .constant import Exchange
from .object import OrderData, Status, Direction


log_formatter = logging.Formatter('[%(asctime)s] %(message)s')


def extract_vt_symbol(vt_symbol: str) -> Tuple[str, Exchange]:
    """
    :return: (symbol, exchange)
    """
    symbol, exchange_str = vt_symbol.split(".")
    return symbol, Exchange(exchange_str)


def generate_vt_symbol(symbol: str, exchange: Exchange) -> str:
    """
    return vt_symbol
    """
    return f"{symbol}.{exchange.value}"


def _get_trader_dir(temp_name: str) -> Tuple[Path, Path]:
    """
    Get path where trader is running in.
    """
    cwd = Path.cwd()
    temp_path = cwd.joinpath(temp_name)

    # If .vntrader folder exists in current working directory,
    # then use it as trader running path.
    if temp_path.exists():
        return cwd, temp_path

    # Otherwise use home path of system.
    home_path = Path.home()
    temp_path = home_path.joinpath(temp_name)

    # Create .vntrader folder under home path if not exist.
    if not temp_path.exists():
        temp_path.mkdir()

    return home_path, temp_path


TRADER_DIR, TEMP_DIR = _get_trader_dir("gridtrader")
sys.path.append(str(TRADER_DIR))


def get_file_path(filename: str) -> Path:
    """
    Get path for temp file with filename.
    """
    return TEMP_DIR.joinpath(filename)


def get_folder_path(folder_name: str) -> Path:
    """
    Get path for temp folder with folder name.
    """
    folder_path = TEMP_DIR.joinpath(folder_name)
    if not folder_path.exists():
        folder_path.mkdir()
    return folder_path


def get_icon_path(filepath: str, ico_name: str) -> str:
    """
    Get path for icon file with ico name.
    """
    ui_path = Path(filepath).parent
    icon_path = ui_path.joinpath("ico", ico_name)
    return str(icon_path)


def load_json(filename: str) -> dict:
    """
    Load data from json file in temp path.
    """
    filepath = get_file_path(filename)

    if filepath.exists():
        with open(filepath, mode="r", encoding="UTF-8") as f:
            data = json.load(f)
        return data
    else:
        save_json(filename, {})
        return {}


def save_json(filename: str, data: dict) -> None:
    """
    Save data into json file in temp path.
    """
    filepath = get_file_path(filename)
    with open(filepath, mode="w+", encoding="UTF-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


def round_to(value: float, target: Decimal) -> Decimal:
    """
    Round price to price tick value.
    """
    value = Decimal(str(value))
    rounded = value.quantize(target)
    return rounded

def floor_to(value: float, target: Decimal) -> Decimal:
    """
    Similar to math.floor function, but to target float number.
    """
    value = Decimal(str(value))
    result = value.quantize(target, rounding=ROUND_DOWN)

    return result

def virtual(func: Callable) -> Callable:
    """
    mark a function as "virtual", which means that this function can be override.
    any base class should use this or @abstractmethod to decorate all functions
    that can be (re)implemented by subclasses.
    """
    return func


file_handlers: Dict[str, logging.FileHandler] = {}


def _get_file_logger_handler(filename: str) -> logging.FileHandler:
    handler = file_handlers.get(filename, None)
    if handler is None:
        handler = logging.FileHandler(filename)
        file_handlers[filename] = handler  # Am i need a lock?
    return handler


def get_file_logger(filename: str) -> logging.Logger:
    """
    return a logger that writes records into a file.
    """
    logger = logging.getLogger(filename)
    handler = _get_file_logger_handler(filename)  # get singleton handler.
    handler.setFormatter(log_formatter)
    logger.addHandler(handler)  # each handler will be added only once.
    return logger


class GridPositionCalculator(object):
    """
    用来计算网格头寸的平均价格
    Use for calculating the grid position's average price.

    """

    def __init__(self):
        self.pos = 0
        self.avg_price = 0

    def update_position(self, order: OrderData):
        if order.status != Status.ALLTRADED:
            return

        previous_pos = self.pos
        previous_avg = self.avg_price

        volume = float(order.volume)
        price = float(order.price)

        if order.direction == Direction.LONG:

            self.pos += volume

            if self.pos == 0:
                self.avg_price = 0
            else:

                if previous_pos == 0:
                    self.avg_price = price

                elif previous_pos > 0:
                    self.avg_price = (previous_pos * previous_avg + volume * price) / abs(self.pos)

                elif previous_pos < 0 < self.pos:
                    self.avg_price = price


        elif order.direction == Direction.SHORT:
            self.pos -= volume

            if self.pos == 0:
                self.avg_price = 0
            else:

                if previous_pos == 0:
                    self.avg_price = price

                elif previous_pos < 0:
                    self.avg_price = (abs(previous_pos) * previous_avg + volume * price) / abs(self.pos)

                elif previous_pos > 0 > self.pos:
                    self.avg_price = price