"""
API request utilities for hactl
"""

import json
import urllib.request
import urllib.error
import click
from typing import Optional, Dict, Any


def make_api_request(url: str, token: str, method: str = 'GET',
                     data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Make an API request to Home Assistant.

    Args:
        url: Full URL for the API endpoint
        token: Home Assistant API token
        method: HTTP method (default: GET)
        data: Optional data to send with POST/PUT requests

    Returns:
        dict: JSON response from the API

    Raises:
        click.ClickException: If the API request fails
    """
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')
    # Browser-shaped UA: Cloudflare's WAF returns 1010 on the default
    # `Python-urllib/<ver>` UA when DNS for HASS_URL falls back to a CF
    # edge IP (e.g. AdGuard split-horizon temporarily unreachable).
    req.add_header('User-Agent', 'Mozilla/5.0 (hactl)')

    try:
        if data and method in ('POST', 'PUT', 'PATCH'):
            req.data = json.dumps(data).encode('utf-8')
            req.get_method = lambda: method

        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_msg = f'HTTP {e.code} {e.reason}'
        if e.fp:
            error_body = e.fp.read().decode()
            error_msg += f'\nResponse: {error_body}'
        raise click.ClickException(error_msg)
    except Exception as e:
        raise click.ClickException(f'API request failed: {e}')
