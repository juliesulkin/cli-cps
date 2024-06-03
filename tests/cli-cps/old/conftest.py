from __future__ import annotations

import pytest
import requests
import requests_mock


@pytest.fixture(scope='function')
def session(request):
    session = requests.Session()
    with requests_mock.Mocker(session=session) as m:
        if request.param[0] == 'GET':
            m.get(request.param[1], status_code=request.param[2])
        if request.param[0] == 'POST':
            m.post(request.param[1], status_code=request.param[2])
        if request.param[0] == 'PUT':
            m.put(request.param[1], status_code=request.param[2])
        if request.param[0] == 'DELETE':
            m.delete(request.param[1], status_code=request.param[2])

        yield session
