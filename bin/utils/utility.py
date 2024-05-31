from __future__ import annotations

import logging

import requests
import utils.emojis as emoji


class utility():
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.hostnames = []
        self.waiting = f'{emoji.clock} waiting'
        self.s = requests.Session()
        self.max_column_width = 20
        self.column_width = 30
