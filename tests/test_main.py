"""Однопроцессный lock демона без запуска Qt и сокета."""
import os
import tempfile

from pill.__main__ import _instance_lock


def test_instance_lock_is_exclusive_and_reusable():
    if os.name == "nt":
        return
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CACHE_HOME"] = d
        first = _instance_lock()
        assert first and _instance_lock() is False
        first.close()
        second = _instance_lock()
        assert second
        second.close()


if __name__ == "__main__":
    test_instance_lock_is_exclusive_and_reusable()
    print("test_main OK")
