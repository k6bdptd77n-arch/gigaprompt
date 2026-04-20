"""
Centralized print utilities for Super Memory CLI
"""
import sys


def safe_print(msg):
    """Print without Unicode errors (Windows-safe)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode())


# Alias for interactive.py compatibility
print_safe = safe_print


def print_ok(msg):
    print(f"[OK] {msg}")


def print_err(msg):
    print(f"[X] {msg}")


def print_info(msg):
    print(f"[*] {msg}")
