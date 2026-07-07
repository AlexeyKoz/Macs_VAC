"""
AutoBuilder — визуальный конструктор автоматизации (скица).
===========================================================

Каждый шаг = строка таблицы:
  [✓ вкл] [тип действия ▼] [путь к образцу + Обзор] [значение] [таймаут] [стоп при ошибке ✓]

Управление сверху: ▶ Запустить  ⏹ Стоп  ➕ Шаг  💾 Сохранить  📂 Загрузить
Лог снизу: поэтапно, с цветом (зелёный ок / красный ошибка / серый пропущен).

Сценарий сохраняется/грузится как JSON — разные программы = разные файлы.

УСТАНОВКА:
    pip install PySide6 pyautogui pillow pytesseract opencv-python numpy
    + движок Tesseract OCR (пропиши путь в TESSERACT_PATH).

ЗАПУСК:
    python autobuilder.py
"""

import sys
import os
import json
import time
import shutil
import traceback
import ctypes


def _enable_dpi_awareness():
    """Единая система координат для Qt/pyautogui/mss (важно для мультимонитора).

    Делает процесс DPI-aware ДО создания QApplication — тогда все физические
    пиксели совпадают между снимком экрана, поиском шаблона и кликами.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_enable_dpi_awareness()

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QLabel, QTextEdit, QFileDialog, QSpinBox, QHeaderView,
    QDoubleSpinBox, QSplitter, QDialog, QScrollArea, QAbstractItemView,
    QListWidget, QListWidgetItem, QFrame,
    QStyle, QStyleOptionButton, QStyleOptionHeader, QToolTip,
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap, QPainter, QPen, QShortcut, QKeySequence, QAction

# --- Автоматизация (импортим мягко, чтобы GUI открылся даже без библиотек) ---
try:
    import pyautogui
    import pytesseract
    import cv2
    import numpy as np
    import mss
    from PIL import Image
    pyautogui.FAILSAFE = True
    AUTOMATION_OK = True
except Exception as _e:
    AUTOMATION_OK = False
    _IMPORT_ERR = str(_e)

def _find_tesseract():
    """Ищем движок Tesseract в PATH и типовых местах установки."""
    import shutil
    in_path = shutil.which("tesseract")
    if in_path:
        return in_path
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.extend([
            os.path.join(exe_dir, "Tesseract-OCR", "tesseract.exe"),
            os.path.join(exe_dir, "tesseract", "tesseract.exe"),
        ])
    candidates.extend([
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
    ])
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


TESSERACT_PATH = _find_tesseract() if AUTOMATION_OK else None
TESSERACT_OK = bool(TESSERACT_PATH)
if TESSERACT_OK:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

TESSERACT_HINT = (
    "Tesseract OCR engine not found. Install it (e.g. the UB Mannheim build) and "
    "either add it to PATH or place it at C:\\Program Files\\Tesseract-OCR\\tesseract.exe."
)

CONFIDENCE = 0.8


def template_meta_path(image_path):
    """Sidecar JSON next to the template PNG."""
    base, _ = os.path.splitext(image_path)
    return base + ".meta.json"


def load_template_meta(image_path):
    path = template_meta_path(image_path)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_template_meta(image_path, meta):
    with open(template_meta_path(image_path), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def default_template_meta(w, h):
    return {
        "compare_rect": [0, 0, w, h],
        "exclude_rects": [],
        "click_point": [w // 2, h // 2],
        "input_rect": None,
        "scroll_bar_rect": None,
    }


def resolve_template_click(meta, tw0, th0):
    """Click point in template pixels: input zone > scroll bar > click_point."""
    ir = meta.get("input_rect")
    if ir and len(ir) == 4:
        ix, iy, iw, ih = _clamp_rect(*ir, tw0, th0)
        return ix + iw // 2, iy + ih // 2
    sb = meta.get("scroll_bar_rect")
    if sb and len(sb) == 4:
        sx, sy, sw, sh = _clamp_rect(*sb, tw0, th0)
        return sx + sw // 2, sy + sh // 2
    cpx, cpy = meta.get("click_point", [tw0 // 2, th0 // 2])
    return max(0, min(int(cpx), tw0 - 1)), max(0, min(int(cpy), th0 - 1))


def _clamp_rect(x, y, w, h, max_w, max_h):
    x = max(0, min(x, max_w - 1))
    y = max(0, min(y, max_h - 1))
    w = max(1, min(w, max_w - x))
    h = max(1, min(h, max_h - y))
    return x, y, w, h


def _build_compare_mask(compare_rect, exclude_rects):
    """Mask for cv2.matchTemplate: 255 = use pixel, 0 = ignore."""
    cx, cy, cw, ch = compare_rect
    mask = np.full((ch, cw), 255, dtype=np.uint8)
    for ex, ey, ew, eh in exclude_rects:
        x1 = max(cx, ex)
        y1 = max(cy, ey)
        x2 = min(cx + cw, ex + ew)
        y2 = min(cy + ch, ey + eh)
        if x2 > x1 and y2 > y1:
            mask[y1 - cy:y2 - cy, x1 - cx:x2 - cx] = 0
    return mask


TEMPLATE_ACTIONS = frozenset({"click_image", "double_click_image", "wait_image"})
REGION_EDIT_ACTIONS = TEMPLATE_ACTIONS | {"scroll", "fill_field"}


def _editor_purpose_for_action(action):
    if action == "scroll":
        return "scroll"
    if action == "fill_field":
        return "field"
    return "template"


def _parse_xy(text):
    """Parse 'x, y' screen coordinates."""
    parts = text.replace(" ", "").split(",")
    if len(parts) < 2:
        raise ValueError("expected x,y")
    return int(parts[0]), int(parts[1])


def _is_xy(text):
    text = (text or "").strip()
    if not text or os.path.isfile(text):
        return False
    try:
        _parse_xy(text)
        return True
    except ValueError:
        return False


def parse_scroll_value(val):
    """Return signed wheel clicks for pyautogui.scroll (positive=up, negative=down)."""
    val = (val or "down, 3").strip().lower()
    if not val:
        val = "down, 3"
    parts = [p.strip() for p in val.replace(" ", "").split(",") if p.strip()]
    direction = "down"
    amount = 3
    if len(parts) == 1:
        p = parts[0]
        if p in ("down", "up"):
            direction = p
        elif p.lstrip("-").isdigit():
            n = int(p)
            direction, amount = ("up", abs(n)) if n < 0 else ("down", n)
        elif p.startswith("down") and p[4:].isdigit():
            direction, amount = "down", int(p[4:])
        elif p.startswith("up") and p[2:].isdigit():
            direction, amount = "up", int(p[2:])
    elif len(parts) >= 2:
        direction = parts[0] if parts[0] in ("down", "up") else "down"
        amount = int(parts[1]) if parts[1].lstrip("-").isdigit() else 3
    clicks = amount if direction == "up" else -amount
    return clicks, direction, amount


WHEEL_DELTA = 120   # Windows standard wheel notch size

# Алиасы для press_key_spec (ctrl+a, backspace, …)
KEY_ALIASES = {
    "control": "ctrl", "ctl": "ctrl",
    "command": "cmd", "win": "win", "windows": "win",
    "del": "delete", "bksp": "backspace", "bs": "backspace",
    "return": "enter", "esc": "escape",
    "pgup": "pageup", "pgdn": "pagedown", "page_down": "pagedown", "page_up": "pageup",
}


def press_key_spec(spec):
    """Одна клавиша или сочетание: enter, backspace, ctrl+a, ctrl+shift+s."""
    spec = (spec or "").strip().lower()
    if not spec:
        raise ValueError("empty key")
    if "+" in spec:
        parts = [KEY_ALIASES.get(p.strip(), p.strip()) for p in spec.split("+") if p.strip()]
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(KEY_ALIASES.get(spec, spec))


def parse_fill_field_value(val):
    """Разбор значения fill_field: [method:]text[|enter|tab]. method: clear|replace|paste."""
    raw = (val or "").strip()
    method = "clear"
    confirm = None
    if ":" in raw:
        prefix, rest = raw.split(":", 1)
        if prefix.lower() in ("clear", "replace", "paste"):
            method = prefix.lower()
            raw = rest.strip()
    if "|" in raw:
        raw, confirm = raw.rsplit("|", 1)
        confirm = confirm.strip().lower() or None
    return method, raw, confirm


def fill_input_field(text, method="clear", confirm_key=None, click_xy=None):
    """Клик в поле (опц.), очистка, ввод текста, подтверждение (опц.)."""
    if click_xy is not None:
        pyautogui.click(click_xy[0], click_xy[1])
        time.sleep(0.2)

    time.sleep(0.08)

    if method == "paste":
        import pyperclip
        old_clip = None
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.06)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.06)
        if old_clip is not None:
            try:
                pyperclip.copy(old_clip)
            except Exception:
                pass
    elif method == "replace":
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.06)
        pyautogui.write(text, interval=0.02)
    else:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.06)
        pyautogui.press("backspace")
        time.sleep(0.06)
        pyautogui.write(text, interval=0.02)

    if confirm_key:
        time.sleep(0.08)
        press_key_spec(confirm_key)


def perform_mouse_scroll(x, y, clicks):
    """Scroll at screen position. clicks: +up / -down in wheel notches."""
    notches = abs(int(clicks))
    if notches == 0:
        return
    sign = 1 if clicks > 0 else -1

    pyautogui.moveTo(x, y, duration=0.05)
    time.sleep(0.08)
    pyautogui.click(x, y)          # focus the scrollable panel
    time.sleep(0.1)

    if sys.platform == "win32":
        # pyautogui.scroll passes dwData=clicks without × WHEEL_DELTA — too small to see.
        user32 = ctypes.windll.user32
        for _ in range(notches):
            user32.mouse_event(0x0800, 0, 0, sign * WHEEL_DELTA, 0)  # MOUSEEVENTF_WHEEL
            time.sleep(0.04)
    else:
        pyautogui.scroll(clicks, x=x, y=y)


def grab_all():
    """Снимок ВСЕГО виртуального рабочего стола (все мониторы).

    Возвращает (PIL.Image RGB, left, top), где left/top — абсолютное
    смещение виртуального экрана (у монитора слева/сверху может быть < 0).
    Так координаты областей/точек одинаковы на любом мониторе.
    """
    factory = getattr(mss, "MSS", None) or mss.mss   # mss>=10 переименовал класс
    with factory() as sct:
        mon = sct.monitors[0]                 # индекс 0 = объединение всех мониторов
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img, mon["left"], mon["top"]

# Типы действий. Ключ = внутреннее имя, значение = что показать в списке.
ACTIONS = {
    "click_image":         "Click on template",
    "double_click_image":  "Double-click on template",
    "click_xy":            "Click on coordinates (x,y)",
    "double_click_xy":     "Double-click on coordinates (x,y)",
    "wait_image":          "Wait for template to appear",
    "scroll":              "Scroll panel (mouse wheel)",
    "key":                 "Press key / shortcut",
    "type_text":           "Type text",
    "fill_field":          "Fill input field (clear & type)",
    "ui_delete":           "Delete on-screen item (Delete key)",
    "ocr_check":           "OCR check (search for word)",
    "verify_text":         "Verify text & save proof (pass/fail)",
    "branch_image":        "IF template found → JSON A else JSON B",
    "branch_text":         "IF word found (OCR) → JSON A else JSON B",
    "branch_verify":       "IF word found → JSON A else JSON B (+ proof screenshot)",
    "screenshot":          "Screenshot of area",
    "select_target":       "Select folder/file (for next step)",
    "create_folder":       "Create folder",
    "rename_folder":       "Rename folder",
    "delete_folder":       "Delete folder on disk (by path)",
    "pause":               "Pause (seconds)",
}

# Подсказка, что писать в поле "значение" для каждого действия.
VALUE_HINT = {
    "click_image":         "(not needed)",
    "double_click_image":  "(not needed)",
    "click_xy":            "e.g. 450, 300",
    "double_click_xy":     "e.g. 450, 300",
    "wait_image":          "(not needed)",
    "scroll":              "down, 5  or  up, 3  (wheel clicks)",
    "key":                 "e.g. enter, backspace, ctrl+a, ctrl+shift+s",
    "type_text":           "text or file path",
    "fill_field":          "paste:847|enter  — capture field, set input zone",
    "ui_delete":           "empty, or 'enter' to confirm the dialog",
    "ocr_check":           "word to find, e.g. pass",
    "verify_text":         "keyword to expect, e.g. pass",
    "branch_image":        "wayA.json | wayB.json  (empty side = continue)",
    "branch_text":         "word | wayA.json | wayB.json",
    "branch_verify":       "word | wayA.json | wayB.json  (+ saves PASS/FAIL proof)",
    "screenshot":          "name, e.g. unit_{serial}\\log.png",
    "select_target":       "path to select, e.g. results\\unit_{serial}",
    "create_folder":       "path, e.g. results\\unit_{serial}",
    "rename_folder":       "new name/path (selected first), e.g. unit_{serial}_done",
    "delete_folder":       "path, or empty = use selected",
    "pause":               "seconds, e.g. 3",
}

# Колонки таблицы
COL_ON, COL_ACTION, COL_IMAGE, COL_BROWSE, COL_PREVIEW, COL_VALUE, COL_TIMEOUT, COL_FIND, COL_STOP = range(9)

BRANCH_ACTIONS = frozenset({"branch_image", "branch_text", "branch_verify"})
MAX_BRANCH_DEPTH = 25

# Подсказки к колонкам таблицы шагов (видны в панели над таблицей + при наведении на заголовок)
COLUMN_HELP = {
    COL_ON: (
        "ON — enable/disable this step.\n"
        "Unchecked steps are skipped when the scenario runs.\n"
        "The checkbox in this header toggles ALL rows at once."
    ),
    COL_ACTION: (
        "ACTION — what this step does.\n"
        "Includes conditional branches (IF … → JSON A else JSON B):\n"
        "• IF template found — branch on image on screen.\n"
        "• IF word found (OCR) — branch on text in a region.\n"
        "• IF word found (+ proof) — branch + PASS/FAIL screenshot.\n"
        "Use ↷ Branch setup to pick Way A / Way B JSON files."
    ),
    COL_IMAGE: (
        "TEMPLATE / AREA — the target for this step.\n"
        "• Image actions: path to a PNG template to find on screen.\n"
        "• OCR / screenshot actions: a screen region as x,y,w,h.\n"
        "Use the … button or 📷 Capture to fill this in automatically."
    ),
    COL_BROWSE: (
        "… (Browse) — pick a template image file from disk\n"
        "and put its path into the Template / area column."
    ),
    COL_PREVIEW: (
        "PREVIEW — thumbnail of the step's template image,\n"
        "so you can tell steps apart at a glance.\n"
        "Click a thumbnail to view it full size."
    ),
    COL_VALUE: (
        "VALUE — action-specific input.\n"
        "For branch steps: word | wayA.json | wayB.json "
        "(or wayA | wayB for image branch).\n"
        "Use ↷ Branch setup — empty side = continue this scenario.\n"
        "Tokens {serial} {date} {time} {ts} are expanded at run time."
    ),
    COL_TIMEOUT: (
        "TIMEOUT — max seconds to keep searching for the template\n"
        "or text before this step fails (or the pause length)."
    ),
    COL_FIND: (
        "FIND WIN — if the target isn't visible, cycle through open\n"
        "windows (Alt+Tab style) to bring it forward and find it.\n"
        "Default off. The header checkbox toggles ALL rows."
    ),
    COL_STOP: (
        "STOP — if this step errors, stop the whole scenario.\n"
        "If unchecked, the run continues with the next step.\n"
        "The header checkbox toggles ALL rows."
    ),
}

COLUMN_GUIDE_DEFAULT = (
    "Column guide — hover a header below for details:  "
    "On = enable step  |  Action = step type  |  Template/area = png or x,y,w,h  |  "
    "… = browse file  |  Preview = thumbnail  |  Value = extra input  |  "
    "Timeout = seconds  |  Find win = search windows  |  Stop = halt on error"
)


def parse_branch_value(action, val):
    """Разбирает Value условного шага → (keyword, path_a, path_b)."""
    parts = [p.strip() for p in (val or "").split("|")]
    if action == "branch_image":
        return "", parts[0] if len(parts) > 0 else "", parts[1] if len(parts) > 1 else ""
    return (
        parts[0] if len(parts) > 0 else "",
        parts[1] if len(parts) > 1 else "",
        parts[2] if len(parts) > 2 else "",
    )


def format_branch_value(action, keyword, path_a, path_b):
    """Собирает Value для условного шага."""
    if action == "branch_image":
        return f"{path_a} | {path_b}"
    return f"{keyword} | {path_a} | {path_b}"


def resolve_scenario_path(path, base_dir):
    """Абсолютный путь к JSON-сценарию (относительные — от папки текущего сценария)."""
    if not path or not str(path).strip():
        return ""
    path = str(path).strip()
    if os.path.isabs(path):
        return os.path.normpath(path)
    base = base_dir or os.getcwd()
    return os.path.normpath(os.path.join(base, path))


def path_for_scenario_storage(path, base_dir):
    """Сохраняем относительный путь, если JSON рядом со сценарием (удобно переносить)."""
    if not path or not str(path).strip():
        return ""
    abs_p = os.path.normpath(os.path.abspath(path))
    base = os.path.abspath(base_dir or os.getcwd())
    try:
        rel = os.path.relpath(abs_p, base)
        if not rel.startswith(".."):
            return rel
    except ValueError:
        pass
    return abs_p


# ============================================================================
# ДВИЖОК ВЫПОЛНЕНИЯ (в отдельном потоке, чтобы GUI не подвисал)
# ============================================================================

class Runner(QThread):
    log = Signal(str, str)        # (текст, уровень: info/ok/err/skip)
    finished_all = Signal()
    serial_update = Signal(str)   # следующий серийный номер (чтобы прогон продолжался)
    branch_request = Signal(str)  # путь к JSON-сценарию, на который надо перейти

    def __init__(self, steps, start_delay, own_title="AutoBuilder",
                 serial_start="0001", scenario_dir=None):
        super().__init__()
        self.steps = steps
        self.start_delay = start_delay
        self.own_title = own_title      # заголовок нашего окна (чтобы прятать его при поиске)
        self._serial = str(serial_start) or "0001"   # серийник (буквы+цифры, до 16 символов)
        self._selected = ""             # выбранная папка/файл (для delete/rename)
        self._stop = False
        self._own_minimized = False
        self._branch_target = None      # JSON, выбранный условным переходом (branch)
        self._scenario_dir = scenario_dir or os.getcwd()

    def stop(self):
        self._stop = True

    def run(self):
        if not AUTOMATION_OK:
            self.log.emit(f"Automation libraries are not installed: {_IMPORT_ERR}", "err")
            self.finished_all.emit()
            return

        self.log.emit(f"Starting in {self.start_delay} s — switch to the target window…", "info")
        for _ in range(int(self.start_delay * 2)):
            if self._stop:
                self.log.emit("Stopped before start.", "err")
                self.finished_all.emit()
                return
            time.sleep(0.5)

        try:
            for i, st in enumerate(self.steps, 1):
                if self._stop:
                    self.log.emit("⏹ Stopped by user.", "err")
                    break

                if not st["enabled"]:
                    self.log.emit(f"[{i}] {ACTIONS[st['action']]} — skipped (checkbox off)", "skip")
                    continue

                try:
                    self._exec_step(i, st)
                except Exception as e:
                    self.log.emit(f"[{i}] ✗ ERROR: {e}", "err")
                    if st["stop_on_error"]:
                        self.log.emit("Scenario stopped (stop on error).", "err")
                        break
                    else:
                        self.log.emit("Continuing with the next step.", "info")

                # условный переход: оставшиеся шаги пропускаются, дальше — другой JSON
                if self._branch_target:
                    self.log.emit(
                        f"↷ Branching to {os.path.basename(self._branch_target)} — "
                        "remaining steps of this scenario are skipped.", "info")
                    break
        finally:
            # если прятали своё окно ради «чистого рабочего стола» — вернём его
            self._restore_own()

        self.serial_update.emit(self._serial)   # запомнить, где остановился счётчик
        if self._branch_target and not self._stop:
            self.branch_request.emit(self._branch_target)
        self.log.emit("=== Done ===", "info")
        self.finished_all.emit()

    # --- реализация одного шага ---
    def _exec_step(self, i, st):
        a = st["action"]
        val = st["value"].strip()
        to = st["timeout"]
        find = st.get("find_window", False)
        label = ACTIONS[a]

        if a == "click_image":
            x, y = self._locate(st["image"], to, find)
            pyautogui.click(x, y)
            self.log.emit(f"[{i}] ✓ {label} @ ({x},{y})", "ok")

        elif a == "double_click_image":
            x, y = self._locate(st["image"], to, find)
            pyautogui.doubleClick(x, y)
            self.log.emit(f"[{i}] ✓ {label} @ ({x},{y})", "ok")

        elif a == "wait_image":
            x, y = self._locate(st["image"], to, find)
            self.log.emit(f"[{i}] ✓ {label} — found @ ({x},{y})", "ok")

        elif a == "click_xy":
            x, y = [int(v) for v in val.replace(" ", "").split(",")]
            pyautogui.click(x, y)
            self.log.emit(f"[{i}] ✓ {label} @ ({x},{y})", "ok")

        elif a == "double_click_xy":
            x, y = [int(v) for v in val.replace(" ", "").split(",")]
            pyautogui.doubleClick(x, y)
            self.log.emit(f"[{i}] ✓ {label} @ ({x},{y})", "ok")

        elif a == "scroll":
            target = st["image"].strip()
            if not target:
                raise RuntimeError(
                    "Scroll needs a template PNG in Template/area — capture a large "
                    "area with 📷, then mark compare / exclude / scroll bar regions."
                )
            if _is_xy(target):
                x, y = _parse_xy(target)
            elif os.path.isfile(target):
                x, y = self._locate(target, to, find)
            else:
                raise RuntimeError(f"scroll template not found: {target}")
            clicks, direction, amount = parse_scroll_value(val)
            perform_mouse_scroll(x, y, clicks)
            self.log.emit(
                f"[{i}] ✓ {label} {direction} ×{amount} @ ({x},{y})",
                "ok",
            )

        elif a == "key":
            press_key_spec(val)
            self.log.emit(f"[{i}] ✓ {label}: {val}", "ok")

        elif a == "type_text":
            text = self._expand(val)
            pyautogui.write(text, interval=0.01)
            self.log.emit(f"[{i}] ✓ {label}: {text}", "ok")

        elif a == "fill_field":
            method, text_raw, confirm = parse_fill_field_value(val)
            text = self._expand(text_raw)
            if not text and text_raw:
                text = text_raw
            click_xy = None
            target = st["image"].strip()
            if not target:
                raise RuntimeError(
                    "Fill field needs a template — capture label + input with 📷, "
                    "then set Compare (green) and Input zone (blue) in the editor."
                )
            if _is_xy(target):
                click_xy = _parse_xy(target)
            elif os.path.isfile(target):
                click_xy = self._locate(target, to, find)
            else:
                raise RuntimeError(f"fill field target not found: {target}")
            fill_input_field(text, method=method, confirm_key=confirm, click_xy=click_xy)
            extra = f" + {confirm}" if confirm else ""
            self.log.emit(
                f"[{i}] ✓ {label} ({method}): {text!r}{extra}"
                + (f" @ {click_xy}" if click_xy else ""),
                "ok",
            )

        elif a == "ui_delete":
            # UI-удаление: жмём Delete по тому, что выделено на экране (после click).
            # Значение 'enter'/'confirm'/'yes' -> ещё и подтверждаем диалог.
            pyautogui.press("delete")
            confirm = val.lower() in ("enter", "confirm", "yes", "y", "ok")
            if confirm:
                time.sleep(0.6)          # дать появиться диалогу подтверждения
                pyautogui.press("enter")
            self.log.emit(f"[{i}] ✓ {label}{' + confirm' if confirm else ''}", "ok")

        elif a == "ocr_check":
            found, text = self._find_text(st["image"], val, to, find)
            lvl = "ok" if found else "err"
            self.log.emit(f"[{i}] {'✓' if found else '✗'} {label} '{val}': "
                          f"{'FOUND' if found else 'not found'}", lvl)
            if not found:
                raise RuntimeError(f"word '{val}' not found in OCR")

        elif a == "verify_text":
            # OCR-проверка области + сохранение скриншота-доказательства (pass/fail)
            os.makedirs("results", exist_ok=True)
            found, text = self._find_text(st["image"], val, to, find)
            status = "PASS" if found else "FAIL"
            img, left, top = grab_all()
            region = self._region_tuple(st["image"])
            if region:
                x, y, w, hh = region
                img = img.crop((x - left, y - top, x - left + w, y - top + hh))
            safe = "".join(c if c.isalnum() else "_" for c in (val or "check"))
            path = os.path.join("results", f"{status}_{safe}_{int(time.time())}.png")
            img.save(path)
            lvl = "ok" if found else "err"
            self.log.emit(f"[{i}] {'✓' if found else '✗'} {label} '{val}': {status} → {path}", lvl)
            if not found:
                raise RuntimeError(f"verification failed: '{val}' not found")

        elif a == "screenshot":
            name = self._expand(val) or f"shot_{int(time.time())}.png"
            # без папки/не абсолютный путь -> кладём в results\
            if not os.path.isabs(name) and not os.path.dirname(name):
                name = os.path.join("results", name)
            os.makedirs(os.path.dirname(name) or ".", exist_ok=True)
            img, left, top = grab_all()
            region = self._region_tuple(st["image"])
            if region:
                x, y, w, hh = region
                img = img.crop((x - left, y - top, x - left + w, y - top + hh))
            img.save(name)
            self.log.emit(f"[{i}] ✓ {label} → {name}", "ok")

        elif a == "select_target":
            target = self._expand(val)
            if not target:
                raise RuntimeError("no path to select")
            self._selected = target
            self.log.emit(f"[{i}] ✓ {label}: {os.path.abspath(target)}", "ok")

        elif a == "create_folder":
            target = self._expand(val)
            if not target:
                raise RuntimeError("no folder path given")
            os.makedirs(target, exist_ok=True)
            self._selected = target          # созданную папку сразу считаем выбранной
            self.log.emit(f"[{i}] ✓ {label}: {os.path.abspath(target)}", "ok")

        elif a == "rename_folder":
            old = self._selected
            if not old:
                raise RuntimeError("nothing selected — add a 'Select folder/file' step first")
            new_name = self._expand(val)
            if not new_name:
                raise RuntimeError("no new name/path given")
            # только имя -> в той же папке; иначе абсолютный/относительный путь как есть
            if os.path.isabs(new_name) or os.path.dirname(new_name):
                dest = new_name
            else:
                dest = os.path.join(os.path.dirname(old), new_name)
            if not os.path.exists(old):
                raise FileNotFoundError(f"selected path not found: {old}")
            os.rename(old, dest)
            self._selected = dest            # переименованный объект остаётся выбранным
            self.log.emit(f"[{i}] ✓ {label}: {os.path.abspath(old)} → {os.path.abspath(dest)}", "ok")

        elif a == "delete_folder":
            target = self._expand(val) or self._selected
            if not target:
                raise RuntimeError(
                    "nothing to delete — this deletes a folder ON DISK. Type a path "
                    "in Value (e.g. results\\unit_{serial}) or add a 'Select folder/file' "
                    "step first. To delete an item you clicked on screen, use the "
                    "'Delete on-screen item (Delete key)' action instead."
                )
            self._safe_rmtree(target)
            if os.path.abspath(target) == os.path.abspath(self._selected or ""):
                self._selected = ""          # выбранное удалено
            self.log.emit(f"[{i}] ✓ {label}: {os.path.abspath(target)}", "ok")

        elif a == "pause":
            sec = float(val or "1")
            self.log.emit(f"[{i}] … {label} {sec} s", "info")
            waited = 0.0
            while waited < sec:
                if self._stop:
                    return
                time.sleep(0.2)
                waited += 0.2
            self.log.emit(f"[{i}] ✓ {label} finished", "ok")

        elif a in ("branch_image", "branch_text", "branch_verify"):
            # Условный переход («узел»): проверяем условие и выбираем JSON-сценарий.
            # Пустой путь на выбранной стороне = продолжаем текущий сценарий.
            keyword, path_a, path_b = parse_branch_value(a, val)
            if a == "branch_image":
                if not path_a and not path_b:
                    raise RuntimeError(
                        "Configure branch paths: Way A | Way B "
                        "(use ↷ Branch setup button)")
                try:
                    self._locate(st["image"], to, find)
                    found = True
                except TimeoutError:
                    found = False
                cond = "template FOUND" if found else "template NOT found"
            else:
                if not keyword:
                    raise RuntimeError("branch keyword is empty")
                if not path_a and not path_b:
                    raise RuntimeError(
                        "Configure branch paths: word | Way A | Way B "
                        "(use ↷ Branch setup button)")
                found, _ = self._find_text(st["image"], keyword, to, find)
                cond = f"'{keyword}' FOUND" if found else f"'{keyword}' NOT found"
                if a == "branch_verify":
                    os.makedirs("results", exist_ok=True)
                    status = "PASS" if found else "FAIL"
                    img, left, top = grab_all()
                    region = self._region_tuple(st["image"])
                    if region:
                        x, y, w, hh = region
                        img = img.crop((x - left, y - top, x - left + w, y - top + hh))
                    safe = "".join(c if c.isalnum() else "_" for c in (keyword or "check"))
                    proof = os.path.join("results", f"{status}_{safe}_{int(time.time())}.png")
                    img.save(proof)
                    self.log.emit(f"[{i}]   proof screenshot → {proof}", "info")

            side = "A" if found else "B"
            raw = path_a if found else path_b
            target = self._resolve_branch_path(raw)
            if not target:
                self.log.emit(
                    f"[{i}] ✓ {label}: {cond} → way {side} is empty, "
                    "continuing this scenario", "ok")
            else:
                if not os.path.isfile(target):
                    raise FileNotFoundError(f"branch scenario not found: {target}")
                self._branch_target = target
                self.log.emit(
                    f"[{i}] ✓ {label}: {cond} → way {side}: "
                    f"{os.path.basename(target)}", "ok")

    # масштабы для мультимасштабного поиска (DPI/разное разрешение экрана)
    _SCALES = (1.0, 0.9, 1.1, 0.8, 1.25, 0.75, 0.67, 1.5, 0.6, 0.5, 2.0)

    def _locate(self, image_path, timeout, find_window=False):
        # Ищем шаблон по ВСЕМ мониторам через cv2 (pyautogui умеет только primary).
        # Многомасштабно + оттенки серого + контуры — устойчиво к DPI/теме/подсветке.
        # .meta.json: compare_rect, exclude_rects (игнорировать), click_point.
        # find_window: если не нашли — перебираем окна (как Alt+Tab) и повторяем.
        # Возвращаем (x, y) в абсолютных координатах виртуального экрана.
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"template not found: {image_path}")
        templ = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if templ is None:
            raise FileNotFoundError(f"cannot read template image: {image_path}")

        th0, tw0 = templ.shape[:2]
        meta = load_template_meta(image_path)
        if meta is None:
            meta = default_template_meta(tw0, th0)

        cx, cy, cw, ch = _clamp_rect(*meta["compare_rect"], tw0, th0)
        compare_rect = (cx, cy, cw, ch)
        exclude_rects = meta.get("exclude_rects") or []
        cpx, cpy = resolve_template_click(meta, tw0, th0)

        compare_bgr = templ[cy:cy + ch, cx:cx + cw]
        compare_gray = cv2.cvtColor(compare_bgr, cv2.COLOR_BGR2GRAY)
        compare_edge = cv2.Canny(compare_gray, 50, 150)
        mask = _build_compare_mask(compare_rect, exclude_rects)
        use_mask = bool(exclude_rects) and int(mask.sum()) > 0

        best = 0.0
        best_scale = 1.0

        def detect():
            nonlocal best, best_scale
            img, left, top = grab_all()
            scene = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            scene_edge = cv2.Canny(scene, 50, 150)
            sh, sw = scene.shape[:2]
            for scale in self._SCALES:
                tw, th = int(cw * scale), int(ch * scale)
                if tw < 8 or th < 8 or th > sh or tw > sw:
                    continue
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                tg = cv2.resize(compare_gray, (tw, th), interpolation=interp)
                te = cv2.resize(compare_edge, (tw, th), interpolation=interp)
                if use_mask:
                    ms = cv2.resize(mask, (tw, th), interpolation=cv2.INTER_NEAREST)
                    _, gv, _, gloc = cv2.minMaxLoc(
                        cv2.matchTemplate(scene, tg, cv2.TM_CCORR_NORMED, mask=ms))
                    _, ev, _, eloc = cv2.minMaxLoc(
                        cv2.matchTemplate(scene_edge, te, cv2.TM_CCORR_NORMED, mask=ms))
                else:
                    _, gv, _, gloc = cv2.minMaxLoc(cv2.matchTemplate(scene, tg, cv2.TM_CCOEFF_NORMED))
                    _, ev, _, eloc = cv2.minMaxLoc(cv2.matchTemplate(scene_edge, te, cv2.TM_CCOEFF_NORMED))

                maxv, maxloc = (gv, gloc) if gv >= ev else (ev, eloc)
                if maxv > best:
                    best, best_scale = maxv, scale
                if maxv >= CONFIDENCE:
                    click_x = left + maxloc[0] - int(cx * scale) + int(cpx * scale)
                    click_y = top + maxloc[1] - int(cy * scale) + int(cpy * scale)
                    return (click_x, click_y)
            return None

        res = self._search(detect, timeout, find_window)
        if res is None:
            raise TimeoutError(
                f"not found on screen within {timeout} s "
                f"(best match {best:.2f} at scale {best_scale}): {image_path}"
            )
        return res

    # ---------- поиск с перебором окон (Alt+Tab) ----------

    def _search(self, detect, timeout, find_window):
        """Повторяет detect() до таймаута.

        detect() -> результат (истинный) или None. Возвращает результат или None.
        При find_window: СНАЧАЛА чистим рабочий стол (сворачиваем все окна),
        затем показываем окна по одному и проверяем каждое.
        """
        if self._stop:
            raise RuntimeError("stopped")

        if not find_window:
            # обычный режим: опрашиваем текущий экран до таймаута
            res = detect()
            if res is not None:
                return res
            t0 = time.time()
            while time.time() - t0 < timeout:
                if self._stop:
                    raise RuntimeError("stopped")
                time.sleep(0.4)
                res = detect()
                if res is not None:
                    return res
            return None

        # режим поиска окна: чистый рабочий стол -> окна по одному
        self._minimize_own()                # прячем и СВОЁ окно, чтобы не перекрывало экран
        windows = self._list_windows()
        self._minimize_all(windows)
        time.sleep(0.6)
        res = detect()                      # вдруг цель на самом рабочем столе (иконки)
        if res is not None:
            return res

        idx = 0
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._stop:
                raise RuntimeError("stopped")
            if not windows:
                time.sleep(0.4)
                res = detect()
                if res is not None:
                    return res
                continue
            w = windows[idx % len(windows)]
            idx += 1
            self._activate_window(w)
            time.sleep(0.5)                 # дать окну выйти на передний план
            res = detect()
            if res is not None:
                return res
            self._minimize_window(w)        # снова спрятать — показываем строго по одному
        return None

    def _list_windows(self):
        try:
            import pygetwindow as gw
        except Exception as e:
            self.log.emit(f"    window search needs pygetwindow ({e})", "err")
            return []
        out = []
        try:
            for w in gw.getAllWindows():
                try:
                    if w.title and w.visible and w.width > 1 and w.height > 1 \
                            and "AutoBuilder" not in w.title:
                        out.append(w)
                except Exception:
                    continue
        except Exception:
            pass
        self.log.emit(f"    window search: scanning {len(out)} window(s)…", "info")
        return out

    def _activate_window(self, w):
        try:
            if getattr(w, "isMinimized", False):
                w.restore()
            w.activate()
            self.log.emit(f"    → window: {w.title[:50]}", "info")
        except Exception:
            # activate() иногда бросает на Windows — пробуем «встряхнуть» окно
            try:
                w.minimize()
                w.restore()
            except Exception:
                pass

    def _minimize_all(self, windows):
        self.log.emit("    clearing desktop (minimizing all windows)…", "info")
        for w in windows:
            self._minimize_window(w)

    @staticmethod
    def _minimize_window(w):
        try:
            if not getattr(w, "isMinimized", False):
                w.minimize()
        except Exception:
            pass

    def _own_windows(self):
        """Наши собственные окна (по заголовку) — чтобы прятать/возвращать их."""
        try:
            import pygetwindow as gw
        except Exception:
            return []
        out = []
        for w in gw.getAllWindows():
            try:
                if w.title and "AutoBuilder" in w.title:
                    out.append(w)
            except Exception:
                continue
        return out

    def _minimize_own(self):
        for w in self._own_windows():
            try:
                if not getattr(w, "isMinimized", False):
                    w.minimize()
                    self._own_minimized = True
            except Exception:
                pass

    def _restore_own(self):
        if not self._own_minimized:
            return
        for w in self._own_windows():
            try:
                if getattr(w, "isMinimized", False):
                    w.restore()
            except Exception:
                pass
        self._own_minimized = False

    def _find_text(self, region_str, keyword, timeout, find_window):
        """Ищем keyword в OCR-области. При find_window перебираем окна.

        Возвращает (found: bool, last_text: str).
        """
        self._last_text = ""
        kw = keyword.lower()

        def detect():
            text = self._ocr(region_str)
            self._last_text = text
            return True if kw in text.lower() else None

        # без find_window — одна проверка (как раньше); с ним — до таймаута
        res = self._search(detect, timeout if find_window else 0, find_window)
        return (res is True), self._last_text

    def _expand(self, text):
        """Подставляет токены в строку (пути/имена/вводимый текст).

        {serial} — текущий серийник (буквы+цифры), затем инкремент числовой части.
        {date} = ГГГГ-ММ-ДД, {time} = ЧЧММСС, {ts} = epoch-секунды.
        """
        if not text:
            return text
        now = time.localtime()
        text = text.replace("{date}", time.strftime("%Y-%m-%d", now))
        text = text.replace("{time}", time.strftime("%H%M%S", now))
        text = text.replace("{ts}", str(int(time.time())))
        if "{serial}" in text:
            text = text.replace("{serial}", self._serial)
            self._serial = self._increment_serial(self._serial)   # каждое использование +1
        return text

    def _resolve_branch_path(self, path):
        """Путь к JSON ветки: токены + относительный путь от папки сценария."""
        if not path:
            return ""
        expanded = self._expand(path.strip())
        return resolve_scenario_path(expanded, self._scenario_dir)

    @staticmethod
    def _increment_serial(s):
        """Увеличивает серийник на 1, сохраняя префикс и ширину числовой части.

        Примеры: 0001->0002, SN0099->SN0100, AB->AB1, unit_09z->unit_10z? (нет —
        инкрементируется ХВОСТОВАЯ группа цифр). Длина ограничена 16 символами.
        """
        s = str(s)
        # найти хвостовую группу цифр
        i = len(s)
        while i > 0 and s[i - 1].isdigit():
            i -= 1
        prefix, digits = s[:i], s[i:]
        if digits:
            width = len(digits)
            nxt = str(int(digits) + 1)
            new = prefix + (nxt.zfill(width) if len(nxt) <= width else nxt)
        else:
            new = s + "1"     # нет цифр в хвосте — начинаем счёт
        return new[:16]

    @staticmethod
    def _safe_rmtree(path):
        """Удаляет папку с защитой от опасных путей (корни дисков и т.п.)."""
        if not path:
            raise RuntimeError("no folder path given")
        p = os.path.abspath(path)
        drive, tail = os.path.splitdrive(p)
        if not tail.strip("\\/"):
            raise RuntimeError(f"refusing to delete drive root: {p}")
        if not os.path.exists(p):
            raise FileNotFoundError(f"folder not found: {p}")
        if not os.path.isdir(p):
            raise RuntimeError(f"not a folder: {p}")
        shutil.rmtree(p)

    @staticmethod
    def _region_tuple(region_str):
        # region_str: "x,y,w,h" -> (x,y,w,h) или None
        if region_str and "," in region_str:
            try:
                parts = tuple(int(v) for v in region_str.replace(" ", "").split(","))
                if len(parts) == 4:
                    return parts
            except ValueError:
                return None
        return None

    def _ocr(self, region_str):
        # region_str: "x,y,w,h" (абс. координаты) или пусто = весь виртуальный экран
        if not TESSERACT_OK:
            raise RuntimeError(TESSERACT_HINT)
        shot, left, top = grab_all()
        region = self._region_tuple(region_str)
        if region:
            x, y, w, h = region
            shot = shot.crop((x - left, y - top, x - left + w, y - top + h))
        img = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        img = cv2.resize(img, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return pytesseract.image_to_string(img)


# ============================================================================
# ОВЕРЛЕЙ ВЫДЕЛЕНИЯ ОБЛАСТИ (снимок экрана + рамка мышью)
# ============================================================================

class SnipOverlay(QWidget):
    """Полноэкранный оверлей поверх «замороженного» снимка экрана.

    Пользователь тянет прямоугольник мышью. По отпусканию вызывается
    on_done(rect, screen_geometry). rect — в координатах виджета (= логические
    экранные координаты со смещением geo). Esc или пустое выделение = отмена.
    """

    def __init__(self, pixmap, on_done):
        super().__init__()
        self._on_done = on_done
        self._origin = None
        self._rubber = QRect()

        # вся виртуальная область (объединение всех мониторов)
        self._geo = QApplication.primaryScreen().virtualGeometry()
        # масштабируем снимок под геометрию экрана, чтобы координаты совпадали
        self._pix = pixmap.scaled(
            self._geo.width(), self._geo.height(),
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(self._geo)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._pix)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        if not self._rubber.isNull():
            # показать выбранную область в полной яркости
            p.drawPixmap(self._rubber, self._pix, self._rubber)
            p.setPen(QPen(QColor("#00c8ff"), 2))
            p.drawRect(self._rubber)
            hint = f"{self._rubber.width()} × {self._rubber.height()}"
            p.setPen(QColor("#ffffff"))
            p.drawText(self._rubber.topLeft() + QPoint(2, -6), hint)

    def mousePressEvent(self, e):
        self._origin = e.pos()
        self._rubber = QRect(self._origin, self._origin)
        self.update()

    def mouseMoveEvent(self, e):
        if self._origin is not None:
            self._rubber = QRect(self._origin, e.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, _e):
        rect = self._rubber.normalized()
        self.close()
        if rect.width() > 3 and rect.height() > 3:
            self._on_done(rect, self._geo)
        else:
            self._on_done(None, self._geo)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self._on_done(None, self._geo)


# ============================================================================
# РЕДАКТОР ШАБЛОНА (сравнение / исключение / точка клика)
# ============================================================================

class TemplateEditorCanvas(QWidget):
    """Рисуем на захваченном шаблоне: compare, exclude, click / scroll bar."""

    def __init__(self, image_path, purpose="template"):
        super().__init__()
        self._purpose = purpose
        self._pix = QPixmap(image_path)
        self._img_w = max(self._pix.width(), 1)
        self._img_h = max(self._pix.height(), 1)
        self._mode = "compare"
        self._compare = QRect(0, 0, self._img_w, self._img_h)
        self._excludes = []
        self._click = QPoint(self._img_w // 2, self._img_h // 2)
        self._input_rect = None
        self._scroll_bar = None
        self._origin = None
        self._rubber = QRect()
        self.setMinimumSize(480, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_mode(self, mode):
        self._mode = mode
        self._origin = None
        self._rubber = QRect()
        self.update()

    def load_meta(self, meta):
        cx, cy, cw, ch = meta.get("compare_rect", [0, 0, self._img_w, self._img_h])
        cx, cy, cw, ch = _clamp_rect(cx, cy, cw, ch, self._img_w, self._img_h)
        self._compare = QRect(cx, cy, cw, ch)
        self._excludes = []
        for r in meta.get("exclude_rects") or []:
            if len(r) == 4:
                x, y, w, h = _clamp_rect(*r, self._img_w, self._img_h)
                self._excludes.append(QRect(x, y, w, h))
        px, py = meta.get("click_point", [self._img_w // 2, self._img_h // 2])
        self._click = QPoint(max(0, min(int(px), self._img_w - 1)),
                             max(0, min(int(py), self._img_h - 1)))
        ir = meta.get("input_rect")
        if ir and len(ir) == 4:
            x, y, w, h = _clamp_rect(*ir, self._img_w, self._img_h)
            self._input_rect = QRect(x, y, w, h)
            self._click = QPoint(x + w // 2, y + h // 2)
        else:
            self._input_rect = None
        sb = meta.get("scroll_bar_rect")
        if sb and len(sb) == 4:
            x, y, w, h = _clamp_rect(*sb, self._img_w, self._img_h)
            self._scroll_bar = QRect(x, y, w, h)
            self._click = QPoint(x + w // 2, y + h // 2)
        else:
            self._scroll_bar = None
        self.update()

    def get_meta(self):
        c = self._compare
        meta = {
            "compare_rect": [c.x(), c.y(), c.width(), c.height()],
            "exclude_rects": [[r.x(), r.y(), r.width(), r.height()] for r in self._excludes],
            "click_point": [self._click.x(), self._click.y()],
        }
        if self._input_rect is not None and not self._input_rect.isNull():
            r = self._input_rect
            meta["input_rect"] = [r.x(), r.y(), r.width(), r.height()]
        else:
            meta["input_rect"] = None
        if self._scroll_bar is not None and not self._scroll_bar.isNull():
            r = self._scroll_bar
            meta["scroll_bar_rect"] = [r.x(), r.y(), r.width(), r.height()]
        else:
            meta["scroll_bar_rect"] = None
        return meta

    def reset_compare_full(self):
        self._compare = QRect(0, 0, self._img_w, self._img_h)
        self.update()

    def remove_last_exclude(self):
        if self._excludes:
            self._excludes.pop()
            self.update()

    def clear_excludes(self):
        self._excludes.clear()
        self.update()

    def clear_input_zone(self):
        self._input_rect = None
        self.update()

    def _auto_exclude_input_value(self, rect):
        """Changing value inside input — ignore for matching, still clickable."""
        for ex in self._excludes:
            if ex.contains(rect.center()):
                return
        self._excludes.append(QRect(rect))

    def _layout(self):
        scale = min(self.width() / self._img_w, self.height() / self._img_h)
        dw, dh = self._img_w * scale, self._img_h * scale
        ox = (self.width() - dw) / 2
        oy = (self.height() - dh) / 2
        return scale, ox, oy, dw, dh

    def _img_to_disp_rect(self, rect):
        scale, ox, oy, _, _ = self._layout()
        return QRect(
            int(ox + rect.x() * scale),
            int(oy + rect.y() * scale),
            max(1, int(rect.width() * scale)),
            max(1, int(rect.height() * scale)),
        )

    def _img_to_disp_point(self, pt):
        scale, ox, oy, _, _ = self._layout()
        return QPoint(int(ox + pt.x() * scale), int(oy + pt.y() * scale))

    def _disp_to_img(self, pt):
        scale, ox, oy, dw, dh = self._layout()
        if pt.x() < ox or pt.y() < oy or pt.x() > ox + dw or pt.y() > oy + dh:
            return None
        ix = int((pt.x() - ox) / scale)
        iy = int((pt.y() - oy) / scale)
        return QPoint(max(0, min(ix, self._img_w - 1)), max(0, min(iy, self._img_h - 1)))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1e1e1e"))
        scale, ox, oy, dw, dh = self._layout()
        target = QRect(int(ox), int(oy), int(dw), int(dh))
        p.drawPixmap(target, self._pix)

        # exclude — красная штриховка (ignored when FINDING only)
        for rect in self._excludes:
            dr = self._img_to_disp_rect(rect)
            p.fillRect(dr, QColor(255, 60, 60, 90))
            p.setPen(QPen(QColor("#ff5555"), 2, Qt.DashLine))
            p.drawRect(dr)

        # input zone — синяя зона (click & type here)
        if self._input_rect is not None and not self._input_rect.isNull():
            dr = self._img_to_disp_rect(self._input_rect)
            p.fillRect(dr, QColor(66, 165, 245, 70))
            p.setPen(QPen(QColor("#42a5f5"), 2))
            p.drawRect(dr)

        # compare — зелёная рамка
        dr = self._img_to_disp_rect(self._compare)
        p.fillRect(dr, QColor(0, 200, 80, 35))
        p.setPen(QPen(QColor("#00e676"), 2))
        p.drawRect(dr)

        # rubber band while dragging
        if not self._rubber.isNull() and self._mode in ("compare", "exclude", "scroll", "input"):
            colors = {"scroll": "#ff9800", "input": "#42a5f5", "exclude": "#ff5555"}
            color = colors.get(self._mode, "#00c8ff")
            p.setPen(QPen(QColor(color), 2, Qt.DashLine))
            p.drawRect(self._rubber)

        # scroll bar area — оранжевая рамка
        if self._scroll_bar is not None and not self._scroll_bar.isNull():
            dr = self._img_to_disp_rect(self._scroll_bar)
            p.fillRect(dr, QColor(255, 152, 0, 60))
            p.setPen(QPen(QColor("#ff9800"), 2))
            p.drawRect(dr)

        # click / wheel point — синий крест
        cp = self._img_to_disp_point(self._click)
        arm = 10
        p.setPen(QPen(QColor("#42a5f5"), 2))
        p.drawLine(cp.x() - arm, cp.y(), cp.x() + arm, cp.y())
        p.drawLine(cp.x(), cp.y() - arm, cp.x(), cp.y() + arm)
        p.setBrush(QColor("#42a5f5"))
        p.drawEllipse(cp, 4, 4)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._mode == "click":
            pt = self._disp_to_img(e.pos())
            if pt is not None:
                self._click = pt
                self._scroll_bar = None
                self._input_rect = None
                self.update()
            return
        self._origin = e.pos()
        self._rubber = QRect(self._origin, self._origin)

    def mouseMoveEvent(self, e):
        if self._origin is not None and self._mode in ("compare", "exclude", "scroll", "input"):
            self._rubber = QRect(self._origin, e.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._origin is None:
            return
        if self._mode not in ("compare", "exclude", "scroll", "input"):
            return
        p1 = self._disp_to_img(self._origin)
        p2 = self._disp_to_img(e.pos())
        self._origin = None
        self._rubber = QRect()
        if p1 is None or p2 is None:
            self.update()
            return
        x1, y1 = min(p1.x(), p2.x()), min(p1.y(), p2.y())
        x2, y2 = max(p1.x(), p2.x()), max(p1.y(), p2.y())
        if x2 - x1 < 3 and y2 - y1 < 3:
            if self._mode == "scroll":
                pt = self._disp_to_img(e.pos())
                if pt is not None:
                    self._click = pt
                    self._scroll_bar = None
            self.update()
            return
        rect = QRect(x1, y1, x2 - x1, y2 - y1)
        if self._mode == "compare":
            self._compare = rect
        elif self._mode == "scroll":
            self._scroll_bar = rect
            self._click = QPoint(rect.x() + rect.width() // 2,
                                 rect.y() + rect.height() // 2)
            self._input_rect = None
        elif self._mode == "input":
            self._input_rect = rect
            self._click = QPoint(rect.x() + rect.width() // 2,
                                 rect.y() + rect.height() // 2)
            self._scroll_bar = None
            if self._purpose == "field":
                self._auto_exclude_input_value(rect)
        else:
            self._excludes.append(rect)
        self.update()


class TemplateEditorDialog(QDialog):
    """После захвата: задать compare / exclude / click или scroll bar."""

    def __init__(self, image_path, parent=None, purpose="template"):
        super().__init__(parent)
        self._path = image_path
        self._purpose = purpose
        is_scroll = purpose == "scroll"
        is_field = purpose == "field"
        if is_scroll:
            title = "Scroll regions — compare / exclude / scroll bar"
        elif is_field:
            title = "Input field — find / ignore value / type here"
        else:
            title = "Template regions — compare / exclude / click"
        self.setWindowTitle(title)
        self.setMinimumSize(720, 520)

        root = QVBoxLayout(self)
        if is_scroll:
            hint = QLabel(
                "<b>Green</b> = stable area to find this panel on screen. "
                "<b>Red</b> = ignored (changing content). "
                "<b>Orange</b> = scroll bar / wheel target (drag over the scrollbar)."
            )
        elif is_field:
            hint = QLabel(
                "<b>Green</b> = stable frame (label, border) — used to FIND the field. "
                "<b>Red</b> = current value — IGNORED when finding (numbers change). "
                "<b>Blue</b> = input zone — where to CLICK and TYPE (can overlap red)."
            )
        else:
            hint = QLabel(
                "<b>Green</b> = area used to find this on screen. "
                "<b>Red</b> = ignored (e.g. changing numbers). "
                "<b>Blue cross</b> = where to click."
            )
        hint.setWordWrap(True)
        root.addWidget(hint)

        modes = QHBoxLayout()
        self._btn_compare = QPushButton("1. Compare (match)")
        self._btn_exclude = QPushButton(
            "2. Value (ignore)" if is_field else "2. Exclude (ignore)"
        )
        if is_scroll:
            btn3_label, btn3_mode = "3. Scroll bar", "scroll"
        elif is_field:
            btn3_label, btn3_mode = "3. Input zone (type)", "input"
        else:
            btn3_label, btn3_mode = "3. Click point", "click"
        self._btn_click = QPushButton(btn3_label)
        mode_map = (
            (self._btn_compare, "compare"),
            (self._btn_exclude, "exclude"),
            (self._btn_click, btn3_mode),
        )
        for btn, mode in mode_map:
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            modes.addWidget(btn)
        root.addLayout(modes)

        self._canvas = TemplateEditorCanvas(image_path, purpose=purpose)
        meta = load_template_meta(image_path)
        if meta:
            self._canvas.load_meta(meta)
        root.addWidget(self._canvas, stretch=1)

        if is_scroll:
            help_text = (
                "Capture a large area, then: Compare = unique stable frame around the list. "
                "Exclude = changing list items/numbers. Scroll bar = drag a rectangle over "
                "the vertical scrollbar (wheel events go to its center)."
            )
        elif is_field:
            help_text = (
                "Capture label + input box together. Compare = stable label/frame. "
                "Value (ignore) = digits already shown (optional if Input zone covers them). "
                "Input zone = drag over the editable box — app finds by green, clicks blue, "
                "types your value. Red areas are NOT used for matching but ARE still clickable."
            )
        else:
            help_text = (
                "Compare: drag a rectangle. Exclude: drag one or more rectangles "
                "over changing fields. Click: single-click the button/target."
            )
        help_l = QLabel(help_text)
        help_l.setStyleSheet("color:#aaa; font-size:11px;")
        help_l.setWordWrap(True)
        root.addWidget(help_l)

        tools = QHBoxLayout()
        btn_full = QPushButton("Reset compare → full image")
        btn_full.clicked.connect(self._canvas.reset_compare_full)
        tools.addWidget(btn_full)
        btn_undo = QPushButton("Remove last exclude")
        btn_undo.clicked.connect(self._canvas.remove_last_exclude)
        tools.addWidget(btn_undo)
        btn_clear = QPushButton("Clear all excludes")
        btn_clear.clicked.connect(self._canvas.clear_excludes)
        tools.addWidget(btn_clear)
        if is_field:
            btn_clear_in = QPushButton("Clear input zone")
            btn_clear_in.clicked.connect(self._canvas.clear_input_zone)
            tools.addWidget(btn_clear_in)
        tools.addStretch()
        root.addLayout(tools)

        btns = QHBoxLayout()
        btns.addStretch()
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        root.addLayout(btns)

        self._set_mode("compare")

    def _set_mode(self, mode):
        self._canvas.set_mode(mode)
        self._btn_compare.setChecked(mode == "compare")
        self._btn_exclude.setChecked(mode == "exclude")
        self._btn_click.setChecked(mode in ("click", "scroll", "input"))

    def save_meta(self):
        save_template_meta(self._path, self._canvas.get_meta())


# ============================================================================
# ПРЕВЬЮ ШАБЛОНА (миниатюра в строке + просмотр в полном размере)
# ============================================================================

class ThumbLabel(QLabel):
    """Маленькая кликабельная миниатюра шаблона внутри строки таблицы.

    Показывает уменьшенную картинку шаблона (если путь ведёт к файлу-картинке).
    Для OCR-области (x,y,w,h) или пустого поля показывает прочерк. Клик по
    миниатюре с картинкой открывает просмотр в полном размере (сигнал clicked).
    """

    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(72, 44)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self._path = ""
        self._set_placeholder("—")

    def _set_placeholder(self, text):
        self.setPixmap(QPixmap())
        self.setText(text)
        self.setStyleSheet(
            "border:1px solid #555; background:#2b2b2b; color:#777; font-size:11px;"
        )
        self.setCursor(Qt.ArrowCursor)

    def set_image(self, path):
        """Обновляет миниатюру по пути. Пусто/не картинка -> прочерк."""
        path = (path or "").strip()
        self._path = path
        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                thumb = pix.scaled(
                    self.width() - 4, self.height() - 4,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.setText("")
                self.setPixmap(thumb)
                self.setStyleSheet(
                    "border:1px solid #00c8ff; background:#1e1e1e;"
                )
                self.setCursor(Qt.PointingHandCursor)
                self.setToolTip(f"Click to view full size:\n{path}")
                return
        # region "x,y,w,h" -> подскажем, что это OCR-область
        if "," in path:
            self._set_placeholder("area")
            self.setToolTip(f"OCR/area region (no image file):\n{path}")
        else:
            self._set_placeholder("—")
            self.setToolTip("No template image for this step yet.")

    def mousePressEvent(self, e):
        if self._path and os.path.isfile(self._path):
            self.clicked.emit()


class ImagePreviewDialog(QDialog):
    """Просмотр шаблона в полном размере (с прокруткой для больших картинок)."""

    def __init__(self, path, parent=None, on_edit=None):
        super().__init__(parent)
        self._path = path
        self._on_edit = on_edit
        self.setWindowTitle(f"Preview — {os.path.basename(path)}")
        lay = QVBoxLayout(self)

        info = QLabel(os.path.abspath(path))
        info.setStyleSheet("color:#aaa; font-size:11px;")
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.setWordWrap(True)
        lay.addWidget(info)

        meta = load_template_meta(path)
        if meta:
            c = meta.get("compare_rect", [])
            n_ex = len(meta.get("exclude_rects") or [])
            ck = meta.get("click_point", [])
            sb = meta.get("scroll_bar_rect")
            parts = [f"Compare: {c}", f"Excludes: {n_ex}", f"Wheel: {ck}"]
            if meta.get("input_rect"):
                parts.append(f"Input: {meta['input_rect']}")
            if sb:
                parts.append(f"Scroll bar: {sb}")
            meta_lbl = QLabel("  |  ".join(parts))
            meta_lbl.setStyleSheet("color:#8bc; font-size:11px;")
            lay.addWidget(meta_lbl)

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        pix = QPixmap(path)

        w, h = 640, 480
        if pix.isNull():
            self._img_label.setText("Cannot load image.")
        else:
            scr = QApplication.primaryScreen().availableGeometry()
            maxw, maxh = int(scr.width() * 0.85), int(scr.height() * 0.8)
            shown = pix
            if pix.width() > maxw or pix.height() > maxh:
                shown = pix.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_label.setPixmap(self._draw_overlays(shown, pix, meta))
            w = min(shown.width() + 40, maxw)
            h = min(shown.height() + 90, maxh)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._img_label)
        lay.addWidget(scroll)

        btns = QHBoxLayout()
        if on_edit and os.path.isfile(path):
            btn_edit = QPushButton("Edit regions…")
            btn_edit.clicked.connect(self._edit_regions)
            btns.addWidget(btn_edit)
        btns.addStretch()
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        btns.addWidget(btn)
        lay.addLayout(btns)

        self.resize(max(w, 360), max(h, 240))

    def _draw_overlays(self, shown, original, meta):
        if meta is None or shown.isNull():
            return shown
        out = shown.copy()
        sx = shown.width() / max(original.width(), 1)
        sy = shown.height() / max(original.height(), 1)
        p = QPainter(out)
        for r in meta.get("exclude_rects") or []:
            if len(r) == 4:
                x, y, w, h = r
                p.fillRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy),
                           QColor(255, 60, 60, 90))
        c = meta.get("compare_rect")
        if c and len(c) == 4:
            x, y, w, h = c
            p.setPen(QPen(QColor("#00e676"), 2))
            p.drawRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy))
        sb = meta.get("scroll_bar_rect")
        if sb and len(sb) == 4:
            x, y, w, h = sb
            p.fillRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy),
                       QColor(255, 152, 0, 70))
            p.setPen(QPen(QColor("#ff9800"), 2))
            p.drawRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy))
        ir = meta.get("input_rect")
        if ir and len(ir) == 4:
            x, y, w, h = ir
            p.fillRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy),
                       QColor(66, 165, 245, 70))
            p.setPen(QPen(QColor("#42a5f5"), 2))
            p.drawRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy))
        ck = meta.get("click_point")
        if ck and len(ck) == 2:
            cx, cy = int(ck[0] * sx), int(ck[1] * sy)
            p.setPen(QPen(QColor("#42a5f5"), 2))
            p.drawLine(cx - 8, cy, cx + 8, cy)
            p.drawLine(cx, cy - 8, cx, cy + 8)
        p.end()
        return out

    def _edit_regions(self):
        if self._on_edit and self._on_edit(self._path):
            meta = load_template_meta(self._path)
            pix = QPixmap(self._path)
            if not pix.isNull():
                scr = QApplication.primaryScreen().availableGeometry()
                maxw, maxh = int(scr.width() * 0.85), int(scr.height() * 0.8)
                shown = pix
                if pix.width() > maxw or pix.height() > maxh:
                    shown = pix.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._img_label.setPixmap(self._draw_overlays(shown, pix, meta))


# ============================================================================
# СПРАВКА ПО КОЛОНКАМ ТАБЛИЦЫ
# ============================================================================

class ColumnHelpDialog(QDialog):
    """Полное описание всех колонок таблицы шагов."""

    _LABELS = [
        "On", "Action", "Template / area", "…", "Preview",
        "Value", "Timeout", "Find win", "Stop",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Column guide — all columns explained")
        self.setMinimumSize(520, 420)
        lay = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        parts = []
        for col, title in enumerate(self._LABELS):
            body = COLUMN_HELP.get(col, "").strip()
            parts.append(f"<h3 style='color:#5c93d6; margin:12px 0 4px 0;'>{title}</h3>")
            parts.append(f"<p style='margin:0 0 8px 0; color:#ddd;'>{body.replace(chr(10), '<br>')}</p>")
        text.setHtml("".join(parts))
        lay.addWidget(text)
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignRight)


# ============================================================================
# НАСТРОЙКА УСЛОВНОГО ПЕРЕХОДА (ветка A / ветка B)
# ============================================================================

class BranchConfigDialog(QDialog):
    """Диалог выбора JSON-сценариев для веток A и B (условный «узел»)."""

    def __init__(self, action, current_value="", parent=None, start_dir=""):
        super().__init__(parent)
        self._action = action
        self._start_dir = start_dir or os.getcwd()
        titles = {
            "branch_image": "Branch on template (image found?)",
            "branch_text": "Branch on OCR text (word found?)",
            "branch_verify": "Branch on verify result (word found? + proof)",
        }
        self.setWindowTitle(titles.get(action, "Configure branch"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)

        help_text = {
            "branch_image": (
                "Checks whether the template in Template/area is visible on screen.\n"
                "• Way A — runs if the template IS found.\n"
                "• Way B — runs if the template is NOT found.\n"
                "Leave a side empty to continue the remaining steps in THIS scenario."
            ),
            "branch_text": (
                "Reads text in the OCR region (Template/area: x,y,w,h) and searches for a keyword.\n"
                "• Way A — runs if the word IS found.\n"
                "• Way B — runs if the word is NOT found."
            ),
            "branch_verify": (
                "Like OCR branch, but also saves a PASS/FAIL proof screenshot to results\\.\n"
                "• Way A — runs if the keyword IS found (PASS).\n"
                "• Way B — runs if NOT found (FAIL). Never stops the scenario on its own."
            ),
        }
        hint = QLabel(help_text.get(action, ""))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#aaa; margin-bottom:8px;")
        lay.addWidget(hint)

        keyword, path_a, path_b = parse_branch_value(action, current_value)

        self._keyword = QLineEdit(keyword)
        if action != "branch_image":
            lay.addWidget(QLabel("Keyword to search for:"))
            lay.addWidget(self._keyword)

        self._path_a = QLineEdit(path_a)
        self._path_b = QLineEdit(path_b)
        lay_a = QHBoxLayout()
        lay_a.addWidget(self._path_a, stretch=1)
        btn_a = QPushButton("Browse…")
        btn_a.clicked.connect(lambda: self._pick_json(self._path_a))
        lay_a.addWidget(btn_a)
        lay.addWidget(QLabel("Way A — if condition is TRUE (found / PASS):"))
        lay.addLayout(lay_a)

        lay_b = QHBoxLayout()
        lay_b.addWidget(self._path_b, stretch=1)
        btn_b = QPushButton("Browse…")
        btn_b.clicked.connect(lambda: self._pick_json(self._path_b))
        lay_b.addWidget(btn_b)
        lay.addWidget(QLabel("Way B — if condition is FALSE (not found / FAIL):"))
        lay.addLayout(lay_b)

        note = QLabel(
            "Tip: nested branches work — a branch JSON can contain another branch step.\n"
            "Paths are stored relative to the current scenario folder when possible."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888; font-size:11px; margin-top:6px;")
        lay.addWidget(note)

        btns = QHBoxLayout()
        btns.addStretch()
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    def _pick_json(self, edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select branch scenario (JSON)", self._start_dir, "JSON (*.json)"
        )
        if path:
            edit.setText(path_for_scenario_storage(path, self._start_dir))

    def result_value(self):
        kw = self._keyword.text().strip() if self._action != "branch_image" else ""
        return format_branch_value(
            self._action, kw,
            self._path_a.text().strip(),
            self._path_b.text().strip(),
        )


# ============================================================================
# ЗАГОЛОВОК ТАБЛИЦЫ С МАСТЕР-ЧЕКБОКСАМИ
# ============================================================================

class MasterCheckboxHeader(QHeaderView):
    """Чекбокс в заголовке колонки — включить/выключить все строки сразу."""

    masterToggled = Signal(int, bool)
    columnHovered = Signal(int)   # индекс колонки под курсором, -1 = нет

    def __init__(self, checkbox_cols, column_help=None, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._checkbox_cols = set(checkbox_cols)
        self._states = {COL_ON: True, COL_FIND: False, COL_STOP: True}
        self._column_help = column_help or {}
        self._hover_col = -1
        self.setMouseTracking(True)
        # подписи сверху по центру — чтобы master-чекбокс поместился снизу
        self.setDefaultAlignment(Qt.AlignHCenter | Qt.AlignTop)

    def setColumnHelp(self, column_help):
        self._column_help = column_help or {}

    def _global_pos(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    def mouseMoveEvent(self, event):
        idx = self.logicalIndexAt(event.pos())
        if idx != self._hover_col:
            self._hover_col = idx
            self.columnHovered.emit(idx)
        tip = self._column_help.get(idx, "") if idx >= 0 else ""
        if tip:
            QToolTip.showText(self._global_pos(event), tip, self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_col = -1
        self.columnHovered.emit(-1)
        QToolTip.hideText()
        super().leaveEvent(event)

    def setMasterState(self, col, checked):
        if col in self._checkbox_cols:
            self._states[col] = checked
            self.viewport().update()

    def _section_rect(self, logical_index):
        return QRect(
            self.sectionViewportPosition(logical_index), 0,
            self.sectionSize(logical_index), self.height(),
        )

    def _checkbox_rect(self, section_rect):
        # Чекбокс в нижней части секции, подпись колонки — сверху (как у обычных).
        box = 16
        return QRect(
            section_rect.x() + (section_rect.width() - box) // 2,
            section_rect.bottom() - box - 4,
            box, box,
        )

    def paintSection(self, painter, rect, logical_index):
        # Сначала обычная отрисовка Qt — у ВСЕХ колонок видна подпись заголовка.
        super().paintSection(painter, rect, logical_index)
        # Для колонок-переключателей добавляем master-чекбокс под подписью.
        if logical_index in self._checkbox_cols:
            painter.save()
            cb_opt = QStyleOptionButton()
            cb_opt.rect = self._checkbox_rect(rect)
            cb_opt.state = QStyle.State_Enabled
            cb_opt.state |= QStyle.State_On if self._states[logical_index] else QStyle.State_Off
            self.style().drawControl(QStyle.CE_CheckBox, cb_opt, painter)
            painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            for col in self._checkbox_cols:
                if self._checkbox_rect(self._section_rect(col)).contains(pos):
                    self._states[col] = not self._states[col]
                    self.masterToggled.emit(col, self._states[col])
                    self.viewport().update()
                    return
        super().mousePressEvent(event)


# ============================================================================
# ГЛАВНОЕ ОКНО
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoBuilder — automation builder")
        self.setMinimumSize(900, 560)
        # просторный старт (~три четверти экрана) — элементы читаемы даже не в фуллскрине
        scr = QApplication.primaryScreen().availableGeometry()
        win_w, win_h = int(scr.width() * 0.78), int(scr.height() * 0.82)
        self.resize(win_w, win_h)
        self.move(scr.x() + (scr.width() - win_w) // 2, scr.y() + (scr.height() - win_h) // 2)
        self.runner = None
        self._clipboard = []
        self._playlist_active = False
        self._playlist_index = -1
        self._blink_on = False
        self._scenario_path = ""       # путь текущего JSON (для относительных веток)
        self._pending_branch = None    # JSON, на который перейти после текущего прогона
        self._branch_depth = 0         # защита от бесконечных циклов ветвления

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Верхняя панель управления ---
        top = QHBoxLayout()
        self.btn_run   = QPushButton("▶ Run")
        self.btn_stop  = QPushButton("⏹ Stop")
        self.btn_add   = QPushButton("➕ Add")
        self.btn_add.setToolTip("Add a new step at the end of the list")
        self.btn_insert = QPushButton("➕ Insert")
        self.btn_insert.setToolTip("Insert a new step after the selected row")
        self.btn_copy  = QPushButton("📋 Copy")
        self.btn_copy.setToolTip("Copy selected step(s)")
        self.btn_paste = QPushButton("📋 Paste")
        self.btn_paste.setToolTip("Paste copied step(s) after the selected row")
        self.btn_del   = QPushButton("🗑 Delete")
        self.btn_up    = QPushButton("↑")
        self.btn_down  = QPushButton("↓")
        self.btn_snip  = QPushButton("📷 Capture")
        self.btn_snip.setToolTip("Capture a screen region for the selected step (Ctrl+Shift+S)")
        self.btn_regions = QPushButton("✏ Regions")
        self.btn_regions.setToolTip(
            "Edit compare / exclude / click or scroll-bar regions for the selected step"
        )
        self.btn_branch = QPushButton("↷ Branch setup")
        self.btn_branch.setToolTip(
            "Configure Way A / Way B JSON scenarios for the selected branch step"
        )
        self.btn_branch.setEnabled(False)
        self.btn_save  = QPushButton("💾 Save")
        self.btn_load  = QPushButton("📂 Load")
        self.btn_stop.setEnabled(False)

        # Ряд 1 — запуск и параметры прогона
        top.addWidget(self.btn_run)
        top.addWidget(self.btn_stop)
        top.addStretch()
        top.addWidget(QLabel("Start delay, s:"))
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0, 60)
        self.spin_delay.setValue(3.0)
        top.addWidget(self.spin_delay)
        top.addSpacing(20)
        top.addWidget(QLabel("Serial:"))
        self.edit_serial = QLineEdit("0001")
        self.edit_serial.setMaxLength(16)
        self.edit_serial.setFixedWidth(150)
        self.edit_serial.setToolTip(
            "Serial number (letters + digits, up to 16 chars). Use {serial} in "
            "folder/file names; the trailing number increments on each use and "
            "continues on the next run. E.g. 0001, SN0001, AB00000001."
        )
        top.addWidget(self.edit_serial)
        top.addSpacing(20)
        top.addWidget(self.btn_save)
        top.addWidget(self.btn_load)
        root.addLayout(top)

        # Ряд 2 — редактирование шагов
        tools = QHBoxLayout()
        tools.addWidget(self.btn_add)
        tools.addWidget(self.btn_insert)
        tools.addWidget(self.btn_copy)
        tools.addWidget(self.btn_paste)
        tools.addWidget(self.btn_del)
        tools.addSpacing(16)
        tools.addWidget(self.btn_up)
        tools.addWidget(self.btn_down)
        tools.addSpacing(16)
        tools.addWidget(self.btn_snip)
        tools.addWidget(self.btn_regions)
        tools.addWidget(self.btn_branch)
        tools.addStretch()
        root.addLayout(tools)

        # --- Левая часть: таблица сверху, лог снизу ---
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setHandleWidth(7)
        left_splitter.setChildrenCollapsible(False)

        # Таблица шагов
        table_box = QWidget()
        table_layout = QVBoxLayout(table_box)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        guide_hdr = QHBoxLayout()
        guide_hdr.addWidget(QLabel("Column guide:"))
        self.btn_col_help = QPushButton("Show all columns")
        self.btn_col_help.setToolTip("Open a window with full explanation of every column")
        self.btn_col_help.clicked.connect(self._show_all_column_help)
        guide_hdr.addWidget(self.btn_col_help)
        guide_hdr.addStretch()
        table_layout.addLayout(guide_hdr)

        self.column_guide = QLabel(COLUMN_GUIDE_DEFAULT)
        self.column_guide.setWordWrap(True)
        self.column_guide.setTextFormat(Qt.AutoText)
        self.column_guide.setStyleSheet(
            "color:#b8c0c8; padding:6px 8px; background:#1a1d20; "
            "border:1px solid #3a3f44; border-radius:4px;"
        )
        table_layout.addWidget(self.column_guide)

        self.table = QTableWidget(0, 9)
        self._header = MasterCheckboxHeader(
            [COL_ON, COL_FIND, COL_STOP], COLUMN_HELP, self.table
        )
        self.table.setHorizontalHeader(self._header)
        self._header.masterToggled.connect(self._master_toggle_column)
        self._header.columnHovered.connect(self._update_column_guide)
        self.table.setHorizontalHeaderLabels(
            ["On", "Action", "Template / area", "…", "Preview",
             "Value", "Timeout", "Find win", "Stop"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(COL_IMAGE, QHeaderView.Stretch)
        self.table.setColumnWidth(COL_ON, 40)
        self.table.setColumnWidth(COL_ACTION, 180)
        self.table.setColumnWidth(COL_BROWSE, 40)
        self.table.setColumnWidth(COL_PREVIEW, 84)
        self.table.setColumnWidth(COL_VALUE, 160)
        self.table.setColumnWidth(COL_TIMEOUT, 70)
        self.table.setColumnWidth(COL_FIND, 60)
        self.table.setColumnWidth(COL_STOP, 50)
        self._header.setFixedHeight(42)
        # строки повыше, чтобы миниатюры были видны
        self.table.verticalHeader().setDefaultSectionSize(48)

        for col, text in COLUMN_HELP.items():
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setToolTip(text)

        table_layout.addWidget(self.table)
        left_splitter.addWidget(table_box)

        # Лог
        log_box = QWidget()
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.addWidget(QLabel("Execution log:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        log_layout.addWidget(self.log_view)
        left_splitter.addWidget(log_box)

        left_splitter.setSizes([int(win_h * 0.62), int(win_h * 0.32)])

        # --- Правая часть: playlist + отдельный лог ---
        self.playlist_box = QWidget()
        self.playlist_box.setMinimumWidth(260)
        playlist_layout = QVBoxLayout(self.playlist_box)
        playlist_layout.setContentsMargins(6, 0, 0, 0)
        playlist_layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Program playlist (JSON):"))
        self.play_state = QLabel()
        self.play_state.setFixedSize(14, 14)
        self.play_state.setFrameShape(QFrame.StyledPanel)
        self.play_state.setToolTip("Idle/Stopped/Running")
        hdr.addWidget(self.play_state)
        hdr.addStretch()
        playlist_layout.addLayout(hdr)

        self.playlist_list = QListWidget()
        self.playlist_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.playlist_list.setToolTip("Order matters: programs run top → bottom")
        playlist_layout.addWidget(self.playlist_list, stretch=1)

        row1 = QHBoxLayout()
        self.btn_pl_add = QPushButton("➕ Add JSON")
        self.btn_pl_remove = QPushButton("➖ Remove")
        self.btn_pl_up = QPushButton("↑")
        self.btn_pl_down = QPushButton("↓")
        row1.addWidget(self.btn_pl_add)
        row1.addWidget(self.btn_pl_remove)
        row1.addWidget(self.btn_pl_up)
        row1.addWidget(self.btn_pl_down)
        playlist_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_pl_run = QPushButton("▶ Run list")
        self.btn_pl_stop = QPushButton("⏹ Stop list")
        self.btn_pl_stop.setEnabled(False)
        row2.addWidget(self.btn_pl_run)
        row2.addWidget(self.btn_pl_stop)
        playlist_layout.addLayout(row2)

        playlist_layout.addWidget(QLabel("Playlist log:"))
        self.playlist_log_view = QTextEdit()
        self.playlist_log_view.setReadOnly(True)
        self.playlist_log_view.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        playlist_layout.addWidget(self.playlist_log_view, stretch=1)

        # --- Общий сплиттер: слева сценарий, справа плейлист ---
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(7)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(left_splitter)
        self.main_splitter.addWidget(self.playlist_box)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 2)
        # пропорции от реальной ширины окна, чтобы плейлист не «схлопывался»
        self.main_splitter.setSizes([int(win_w * 0.66), int(win_w * 0.34)])
        root.addWidget(self.main_splitter)

        # --- Сигналы ---
        self.btn_add.clicked.connect(lambda: self.add_step())
        self.btn_insert.clicked.connect(self.insert_step)
        self.btn_copy.clicked.connect(self.copy_steps)
        self.btn_paste.clicked.connect(self.paste_steps)
        self.btn_del.clicked.connect(self.del_step)
        self.btn_up.clicked.connect(lambda: self.move_step(-1))
        self.btn_down.clicked.connect(lambda: self.move_step(1))
        self.btn_run.clicked.connect(self.run_scenario)
        self.btn_stop.clicked.connect(self.stop_scenario)
        self.btn_save.clicked.connect(self.save_scenario)
        self.btn_load.clicked.connect(self.load_scenario)
        self.btn_snip.clicked.connect(self.capture_region)
        self.btn_regions.clicked.connect(self.edit_template_regions)
        self.btn_branch.clicked.connect(self.edit_branch_paths)
        self.table.itemSelectionChanged.connect(self._update_branch_btn)
        self.btn_pl_add.clicked.connect(self.playlist_add_files)
        self.btn_pl_remove.clicked.connect(self.playlist_remove_selected)
        self.btn_pl_up.clicked.connect(lambda: self.playlist_move(-1))
        self.btn_pl_down.clicked.connect(lambda: self.playlist_move(1))
        self.btn_pl_run.clicked.connect(self.playlist_run)
        self.btn_pl_stop.clicked.connect(self.playlist_stop)

        # горячая клавиша для захвата области
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.capture_region)
        QShortcut(QKeySequence("Ctrl+C"), self.table, activated=self.copy_steps)
        QShortcut(QKeySequence("Ctrl+V"), self.table, activated=self.paste_steps)
        QShortcut(QKeySequence("Insert"), self.table, activated=self.insert_step)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(450)
        self._blink_timer.timeout.connect(self._blink_status)
        self._set_play_state("idle")
        self._build_menu()

        if not AUTOMATION_OK:
            self._log(f"⚠ Automation libraries not found: {_IMPORT_ERR}", "err")
            self._log("The GUI works, but running scenarios is unavailable until installed.", "info")
        elif not TESSERACT_OK:
            self._log(f"⚠ {TESSERACT_HINT}", "err")
            self._log("All actions work except OCR check / Verify text until Tesseract is installed.", "info")

        # стартовый пример-шаг
        self.add_step()

    # ---------- работа с таблицей ----------

    def _selected_rows(self):
        return sorted({idx.row() for idx in self.table.selectedIndexes()})

    def _master_toggle_column(self, col, checked):
        for r in range(self.table.rowCount()):
            cb = self._checkbox_at(r, col)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)
        self._header.setMasterState(col, checked)

    def _sync_master_from_rows(self):
        for col in (COL_ON, COL_FIND, COL_STOP):
            if self.table.rowCount() == 0:
                continue
            vals = [self._checkbox_at(r, col).isChecked()
                    for r in range(self.table.rowCount())
                    if self._checkbox_at(r, col)]
            if vals:
                self._header.setMasterState(col, all(vals))

    def add_step(self, data=None, insert_at=None):
        if insert_at is None:
            insert_at = self.table.rowCount()
        else:
            insert_at = max(0, min(int(insert_at), self.table.rowCount()))
        self.table.insertRow(insert_at)
        self._populate_row(insert_at, data)
        self._sync_master_from_rows()

    def insert_step(self):
        rows = self._selected_rows()
        insert_at = rows[-1] + 1 if rows else self.table.rowCount()
        self.add_step(insert_at=insert_at)
        self.table.clearSelection()
        self.table.setCurrentCell(insert_at, COL_ACTION)
        self._log(f"Inserted new step at row {insert_at + 1}.", "ok")

    def copy_steps(self):
        rows = self._selected_rows()
        if not rows:
            self._log("Select one or more steps to copy (Ctrl+click / Shift+click).", "err")
            return
        self._clipboard = [self._row_data(r) for r in rows]
        self._log(f"Copied {len(rows)} step(s).", "ok")

    def paste_steps(self):
        if not self._clipboard:
            self._log("Nothing copied yet — select steps and press Copy first.", "err")
            return
        rows = self._selected_rows()
        insert_at = rows[-1] + 1 if rows else self.table.rowCount()
        for i, data in enumerate(self._clipboard):
            self.add_step(dict(data), insert_at=insert_at + i)
        self.table.clearSelection()
        self.table.setCurrentCell(insert_at, COL_ACTION)
        self._log(f"Pasted {len(self._clipboard)} step(s) at row {insert_at + 1}.", "ok")

    def _populate_row(self, r, data=None):
        chk_on = QCheckBox()
        chk_on.setChecked(True if not data else data.get("enabled", True))
        chk_on.stateChanged.connect(self._sync_master_from_rows)
        self._center(chk_on, r, COL_ON)

        combo = QComboBox()
        for key, name in ACTIONS.items():
            combo.addItem(name, key)
        if data:
            idx = list(ACTIONS).index(data.get("action", "click_image"))
            combo.setCurrentIndex(idx)
        self.table.setCellWidget(r, COL_ACTION, combo)

        img = QLineEdit(data.get("image", "") if data else "")
        img.setPlaceholderText("path to png (or x,y,w,h for OCR)")
        self.table.setCellWidget(r, COL_IMAGE, img)

        browse = QPushButton("…")
        browse.clicked.connect(lambda _=False, edit=img: self._browse(edit))
        self.table.setCellWidget(r, COL_BROWSE, browse)

        thumb = ThumbLabel()
        thumb.clicked.connect(lambda t=thumb: self._open_preview(t._path))
        img.textChanged.connect(lambda text, t=thumb: t.set_image(text))
        thumb.set_image(img.text())
        self._center(thumb, r, COL_PREVIEW)

        val = QLineEdit(data.get("value", "") if data else "")
        self.table.setCellWidget(r, COL_VALUE, val)

        combo.currentIndexChanged.connect(
            lambda _=0, c=combo, v=val, im=img: self._update_hint(c, v, im)
        )
        combo.currentIndexChanged.connect(lambda _=0: self._update_branch_btn())

        to = QSpinBox()
        to.setRange(1, 600)
        to.setValue(data.get("timeout", 10) if data else 10)
        self.table.setCellWidget(r, COL_TIMEOUT, to)

        chk_find = QCheckBox()
        chk_find.setChecked(data.get("find_window", False) if data else False)
        chk_find.setToolTip("Search for the window/element (cycle windows if not visible)")
        chk_find.stateChanged.connect(self._sync_master_from_rows)
        self._center(chk_find, r, COL_FIND)

        chk_stop = QCheckBox()
        chk_stop.setChecked(data.get("stop_on_error", True) if data else True)
        chk_stop.stateChanged.connect(self._sync_master_from_rows)
        self._center(chk_stop, r, COL_STOP)

        self._update_hint(combo, val, img)

    def _center(self, widget, row, col):
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(wrap)
        lay.addWidget(widget)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, col, wrap)

    def _checkbox_at(self, row, col):
        wrap = self.table.cellWidget(row, col)
        return wrap.findChild(QCheckBox)

    def _update_hint(self, combo, val, img=None):
        if not combo or not val:
            return
        action = combo.currentData()
        val.setPlaceholderText(VALUE_HINT.get(action, ""))
        if img is not None:
            if action == "scroll":
                img.setPlaceholderText("template png — capture large area, then mark scroll bar")
            elif action == "fill_field":
                img.setPlaceholderText("capture label+field — then set compare / input zone")
            elif action in BRANCH_ACTIONS:
                img.setPlaceholderText(
                    "template png (image branch) or x,y,w,h OCR region (text branch)"
                )
            else:
                img.setPlaceholderText("path to png (or x,y,w,h for OCR)")

    def _browse(self, edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select template", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All (*)"
        )
        if path:
            edit.setText(path)

    def _update_column_guide(self, col):
        """Обновляет видимую панель подсказки при наведении на заголовок колонки."""
        if col >= 0 and col in COLUMN_HELP:
            titles = ColumnHelpDialog._LABELS
            title = titles[col] if col < len(titles) else f"Column {col}"
            self.column_guide.setText(f"<b>{title}</b> — {COLUMN_HELP[col].replace(chr(10), ' ')}")
        else:
            self.column_guide.setText(COLUMN_GUIDE_DEFAULT)

    def _show_all_column_help(self):
        ColumnHelpDialog(self).exec()

    def _update_branch_btn(self):
        row = self.table.currentRow()
        enabled = False
        if row >= 0:
            combo = self.table.cellWidget(row, COL_ACTION)
            if combo and combo.currentData() in BRANCH_ACTIONS:
                enabled = True
        self.btn_branch.setEnabled(enabled)

    def edit_branch_paths(self):
        """Открыть диалог настройки веток A/B для выбранного условного шага."""
        row = self.table.currentRow()
        if row < 0:
            self._log("Select a branch step first (IF … → JSON A else JSON B).", "err")
            return
        combo = self.table.cellWidget(row, COL_ACTION)
        action = combo.currentData()
        if action not in BRANCH_ACTIONS:
            self._log(
                "Change Action to a branch type first:\n"
                "  • IF template found → JSON A else JSON B\n"
                "  • IF word found (OCR) → JSON A else JSON B\n"
                "  • IF word found (+ proof) → JSON A else JSON B",
                "err",
            )
            return
        val_field = self.table.cellWidget(row, COL_VALUE)
        base = os.path.dirname(self._scenario_path) if self._scenario_path else os.getcwd()
        dlg = BranchConfigDialog(action, val_field.text(), self, start_dir=base)
        if dlg.exec() == QDialog.Accepted:
            val_field.setText(dlg.result_value())
            self._log(f"Branch paths set for step {row + 1}.", "ok")

    def _open_preview(self, path):
        """Показ шаблона в полном размере по клику на миниатюре."""
        if not path or not os.path.isfile(path):
            self._log("No image to preview for this step.", "skip")
            return
        dlg = ImagePreviewDialog(path, self, on_edit=self._open_template_editor)
        dlg.exec()

    def _open_template_editor(self, path, purpose=None):
        """Открыть редактор compare/exclude/click или scroll bar. True если сохранено."""
        if not path or not os.path.isfile(path):
            return False
        if purpose is None:
            row = self.table.currentRow()
            if row >= 0:
                action = self.table.cellWidget(row, COL_ACTION).currentData()
                purpose = _editor_purpose_for_action(action)
            else:
                purpose = "template"
        dlg = TemplateEditorDialog(path, self, purpose=purpose)
        if dlg.exec() == QDialog.Accepted:
            dlg.save_meta()
            labels = {"scroll": "Scroll regions", "field": "Input field regions", "template": "Template regions"}
            self._log(f"{labels.get(purpose, 'Regions')} saved: {os.path.basename(path)}", "ok")
            return True
        return False

    def edit_template_regions(self):
        row = self.table.currentRow()
        if row < 0:
            self._log("Select a step first.", "err")
            return
        action = self.table.cellWidget(row, COL_ACTION).currentData()
        if action not in REGION_EDIT_ACTIONS:
            self._log("Regions apply to template or scroll steps only.", "err")
            return
        path = self.table.cellWidget(row, COL_IMAGE).text().strip()
        if not path or not os.path.isfile(path):
            self._log("Capture or browse a template image for this step first.", "err")
            return
        purpose = _editor_purpose_for_action(action)
        self._open_template_editor(path, purpose=purpose)
        img_field = self.table.cellWidget(row, COL_IMAGE)
        if img_field:
            img_field.setText(img_field.text())

    # ---------- захват области экрана ----------

    @staticmethod
    def _pil_to_pixmap(pil_img):
        rgb = pil_img.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def capture_region(self):
        """Свернуть окно, снять экран и показать оверлей для выделения области."""
        if not AUTOMATION_OK:
            self._log("Capture unavailable: automation libraries not installed.", "err")
            return
        row = self.table.currentRow()
        if row < 0:
            row = self.table.rowCount() - 1
        if row < 0:
            self._log("Add a step first, then capture a region for it.", "err")
            return
        self._capture_row = row

        self.hide()
        QApplication.processEvents()
        time.sleep(0.3)   # дать окну скрыться до снимка
        try:
            img, left, top = grab_all()           # весь виртуальный экран (все мониторы)
        except Exception as e:
            self.show()
            self._log(f"Screenshot failed: {e}", "err")
            return
        self._capture_grab = (img, left, top)
        pix = self._pil_to_pixmap(img)
        self._overlay = SnipOverlay(pix, self._on_region_selected)

    def _on_region_selected(self, rect, geo):
        self.show()
        self.raise_()
        self.activateWindow()
        if rect is None:
            self._log("Capture cancelled.", "skip")
            return

        row = getattr(self, "_capture_row", self.table.currentRow())
        if row < 0 or row >= self.table.rowCount():
            self._log("Target row no longer exists.", "err")
            return

        img, left, top = self._capture_grab
        sw, sh = img.size
        gw, gh = max(geo.width(), 1), max(geo.height(), 1)
        sx, sy = sw / gw, sh / gh   # логические координаты Qt -> физические пиксели снимка

        # локальная область внутри снимка (пиксели)
        lx, ly = int(rect.x() * sx), int(rect.y() * sy)
        lw, lh = int(rect.width() * sx), int(rect.height() * sy)
        # абсолютные координаты виртуального экрана (учёт смещения мониторов)
        ax, ay = left + lx, top + ly

        action = self.table.cellWidget(row, COL_ACTION).currentData()
        img_field = self.table.cellWidget(row, COL_IMAGE)
        val_field = self.table.cellWidget(row, COL_VALUE)

        if action in ("click_xy", "double_click_xy"):
            # центр области в абсолютных экранных координатах (для клика)
            cx, cy = ax + lw // 2, ay + lh // 2
            val_field.setText(f"{cx}, {cy}")
            self._log(f"Captured point ({cx}, {cy}) → step {row + 1}", "ok")

        elif action == "fill_field":
            os.makedirs("templates", exist_ok=True)
            path = os.path.join("templates", f"tpl_{int(time.time())}.png")
            img.crop((lx, ly, lx + lw, ly + lh)).save(path)
            img_field.setText(path)
            self._log(f"Captured input field → {path} (step {row + 1})", "ok")
            save_template_meta(path, default_template_meta(lw, lh))
            self.table.setCurrentCell(row, 0)
            if self._open_template_editor(path, purpose="field"):
                img_field.setText(path)
            else:
                self._log("Mark compare / value-ignore / input zone with ✏ Regions.", "info")

        elif action == "scroll":
            os.makedirs("templates", exist_ok=True)
            path = os.path.join("templates", f"tpl_{int(time.time())}.png")
            img.crop((lx, ly, lx + lw, ly + lh)).save(path)
            img_field.setText(path)
            self._log(f"Captured scroll template → {path} (step {row + 1})", "ok")
            save_template_meta(path, default_template_meta(lw, lh))
            self.table.setCurrentCell(row, 0)
            if self._open_template_editor(path, purpose="scroll"):
                img_field.setText(path)
            else:
                self._log("Mark compare / exclude / scroll bar with ✏ Regions.", "info")

        elif action in ("ocr_check", "verify_text", "branch_text", "branch_verify"):
            img_field.setText(f"{ax}, {ay}, {lw}, {lh}")
            self._log(f"Captured OCR region {ax},{ay},{lw},{lh} → step {row + 1}", "ok")

        else:
            os.makedirs("templates", exist_ok=True)
            path = os.path.join("templates", f"tpl_{int(time.time())}.png")
            img.crop((lx, ly, lx + lw, ly + lh)).save(path)
            img_field.setText(path)
            self._log(f"Captured template → {path} (step {row + 1})", "ok")
            if action in TEMPLATE_ACTIONS:
                save_template_meta(path, default_template_meta(lw, lh))
                self.table.setCurrentCell(row, 0)
                if self._open_template_editor(path):
                    img_field.setText(path)
                else:
                    self._log("Regions: using full image + center click (edit later with ✏ Regions).", "info")

    def del_step(self):
        rows = self._selected_rows()
        if not rows:
            r = self.table.currentRow()
            if r >= 0:
                rows = [r]
        for r in reversed(rows):
            self.table.removeRow(r)
        if rows:
            self._log(f"Deleted {len(rows)} step(s).", "ok")
        self._sync_master_from_rows()

    def move_step(self, direction):
        r = self.table.currentRow()
        if r < 0:
            return
        new_r = r + direction
        if new_r < 0 or new_r >= self.table.rowCount():
            return
        data_r = self._row_data(r)
        data_new = self._row_data(new_r)
        self._set_row(r, data_new)
        self._set_row(new_r, data_r)
        self.table.setCurrentCell(new_r, 0)

    # ---------- сбор данных со строк ----------

    def _row_data(self, row):
        combo = self.table.cellWidget(row, COL_ACTION)
        return {
            "enabled": self._checkbox_at(row, COL_ON).isChecked(),
            "action": combo.currentData(),
            "image": self.table.cellWidget(row, COL_IMAGE).text(),
            "value": self.table.cellWidget(row, COL_VALUE).text(),
            "timeout": self.table.cellWidget(row, COL_TIMEOUT).value(),
            "find_window": self._checkbox_at(row, COL_FIND).isChecked(),
            "stop_on_error": self._checkbox_at(row, COL_STOP).isChecked(),
        }

    def _set_row(self, row, data):
        self._checkbox_at(row, COL_ON).setChecked(data["enabled"])
        combo = self.table.cellWidget(row, COL_ACTION)
        combo.setCurrentIndex(list(ACTIONS).index(data["action"]))
        self.table.cellWidget(row, COL_IMAGE).setText(data["image"])
        self.table.cellWidget(row, COL_VALUE).setText(data["value"])
        self.table.cellWidget(row, COL_TIMEOUT).setValue(data["timeout"])
        self._checkbox_at(row, COL_FIND).setChecked(data.get("find_window", False))
        self._checkbox_at(row, COL_STOP).setChecked(data["stop_on_error"])

    def _all_steps(self):
        return [self._row_data(r) for r in range(self.table.rowCount())]

    # ---------- playlist ----------

    def _build_menu(self):
        bar = self.menuBar()

        m_file = bar.addMenu("&File")
        a_open = QAction("Open scenario...", self)
        a_open.setShortcut(QKeySequence("Ctrl+O"))
        a_open.triggered.connect(self.load_scenario)
        m_file.addAction(a_open)

        a_save = QAction("Save scenario...", self)
        a_save.setShortcut(QKeySequence("Ctrl+S"))
        a_save.triggered.connect(self.save_scenario)
        m_file.addAction(a_save)
        m_file.addSeparator()

        a_add_json = QAction("Add JSON to playlist...", self)
        a_add_json.triggered.connect(self.playlist_add_files)
        m_file.addAction(a_add_json)

        a_run_list = QAction("Run playlist", self)
        a_run_list.triggered.connect(self.playlist_run)
        m_file.addAction(a_run_list)
        m_file.addSeparator()

        a_exit = QAction("Exit", self)
        a_exit.setShortcut(QKeySequence("Alt+F4"))
        a_exit.triggered.connect(self.close)
        m_file.addAction(a_exit)

        m_view = bar.addMenu("&View")
        self.act_view_playlist = QAction("Show playlist panel", self)
        self.act_view_playlist.setCheckable(True)
        self.act_view_playlist.setChecked(True)
        self.act_view_playlist.triggered.connect(self.toggle_playlist_panel)
        m_view.addAction(self.act_view_playlist)

        m_help = bar.addMenu("&Help")
        a_readme = QAction("Open README", self)
        a_readme.triggered.connect(self.open_readme)
        m_help.addAction(a_readme)

    def toggle_playlist_panel(self, checked):
        if checked:
            self.playlist_box.show()
            total = max(self.main_splitter.width(), 900)
            self.main_splitter.setSizes([int(total * 0.66), int(total * 0.34)])
        else:
            self.playlist_box.hide()

    def open_readme(self):
        path = os.path.join(os.path.dirname(__file__), "README.md")
        if not os.path.isfile(path):
            self._log("README.md not found.", "err")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                import webbrowser
                webbrowser.open(path)
            self._log("Opened README.md", "ok")
        except Exception as e:
            self._log(f"Failed to open README.md: {e}", "err")

    def _set_play_state(self, state):
        # state: idle|running|stopped
        if state == "running":
            self._blink_on = True
            self._blink_timer.start()
            self.play_state.setToolTip("Playlist running")
            self.play_state.setStyleSheet("background:#43a047; border-radius:7px; border:1px solid #1b5e20;")
        elif state == "stopped":
            self._blink_timer.stop()
            self.play_state.setToolTip("Playlist stopped")
            self.play_state.setStyleSheet("background:#e53935; border-radius:7px; border:1px solid #8e0000;")
        else:
            self._blink_timer.stop()
            self.play_state.setToolTip("Playlist idle")
            self.play_state.setStyleSheet("background:#9e9e9e; border-radius:7px; border:1px solid #555;")

    def _blink_status(self):
        if not self._playlist_active:
            return
        self._blink_on = not self._blink_on
        color = "#43a047" if self._blink_on else "#2e7d32"
        self.play_state.setStyleSheet(
            f"background:{color}; border-radius:7px; border:1px solid #1b5e20;"
        )

    def _playlist_log(self, text, level="info"):
        colors = {"info": "#cccccc", "ok": "#4caf50", "err": "#f44336", "skip": "#888888"}
        ts = time.strftime("%H:%M:%S")
        color = colors.get(level, "#cccccc")
        self.playlist_log_view.append(
            f'<span style="color:#666">{ts}</span> <span style="color:{color}">{text}</span>'
        )

    def playlist_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add programs to playlist", "", "JSON (*.json)")
        if not files:
            return
        for p in files:
            item = QListWidgetItem(os.path.basename(p))
            item.setToolTip(p)
            item.setData(Qt.UserRole, p)
            self.playlist_list.addItem(item)
        self._playlist_log(f"Added {len(files)} program(s).", "ok")

    def playlist_remove_selected(self):
        rows = sorted({i.row() for i in self.playlist_list.selectedIndexes()}, reverse=True)
        for r in rows:
            self.playlist_list.takeItem(r)
        if rows:
            self._playlist_log(f"Removed {len(rows)} program(s).", "ok")

    def playlist_move(self, direction):
        row = self.playlist_list.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.playlist_list.count():
            return
        item = self.playlist_list.takeItem(row)
        self.playlist_list.insertItem(new_row, item)
        self.playlist_list.setCurrentRow(new_row)

    def _load_scenario_file(self, path, for_playlist=False):
        if not path or not os.path.isfile(path):
            msg = f"Scenario file not found: {path}"
            self._playlist_log(msg, "err") if for_playlist else self._log(msg, "err")
            return False
        try:
            with open(path, encoding="utf-8") as f:
                steps = json.load(f)
        except Exception as e:
            msg = f"Failed to load scenario {path}: {e}"
            self._playlist_log(msg, "err") if for_playlist else self._log(msg, "err")
            return False
        self.table.setRowCount(0)
        for st in steps:
            self.add_step(st)
        self._scenario_path = os.path.abspath(path)
        if for_playlist:
            self._playlist_log(f"Loaded {len(steps)} step(s): {os.path.basename(path)}", "ok")
        else:
            self._log(f"Loaded steps: {len(steps)} from {path}", "ok")
        return True

    def playlist_run(self):
        if self.runner:
            self._playlist_log("Runner is already active.", "err")
            return
        if self.playlist_list.count() == 0:
            self._playlist_log("Playlist is empty. Add JSON programs first.", "err")
            return
        self._playlist_active = True
        self._playlist_index = 0
        self._branch_depth = 0
        self.playlist_log_view.clear()
        self._playlist_log(f"Starting playlist with {self.playlist_list.count()} program(s).", "info")
        self.btn_pl_run.setEnabled(False)
        self.btn_pl_stop.setEnabled(True)
        self._set_play_state("running")
        self._run_playlist_item()

    def _run_playlist_item(self):
        if not self._playlist_active:
            return
        self._branch_depth = 0
        if self._playlist_index >= self.playlist_list.count():
            self._playlist_log("Playlist completed successfully.", "ok")
            self._playlist_active = False
            self.btn_pl_run.setEnabled(True)
            self.btn_pl_stop.setEnabled(False)
            self._set_play_state("stopped")
            return
        item = self.playlist_list.item(self._playlist_index)
        path = item.data(Qt.UserRole)
        name = os.path.basename(path) if path else f"item #{self._playlist_index + 1}"
        if not self._load_scenario_file(path, for_playlist=True):
            self._playlist_log(f"Skipping invalid scenario: {name}", "err")
            self._playlist_index += 1
            self._run_playlist_item()
            return
        self._playlist_log(f"Running [{self._playlist_index + 1}/{self.playlist_list.count()}]: {name}", "info")
        self.run_scenario()

    def playlist_stop(self):
        self._playlist_active = False
        self._playlist_index = -1
        self._pending_branch = None
        self.btn_pl_run.setEnabled(True)
        self.btn_pl_stop.setEnabled(False)
        self._set_play_state("stopped")
        if self.runner:
            self.runner.stop()
        self._playlist_log("Playlist stop requested.", "err")

    # ---------- запуск / стоп ----------

    def run_scenario(self, from_branch=False):
        steps = self._all_steps()
        if not steps:
            self._log("No steps to execute.", "err")
            return
        if not from_branch:
            self._branch_depth = 0
        self.log_view.clear()
        self._log(f"Running scenario: {len(steps)} step(s)", "info")
        scenario_dir = os.path.dirname(self._scenario_path) if self._scenario_path else os.getcwd()
        self.runner = Runner(
            steps, self.spin_delay.value(),
            own_title=self.windowTitle(),
            serial_start=self.edit_serial.text().strip() or "0001",
            scenario_dir=scenario_dir,
        )
        self.runner.log.connect(self._log)
        self.runner.serial_update.connect(self.edit_serial.setText)
        self.runner.branch_request.connect(self._on_branch_request)
        self.runner.finished_all.connect(self._on_finished)
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.runner.start()

    def stop_scenario(self):
        if self._playlist_active:
            self.playlist_stop()
            return
        self._pending_branch = None
        if self.runner:
            self.runner.stop()

    def _on_branch_request(self, path):
        """Runner попросил условный переход: запомним путь до конца прогона."""
        self._pending_branch = path

    def _on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # условный переход: грузим выбранный JSON и продолжаем цепочку
        pending, self._pending_branch = self._pending_branch, None
        if pending:
            self._branch_depth += 1
            if self._branch_depth > MAX_BRANCH_DEPTH:
                self._log(
                    f"Branch chain too deep ({MAX_BRANCH_DEPTH}) — possible loop. Stopping.",
                    "err",
                )
                if self._playlist_active:
                    self._playlist_active = False
                    self._playlist_index = -1
                    self.btn_pl_run.setEnabled(True)
                    self.btn_pl_stop.setEnabled(False)
                    self._set_play_state("stopped")
                return
            name = os.path.basename(pending)
            if self._playlist_active:
                self._playlist_log(f"↷ Branch → {name}", "info")
            if self._load_scenario_file(pending, for_playlist=self._playlist_active):
                self._log(f"↷ Branch: running {name}", "info")
                self.run_scenario(from_branch=True)
                return          # плейлист продолжится после конца всей цепочки
            self._log(f"Branch target failed to load: {pending}", "err")

        if self._playlist_active:
            self._playlist_log("Program finished.", "ok")
            self._playlist_index += 1
            self._run_playlist_item()

    # ---------- лог ----------

    def _log(self, text, level="info"):
        colors = {"info": "#cccccc", "ok": "#4caf50", "err": "#f44336", "skip": "#888888"}
        ts = time.strftime("%H:%M:%S")
        color = colors.get(level, "#cccccc")
        self.log_view.append(f'<span style="color:#666">{ts}</span> '
                             f'<span style="color:{color}">{text}</span>')

    # ---------- сохранение / загрузка ----------

    def save_scenario(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save scenario", "scenario.json", "JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._all_steps(), f, ensure_ascii=False, indent=2)
        self._scenario_path = os.path.abspath(path)
        self._log(f"Scenario saved: {path}", "ok")

    def load_scenario(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load scenario", "", "JSON (*.json)")
        if not path:
            return
        self._load_scenario_file(path, for_playlist=False)


# ============================================================================
# ТЕМА ОФОРМЛЕНИЯ (единый тёмный стиль — крупнее шрифт, читаемые кнопки)
# ============================================================================

APP_STYLE = """
* { font-size: 13px; }
QWidget { background-color: #232629; color: #e6e6e6; }
QMainWindow, QDialog { background-color: #1e2124; }

QLabel { background: transparent; }

QPushButton {
    background-color: #3a3f44;
    border: 1px solid #4a5057;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 24px;
    color: #f0f0f0;
}
QPushButton:hover { background-color: #464c53; border-color: #5c93d6; }
QPushButton:pressed { background-color: #2f343a; }
QPushButton:disabled { background-color: #2b2e31; color: #6a6f74; border-color: #34383c; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1b1e20;
    border: 1px solid #4a5057;
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 24px;
    selection-background-color: #5c93d6;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #5c93d6;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #232629;
    border: 1px solid #4a5057;
    selection-background-color: #5c93d6;
    outline: none;
}

QTableWidget {
    background-color: #1b1e20;
    alternate-background-color: #212528;
    gridline-color: #34383c;
    border: 1px solid #3a3f44;
}
QTableWidget::item { padding: 2px; }
QTableWidget::item:selected { background-color: #35506f; }
QHeaderView::section {
    background-color: #2f343a;
    color: #dfe3e6;
    padding: 6px 4px;
    border: none;
    border-right: 1px solid #3a3f44;
    border-bottom: 1px solid #3a3f44;
    font-weight: bold;
}
QTableCornerButton::section { background-color: #2f343a; border: none; }

QListWidget {
    background-color: #1b1e20;
    border: 1px solid #3a3f44;
    border-radius: 4px;
}
QListWidget::item { padding: 7px 5px; border-bottom: 1px solid #26292c; }
QListWidget::item:selected { background-color: #35506f; color: #ffffff; }
QListWidget::item:hover { background-color: #2a2e31; }

QTextEdit {
    background-color: #15181a;
    border: 1px solid #3a3f44;
    border-radius: 4px;
}

QSplitter::handle { background-color: #3a3f44; }
QSplitter::handle:horizontal { width: 7px; }
QSplitter::handle:vertical { height: 7px; }
QSplitter::handle:hover { background-color: #5c93d6; }

QScrollBar:vertical { background: #1b1e20; width: 13px; margin: 0; }
QScrollBar::handle:vertical { background: #4a5057; border-radius: 5px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: #5c93d6; }
QScrollBar:horizontal { background: #1b1e20; height: 13px; margin: 0; }
QScrollBar::handle:horizontal { background: #4a5057; border-radius: 5px; min-width: 26px; }
QScrollBar::handle:horizontal:hover { background: #5c93d6; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QToolTip {
    background-color: #2f343a; color: #f0f0f0;
    border: 1px solid #5c93d6; padding: 4px;
}
QMenuBar { background-color: #232629; }
QMenuBar::item { padding: 5px 10px; }
QMenuBar::item:selected { background-color: #35506f; }
QMenu { background-color: #232629; border: 1px solid #4a5057; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background-color: #35506f; }
QCheckBox::indicator { width: 17px; height: 17px; }
"""


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())