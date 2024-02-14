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
