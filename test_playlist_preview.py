"""Регрессионные проверки плейлиста и превью-переключателя (без реального GUI).

Покрывает два бага, которые уже "чинили" вручную и хотим не повторить:
  1. Клик/Prev/Next по пункту плейлиста с повреждённым сценарием (список,
     где среди объектов-шагов затесалась обычная строка) не должен ронять
     приложение трейсбеком в консоль — должен быть чистый лог-эксепшн.
  2. Подпись пункта плейлиста/бара предпросмотра должна оставаться
     различимой, даже если у файлов совпадает имя и даже родительская папка
     на разной глубине вложенности (see make_unique_playlist_labels).

Запуск:
    venv\\Scripts\\python.exe test_playlist_preview.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import io
import json
import shutil
import sys
import contextlib

from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import Qt

import MACS_Visual_Automation as app_mod

FAILURES = []


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


def make_scenario(path, steps):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(steps, f)


def add_to_playlist(win, path):
    item = QListWidgetItem(os.path.basename(path))
    item.setData(Qt.UserRole, path)
    win.playlist_list.addItem(item)


def main():
    app = QApplication(sys.argv)
    win = app_mod.MainWindow()
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_playlist_preview_tmp")
    shutil.rmtree(base, ignore_errors=True)

    good_step = {"enabled": True, "action": "click_image", "image": "a.png", "value": "",
                 "timeout": 10, "find_window": False, "stop_on_error": True}

    p_good_a = os.path.join(base, "a", "scenario.json")
    p_good_b = os.path.join(base, "b", "scenario.json")
    p_broken = os.path.join(base, "c", "scenario.json")

    make_scenario(p_good_a, [good_step])
    make_scenario(p_good_b, [good_step, good_step])
    # Повреждённый файл: список шагов, где одна запись — строка, а не объект.
    make_scenario(p_broken, [good_step, "oops_this_is_a_bare_string"])

    try:
        # --- Bug #1: corrupted scenario must not crash, must log cleanly ---
        for p in (p_good_a, p_broken):
            add_to_playlist(win, p)
        win._refresh_playlist_labels()

        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            win._preview_step(1)   # -> loads p_good_a (row 0)
            label_after_good = win.preview_label.text()
            rows_after_good = win.table.rowCount()
            win._preview_step(1)   # -> tries to load p_broken (row 1), must NOT crash
        stderr_out = stderr_buf.getvalue()

        check("Loading a valid scenario updates the preview label",
              "a" in label_after_good and "scenario.json" in label_after_good)
        check("Loading a valid scenario populates the table",
              rows_after_good == 1)
        check("No traceback printed while previewing a corrupted scenario",
              "Traceback" not in stderr_out and "AttributeError" not in stderr_out)
        check("Corrupted scenario logs a clean error instead of crashing",
              "unexpected/corrupted format" in win.log_view.toPlainText())

        # --- Bug #2: duplicate filenames at different folder depths ---
        win.playlist_list.clear()
        deep_dup = os.path.join(base, "nested", "a", "scenario.json")
        make_scenario(deep_dup, [good_step])
        for p in (p_good_a, deep_dup):
            add_to_playlist(win, p)
        win._refresh_playlist_labels()
        label0 = win.playlist_list.item(0).text()
        label1 = win.playlist_list.item(1).text()
        check("Same-named files in different folders get distinct labels",
              label0 != label1)

        # Identical file added twice must legitimately share the same label.
        win.playlist_list.clear()
        for p in (p_good_a, p_good_a):
            add_to_playlist(win, p)
        win._refresh_playlist_labels()
        check("The same file added twice keeps an identical label (expected)",
              win.playlist_list.item(0).text() == win.playlist_list.item(1).text())
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
