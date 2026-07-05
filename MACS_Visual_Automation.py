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
    QDoubleSpinBox, QSplitter, QDialog, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint
from PySide6.QtGui import QColor, QImage, QPixmap, QPainter, QPen, QShortcut, QKeySequence

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
    }


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
    "key":                 "Press key",
    "type_text":           "Type text",
    "ui_delete":           "Delete on-screen item (Delete key)",
    "ocr_check":           "OCR check (search for word)",
    "verify_text":         "Verify text & save proof (pass/fail)",
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
    "key":                 "e.g. enter / tab / f5",
    "type_text":           "text or file path",
    "ui_delete":           "empty, or 'enter' to confirm the dialog",
    "ocr_check":           "word to find, e.g. pass",
    "verify_text":         "keyword to expect, e.g. pass",
    "screenshot":          "name, e.g. unit_{serial}\\log.png",
    "select_target":       "path to select, e.g. results\\unit_{serial}",
    "create_folder":       "path, e.g. results\\unit_{serial}",
    "rename_folder":       "new name/path (selected first), e.g. unit_{serial}_done",
    "delete_folder":       "path, or empty = use selected",
    "pause":               "seconds, e.g. 3",
}

# Колонки таблицы
COL_ON, COL_ACTION, COL_IMAGE, COL_BROWSE, COL_PREVIEW, COL_VALUE, COL_TIMEOUT, COL_FIND, COL_STOP = range(9)


# ============================================================================
# ДВИЖОК ВЫПОЛНЕНИЯ (в отдельном потоке, чтобы GUI не подвисал)
# ============================================================================

class Runner(QThread):
    log = Signal(str, str)        # (текст, уровень: info/ok/err/skip)
    finished_all = Signal()
    serial_update = Signal(str)   # следующий серийный номер (чтобы прогон продолжался)

    def __init__(self, steps, start_delay, own_title="AutoBuilder",
                 serial_start="0001"):
        super().__init__()
        self.steps = steps
        self.start_delay = start_delay
        self.own_title = own_title      # заголовок нашего окна (чтобы прятать его при поиске)
        self._serial = str(serial_start) or "0001"   # серийник (буквы+цифры, до 16 символов)
        self._selected = ""             # выбранная папка/файл (для delete/rename)
        self._stop = False
        self._own_minimized = False

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
        finally:
            # если прятали своё окно ради «чистого рабочего стола» — вернём его
            self._restore_own()

        self.serial_update.emit(self._serial)   # запомнить, где остановился счётчик
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

        elif a == "key":
            pyautogui.press(val)
            self.log.emit(f"[{i}] ✓ {label}: {val}", "ok")

        elif a == "type_text":
            text = self._expand(val)
            pyautogui.write(text, interval=0.01)
            self.log.emit(f"[{i}] ✓ {label}: {text}", "ok")

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
        cpx, cpy = meta.get("click_point", [tw0 // 2, th0 // 2])
        cpx = max(0, min(int(cpx), tw0 - 1))
        cpy = max(0, min(int(cpy), th0 - 1))

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
    """Рисуем на захваченном шаблоне: compare, exclude, click."""

    def __init__(self, image_path):
        super().__init__()
        self._pix = QPixmap(image_path)
        self._img_w = max(self._pix.width(), 1)
        self._img_h = max(self._pix.height(), 1)
        self._mode = "compare"
        self._compare = QRect(0, 0, self._img_w, self._img_h)
        self._excludes = []
        self._click = QPoint(self._img_w // 2, self._img_h // 2)
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
        self.update()

    def get_meta(self):
        c = self._compare
        return {
            "compare_rect": [c.x(), c.y(), c.width(), c.height()],
            "exclude_rects": [[r.x(), r.y(), r.width(), r.height()] for r in self._excludes],
            "click_point": [self._click.x(), self._click.y()],
        }

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

        # exclude — красная штриховка
        for rect in self._excludes:
            dr = self._img_to_disp_rect(rect)
            p.fillRect(dr, QColor(255, 60, 60, 90))
            p.setPen(QPen(QColor("#ff5555"), 2, Qt.DashLine))
            p.drawRect(dr)

        # compare — зелёная рамка
        dr = self._img_to_disp_rect(self._compare)
        p.fillRect(dr, QColor(0, 200, 80, 35))
        p.setPen(QPen(QColor("#00e676"), 2))
        p.drawRect(dr)

        # rubber band while dragging
        if not self._rubber.isNull() and self._mode in ("compare", "exclude"):
            p.setPen(QPen(QColor("#00c8ff"), 2, Qt.DashLine))
            p.drawRect(self._rubber)

        # click — синий крест
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
                self.update()
            return
        self._origin = e.pos()
        self._rubber = QRect(self._origin, self._origin)

    def mouseMoveEvent(self, e):
        if self._origin is not None and self._mode in ("compare", "exclude"):
            self._rubber = QRect(self._origin, e.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._origin is None:
            return
        if self._mode not in ("compare", "exclude"):
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
        if x2 - x1 < 3 or y2 - y1 < 3:
            self.update()
            return
        rect = QRect(x1, y1, x2 - x1, y2 - y1)
        if self._mode == "compare":
            self._compare = rect
        else:
            self._excludes.append(rect)
        self.update()


class TemplateEditorDialog(QDialog):
    """После захвата: задать compare / exclude / click для шаблона."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self._path = image_path
        self.setWindowTitle("Template regions — compare / exclude / click")
        self.setMinimumSize(720, 520)

        root = QVBoxLayout(self)
        hint = QLabel(
            "<b>Green</b> = area used to find this on screen. "
            "<b>Red</b> = ignored (e.g. changing numbers). "
            "<b>Blue cross</b> = where to click."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        modes = QHBoxLayout()
        self._btn_compare = QPushButton("1. Compare (match)")
        self._btn_exclude = QPushButton("2. Exclude (ignore)")
        self._btn_click = QPushButton("3. Click point")
        for btn, mode in ((self._btn_compare, "compare"),
                          (self._btn_exclude, "exclude"),
                          (self._btn_click, "click")):
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            modes.addWidget(btn)
        root.addLayout(modes)

        self._canvas = TemplateEditorCanvas(image_path)
        meta = load_template_meta(image_path)
        if meta:
            self._canvas.load_meta(meta)
        root.addWidget(self._canvas, stretch=1)

        help_l = QLabel(
            "Compare: drag a rectangle. Exclude: drag one or more rectangles "
            "over changing fields. Click: single-click the button/target."
        )
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
        self._btn_click.setChecked(mode == "click")

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
            meta_lbl = QLabel(
                f"Compare: {c}  |  Excludes: {n_ex}  |  Click: {ck}"
            )
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
# ГЛАВНОЕ ОКНО
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoBuilder — automation builder")
        self.setMinimumSize(560, 380)
        # компактный старт ~половина экрана (можно развернуть на весь экран)
        scr = QApplication.primaryScreen().availableGeometry()
        w, h = int(scr.width() * 0.5), int(scr.height() * 0.6)
        self.resize(w, h)
        self.move(scr.x() + (scr.width() - w) // 2, scr.y() + (scr.height() - h) // 2)
        self.runner = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Верхняя панель управления ---
        top = QHBoxLayout()
        self.btn_run   = QPushButton("▶ Run")
        self.btn_stop  = QPushButton("⏹ Stop")
        self.btn_add   = QPushButton("➕ Step")
        self.btn_del   = QPushButton("🗑 Delete")
        self.btn_up    = QPushButton("↑")
        self.btn_down  = QPushButton("↓")
        self.btn_snip  = QPushButton("📷 Capture")
        self.btn_snip.setToolTip("Capture a screen region for the selected step (Ctrl+Shift+S)")
        self.btn_regions = QPushButton("✏ Regions")
        self.btn_regions.setToolTip(
            "Edit compare / exclude / click regions for the selected step's template"
        )
        self.btn_save  = QPushButton("💾 Save")
        self.btn_load  = QPushButton("📂 Load")
        self.btn_stop.setEnabled(False)

        top.addWidget(self.btn_run)
        top.addWidget(self.btn_stop)
        top.addSpacing(20)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_del)
        top.addWidget(self.btn_up)
        top.addWidget(self.btn_down)
        top.addSpacing(20)
        top.addWidget(self.btn_snip)
        top.addWidget(self.btn_regions)
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

        # --- Разделитель: таблица сверху, лог снизу ---
        splitter = QSplitter(Qt.Vertical)

        # Таблица шагов
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["On", "Action", "Template / area", "…", "Preview",
             "Value", "Timeout", "Find win", "Stop"]
        )
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
        self.table.horizontalHeaderItem(COL_PREVIEW).setToolTip(
            "Thumbnail of the step's template image. Click a thumbnail to view "
            "it full size (helps tell steps apart)."
        )
        # строки повыше, чтобы миниатюры были видны
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeaderItem(COL_FIND).setToolTip(
            "Search for the window/element: if the target isn't visible, cycle "
            "through open windows (Alt+Tab style) to find it. Default off."
        )
        splitter.addWidget(self.table)

        # Лог
        log_box = QWidget()
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.addWidget(QLabel("Execution log:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        log_layout.addWidget(self.log_view)
        splitter.addWidget(log_box)

        splitter.setSizes([400, 250])
        root.addWidget(splitter)

        # --- Сигналы ---
        self.btn_add.clicked.connect(lambda: self.add_step())
        self.btn_del.clicked.connect(self.del_step)
        self.btn_up.clicked.connect(lambda: self.move_step(-1))
        self.btn_down.clicked.connect(lambda: self.move_step(1))
        self.btn_run.clicked.connect(self.run_scenario)
        self.btn_stop.clicked.connect(self.stop_scenario)
        self.btn_save.clicked.connect(self.save_scenario)
        self.btn_load.clicked.connect(self.load_scenario)
        self.btn_snip.clicked.connect(self.capture_region)
        self.btn_regions.clicked.connect(self.edit_template_regions)

        # горячая клавиша для захвата области
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.capture_region)

        if not AUTOMATION_OK:
            self._log(f"⚠ Automation libraries not found: {_IMPORT_ERR}", "err")
            self._log("The GUI works, but running scenarios is unavailable until installed.", "info")
        elif not TESSERACT_OK:
            self._log(f"⚠ {TESSERACT_HINT}", "err")
            self._log("All actions work except OCR check / Verify text until Tesseract is installed.", "info")

        # стартовый пример-шаг
        self.add_step()

    # ---------- работа с таблицей ----------

    def add_step(self, data=None):
        r = self.table.rowCount()
        self.table.insertRow(r)

        chk_on = QCheckBox()
        chk_on.setChecked(True if not data else data.get("enabled", True))
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
        # захватываем сам QLineEdit, а не индекс строки (индекс "протухает" после удаления/перемещения)
        browse.clicked.connect(lambda _=False, edit=img: self._browse(edit))
        self.table.setCellWidget(r, COL_BROWSE, browse)

        # миниатюра-превью шаблона (обновляется при смене пути, клик = полный размер)
        thumb = ThumbLabel()
        thumb.clicked.connect(lambda t=thumb: self._open_preview(t._path))
        img.textChanged.connect(lambda text, t=thumb: t.set_image(text))
        thumb.set_image(img.text())
        self._center(thumb, r, COL_PREVIEW)

        val = QLineEdit(data.get("value", "") if data else "")
        self.table.setCellWidget(r, COL_VALUE, val)

        # подсказку обновляем по ссылкам на виджеты, а не по индексу строки
        combo.currentIndexChanged.connect(lambda _=0, c=combo, v=val: self._update_hint(c, v))

        to = QSpinBox()
        to.setRange(1, 600)
        to.setValue(data.get("timeout", 10) if data else 10)
        self.table.setCellWidget(r, COL_TIMEOUT, to)

        chk_find = QCheckBox()
        chk_find.setChecked(data.get("find_window", False) if data else False)
        chk_find.setToolTip("Search for the window/element (cycle windows if not visible)")
        self._center(chk_find, r, COL_FIND)

        chk_stop = QCheckBox()
        chk_stop.setChecked(data.get("stop_on_error", True) if data else True)
        self._center(chk_stop, r, COL_STOP)

        self._update_hint(combo, val)

    def _center(self, widget, row, col):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.addWidget(widget)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, col, wrap)

    def _checkbox_at(self, row, col):
        wrap = self.table.cellWidget(row, col)
        return wrap.findChild(QCheckBox)

    def _update_hint(self, combo, val):
        if not combo or not val:
            return
        action = combo.currentData()
        val.setPlaceholderText(VALUE_HINT.get(action, ""))

    def _browse(self, edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select template", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All (*)"
        )
        if path:
            edit.setText(path)

    def _open_preview(self, path):
        """Показ шаблона в полном размере по клику на миниатюре."""
        if not path or not os.path.isfile(path):
            self._log("No image to preview for this step.", "skip")
            return
        dlg = ImagePreviewDialog(path, self, on_edit=self._open_template_editor)
        dlg.exec()

    def _open_template_editor(self, path):
        """Открыть редактор compare/exclude/click. True если сохранено."""
        if not path or not os.path.isfile(path):
            return False
        dlg = TemplateEditorDialog(path, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.save_meta()
            self._log(f"Template regions saved: {os.path.basename(path)}", "ok")
            return True
        return False

    def edit_template_regions(self):
        row = self.table.currentRow()
        if row < 0:
            self._log("Select a step first.", "err")
            return
        action = self.table.cellWidget(row, COL_ACTION).currentData()
        if action not in TEMPLATE_ACTIONS:
            self._log("Regions apply only to template steps (click/wait on template).", "err")
            return
        path = self.table.cellWidget(row, COL_IMAGE).text().strip()
        if not path or not os.path.isfile(path):
            self._log("Capture or browse a template image for this step first.", "err")
            return
        self._open_template_editor(path)
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

        elif action in ("ocr_check", "verify_text"):
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
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

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

    # ---------- запуск / стоп ----------

    def run_scenario(self):
        steps = self._all_steps()
        if not steps:
            self._log("No steps to execute.", "err")
            return
        self.log_view.clear()
        self._log(f"Running scenario: {len(steps)} step(s)", "info")
        self.runner = Runner(
            steps, self.spin_delay.value(),
            own_title=self.windowTitle(),
            serial_start=self.edit_serial.text().strip() or "0001",
        )
        self.runner.log.connect(self._log)
        self.runner.serial_update.connect(self.edit_serial.setText)
        self.runner.finished_all.connect(self._on_finished)
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.runner.start()

    def stop_scenario(self):
        if self.runner:
            self.runner.stop()

    def _on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

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
        self._log(f"Scenario saved: {path}", "ok")

    def load_scenario(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load scenario", "", "JSON (*.json)")
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            steps = json.load(f)
        self.table.setRowCount(0)
        for st in steps:
            self.add_step(st)
        self._log(f"Loaded steps: {len(steps)} from {path}", "ok")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())