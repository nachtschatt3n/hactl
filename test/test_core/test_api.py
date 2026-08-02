"""
Tests for hactl.core.api.make_api_request

Regression coverage for the empty-body POST bug: `data={}` is falsy, and
the old guard (`if data and method in (...)`) skipped both attaching the
body AND overriding the request method, so a POST with an empty JSON
payload silently went out as GET (HA answered 405 Method Not Allowed).
"""

import io
import json
import urllib.error
from unittest.mock import patch, MagicMock

import click
import pytest

from hactl.core.api import make_api_request

TEST_URL = 'https://test-hass.example.com/api/services/automation/reload'
TEST_TOKEN = 'test_token_12345'


def _mock_urlopen(response_data=None):
    """Build a mock for urllib.request.urlopen returning a JSON body."""
    response = MagicMock()
    response.read.return_value = json.dumps(
        response_data if response_data is not None else {}
    ).encode('utf-8')
    urlopen = MagicMock()
    urlopen.return_value.__enter__.return_value = response
    return urlopen


class TestMakeApiRequestMethods:
    """Explicit method must always be honored, regardless of body."""

    def test_post_with_empty_dict_sends_post_with_empty_json_body(self):
        """POST with data={} must go out as POST with body b'{}' (regression)."""
        urlopen = _mock_urlopen()
        with patch('urllib.request.urlopen', urlopen):
            result = make_api_request(TEST_URL, TEST_TOKEN, method='POST', data={})

        req = urlopen.call_args[0][0]
        assert req.get_method() == 'POST'
        assert req.data == b'{}'
        assert result == {}

    def test_post_with_none_data_still_sends_post(self):
        """POST with data=None must not degrade to GET."""
        urlopen = _mock_urlopen()
        with patch('urllib.request.urlopen', urlopen):
            make_api_request(TEST_URL, TEST_TOKEN, method='POST', data=None)

        req = urlopen.call_args[0][0]
        assert req.get_method() == 'POST'
        assert req.data is None

    def test_get_unchanged(self):
        """Default GET request has no body and method GET."""
        urlopen = _mock_urlopen([{'entity_id': 'sensor.temperature'}])
        with patch('urllib.request.urlopen', urlopen):
            result = make_api_request(TEST_URL, TEST_TOKEN)

        req = urlopen.call_args[0][0]
        assert req.get_method() == 'GET'
        assert req.data is None
        assert result == [{'entity_id': 'sensor.temperature'}]

    def test_post_with_payload_unchanged(self):
        """POST with a real payload still sends the JSON-encoded body."""
        payload = {'entity_id': 'light.living_room', 'brightness': 255}
        urlopen = _mock_urlopen()
        with patch('urllib.request.urlopen', urlopen):
            make_api_request(TEST_URL, TEST_TOKEN, method='POST', data=payload)

        req = urlopen.call_args[0][0]
        assert req.get_method() == 'POST'
        assert json.loads(req.data.decode('utf-8')) == payload


class TestMakeApiRequestHeaders:
    """Headers must be attached regardless of method/body."""

    def test_headers_present_on_empty_body_post(self):
        urlopen = _mock_urlopen()
        with patch('urllib.request.urlopen', urlopen):
            make_api_request(TEST_URL, TEST_TOKEN, method='POST', data={})

        req = urlopen.call_args[0][0]
        assert req.get_header('Authorization') == f'Bearer {TEST_TOKEN}'
        assert req.get_header('Content-type') == 'application/json'


class TestMakeApiRequestErrors:
    """Error handling stays as click.ClickException."""

    def test_http_error_raises_click_exception(self):
        error = urllib.error.HTTPError(
            url=TEST_URL, code=405, msg='Method Not Allowed',
            hdrs=None, fp=io.BytesIO(b'{"message": "Method not allowed"}'),
        )
        with patch('urllib.request.urlopen', side_effect=error):
            with pytest.raises(click.ClickException) as exc_info:
                make_api_request(TEST_URL, TEST_TOKEN, method='POST', data={})

        assert 'HTTP 405' in str(exc_info.value)

    def test_generic_error_raises_click_exception(self):
        with patch('urllib.request.urlopen', side_effect=OSError('boom')):
            with pytest.raises(click.ClickException) as exc_info:
                make_api_request(TEST_URL, TEST_TOKEN)

        assert 'API request failed' in str(exc_info.value)
