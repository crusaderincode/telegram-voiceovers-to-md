"""Configuration package"""
from .settings import Settings
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

__all__ = ['Settings', 'SYSTEM_PROMPT', 'USER_PROMPT_TEMPLATE']
