"""Диагностика поиска шаблона на текущем экране.

Запуск:
    py test_match.py templates\\tpl_1782932243.png

Показывает лучший счёт и масштаб, где нашёлся шаблон, и сохраняет
match_debug.png с рамкой найденного места (для проверки глазами).
"""
import sys
import ctypes

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import cv2
import numpy as np
import mss
from PIL import Image

SCALES = (1.0, 0.9, 1.1, 0.8, 1.25, 0.75, 0.67, 1.5, 0.6, 0.5, 2.0)


def grab_all():
    factory = getattr(mss, "MSS", None) or mss.mss
    with factory() as sct:
        mon = sct.monitors[0]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img, mon["left"], mon["top"]


def main(template_path):
    templ = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if templ is None:
        print("cannot read:", template_path)
        return
    templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    templ_edge = cv2.Canny(templ_gray, 50, 150)
    th0, tw0 = templ_gray.shape[:2]
    print(f"template: {template_path}  size={tw0}x{th0}")

    img, left, top = grab_all()
    scene_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    scene = cv2.cvtColor(scene_bgr, cv2.COLOR_BGR2GRAY)
    scene_edge = cv2.Canny(scene, 50, 150)
    sh, sw = scene.shape[:2]
    print(f"screen grab: {sw}x{sh}  (virtual origin {left},{top})")

    best = (-1.0, 1.0, (0, 0), (tw0, th0))
    for scale in SCALES:
        tw, th = int(tw0 * scale), int(th0 * scale)
        if tw < 8 or th < 8 or th > sh or tw > sw:
            continue
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        tg = cv2.resize(templ_gray, (tw, th), interpolation=interp)
        _, gv, _, gloc = cv2.minMaxLoc(cv2.matchTemplate(scene, tg, cv2.TM_CCOEFF_NORMED))
        te = cv2.resize(templ_edge, (tw, th), interpolation=interp)
        _, ev, _, eloc = cv2.minMaxLoc(cv2.matchTemplate(scene_edge, te, cv2.TM_CCOEFF_NORMED))
        maxv, maxloc = (gv, gloc) if gv >= ev else (ev, eloc)
        print(f"  scale {scale:<4}  gray {gv:.3f}  edge {ev:.3f}  -> {maxv:.3f}  at {maxloc}")
        if maxv > best[0]:
            best = (maxv, scale, maxloc, (tw, th))

    score, scale, loc, (tw, th) = best
    print(f"\nBEST: score {score:.3f} at scale {scale}, top-left {loc}, size {tw}x{th}")
    print("Threshold used by app: 0.80  ->", "MATCH" if score >= 0.80 else "NO MATCH")

    cv2.rectangle(scene_bgr, loc, (loc[0] + tw, loc[1] + th), (0, 0, 255), 3)
    cv2.imwrite("match_debug.png", scene_bgr)
    print("saved: match_debug.png (red box = best guess)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: py test_match.py <template.png>")
    else:
        main(sys.argv[1])
