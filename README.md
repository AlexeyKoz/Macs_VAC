# MACS Visual Automation

**Version 1.3** · see the [Changelog](#changelog) for what changed. The app also
shows a **"What's new"** popup automatically the first time you launch a new
version, and you can reopen it any time via **Help → What's new**.

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
- **Numeric value branching** — read numbers off the screen (e.g. a plot's
  `Az ML` / `El ML` result) and branch on a condition like
  `Az ML<=0.1 AND El ML<=0.1`. Supports `<= >= < > == !=`, `AND`/`OR`, and
  `abs(...)` / `|...|` for tolerance checks; always saves a PASS/FAIL proof.
- **Gimbal calibration CSV branching** — read a calibration CSV (Azimuth,
  Elevation, Gain/Power columns), automatically find the Az/El boresight
  offsets from the peak-gain point, and branch on a tolerance condition like
  `abs(Az)<=0.3 AND abs(El)<=0.3`. Perfect for auto-looping back into a
  recalibration scenario when the gimbal is out of tolerance.
- **Conditional branching (decision nodes)** — route the workflow down Way A or
  Way B based on an image, a word, or a numeric value. A branch target can be a
  single scenario **or a whole playlist** that gets driven through in order.
- **Unconditional playlist/scenario jump** — the *Move to another playlist/scenario*
  action switches to another JSON as soon as it runs, no condition needed. Useful
  for handing the workflow off to a different playlist once you've reached a result.
- **The playlist panel follows the run** — as soon as a jump (or a branch) hands the
  run over, the right panel switches to a **↷ Jump chain** view listing every
  scenario the run moves through: **▶** marks the one running now, **✓** the ones
  already finished. Your own list stays one click away behind the **▣ My list**
  chip — even if it was never saved — and it is what **▶ Run list** always runs.
- **Playlist preview switcher** — click any program in the playlist panel to load
  its steps into the main table for viewing/editing; a bar above the table shows
  the current file and its position in the playlist, with **◀ Prev / Next ▶**
  buttons to step through every program one by one.
- **"Find window" mode** — if a target isn't currently visible, the app cycles
  through open windows (Alt+Tab style) to locate it.
- **Serial number tokens** — use `{serial}`, `{date}`, `{time}`, `{ts}` in paths
  and text; `{serial}` auto-increments and continues across runs.
- **File/folder actions** — create, rename, delete, and select folders (with a
  safety guard against deleting drive roots).
- **Save / load scenarios** as JSON, so each program/workflow is its own file.
- **Playlist runner (right panel)** — queue multiple scenario JSON files, reorder
  them, run sequentially, and watch dedicated playlist status/log. Playlists can
  be **saved/loaded as reusable files** (💾 Save list… / 📂 Load list…) and used
  as branch targets.
- **Collapsible logs** — the Execution log and Playlist log start minimized to
  keep the interface compact; a **▸ Show / ▾ Hide** button next to each header
  (or **View → Show execution log / Show playlist log**) expands them on demand.
- **Version tracking** — the title bar shows the version, a **What's new** popup
  appears once per new version, and **Help → About / What's new** shows the full
  change history.
- **Top menu navigation** — File / View / Help for core actions (open/save,
  playlist run, toggle playlist panel, toggle logs, open README, What's new / About).
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

This script installs everything needed, **step by step, in order**:

1. **Python 3.14.x** — from `offline_installers\` (only if a matching Python
   isn't already found).
2. **Visual C++ Redistributable** — required by Qt/PySide6 (only if missing).
3. **Tesseract OCR** — optional, only needed for *OCR check* / *Verify text*
   steps (only if missing).
4. **`venv\`** — created if it doesn't already exist (or rebuilt automatically
   if it was built with the wrong Python version).
5. **Pip packages** — installed from `offline_packages\` into `venv\`.

It's **safe to re-run at any time** and is idempotent — anything already
installed is detected and skipped, and only what's missing gets installed, so
a partially-set-up PC (e.g. Python already there but no venv yet, or some pip
packages already installed) is simply completed rather than starting over.
If `venv\` already has everything working, the script does nothing at all and
exits immediately.

At the end it doesn't just trust that `pip` returned success — it **verifies**
the install by actually importing every module the app needs
(`PySide6`, `cv2`, `numpy`, `PIL`, `pyautogui`, `pytesseract`, `mss`,
`pygetwindow`, `pyperclip`). If anything still fails to import, it prints the
exact error and exits with a clear next step instead of reporting a false
"success".

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
5. Press **▶ Run**. Watch the **Execution log** at the bottom (click **▸ Show**
   next to its header if it's collapsed). Press **⏹ Stop** to abort.
6. **💾 Save** / **📂 Load** your scenario as JSON.
7. For chained runs, use the **playlist panel on the right**:
   - **➕ Add JSON** — add one or more scenario files.
   - **↑ / ↓** — reorder program execution order.
   - **▶ Run list** / **⏹ Stop list** — start/stop sequential execution.
   - status indicator: **blinking green** while running, **red** when stopped.
   - **Playlist log** (below) shows file-level load/run issues separately —
     click its **▸ Show** button to expand it.
   - **Click a program** to preview its steps in the left table; use
     **◀ Prev / Next ▶** above the table to step through the whole list (see
     [Playlist preview switcher](#playlist-preview-switcher-view-each-programs-steps)).

8. Both the **Execution log** and **Playlist log** start **minimized** to keep
   things compact — expand only the one you need with its **▸ Show** button
   (it becomes **▾ Hide** once expanded).
9. Use the top menu for quick navigation:
   - **File** → Open/Save scenario, Add JSON to playlist, Run playlist, Exit
   - **View** → Show/Hide playlist panel, Show execution log, Show playlist log
   - **Help** → Open `README.md`, **What's new**, **About** (shows version)

> Safety: `pyautogui`'s fail-safe is **on** — slamming the mouse into a screen
> corner aborts the run.

---

## Conditional branching (decision nodes)

Some workflows need different paths depending on what appears on screen — e.g.
**PASS** vs **FAIL**, or one dialog vs another. Use **branch** steps as
decision nodes in your scenario chain.

### How it works

1. Add a branch step (one of the **IF … → A else B** actions).
2. Set **Template / area**:
   - **Image branch** — PNG template to look for.
   - **Text / value branch** — OCR region `x,y,w,h` (capture with 📷).
3. Click **↷ Branch setup** and choose:
   - **Way A** — scenario (or playlist) to run if condition is **TRUE** (found / PASS).
   - **Way B** — scenario (or playlist) to run if condition is **FALSE** (not found / FAIL).
   - Leave either side **empty** to continue the **remaining steps** in the
     current scenario instead of loading another file.
4. When the branch step runs, remaining steps in the current JSON are **skipped**
   if a Way A/B target was chosen. That target loads and runs automatically.
5. **Nested branches** work — a branch JSON can contain another branch step.
   The app follows the whole chain before advancing the playlist.

### Branch targets can be playlists

A Way A / Way B path may point to **a single scenario** *or* **a playlist file**:

- **Scenario file** — a JSON array of step objects (a normal saved scenario).
- **Playlist file** — a JSON array of scenario paths, or `{"playlist": [ ... ]}`.
  When the branch selects a playlist, the app **drives through every scenario in
  it, in order**, and then continues the chain. Create one easily from the
  playlist panel with **💾 Save list…**.

This is the recommended way to "go to another playlist" from a decision node —
e.g. *if calibration is not perfect → run the whole re-calibration playlist*.

### Numeric value branch (read a measured value)

Use **IF value condition met → A else B (+ proof)** to branch on a **number** read
from the screen (great for reading a result off a generated plot/report):

1. Capture a **tight** OCR region (`x,y,w,h`) around the result text with 📷.
2. In **↷ Branch setup**, enter a **condition**, for example:
   - `Az ML<=0.1 AND El ML<=0.1` — perfect calibration.
   - `abs(Az ML)<=0.1 AND abs(El ML)<=0.1` — tolerance around zero (recommended,
     since values can be slightly negative).
3. Operators: `<=  >=  <  >  ==  !=`. Combine clauses with `AND` / `OR`. Wrap a
   label in `abs(...)` or `|...|` to compare the absolute value.
4. The app reads the **first number after each label**
   (e.g. `Az ML: [0.0, 35.99]` → `0.0`), evaluates the condition, and always
   saves a **PASS/FAIL proof screenshot** to `results\`.
   - **Way A** runs on **TRUE** (PASS) — e.g. your "success/finish" scenario.
   - **Way B** runs on **FALSE** (FAIL) — e.g. the re-calibration playlist.

> Tip: give the step a **Timeout** (e.g. 5 s). With a timeout it keeps
> re-reading the region until the condition passes — useful if the plot renders
> slowly. OCR on small plot text can be finicky, so capture a tight, high-contrast
> region.

### Gimbal calibration CSV branch (read Az/El offsets from a file)

Use **IF gimbal calib CSV OK (Az/El) → A else B (+ proof)** to branch on the
result of a **gimbal calibration CSV** instead of reading numbers off the
screen. This is the recommended way to check calibration results that were
exported to a file (e.g. `calib.csv` written after a calibration run) and
loop back into a fresh calibration when the gimbal is out of tolerance.

1. Set **Template / area** to the path of the calibration CSV, e.g. `calib.csv`
   (tokens like `{serial}` work too). The CSV needs `Azimuth`, `Elevation`, and
   either an `Antenna Gain` or `Power Received` column (column names are matched
   loosely, case-insensitive).
2. The app finds the **raw peak-gain point** on each cut:
   - **Az offset** = azimuth value at the highest gain among rows where
     elevation is closest to `0`.
   - **El offset** = elevation value at the highest gain among rows where
     azimuth is closest to `0`.
3. In **↷ Branch setup**, enter a **condition** using labels `Az` / `El`, e.g.:
   - `abs(Az)<=0.3 AND abs(El)<=0.3` — calibration within ±0.3° (recommended,
     tolerant of small negative offsets).
   - `Az==0 AND El==0` — perfect calibration only.
4. Operators: `<=  >=  <  >  ==  !=`. Combine clauses with `AND` / `OR`. Wrap a
   label in `abs(...)` or `|...|` to compare the absolute value.
   - **Way A** runs on **TRUE** (calibration OK) — continue the workflow.
   - **Way B** runs on **FALSE** (out of tolerance) — point it at your
     recalibration scenario (adjust the tolerance on the gimbal, calibrate
     again), building a retry loop.
5. A PASS/FAIL report is always saved to `results\` as a `.txt` file with the
   computed offsets and peak gain values. If a `<csv name>_Pattern.png` file
   (e.g. `calib_Pattern.png` next to `calib.csv`) exists, it's copied alongside
   the report as visual proof.

> Tip: combine this with a playlist Way B target (see
> [Branch targets can be playlists](#branch-targets-can-be-playlists)) to run a
> full "adjust tolerance → recalibrate → re-check" loop automatically.

### Unconditional jump (no condition needed)

Sometimes you don't need a decision — you just want the workflow to hand off
to another playlist or scenario once it reaches a certain point (e.g. "we've
got a result, now keep going with the follow-up playlist"). Use **Move to
another playlist/scenario** for that:

1. Set **Template / area** to the path of the playlist or scenario JSON to
   jump to (tokens like `{serial}` work too).
2. As soon as this step executes, the rest of the current scenario is skipped
   and the app switches straight to that JSON — same mechanism as a branch's
   Way A/B, just without a condition to evaluate.
3. If the target is a **playlist file**, the whole playlist is driven through
   in order (see [Branch targets can be playlists](#branch-targets-can-be-playlists)).

This is the simplest way to chain "if I've reached this point in my scenario,
keep going with a different playlist depending on where I ended up" without
setting up a branch condition at all — put it at the end of one path and point
it at the next playlist.

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
| **IF value condition met (+ proof)** | Reads numbers from a region and checks a condition (`Az ML<=0.1 AND El ML<=0.1`) + saves proof | Reading measured results off plots/reports |
| **IF gimbal calib CSV OK (+ proof)** | Reads a calibration CSV, computes Az/El offsets, checks a condition (`abs(Az)<=0.3 AND abs(El)<=0.3`) + saves a report | Gimbal calibration pass/fail + recalibration loop |

Any Way A / Way B target can be a **single scenario or a playlist file** (see
[Branch targets can be playlists](#branch-targets-can-be-playlists)). Paths in
branch setup are stored **relative to the current scenario folder** when
possible, so you can move `scenarios\` as a group.

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
| **IF value condition met → A else B (+ proof)** | Reads numbers via OCR and checks a numeric condition; saves PASS/FAIL proof. A/B may be a scenario **or a playlist** | `Az ML<=0.1 AND El ML<=0.1 \| wayA \| wayB` (use **↷ Branch setup**) |
| **IF gimbal calib CSV OK → A else B (+ proof)** | **Branch node:** reads a gimbal calibration CSV (Template/area = path to the CSV), computes the Az/El boresight offsets, and checks a numeric condition; saves a PASS/FAIL `.txt` report (+ a copy of `<csv>_Pattern.png` if present). A/B may be a scenario **or a playlist** | `abs(Az)<=0.3 AND abs(El)<=0.3 \| wayA \| wayB` (use **↷ Branch setup**) |
| **Move to another playlist/scenario** | **Unconditional jump:** as soon as this step runs, the app switches straight to the given JSON — no condition, no Way A/B. The rest of the current scenario is skipped, just like a branch that always takes one path | Template/area = path to a playlist or scenario JSON |
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

### Save / load a playlist as a file

- **💾 Save list…** — export the current panel as a playlist file
  (`{"playlist": [ ...scenario paths... ]}`). Paths are stored relative to the
  file when possible, so the folder can be moved as a group.
- **📂 Load list…** — load a playlist file back into the panel (replaces the
  current list).

A saved playlist file is exactly what a **branch** step can point to as Way A or
Way B — so a decision node can send the workflow into an entire playlist. See
[Branch targets can be playlists](#branch-targets-can-be-playlists).

### Playlist preview switcher (view each program's steps)

A bar above the main table shows **which file is currently loaded** and, when
it's part of the playlist, its position — e.g. `📄 pass_flow.json — [2/4 in
playlist]` — with **◀ Prev / Next ▶** buttons next to it.

- **Click any program** in the right-hand playlist list to instantly load its
  steps into the left-hand table, so you can inspect or edit it.
- **◀ Prev / Next ▶** step through every program in the playlist one at a
  time, in order — handy for reviewing a whole playlist without clicking each
  item individually.
- While **▶ Run list** is executing, the bar automatically follows along and
  highlights the program currently running, so you always know where you are.
- Clicking a program **loads it exactly like Open/Load** does — it becomes the
  table you're editing, so **💾 Save** saves changes back to that file.

### Two lists in one panel: ▣ My list ↔ ↷ Jump chain

Above the list there are two chips that decide **which list you are looking at**:

- **▣ My list (n)** — the list you built yourself. This is the one **▶ Run list**
  runs and the only one you can edit, and it is kept even when it was never saved
  to a file.
- **↷ Jump chain (k/n)** — where a *Move to another playlist/scenario* (or a
  branch) step took the run. It lists every scenario the run moves through, in
  order: **▶** = running right now, **✓** = already finished. If the jump target
  was a playlist file, all of its programs appear here at once.

The panel switches to the jump chain by itself on every jump, so you can watch the
run travel; the header and the bar above the steps table say `Jump chain — <file>`
so it's obvious which list is on screen. Click **▣ My list** to go back to your own
programs (the run keeps going in the background, and the app stops auto-switching
until the next run starts). The jump chain is a read-only view — ➕/➖/↑/↓ and
💾 Save list… always work on your own list, switching back to it if needed.

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
- `image` — template PNG path, OCR region `x,y,w,h`, or (for `branch_calib`) a
  path to a calibration CSV.
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

## Changelog

The in-app history lives in the `CHANGELOG` list at the top of
`MACS_Visual_Automation.py`, next to `APP_VERSION`. The app shows a **What's new**
popup once whenever `APP_VERSION` changes (it remembers the last-seen version in
`app_state.json`).

> **Maintaining versions:** when you add a feature, bump `APP_VERSION` and add a
> new entry at the **top** of `CHANGELOG` (`(version, date, [changes])`) — the
> popup, the **Help → What's new** dialog, and this file should stay in sync.

### Version 1.3 — 2026-08-07

- **Collapsible logs**: the Execution log (left panel) and Playlist log (right
  panel) now start **minimized** to keep the interface compact. Each has a
  small **▸ Show / ▾ Hide** button next to its header to expand/collapse it.
- **New View menu items**: **Show execution log** and **Show playlist log**
  (checkable, kept in sync with the inline buttons) join the existing **Show
  playlist panel** option for controlling screen real estate from one place.
- No new Python packages required — UI-only change.

### Version 1.2 — 2026-08-07

- **New action — unconditional jump** (`goto_playlist`): *Move to another
  playlist/scenario*. Put a playlist or scenario JSON path in Template/area
  and the run switches to it as soon as the step executes — no condition, no
  Way A/B. Ideal for handing the workflow off to another playlist once you've
  reached a result.
- **Playlist preview switcher**: click any program in the playlist panel to
  load its steps into the main table for viewing/editing. A new bar above the
  table shows the current file and its position in the playlist, with
  **◀ Prev / Next ▶** buttons to step through every program one by one. The
  bar also follows along automatically while a playlist runs.

### Version 1.1 — 2026-08-06

- **New action — gimbal calibration CSV branch** (`branch_calib`): *IF gimbal
  calib CSV OK (Az/El) → A else B (+ proof)*. Reads a calibration CSV
  (Azimuth, Elevation, Gain/Power columns), computes the Az/El boresight
  offsets from the peak-gain point on each raw cut, and evaluates conditions
  such as `abs(Az)<=0.3 AND abs(El)<=0.3`.
- **Way A = calibration OK, Way B = out of tolerance** — point Way B at a
  recalibration scenario (adjust tolerance, calibrate again) to build a retry
  loop directly from the automation.
- Saves a PASS/FAIL `.txt` report to `results\` with the computed offsets; if
  a `<csv name>_Pattern.png` sits next to the CSV, it's copied there too as
  visual proof.
- No new Python packages required — the CSV is parsed with the built-in `csv`
  module.

### Version 1.0 — 2026-08-06

First versioned release — the baseline for change tracking.

- **New action — numeric value branch** (`branch_value`): *IF value condition met
  → A else B (+ proof)*. Reads numbers via OCR and evaluates conditions such as
  `Az ML<=0.1 AND El ML<=0.1` (operators `<= >= < > == !=`, `AND`/`OR`, and
  `abs(...)` / `|...|` for tolerance). Always saves a PASS/FAIL proof screenshot.
- **Branch into a playlist:** Way A / Way B can point to a **playlist file** and
  the whole playlist is driven through in order (not just a single scenario).
- **Playlist save/load:** new **💾 Save list… / 📂 Load list…** buttons to export
  and reuse a playlist as a file (ideal as a branch target).
- **Anti-loop guard** raised to 200 branch hops to support re-calibration loops.
- **Version tracking:** title-bar version, first-run **What's new** popup, and
  **Help → What's new / About** dialogs.

---

## Project files

- `MACS_Visual_Automation.py` — the application (GUI + automation engine).
- `app_state.json` — remembers the last-seen version for the What's new popup
  (created on first run; safe to delete — it just re-shows the popup once).
- `test_match.py` — standalone template-matching diagnostic tool.
- `requirements.txt` — Python dependencies.
- `download_packages.bat` — download Python, Tesseract, and pip wheels (online PC).
- `install_offline.bat` — idempotently install everything from local folders
  (offline PC); skips what's already installed and verifies the result.
- `run_app.bat` — start the app using the virtual environment.
- `build.bat` / `MACS_Visual_Automation.spec` — build a standalone `.exe` with PyInstaller.
- `offline_installers\` — Python and Tesseract installers (created by download script).
- `offline_packages\` — pip wheels for offline install (created by download script).
- `scenario.json`, `scenario1.json` — example saved scenarios.
- `templates\` — captured template images (created on first capture).
- `results\` — screenshots / PASS-FAIL proof output (created on first run).
