from __future__ import annotations

import logging
import sys
from configparser import NoSectionError
from pathlib import Path

import requests
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class AkamaiSession:
    def __init__(self, args, account_switch_key: str | None = None):

        if args.edgerc is None:
            self.edgerc_file = EdgeRc(f'{str(Path.home())}/.edgerc')
        else:
            self.edgerc_file = EdgeRc(f'{str(Path(args.edgerc))}')
        self.section = args.section if args.section else 'default'

        self.account_switch_key = account_switch_key if account_switch_key else args.account_switch_key
        self._params = {}
        self._params = {'accountSwitchKey': self.account_switch_key}

        if 'contract' in args:
            self.contract_id = args.contract
        else:
            self.contract_id = 0

        try:
            self.host = self.edgerc_file.get(self.section, 'host')
            self.base_url = f'https://{self.host}'
            self.session = requests.Session()
            self.session.auth = EdgeGridAuth.from_edgerc(self.edgerc_file, self.section)
        except NoSectionError:
            sys.exit(logger.error(f'edgerc section "{self.section}" not found'))

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
