"""Точка входа для PyInstaller: запускает пакет pill как приложение.

Нужен отдельный скрипт, потому что frozen-entry исполняется как top-level
модуль, а `pill/__main__.py` использует относительные импорты пакета."""
import sys

from pill.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
