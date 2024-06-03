from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock


class Namespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class MockFactory():
    def get_mock_objects():
        mock_logger = MagicMock()
        mock_cps = MagicMock()
        mock_idm = MagicMock()

        return (mock_logger, mock_cps, mock_idm)

    def getJSONFromFile(jsonPath):

        with open(jsonPath) as myfile:
            jsonStr = myfile.read()

        jsonObj = json.loads(jsonStr)
        return jsonObj

    def get_mock_response(status_code, response_body):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = response_body
        return (mock_response)
