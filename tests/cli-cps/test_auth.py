from __future__ import annotations

import os.path
import unittest
from unittest.mock import patch

import pytest
from akamai_apis.idm import IdentityAccessManagement
from mock_factory import MockFactory
from mock_factory import Namespace


class TestAccountLookup(unittest.TestCase):
    @patch('akamai_apis.auth.requests.Session.get')
    def test_success(self, mock_get):

        # test with account switch key
        mock_logger, _, _ = MockFactory.get_mock_objects()
        cli_args = Namespace(account_switch_key='ABC-123', section='default')

        response_body = MockFactory.getJSONFromFile(f'{os.getcwd()}/tests/cli-cps/data/idm/list_account_switch_keys.json')
        mock_response = MockFactory.get_mock_response(200, response_body)
        mock_get.return_value = mock_response

        idm = IdentityAccessManagement(mock_logger, cli_args)

        account_name = idm()
        assert account_name == 'Internet Company'

        # test without account switch key
        mock_logger, _, _ = MockFactory.get_mock_objects()
        cli_args = Namespace(section='default')

        response_body = MockFactory.getJSONFromFile(f'{os.getcwd()}/tests/cli-cps/data/idm/list_account_switch_keys.json')
        mock_response = MockFactory.get_mock_response(200, response_body)
        mock_get.return_value = mock_response

        idm = IdentityAccessManagement(mock_logger, cli_args)

        account_name = idm()
        assert account_name == 'Internet Company'

    @patch('akamai_apis.auth.requests.Session.get')
    def test_failure(self, mock_get):

        # test with account switch key
        mock_logger, _, _ = MockFactory.get_mock_objects()
        cli_args = Namespace(account_switch_key='ABC-123', section='default')

        response_body = MockFactory.getJSONFromFile(f'{os.getcwd()}/tests/cli-cps/data/idm/list_account_switch_keys.json')
        mock_response = MockFactory.get_mock_response(404, response_body)
        mock_response.ok = False  # test error response
        mock_get.return_value = mock_response

        idm = IdentityAccessManagement(mock_logger, cli_args)

        account_name = 'not set'
        with pytest.raises(SystemExit) as excinfo:
            account_name = idm()
        assert excinfo.type == SystemExit
        assert account_name == 'not set'

        # test without account switch key
        mock_logger, _, _ = MockFactory.get_mock_objects()
        cli_args = Namespace(section='default')

        response_body = MockFactory.getJSONFromFile(f'{os.getcwd()}/tests/cli-cps/data/idm/list_account_switch_keys.json')
        mock_response = MockFactory.get_mock_response(501, response_body)
        mock_response.ok = False  # test error response
        mock_get.return_value = mock_response

        idm = IdentityAccessManagement(mock_logger, cli_args)

        account_name = 'not set'
        with pytest.raises(SystemExit) as excinfo:
            account_name = idm()
        assert excinfo.type == SystemExit
        assert account_name == 'not set'


if __name__ == '__main__':
    unittest.main()
