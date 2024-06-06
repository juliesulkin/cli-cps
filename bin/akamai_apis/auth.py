from __future__ import annotations

import sys
from configparser import NoSectionError
from pathlib import Path

import requests
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AkamaiSession:
    def __init__(self, args, logger):
        if args.edgerc is None:
            self.edgerc_file = EdgeRc(f'{str(Path.home())}/.edgerc')
        else:
            self.edgerc_file = EdgeRc(f'{str(Path(args.edgerc))}')
        self.account_switch_key = args.account_switch_key if args.account_switch_key else None
        try:
            self.contract_id = args.contract if args.contract else 0
        except Exception:
            self.contract_id = 0

        self.section = args.section if args.section else 'default'
        self.logger = logger
        self._params = {}

        try:
            self.host = self.edgerc_file.get(self.section, 'host')
            self.base_url = f'https://{self.host}'
            self.session = requests.Session()
            self.session.auth = EdgeGridAuth.from_edgerc(self.edgerc_file, self.section)
        except NoSectionError:
            sys.exit(self.logger.error(f'edgerc section "{self.section}" not found'))

        retry_strategy = Retry(total=3,
                               backoff_factor=1,
                               status_forcelist=[429, 500, 502, 503, 504],
                               )

        adapter_with_retries = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter_with_retries)
        self.session.mount('https://', adapter_with_retries)

    @property
    def params(self) -> dict:
        self._params.update({'accountSwitchKey': self.account_switch_key}) if self.account_switch_key else {}
        return self._params

    @params.setter
    def params(self, new_dict):
        self._params.update(new_dict)


if __name__ == '__main__':
    pass
