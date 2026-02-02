#!/usr/bin/env python3
"""Logging utilities"""

import os
import datetime
from .colors import Colors

LOG_DIR = "/var/log/bhtk"


def ensure_log_dir():
    """Ensure log directory exists"""
    os.makedirs(LOG_DIR, exist_ok=True)


def get_log_file(prefix="bhtk"):
    """Get a timestamped log file path"""
    ensure_log_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(LOG_DIR, f"{prefix}_{timestamp}.log")


def log(message, filename=None, also_print=True):
    """Log message to file and optionally print"""
    if also_print:
        print(message)
    
    if filename:
        # Strip ANSI codes for file logging
        clean_msg = strip_ansi(message)
        with open(filename, 'a') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {clean_msg}\n")


def strip_ansi(text):
    """Remove ANSI escape codes from text"""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class Logger:
    """Logger class for persistent logging"""
    
    def __init__(self, prefix="bhtk"):
        self.log_file = get_log_file(prefix)
        self.info(f"Logging to: {self.log_file}")
    
    def info(self, msg):
        log(Colors.info(msg), self.log_file)
    
    def success(self, msg):
        log(Colors.success(msg), self.log_file)
    
    def warning(self, msg):
        log(Colors.warning(msg), self.log_file)
    
    def error(self, msg):
        log(Colors.error(msg), self.log_file)
    
    def raw(self, msg):
        log(msg, self.log_file)
