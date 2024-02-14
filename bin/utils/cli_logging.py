from __future__ import annotations

import logging
import time
from pathlib import Path


custom_level_styles = {
    'debug': {'color': 'cyan'},
    'info': {'color': 'white'},
    'warning': {'color': 'yellow'},
    'error': {'color': 'red'},
    'critical': {'color': 'magenta'},
}


def setup_logger():
    # Create folders and copy config json when running via Akamai CLI
    Path('logs').mkdir(parents=True, exist_ok=True)
    Path('config').mkdir(parents=True, exist_ok=True)
    logging.Formatter.converter = time.gmtime

    logger = logging.getLogger()
    logging.basicConfig(filename='logs/cps.log', encoding='utf-8', level=logging.INFO)

    return logger


def countdown(time_sec: int, msg: str, logger=None):
    time_min = int(time_sec / 60)
    msg = f'{msg} {time_min} minutes count down'
    logger.critical(msg)
    while time_sec:
        mins, secs = divmod(time_sec, 60)
        timeformat = f'{mins:02d}:{secs:02d}'
        print(f'\t\t\t\t{timeformat}', end='\r')
        time.sleep(1)
        time_sec -= 1
