"""Configuration package"""
from .settings import Settings
from .prompts import SYSTEM_PROMPT_RECORD, SYSTEM_PROMPT_SUMMARIZE, USER_PROMPT_TEMPLATE

__all__ = ['Settings', 'SYSTEM_PROMPT_RECORD', 'SYSTEM_PROMPT_SUMMARIZE', 'USER_PROMPT_TEMPLATE']
