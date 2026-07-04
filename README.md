# MACS Visual Automation

A visual, no-code **desktop UI automation builder**. You build a scenario as a
list of steps in a table, then press **▶ Run** and the app drives the mouse and
keyboard to reproduce those steps on screen — clicking on-screen images it finds
via computer vision, typing text, pressing keys, reading text with OCR, taking
screenshots, and managing result folders.

It is designed for repetitive UI workflows such as manufacturing/test-station
tasks (hence *MACS*): open a program, click through a sequence, verify a
**PASS/FAIL** result on screen, and archive proof screenshots into per-unit
folders that are numbered by an auto-incrementing serial number.

---

## Key features

- **Table-based scenario editor** — each row is one step; no scripting required.
- **Image (template) matching** — click/wait for a UI element by a captured
  picture of it, not fixed coordinates. Matching is:
  - **multi-scale** (tries many zoom levels → robust to DPI / resolution changes),
  - **grayscale + edge (Canny)** based → robust to theme, highlight and color changes,
  - **multi-monitor aware** (searches the whole virtual desktop).
- **Built-in region capture** — press **📷 Capture** (or `Ctrl+Shift+S`) to freeze
  the screen and drag a rectangle. Depending on the step type it saves a PNG
  template, an OCR region, or a click coordinate.
- **Template thumbnails** — each step row shows a small preview of its template
  image so you can tell steps apart at a glance; click a thumbnail to view it
  full size.
- **OCR** via Tesseract — check that a word appears on screen, or verify a
  **PASS/FAIL** keyword and automatically save a proof screenshot.
- **"Find window" mode** — if a target isn't currently visible, the app cycles
  through open windows (Alt+Tab style) to locate it.
- **Serial number tokens** — use `{serial}`, `{date}`, `{time}`, `{ts}` in paths
  and text; `{serial}` auto-increments and continues across runs.
- **File/folder actions** — create, rename, delete, and select folders (with a
  safety guard against deleting drive roots).
- **Save / load scenarios** as JSON, so each program/workflow is its own file.
- **Live color-coded log** (green OK / red error / gray skipped).
- **Runs in a background thread** so the GUI never freezes; **⏹ Stop** any time.
- **Degrades gracefully** — the GUI still opens if automation libraries or the
  Tesseract engine are missing; it just disables the affected actions and tells
  you what to install.

---

## Requirements

- **OS:** Windows (uses per-monitor DPI awareness and `PyGetWindow` window
  control; the "Find window" feature is Windows-oriented).
- **Python:** 3.10+ recommended.
- **Python packages:** see [`requirements.txt`](requirements.txt).
- **Tesseract OCR engine** (only needed for *OCR check* / *Verify text* steps) —
  this is a native program, **not** a pip package.

---

## Installation

```bash
# 1) (recommended) create & activate a virtual environment
python -m venv venv
venv\Scripts\activate            # Windows PowerShell / CMD

# 2) install Python dependencies
pip install -r requirements.txt
```

### Installing the Tesseract engine (for OCR steps)

Download and install a Tesseract build (e.g. the **UB Mannheim** Windows build),
then either:

- add its folder to your `PATH`, **or**
- install it to the default location
  `C:\Program Files\Tesseract-OCR\tesseract.exe`.

The app auto-detects Tesseract in `PATH` and in common install locations. If it
still can't be found, set the path directly by editing `TESSERACT_PATH` /
`pytesseract.pytesseract.tesseract_cmd` in `MACS_Visual_Automation.py`.

> All other actions (clicks, typing, screenshots, folder ops) work without
> Tesseract — only *OCR check* and *Verify text* require it.

---

## Running

```bash
python MACS_Visual_Automation.py
```

---

## How to use

1. **Add steps** with **➕ Step**. Reorder with **↑ / ↓**, remove with **🗑 Delete**.
2. For each step, pick the **Action** from the dropdown and fill in:
   - **Template / area** — path to a PNG template, or an OCR region as `x,y,w,h`.
   - **Value** — action-specific input (the placeholder shows a hint).
   - **Timeout** — seconds to keep searching before failing.
   - **Find win** — cycle windows to locate a hidden target.
   - **Stop** — stop the whole scenario if this step errors (on by default).
3. Use **📷 Capture** (`Ctrl+Shift+S`) with a row selected to grab a template,
   an OCR region, or a click point straight from the screen. The **Preview**
   column then shows a thumbnail of the template — click it to view full size.
4. Set the **Start delay** (seconds to switch to the target window before it
   begins) and the starting **Serial**.
5. Press **▶ Run**. Watch the **Execution log** at the bottom. Press **⏹ Stop**
   to abort.
6. **💾 Save** / **📂 Load** your scenario as JSON.

> Safety: `pyautogui`'s fail-safe is **on** — slamming the mouse into a screen
> corner aborts the run.

---

## Actions reference

| Action | What it does | Value field |
| --- | --- | --- |
| **Click on template** | Find the template image on screen and click its center | *(not needed)* |
| **Double-click on template** | Same, double-click | *(not needed)* |
| **Click on coordinates (x,y)** | Click absolute screen coordinates | `450, 300` |
| **Double-click on coordinates (x,y)** | Double-click absolute coordinates | `450, 300` |
| **Wait for template to appear** | Wait until the template shows up (no click) | *(not needed)* |
| **Press key** | Press a single key | `enter` / `tab` / `f5` |
| **Type text** | Type text (tokens expanded) | text or file path |
| **Delete on-screen item (Delete key)** | UI delete: presses the **Delete** key on whatever is selected on screen (use right after a click). Optionally confirms a dialog | empty, or `enter` to confirm |
| **OCR check (search for word)** | OCR the region; pass if the word is present | word, e.g. `pass` |
| **Verify text & save proof** | OCR + save a PASS/FAIL screenshot into `results\` | keyword, e.g. `pass` |
| **Screenshot of area** | Save a screenshot (region = template/area field) | name, e.g. `unit_{serial}\log.png` |
| **Select folder/file** | Remember a path for the next folder step | path to select |
| **Create folder** | Create a folder (also becomes "selected") | `results\unit_{serial}` |
| **Rename folder** | Rename the selected folder/file | new name/path |
| **Delete folder on disk (by path)** | Delete a folder **on disk** by path (or the selected one). *Not* related to on-screen clicks | path, or empty = selected |
| **Pause (seconds)** | Wait a fixed time | seconds, e.g. `3` |

### Tokens (expanded in paths / typed text)

- `{serial}` — current serial (letters + digits, up to 16 chars). The trailing
  number increments **each time it is used**, and the run remembers where it
  stopped so the next run continues from there. Examples: `0001 → 0002`,
  `SN0099 → SN0100`.
- `{date}` — `YYYY-MM-DD`
- `{time}` — `HHMMSS`
- `{ts}` — Unix epoch seconds

---

## Scenario file format

Scenarios are plain JSON — a list of step objects. Each step:

```json
{
  "enabled": true,
  "action": "click_image",
  "image": "templates\\tpl_1783053819.png",
  "value": "",
  "timeout": 10,
  "find_window": false,
  "stop_on_error": true
}
```

- `enabled` — whether the step runs (the "On" checkbox).
- `action` — internal action key (see the code's `ACTIONS` map).
- `image` — template PNG path, or OCR region `x,y,w,h`.
- `value` — action-specific input (see table above).
- `timeout` — seconds to search before failing.
- `find_window` — cycle windows to find a hidden target.
- `stop_on_error` — abort the scenario if this step fails.

Captured templates are stored under `templates\`, and proof/screenshots under
`results\`.

---

## How it works (internals)

- **DPI awareness** is enabled *before* the Qt app starts, so screenshot pixels,
  template search, and click coordinates all share one coordinate system across
  monitors.
- **`grab_all()`** captures the entire virtual desktop (all monitors) via `mss`
  and returns the image plus the virtual-screen origin offset, keeping
  coordinates consistent even when a monitor sits at negative offsets.
- **`Runner` (QThread)** executes steps off the UI thread and streams log
  messages, PASS/FAIL results, and the updated serial back to the window via Qt
  signals.
- **Template matching** (`_locate`) tries multiple scales and both grayscale and
  Canny-edge matching with OpenCV's `TM_CCOEFF_NORMED`, accepting a match at a
  confidence threshold of `0.80`.
- **`SnipOverlay`** is a full-screen, always-on-top overlay drawn over a frozen
  screenshot that lets you rubber-band select a region.

---

## Troubleshooting

- **"Automation libraries are not installed"** — run
  `pip install -r requirements.txt` (inside your venv).
- **OCR steps fail / "Tesseract OCR engine not found"** — install the Tesseract
  engine and add it to `PATH` (see above).
- **Template "not found on screen"** — the log prints the best match score and
  scale. Use `test_match.py` to debug a specific template:

  ```bash
  python test_match.py templates\tpl_1783053819.png
  ```

  It prints the best score/scale and writes `match_debug.png` with a red box on
  the best guess. Try re-capturing a tighter, higher-contrast template, or enable
  **Find win** if the target window may be hidden.
- **"Find window" does nothing** — it needs `PyGetWindow` (installed via
  requirements) and is intended for Windows.

---

## Project files

- `MACS_Visual_Automation.py` — the application (GUI + automation engine).
- `test_match.py` — standalone template-matching diagnostic tool.
- `requirements.txt` — Python dependencies.
- `scenario.json`, `scenario1.json` — example saved scenarios.
- `templates\` — captured template images (created on first capture).
- `results\` — screenshots / PASS-FAIL proof output (created on first run).
