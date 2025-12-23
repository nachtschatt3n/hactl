"""
Configuration management for hactl
"""

import os
import click
from typing import Tuple

# Try to import dotenv, but make it optional
try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback: manually load .env file if dotenv is not available
    def load_dotenv():
        env_file = '.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key.strip()] = value


def load_config() -> Tuple[str, str]:
    """
    Load Home Assistant configuration from environment variables.

    Returns:
        tuple: (HASS_URL, HASS_TOKEN)

    Raises:
        click.ClickException: If required environment variables are not set
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment (never hardcoded)
    HASS_URL = os.environ.get('HASS_URL')
    HASS_TOKEN = os.environ.get('HASS_TOKEN')

    # Validate required environment variables
    if not HASS_URL:
        raise click.ClickException(
            "HASS_URL not set. Set it in .env or export manually.\n"
            "Example: export HASS_URL='https://homeassistant.local:8123'"
        )

    if not HASS_TOKEN:
        raise click.ClickException(
            "HASS_TOKEN not set. Set it in .env or export manually.\n"
            "Example: export HASS_TOKEN='your_long_lived_access_token'"
        )

    return HASS_URL, HASS_TOKEN
