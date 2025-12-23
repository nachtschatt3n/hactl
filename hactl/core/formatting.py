"""
Output formatting utilities for hactl
"""

import json
import click
from typing import Any


def json_to_yaml(obj: Any, indent: int = 0) -> str:
    """
    Convert JSON-like structure to YAML format.

    Args:
        obj: Object to convert (dict, list, or primitive)
        indent: Current indentation level

    Returns:
        str: YAML-formatted string
    """
    yaml_str = ""
    indent_str = "  " * indent

    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is None:
                yaml_str += f"{indent_str}{key}: null\n"
            elif isinstance(value, bool):
                yaml_str += f"{indent_str}{key}: {str(value).lower()}\n"
            elif isinstance(value, (int, float)):
                yaml_str += f"{indent_str}{key}: {value}\n"
            elif isinstance(value, str):
                if value == "" or ':' in value or '\n' in value:
                    yaml_str += f"{indent_str}{key}: {json.dumps(value, ensure_ascii=False)}\n"
                else:
                    yaml_str += f"{indent_str}{key}: {value}\n"
            elif isinstance(value, dict):
                if not value:
                    yaml_str += f"{indent_str}{key}: {{}}\n"
                else:
                    yaml_str += f"{indent_str}{key}:\n"
                    yaml_str += json_to_yaml(value, indent + 1)
            elif isinstance(value, list):
                if not value:
                    yaml_str += f"{indent_str}{key}: []\n"
                else:
                    yaml_str += f"{indent_str}{key}:\n"
                    yaml_str += json_to_yaml(value, indent + 1)
            else:
                yaml_str += f"{indent_str}{key}: {json.dumps(value, ensure_ascii=False)}\n"
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                yaml_str += f"{indent_str}- \n"
                yaml_str += json_to_yaml(item, indent + 1)
            elif isinstance(item, list):
                yaml_str += f"{indent_str}- \n"
                yaml_str += json_to_yaml(item, indent + 1)
            elif item is None:
                yaml_str += f"{indent_str}- null\n"
            elif isinstance(item, bool):
                yaml_str += f"{indent_str}- {str(item).lower()}\n"
            elif isinstance(item, (int, float)):
                yaml_str += f"{indent_str}- {item}\n"
            elif isinstance(item, str):
                if item == "" or ':' in item or '\n' in item:
                    yaml_str += f"{indent_str}- {json.dumps(item, ensure_ascii=False)}\n"
                else:
                    yaml_str += f"{indent_str}- {item}\n"
            else:
                yaml_str += f"{indent_str}- {json.dumps(item, ensure_ascii=False)}\n"
    return yaml_str


def format_output(data: Any, format_type: str, title: str = "Data") -> None:
    """
    Format and print data in the requested format.

    Args:
        data: Data to format (usually a list or dict)
        format_type: Output format ('table', 'json', 'detail', 'yaml')
        title: Title for the output (used in table and detail formats)
    """
    if format_type == 'json':
        click.echo(json.dumps(data, indent=2))
    elif format_type == 'yaml':
        click.echo(f"# {title}")
        click.echo("---")
        click.echo(json_to_yaml(data))
    elif format_type == 'detail':
        click.echo(f"=== {title} ===\n")
        if isinstance(data, list):
            click.echo(f"Total Items: {len(data)}\n")
        # For detail format, scripts should implement their own formatting
        click.echo(json.dumps(data, indent=2))
    else:  # table format
        # For table format, scripts should implement their own formatting
        click.echo(f"=== {title} ===\n")
        if isinstance(data, list):
            click.echo(f"Total Items: {len(data)}\n")
        click.echo(json.dumps(data, indent=2))
