"""Проверки удаления действий «клик по координатам (x,y)».

Что должно выполняться:
  1. click_xy / double_click_xy больше нигде нет: ни в списке действий, ни в
     подсказках Value, ни в справке, ни в исполнителе шагов.
  2. Выпадающий список в таблице их не предлагает.
  3. Старый сценарий с такими шагами всё равно загружается: шаг превращается в
     клик по шаблону, а в логе перечислены номера шагов, которым нужен шаблон.
  4. После загрузки сохранение пишет уже новое действие (файл «лечится» сам).

Запуск:
    venv\\Scripts\\python.exe test_retired_actions.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import sys
import tempfile

from PySide6.QtWidgets import QApplication

import MACS_Visual_Automation as app_mod

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []
RETIRED = ("click_xy", "double_click_xy")


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


def step(action, value=""):
    return {"enabled": True, "action": action, "image": "", "value": value,
            "timeout": 10, "find_window": False, "stop_on_error": True}


def main():
    app = QApplication(sys.argv)

    # --- 1. действий больше нет ни в одной таблице/справке ---
    check("Actions list no longer offers x,y clicks",
          all(a not in app_mod.ACTIONS for a in RETIRED))
    check("No Value hints left for x,y clicks",
          all(a not in app_mod.VALUE_HINT for a in RETIRED))
    check("No guide entries left for x,y clicks",
          all(a not in app_mod.ACTION_DOCS for a in RETIRED))
    grouped = [a for group in app_mod.HELP_ACTION_GROUPS.values() for a in group]
    check("No help section lists x,y clicks",
          all(a not in grouped for a in RETIRED))
    check("Both are recorded as retired with a replacement",
          all(app_mod.RETIRED_ACTIONS[a][0] in app_mod.ACTIONS for a in RETIRED))

    win = app_mod.MainWindow()
    combo = win.table.cellWidget(0, app_mod.COL_ACTION)
    offered = [combo.itemData(i) for i in range(combo.count())]
    check("The action drop-down in the table has no x,y clicks",
          all(a not in offered for a in RETIRED))
    check("The drop-down matches the actions list", offered == list(app_mod.ACTIONS))

    # --- 2. старый сценарий грузится и переводится на клик по шаблону ---
    old = [step("click_xy", "450, 300"),
           step("type_text", "hello"),
           step("double_click_xy", "10, 20"),
           step("click_xy", "1, 2")]
    tmp = tempfile.mkdtemp(prefix="macs_retired_")
    path = os.path.join(tmp, "old_scenario.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(old, f)

    win.log_view.clear()
    loaded = win._load_scenario_file(path, for_playlist=False)
    check("An old scenario with x,y clicks still loads", loaded)
    check("All its steps are kept", win.table.rowCount() == len(old))

    steps = win._all_steps()
    check("Single x,y click became a click on template",
          steps[0]["action"] == "click_image")
    check("Double x,y click became a double-click on template",
          steps[2]["action"] == "double_click_image")
    check("Other steps are untouched",
          steps[1]["action"] == "type_text" and steps[1]["value"] == "hello")

    log = win.log_view.toPlainText()
    check("The log names the steps that now need a template",
          "1, 4" in log and "3" in log and "Capture" in log)
    check("The log says which action was removed",
          "Click on coordinates (x,y)" in log
          and "Double-click on coordinates (x,y)" in log)

    # --- 3. пересохранение чинит файл: убранных действий в нём не остаётся ---
    fixed = os.path.join(tmp, "fixed.json")
    with open(fixed, "w", encoding="utf-8") as f:
        json.dump(win._all_steps(), f)
    with open(fixed, encoding="utf-8") as f:
        saved = json.load(f)
    check("Re-saving writes a file free of retired actions",
          all(st["action"] not in RETIRED for st in saved))

    win.log_view.clear()
    win._load_scenario_file(fixed, for_playlist=False)
    check("Loading the fixed file warns about nothing",
          "was removed" not in win.log_view.toPlainText())

    # --- 4. исполнитель шагов не знает про убранные действия ---
    runner_src = app_mod.Runner._exec_step.__code__.co_consts
    check("Runner has no branch for the retired actions",
          all(a not in [c for c in runner_src if isinstance(c, str)] for a in RETIRED))

    win.deleteLater()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
