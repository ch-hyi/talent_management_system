"""
解析器模組
提供郵件解析功能
"""
from .base_parser import BaseMailParser, ParsedMail, ParsedInstruction
from .job104_parser import Job104Parser


__all__ = [
    'BaseMailParser',
    'ParsedMail',
    'ParsedInstruction',
    'Job104Parser',
    'ReplyParser'
]