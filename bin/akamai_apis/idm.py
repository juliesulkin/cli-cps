# Techdocs reference
# https://techdocs.akamai.com/iam-api/reference/get-client-account-switch-keys
from __future__ import annotations

import logging

from akamai_apis.auth import AkamaiSession
from rich.console import Console
from utils.emojis import emojis as emoji


class IdentityAccessManagement(AkamaiSession):
    def __init__(self, logger: logging.Logger, args):
        super().__init__(args)
        self.baseurl = f'{self.baseurl}/identity-management/v3'
        self.headers = {'Accept': 'application/json'}
        self.logger = logger
        self.account_name = None

    def exit_condition(self):
        print()
        self.logger.error(f'invalid account switch key {self.account_switch_key}')
        console = Console(stderr=True)
        exit(
            console.print(f'{emoji.poop} [red]Error looking up account. Exiting....\n')
        )

    def search_account(self):
        url = f'{self.baseurl}/api-clients/self/account-switch-keys'
        if self.account_switch_key:
            params = {'search': self.account_switch_key.split(':')[0]}
        resp = self.s.get(url, params=params, headers=self.headers)

        if not resp.ok:
            self.exit_condition()
        else:
            try:
                self.account_name = resp.json()[0]['accountName']
                if not self.account_name:
                    self.exit_condition()
            except IndexError:
                self.exit_condition()
        self.logger.critical(f'Account Name: {self.account_name}')
        return self.account_name

    def __call__(self):
        return self.search_account()
