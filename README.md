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
- **Playlist runner (right panel)** — queue multiple scenario JSON files, reorder
  them, run sequentially, and watch dedicated playlist status/log.
- **Top menu navigation** — File / View / Help for core actions (open/save,
  playlist run, toggle playlist panel, open README).
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

1. **Add steps** with **➕ Add** (append) or **➕ Insert** (insert after selected row).
   You can select multiple rows and use **📋 Copy** / **📋 Paste**.
2. For each step, pick the **Action** from the dropdown and fill in:
   - **Template / area** — path to a PNG template, or an OCR region as `x,y,w,h`.
   - **Value** — action-specific input (the placeholder shows a hint).
   - **Timeout** — seconds to keep searching before failing.
   - **Find win** — cycle windows to locate a hidden target.
   - **Stop** — stop the whole scenario if this step errors (on by default).
3. Use **📷 Capture** (`Ctrl+Shift+S`) with a row selected to grab a template,
   an OCR region, or a click point straight from the screen. The **Preview**
   column then shows a thumbnail of the template — click it to view full size.
   Use **✏ Regions** to edit compare/exclude/click zones for template-based steps.
   For **branch** steps, use **↷ Branch setup** to pick Way A / Way B JSON files.
4. Set the **Start delay** (seconds to switch to the target window before it
   begins) and the starting **Serial**.
5. Press **▶ Run**. Watch the **Execution log** at the bottom. Press **⏹ Stop**
   to abort.
6. **💾 Save** / **📂 Load** your scenario as JSON.
7. For chained runs, use the **playlist panel on the right**:
   - **➕ Add JSON** — add one or more scenario files.
   - **↑ / ↓** — reorder program execution order.
   - **▶ Run list** / **⏹ Stop list** — start/stop sequential execution.
   - status indicator: **blinking green** while running, **red** when stopped.
   - **Playlist log** (below) shows file-level load/run issues separately.

8. Use the top menu for quick navigation:
   - **File** → Open/Save scenario, Add JSON to playlist, Run playlist, Exit
   - **View** → Show/Hide playlist panel
   - **Help** → Open `README.md`

> Safety: `pyautogui`'s fail-safe is **on** — slamming the mouse into a screen
> corner aborts the run.

---

## Conditional branching (decision nodes)

Some workflows need different paths depending on what appears on screen — e.g.
**PASS** vs **FAIL**, or one dialog vs another. Use **branch** steps as
decision nodes in your scenario chain.

### How it works

1. Add a branch step (one of the **IF … → JSON A else JSON B** actions).
2. Set **Template / area**:
   - **Image branch** — PNG template to look for.
   - **Text branch** — OCR region `x,y,w,h` (capture with 📷).
3. Click **↷ Branch setup** and choose:
   - **Way A** — JSON scenario to run if condition is **TRUE** (found / PASS).
   - **Way B** — JSON to run if condition is **FALSE** (not found / FAIL).
   - Leave either side **empty** to continue the **remaining steps** in the
     current scenario instead of loading another file.
4. When the branch step runs, remaining steps in the current JSON are **skipped**
   if a Way A/B file was chosen. That JSON loads and runs automatically.
5. **Nested branches** work — a branch JSON can contain another branch step.
   The app follows the whole chain before advancing the playlist.

### Example flow

```
main.json
  step 1: open app
  step 2: click Start
  step 3: IF word "PASS" → pass_flow.json else fail_flow.json
  step 4: (skipped if branch loaded a file)
  step 5: cleanup

pass_flow.json  → archive result, continue…
fail_flow.json  → log error, notify operator…
```

### Branch types

| Type | Checks | Best for |
| --- | --- | --- |
| **IF template found** | Is a UI image visible? | Different screens/dialogs |
| **IF word found (OCR)** | Is a keyword in a region? | PASS/FAIL text, status labels |
| **IF word found (+ proof)** | Same as OCR + saves `results\PASS_…png` or `FAIL_…png` | Test stations needing proof |

Paths in branch setup are stored **relative to the current scenario folder**
when possible, so you can move `scenarios\` as a group.

---

## Actions reference

| Action | What it does | Value field |
| --- | --- | --- |
| **Click on template** | Find the template image on screen and click its center | *(not needed)* |
| **Double-click on template** | Same, double-click | *(not needed)* |
| **Click on coordinates (x,y)** | Click absolute screen coordinates | `450, 300` |
| **Double-click on coordinates (x,y)** | Double-click absolute coordinates | `450, 300` |
| **Wait for template to appear** | Wait until the template shows up (no click) | *(not needed)* |
| **Scroll panel (mouse wheel)** | Find a scroll panel and send wheel events at its scrollbar zone | `down, 5` / `up, 3` |
| **Press key / shortcut** | Press one key or a hotkey combination | `enter`, `backspace`, `ctrl+a`, `ctrl+shift+s` |
| **Type text** | Type text (tokens expanded) | text or file path |
| **Fill input field (clear & type)** | Find input by stable frame, ignore current value, click input zone, then clear/type (or paste) | `847`, `847\|enter`, `paste:847\|enter`, `replace:{serial}` |
| **Delete on-screen item (Delete key)** | UI delete: presses the **Delete** key on whatever is selected on screen (use right after a click). Optionally confirms a dialog | empty, or `enter` to confirm |
| **OCR check (search for word)** | OCR the region; pass if the word is present | word, e.g. `pass` |
| **Verify text & save proof** | OCR + save a PASS/FAIL screenshot into `results\` | keyword, e.g. `pass` |
| **IF template found → JSON A else JSON B** | **Branch node:** checks if template is on screen; loads Way A or Way B JSON | `wayA.json \| wayB.json` (use **↷ Branch setup**) |
| **IF word found (OCR) → JSON A else JSON B** | **Branch node:** OCR region + keyword; loads Way A or Way B JSON | `word \| wayA.json \| wayB.json` |
| **IF word found (+ proof) → JSON A else JSON B** | Like OCR branch + saves PASS/FAIL proof; never fails the step | `word \| wayA.json \| wayB.json` |
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

## Reliable input fields (important)

For UI fields where the current number changes (and often contains `-` or masks),
do **not** rely on double-click + type.

Use **Fill input field (clear & type)** with a captured template and regions:

1. Capture a large area with **label + input box**.
2. In **✏ Regions**:
   - **Compare (green):** stable frame/label used to find the field.
   - **Value (ignore, red):** current value digits (ignored during matching).
   - **Input zone (blue):** where to click and type/paste.
3. Set value to `paste:...` for best reliability in masked fields.

Example values:

- `paste:847|enter`
- `847|enter`
- `replace:{serial}`

This solves the logical conflict: the changing value is excluded from comparison,
but the same area is still editable through the dedicated input zone.

---

## Playlist mode (multi-JSON queue)

Use playlist mode when one automation should start another automatically.

1. Save each program as its own JSON file (`💾 Save`).
2. Add files in the right panel with **➕ Add JSON**.
3. Reorder queue with **↑ / ↓**.
4. Click **▶ Run list**.

How it behaves:

- Programs run in top-to-bottom order.
- Each JSON is loaded into the main table, then executed.
- If a file fails to load, the error is written to **Playlist log** and queue
  continues with the next item.
- **⏹ Stop list** stops the current run and the remaining queue.

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
- **Field input sometimes leaves old symbols (`-`, mask chars)** — use
  **Fill input field** and prefer `paste:...` mode. Configure **Compare / Value
  ignore / Input zone** in **✏ Regions**.
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
