"""Проверки связи «шаг перехода (goto/branch) ↔ правая панель» (без реального GUI).

Что должно выполняться:
  1. Когда прогон уходит в другой плейлист/сценарий, правая панель показывает
     цепочку переходов и подсвечивает (▶) тот сценарий, который идёт сейчас.
  2. Свой (в том числе НЕсохранённый) список при этом не теряется: он живёт в
     чипе «▣ My list», куда можно вернуться одним кликом.
  3. Следующий переход двигает подсветку дальше (пройденное помечается ✓).
  4. «▶ Run list» и правки списка всегда применяются к своему списку, даже если
     панель в этот момент показывала цепочку переходов.
  5. Закончившийся движок отпускается (иначе «▶ Run list» вечно отвечает
     'Runner is already active').

Запуск:
    venv\\Scripts\\python.exe test_playlist_jump_panel.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import shutil
import sys
import types

from PySide6.QtWidgets import QApplication

import MACS_Visual_Automation as app_mod

# консоль Windows может быть в cp1255/cp1251 — не роняем тест на ▶/✓ в подписях
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []

GOOD_STEP = {"enabled": True, "action": "pause", "image": "", "value": "1",
             "timeout": 10, "find_window": False, "stop_on_error": True}


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


def make_scenario(path, steps=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(steps or [GOOD_STEP], f)
    return path


def make_playlist_file(path, scenario_paths):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"playlist": [os.path.basename(p) for p in scenario_paths]}, f)
    return path


def row_texts(win):
    return [win.playlist_list.item(i).text() for i in range(win.playlist_list.count())]


def main():
    app = QApplication(sys.argv)
    win = app_mod.MainWindow()
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_jump_panel_tmp")
    shutil.rmtree(base, ignore_errors=True)

    my1 = make_scenario(os.path.join(base, "mine", "my_first.json"))
    my2 = make_scenario(os.path.join(base, "mine", "my_second.json"))
    jump1 = make_scenario(os.path.join(base, "far", "jump_one.json"))
    jump2 = make_scenario(os.path.join(base, "far", "jump_two.json"))
    jump_list = make_playlist_file(os.path.join(base, "far", "handoff.json"), [jump1, jump2])

    # прогоны не запускаем по-настоящему (иначе поедет мышь) — только фиксируем
    started = []
    win.run_scenario = lambda from_branch=False: started.append(win._scenario_path)

    try:
        # свой, ещё не сохранённый список
        win._fill_playlist_widget([my1, my2])
        win._update_preview_bar()
        check("My list holds both programs",
              win.my_list_paths() == [my1, my2])
        check("Jump chip is disabled while nothing has jumped yet",
              not win.btn_list_jump.isEnabled())

        # --- 1. шаг goto → панель показывает цепочку перехода ---
        win._pending_branch = jump_list
        win._on_finished()

        check("Panel switches to the jump chain on a jump",
              win._shown_list == "jump")
        check("Jump chain lists both programs of the target playlist",
              win._widget_paths() == [jump1, jump2])
        check("The running program is marked with ▶",
              row_texts(win)[0].startswith("▶ ") and not row_texts(win)[1].startswith("▶ "))
        check("Jump chip shows position in the chain",
              "1/2" in win.btn_list_jump.text())
        check("Left preview bar reports the jump chain",
              "jump chain" in win.preview_label.text())
        check("The jump target actually started",
              started and os.path.samefile(started[-1], jump1))

        # --- 2. свой несохранённый список не потерян ---
        check("My list survives the jump (still 2 programs)",
              win.my_list_paths() == [my1, my2])
        check("My list chip still shows its count",
              "(2)" in win.btn_list_my.text())

        # --- 3. следующий переход двигает подсветку ---
        win._on_finished()
        texts = row_texts(win)
        check("Finished program of the chain is marked with ✓",
              texts[0].startswith("✓ "))
        check("Next program of the chain becomes the running one",
              texts[1].startswith("▶ "))
        check("Jump chip advances to 2/2",
              "2/2" in win.btn_list_jump.text())
        check("Second jump target started",
              os.path.samefile(started[-1], jump2))

        # --- 4. возврат к своему списку и обратно ---
        win._on_chip_my_list()
        check("Clicking '▣ My list' brings back my own programs",
              win._shown_list == "my" and win._widget_paths() == [my1, my2])
        check("Jump chain stays available after switching back",
              win.btn_list_jump.isEnabled())
        win._on_chip_jump_list()
        check("Clicking the jump chip shows the chain again",
              win._shown_list == "jump" and win._widget_paths() == [jump1, jump2])

        # --- 5. «Run list» всегда про свой список ---
        started.clear()
        win.runner = None
        win.playlist_run()
        check("Run list restores my own list in the panel",
              win._shown_list == "my" and win._widget_paths() == [my1, my2])
        check("Run list starts my first program, not a jump target",
              started and os.path.samefile(started[-1], my1))
        check("Running program of my list is marked with ▶",
              row_texts(win)[0].startswith("▶ "))
        check("Jump chip is disabled again after a fresh run",
              not win.btn_list_jump.isEnabled())

        # --- 6. движок отпускается после прогона ---
        win._playlist_active = False
        win.runner = types.SimpleNamespace(wait=lambda ms=0: None)
        win._release_runner()
        check("Finished runner is released so 'Run list' is available again",
              win.runner is None and win.btn_pl_run.isEnabled())

        # --- 7. цепочка read-only: правки не портят свой список ---
        win._pending_branch = jump1
        win._on_finished()
        win.playlist_list.setCurrentRow(0)
        win.playlist_remove_selected()
        win.playlist_move(1)
        check("Editing is refused while the jump chain is shown",
              win._widget_paths() == [jump1])
        win._on_chip_my_list()
        check("My list is intact after refused edits",
              win._widget_paths() == [my1, my2])
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
