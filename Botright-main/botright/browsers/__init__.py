# browsers/__init__.py
from .browser import build_chrome

# Alias cho tương thích với Botright
launch = build_chrome
__all__ = ["build_chrome", "launch"]
