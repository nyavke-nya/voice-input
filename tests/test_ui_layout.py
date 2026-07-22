"""The settings header stays visible when the screen is shorter than the content."""
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_settings_scroll_on_short_screen():
    probe = textwrap.dedent(
        """
        import time
        from PySide6.QtCore import QCoreApplication, QEvent, QObject
        from pill import config
        from pill.ui import build_app

        app, backend, engine = build_app(config.load())
        backend.expanded = True
        deadline = time.monotonic() + 0.6
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

        window = engine.rootObjects()[0]
        surface = window.findChild(QObject, "surface")
        header = window.findChild(QObject, "header")
        scroll = window.findChild(QObject, "paneScroll")
        panes = window.findChild(QObject, "panes")
        prop = lambda obj, name: obj.property(name)

        assert window.height() == 800  # Qt offscreen test screen
        assert prop(surface, "height") <= window.height() - 36
        assert prop(surface, "y") >= 18
        assert prop(header, "y") >= 0
        assert prop(scroll, "contentHeight") == prop(panes, "height")
        assert prop(scroll, "contentHeight") > prop(scroll, "height")
        assert prop(scroll, "interactive")

        maximum = prop(scroll, "contentHeight") - prop(scroll, "height")
        scroll.setProperty("contentY", maximum)
        app.processEvents()
        assert abs(prop(scroll, "contentY") - maximum) < 1

        backend._teardown_qml()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        backend.shutdown()
        """
    )
    with tempfile.TemporaryDirectory() as temp:
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(ROOT),
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_CONFIG_HOME": str(Path(temp) / "config"),
            "XDG_CACHE_HOME": str(Path(temp) / "cache"),
        })
        result = subprocess.run(
            [sys.executable, "-c", probe], cwd=ROOT, env=env,
            capture_output=True, text=True, check=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    test_settings_scroll_on_short_screen()
    print("test_ui_layout OK")
