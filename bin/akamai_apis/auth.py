from __future__ import annotations

import logging
import sys
from configparser import NoSectionError
from pathlib import Path

import requests
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc


logger = logging.getLogger(__name__)


class AkamaiSession:
    def __init__(self,
                 account_switch_key: str | None = None,
                 section: str | None = None,
                 edgerc: str | None = None,
                 cookies: str | None = None,
                 contract_id: int | None = None,
                 group_id: int | None = None):

        self.edgerc_file = edgerc if edgerc else EdgeRc(f'{str(Path.home())}/.edgerc')
        self.account_switch_key = account_switch_key if account_switch_key else None
        self.contract_id = contract_id if contract_id else None
        self.group_id = group_id if group_id else None
        self.section = section if section else 'default'
        self.cookies = self.update_acc_cookie(cookies)

        try:
            self.host = self.edgerc_file.get(self.section, 'host')
            self.base_url = f'https://{self.host}'
            self.session = requests.Session()
            self.session.auth = EdgeGridAuth.from_edgerc(self.edgerc_file, self.section)
        except NoSectionError:
            sys.exit(logger.error(f'edgerc section "{self.section}" not found'))

    @property
    def params(self) -> dict:
        return {'accountSwitchKey': self.account_switch_key} if self.account_switch_key else {}

    def form_url(self, url: str) -> str:
        account_switch_key = f'&accountSwitchKey={self.account_switch_key}' if self.account_switch_key is not None else ''
        if '?' in url:
            return f'{url}{account_switch_key}'
        else:
            account_switch_key = account_switch_key.translate(account_switch_key.maketrans('&', '?'))
            return f'{url}{account_switch_key}'

    def update_account_key(self, account_key: str) -> None:
        self.account_switch_key = account_key


if __name__ == '__main__':
    pass
