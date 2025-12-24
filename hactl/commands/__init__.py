"""
Command groups for hactl
"""

from .get import get_group
from .update import update_group
from .battery import battery_group
from .k8s import k8s_group
from .memory import memory_group

__all__ = ['get_group', 'update_group', 'battery_group', 'k8s_group', 'memory_group']
