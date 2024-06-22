# Techdocs reference
# https://techdocs.akamai.com/iam-api/reference/get-client-account-switch-keys
from __future__ import annotations

import logging
import random
import time

import utils.emojis as emoji
from akamai_apis.auth import AkamaiSession
from rich.console import Console
from utils import cli_logging as lg


logger = logging.getLogger(__name__)


class IdentityAccessManagement(AkamaiSession):
    def __init__(self, args, account_switch_key: str | None = None):

        super().__init__(args, account_switch_key)
        self.base_url = f'{self.base_url}/identity-management/v3'
        self.headers = {'Accept': 'application/json'}
        self.account_name = None
        if account_switch_key:
            self.account_switch_key = account_switch_key

        if self.account_switch_key and ':' in self.account_switch_key:
            self.account_id = self.account_switch_key.split(':')[0]
        else:
            self.account_id = self.account_switch_key

    def exit_condition(self):
        print()
        logger.error(f'invalid account switch key {self.account_switch_key}')
        console = Console(stderr=True)
        exit(
            console.print(f'{emoji.poop} [red]Error looking up account. Exiting....\n')
        )

    def remove_account_type(self, account_name: str):
        substrings_to_remove = ['_Akamai Internal',
                                '_Indirect Customer',
                                '_Direct Customer',
                                '_Marketplace Prospect',
                                '_NAP Master Agreement',
                                '_Value Added Reseller',
                                '_Tier 1 Reseller',
                                '_VAR Customer',
                                '_ISP']

        for substring in substrings_to_remove:
            if substring in account_name:
                return account_name.replace(substring, '')
        return account_name

    def search_account(self):
        url = f'{self.base_url}/api-clients/self/account-switch-keys'
        params = {}
        ask_without_type = ''
        if self.account_switch_key:
            try:
                ask_without_type = self.account_switch_key.split(':')[0]
            except (ValueError, IndexError):
                ask_without_type = self.account_switch_key
            params = {'search': ask_without_type}

        resp = self.session.get(url, params=params, headers=self.headers)

        self.account_name = ''
        if resp.ok:
            try:
                self.account_name = resp.json()[0]['accountName']
            except IndexError:
                logger.error(resp.json())
        elif resp.json()['title'] == 'ERROR_NO_SWITCH_CONTEXT':
            logger.error('You do not have permission to lookup other accounts')
        elif 'WAF deny rule IPBLOCK-BURST' in resp.json()['detail']:
            print()
            logger.error(resp.json()['detail'])
            lg.countdown(540, msg='Oopsie! You just hit rate limit.')
        else:
            logger.error(f'unknown error {resp}')
            self.exit_condition()

        if self.account_name:
            self.account_name = self.remove_account_type(self.account_name)

        return self.account_name

    def __call__(self):
        return self.search_account()


class Papi(AkamaiSession):
    def __init__(self, args):
        super().__init__(args, logger)
        self.MODULE = f'{self.base_url}/papi/v1'
        self.headers = {'Accept': 'application/json'}
        self.account_name = None

    def search_property_by_hostname(self, hostname: str, account: str) -> tuple:

        rd = random.randint(1, 3)
        time.sleep(rd)
        logger.debug(f'{account} {rd}')

        if account:
            url = f'{self.MODULE}/search/find-by-value?accountSwitchKey={account}'
        else:
            url = f'{self.MODULE}/search/find-by-value?accountSwitchKey={self.account_switch_key}'

        payload = {'hostname': hostname}

        resp = self.session.post(url,
                                 json=payload,
                                 headers=self.headers)

        if not resp.ok:
            logger.error(f'{account} {hostname} {rd} {resp}')
            try:
                config = f"ERROR_{resp.status_code}_{resp.json()['detail']}"
            except KeyError:
                config = f'ERROR_{resp.status_code}'
        else:
            if hostname == 'Others':
                config = 'ERROR_Others'
            else:
                if len(resp.json()['versions']['items']) == 0:
                    config = 'NOT FOUND'
                else:
                    config = resp.json()['versions']['items'][0]['propertyName']
        return config
