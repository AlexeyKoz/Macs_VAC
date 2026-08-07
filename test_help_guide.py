"""Проверки полного руководства (Help → Full guide) на двух языках.

Что должно выполняться:
  1. У КАЖДОГО действия из ACTIONS есть описание и на английском, и на русском,
     с заполненными полями «что делает / Template-area / Value» (и русским
     названием действия) — новое действие нельзя добавить, забыв про справку.
  2. Каждое действие попадает ровно в один раздел справки, а разделы не
     ссылаются на несуществующие действия.
  3. У каждого раздела есть заголовок на обоих языках и непустой текст.
  4. Диалог собирается, переключает язык, фильтрует разделы поиском и
     открывается на разделе выбранного в таблице действия.

Запуск:
    venv\\Scripts\\python.exe test_help_guide.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

from PySide6.QtWidgets import QApplication

import MACS_Visual_Automation as app_mod

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


def main():
    app = QApplication(sys.argv)

    # --- 1. каждое действие описано на двух языках ---
    missing = [a for a in app_mod.ACTIONS if a not in app_mod.ACTION_DOCS]
    check(f"Every action has docs (missing: {missing or 'none'})", not missing)

    incomplete = []
    for action, docs in app_mod.ACTION_DOCS.items():
        for lang in app_mod.HELP_LANGS:
            doc = docs.get(lang) or {}
            for field in ("what", "target", "value"):
                if not (doc.get(field) or "").strip():
                    incomplete.append(f"{action}.{lang}.{field}")
    check(f"Every action doc fills what/target/value in both languages "
          f"(gaps: {incomplete or 'none'})", not incomplete)

    no_ru_title = [a for a, d in app_mod.ACTION_DOCS.items()
                   if not (d.get("ru", {}).get("title") or "").strip()]
    check(f"Every action has a Russian name (missing: {no_ru_title or 'none'})",
          not no_ru_title)

    stale = [a for a in app_mod.ACTION_DOCS if a not in app_mod.ACTIONS]
    check(f"No docs for removed actions (stale: {stale or 'none'})", not stale)

    # --- 2. группировка действий по разделам ---
    grouped = [a for actions in app_mod.HELP_ACTION_GROUPS.values() for a in actions]
    check("Each action is listed in exactly one help section",
          sorted(grouped) == sorted(set(grouped)) == sorted(app_mod.ACTIONS))
    check("help_action_topic_key maps an action to its section",
          app_mod.help_action_topic_key("click_image") == "act_input"
          and app_mod.help_action_topic_key("goto_playlist") == "act_flow"
          and app_mod.help_action_topic_key("pause") == "act_files")

    # --- 3. разделы руководства ---
    bad_titles = [t.get("key") for t in app_mod.HELP_TOPICS
                  if not all((t.get("title", {}).get(l) or "").strip()
                             for l in app_mod.HELP_LANGS)]
    check(f"Every section has a title in both languages (bad: {bad_titles or 'none'})",
          not bad_titles)

    short = []
    for topic in app_mod.HELP_TOPICS:
        for lang in app_mod.HELP_LANGS:
            html = app_mod.help_topic_html(topic, lang)
            if len(app_mod.help_topic_plain(topic, lang)) < 200:
                short.append(f"{topic['key']}.{lang}")
            if "<h2" not in html:
                short.append(f"{topic['key']}.{lang}.no-heading")
    check(f"Every section renders real content in both languages "
          f"(thin: {short or 'none'})", not short)

    action_sections_ok = True
    for group, actions in app_mod.HELP_ACTION_GROUPS.items():
        for lang in app_mod.HELP_LANGS:
            html = app_mod.help_actions_html(group, lang)
            for action in actions:
                if action not in html or app_mod.help_escape(app_mod.ACTIONS[action]) not in html:
                    action_sections_ok = False
    check("Action sections list every action they own, in both languages",
          action_sections_ok)

    # Текст описаний не должен потеряться в разметке: '<=', '<word>', '<csv name>'
    # раньше съедались как HTML-теги.
    topics_by_key = {t["key"]: t for t in app_mod.HELP_TOPICS}
    lost = []
    for group, actions in app_mod.HELP_ACTION_GROUPS.items():
        for lang in app_mod.HELP_LANGS:
            plain = app_mod.help_topic_plain(topics_by_key[group], lang)
            for action in actions:
                doc = app_mod.ACTION_DOCS[action][lang]
                for field in ("what", "target", "value", "note"):
                    text = (doc.get(field) or "").strip().lower()
                    if text and text not in plain:
                        lost.append(f"{action}.{lang}.{field}")
    check(f"Angle brackets in docs survive rendering (lost: {lost or 'none'})", not lost)

    # --- 4. диалог ---
    dlg = app_mod.HelpDialog(None, lang="en")
    check("Dialog lists all sections", dlg.topic_list.count() == len(app_mod.HELP_TOPICS))
    check("Dialog opens on the first section and shows text",
          len(dlg.view.toPlainText().strip()) > 200)
    first_en = dlg.topic_list.item(0).text()

    dlg.set_language("ru")
    check("Switching to Russian re-titles the sections",
          dlg.topic_list.item(0).text() != first_en
          and dlg.topic_list.item(0).text() == app_mod.HELP_TOPICS[0]["title"]["ru"])
    check("Russian content is rendered",
          any(ch.isalpha() and ch.lower() != ch.upper() and ord(ch) > 1000
              for ch in dlg.view.toPlainText()))
    check("Language choice is reported back for saving", dlg.language() == "ru")

    dlg.set_language("en")
    dlg.select_topic("act_flow")
    text = dlg.view.toPlainText()
    check("The section list follows the shown section",
          dlg.topic_list.currentItem().data(app_mod.Qt.UserRole) == "act_flow")
    check("Selecting a section shows that section",
          "goto_playlist" in text and "Jump chain" in text)
    check("Operators and placeholders reach the screen as written",
          "<=" in text and "abs(Az)<=0.3" in text and "<csv name>_Pattern.png" in text)

    dlg.search.setText("gimbal")
    check("Search narrows the section list",
          0 < dlg.topic_list.count() < len(app_mod.HELP_TOPICS))
    dlg.search.setText("zzzzz-nothing-here")
    check("A search with no hits explains itself",
          dlg.topic_list.count() == 0
          and app_mod.HELP_UI_TEXT["en"]["empty"] in dlg.view.toPlainText())
    dlg.search.setText("")
    check("Clearing the search restores all sections",
          dlg.topic_list.count() == len(app_mod.HELP_TOPICS))
    dlg.deleteLater()

    # Диалог, открытый на конкретном разделе (так работает F1 по выбранному шагу),
    # должен показать именно его, а не первый раздел руководства.
    opened = app_mod.HelpDialog(None, lang="ru", topic_key="act_files")
    check("Opening on a requested section honours it",
          opened.topic_list.currentItem().data(app_mod.Qt.UserRole) == "act_files"
          and "pause" in opened.view.toPlainText())
    opened.deleteLater()

    # --- 5. F1 открывает раздел выделенного действия ---
    win = app_mod.MainWindow()
    win.table.setCurrentCell(0, app_mod.COL_ACTION)
    check("F1 targets the section of the selected step's action",
          win._help_topic_for_selection() == "act_input")
    combo = win.table.cellWidget(0, app_mod.COL_ACTION)
    combo.setCurrentIndex(list(app_mod.ACTIONS).index("branch_calib"))
    check("Changing the action changes the section F1 opens",
          win._help_topic_for_selection() == "act_flow")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
