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
import re
import csv
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
    QStyle, QStyleOptionButton, QStyleOptionHeader, QToolTip, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap, QPainter, QPen, QShortcut, QKeySequence, QAction


# ============================================================================
# ВЕРСИЯ ПРИЛОЖЕНИЯ + ИСТОРИЯ ИЗМЕНЕНИЙ
# ----------------------------------------------------------------------------
# При добавлении новых возможностей: подними APP_VERSION и добавь запись в
# CHANGELOG (сверху — самая новая версия). Приложение покажет «What's new»
# один раз, когда версия сменится (запоминается в app_state.json рядом с .py).
# ============================================================================

APP_NAME = "MACS Visual Automation"
APP_VERSION = "1.5"

CHANGELOG = [
    (
        "1.5",
        "2026-08-07",
        [
            "Removed the two raw-coordinate actions ('Click on coordinates (x,y)' and "
            "'Double-click on coordinates (x,y)'): there was no good way to find those "
            "numbers, and such a step broke as soon as the window moved. Old scenarios "
            "still load — those steps become 'Click on template' / 'Double-click on "
            "template' and the log lists which step numbers now need a 📷 Capture.",
            "New Help → 📖 Full guide (F1): a deep, searchable manual in TWO languages "
            "(English / Русский) — every action explained with what it really does "
            "(search scales and match threshold, when Timeout retries and when it does "
            "not, what each proof file contains), what goes into Template/area and Value, "
            "and what to watch out for. Also covers the steps table, template capture and "
            "the regions editor, the playlist and jump chain, tokens/serial numbers and "
            "troubleshooting. F1 opens straight at the section of the action selected in "
            "the table, and the language you pick is remembered.",
            "The playlist panel now follows the run: when a 'Move to another "
            "playlist/scenario' (goto) or a branch step hands the run over, the right "
            "panel switches to a '↷ Jump chain' view listing every scenario the run "
            "moves through — ▶ marks the one running now, ✓ the ones already done.",
            "Your own list is never lost: it stays behind the '▣ My list' chip above "
            "the panel (with its program count), even if it was never saved. One click "
            "flips between your list and the jump chain; '▶ Run list' and all editing "
            "always apply to your own list.",
            "The list also highlights progress while a playlist runs (▶ / ✓), and the "
            "bar above the steps table says whether you're looking at a playlist "
            "position or a jump-chain position.",
            "Fixed: after a single '▶ Run', the engine was never released, so "
            "'▶ Run list' kept answering 'Runner is already active' until restart.",
        ],
    ),
    (
        "1.3",
        "2026-08-07",
        [
            "Collapsible logs to free up space: the Execution log (left) and Playlist "
            "log (right) now start minimized, each with a small ▸ Show / ▾ Hide button "
            "next to its header — expand only when you need to look at it.",
            "New View menu items 'Show execution log' and 'Show playlist log' let you "
            "toggle both logs from the top menu too, alongside the existing 'Show "
            "playlist panel' option.",
        ],
    ),
    (
        "1.2",
        "2026-08-07",
        [
            "New action: 'Move to another playlist/scenario' (goto_playlist) — an "
            "unconditional jump (no A/B, no condition): put a playlist or scenario JSON "
            "path in Template/area and the run switches to it as soon as the step "
            "executes. Great for handing off to another playlist once you've reached a "
            "result, without needing a branch condition.",
            "Playlist preview switcher: click any program in the right-hand playlist "
            "panel to load its steps into the left-hand table for viewing/editing. A "
            "new bar above the table shows the current file and its position in the "
            "playlist, with ◀ Prev / Next ▶ buttons to step through every program one "
            "by one. The bar also tracks progress automatically while a playlist runs.",
        ],
    ),
    (
        "1.1",
        "2026-08-06",
        [
            "New action: 'IF gimbal calib CSV OK (Az/El) → A else B (+ proof)' (branch_calib) — "
            "reads a gimbal calibration CSV (Azimuth, Elevation, Gain/Power columns), finds the "
            "Az/El boresight offsets from the peak-gain point on each raw cut, and checks a "
            "tolerance condition like 'abs(Az)<=0.3 AND abs(El)<=0.3'.",
            "Way A = calibration OK, Way B = out of tolerance — point Way B at a recalibration "
            "scenario (adjust the gimbal tolerance, calibrate again) to build a retry loop.",
            "Saves a PASS/FAIL .txt report to results\\ with the computed offsets; if a "
            "'<csv name>_Pattern.png' sits next to the CSV, it's copied there too as proof.",
        ],
    ),
    (
        "1.0",
        "2026-08-06",
        [
            "First versioned release — baseline for change tracking.",
            "New action: 'IF value condition met → A else B (+ proof)' (branch_value) — "
            "reads numbers via OCR and checks conditions like 'Az ML<=0.1 AND El ML<=0.1' "
            "(supports <= >= < > == !=, AND/OR, and abs()/|...| for tolerance). Saves a "
            "PASS/FAIL proof screenshot automatically.",
            "Branch targets (Way A / Way B) can now point to a PLAYLIST file — the whole "
            "playlist is driven through in order instead of loading a single scenario.",
            "Playlist panel: new '💾 Save list…' / '📂 Load list…' buttons to export/import "
            "the playlist as a reusable file (perfect as a branch target).",
            "Anti-loop branch-depth guard raised to 200 to support recalibration loops.",
            "About / What's new dialog added under the Help menu, with version tracking.",
        ],
    ),
]


def changelog_html(entries=None):
    """HTML-текст истории изменений для окна «What's new / About»."""
    entries = entries if entries is not None else CHANGELOG
    parts = []
    for ver, date, items in entries:
        parts.append(f"<h3 style='margin:8px 0 2px'>Version {ver} "
                     f"<span style='color:#888;font-weight:normal'>({date})</span></h3>")
        parts.append("<ul style='margin:0 0 8px 0'>")
        for it in items:
            parts.append(f"<li style='margin-bottom:4px'>{it}</li>")
        parts.append("</ul>")
    return "".join(parts)

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
    "branch_value":        "IF value condition met → A else B (+ proof, A/B may be playlist)",
    "branch_calib":        "IF gimbal calib CSV OK (Az/El) → A else B (+ proof)",
    "goto_playlist":       "Move to another playlist/scenario",
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
    "branch_value":        "Az ML<=0.1 AND El ML<=0.1 | wayA | wayB  (use ↷ Branch setup)",
    "branch_calib":        "abs(Az)<=0.3 AND abs(El)<=0.3 | wayA | wayB  (use ↷ Branch setup)",
    "goto_playlist":       "(not needed — put the path in Template/area)",
    "screenshot":          "name, e.g. unit_{serial}\\log.png",
    "select_target":       "path to select, e.g. results\\unit_{serial}",
    "create_folder":       "path, e.g. results\\unit_{serial}",
    "rename_folder":       "new name/path (selected first), e.g. unit_{serial}_done",
    "delete_folder":       "path, or empty = use selected",
    "pause":               "seconds, e.g. 3",
}

# Действия, убранные из списка (клик по «сырым» координатам x,y: их неоткуда
# взять, и шаг ломался при любом сдвиге окна). Старые сценарии не роняем: шаг
# превращается в ближайший по смыслу клик по шаблону, а при загрузке пишем
# предупреждение — для такого шага нужно снять шаблон.
RETIRED_ACTIONS = {
    "click_xy":        ("click_image", "Click on coordinates (x,y)"),
    "double_click_xy": ("double_click_image", "Double-click on coordinates (x,y)"),
}


def migrate_action(action):
    """Ключ действия из файла → действующий ключ (учитывая убранные действия)."""
    if action in RETIRED_ACTIONS:
        return RETIRED_ACTIONS[action][0]
    return action

# Колонки таблицы
COL_ON, COL_ACTION, COL_IMAGE, COL_BROWSE, COL_PREVIEW, COL_VALUE, COL_TIMEOUT, COL_FIND, COL_STOP = range(9)

BRANCH_ACTIONS = frozenset(
    {"branch_image", "branch_text", "branch_verify", "branch_value", "branch_calib"}
)
MAX_BRANCH_DEPTH = 200

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
        "• IF value condition met — branch on OCR-read numbers (+ proof).\n"
        "• IF gimbal calib CSV OK — branch on Az/El offsets from a calibration CSV.\n"
        "Use ↷ Branch setup to pick Way A / Way B JSON files.\n"
        "• Move to another playlist/scenario — unconditional jump (no A/B, no "
        "condition): put the target JSON path in Template/area. The right panel "
        "switches to '↷ Jump chain' and follows where the run goes."
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


# ---------------------------------------------------------------------------
# Числовые условия для branch_value (например: "Az ML<=0.1 AND El ML<=0.1")
# ---------------------------------------------------------------------------

# порядок важен: длинные операторы (<=, >=, ==, !=) до одиночных (<, >, =)
_COND_OPS = ("<=", ">=", "==", "!=", "<", ">", "=")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _num(text):
    """'0,09' / '0.09' → float, иначе None."""
    if text is None:
        return None
    try:
        return float(str(text).replace(",", "."))
    except ValueError:
        return None


def extract_labeled_number(text, label):
    """Находит первое число, идущее ПОСЛЕ метки label в тексте OCR.

    Пример: label='Az ML', text='Az ML: [0.0, 35.99] ...' → 0.0
    Метка ищется без учёта регистра, пробелы внутри метки — «гибкие».
    """
    if not text or not label:
        return None
    # метку разбиваем по пробелам и разрешаем произвольные разделители между словами
    words = [re.escape(w) for w in str(label).split()]
    if not words:
        return None
    label_re = re.compile(r"\s*".join(words), re.IGNORECASE)
    m = label_re.search(text)
    if not m:
        return None
    tail = text[m.end():]
    num_m = _NUMBER_RE.search(tail)
    if not num_m:
        return None
    return _num(num_m.group(0))


def _parse_condition_clause(clause):
    """'abs(Az ML) <= 0.1' → (label, op, target, use_abs) или None."""
    clause = clause.strip()
    if not clause:
        return None
    op = None
    op_pos = -1
    for candidate in _COND_OPS:
        pos = clause.find(candidate)
        if pos != -1:
            op = candidate
            op_pos = pos
            break
    if op is None:
        return None
    label = clause[:op_pos].strip()
    target = _num(clause[op_pos + len(op):])
    if target is None:
        return None
    use_abs = False
    low = label.lower()
    if (low.startswith("abs(") and label.endswith(")")):
        use_abs = True
        label = label[4:-1].strip()
    elif label.startswith("|") and label.endswith("|") and len(label) > 1:
        use_abs = True
        label = label[1:-1].strip()
    if op == "=":
        op = "=="
    return (label, op, target, use_abs)


def _eval_clause(value, op, target):
    if value is None:
        return False
    if op == "==":
        return abs(value - target) < 1e-9
    if op == "!=":
        return abs(value - target) >= 1e-9
    if op == "<":
        return value < target
    if op == "<=":
        return value <= target
    if op == ">":
        return value > target
    if op == ">=":
        return value >= target
    return False


def evaluate_value_condition(expr, text):
    """Проверяет условие вида 'Az ML<=0.1 AND El ML<=0.1' по OCR-тексту.

    Поддержка: операторы <=, >=, <, >, ==, != (и '=' как ==), abs(...) / |...|,
    объединение через AND / OR (регистр не важен). OR имеет более низкий приоритет.
    Возвращает (result: bool, detail: str) — detail показывает разобранные значения.
    """
    if not expr or not str(expr).strip():
        return False, "empty condition"
    text = text or ""
    or_groups = re.split(r"\bOR\b", expr, flags=re.IGNORECASE)
    details = []
    group_results = []
    for group in or_groups:
        clauses = re.split(r"\bAND\b", group, flags=re.IGNORECASE)
        clause_results = []
        for raw in clauses:
            parsed = _parse_condition_clause(raw)
            if parsed is None:
                if raw.strip():
                    details.append(f"{raw.strip()}=?(bad)")
                    clause_results.append(False)
                continue
            label, op, target, use_abs = parsed
            value = extract_labeled_number(text, label)
            cmp_value = abs(value) if (use_abs and value is not None) else value
            ok = _eval_clause(cmp_value, op, target)
            shown = "n/a" if value is None else (f"|{value:g}|" if use_abs else f"{value:g}")
            details.append(f"{label}{op}{target:g}→{shown}[{'ok' if ok else 'no'}]")
            clause_results.append(ok)
        if clause_results:
            group_results.append(all(clause_results))
    result = any(group_results) if group_results else False
    return result, "; ".join(details)


# ---------------------------------------------------------------------------
# Проверка калибровки гимбала по CSV (branch_calib)
# CSV — результат сканирования гимбала: колонки Azimuth/Elevation/Gain(или Power).
# Az-сечение = строки с El, ближайшим к 0 (ищем Az пика усиления в них).
# El-сечение = строки с Az, ближайшим к 0 (ищем El пика усиления в них).
# ---------------------------------------------------------------------------

def read_calib_csv(path):
    """Читает CSV калибровки гимбала → список {"az":, "el":, "gain":}.

    Колонки ищутся по имени (без учёта регистра/лишних слов): Azimuth, Elevation,
    Antenna Gain (или, если её нет, Power Received).
    """
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"calibration CSV not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        def find_col(*keys):
            for name in fieldnames:
                low = name.strip().lower()
                if any(k in low for k in keys):
                    return name
            return None

        az_col = find_col("azimuth", "az")
        el_col = find_col("elevation", "el")
        gain_col = find_col("antenna gain", "gain") or find_col("power received", "power", "dbm")
        if not az_col or not el_col or not gain_col:
            raise ValueError(
                "calibration CSV must have Azimuth, Elevation and Gain/Power columns "
                f"(found columns: {fieldnames})"
            )
        rows = []
        for row in reader:
            az = _num(row.get(az_col))
            el = _num(row.get(el_col))
            gain = _num(row.get(gain_col))
            if az is None or el is None or gain is None:
                continue
            rows.append({"az": az, "el": el, "gain": gain})
    if not rows:
        raise ValueError(f"calibration CSV has no valid data rows: {path}")
    return rows


def compute_calib_offsets(path):
    """Вычисляет боресайт-ошибки Az/El (метод пика усиления по raw-сечениям).

    Возвращает (az_offset, el_offset, info); info — для отчёта/лога.
    """
    rows = read_calib_csv(path)
    el0 = min(abs(r["el"]) for r in rows)
    az_cut = [r for r in rows if abs(r["el"]) <= el0 + 1e-9]
    az0 = min(abs(r["az"]) for r in rows)
    el_cut = [r for r in rows if abs(r["az"]) <= az0 + 1e-9]
    if not az_cut or not el_cut:
        raise ValueError("could not isolate Az/El cuts in calibration CSV")
    az_peak = max(az_cut, key=lambda r: r["gain"])
    el_peak = max(el_cut, key=lambda r: r["gain"])
    info = {
        "az_offset": az_peak["az"], "az_gain": az_peak["gain"], "az_points": len(az_cut),
        "el_offset": el_peak["el"], "el_gain": el_peak["gain"], "el_points": len(el_cut),
        "points": len(rows),
    }
    return az_peak["az"], el_peak["el"], info


# ---------------------------------------------------------------------------
# Плейлисты в файле: массив путей к JSON-сценариям (для ветвления в плейлист)
# ---------------------------------------------------------------------------

def is_playlist_data(data):
    """True, если JSON-данные — это плейлист (список путей), а не сценарий (список шагов)."""
    if isinstance(data, dict):
        return isinstance(data.get("playlist"), list)
    if isinstance(data, list):
        if not data:
            return False
        # сценарий = список словарей-шагов (в каждом есть 'action')
        if all(isinstance(x, str) for x in data):
            return True
        if all(isinstance(x, dict) for x in data):
            # плейлист может быть списком {'path': ...} без 'action'
            if all(("path" in x and "action" not in x) for x in data):
                return True
        return False
    return False


def playlist_paths_from_data(data, base_dir):
    """Разворачивает плейлист-данные в список абсолютных путей к сценариям."""
    items = []
    if isinstance(data, dict):
        items = data.get("playlist", []) or []
    elif isinstance(data, list):
        items = data
    paths = []
    for it in items:
        if isinstance(it, str):
            raw = it
        elif isinstance(it, dict):
            raw = it.get("path", "")
        else:
            raw = ""
        raw = str(raw).strip()
        if not raw:
            continue
        paths.append(resolve_scenario_path(raw, base_dir))
    return paths


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


def make_unique_playlist_labels(paths):
    """Подписи для пунктов плейлиста, различимые даже при одинаковых именах.

    os.path.basename() (или даже basename + один родительский каталог) не
    отличает файлы с одинаковым именем, если совпадает и имя родительской
    папки на любую глубину вложенности (например, вложенная копия проекта).
    Здесь подпись растёт вглубь пути (папка/папка/файл.json, ...) ровно до
    тех пор, пока не станет уникальной среди РЕАЛЬНО разных файлов; если два
    пункта физически указывают на один и тот же файл, им закономерно
    оставляется одинаковая подпись.
    """
    norm = [os.path.normpath(os.path.abspath(p)) if p else "" for p in paths]
    parts = [p.split(os.sep) if p else [] for p in norm]
    max_depth = max((len(p) for p in parts), default=1) or 1
    depth = 1
    labels = [os.sep.join(p[-depth:]) if p else "" for p in parts]
    while depth < max_depth:
        groups = {}
        for i, lbl in enumerate(labels):
            groups.setdefault(lbl, []).append(i)
        colliding = [idxs for idxs in groups.values()
                     if len(idxs) > 1 and len({norm[i] for i in idxs}) > 1]
        if not colliding:
            break
        depth += 1
        for idxs in colliding:
            for i in idxs:
                labels[i] = os.sep.join(parts[i][-depth:])
    return labels


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

        elif a in ("branch_image", "branch_text", "branch_verify", "branch_value", "branch_calib"):
            # Условный переход («узел»): проверяем условие и выбираем JSON-сценарий.
            # Пустой путь на выбранной стороне = продолжаем текущий сценарий.
            # Выбранная ветка может указывать на плейлист-файл (список сценариев).
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
            elif a == "branch_value":
                # keyword хранит условие, напр. "Az ML<=0.1 AND El ML<=0.1"
                if not keyword:
                    raise RuntimeError(
                        "branch condition is empty — e.g. 'Az ML<=0.1 AND El ML<=0.1' "
                        "(use ↷ Branch setup button)")
                if not path_a and not path_b:
                    raise RuntimeError(
                        "Configure branch paths: condition | Way A | Way B "
                        "(use ↷ Branch setup button)")
                found, detail, _ = self._eval_value_condition(st["image"], keyword, to, find)
                cond = f"condition {'TRUE' if found else 'FALSE'} [{detail}]"
                # доказательство (PASS/FAIL) как в branch_verify
                os.makedirs("results", exist_ok=True)
                status = "PASS" if found else "FAIL"
                img, left, top = grab_all()
                region = self._region_tuple(st["image"])
                if region:
                    x, y, w, hh = region
                    img = img.crop((x - left, y - top, x - left + w, y - top + hh))
                safe = "".join(c if c.isalnum() else "_" for c in (keyword[:40] or "check"))
                proof = os.path.join("results", f"{status}_{safe}_{int(time.time())}.png")
                img.save(proof)
                self.log.emit(f"[{i}]   proof screenshot → {proof}", "info")
            elif a == "branch_calib":
                # keyword хранит условие, напр. "abs(Az)<=0.3 AND abs(El)<=0.3"
                if not keyword:
                    raise RuntimeError(
                        "branch condition is empty — e.g. 'abs(Az)<=0.3 AND abs(El)<=0.3' "
                        "(use ↷ Branch setup button)")
                if not path_a and not path_b:
                    raise RuntimeError(
                        "Configure branch paths: condition | Way A | Way B "
                        "(use ↷ Branch setup button)")
                csv_path = self._expand(st["image"].strip())
                if not csv_path:
                    raise RuntimeError(
                        "no calibration CSV given — put its path in Template/area "
                        "(e.g. calib.csv)")
                az_offset, el_offset, cinfo = compute_calib_offsets(csv_path)
                text = f"Az: {az_offset:.3f}  El: {el_offset:.3f}"
                found, detail = evaluate_value_condition(keyword, text)
                cond = f"Az={az_offset:.2f} El={el_offset:.2f} → condition {'TRUE' if found else 'FALSE'} [{detail}]"
                # отчёт (PASS/FAIL) + копия картинки паттерна, если она лежит рядом с CSV
                os.makedirs("results", exist_ok=True)
                status = "PASS" if found else "FAIL"
                safe = "".join(c if c.isalnum() else "_" for c in (keyword[:40] or "calib"))
                stamp = int(time.time())
                report = os.path.join("results", f"{status}_{safe}_{stamp}.txt")
                with open(report, "w", encoding="utf-8") as f:
                    f.write(
                        "Gimbal calibration check\n"
                        f"csv: {os.path.abspath(csv_path)}\n"
                        f"Az offset: {az_offset:.3f} deg "
                        f"(peak gain {cinfo['az_gain']:.3f} over {cinfo['az_points']} pts)\n"
                        f"El offset: {el_offset:.3f} deg "
                        f"(peak gain {cinfo['el_gain']:.3f} over {cinfo['el_points']} pts)\n"
                        f"condition: {keyword}\n"
                        f"result: {status}\n"
                        f"detail: {detail}\n"
                    )
                self.log.emit(f"[{i}]   report → {report}", "info")
                base, _ext = os.path.splitext(csv_path)
                for suffix in ("_Pattern.png", "_pattern.png", "_Pattern.PNG"):
                    pattern_png = base + suffix
                    if os.path.isfile(pattern_png):
                        proof_png = os.path.join("results", f"{status}_{safe}_{stamp}.png")
                        shutil.copy(pattern_png, proof_png)
                        self.log.emit(f"[{i}]   pattern proof → {proof_png}", "info")
                        break
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

        elif a == "goto_playlist":
            # Безусловный переход (без ветвления): всегда грузим указанный
            # сценарий или плейлист-файл, как только этот шаг выполнится.
            target_raw = st["image"].strip()
            if not target_raw:
                raise RuntimeError(
                    "no playlist/scenario path given — put it in Template/area")
            target = self._resolve_branch_path(target_raw)
            if not target or not os.path.isfile(target):
                raise FileNotFoundError(f"playlist/scenario not found: {target}")
            self._branch_target = target
            self.log.emit(f"[{i}] ✓ {label} → {os.path.basename(target)}", "ok")

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

    def _eval_value_condition(self, region_str, expr, timeout, find_window):
        """OCR-область + проверка числового условия (branch_value).

        Возвращает (result: bool, detail: str, last_text: str).
        Повторяет чтение до таймаута, пока условие не станет истинным.
        """
        self._last_text = ""

        def detect():
            text = self._ocr(region_str)
            self._last_text = text
            ok, _ = evaluate_value_condition(expr, text)
            return True if ok else None

        res = self._search(detect, timeout if find_window else timeout, find_window)
        ok, detail = evaluate_value_condition(expr, self._last_text)
        return (res is True) or ok, detail, self._last_text

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
# ПОЛНОЕ РУКОВОДСТВО (Help → Full guide) — два языка: en + ru
# ----------------------------------------------------------------------------
# ACTION_DOCS — подробное описание КАЖДОГО действия: что делает (включая детали
# движка: масштабы поиска, порог совпадения, повторы до таймаута), что писать в
# Template/area и в Value, и что важно знать. HELP_TOPICS — остальные разделы
# (интерфейс, шаблоны, плейлист, токены, диагностика). При добавлении действия
# в ACTIONS добавь его и сюда — диалог собирается из этих данных.
# ============================================================================

HELP_LANGS = ("en", "ru")

ACTION_DOCS = {
    "click_image": {
        "en": {
            "what": "Finds the picture from Template/area anywhere on your monitors and "
                    "left-clicks it. The search covers all screens at once (one virtual "
                    "desktop), compares both grayscale pixels and Canny edges, and tries "
                    "11 zoom levels from ×0.5 to ×2.0 — so a step keeps working after a "
                    "DPI change, another resolution or a theme change. A match counts "
                    "from correlation 0.80.",
            "target": "PNG template — capture it with 📷 Capture (or … to pick a file).",
            "value": "Not used.",
            "note": "The click lands on the template's click point (its centre by default; "
                    "✏ Regions can move it — an Input zone or Scroll bar region wins over "
                    "it). The search repeats every 0.4 s until Timeout runs out, then the "
                    "step fails and the log prints the best score it saw: ~0.7 means the "
                    "template is nearly right (re-capture it), ~0.2 means it isn't on "
                    "screen at all.",
        },
        "ru": {
            "title": "Клик по шаблону",
            "what": "Ищет картинку из Template/area на всех мониторах и делает левый клик "
                    "по ней. Поиск идёт сразу по всему виртуальному экрану, сравнивает и "
                    "оттенки серого, и контуры (Canny), и перебирает 11 масштабов от ×0.5 "
                    "до ×2.0 — поэтому шаг продолжает работать после смены DPI, "
                    "разрешения или темы. Совпадением считается корреляция от 0.80.",
            "target": "PNG-шаблон — снимите его кнопкой 📷 Capture (или выберите файл "
                      "через …).",
            "value": "Не нужно.",
            "note": "Клик приходится в точку клика шаблона (по умолчанию центр; сдвигается "
                    "в ✏ Regions, причём Input zone и Scroll bar имеют приоритет). Поиск "
                    "повторяется каждые 0.4 с до истечения Timeout, после чего шаг падает, "
                    "а в лог пишется лучшее совпадение: ~0.7 — шаблон почти подходит "
                    "(переснимите), ~0.2 — его вообще нет на экране.",
        },
    },
    "double_click_image": {
        "en": {
            "what": "Exactly the same search as Click on template, but performs a "
                    "double-click — for opening files, folders and list items.",
            "target": "PNG template.",
            "value": "Not used.",
        },
        "ru": {
            "title": "Двойной клик по шаблону",
            "what": "Тот же поиск, что и у «Click on template», но выполняется двойной "
                    "клик — для открытия файлов, папок и элементов списка.",
            "target": "PNG-шаблон.",
            "value": "Не нужно.",
        },
    },
    "wait_image": {
        "en": {
            "what": "The same search as Click on template, but nothing is clicked: the step "
                    "simply waits until the picture shows up, and fails if it doesn't "
                    "appear within Timeout.",
            "target": "PNG template.",
            "value": "Not used.",
            "note": "This is your synchronisation point — put it before steps that must not "
                    "start too early (wait for a dialog, a progress bar to disappear, a "
                    "'Done' badge). Much more reliable than guessing with Pause.",
        },
        "ru": {
            "title": "Ожидание шаблона",
            "what": "Тот же поиск, что и у клика по шаблону, но без клика: шаг просто ждёт "
                    "появления картинки и падает, если она не появилась за Timeout.",
            "target": "PNG-шаблон.",
            "value": "Не нужно.",
            "note": "Это точка синхронизации — ставьте перед шагами, которые нельзя "
                    "начинать раньше времени (дождаться диалога, исчезновения прогресса, "
                    "надписи «Done»). Надёжнее, чем угадывать длину Pause.",
        },
    },
    "scroll": {
        "en": {
            "what": "Moves the mouse onto the target, clicks once to give that panel focus, "
                    "and then sends real mouse-wheel notches (on Windows via "
                    "MOUSEEVENTF_WHEEL, 120 units each, 40 ms apart). That is why it "
                    "scrolls panels which ignore synthetic scroll events.",
            "target": "PNG template of the scrollable panel, or plain x,y coordinates.",
            "value": "down, 5 / up, 3 / a bare number (positive = down, negative = up). "
                     "Empty means down, 3.",
            "note": "Capture a large area that contains the scrollbar and mark the "
                    "Scroll bar region in ✏ Regions — the wheel is then delivered exactly "
                    "over the bar. If the panel's content changes between runs, mark the "
                    "changing parts as Exclude so matching ignores them.",
        },
        "ru": {
            "title": "Прокрутка панели (колесо мыши)",
            "what": "Наводит мышь на цель, делает один клик (чтобы панель получила фокус) "
                    "и отправляет настоящие «щелчки» колеса (в Windows через "
                    "MOUSEEVENTF_WHEEL, по 120 единиц с паузой 40 мс). Именно поэтому "
                    "прокручиваются даже панели, игнорирующие синтетический скролл.",
            "target": "PNG-шаблон прокручиваемой панели или координаты x,y.",
            "value": "down, 5 / up, 3 / просто число (положительное — вниз, отрицательное — "
                     "вверх). Пусто = down, 3.",
            "note": "Снимите область побольше, вместе с полосой прокрутки, и отметьте в "
                    "✏ Regions регион Scroll bar — колесо будет крутиться точно над "
                    "полосой. Если содержимое панели меняется между прогонами, отметьте "
                    "меняющиеся части как Exclude.",
        },
    },
    "key": {
        "en": {
            "what": "Presses one key or a key combination in the window that currently has "
                    "focus.",
            "target": "Not used.",
            "value": "enter, backspace, ctrl+a, ctrl+shift+s, alt+f4 … Aliases are "
                     "understood: control/ctl → ctrl, del → delete, bksp/bs → backspace, "
                     "return → enter, esc → escape, pgup/pgdn, win.",
        },
        "ru": {
            "title": "Нажатие клавиши / сочетания",
            "what": "Нажимает одну клавишу или сочетание в окне, у которого сейчас фокус.",
            "target": "Не нужно.",
            "value": "enter, backspace, ctrl+a, ctrl+shift+s, alt+f4 … Понимаются "
                     "псевдонимы: control/ctl → ctrl, del → delete, bksp/bs → backspace, "
                     "return → enter, esc → escape, pgup/pgdn, win.",
        },
    },
    "type_text": {
        "en": {
            "what": "Types the text on the keyboard into whatever has focus (about 0.01 s "
                    "per character). Tokens are expanded first, so a path can be typed "
                    "straight into a Save dialog.",
            "target": "Not used.",
            "value": "The text itself, e.g. results\\unit_{serial}\\report.png. Tokens: "
                     "{serial} {date} {time} {ts}.",
            "note": "It does NOT clear the field first — for that use Fill input field.",
        },
        "ru": {
            "title": "Ввод текста",
            "what": "Печатает текст с клавиатуры туда, где сейчас фокус (примерно 0.01 с на "
                    "символ). Токены подставляются заранее, поэтому путь можно вводить "
                    "прямо в диалог сохранения.",
            "target": "Не нужно.",
            "value": "Сам текст, например results\\unit_{serial}\\report.png. Токены: "
                     "{serial} {date} {time} {ts}.",
            "note": "Поле предварительно НЕ очищается — для этого есть «Fill input field».",
        },
    },
    "fill_field": {
        "en": {
            "what": "One step instead of four: click the input field, clear it, type the new "
                    "value and (optionally) confirm with a key.",
            "target": "PNG template of the label + field (or x,y). In ✏ Regions put Compare "
                      "(green) on the stable label and the Input zone (blue) on the box to "
                      "click — the click goes to the middle of the blue zone.",
            "value": "[method:]text[|confirm]. Methods: clear (default — Ctrl+A, Backspace, "
                     "then type), replace (Ctrl+A and type over the selection), paste (via "
                     "the clipboard: Ctrl+A, Ctrl+V — best for long or non-Latin text; your "
                     "clipboard is restored afterwards). confirm is any key spec. Examples: "
                     "847 · paste:847|enter · replace:{serial}|tab.",
        },
        "ru": {
            "title": "Заполнение поля ввода (очистить и напечатать)",
            "what": "Один шаг вместо четырёх: клик по полю ввода, очистка, ввод нового "
                    "значения и, если нужно, подтверждение клавишей.",
            "target": "PNG-шаблон подписи вместе с полем (или x,y). В ✏ Regions отметьте "
                      "Compare (зелёный) по неизменной подписи и Input zone (синий) по "
                      "самому полю — клик придётся в центр синей зоны.",
            "value": "[метод:]текст[|подтверждение]. Методы: clear (по умолчанию — Ctrl+A, "
                     "Backspace, затем ввод), replace (Ctrl+A и печать поверх выделения), "
                     "paste (через буфер обмена: Ctrl+A, Ctrl+V — лучший вариант для "
                     "длинного текста и не-латиницы; буфер потом восстанавливается). "
                     "Подтверждение — любая клавиша. Примеры: 847 · paste:847|enter · "
                     "replace:{serial}|tab.",
        },
    },
    "ui_delete": {
        "en": {
            "what": "Presses the Delete key, which removes whatever is currently selected "
                    "inside the OTHER program's interface. Put a Click on template step "
                    "before it to select the row/file first.",
            "target": "Not used.",
            "value": "Empty, or enter / confirm / yes / y / ok — then the step also waits "
                     "0.6 s and presses Enter to accept the confirmation dialog.",
            "note": "This never touches your disk by itself. To delete a folder on disk use "
                    "Delete folder on disk (by path).",
        },
        "ru": {
            "title": "Удаление элемента на экране (клавиша Delete)",
            "what": "Нажимает Delete — удаляется то, что выделено в интерфейсе ДРУГОЙ "
                    "программы. Перед этим шагом поставьте клик по шаблону, чтобы выделить "
                    "нужную строку или файл.",
            "target": "Не нужно.",
            "value": "Пусто или enter / confirm / yes / y / ok — тогда шаг ещё подождёт "
                     "0.6 с и нажмёт Enter, подтверждая диалог.",
            "note": "Сам по себе диск не трогает. Чтобы удалить папку на диске, есть "
                    "«Delete folder on disk (by path)».",
        },
    },
    "ocr_check": {
        "en": {
            "what": "Reads the text inside the region with the Tesseract OCR engine and "
                    "fails the step when the word is not there. Before OCR the region is "
                    "upscaled ×2.5, converted to gray and Otsu-thresholded — that is what "
                    "makes small UI labels readable. The comparison is a case-insensitive "
                    "substring match.",
            "target": "Screen region as x,y,w,h — 📷 Capture fills it in. Empty means the "
                      "whole virtual screen (slow and noisy).",
            "value": "The word to find, e.g. pass.",
            "note": "Important: with Find win OFF the region is read exactly ONCE — Timeout "
                    "is not used for retries here. Turn Find win ON to keep re-reading "
                    "until the timeout, or put a Wait for template step in front. Needs "
                    "the Tesseract engine installed.",
        },
        "ru": {
            "title": "OCR-проверка (поиск слова)",
            "what": "Читает текст в области движком Tesseract и роняет шаг, если слова "
                    "там нет. Перед распознаванием область увеличивается в 2.5 раза, "
                    "переводится в серый и бинаризуется по Оцу — именно поэтому читаются "
                    "мелкие подписи интерфейса. Сравнение — по подстроке, регистр не важен.",
            "target": "Область экрана в виде x,y,w,h — заполняется кнопкой 📷 Capture. "
                      "Пусто = весь виртуальный экран (медленно и много мусора).",
            "value": "Искомое слово, например pass.",
            "note": "Важно: при выключенном Find win область читается РОВНО ОДИН раз — "
                    "Timeout здесь на повторы не влияет. Включите Find win, чтобы читать "
                    "до таймаута, либо поставьте перед этим шагом «Wait for template». "
                    "Нужен установленный Tesseract.",
        },
    },
    "verify_text": {
        "en": {
            "what": "The same OCR check plus evidence: a PNG of the region is always saved "
                    "to results\\ as PASS_<word>_<timestamp>.png or FAIL_…, and the step "
                    "fails when the word is missing.",
            "target": "Region x,y,w,h (empty = whole screen).",
            "value": "The keyword you expect, e.g. pass.",
            "note": "This is the step that turns a scenario into a test report — the proof "
                    "file is written on both outcomes, so a FAIL is documented too.",
        },
        "ru": {
            "title": "Проверка текста с сохранением доказательства (pass/fail)",
            "what": "Та же OCR-проверка плюс доказательство: PNG области всегда "
                    "сохраняется в results\\ под именем PASS_<слово>_<время>.png или "
                    "FAIL_…, а сам шаг падает, если слова нет.",
            "target": "Область x,y,w,h (пусто = весь экран).",
            "value": "Ожидаемое слово, например pass.",
            "note": "Именно этот шаг превращает сценарий в отчёт о тесте: файл-"
                    "доказательство пишется при любом исходе, то есть FAIL тоже "
                    "задокументирован.",
        },
    },
    "screenshot": {
        "en": {
            "what": "Saves a picture of the region (or of the whole virtual screen when "
                    "Template/area is empty). Missing folders are created automatically.",
            "target": "Region x,y,w,h, or empty for everything.",
            "value": "File name. Without a folder it goes to results\\; tokens are expanded, "
                     "so unit_{serial}\\log.png creates a folder per unit.",
        },
        "ru": {
            "title": "Скриншот области",
            "what": "Сохраняет картинку области (или всего виртуального экрана, если "
                    "Template/area пусто). Недостающие папки создаются автоматически.",
            "target": "Область x,y,w,h или пусто — тогда весь экран.",
            "value": "Имя файла. Без папки файл ляжет в results\\; токены "
                     "подставляются, поэтому unit_{serial}\\log.png создаёт папку на "
                     "каждое изделие.",
        },
    },
    "branch_image": {
        "en": {
            "what": "Decision node on a picture: if the template IS on screen the run "
                    "continues with Way A, otherwise with Way B. Once the decision is made "
                    "the remaining steps of THIS scenario are skipped and the chosen JSON "
                    "is loaded and run.",
            "target": "PNG template to look for.",
            "value": "wayA.json | wayB.json — set it with ↷ Branch setup. An empty side "
                     "means 'no jump, just continue this scenario'. Relative paths are "
                     "resolved from the folder of the scenario that contains the step, and "
                     "a side may point at a whole playlist file, which is then driven "
                     "through program by program.",
        },
        "ru": {
            "title": "ЕСЛИ шаблон найден → JSON A иначе JSON B",
            "what": "Узел решения по картинке: если шаблон ЕСТЬ на экране, прогон "
                    "продолжается путём A, если нет — путём B. После решения оставшиеся "
                    "шаги ЭТОГО сценария пропускаются, а выбранный JSON загружается и "
                    "запускается.",
            "target": "PNG-шаблон, который ищем.",
            "value": "wayA.json | wayB.json — удобнее задать кнопкой ↷ Branch setup. "
                     "Пустая сторона означает «никуда не переходить, продолжить этот "
                     "сценарий». Относительные пути считаются от папки сценария, а сторона "
                     "может указывать на целый файл-плейлист — тогда он проезжается "
                     "программа за программой.",
        },
    },
    "branch_text": {
        "en": {
            "what": "The same decision, but on text: the region is read with OCR and the "
                    "keyword decides between Way A (found) and Way B (not found).",
            "target": "Region x,y,w,h.",
            "value": "word | wayA.json | wayB.json.",
            "note": "As with OCR check, the region is read once when Find win is off.",
        },
        "ru": {
            "title": "ЕСЛИ слово найдено (OCR) → JSON A иначе JSON B",
            "what": "То же решение, но по тексту: область читается через OCR, и слово "
                    "выбирает путь A (найдено) или B (не найдено).",
            "target": "Область x,y,w,h.",
            "value": "слово | wayA.json | wayB.json.",
            "note": "Как и в «OCR check», при выключенном Find win область читается один "
                    "раз.",
        },
    },
    "branch_verify": {
        "en": {
            "what": "Branch on the word AND save proof: a PASS/FAIL PNG of the region goes "
                    "to results\\ before the run continues down Way A or Way B. The "
                    "branching version of Verify text.",
            "target": "Region x,y,w,h.",
            "value": "word | wayA.json | wayB.json.",
        },
        "ru": {
            "title": "ЕСЛИ слово найдено → A иначе B (+ скриншот-доказательство)",
            "what": "Ветвление по слову И сохранение доказательства: PNG области с "
                    "префиксом PASS/FAIL кладётся в results\\, и только потом прогон идёт "
                    "путём A или B. Это «Verify text» с ветвлением.",
            "target": "Область x,y,w,h.",
            "value": "слово | wayA.json | wayB.json.",
        },
    },
    "branch_value": {
        "en": {
            "what": "Branch on numbers read from the screen. The condition names a label, "
                    "the app finds that label in the OCR text and takes the number next to "
                    "it. Clauses are joined with AND / OR (OR has the lower priority), "
                    "operators are <= >= < > == != ('=' means '=='), and abs(...) or "
                    "|...| compare the absolute value — perfect for a tolerance around "
                    "zero.",
            "target": "Region x,y,w,h with the numbers.",
            "value": "condition | wayA | wayB, e.g. Az ML<=0.1 AND El ML<=0.1 | pass.json | "
                     "retry.json (use ↷ Branch setup).",
            "note": "Unlike the text branches this one keeps re-reading until the condition "
                    "becomes true or Timeout expires, and it always saves a PASS/FAIL proof "
                    "PNG. The log shows every parsed clause, e.g. 'Az ML<=0.1→0.07[ok]', so "
                    "a wrong label is easy to spot ('n/a' = the label was not recognised).",
        },
        "ru": {
            "title": "ЕСЛИ числовое условие выполнено → A иначе B (+ доказательство)",
            "what": "Ветвление по числам с экрана. В условии указывается подпись, "
                    "программа находит её в OCR-тексте и берёт стоящее рядом число. "
                    "Условия соединяются через AND / OR (у OR приоритет ниже), операторы "
                    "<= >= < > == != (одиночное «=» означает «==»), а abs(...) или |...| "
                    "сравнивают модуль — то, что нужно для допуска вокруг нуля.",
            "target": "Область x,y,w,h с числами.",
            "value": "условие | wayA | wayB, например Az ML<=0.1 AND El ML<=0.1 | "
                     "pass.json | retry.json (удобнее через ↷ Branch setup).",
            "note": "В отличие от текстовых ветвлений это читает область повторно, пока "
                    "условие не станет истинным или не выйдет Timeout, и всегда сохраняет "
                    "PASS/FAIL-доказательство. В лог пишется каждое разобранное условие, "
                    "например «Az ML<=0.1→0.07[ok]», так что ошибку в подписи видно сразу "
                    "(«n/a» = подпись не распознана).",
        },
    },
    "branch_calib": {
        "en": {
            "what": "Branch on a gimbal calibration CSV instead of the screen. The file is "
                    "read (columns Azimuth, Elevation and Antenna Gain — or Power Received "
                    "— are found by name), then the app takes the Az cut (rows whose El is "
                    "closest to 0) and the El cut (rows whose Az is closest to 0), finds "
                    "the peak-gain point in each, and uses those two points as the Az/El "
                    "boresight offsets. Your condition is checked against them.",
            "target": "Path to the calibration CSV, e.g. calib.csv.",
            "value": "condition | wayA | wayB, typically abs(Az)<=0.3 AND abs(El)<=0.3 | "
                     "pass.json | recalibrate.json.",
            "note": "A PASS/FAIL .txt report with both offsets, their peak gains and point "
                    "counts is saved to results\\; if '<csv name>_Pattern.png' sits next to "
                    "the CSV it is copied there too as proof. Point Way B at a "
                    "recalibration scenario and you have an automatic retry loop.",
        },
        "ru": {
            "title": "ЕСЛИ калибровка гимбала по CSV в норме (Az/El) → A иначе B",
            "what": "Ветвление не по экрану, а по CSV калибровки гимбала. Файл читается "
                    "(колонки Azimuth, Elevation и Antenna Gain — либо Power Received — "
                    "ищутся по названию), затем берётся Az-сечение (строки, где El ближе "
                    "всего к 0) и El-сечение (строки, где Az ближе всего к 0), в каждом "
                    "находится точка максимума усиления, и эти две точки считаются "
                    "смещениями Az/El. По ним и проверяется условие.",
            "target": "Путь к CSV калибровки, например calib.csv.",
            "value": "условие | wayA | wayB, обычно abs(Az)<=0.3 AND abs(El)<=0.3 | "
                     "pass.json | recalibrate.json.",
            "note": "В results\\ сохраняется отчёт .txt с префиксом PASS/FAIL: оба "
                    "смещения, усиление в пике и количество точек. Если рядом с CSV лежит "
                    "«<имя csv>_Pattern.png», он тоже копируется как доказательство. "
                    "Направьте путь B на сценарий рекалибровки — получится автоматический "
                    "цикл повторов.",
        },
    },
    "goto_playlist": {
        "en": {
            "what": "Unconditional jump — no condition, no Way A/B. The moment this step "
                    "runs, the remaining steps of the scenario are skipped and the given "
                    "JSON takes over. If the target is a playlist file, all of its programs "
                    "run in order.",
            "target": "Path to a scenario JSON or a playlist JSON. Relative paths are "
                      "resolved from the current scenario's folder.",
            "value": "Not used.",
            "note": "The right panel switches to ↷ Jump chain and follows the run (▶ = "
                    "running now, ✓ = finished) while ▣ My list keeps your own list "
                    "untouched. Chains are limited to 200 hops so an accidental loop stops "
                    "itself instead of running forever.",
        },
        "ru": {
            "title": "Переход в другой плейлист/сценарий",
            "what": "Безусловный переход — без условия и без путей A/B. Как только шаг "
                    "выполнился, оставшиеся шаги сценария пропускаются, и управление "
                    "забирает указанный JSON. Если цель — файл-плейлист, все его "
                    "программы выполняются по порядку.",
            "target": "Путь к JSON-сценарию или к JSON-плейлисту. Относительные пути "
                      "считаются от папки текущего сценария.",
            "value": "Не нужно.",
            "note": "Правая панель переключается на ↷ Jump chain и едет вместе с прогоном "
                    "(▶ — идёт сейчас, ✓ — пройдено), а ваш собственный список остаётся "
                    "в чипе ▣ My list. Длина цепочки ограничена 200 переходами, поэтому "
                    "случайный цикл остановится сам.",
        },
    },
    "select_target": {
        "en": {
            "what": "Remembers a path inside the runner — nothing happens on disk. The next "
                    "Rename folder / Delete folder steps use it when their own Value is "
                    "empty.",
            "target": "Not used.",
            "value": "The path to remember, e.g. results\\unit_{serial}.",
        },
        "ru": {
            "title": "Выбор папки/файла (для следующего шага)",
            "what": "Запоминает путь внутри движка — на диске ничего не происходит. "
                    "Следующие шаги переименования/удаления берут его, если их "
                    "собственное Value пусто.",
            "target": "Не нужно.",
            "value": "Путь, который надо запомнить, например results\\unit_{serial}.",
        },
    },
    "create_folder": {
        "en": {
            "what": "Creates the folder together with its parents (no error if it already "
                    "exists) and immediately makes it the selected target for the following "
                    "steps.",
            "target": "Not used.",
            "value": "Path, e.g. results\\unit_{serial}.",
        },
        "ru": {
            "title": "Создание папки",
            "what": "Создаёт папку вместе с родительскими (если уже есть — не ошибка) и "
                    "сразу делает её выбранной целью для следующих шагов.",
            "target": "Не нужно.",
            "value": "Путь, например results\\unit_{serial}.",
        },
    },
    "rename_folder": {
        "en": {
            "what": "Renames the selected path, so a Select folder/file or Create folder "
                    "step must come first. A bare name renames inside the same parent "
                    "folder; a value that contains folders (or is absolute) moves it there. "
                    "The renamed path stays selected.",
            "target": "Not used.",
            "value": "New name or path, e.g. unit_{serial}_done.",
        },
        "ru": {
            "title": "Переименование папки",
            "what": "Переименовывает выбранный путь, поэтому перед ним нужен шаг выбора "
                    "или создания папки. Просто имя — переименование в той же "
                    "родительской папке; значение с папками (или абсолютное) — перемещение "
                    "туда. Переименованный путь остаётся выбранным.",
            "target": "Не нужно.",
            "value": "Новое имя или путь, например unit_{serial}_done.",
        },
    },
    "delete_folder": {
        "en": {
            "what": "Deletes a folder ON DISK, recursively. Refuses to delete a drive root, "
                    "and fails when the path does not exist or is a file.",
            "target": "Not used.",
            "value": "Path to delete, or empty to use the selected target.",
            "note": "To remove something inside another program's window use Delete "
                    "on-screen item (Delete key) instead — that one only presses a key.",
        },
        "ru": {
            "title": "Удаление папки на диске (по пути)",
            "what": "Удаляет папку НА ДИСКЕ вместе с содержимым. Отказывается удалять "
                    "корень диска и падает, если путь не существует или это файл.",
            "target": "Не нужно.",
            "value": "Путь для удаления или пусто — тогда берётся выбранная цель.",
            "note": "Чтобы удалить что-то внутри чужого окна, используйте «Delete "
                    "on-screen item (Delete key)» — тот шаг просто жмёт клавишу.",
        },
    },
    "pause": {
        "en": {
            "what": "Waits the given number of seconds. The wait is checked every 0.2 s, so "
                    "⏹ Stop reacts immediately instead of after the whole pause.",
            "target": "Not used.",
            "value": "Seconds, e.g. 3. Empty = 1.",
            "note": "Prefer Wait for template when you are waiting for something specific — "
                    "a fixed pause is either too short on a slow day or wasted time on a "
                    "fast one.",
        },
        "ru": {
            "title": "Пауза (секунды)",
            "what": "Ждёт заданное число секунд. Ожидание проверяется каждые 0.2 с, "
                    "поэтому ⏹ Stop срабатывает сразу, а не после конца паузы.",
            "target": "Не нужно.",
            "value": "Секунды, например 3. Пусто = 1.",
            "note": "Если вы ждёте конкретное событие, лучше «Wait for template»: "
                    "фиксированная пауза либо окажется короткой в медленный день, либо "
                    "будет тратить время в быстрый.",
        },
    },
}

# Действия, сгруппированные по разделам справки (порядок = порядок в диалоге).
HELP_ACTION_GROUPS = {
    "act_input": ["click_image", "double_click_image", "wait_image", "scroll", "key",
                  "type_text", "fill_field", "ui_delete"],
    "act_ocr": ["ocr_check", "verify_text", "screenshot"],
    "act_flow": ["branch_image", "branch_text", "branch_verify", "branch_value",
                 "branch_calib", "goto_playlist"],
    "act_files": ["select_target", "create_folder", "rename_folder", "delete_folder",
                  "pause"],
}

HELP_FIELD_LABELS = {
    "en": {"what": "What it does", "target": "Template / area", "value": "Value",
           "note": "Good to know"},
    "ru": {"what": "Что делает", "target": "Template / area", "value": "Value",
           "note": "Важно знать"},
}


def help_action_topic_key(action):
    """Раздел справки, в котором описано данное действие."""
    for topic, actions in HELP_ACTION_GROUPS.items():
        if action in actions:
            return topic
    return "start"


def help_escape(text):
    """Описания действий — обычный текст, а не разметка: '<=' и '<word>' должны
    доехать до экрана, а не быть съеденными как HTML-тег."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def help_actions_html(topic_key, lang):
    """Собирает карточки действий раздела: заголовок + поля описания."""
    parts = []
    for action in HELP_ACTION_GROUPS.get(topic_key, []):
        doc = ACTION_DOCS.get(action, {}).get(lang, {})
        parts.append(
            "<h3 style='color:#5c93d6; margin:16px 0 2px 0;'>"
            f"{help_escape(ACTIONS[action])}</h3>")
        subtitle = doc.get("title")
        tail = f" — {help_escape(subtitle)}" if subtitle else ""
        parts.append(
            "<p style='margin:0 0 8px 0; color:#7f8a94;'>"
            f"<code>{action}</code>{tail}</p>")
        for field in ("what", "target", "value", "note"):
            text = doc.get(field)
            if text:
                parts.append(
                    "<p style='margin:0 0 6px 0;'>"
                    f"<b style='color:#cfd6dc;'>{HELP_FIELD_LABELS[lang][field]}:</b> "
                    f"{help_escape(text)}</p>")
    return "".join(parts)


HELP_TOPICS = [
    {
        "key": "start",
        "title": {"en": "1. Getting started", "ru": "1. Быстрый старт"},
        "body": {
            "en": """
<p>A scenario is a <b>list of steps</b>, top to bottom. Each row is one action performed
on <i>another</i> program's window — a click, a keystroke, an OCR check, a file
operation. Nothing is scripted: you capture what you see on screen and pick what to do
with it.</p>

<h3>How a run works</h3>
<ul>
<li><b>▶ Run</b> waits <b>Start delay</b> seconds first, so you can bring the target
window to the front, and then executes the rows in order.</li>
<li>The <b>Execution log</b> (left, expand it with ▸ Show) reports every step with its
result, coordinates and file paths.</li>
<li><b>⏹ Stop</b> interrupts the run at the next check point — a Pause is checked every
0.2 s, a search every 0.4 s.</li>
<li>A step that errors either halts the run or is skipped, depending on its <b>Stop</b>
checkbox.</li>
</ul>

<h3>Building a step</h3>
<ul>
<li><b>➕ Add</b> appends a row, <b>➕ Insert</b> puts one after the selected row; ↑ ↓
reorder; <b>📋 Copy / 📋 Paste</b> (Ctrl+C / Ctrl+V) duplicate steps.</li>
<li>Pick the <b>Action</b>, then press <b>📷 Capture</b> (Ctrl+Shift+S) and drag a
rectangle over the target. For image actions a PNG is saved into <code>templates\\</code>
and its path goes into Template/area; for OCR/screenshot actions the region is written as
<code>x,y,w,h</code> instead.</li>
<li>Fill <b>Value</b> if the action needs one — the placeholder text in the cell always
shows the expected format.</li>
</ul>

<h3>Files</h3>
<p><b>💾 Save</b> writes the scenario as a JSON file — one file per program or workflow —
and <b>📂 Load</b> opens it again. Templates are PNG files with a small
<code>.meta.json</code> next to them. Everything is plain data, so the whole folder can be
copied to another PC. The <b>playlist</b> on the right chains those scenario files
together.</p>
""",
            "ru": """
<p>Сценарий — это <b>список шагов</b> сверху вниз. Каждая строка — одно действие над
окном <i>другой</i> программы: клик, нажатие клавиш, OCR-проверка, операция с файлами.
Ничего программировать не нужно: вы снимаете то, что видите на экране, и выбираете, что с
этим сделать.</p>

<h3>Как идёт прогон</h3>
<ul>
<li><b>▶ Run</b> сначала ждёт <b>Start delay</b> секунд, чтобы вы успели вывести нужное
окно на передний план, а затем выполняет строки по порядку.</li>
<li><b>Execution log</b> (слева, раскрывается кнопкой ▸ Show) пишет каждый шаг: результат,
координаты, пути к файлам.</li>
<li><b>⏹ Stop</b> прерывает прогон на ближайшей проверке — пауза проверяется каждые
0.2 с, поиск — каждые 0.4 с.</li>
<li>Упавший шаг либо останавливает прогон, либо пропускается — в зависимости от галочки
<b>Stop</b> в его строке.</li>
</ul>

<h3>Как собрать шаг</h3>
<ul>
<li><b>➕ Add</b> добавляет строку в конец, <b>➕ Insert</b> — после выделенной; ↑ ↓
меняют порядок; <b>📋 Copy / 📋 Paste</b> (Ctrl+C / Ctrl+V) копируют шаги.</li>
<li>Выберите <b>Action</b>, нажмите <b>📷 Capture</b> (Ctrl+Shift+S) и обведите цель
мышью. Для действий с картинками PNG сохранится в <code>templates\\</code>, а путь
подставится в Template/area; для OCR и скриншотов вместо пути запишется область
<code>x,y,w,h</code>.</li>
<li>Заполните <b>Value</b>, если действие его требует — подсказка в самой ячейке всегда
показывает ожидаемый формат.</li>
</ul>

<h3>Файлы</h3>
<p><b>💾 Save</b> сохраняет сценарий в JSON — один файл на программу или процесс, а
<b>📂 Load</b> открывает его снова. Шаблоны — это PNG плюс небольшой
<code>.meta.json</code> рядом. Всё хранится в открытых данных, поэтому папку можно целиком
перенести на другой компьютер. <b>Плейлист</b> справа связывает такие файлы в
последовательность.</p>
""",
        },
    },
    {
        "key": "columns",
        "title": {"en": "2. The steps table", "ru": "2. Таблица шагов"},
        "body": {
            "en": """
<ul>
<li><b>On</b> — enable/disable the step. Disabled rows are skipped and logged as skipped.
The checkbox in the header toggles every row at once.</li>
<li><b>Action</b> — what the step does (see the Actions sections).</li>
<li><b>Template / area</b> — the target: a path to a PNG template, a region
<code>x,y,w,h</code>, a CSV path (calibration branch) or a JSON path (jump step).</li>
<li><b>…</b> — pick a template file from disk instead of capturing it.</li>
<li><b>Preview</b> — thumbnail of the template so rows are easy to tell apart; click it to
open the picture full size with its regions drawn on top.</li>
<li><b>Value</b> — the action-specific input. Tokens <code>{serial} {date} {time}
{ts}</code> are expanded at run time.</li>
<li><b>Timeout</b> — how many seconds a search may keep retrying before the step fails
(and the length of a Pause).</li>
<li><b>Find win</b> — see below. Off by default; the header checkbox toggles all rows.</li>
<li><b>Stop</b> — if this step errors, stop the whole scenario. Unchecked means the run
continues with the next step. The header checkbox toggles all rows.</li>
</ul>

<h3>What Timeout really affects</h3>
<p>Template searches (click / double-click / wait / scroll / fill field) retry every 0.4 s
until Timeout. <b>OCR check</b> and the <b>word branches</b> read the region only
<i>once</i> when Find win is off — Timeout does not add retries there. The
<b>value condition branch</b> always retries until Timeout. <b>Pause</b> uses Timeout's
neighbour, its own Value, as the number of seconds.</p>

<h3>What Find win really does</h3>
<p>It is a last resort for targets that are not visible: the app minimises <i>all</i>
windows (including its own), looks at the bare desktop, then brings windows to the front
<b>one at a time</b> and re-checks after each one, until the target is found or Timeout
expires. Own windows are restored at the end. It needs the <code>pygetwindow</code>
package, it is slow, and it steals focus — but it also turns OCR steps into
retry-until-timeout steps, which is sometimes exactly what you want.</p>

<p>Hover any column header to get its short description in the guide bar above the table,
or press <b>Show all columns</b> for the full list.</p>
""",
            "ru": """
<ul>
<li><b>On</b> — включить/выключить шаг. Выключенные строки пропускаются и отмечаются в
логе. Галочка в заголовке переключает все строки сразу.</li>
<li><b>Action</b> — что делает шаг (см. разделы про действия).</li>
<li><b>Template / area</b> — цель шага: путь к PNG-шаблону, область <code>x,y,w,h</code>,
путь к CSV (калибровочное ветвление) или путь к JSON (шаг перехода).</li>
<li><b>…</b> — выбрать файл шаблона с диска вместо съёмки с экрана.</li>
<li><b>Preview</b> — миниатюра шаблона, чтобы строки было легко различать; по клику
картинка открывается в полном размере с нарисованными регионами.</li>
<li><b>Value</b> — данные, специфичные для действия. Токены <code>{serial} {date} {time}
{ts}</code> подставляются во время прогона.</li>
<li><b>Timeout</b> — сколько секунд поиск может повторяться, прежде чем шаг упадёт (а
также длина паузы).</li>
<li><b>Find win</b> — см. ниже. По умолчанию выключено; галочка в заголовке переключает
все строки.</li>
<li><b>Stop</b> — если шаг упал, остановить весь сценарий. Без галочки прогон продолжится
со следующего шага. Заголовок переключает все строки.</li>
</ul>

<h3>На что реально влияет Timeout</h3>
<p>Поиск шаблонов (клик, двойной клик, ожидание, прокрутка, заполнение поля) повторяется
каждые 0.4 с до истечения Timeout. <b>OCR-проверка</b> и <b>ветвления по слову</b> при
выключенном Find win читают область только <i>один раз</i> — Timeout повторов не даёт.
<b>Ветвление по числовому условию</b> повторяет чтение до таймаута всегда. У <b>Pause</b>
длительность берётся не из Timeout, а из его собственного Value.</p>

<h3>Что реально делает Find win</h3>
<p>Это крайняя мера для целей, которых не видно: программа сворачивает <i>все</i> окна
(включая своё), проверяет пустой рабочий стол, а затем выводит окна на передний план
<b>по одному</b>, каждый раз проверяя заново — пока цель не найдётся или не выйдет
Timeout. В конце свои окна возвращаются. Нужен пакет <code>pygetwindow</code>, работает
медленно и забирает фокус — зато превращает OCR-шаги в шаги «повторять до таймаута», что
иногда как раз и требуется.</p>

<p>Наведите курсор на заголовок любой колонки — краткое описание появится в полосе над
таблицей; кнопка <b>Show all columns</b> покажет весь список сразу.</p>
""",
        },
    },
    {
        "key": "act_input",
        "title": {"en": "3. Actions — mouse, keyboard, fields",
                  "ru": "3. Действия — мышь, клавиатура, поля"},
    },
    {
        "key": "act_ocr",
        "title": {"en": "4. Actions — OCR, verification, screenshots",
                  "ru": "4. Действия — OCR, проверки, скриншоты"},
    },
    {
        "key": "act_flow",
        "title": {"en": "5. Actions — branching and jumps",
                  "ru": "5. Действия — ветвления и переходы"},
    },
    {
        "key": "act_files",
        "title": {"en": "6. Actions — files, folders, pauses",
                  "ru": "6. Действия — файлы, папки, паузы"},
    },
    {
        "key": "templates",
        "title": {"en": "7. Templates, capture and the regions editor",
                  "ru": "7. Шаблоны, съёмка и редактор регионов"},
        "body": {
            "en": """
<h3>📷 Capture (Ctrl+Shift+S)</h3>
<p>Freezes a screenshot of all monitors and lets you drag a rectangle over it. For image
actions the selection is saved as a PNG in <code>templates\\</code> and its path is
written into Template/area; for OCR, verification and screenshot actions the selection is
written as absolute coordinates <code>x,y,w,h</code> instead. Esc cancels.</p>

<h3>✏ Regions — the five markings</h3>
<ul>
<li><b>Compare (green)</b> — the part of the PNG that is actually matched. Crop it down to
the stable, unmistakable piece of UI; everything outside is ignored.</li>
<li><b>Exclude (red)</b> — areas <i>inside</i> Compare that must be ignored: changing
numbers, timestamps, progress bars, highlighted rows. Matching switches to a masked
correlation, so the template survives dynamic content.</li>
<li><b>Click point</b> — where the click actually lands (the centre by default). Move it
when you must match a label but click the control next to it.</li>
<li><b>Input zone (blue)</b> — for <i>Fill input field</i>: the box to click. It overrides
the click point, so you can match a label and type into the field beside it.</li>
<li><b>Scroll bar</b> — for <i>Scroll panel</i>: where the wheel notches are delivered. It
also overrides the click point.</li>
</ul>

<h3>Where it is stored</h3>
<p>Next to <code>tpl_123.png</code> lies <code>tpl_123.meta.json</code> with these
rectangles. Keep the pair together — copying only the PNG loses all the markings and the
whole image is matched again.</p>

<h3>How matching works</h3>
<p>The search runs on the virtual desktop (all monitors joined), on both grayscale pixels
and Canny edges, over 11 scales from ×0.5 to ×2.0, and accepts a match from a correlation
of <b>0.80</b>. When a step fails, the log prints the best score and the scale where it
happened — that tells you whether to re-capture the template (≈0.7), to crop Compare
tighter, or to look for the window at all (≈0.2).</p>
""",
            "ru": """
<h3>📷 Capture (Ctrl+Shift+S)</h3>
<p>Замораживает снимок всех мониторов и даёт обвести область мышью. Для действий с
картинками выделение сохраняется как PNG в <code>templates\\</code>, а путь подставляется
в Template/area; для OCR, проверок и скриншотов вместо пути записываются абсолютные
координаты <code>x,y,w,h</code>. Esc — отмена.</p>

<h3>✏ Regions — пять разметок</h3>
<ul>
<li><b>Compare (зелёный)</b> — та часть PNG, по которой реально идёт сравнение. Обрежьте
её до неизменного, однозначно узнаваемого фрагмента интерфейса; всё вне этой рамки
игнорируется.</li>
<li><b>Exclude (красный)</b> — области <i>внутри</i> Compare, которые надо игнорировать:
меняющиеся числа, время, прогресс-бары, подсветка строк. Сравнение переключается на
корреляцию с маской, поэтому шаблон выдерживает динамическое содержимое.</li>
<li><b>Click point</b> — куда именно придётся клик (по умолчанию центр). Сдвиньте его,
когда искать нужно подпись, а кликать — по соседнему элементу.</li>
<li><b>Input zone (синий)</b> — для <i>Fill input field</i>: поле, по которому надо
кликнуть. Приоритетнее точки клика, поэтому можно искать подпись, а печатать в поле
рядом.</li>
<li><b>Scroll bar</b> — для <i>Scroll panel</i>: место, куда отправляются щелчки колеса.
Тоже приоритетнее точки клика.</li>
</ul>

<h3>Где это хранится</h3>
<p>Рядом с <code>tpl_123.png</code> лежит <code>tpl_123.meta.json</code> с этими
прямоугольниками. Держите пару вместе: если скопировать только PNG, вся разметка
потеряется и сравниваться будет всё изображение.</p>

<h3>Как работает сравнение</h3>
<p>Поиск идёт по виртуальному рабочему столу (все мониторы вместе), и по оттенкам серого,
и по контурам Canny, в 11 масштабах от ×0.5 до ×2.0, а совпадением считается корреляция от
<b>0.80</b>. Когда шаг падает, в лог пишется лучшее совпадение и масштаб, на котором оно
получилось — по этому числу понятно, надо ли переснять шаблон (≈0.7), обрезать Compare
плотнее или искать само окно (≈0.2).</p>
""",
        },
    },
    {
        "key": "playlist",
        "title": {"en": "8. Playlist panel and the jump chain",
                  "ru": "8. Панель плейлиста и цепочка переходов"},
        "body": {
            "en": """
<p>The right-hand panel chains whole scenario files. <b>➕ Add JSON</b> queues programs,
<b>➖ Remove</b> and ↑ ↓ edit the queue, <b>▶ Run list</b> runs them top to bottom and
<b>⏹ Stop list</b> stops after the current step. The dot next to the header blinks green
while a list is running, turns red when it stopped and grey when idle.</p>

<h3>Two lists, two chips</h3>
<ul>
<li><b>▣ My list (n)</b> — the list you built. It is what ▶ Run list runs and the only one
you can edit, and it is kept even when it was never saved to a file.</li>
<li><b>↷ Jump chain (k/n)</b> — appears as soon as a <i>Move to another
playlist/scenario</i> or a branch step hands the run over. It lists every scenario the run
travels through, in order: <b>▶</b> = running now, <b>✓</b> = already finished. If the
target was a playlist file, all of its programs show up at once.</li>
</ul>
<p>The panel switches to the jump chain by itself on every jump, so you can watch the run
travel. Click <b>▣ My list</b> to get your own programs back — the run keeps going, and
auto-switching pauses until the next run starts. The chain is a read-only view; editing
buttons always work on your own list.</p>

<h3>Playlist files</h3>
<p><b>💾 Save list…</b> exports the panel as <code>{"playlist": [ …paths… ]}</code>, with
paths relative to the file when possible, so the folder can be moved as a group.
<b>📂 Load list…</b> loads such a file back. A saved playlist is exactly what a branch or
a jump step can point at — that is how one decision node drives an entire playlist.</p>

<h3>Preview switcher</h3>
<p>Click any program to load its steps into the table on the left (it becomes the file you
are editing, so 💾 Save writes back to it). The bar above the table shows what is loaded
and where it sits — <code>📄 name.json — [2/4 in playlist]</code> or
<code>↷ name.json — [2/3 in jump chain]</code> — and <b>◀ Prev / Next ▶</b> step through
the whole list one program at a time.</p>

<p>The <b>Playlist log</b> below records the list's own history: which program started,
where a jump went, what failed to load. It starts collapsed — expand it with ▸ Show.</p>
""",
            "ru": """
<p>Правая панель связывает целые файлы-сценарии. <b>➕ Add JSON</b> добавляет программы в
очередь, <b>➖ Remove</b> и ↑ ↓ правят очередь, <b>▶ Run list</b> выполняет их сверху
вниз, <b>⏹ Stop list</b> останавливает после текущего шага. Точка рядом с заголовком
мигает зелёным во время прогона, краснеет после остановки и серая в покое.</p>

<h3>Два списка, два чипа</h3>
<ul>
<li><b>▣ My list (n)</b> — список, который вы собрали сами. Именно его запускает
▶ Run list, только его можно править, и он сохраняется в памяти, даже если ни разу не был
записан в файл.</li>
<li><b>↷ Jump chain (k/n)</b> — появляется, как только шаг <i>Move to another
playlist/scenario</i> или ветвление передаёт управление дальше. Здесь перечислены все
сценарии, через которые едет прогон, по порядку: <b>▶</b> — идёт сейчас, <b>✓</b> — уже
пройдено. Если целью был файл-плейлист, все его программы появятся сразу.</li>
</ul>
<p>При каждом переходе панель сама показывает цепочку, чтобы было видно движение прогона.
Нажмите <b>▣ My list</b>, чтобы вернуть свои программы — прогон при этом продолжается, а
автопереключение приостановится до следующего запуска. Цепочка доступна только для
просмотра; кнопки правки всегда работают с вашим списком.</p>

<h3>Файлы плейлистов</h3>
<p><b>💾 Save list…</b> сохраняет панель как <code>{"playlist": [ …пути… ]}</code>, по
возможности с относительными путями, чтобы папку можно было переносить целиком.
<b>📂 Load list…</b> загружает такой файл обратно. Именно на сохранённый плейлист может
указывать ветвление или шаг перехода — так один узел решения проезжает целый плейлист.</p>

<h3>Переключатель предпросмотра</h3>
<p>Клик по программе загружает её шаги в таблицу слева (она становится файлом, который вы
редактируете, поэтому 💾 Save пишет именно в него). Полоса над таблицей показывает, что
загружено и где это находится — <code>📄 name.json — [2/4 in playlist]</code> или
<code>↷ name.json — [2/3 in jump chain]</code>, а <b>◀ Prev / Next ▶</b> проходят весь
список по одной программе.</p>

<p><b>Playlist log</b> внизу ведёт историю списка: какая программа началась, куда ушёл
переход, что не удалось загрузить. Он свёрнут по умолчанию — раскройте кнопкой
▸ Show.</p>
""",
        },
    },
    {
        "key": "tokens",
        "title": {"en": "9. Tokens, serial numbers, results",
                  "ru": "9. Токены, серийные номера, результаты"},
        "body": {
            "en": """
<h3>Tokens</h3>
<ul>
<li><code>{serial}</code> — the current serial from the <b>Serial</b> field.</li>
<li><code>{date}</code> — YYYY-MM-DD, <code>{time}</code> — HHMMSS, <code>{ts}</code> —
epoch seconds (handy for guaranteed-unique names).</li>
</ul>
<p>They are expanded in the Value of Type text, Fill input field, Screenshot and all
folder actions, and in branch / jump paths.</p>

<h3>How the serial counts</h3>
<p>Every <i>use</i> of <code>{serial}</code> increments the trailing group of digits while
keeping the prefix and the width: <code>0001 → 0002</code>, <code>SN0099 → SN0100</code>,
<code>AB → AB1</code>. Up to 16 characters, letters and digits. When the run ends, the
Serial field is updated to the next value, so the next run continues the count instead of
starting over. Two <code>{serial}</code> tokens in one step therefore give two different
numbers — put the serial in a folder name once and reuse that folder.</p>

<h3>Where files go</h3>
<ul>
<li><code>results\\</code> — proofs and reports: <code>PASS_…png</code> /
<code>FAIL_…png</code> from Verify text and the proof branches, the calibration
<code>.txt</code> report plus a copied <code>_Pattern.png</code>, and any Screenshot whose
name has no folder of its own.</li>
<li><code>templates\\</code> — captured PNG templates with their <code>.meta.json</code>
sidecars.</li>
<li>Your own scenario and playlist JSON files live wherever you save them; relative paths
inside them are resolved from the folder of the file that contains them.</li>
</ul>
""",
            "ru": """
<h3>Токены</h3>
<ul>
<li><code>{serial}</code> — текущий серийник из поля <b>Serial</b>.</li>
<li><code>{date}</code> — ГГГГ-ММ-ДД, <code>{time}</code> — ЧЧММСС, <code>{ts}</code> —
секунды эпохи (удобно для гарантированно уникальных имён).</li>
</ul>
<p>Подставляются в Value действий «Type text», «Fill input field», «Screenshot» и всех
действий с папками, а также в пути ветвлений и переходов.</p>

<h3>Как считается серийник</h3>
<p>Каждое <i>использование</i> <code>{serial}</code> увеличивает хвостовую группу цифр,
сохраняя префикс и количество разрядов: <code>0001 → 0002</code>,
<code>SN0099 → SN0100</code>, <code>AB → AB1</code>. До 16 символов, буквы и цифры. По
окончании прогона поле Serial обновляется на следующее значение, поэтому следующий прогон
продолжает счёт, а не начинает заново. Два токена <code>{serial}</code> в одном шаге дадут
два разных номера — вставьте серийник один раз в имя папки и дальше используйте эту
папку.</p>

<h3>Куда попадают файлы</h3>
<ul>
<li><code>results\\</code> — доказательства и отчёты: <code>PASS_…png</code> /
<code>FAIL_…png</code> от «Verify text» и ветвлений с доказательством, отчёт
<code>.txt</code> по калибровке вместе со скопированным <code>_Pattern.png</code>, а также
любой скриншот, в имени которого не указана своя папка.</li>
<li><code>templates\\</code> — снятые PNG-шаблоны с файлами <code>.meta.json</code>.</li>
<li>Ваши JSON сценариев и плейлистов лежат там, где вы их сохранили; относительные пути
внутри них считаются от папки того файла, в котором записаны.</li>
</ul>
""",
        },
    },
    {
        "key": "trouble",
        "title": {"en": "10. Troubleshooting", "ru": "10. Диагностика проблем"},
        "body": {
            "en": """
<ul>
<li><b>"Automation libraries not found"</b> — the GUI still opens and you can build
scenarios, but running needs the packages from <code>requirements.txt</code>.</li>
<li><b>OCR steps fail with a Tesseract message</b> — install the Tesseract engine and
either add it to PATH or put it in <code>C:\\Program Files\\Tesseract-OCR\\</code>. Every
other action keeps working without it.</li>
<li><b>"not found on screen within N s (best match 0.62 at scale 0.9)"</b> — the template
was not recognised. A best match around 0.7 means it is nearly right: re-capture it, or
crop <b>Compare</b> to a smaller stable piece and mark changing parts as <b>Exclude</b>.
A scale far from 1.0 means the target is drawn at another size (different DPI or
resolution) — that is supported, but a tighter Compare helps a lot.</li>
<li><b>OCR reads nonsense</b> — capture a tighter region around just the text; avoid
scaled or anti-aliased text on a busy background. The region is already upscaled ×2.5 and
thresholded, so what usually helps is <i>less</i> in the frame.</li>
<li><b>Clicks land in the wrong place</b> — check the click point in ✏ Regions, and
re-capture templates after changing display scaling. The app makes itself per-monitor
DPI-aware at start so screenshots, matching and clicks share one coordinate system.</li>
<li><b>A run must be aborted right now</b> — slam the mouse pointer into the very top-left
corner of the screen: pyautogui's failsafe aborts the automation immediately. ⏹ Stop is
the graceful way.</li>
<li><b>Find win does nothing</b> — it needs the <code>pygetwindow</code> package; without
it the log says so and the search stays on the current screen.</li>
<li><b>"Branch chain too deep (200)"</b> — the scenarios keep jumping into each other. The
guard stops the run; look at the jump chain in the right panel to see the loop.</li>
<li><b>"Runner is already active"</b> — a run is still in progress; press ⏹ Stop and wait
for the log to report the end.</li>
<li><b>The playlist skipped a program</b> — the Playlist log names the file and the
reason: missing file, a playlist file used where a scenario was expected, or a corrupted
JSON (it must be a list of step objects).</li>
</ul>
""",
            "ru": """
<ul>
<li><b>«Automation libraries not found»</b> — интерфейс всё равно откроется и сценарии
собирать можно, но для запуска нужны пакеты из <code>requirements.txt</code>.</li>
<li><b>OCR-шаги падают с сообщением про Tesseract</b> — установите движок Tesseract и либо
добавьте его в PATH, либо положите в <code>C:\\Program Files\\Tesseract-OCR\\</code>. Все
остальные действия работают и без него.</li>
<li><b>«not found on screen within N s (best match 0.62 at scale 0.9)»</b> — шаблон не
распознан. Лучшее совпадение около 0.7 означает «почти то же самое»: переснимите шаблон
или обрежьте <b>Compare</b> до меньшего неизменного фрагмента, а меняющиеся части
отметьте как <b>Exclude</b>. Масштаб, далёкий от 1.0, говорит, что цель отрисована в
другом размере (другой DPI или разрешение) — это поддерживается, но плотный Compare
помогает сильно.</li>
<li><b>OCR читает ерунду</b> — снимите область теснее, только вокруг текста; избегайте
масштабированного и сглаженного текста на пёстром фоне. Область и так увеличивается в
2.5 раза и бинаризуется, поэтому помогает обычно <i>меньше</i> лишнего в кадре.</li>
<li><b>Клики попадают не туда</b> — проверьте точку клика в ✏ Regions и переснимите
шаблоны после смены масштаба экрана. Программа при старте делает себя per-monitor
DPI-aware, чтобы снимок, поиск и клики жили в одной системе координат.</li>
<li><b>Нужно немедленно прервать прогон</b> — резко уведите указатель мыши в самый левый
верхний угол экрана: защита pyautogui мгновенно прерывает автоматизацию. Штатный способ —
⏹ Stop.</li>
<li><b>Find win ничего не делает</b> — нужен пакет <code>pygetwindow</code>; без него в
лог пишется предупреждение, а поиск остаётся на текущем экране.</li>
<li><b>«Branch chain too deep (200)»</b> — сценарии переходят друг в друга по кругу.
Защита останавливает прогон; посмотрите цепочку переходов в правой панели, чтобы найти
цикл.</li>
<li><b>«Runner is already active»</b> — прогон ещё идёт; нажмите ⏹ Stop и дождитесь
сообщения об окончании в логе.</li>
<li><b>Плейлист пропустил программу</b> — в Playlist log указан файл и причина: файла нет,
вместо сценария подставлен плейлист, или JSON повреждён (ожидается список объектов-
шагов).</li>
</ul>
""",
        },
    },
]

HELP_UI_TEXT = {
    "en": {
        "window": "Full guide",
        "heading": "Full guide — every action and feature explained",
        "search": "Search the guide…",
        "close": "Close",
        "empty": "Nothing in the guide matches this search.",
    },
    "ru": {
        "window": "Полное руководство",
        "heading": "Полное руководство — подробно о каждом действии и возможности",
        "search": "Поиск по руководству…",
        "close": "Закрыть",
        "empty": "По этому запросу в руководстве ничего не найдено.",
    },
}


def help_topic_html(topic, lang):
    """HTML раздела: либо готовый текст, либо собранные карточки действий."""
    body = topic.get("body", {}).get(lang)
    if body is None:
        body = help_actions_html(topic["key"], lang)
    return (
        f"<h2 style='color:#5c93d6; margin:0 0 6px 0;'>{topic['title'][lang]}</h2>"
        f"{body}"
    )


def help_topic_plain(topic, lang):
    """Тот же раздел простым текстом — для поиска по руководству."""
    text = topic["title"][lang] + " " + help_topic_html(topic, lang)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    return text.lower()


class HelpDialog(QDialog):
    """Полное руководство: разделы слева, текст справа, поиск и выбор языка."""

    def __init__(self, parent=None, lang="en", topic_key=None):
        super().__init__(parent)
        self._lang = lang if lang in HELP_LANGS else "en"
        self._topic_key = topic_key or HELP_TOPICS[0]["key"]
        scr = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1080, int(scr.width() * 0.8)), min(760, int(scr.height() * 0.85)))

        root = QVBoxLayout(self)

        head = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setStyleSheet("font-weight:bold; color:#cfd6dc;")
        head.addWidget(self.heading)
        head.addStretch()
        self.btn_en = QPushButton("English")
        self.btn_ru = QPushButton("Русский")
        for btn in (self.btn_en, self.btn_ru):
            btn.setCheckable(True)
            btn.setFixedWidth(110)
            head.addWidget(btn)
        root.addLayout(head)

        body = QHBoxLayout()
        side = QWidget()
        side.setFixedWidth(300)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        side_lay.addWidget(self.search)
        self.topic_list = QListWidget()
        self.topic_list.setWordWrap(True)
        self.topic_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_lay.addWidget(self.topic_list, stretch=1)
        body.addWidget(side)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        body.addWidget(self.view, stretch=1)
        root.addLayout(body, stretch=1)

        foot = QHBoxLayout()
        foot.addStretch()
        self.btn_close = QPushButton()
        self.btn_close.clicked.connect(self.accept)
        foot.addWidget(self.btn_close)
        root.addLayout(foot)

        self.btn_en.clicked.connect(lambda: self.set_language("en"))
        self.btn_ru.clicked.connect(lambda: self.set_language("ru"))
        self.topic_list.currentItemChanged.connect(self._on_topic_changed)
        self.search.textChanged.connect(lambda _t: self._reload(keep_topic=True))

        # keep_topic=True — уважаем раздел, с которым диалог открыли (F1 по шагу)
        self._reload(keep_topic=True)

    # ---------- состояние ----------

    def language(self):
        return self._lang

    def set_language(self, lang):
        if lang not in HELP_LANGS or lang == self._lang:
            self._sync_lang_buttons()
            return
        self._lang = lang
        self._reload(keep_topic=True)

    def select_topic(self, topic_key):
        self._topic_key = topic_key
        self._reload(keep_topic=True)

    # ---------- отрисовка ----------

    def _matching_topics(self):
        query = self.search.text().strip().lower()
        if not query:
            return list(HELP_TOPICS)
        return [t for t in HELP_TOPICS if query in help_topic_plain(t, self._lang)]

    def _reload(self, keep_topic=False):
        ui = HELP_UI_TEXT[self._lang]
        self.setWindowTitle(f"{APP_NAME} — {ui['window']}")
        self.heading.setText(ui["heading"])
        self.search.setPlaceholderText(ui["search"])
        self.btn_close.setText(ui["close"])
        self._sync_lang_buttons()

        topics = self._matching_topics()
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        for topic in topics:
            item = QListWidgetItem(topic["title"][self._lang])
            item.setData(Qt.UserRole, topic["key"])
            self.topic_list.addItem(item)
        self.topic_list.blockSignals(False)

        if not topics:
            self.view.setHtml(f"<p style='color:#cfd6dc;'>{ui['empty']}</p>")
            return
        keys = [t["key"] for t in topics]
        key = self._topic_key if (keep_topic and self._topic_key in keys) else keys[0]
        self._topic_key = key
        self.topic_list.setCurrentRow(keys.index(key))   # вызовет _on_topic_changed

    def _sync_lang_buttons(self):
        for btn, lang in ((self.btn_en, "en"), (self.btn_ru, "ru")):
            btn.blockSignals(True)
            btn.setChecked(self._lang == lang)
            btn.blockSignals(False)

    def _on_topic_changed(self, current, _previous=None):
        if current is None:
            return
        self._topic_key = current.data(Qt.UserRole)
        topic = next((t for t in HELP_TOPICS if t["key"] == self._topic_key), None)
        if topic is None:
            return
        self.view.setHtml(
            "<div style='color:#dddddd;'>"
            f"{help_topic_html(topic, self._lang)}"
            "</div>"
        )
        self.view.verticalScrollBar().setValue(0)


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
            "branch_value": "Branch on measured value (numeric condition + proof)",
            "branch_calib": "Branch on gimbal calibration CSV (Az/El tolerance + proof)",
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
            "branch_value": (
                "Reads NUMBERS in the OCR region (Template/area: x,y,w,h) and checks a condition.\n"
                "Condition = one or more 'Label OP Value' clauses joined by AND / OR, e.g.:\n"
                "    Az ML<=0.1 AND El ML<=0.1        (perfect calibration)\n"
                "    abs(Az ML)<=0.1 AND abs(El ML)<=0.1   (tolerance around 0)\n"
                "OPs: <=  >=  <  >  ==  !=   |   wrap a label in abs(...) or |...| for |value|.\n"
                "The first number after each label is read (e.g. 'Az ML: [0.0, 35.99]' → 0.0).\n"
                "• Way A — runs if the condition is TRUE (PASS).  • Way B — if FALSE (FAIL).\n"
                "A PASS/FAIL proof screenshot is always saved to results\\."
            ),
            "branch_calib": (
                "Reads the gimbal calibration CSV in Template/area (e.g. calib.csv, produced "
                "after a calibration run) and finds the boresight offsets:\n"
                "  Az offset = azimuth of peak gain along the El≈0 cut\n"
                "  El offset = elevation of peak gain along the Az≈0 cut\n"
                "Condition = one or more 'Label OP Value' clauses joined by AND / OR, using "
                "labels Az / El, e.g.:\n"
                "    abs(Az)<=0.3 AND abs(El)<=0.3   (calibration within ±0.3°)\n"
                "OPs: <=  >=  <  >  ==  !=   |   wrap a label in abs(...) or |...| for |value|.\n"
                "• Way A — runs if the condition is TRUE (calibration OK).\n"
                "• Way B — runs if FALSE (out of tolerance) — point it at your recalibration "
                "scenario so the gimbal calibrates again with the new tolerance.\n"
                "A PASS/FAIL report (.txt) is saved to results\\; if a '<csv name>_Pattern.png' "
                "file sits next to the CSV, it's copied there too as visual proof."
            ),
        }
        hint = QLabel(help_text.get(action, ""))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#aaa; margin-bottom:8px;")
        lay.addWidget(hint)

        keyword, path_a, path_b = parse_branch_value(action, current_value)

        self._keyword = QLineEdit(keyword)
        if action == "branch_value":
            lay.addWidget(QLabel("Value condition (e.g. Az ML<=0.1 AND El ML<=0.1):"))
            self._keyword.setPlaceholderText("Az ML<=0.1 AND El ML<=0.1")
            lay.addWidget(self._keyword)
        elif action == "branch_calib":
            lay.addWidget(QLabel("Value condition (e.g. abs(Az)<=0.3 AND abs(El)<=0.3):"))
            self._keyword.setPlaceholderText("abs(Az)<=0.3 AND abs(El)<=0.3")
            lay.addWidget(self._keyword)
        elif action != "branch_image":
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
            "A Way can point to a PLAYLIST file (JSON array of scenario paths, or "
            "{\"playlist\": [...]}) — the whole playlist is then driven through in order.\n"
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
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
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
        self._branch_queue = []        # очередь сценариев из ветки-плейлиста (по порядку)
        self._branch_depth = 0         # защита от бесконечных циклов ветвления
        self._preview_index = -1       # строка показанного справа списка, чьи шаги видны слева
        # Правая панель умеет показывать ДВА списка: свой (тот, что запускает
        # «▶ Run list», в т.ч. несохранённый) и «цепочку переходов» — куда увёл
        # прогон шаг goto/branch. Переключение — чипами над списком.
        self._shown_list = "my"        # какой список сейчас в виджете: my|jump
        self._my_paths_stash = []      # свой список, пока в виджете цепочка переходов
        self._jump_done = []           # цели переходов, уже отработанные в цепочке
        self._jump_current = ""        # цель перехода, которая выполняется сейчас
        self._jump_source = ""         # имя файла, который дал этот переход
        self._follow_jumps = True      # автоматически показывать цепочку при переходе

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
        self.left_splitter = left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setHandleWidth(7)
        left_splitter.setChildrenCollapsible(False)

        # Таблица шагов
        table_box = QWidget()
        table_layout = QVBoxLayout(table_box)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        # Переключатель предпросмотра: какой файл сейчас показан слева, и
        # позиция в плейлисте (если это один из его пунктов) с Prev/Next.
        preview_bar = QHBoxLayout()
        self.preview_label = QLabel("📄 (unsaved scenario)")
        self.preview_label.setStyleSheet("color:#cfd6dc; font-weight:bold;")
        preview_bar.addWidget(self.preview_label)
        preview_bar.addStretch()
        self.btn_preview_prev = QPushButton("◀ Prev")
        self.btn_preview_next = QPushButton("Next ▶")
        self.btn_preview_prev.setToolTip(
            "Show the previous program in the playlist (right panel) here, "
            "so you can step through them one by one."
        )
        self.btn_preview_next.setToolTip(
            "Show the next program in the playlist (right panel) here, "
            "so you can step through them one by one."
        )
        self.btn_preview_prev.setEnabled(False)
        self.btn_preview_next.setEnabled(False)
        preview_bar.addWidget(self.btn_preview_prev)
        preview_bar.addWidget(self.btn_preview_next)
        table_layout.addLayout(preview_bar)

        guide_hdr = QHBoxLayout()
        guide_hdr.addWidget(QLabel("Column guide:"))
        self.btn_col_help = QPushButton("Show all columns")
        self.btn_col_help.setToolTip("Open a window with full explanation of every column")
        self.btn_col_help.clicked.connect(self._show_all_column_help)
        guide_hdr.addWidget(self.btn_col_help)
        self.btn_full_help = QPushButton("📖 Full guide (F1)")
        self.btn_full_help.setToolTip(
            "Deep explanation of every action and feature — English / Русский.\n"
            "Opens on the section of the action selected in the table."
        )
        self.btn_full_help.clicked.connect(lambda: self.show_help())
        guide_hdr.addWidget(self.btn_full_help)
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

        # Лог (сворачиваемый — кнопка рядом с заголовком, чтобы освободить место)
        log_box = QWidget()
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_hdr = QHBoxLayout()
        log_hdr.addWidget(QLabel("Execution log:"))
        log_hdr.addStretch()
        self.btn_log_toggle = QPushButton("▸ Show")
        self.btn_log_toggle.setFixedWidth(90)
        self.btn_log_toggle.setToolTip("Collapse/expand the execution log to save space")
        log_hdr.addWidget(self.btn_log_toggle)
        log_layout.addLayout(log_hdr)
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
        self.lbl_list_title = QLabel("Program playlist (JSON):")
        hdr.addWidget(self.lbl_list_title)
        self.play_state = QLabel()
        self.play_state.setFixedSize(14, 14)
        self.play_state.setFrameShape(QFrame.StyledPanel)
        self.play_state.setToolTip("Idle/Stopped/Running")
        hdr.addWidget(self.play_state)
        hdr.addStretch()
        playlist_layout.addLayout(hdr)

        # Чипы-переключатели: свой список ↔ цепочка переходов (goto/branch)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.btn_list_my = QPushButton("▣ My list")
        self.btn_list_my.setCheckable(True)
        self.btn_list_my.setChecked(True)
        self.btn_list_my.setToolTip(
            "Your own playlist — the one '▶ Run list' runs. Kept as-is even when "
            "a run jumps away, so an unsaved list is never lost."
        )
        self.btn_list_jump = QPushButton("↷ Jump chain")
        self.btn_list_jump.setCheckable(True)
        self.btn_list_jump.setEnabled(False)
        self.btn_list_jump.setToolTip(
            "Where a 'Move to another playlist/scenario' (or branch) step took the "
            "run: every scenario it moved through, the current one highlighted."
        )
        chips.addWidget(self.btn_list_my)
        chips.addWidget(self.btn_list_jump)
        chips.addStretch()
        playlist_layout.addLayout(chips)

        self.playlist_list = QListWidget()
        self.playlist_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.playlist_list.setToolTip(
            "Order matters: programs run top → bottom.\n"
            "Click a program to preview its steps on the left "
            "(◀ Prev / Next ▶ there step through the whole list).\n"
            "▶ = running now, ✓ = already finished.\n"
            "When a run jumps elsewhere, the '↷ Jump chain' chip above shows "
            "where it went; '▣ My list' brings this list back."
        )
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

        row_io = QHBoxLayout()
        self.btn_pl_export = QPushButton("💾 Save list…")
        self.btn_pl_export.setToolTip(
            "Save this playlist to a JSON file. Use it as a branch target so a "
            "branch node drives through the whole playlist."
        )
        self.btn_pl_import = QPushButton("📂 Load list…")
        self.btn_pl_import.setToolTip("Load a playlist file (JSON array of scenario paths).")
        row_io.addWidget(self.btn_pl_export)
        row_io.addWidget(self.btn_pl_import)
        playlist_layout.addLayout(row_io)

        row2 = QHBoxLayout()
        self.btn_pl_run = QPushButton("▶ Run list")
        self.btn_pl_stop = QPushButton("⏹ Stop list")
        self.btn_pl_stop.setEnabled(False)
        row2.addWidget(self.btn_pl_run)
        row2.addWidget(self.btn_pl_stop)
        playlist_layout.addLayout(row2)

        pl_log_hdr = QHBoxLayout()
        pl_log_hdr.addWidget(QLabel("Playlist log:"))
        pl_log_hdr.addStretch()
        self.btn_pl_log_toggle = QPushButton("▸ Show")
        self.btn_pl_log_toggle.setFixedWidth(90)
        self.btn_pl_log_toggle.setToolTip("Collapse/expand the playlist log to save space")
        pl_log_hdr.addWidget(self.btn_pl_log_toggle)
        playlist_layout.addLayout(pl_log_hdr)
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
        self.btn_pl_export.clicked.connect(self.playlist_export)
        self.btn_pl_import.clicked.connect(self.playlist_import)
        self.playlist_list.itemClicked.connect(self._on_playlist_item_clicked)
        self.btn_list_my.clicked.connect(self._on_chip_my_list)
        self.btn_list_jump.clicked.connect(self._on_chip_jump_list)
        self.btn_preview_prev.clicked.connect(lambda: self._preview_step(-1))
        self.btn_preview_next.clicked.connect(lambda: self._preview_step(1))
        self.btn_log_toggle.clicked.connect(
            lambda: self.set_execution_log_visible(not self.log_view.isVisible())
        )
        self.btn_pl_log_toggle.clicked.connect(
            lambda: self.set_playlist_log_visible(not self.playlist_log_view.isVisible())
        )

        # горячая клавиша для захвата области
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.capture_region)
        QShortcut(QKeySequence("Ctrl+C"), self.table, activated=self.copy_steps)
        QShortcut(QKeySequence("Ctrl+V"), self.table, activated=self.paste_steps)
        QShortcut(QKeySequence("Insert"), self.table, activated=self.insert_step)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(450)
        self._blink_timer.timeout.connect(self._blink_status)
        self._set_play_state("idle")
        self._sync_list_chips()
        self._build_menu()
        # Логи стартуют свёрнутыми, чтобы не «сжимать» остальной интерфейс —
        # разворачиваются кнопкой ▸ Show рядом с заголовком или через View-меню.
        self.set_execution_log_visible(False)
        self.set_playlist_log_visible(False)

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
        if data is not None and not isinstance(data, dict):
            # Защита от повреждённых/неожиданных данных шага (например, если в
            # JSON затесалась строка вместо объекта шага) — не роняем таблицу.
            data = None

        chk_on = QCheckBox()
        chk_on.setChecked(True if not data else data.get("enabled", True))
        chk_on.stateChanged.connect(self._sync_master_from_rows)
        self._center(chk_on, r, COL_ON)

        combo = QComboBox()
        for key, name in ACTIONS.items():
            combo.addItem(name, key)
        if data:
            action_key = migrate_action(data.get("action", "click_image"))
            idx = list(ACTIONS).index(action_key) if action_key in ACTIONS else 0
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
            elif action == "branch_calib":
                img.setPlaceholderText("path to calibration CSV (Azimuth,Elevation,Gain columns)")
            elif action == "goto_playlist":
                img.setPlaceholderText("path to a playlist or scenario JSON to jump to")
            elif action in BRANCH_ACTIONS:
                img.setPlaceholderText(
                    "template png (image branch) or x,y,w,h OCR region (text branch)"
                )
            else:
                img.setPlaceholderText("path to png (or x,y,w,h for OCR)")

    def _browse(self, edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select template / file", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;CSV (*.csv);;JSON (*.json);;All (*)"
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
                "  • IF word found (+ proof) → JSON A else JSON B\n"
                "  • IF value condition met → JSON A else JSON B\n"
                "  • IF gimbal calib CSV OK (Az/El) → JSON A else JSON B",
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

        if action == "fill_field":
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
        m_view.addSeparator()

        self.act_view_exec_log = QAction("Show execution log", self)
        self.act_view_exec_log.setCheckable(True)
        self.act_view_exec_log.triggered.connect(self.set_execution_log_visible)
        m_view.addAction(self.act_view_exec_log)

        self.act_view_playlist_log = QAction("Show playlist log", self)
        self.act_view_playlist_log.setCheckable(True)
        self.act_view_playlist_log.triggered.connect(self.set_playlist_log_visible)
        m_view.addAction(self.act_view_playlist_log)

        m_help = bar.addMenu("&Help")
        a_guide = QAction("📖 Full guide — English / Русский", self)
        a_guide.setShortcut(QKeySequence("F1"))
        a_guide.setToolTip("Deep explanation of every action and feature, in two languages")
        a_guide.triggered.connect(lambda: self.show_help())
        m_help.addAction(a_guide)
        m_help.addSeparator()

        a_readme = QAction("Open README", self)
        a_readme.triggered.connect(self.open_readme)
        m_help.addAction(a_readme)
        m_help.addSeparator()

        a_whatsnew = QAction("What's new", self)
        a_whatsnew.triggered.connect(lambda: self._show_whatsnew(force=True))
        m_help.addAction(a_whatsnew)

        a_about = QAction(f"About {APP_NAME}", self)
        a_about.triggered.connect(self._show_about)
        m_help.addAction(a_about)

    def toggle_playlist_panel(self, checked):
        if checked:
            self.playlist_box.show()
            total = max(self.main_splitter.width(), 900)
            self.main_splitter.setSizes([int(total * 0.66), int(total * 0.34)])
        else:
            self.playlist_box.hide()

    def set_execution_log_visible(self, visible):
        """Свернуть/развернуть лог выполнения (внутри вертикального сплиттера)."""
        self.log_view.setVisible(visible)
        self.btn_log_toggle.setText("▾ Hide" if visible else "▸ Show")
        self.act_view_exec_log.blockSignals(True)
        self.act_view_exec_log.setChecked(visible)
        self.act_view_exec_log.blockSignals(False)
        total = sum(self.left_splitter.sizes()) or 100
        if visible:
            self.left_splitter.setSizes([int(total * 0.62), int(total * 0.32)])
        else:
            self.left_splitter.setSizes([total - 36, 36])

    def set_playlist_log_visible(self, visible):
        """Свернуть/развернуть лог плейлиста (обычный layout — просто show/hide)."""
        self.playlist_log_view.setVisible(visible)
        self.btn_pl_log_toggle.setText("▾ Hide" if visible else "▸ Show")
        self.act_view_playlist_log.blockSignals(True)
        self.act_view_playlist_log.setChecked(visible)
        self.act_view_playlist_log.blockSignals(False)

    def show_help(self, topic_key=None):
        """Полное руководство (F1). Без темы открываем раздел выбранного действия,
        а язык берём тот, который читали в прошлый раз."""
        if topic_key is None:
            topic_key = self._help_topic_for_selection()
        lang = self._read_state().get("help_lang", "en")
        dlg = HelpDialog(self, lang=lang, topic_key=topic_key)
        dlg.exec()
        if dlg.language() != lang:
            state = self._read_state()
            state["help_lang"] = dlg.language()
            self._write_state(state)

    def _help_topic_for_selection(self):
        """Раздел руководства по действию выделенной строки (если она есть)."""
        row = self.table.currentRow()
        if row < 0:
            return None
        combo = self.table.cellWidget(row, COL_ACTION)
        action = combo.currentData() if combo else None
        return help_action_topic_key(action) if action else None

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

    # ---------- версия / уведомление «что нового» ----------

    def _state_path(self):
        """Небольшой файл рядом с приложением, где хранится последняя показанная версия."""
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "app_state.json")

    def _read_state(self):
        try:
            with open(self._state_path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_state(self, state):
        try:
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"Could not save app state: {e}", "skip")

    def _maybe_show_whatsnew(self):
        """Показывает «What's new» один раз, когда версия сменилась."""
        state = self._read_state()
        if state.get("last_version") != APP_VERSION:
            self._show_whatsnew(force=False)
            state["last_version"] = APP_VERSION
            self._write_state(state)

    def _show_whatsnew(self, force=False):
        """Окно с историей изменений. force=True — вызвано вручную из меню Help."""
        # при автопоказе отображаем только записи новее ранее виденной версии
        entries = CHANGELOG
        if not force:
            last = self._read_state().get("last_version")
            if last:
                entries = [e for e in CHANGELOG if e[0] != last] or CHANGELOG[:1]
        box = QMessageBox(self)
        box.setWindowTitle(f"What's new — {APP_NAME} v{APP_VERSION}")
        box.setTextFormat(Qt.RichText)
        box.setText(f"<b>{APP_NAME}</b> is now at <b>v{APP_VERSION}</b>.")
        box.setInformativeText(changelog_html(entries))
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle(f"About {APP_NAME}")
        box.setTextFormat(Qt.RichText)
        box.setText(
            f"<b>{APP_NAME}</b><br>Version {APP_VERSION}<br><br>"
            "Visual, no-code desktop UI automation builder."
        )
        box.setInformativeText(
            "See <b>Help → What's new</b> for the full change history, "
            "or <b>Help → Open README</b> for full documentation."
        )
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

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

    def _refresh_playlist_labels(self):
        """Пересчитывает подписи ВСЕХ пунктов плейлиста так, чтобы они были
        различимы, даже если несколько файлов называются одинаково (частый
        случай — диалог сохранения сценария всегда предлагает 'scenario.json').
        Подписи пишутся прямо в текст пункта, поэтому и список, и бар
        предпросмотра берут уже готовое уникальное имя из item.text()."""
        count = self.playlist_list.count()
        paths = [self.playlist_list.item(i).data(Qt.UserRole) for i in range(count)]
        labels = make_unique_playlist_labels(paths)
        for i, label in enumerate(labels):
            item = self.playlist_list.item(i)
            item.setText(label or item.text())

    # ---------- два списка в правой панели: свой ↔ цепочка переходов ----------

    def _widget_paths(self):
        """Пути всех пунктов, которые сейчас лежат в виджете списка."""
        return [self.playlist_list.item(i).data(Qt.UserRole)
                for i in range(self.playlist_list.count())]

    def _fill_playlist_widget(self, paths):
        self.playlist_list.clear()
        for p in paths:
            item = QListWidgetItem(os.path.basename(p or ""))
            item.setToolTip(p or "")
            item.setData(Qt.UserRole, p)
            self.playlist_list.addItem(item)
        self._refresh_playlist_labels()

    @staticmethod
    def _clean_label(text):
        """Подпись пункта без пометок прогресса (✓ / ▶)."""
        for prefix in ("✓ ", "▶ "):
            if text.startswith(prefix):
                return text[len(prefix):]
        return text

    def _decorate_progress(self, current_row):
        """Пометки прогресса прямо в списке: ✓ пройдено, ▶ выполняется сейчас.
        Вызывать только сразу после _fill_planlist-заливки, иначе префиксы
        накладываются друг на друга."""
        if current_row < 0:
            return
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if i < current_row:
                item.setText(f"✓ {item.text()}")
                item.setForeground(QColor("#7f8a94"))
            elif i == current_row:
                item.setText(f"▶ {item.text()}")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor("#4caf50"))

    def _mark_my_list_progress(self, row):
        """Подсветить, какая программа своего списка идёт прямо сейчас."""
        self._fill_playlist_widget(self._widget_paths())   # сбрасывает старые пометки
        self._decorate_progress(row)

    def my_list_paths(self):
        """Свой список — независимо от того, что показано в виджете сейчас."""
        if self._shown_list == "jump":
            return list(self._my_paths_stash)
        return self._widget_paths()

    def _jump_chain(self):
        """Цепочка переходов: отработанные + текущий + ещё не запущенные."""
        chain = list(self._jump_done)
        if self._jump_current:
            chain.append(self._jump_current)
        chain += list(self._branch_queue)
        return chain

    def _jump_chain_row(self):
        return len(self._jump_done) if self._jump_current else -1

    def _set_playlist_edit_enabled(self, on):
        """Правка списка разрешена только когда показан свой список."""
        for btn in (self.btn_pl_add, self.btn_pl_remove, self.btn_pl_up,
                    self.btn_pl_down, self.btn_pl_export, self.btn_pl_import):
            btn.setEnabled(on)
        if on:
            self.btn_pl_run.setEnabled(not self._playlist_active and self.runner is None)
        else:
            self.btn_pl_run.setEnabled(False)

    def show_my_list(self):
        """Вернуть в панель свой список (правки и «▶ Run list» — только по нему)."""
        if self._shown_list == "my":
            self._set_playlist_edit_enabled(True)
            self._sync_list_chips()
            return
        self._shown_list = "my"
        self._fill_playlist_widget(self._my_paths_stash)
        self._my_paths_stash = []
        self._preview_index = -1
        self._set_playlist_edit_enabled(True)
        self._sync_list_chips()
        self._update_preview_bar()

    def show_jump_list(self):
        """Показать в панели цепочку переходов и подсветить текущий сценарий."""
        chain = self._jump_chain()
        if not chain:
            return
        if self._shown_list == "my":
            self._my_paths_stash = self._widget_paths()
        self._shown_list = "jump"
        self._fill_playlist_widget(chain)
        row = self._jump_chain_row()
        self._decorate_progress(row)
        self._set_playlist_edit_enabled(False)
        self._preview_index = row
        if row >= 0:
            self.playlist_list.setCurrentRow(row)
            self.playlist_list.scrollToItem(self.playlist_list.item(row))
        self._sync_list_chips()
        self._update_preview_bar()

    def _reset_jump_chain(self):
        """Новый прогон — старая цепочка переходов больше не актуальна."""
        self._jump_done = []
        self._jump_current = ""
        self._jump_source = ""
        self._follow_jumps = True
        self.show_my_list()

    def _enter_jump_target(self, path):
        """Прогон ушёл в другой сценарий/плейлист — отражаем это в панели."""
        if self._jump_current:
            self._jump_done.append(self._jump_current)
        self._jump_current = path
        if self._follow_jumps:
            self.show_jump_list()
        else:
            self._sync_list_chips()

    def _elide(self, text, limit=26):
        return text if len(text) <= limit else text[:limit - 1] + "…"

    def _sync_list_chips(self):
        my_count = len(self.my_list_paths())
        self.btn_list_my.setText(f"▣ My list ({my_count})")
        chain = self._jump_chain()
        row = self._jump_chain_row()
        name = self._jump_source or "Jump chain"
        if chain:
            pos = f"{row + 1}/{len(chain)}" if row >= 0 else str(len(chain))
            self.btn_list_jump.setText(f"↷ {self._elide(name)} ({pos})")
            self.btn_list_jump.setEnabled(True)
        else:
            self.btn_list_jump.setText("↷ Jump chain")
            self.btn_list_jump.setEnabled(False)
        for btn, key in ((self.btn_list_my, "my"), (self.btn_list_jump, "jump")):
            btn.blockSignals(True)
            btn.setChecked(self._shown_list == key)
            btn.blockSignals(False)
        self.lbl_list_title.setText(
            "Program playlist (JSON):" if self._shown_list == "my"
            else f"Jump chain — {self._elide(name, 20)}:"
        )

    def _ensure_my_list_shown(self, what="edit the list"):
        """Правки всегда применяем к своему списку, даже если панель показывала
        цепочку переходов (например, команду позвали из меню File)."""
        if self._shown_list == "my":
            return
        self.show_my_list()
        self._follow_jumps = False
        self._playlist_log(f"Switched back to your list to {what}.", "info")

    def _on_chip_my_list(self):
        # ручное переключение на свой список = «не перетаскивай меня обратно»
        if self._jump_chain():
            self._follow_jumps = False
        self.show_my_list()

    def _on_chip_jump_list(self):
        self._follow_jumps = True
        self.show_jump_list()

    def playlist_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add programs to playlist", "", "JSON (*.json)")
        if not files:
            return
        self._ensure_my_list_shown("add programs")
        for p in files:
            item = QListWidgetItem(os.path.basename(p))
            item.setToolTip(p)
            item.setData(Qt.UserRole, p)
            self.playlist_list.addItem(item)
        self._refresh_playlist_labels()
        self._playlist_log(f"Added {len(files)} program(s).", "ok")
        self._update_preview_bar()

    def playlist_remove_selected(self):
        if self._shown_list != "my":
            self._playlist_log(
                "The jump chain is a read-only view — switch to '▣ My list' to edit.", "err")
            return
        rows = sorted({i.row() for i in self.playlist_list.selectedIndexes()}, reverse=True)
        for r in rows:
            self.playlist_list.takeItem(r)
        if rows:
            self._refresh_playlist_labels()
            self._playlist_log(f"Removed {len(rows)} program(s).", "ok")
            if self._preview_index >= self.playlist_list.count():
                self._preview_index = -1
            self._update_preview_bar()

    def playlist_export(self):
        """Сохраняет текущий плейлист в файл (JSON-массив путей) для ветвления-в-плейлист."""
        my_paths = [p for p in self.my_list_paths() if p]
        if not my_paths:
            self._playlist_log("Playlist is empty — nothing to save.", "err")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save playlist", "playlist.json", "JSON (*.json)")
        if not path:
            return
        base = os.path.dirname(os.path.abspath(path))
        paths = [path_for_scenario_storage(p, base) for p in my_paths]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"playlist": paths}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._playlist_log(f"Failed to save playlist: {e}", "err")
            return
        self._playlist_log(f"Playlist saved ({len(paths)} program(s)): {os.path.basename(path)}", "ok")

    def playlist_import(self):
        """Загружает плейлист-файл в панель (заменяет текущий список)."""
        path, _ = QFileDialog.getOpenFileName(self, "Load playlist", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._playlist_log(f"Failed to load playlist: {e}", "err")
            return
        if not is_playlist_data(data):
            self._playlist_log(
                f"'{os.path.basename(path)}' is a scenario, not a playlist. "
                "Use ➕ Add JSON for single scenarios.", "err")
            return
        base = os.path.dirname(os.path.abspath(path))
        paths = playlist_paths_from_data(data, base)
        self._ensure_my_list_shown("load a playlist")
        self._fill_playlist_widget(paths)
        self._preview_index = -1
        self._update_preview_bar()
        self._playlist_log(f"Loaded playlist ({len(paths)} program(s)): {os.path.basename(path)}", "ok")

    def playlist_move(self, direction):
        if self._shown_list != "my":
            self._playlist_log(
                "The jump chain is a read-only view — switch to '▣ My list' to reorder.", "err")
            return
        row = self.playlist_list.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.playlist_list.count():
            return
        item = self.playlist_list.takeItem(row)
        self.playlist_list.insertItem(new_row, item)
        self.playlist_list.setCurrentRow(new_row)
        self._update_preview_bar()

    # ---------- переключатель предпросмотра (слева) ----------

    def _on_playlist_item_clicked(self, item):
        """Клик по пункту плейлиста (справа) — показать его шаги слева."""
        self._preview_playlist_at(self.playlist_list.row(item))

    def _preview_step(self, direction):
        """Кнопки ◀ Prev / Next ▶ — пройтись по плейлисту по одному пункту."""
        count = self.playlist_list.count()
        if count == 0:
            return
        if not (0 <= self._preview_index < count):
            row = 0 if direction > 0 else count - 1
        else:
            row = max(0, min(self._preview_index + direction, count - 1))
        self._preview_playlist_at(row)

    def _preview_playlist_at(self, row):
        """Грузит шаги пункта плейлиста #row в левую таблицу для просмотра/правки."""
        count = self.playlist_list.count()
        if row < 0 or row >= count:
            return
        item = self.playlist_list.item(row)
        path = item.data(Qt.UserRole)
        name = self._clean_label(item.text())
        if not path or not os.path.isfile(path):
            self._playlist_log(f"Cannot preview '{name}': file not found.", "err")
            return
        if not self._load_scenario_file(path, for_playlist=False):
            return
        self._preview_index = row
        self.playlist_list.setCurrentRow(row)
        self._update_preview_bar()

    def _update_preview_bar(self):
        """Обновляет надпись/кнопки над таблицей: какой файл сейчас показан."""
        count = self.playlist_list.count()
        if 0 <= self._preview_index < count:
            item = self.playlist_list.item(self._preview_index)
            where = "in jump chain" if self._shown_list == "jump" else "in playlist"
            icon = "↷" if self._shown_list == "jump" else "📄"
            self.preview_label.setText(
                f"{icon} {self._clean_label(item.text())}   —   "
                f"[{self._preview_index + 1}/{count} {where}]"
            )
            self.preview_label.setToolTip(item.data(Qt.UserRole) or "")
        elif self._scenario_path:
            self.preview_label.setText(f"📄 {os.path.basename(self._scenario_path)}")
            self.preview_label.setToolTip(self._scenario_path)
        else:
            self.preview_label.setText("📄 (unsaved scenario)")
            self.preview_label.setToolTip("")
        self.btn_preview_prev.setEnabled(count > 0)
        self.btn_preview_next.setEnabled(count > 0)
        self._sync_list_chips()

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
        if is_playlist_data(steps):
            msg = (f"'{os.path.basename(path)}' is a playlist file, not a scenario — "
                   "it can be used as a branch target, but not loaded as steps.")
            self._playlist_log(msg, "err") if for_playlist else self._log(msg, "err")
            return False
        if not isinstance(steps, list) or not all(isinstance(st, dict) for st in steps):
            msg = (f"'{os.path.basename(path)}' has an unexpected/corrupted format "
                   "(expected a list of step objects) — not loaded.")
            self._playlist_log(msg, "err") if for_playlist else self._log(msg, "err")
            return False
        self.table.setRowCount(0)
        try:
            for st in steps:
                self.add_step(st)
        except Exception as e:
            msg = f"Failed to load steps from '{os.path.basename(path)}': {e}"
            self._playlist_log(msg, "err") if for_playlist else self._log(msg, "err")
            self.table.setRowCount(0)
            return False
        self._scenario_path = os.path.abspath(path)
        if for_playlist:
            self._playlist_log(f"Loaded {len(steps)} step(s): {os.path.basename(path)}", "ok")
        else:
            self._log(f"Loaded steps: {len(steps)} from {path}", "ok")
        self._warn_about_retired_steps(path, steps, for_playlist)
        return True

    def _warn_about_retired_steps(self, path, steps, for_playlist=False):
        """Сообщаем про шаги с убранными действиями: они переведены на клик по
        шаблону, и для них нужно снять шаблон (иначе шаг упадёт при прогоне)."""
        found = {}
        for number, st in enumerate(steps, 1):
            action = st.get("action")
            if action in RETIRED_ACTIONS:
                found.setdefault(action, []).append(number)
        for action, numbers in found.items():
            new_key, old_label = RETIRED_ACTIONS[action]
            rows = ", ".join(str(n) for n in numbers)
            msg = (f"'{os.path.basename(path)}': step(s) {rows} used '{old_label}', "
                   f"which was removed → switched to '{ACTIONS[new_key]}'. "
                   "Capture a template for them with 📷 Capture.")
            self._playlist_log(msg, "err") if for_playlist else self._log(msg, "err")

    def playlist_run(self):
        if self.runner:
            self._playlist_log("Runner is already active.", "err")
            return
        # запускаем всегда СВОЙ список, даже если панель показывает цепочку переходов
        self._reset_jump_chain()
        if self.playlist_list.count() == 0:
            self._playlist_log("Playlist is empty. Add JSON programs first.", "err")
            return
        self._playlist_active = True
        self._playlist_index = 0
        self._branch_depth = 0
        self._branch_queue = []
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
        # следующая программа списка — цепочка переходов предыдущей закрыта
        self._reset_jump_chain()
        if self._playlist_index >= self.playlist_list.count():
            self._playlist_log("Playlist completed successfully.", "ok")
            self._playlist_active = False
            self._release_runner()
            self.btn_pl_run.setEnabled(True)
            self.btn_pl_stop.setEnabled(False)
            self._set_play_state("stopped")
            return
        item = self.playlist_list.item(self._playlist_index)
        path = item.data(Qt.UserRole)
        name = self._clean_label(item.text()) or f"item #{self._playlist_index + 1}"
        if not self._load_scenario_file(path, for_playlist=True):
            self._playlist_log(f"Skipping invalid scenario: {name}", "err")
            self._playlist_index += 1
            self._run_playlist_item()
            return
        self._preview_index = self._playlist_index
        if self._shown_list == "my":
            self._mark_my_list_progress(self._playlist_index)
        self.playlist_list.setCurrentRow(self._playlist_index)
        self.playlist_list.scrollToItem(self.playlist_list.item(self._playlist_index))
        self._update_preview_bar()
        self._playlist_log(f"Running [{self._playlist_index + 1}/{self.playlist_list.count()}]: {name}", "info")
        self.run_scenario()

    def playlist_stop(self):
        self._playlist_active = False
        self._playlist_index = -1
        self._pending_branch = None
        self._branch_queue = []
        self.btn_pl_run.setEnabled(True)
        self.btn_pl_stop.setEnabled(False)
        self._set_play_state("stopped")
        if self.runner:
            self.runner.stop()
        self._playlist_log("Playlist stop requested.", "err")

    # ---------- запуск / стоп ----------

    def _release_runner(self):
        """Отпустить закончившийся поток. Без этого self.runner остаётся занятым
        навсегда и «▶ Run list» вечно отвечает 'Runner is already active'."""
        runner, self.runner = self.runner, None
        if runner is not None:
            runner.wait(3000)      # run() уже отработал — ждём только выхода потока
        if self._shown_list == "my":
            self.btn_pl_run.setEnabled(not self._playlist_active)

    def run_scenario(self, from_branch=False):
        self._release_runner()      # предыдущий прогон уже закончился — отпускаем поток
        steps = self._all_steps()
        if not steps:
            self._log("No steps to execute.", "err")
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return
        if not from_branch:
            self._branch_depth = 0
            self._branch_queue = []
            self._reset_jump_chain()
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
        self.btn_pl_run.setEnabled(False)
        self.runner.start()

    def stop_scenario(self):
        if self._playlist_active:
            self.playlist_stop()
            return
        self._pending_branch = None
        self._branch_queue = []
        if self.runner:
            self.runner.stop()

    def _on_branch_request(self, path):
        """Runner попросил условный переход: запомним путь до конца прогона."""
        self._pending_branch = path

    def _expand_branch_target(self, path):
        """Разворачивает цель ветки в список сценариев.

        Обычный сценарий → [path]. Плейлист-файл (список путей) → все его сценарии
        по порядку, чтобы ветка «проезжала» по плейлисту, а не грузила один JSON.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"Branch target unreadable ({os.path.basename(path)}): {e}", "err")
            return [path]        # пусть обычная загрузка сообщит об ошибке
        if is_playlist_data(data):
            base = os.path.dirname(os.path.abspath(path))
            paths = playlist_paths_from_data(data, base)
            if not paths:
                self._log(f"Playlist '{os.path.basename(path)}' is empty.", "err")
            else:
                self._log(
                    f"↷ Branch into playlist '{os.path.basename(path)}' "
                    f"— {len(paths)} program(s).", "info")
                self._playlist_log(
                    f"↷ Entering playlist '{os.path.basename(path)}' "
                    f"({len(paths)} program(s))", "info")
            return paths
        return [path]

    def _on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # ветка выбрала цель: сценарий или плейлист-файл → раскрываем в очередь
        pending, self._pending_branch = self._pending_branch, None
        if pending:
            self._branch_queue = self._expand_branch_target(pending) + self._branch_queue
            self._jump_source = os.path.basename(pending)

        # проезжаем по очереди веток (сценарий за сценарием), затем — по плейлисту
        while self._branch_queue:
            self._branch_depth += 1
            if self._branch_depth > MAX_BRANCH_DEPTH:
                self._log(
                    f"Branch chain too deep ({MAX_BRANCH_DEPTH}) — possible loop. Stopping.",
                    "err",
                )
                self._branch_queue = []
                if self._playlist_active:
                    self._playlist_active = False
                    self._playlist_index = -1
                    self.btn_pl_stop.setEnabled(False)
                    self._set_play_state("stopped")
                self._release_runner()
                self.btn_pl_run.setEnabled(True)
                self._sync_list_chips()
                return
            next_path = self._branch_queue.pop(0)
            name = os.path.basename(next_path)
            self._playlist_log(f"↷ Moving to → {name}", "info")
            if self._load_scenario_file(next_path, for_playlist=self._playlist_active):
                # правая панель «едет» вместе с прогоном: цепочка переходов
                # показывается и подсвечивает сценарий, который пошёл сейчас
                self._enter_jump_target(next_path)
                self._log(f"↷ Branch: running {name}", "info")
                self.run_scenario(from_branch=True)
                return          # остальное продолжится после конца этого прогона
            # не удалось загрузить — попробуем следующий в очереди
            self._log(f"Branch target failed to load: {next_path}", "err")
            self._playlist_log(f"Cannot load '{name}' — skipped.", "err")

        if self._playlist_active:
            self._playlist_log("Program finished.", "ok")
            self._playlist_index += 1
            self._run_playlist_item()
            return

        # одиночный прогон (не по списку) закончился — движок свободен
        self._release_runner()
        self._sync_list_chips()

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
        self._preview_index = -1
        self._update_preview_bar()
        self._log(f"Scenario saved: {path}", "ok")

    def load_scenario(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load scenario", "", "JSON (*.json)")
        if not path:
            return
        self._preview_index = -1
        self._load_scenario_file(path, for_playlist=False)
        self._update_preview_bar()


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
QPushButton:checked { background-color: #35506f; border-color: #5c93d6; color: #ffffff; }
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
    # уведомление «что нового» показываем после появления окна
    QTimer.singleShot(400, win._maybe_show_whatsnew)
    sys.exit(app.exec())