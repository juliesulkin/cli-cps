# Techdocs reference
# https://techdocs.akamai.com/iam-api/reference/get-client-account-switch-keys
from __future__ import annotations

import logging
import sys

from akamai_apis.auth import AkamaiSession
from rich import print_json
from utils import _logging as lg


class IdentityAccessManagement(AkamaiSession):
    def __init__(self,
                 account_switch_key: str | None = None,
                 section: str | None = None,
                 edgerc: str | None = None,
                 logger: logging.Logger = None):
        super().__init__(account_switch_key=account_switch_key, section=section, edgerc=edgerc)
        self.MODULE = f'{self.base_url}/identity-management/v3'
        self.headers = {'Accept': 'application/json'}
        self.contract_id = self.contract_id
        self.group_id = self.group_id
        self.account_switch_key = account_switch_key
        if account_switch_key and ':' in account_switch_key:
            self.account_id = account_switch_key.split(':')[0]
            self.contract_type = account_switch_key.split(':')[1]
        else:
            self.account_id = self.account_switch_key
        self.property_id = None
        self.logger = logger

    def search_accounts(self, value: str | None = None) -> str:
        qry = f'?search={value.upper()}' if value else None

        # this endpoint doesn't use account switch key
        url = f'{self.MODULE}/api-clients/self/account-switch-keys{qry}'
        resp = self.session.get(url, headers=self.headers)
        account_name = []
        if resp.status_code == 200:
            if len(resp.json()) == 0:
                self.logger.warning(f'{value} not found, remove : from search')
                account = value.split(':')[0]
                accounts = self.search_account_name_without_colon(account)
                return accounts
            else:
                return resp.json()
        elif resp.json()['title'] == 'ERROR_NO_SWITCH_CONTEXT':
            sys.exit(self.logger.error('You do not have permission to lookup other accounts'))
        elif 'WAF deny rule IPBLOCK-BURST' in resp.json()['detail']:
            self.logger.error(resp.json()['detail'])
            self.logger.countdown(540, msg='Oopsie! You just hit rate limit.', logger=self.logger)
            sys.exit()
        elif len(account_name) > 1:
            print_json(data=resp.json())
            sys.exit(self.logger.error('please use the right account switch key'))
        else:
            sys.exit(self.logger.error(resp.json()['detail']))

    def search_account_name(self, value: str | None = None) -> str:
        qry = f'?search={value.upper()}' if value else None

        # this endpoint doesn't use account switch key
        url = f'{self.MODULE}/api-clients/self/account-switch-keys{qry}'
        resp = self.session.get(url, headers=self.headers)
        account_name = []
        if resp.status_code == 200:
            if len(resp.json()) == 0:
                account = value.split(':')[0]
                accounts = self.search_account_name_without_colon(account)
                account_name = []
                for account in accounts:
                    temp_account = account['accountName']
                account_name.append(temp_account)
            else:
                for account in resp.json():
                    account_name.append(account['accountName'])
        elif resp.json()['title'] == 'ERROR_NO_SWITCH_CONTEXT':
            sys.exit(self.logger.error('You do not have permission to lookup other accounts'))
        elif 'WAF deny rule IPBLOCK-' in resp.json()['detail']:
            self.logger.error(resp.json()['detail'])
            lg.countdown(540, msg='Oopsie! You just hit rate limit.', logger=self.logger)
            sys.exit()
        else:
            sys.exit(self.logger.error(resp.json()['detail']))

        if len(account_name) > 1:
            print_json(data=resp.json())
            sys.exit(self.logger.error('please provide correct account switch key [-a/--accountkey]'))
        return account_name

    def search_account_name_without_colon(self, value: str | None = None) -> str:
        qry = f'?search={value.upper()}' if value else None

        # this endpoint doesn't use account switch key
        url = f'{self.MODULE}/api-clients/self/account-switch-keys{qry}'
        resp = self.session.get(url, headers=self.headers)

        if resp.status_code == 200:
            return resp.json()
        elif resp.json()['title'] == 'ERROR_NO_SWITCH_CONTEXT':
            sys.exit(self.logger.error('You do not have permission to lookup other accounts'))
        elif 'WAF deny rule IPBLOCK-BURST' in resp.json()['detail']:
            self.logger.error(resp.json()['detail'])
            lg.countdown(540, msg='Oopsie! You just hit rate limit.', logger=self.logger)
            sys.exit()
        else:
            sys.exit(self.logger.error(resp.json()['detail']))

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

    def show_account_summary(self, account: str):
        account = self.remove_account_type(account)
        # account = account.replace(' - ', '_').replace(',', '').replace('.', '_')
        # account = account.translate(str.maketrans(' -', '__')).rstrip('_')
        account = account.replace(' ', '_')  # replace empty space with underscore
        account = account.replace(',', '')
        account = account.replace('._', '_')
        account = account.replace(',_', '_')
        account = account.rstrip('.')
        acc_url = 'https://control.akamai.com/apps/home-page/#/manage-account?accountId='
        try:
            account_url = f'{acc_url}{self.account_id}&contractTypeId={self.contract_type}&targetUrl='
        except Exception:
            account_url = f'{acc_url}{self.account_id}&targetUrl='
        print()
        self.logger.warning(f'{account}         {account_url}')
        return account

    def get_api_client(self):
        url = f'{self.MODULE}/api-clients/self'
        resp = self.session.get(url, headers=self.headers)
        return resp

    def access_apis_v3(self, username: str):
        url = f'{self.MODULE}/users/{username}/allowed-apis'
        params = {'accountSwitchKey': self.account_switch_key,
                  'clientType': 'USER_CLIENT'}
        resp = self.session.get(url, headers=self.headers, params=params)
        return resp

    def access_apis_v1(self, access_token: str):
        url = f'{self.base_url}/identity-management/v1/open-identities/tokens/{access_token}'
        resp = self.session.get(url, headers=self.headers)
        return resp
