from __future__ import annotations

import logging
from pathlib import Path

import requests
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc

logger = logging.getLogger(__name__)


class AkamaiSession:

    def __init__(self, args):
        self.headers = {'PAPI-Use-Prefixes': 'true',
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'}

        self.edgerc = EdgeRc(f'{str(Path.home())}/.edgerc')
        self.section = args.section if args.section else 'default'
        self.host = self.edgerc.get(self.section, 'host')
        self.host = f'https://{self.host}'
        self.baseurl = self.host
        self.account_switch_key = args.account_switch_key
        self._params = {}

        self.s = requests.Session()
        self.s.auth = EdgeGridAuth.from_edgerc(self.edgerc, self.section)

    @property
    def params(self) -> dict:
        self._params.update({'accountSwitchKey': self.account_switch_key}) if self.account_switch_key else {}
        return self._params

    @params.setter
    def params(self, new_dict):
        self._params.update(new_dict)
