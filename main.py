import json
import os
import signal
import tempfile
import time
from pathlib import Path

import customtkinter
import psutil

from Managers.GSIManager import GSIManager
from Managers.VideoConfigManager import VideoConfigManager
from ui.app import App

LOCK_FILE = Path(tempfile.gettempdir()) / "goose_panel_single_instance.lock"


def _show_relaunch_notice():
    root = customtkinter.CTk()
    root.title("Goose Panel")
    root.geometry("420x120")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    label = customtkinter.CTkLabel(
        root,
        text="Повторное открытие ПО.\nПервый экземпляр будет закрыт через 3 секунды.",
        justify="center",
        font=customtkinter.CTkFont(size=15, weight="bold"),
    )
    label.pack(expand=True, padx=16, pady=16)

    root.after(3000, root.destroy)
    root.mainloop()


def _read_lock():
    if not LOCK_FILE.exists():
        return None

    try:
        return json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_lock():
    LOCK_FILE.write_text(
        json.dumps({"pid": os.getpid(), "started_at": int(time.time())}),
        encoding="utf-8",
    )


def _safe_remove_lock():
    try:
        lock_data = _read_lock()
        if lock_data and int(lock_data.get("pid", -1)) == os.getpid() and LOCK_FILE.exists():
            LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _terminate_process(pid):
    try:
        proc = psutil.Process(pid)
    except Exception:
        return

    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _enforce_single_instance():
    lock_data = _read_lock()
    if not lock_data:
        _write_lock()
        return

    old_pid = int(lock_data.get("pid", -1))
    if old_pid > 0 and psutil.pid_exists(old_pid) and old_pid != os.getpid():
        _show_relaunch_notice()
        _terminate_process(old_pid)
        time.sleep(0.2)

    _write_lock()


if __name__ == "__main__":
    _enforce_single_instance()
    signal.signal(signal.SIGTERM, lambda *_: _safe_remove_lock())

    video_config_manager = VideoConfigManager()
    startup_gpu_info = video_config_manager.sync_on_startup()

    gsi = GSIManager()
    gsi.start()


    app = App(gsi_manager=gsi, startup_gpu_info=startup_gpu_info)

    try:
        app.mainloop()
    finally:
        _safe_remove_lock()