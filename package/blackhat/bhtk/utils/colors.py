#!/usr/bin/env python3
"""Terminal color codes"""


class Colors:
    """ANSI color codes for terminal output"""
    
    # Regular colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    
    # Reset
    RESET = '\033[0m'
    
    @classmethod
    def success(cls, msg):
        return f"{cls.GREEN}[✓] {msg}{cls.RESET}"
    
    @classmethod
    def error(cls, msg):
        return f"{cls.RED}[✗] {msg}{cls.RESET}"
    
    @classmethod
    def warning(cls, msg):
        return f"{cls.YELLOW}[!] {msg}{cls.RESET}"
    
    @classmethod
    def info(cls, msg):
        return f"{cls.CYAN}[*] {msg}{cls.RESET}"
    
    @classmethod
    def prompt(cls, msg):
        return f"{cls.GREEN}[>]{cls.RESET} {msg}"
