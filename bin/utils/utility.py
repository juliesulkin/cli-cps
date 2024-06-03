from __future__ import annotations

import logging

import requests
import utils.emojis as emoji
from akamai_apis.cps import Cps


class utility():
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.hostnames = []
        self.waiting = f'{emoji.clock} waiting'
        self.s = requests.Session()
        self.max_column_width = 20
        self.column_width = 30

    def list_wrapper():
        cps = Cps()
        print(cps)
        pass
