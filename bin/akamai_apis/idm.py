# Techdocs reference
# https://techdocs.akamai.com/iam-api/reference/get-client-account-switch-keys
from __future__ import annotations

import logging

import utils.emojis as emoji
from akamai_apis.auth import AkamaiSession
from rich.console import Console


class IdentityAccessManagement(AkamaiSession):
    def __init__(self, args, logger: logging.Logger = None):
        super().__init__(args, logger)
        self.base_url = f'{self.base_url}/identity-management/v3'
        self.headers = {'Accept': 'application/json'}
        self.logger = logger
        self.account_name = None

    def exit_condition(self):
        print()
        self.logger.error(f'invalid account switch key {super().account_switch_key}')
        console = Console(stderr=True)
        exit(
            console.print(f'{emoji.poop} [red]Error looking up account. Exiting....\n')
        )

    def search_account(self):
        url = f'{self.base_url}/api-clients/self/account-switch-keys'
        params = {}
        if self.account_switch_key:
            ask_without_type = self.account_switch_key.split(':')[0]
            params = {'search': ask_without_type}
        resp = self.session.get(url, params=params, headers=self.headers)

        if not resp.ok:
            self.exit_condition()
        else:
            try:
                self.account_name = resp.json()[0]['accountName']
                if not self.account_name:
                    self.exit_condition()
            except IndexError:
                self.exit_condition()

        print('\n\n')
        self.logger.critical(f'Account Name      : {self.account_name}')
        self.logger.critical(f'Account Switch Key: {ask_without_type}')
        return self.account_name

    def __call__(self):
        return self.search_account()
