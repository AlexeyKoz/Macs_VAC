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
- **Python:** 3.14.6 recommended (offline bundles target this version; 3.10+ may
  work for online install).
- **Python packages:** see [`requirements.txt`](requirements.txt).
- **Tesseract OCR engine** (only needed for *OCR check* / *Verify text* steps) —
  this is a native program, **not** a pip package.

---

## Installation

### Option A — Online install (PC with internet)

**Automatic (recommended):** open **Command Prompt** in the project folder and run:

```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

Or double-click `run_app.bat` after the venv is set up.

**Manual equivalent:**

```cmd
cd path\to\Macs_VAC
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
venv\Scripts\python.exe MACS_Visual_Automation.py
```

---

### Option B — Offline install (PC without internet)

Use this when the target PC has **no internet**. Prepare everything on another
PC that **does** have internet, then copy the whole project folder over.

#### Step 1 — On a PC **with internet**

Double-click or run:

```cmd
download_packages.bat
```

This downloads into the project folder:

| Folder | Contents |
| --- | --- |
| `offline_installers\` | Python 3.14.6 installer + Tesseract OCR installer |
| `offline_packages\` | All pip wheels needed by `requirements.txt` |

#### Step 2 — Copy to the offline PC

Copy the **entire project folder**, including at minimum:

- `offline_installers\`
- `offline_packages\`
- `install_offline.bat`
- `run_app.bat`
- `MACS_Visual_Automation.py`
- `requirements.txt`

#### Step 3 — On the offline PC

Double-click or run:

```cmd
install_offline.bat
```

This script automatically:

1. Installs **Python 3.14.6** from `offline_installers\` (if Python is missing)
2. Installs **Tesseract OCR** from the local installer (optional, for OCR steps)
3. Creates `venv\` and installs all pip packages from `offline_packages\`

Then start the app:

```cmd
run_app.bat
```

> **Important:** pip wheels in `offline_packages\` were built for **Python
> 3.14.6**. The offline PC must use the same version. If you need a different
> Python version, re-run `download_packages.bat` on a PC that has that version
> installed.

---

### Option C — Manual offline install (if `.bat` files fail)

Use these commands one by one in **Command Prompt** (`cmd.exe`). Prefer `cmd`
over PowerShell for activation — it avoids script-policy issues.

#### C.1 Allow PowerShell scripts (only if you use PowerShell)

If `venv\Scripts\activate` fails with *"running scripts is disabled"* in
PowerShell, run **once** (no admin needed):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate with:

```powershell
venv\Scripts\activate
```

**Alternatives that skip PowerShell entirely:**

```cmd
venv\Scripts\activate.bat
```

Or call Python directly without activating:

```cmd
venv\Scripts\python.exe MACS_Visual_Automation.py
```

**One-time bypass** (current PowerShell window only, no permanent change):

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
venv\Scripts\activate
```

#### C.2 Install Python manually (offline PC)

If `install_offline.bat` cannot install Python, run the local installer:

```cmd
cd path\to\Macs_VAC
offline_installers\python-3.14.6-amd64.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1
```

Verify (open a **new** Command Prompt after install):

```cmd
python --version
```

Expected output: `Python 3.14.6`

If `python` is not found, use the full path:

```cmd
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" --version
```

#### C.3 Install pip packages manually (offline PC)

```cmd
cd path\to\Macs_VAC

python -m venv venv
venv\Scripts\activate.bat

python -m pip install --no-index --find-links=offline_packages pip setuptools wheel
python -m pip install --no-index --find-links=offline_packages -r requirements.txt
```

If activation fails, replace `python` with the full path:

```cmd
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -m venv venv
venv\Scripts\python.exe -m pip install --no-index --find-links=offline_packages pip setuptools wheel
venv\Scripts\python.exe -m pip install --no-index --find-links=offline_packages -r requirements.txt
```

#### C.4 Install Tesseract manually (offline PC, OCR steps only)

Silent install from the bundled installer:

```cmd
offline_installers\tesseract-ocr-w64-setup-5.5.0.20241111.exe /S
```

Or run the `.exe` interactively and install to the default folder
`C:\Program Files\Tesseract-OCR\`.

Verify:

```cmd
tesseract --version
```

#### C.5 Run the app manually

```cmd
cd path\to\Macs_VAC
venv\Scripts\python.exe MACS_Visual_Automation.py
```

---

### Download packages manually (if `download_packages.bat` fails)

Run on a PC **with internet** and Python 3.14.6 installed:

```cmd
cd path\to\Macs_VAC
mkdir offline_packages
mkdir offline_installers

curl -L -o offline_installers\python-3.14.6-amd64.exe https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe

curl -L -o offline_installers\tesseract-ocr-w64-setup-5.5.0.20241111.exe https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe

python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip download -r requirements.txt -d offline_packages
pip download setuptools wheel pip build -d offline_packages
```

If your offline PC uses a **different Python version**, download wheels with that
version (example for 3.12):

```cmd
py -3.12 -m pip download -r requirements.txt -d offline_packages
py -3.12 -m pip download setuptools wheel pip build -d offline_packages
```

---

### Installing the Tesseract engine (for OCR steps)

Tesseract is included in `offline_installers\` when you run
`download_packages.bat`. For online install, download a Windows build from
[UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki), then
either:

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

**After install:**

```cmd
run_app.bat
```

**Or manually:**

```cmd
venv\Scripts\activate.bat
python MACS_Visual_Automation.py
```

**Without activating venv:**

```cmd
venv\Scripts\python.exe MACS_Visual_Automation.py
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

- **PowerShell: "running scripts is disabled"** — use `venv\Scripts\activate.bat`
  in Command Prompt instead, or run
  `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` (see
  [Option C.1](#c1-allow-powershell-scripts-only-if-you-use-powershell) above).
- **"Automation libraries are not installed"** — run
  `pip install -r requirements.txt` (online) or `install_offline.bat` (offline).
- **Offline pip install fails / "no matching distribution"** — Python version on
  the offline PC must match the version used when `download_packages.bat` was
  run (default: 3.14.6). Re-download wheels with the correct version.
- **`download_packages.bat` fails to download Python** — download manually from
  `https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe` and save as
  `offline_installers\python-3.14.6-amd64.exe`.
- **OCR steps fail / "Tesseract OCR engine not found"** — install Tesseract from
  `offline_installers\` or add it to `PATH` (see above).
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
- `download_packages.bat` — download Python, Tesseract, and pip wheels (online PC).
- `install_offline.bat` — install everything from local folders (offline PC).
- `run_app.bat` — start the app using the virtual environment.
- `build.bat` / `MACS_Visual_Automation.spec` — build a standalone `.exe` with PyInstaller.
- `offline_installers\` — Python and Tesseract installers (created by download script).
- `offline_packages\` — pip wheels for offline install (created by download script).
- `scenario.json`, `scenario1.json` — example saved scenarios.
- `templates\` — captured template images (created on first capture).
- `results\` — screenshots / PASS-FAIL proof output (created on first run).
