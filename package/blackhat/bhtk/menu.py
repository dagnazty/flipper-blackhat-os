#!/usr/bin/env python3
"""
Professional full-screen TUI menu system for BlackHat ToolKit.

Navigation:
- ↑/↓ or j/k: move
- Enter: select
- Backspace/Esc: back
- /: global command palette
- t: cycle theme
- d: open dashboard
- 1..9: run hotkey-mapped action from current menu
- q: quit
"""

from __future__ import annotations

import curses
import getpass
import io
import json
import socket
import subprocess
import threading
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple


LOG_PATH = Path("/tmp/bhtk-ui.log")
SETTINGS_PATH = Path.home() / ".config" / "bhtk" / "ui.json"
CURRENT_APP: "TUIMenuApp | None" = None

DEFAULT_KEYBINDS = {
    "up": ["KEY_UP", "k"],
    "down": ["KEY_DOWN", "j"],
    "select": ["ENTER"],
    "back": ["KEY_BACKSPACE", "ESC"],
    "palette": ["/"],
    "theme": ["t"],
    "dashboard": ["d"],
    "cancel": ["x"],
    "quit": ["q"],
}


class UILogWriter:
    """File-like stdout sink that streams lines into the UI log."""

    def __init__(self, app: "TUIMenuApp"):
        self.app = app
        self.buf = ""

    def write(self, data: str):
        if not data:
            return 0
        self.buf += data
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            line = line.strip()
            if line:
                self.app._log(line[:180])
        return len(data)

    def flush(self):
        tail = self.buf.strip()
        if tail:
            self.app._log(tail[:180])
        self.buf = ""


@dataclass
class MenuNode:
    """Tree node representing a menu entry."""

    title: str
    subtitle: str = ""
    handler: Optional[Callable[[], None]] = None
    children: List["MenuNode"] = field(default_factory=list)
    risk: str = "low"  # low | medium | high
    description: str = ""

    @property
    def is_leaf(self) -> bool:
        return self.handler is not None and not self.children


@dataclass
class Theme:
    name: str
    header_fg: int
    accent_fg: int
    selected_fg: int
    selected_bg: int
    status_fg: int


THEMES = [
    Theme("Flipper", curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_BLACK, curses.COLOR_CYAN, curses.COLOR_YELLOW),
    Theme("Matrix", curses.COLOR_GREEN, curses.COLOR_GREEN, curses.COLOR_BLACK, curses.COLOR_GREEN, curses.COLOR_GREEN),
    Theme("Amber", curses.COLOR_YELLOW, curses.COLOR_YELLOW, curses.COLOR_BLACK, curses.COLOR_YELLOW, curses.COLOR_MAGENTA),
    Theme("Ice", curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_BLACK, curses.COLOR_WHITE, curses.COLOR_CYAN),
]


def _safe_cmd(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, timeout=2).strip()
    except Exception:
        return "0"


def _print_system_info(get_wifi_interfaces, get_bt_interfaces):
    print("\n=== System Information ===\n")

    print("WiFi Interfaces:")
    wifi = get_wifi_interfaces()
    if wifi:
        for iface in wifi:
            print(f"  - {iface}")
    else:
        print("  none")

    print("\nBluetooth Interfaces:")
    bt = get_bt_interfaces()
    if bt:
        for iface in bt:
            print(f"  - {iface}")
    else:
        print("  none")

    print()


class TUIMenuApp:
    """Curses-based menu application."""

    def __init__(self, root: MenuNode):
        self.root = root
        self.stack: List[MenuNode] = [root]
        self.selected_index = 0
        self.status = "Ready"
        self.running = True
        self.event_log: List[str] = ["UI initialized"]
        self.hotkeys: dict[str, MenuNode] = {}
        self.show_dashboard = True
        self.active_procs: List[subprocess.Popen] = []
        self.cancel_requested = False
        self.last_wifi_networks: List[dict] = []
        self.last_ble_devices: List[dict] = []

        settings = self._load_settings()
        self.theme_index = self._theme_index_from_name(settings.get("default_theme", "Flipper"))
        self.keybinds = settings.get("keybinds", DEFAULT_KEYBINDS)
        self.recent = settings.get("recent", {})

    @property
    def current(self) -> MenuNode:
        return self.stack[-1]

    @property
    def items(self) -> List[MenuNode]:
        return self.current.children

    @property
    def selected_item(self) -> Optional[MenuNode]:
        if not self.items:
            return None
        return self.items[self.selected_index]

    def run(self):
        global CURRENT_APP
        CURRENT_APP = self
        curses.wrapper(self._main)

    def _main(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            self._apply_theme_colors()

        while self.running:
            self._draw(stdscr)
            key = stdscr.getch()
            self._handle_key(stdscr, key)

    def _draw(self, stdscr):
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        if self.show_dashboard:
            self._draw_dashboard(stdscr, h, w)
            stdscr.refresh()
            return

        theme = THEMES[self.theme_index].name
        title = "BLACKHAT TOOLKIT"
        version = "v1.3"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        header = f" {title} {version} [{theme}] "

        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, " " * (w - 1))
        stdscr.addstr(0, max(1, (w - len(header)) // 2), header[: max(1, w - 2)])
        if w > len(now) + 2:
            stdscr.addstr(0, w - len(now) - 2, now)
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        crumb = " > ".join(node.title for node in self.stack)
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(2, 2, crumb[: max(1, w - 4)])
        stdscr.attroff(curses.A_BOLD)

        if self.current.subtitle:
            stdscr.addstr(3, 2, self.current.subtitle[: max(1, w - 4)])

        top = 5
        bottom = h - 7
        left = 2
        right = w - 3
        split = int((right - left) * 0.62) + left

        if bottom <= top or right <= left:
            return

        self._draw_box(stdscr, top, left, bottom, split, " Navigation ")
        self._draw_box(stdscr, top, split + 1, bottom, right, " Context ")

        self._draw_menu_items(stdscr, top, left, bottom, split)
        self._draw_context(stdscr, top, split + 1, bottom, right)

        log_top = bottom + 1
        log_bottom = h - 3
        self._draw_box(stdscr, log_top, left, log_bottom, right, " Activity Log ")
        self._draw_logs(stdscr, log_top, left, log_bottom, right)

        system = self._system_snapshot()
        hints = "↑/↓ move Enter select / global t theme d dash x cancel 1..9 hotkeys Backspace/Esc back q quit"
        stdscr.attron(curses.color_pair(4))
        stdscr.addstr(h - 2, 2, f"Status: {self.status}"[: max(1, w - 4)])
        stdscr.attroff(curses.color_pair(4))
        stdscr.addstr(h - 1, 2, f"{system} | {hints}"[: max(1, w - 4)])

        stdscr.refresh()

    def _draw_dashboard(self, stdscr, h: int, w: int):
        self._draw_box(stdscr, 2, 2, h - 3, w - 3, " Dashboard ")

        leaves, categories, high_risk = self._menu_stats()
        left = 4
        y = 4
        title = "BLACKHAT TOOLKIT"
        stdscr.attron(curses.A_BOLD | curses.color_pair(1))
        stdscr.addstr(y, left, title)
        stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
        y += 2

        lines = [
            f"Theme: {THEMES[self.theme_index].name}",
            f"Categories: {categories}",
            f"Actions: {leaves}",
            f"High-risk actions: {high_risk}",
            f"Recent log file: {LOG_PATH}",
        ]
        for line in lines:
            stdscr.addstr(y, left, line[: max(1, w - 8)])
            y += 1

        y += 1
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y, left, "Quick Start")
        stdscr.attroff(curses.A_BOLD)
        y += 1
        quick = [
            "• Enter: continue to main menu",
            "• /: global palette across all modules/actions",
            "• t: cycle theme (saved automatically)",
            "• 1..9: run visible hotkey actions",
        ]
        for line in quick:
            stdscr.addstr(y, left, line[: max(1, w - 8)])
            y += 1

        stdscr.addstr(h - 5, 4, "Press Enter to continue, or q to quit."[: max(1, w - 8)])

    def _draw_menu_items(self, stdscr, top, left, bottom, split):
        max_rows = max(1, bottom - top - 1)
        start = 0
        if self.selected_index >= max_rows:
            start = self.selected_index - max_rows + 1

        visible_items = self.items[start : start + max_rows]

        self.hotkeys = {}
        hotkey_counter = 1

        for idx, item in enumerate(visible_items, start=start):
            y = top + 1 + (idx - start)
            prefix = "▶" if idx == self.selected_index else " "
            suffix = "  »" if item.children else "  • run"

            hotkey = ""
            if item.is_leaf and hotkey_counter <= 9:
                hotkey = str(hotkey_counter)
                self.hotkeys[hotkey] = item
                hotkey_counter += 1

            hk_label = f"[{hotkey}] " if hotkey else ""
            label = f" {prefix} {hk_label}{item.title}{suffix}"
            width = max(1, split - left - 1)
            label = label[:width]

            if idx == self.selected_index:
                stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                stdscr.addstr(y, left + 1, label.ljust(width))
                stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            else:
                stdscr.addstr(y, left + 1, label)

    def _draw_context(self, stdscr, top, left, bottom, right):
        item = self.selected_item
        if not item:
            return

        width = max(1, right - left - 1)
        y = top + 1
        stdscr.addstr(y, left + 1, f"Name: {item.title}"[:width], curses.A_BOLD)
        y += 1

        risk = (item.risk or "low").lower()
        if risk == "high":
            color = curses.color_pair(5) | curses.A_BOLD
        elif risk == "medium":
            color = curses.color_pair(6) | curses.A_BOLD
        else:
            color = curses.color_pair(7) | curses.A_BOLD

        stdscr.addstr(y, left + 1, f"Risk: {risk.upper()}"[:width], color)
        y += 1

        subtype = "Category" if item.children else "Action"
        stdscr.addstr(y, left + 1, f"Type: {subtype}"[:width])
        y += 1

        path = self._path_for_selected()
        stdscr.addstr(y, left + 1, f"Path: {path}"[:width])
        y += 2

        desc = item.description or item.subtitle or "No description provided."
        for line in self._wrap(desc, width):
            if y >= bottom:
                break
            stdscr.addstr(y, left + 1, line)
            y += 1

    def _draw_logs(self, stdscr, top, left, bottom, right):
        width = max(1, right - left - 1)
        height = max(1, bottom - top - 1)
        entries = self.event_log[-height:]
        for i, msg in enumerate(entries):
            y = top + 1 + i
            stdscr.addstr(y, left + 1, msg[:width])

    def show_table_view(self, title: str, headers: List[str], rows: List[List[str]]):
        """Blocking table viewer with scrolling; keeps user inside results view."""
        if not hasattr(self, "stdscr"):
            return
        stdscr = self.stdscr
        offset = 0
        selected = 0

        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            left, right, top, bottom = 2, w - 3, 1, h - 3
            self._draw_box(stdscr, top, left, bottom, right, f" {title} ")

            inner_w = max(20, right - left - 1)
            view_h = max(3, bottom - top - 3)  # header + rows

            # basic dynamic column widths
            col_count = len(headers)
            col_w = max(8, (inner_w - (col_count - 1) * 3) // max(1, col_count))

            def fmt_line(parts):
                return " | ".join(str(p)[:col_w].ljust(col_w) for p in parts)[:inner_w]

            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(top + 1, left + 1, fmt_line(headers))
            stdscr.attroff(curses.A_BOLD)

            if selected < offset:
                offset = selected
            if selected >= offset + view_h:
                offset = selected - view_h + 1

            window = rows[offset : offset + view_h]
            for idx, row in enumerate(window):
                y = top + 2 + idx
                row_idx = offset + idx
                line = fmt_line(row)
                if row_idx == selected:
                    stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                    stdscr.addstr(y, left + 1, line.ljust(inner_w))
                    stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
                else:
                    stdscr.addstr(y, left + 1, line)

            footer = f"Rows: {len(rows)}  Selected: {selected+1 if rows else 0}  ↑/↓ scroll  PgUp/PgDn jump  q/Esc close"
            stdscr.addstr(bottom - 1, left + 1, footer[:inner_w])
            stdscr.refresh()

            key = stdscr.getch()
            if key in (ord('q'), ord('Q'), 27, curses.KEY_BACKSPACE, 10, 13):
                break
            if not rows:
                continue
            if key in (curses.KEY_UP, ord('k'), ord('K')):
                selected = max(0, selected - 1)
            elif key in (curses.KEY_DOWN, ord('j'), ord('J')):
                selected = min(len(rows) - 1, selected + 1)
            elif key == curses.KEY_NPAGE:
                selected = min(len(rows) - 1, selected + view_h)
            elif key == curses.KEY_PPAGE:
                selected = max(0, selected - view_h)
            elif key == curses.KEY_HOME:
                selected = 0
            elif key == curses.KEY_END:
                selected = len(rows) - 1

    def _draw_box(self, stdscr, top, left, bottom, right, title):
        if bottom <= top or right <= left:
            return
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(top, left, "┌" + "─" * max(1, right - left - 1) + "┐")
        for y in range(top + 1, bottom):
            stdscr.addstr(y, left, "│")
            stdscr.addstr(y, right, "│")
        stdscr.addstr(bottom, left, "└" + "─" * max(1, right - left - 1) + "┘")
        if right - left > len(title) + 4:
            stdscr.addstr(top, left + 2, title)
        stdscr.attroff(curses.color_pair(2))

    def _handle_key(self, stdscr, key):
        if self.show_dashboard:
            if self._is_action_key(key, "quit"):
                self.running = False
                self._log("Quit from dashboard")
            elif self._is_action_key(key, "select") or key == 27:
                self.show_dashboard = False
                self.status = "Dashboard closed"
            return

        if self._is_action_key(key, "quit"):
            self.running = False
            self._log("Quit")
            return

        if self._is_action_key(key, "dashboard"):
            self.show_dashboard = True
            self._log("Opened dashboard")
            return

        if self._is_action_key(key, "theme"):
            self.theme_index = (self.theme_index + 1) % len(THEMES)
            self._apply_theme_colors()
            self._save_settings()
            self.status = f"Theme: {THEMES[self.theme_index].name}"
            self._log(self.status)
            return

        # Hotkeys 1..9 for visible leaf actions
        if ord('1') <= key <= ord('9'):
            hotkey = chr(key)
            node = self.hotkeys.get(hotkey)
            if node:
                self._run_handler(stdscr, node)
            else:
                self.status = f"No action mapped to [{hotkey}]"
            return

        if self._is_action_key(key, "palette"):
            self._open_global_palette(stdscr)
            return

        if self._is_action_key(key, "up"):
            if self.items:
                self.selected_index = max(0, self.selected_index - 1)
            return

        if self._is_action_key(key, "down"):
            if self.items:
                self.selected_index = min(len(self.items) - 1, self.selected_index + 1)
            return

        if self._is_action_key(key, "back"):
            if len(self.stack) > 1:
                last = self.stack.pop().title
                self.selected_index = 0
                self.status = f"Back from {last}"
                self._log(self.status)
            return

        if self._is_action_key(key, "select"):
            if not self.items:
                return

            selected = self.items[self.selected_index]
            if selected.children:
                self.stack.append(selected)
                self.selected_index = 0
                self.status = f"Opened {selected.title}"
                self._log(self.status)
                return

            if selected.handler:
                self._run_handler(stdscr, selected)

    def _is_action_key(self, key: int, action: str) -> bool:
        entries = self.keybinds.get(action, DEFAULT_KEYBINDS.get(action, []))
        for token in entries:
            if self._match_key_token(key, token):
                return True
            # allow uppercase alpha to match lowercase bindings
            if isinstance(token, str) and len(token) == 1 and token.isalpha() and self._match_key_token(key, token.upper()):
                return True
        return False

    @staticmethod
    def _match_key_token(key: int, token: str) -> bool:
        token = str(token)
        mapping = {
            "KEY_UP": curses.KEY_UP,
            "KEY_DOWN": curses.KEY_DOWN,
            "KEY_BACKSPACE": curses.KEY_BACKSPACE,
            "ENTER": 10,
            "ESC": 27,
        }
        if token in mapping:
            if token == "ENTER":
                return key in (10, 13, curses.KEY_ENTER)
            if token == "KEY_BACKSPACE":
                return key in (curses.KEY_BACKSPACE, 127, 8)
            return key == mapping[token]
        return len(token) == 1 and key == ord(token)

    def _open_global_palette(self, stdscr):
        curses.echo()
        h, w = stdscr.getmaxyx()
        prompt = "Palette (supports risk:high module:wifi): "
        stdscr.addstr(h - 1, 2, " " * (w - 4))
        stdscr.addstr(h - 1, 2, prompt[: max(1, w - 4)])
        stdscr.refresh()

        query = stdscr.getstr(h - 1, min(w - 2, len(prompt) + 2), 80).decode(errors="ignore").strip().lower()
        curses.noecho()

        if not query:
            self.status = "Palette canceled"
            return

        matches = self._search_tree(query)
        if not matches:
            self.status = f"No matches for '{query}'"
            self._log(self.status)
            return

        chosen = 0
        if len(matches) > 1:
            chosen = self._pick_palette_match(stdscr, matches)
            if chosen < 0:
                self.status = "Palette canceled"
                return

        path, node = matches[chosen]
        self._select_path(path)
        self.status = f"Palette selected: {' > '.join(n.title for n in path[1:])}"
        self._log(self.status)

        if node.is_leaf:
            self._run_handler(stdscr, node)

    def _search_tree(self, query: str) -> List[Tuple[List[MenuNode], MenuNode]]:
        out: List[Tuple[List[MenuNode], MenuNode]] = []

        tokens = query.split()
        risk_filter = None
        module_filter = None
        text_terms: List[str] = []
        for tok in tokens:
            if tok.startswith("risk:"):
                risk_filter = tok.split(":", 1)[1].strip()
            elif tok.startswith("module:"):
                module_filter = tok.split(":", 1)[1].strip()
            else:
                text_terms.append(tok)

        def walk(node: MenuNode, path: List[MenuNode]):
            if node is not self.root:
                hay = f"{node.title} {node.subtitle} {node.description}".lower()
                node_risk = (node.risk or "low").lower()
                module = path[0].title.lower() if len(path) > 0 else "main"

                risk_ok = (risk_filter is None) or (node_risk == risk_filter)
                module_ok = (module_filter is None) or (module_filter in module)
                text_ok = (not text_terms) or all(term in hay for term in text_terms)

                if risk_ok and module_ok and text_ok:
                    out.append((path + [node], node))

            for child in node.children:
                walk(child, path + [node])

        walk(self.root, [])
        return out

    def _pick_palette_match(self, stdscr, matches: List[Tuple[List[MenuNode], MenuNode]]) -> int:
        h, w = stdscr.getmaxyx()
        max_show = min(9, len(matches))

        start_y = max(2, h - (max_show + 6))
        stdscr.addstr(start_y, 2, " " * (w - 4))
        stdscr.addstr(start_y, 2, "Multiple matches. Pick 1-9 (or Enter for #1, blank to cancel):"[: max(1, w - 4)])

        for i in range(max_show):
            path, node = matches[i]
            label = f"[{i + 1}] {' > '.join(n.title for n in path[1:])}"
            stdscr.addstr(start_y + 1 + i, 2, " " * (w - 4))
            stdscr.addstr(start_y + 1 + i, 2, label[: max(1, w - 4)])

        stdscr.addstr(start_y + 1 + max_show, 2, " " * (w - 4))
        stdscr.addstr(start_y + 1 + max_show, 2, "Choice: ")
        stdscr.refresh()

        curses.echo()
        raw = stdscr.getstr(start_y + 1 + max_show, 10, 2).decode(errors="ignore").strip()
        curses.noecho()

        if not raw:
            return 0
        if raw.isdigit():
            v = int(raw)
            if 1 <= v <= max_show:
                return v - 1
        return -1

    def _select_path(self, path: List[MenuNode]):
        if not path:
            return
        # path includes root as first element for this app
        self.stack = [self.root]
        cur = self.root
        for node in path[1:]:
            if node in cur.children:
                self.stack.append(node)
                cur = node

        if len(self.stack) >= 2:
            parent = self.stack[-2]
            target = self.stack[-1]
            if target in parent.children:
                self.selected_index = parent.children.index(target)

        if self.stack[-1].children:
            self.selected_index = 0

    def _run_handler(self, stdscr, selected: MenuNode):
        if self._is_dangerous(selected) and not self._confirm(stdscr, selected):
            self.status = f"Canceled {selected.title}"
            self._log(self.status)
            return

        self.status = f"Running {selected.title}..."
        self._log(self.status)

        try:
            selected.handler()
            self.status = f"Completed {selected.title}"
            self._log(self.status)
        except KeyboardInterrupt:
            self.status = f"Interrupted {selected.title}"
            self._log(self.status)
        except Exception as exc:
            self.status = f"Error in {selected.title}"
            self._log(f"Error: {selected.title}: {exc}")
            self._log(traceback.format_exc(limit=1).strip())

    def prompt_text(self, prompt: str, default: str = "", max_len: int = 80, remember_key: Optional[str] = None) -> Optional[str]:
        stdscr = getattr(self, "stdscr", None)
        if stdscr is None:
            return default
        h, w = stdscr.getmaxyx()
        if remember_key and not default:
            default = str(self.recent.get(remember_key, ""))
        text = f"{prompt}"
        if default:
            text += f" [{default}]"
        text += ": "
        curses.echo()
        stdscr.addstr(h - 1, 2, " " * (w - 4))
        stdscr.addstr(h - 1, 2, text[: max(1, w - 4)])
        stdscr.refresh()
        raw = stdscr.getstr(h - 1, min(w - 2, len(text) + 2), max_len).decode(errors="ignore").strip()
        curses.noecho()
        if raw == "":
            val = default
        else:
            val = raw
        if remember_key and val is not None:
            self.recent[remember_key] = val
            self._save_settings()
        return val

    def choose_from_list(self, title: str, options: List[str], default_index: int = 0) -> Optional[str]:
        stdscr = getattr(self, "stdscr", None)
        if stdscr is None:
            return options[default_index] if options else None
        if not options:
            self.status = f"No options for {title}"
            self._log(self.status)
            return None
        h, w = stdscr.getmaxyx()
        max_show = min(9, len(options))
        start_y = max(2, h - (max_show + 6))
        stdscr.addstr(start_y, 2, " " * (w - 4))
        stdscr.addstr(start_y, 2, f"{title}: pick 1-{max_show} (blank={default_index+1})"[: max(1, w - 4)])
        for i in range(max_show):
            stdscr.addstr(start_y + 1 + i, 2, " " * (w - 4))
            stdscr.addstr(start_y + 1 + i, 2, f"[{i+1}] {options[i]}"[: max(1, w - 4)])
        stdscr.addstr(start_y + 1 + max_show, 2, " " * (w - 4))
        stdscr.addstr(start_y + 1 + max_show, 2, "Choice: ")
        stdscr.refresh()
        curses.echo()
        raw = stdscr.getstr(start_y + 1 + max_show, 10, 3).decode(errors="ignore").strip()
        curses.noecho()
        if raw == "":
            idx = max(0, min(default_index, len(options)-1))
            return options[idx]
        if raw.isdigit():
            idx = int(raw)-1
            if 0 <= idx < len(options):
                return options[idx]
        return None

    def _terminate_active_procs(self):
        for p in list(self.active_procs):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        time.sleep(0.2)
        for p in list(self.active_procs):
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass

    def run_action_in_app(self, title: str, func: Callable, *args, **kwargs):
        self.status = f"Running {title}... (press x to cancel)"
        result = None
        error = None
        writer = UILogWriter(self)
        self.cancel_requested = False
        self.active_procs = []

        original_popen = subprocess.Popen

        def tracked_popen(*p_args, **p_kwargs):
            p = original_popen(*p_args, **p_kwargs)
            self.active_procs.append(p)
            return p

        holder = {"done": False}

        def worker():
            nonlocal result, error
            try:
                subprocess.Popen = tracked_popen
                with redirect_stdout(writer), redirect_stderr(writer):
                    result = func(*args, **kwargs)
            except KeyboardInterrupt:
                error = "Interrupted"
            except Exception:
                error = traceback.format_exc(limit=1)
            finally:
                subprocess.Popen = original_popen
                holder["done"] = True

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        self.stdscr.timeout(100)
        try:
            while not holder["done"]:
                self._draw(self.stdscr)
                key = self.stdscr.getch()
                if key != -1 and self._is_action_key(key, "cancel"):
                    self.cancel_requested = True
                    self._log("Cancel requested by user")
                    self._terminate_active_procs()
                    self.status = f"Canceling {title}..."
                elif key != -1 and self._is_action_key(key, "quit"):
                    self._log("Quit requested during action; canceling task first")
                    self.cancel_requested = True
                    self._terminate_active_procs()
            t.join(timeout=0.2)
        finally:
            self.stdscr.timeout(-1)
            writer.flush()
            self.active_procs = []

        if self.cancel_requested and not error:
            self.status = f"Canceled {title}"
            self._log(self.status)
        elif error:
            self.status = f"Error: {title}"
            self._log(str(error))
        else:
            self.status = f"Completed {title}"
        return result

    def _confirm(self, stdscr, node: MenuNode) -> bool:
        h, w = stdscr.getmaxyx()
        msg = f"Confirm HIGH-RISK action '{node.title}'? Type YES: "
        curses.echo()
        stdscr.addstr(h - 1, 2, " " * (w - 4))
        stdscr.addstr(h - 1, 2, msg[: max(1, w - 4)])
        stdscr.refresh()
        typed = stdscr.getstr(h - 1, min(w - 2, len(msg) + 2), 8).decode(errors="ignore").strip()
        curses.noecho()
        return typed == "YES"

    def _is_dangerous(self, node: MenuNode) -> bool:
        if node.risk.lower() == "high":
            return True
        dangerous = {
            "Deauth Attack",
            "Evil Twin AP",
            "ARP Spoof",
            "Credential Harvester",
            "Spoof Device",
        }
        return node.title in dangerous

    def _log(self, message: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        self.event_log.append(line)
        self.event_log = self.event_log[-200:]
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    def _path_for_selected(self) -> str:
        if not self.items:
            return "Main"
        item = self.items[self.selected_index]
        return " > ".join(node.title for node in self.stack + [item])

    def _menu_stats(self) -> Tuple[int, int, int]:
        leaves = 0
        categories = 0
        high_risk = 0

        def walk(node: MenuNode):
            nonlocal leaves, categories, high_risk
            if node.children:
                if node is not self.root:
                    categories += 1
                for c in node.children:
                    walk(c)
            elif node.handler:
                leaves += 1
                if node.risk.lower() == "high":
                    high_risk += 1

        walk(self.root)
        return leaves, categories, high_risk

    def _load_settings(self) -> dict:
        data = {"default_theme": "Flipper", "keybinds": DEFAULT_KEYBINDS}
        try:
            if SETTINGS_PATH.exists():
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data.update(raw)
                    if isinstance(raw.get("keybinds"), dict):
                        merged = dict(DEFAULT_KEYBINDS)
                        merged.update(raw["keybinds"])
                        data["keybinds"] = merged
        except Exception:
            pass
        return data

    def _save_settings(self):
        data = {
            "default_theme": THEMES[self.theme_index].name,
            "keybinds": self.keybinds,
            "recent": self.recent,
        }
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _theme_index_from_name(self, name: str) -> int:
        for i, t in enumerate(THEMES):
            if t.name.lower() == str(name).lower():
                return i
        return 0

    def _apply_theme_colors(self):
        theme = THEMES[self.theme_index]
        curses.init_pair(1, theme.header_fg, -1)
        curses.init_pair(2, theme.accent_fg, -1)
        curses.init_pair(3, theme.selected_fg, theme.selected_bg)
        curses.init_pair(4, theme.status_fg, -1)
        curses.init_pair(5, curses.COLOR_RED, -1)
        curses.init_pair(6, curses.COLOR_YELLOW, -1)
        curses.init_pair(7, curses.COLOR_GREEN, -1)

    @staticmethod
    def _wrap(text: str, width: int) -> List[str]:
        if width < 8:
            return [text[:width]]
        words = text.split()
        lines: List[str] = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    @staticmethod
    def _system_snapshot() -> str:
        user = getpass.getuser()
        host = socket.gethostname()
        wifi = _safe_cmd(["sh", "-c", "ls /sys/class/net 2>/dev/null | grep -E '^(wl|wlan)' | wc -l"])
        bt = _safe_cmd(["sh", "-c", "hciconfig -a 2>/dev/null | grep -c '^hci'"])
        return f"{user}@{host} wifi:{wifi.strip() or '0'} bt:{bt.strip() or '0'}"


class MainMenu:
    """Main menu for BlackHat ToolKit."""

    def __init__(self):
        self.root = self._build_tree()

    def run(self):
        TUIMenuApp(self.root).run()

    # -------- In-app action wrappers (no module input prompts) --------
    def _app(self) -> TUIMenuApp:
        if CURRENT_APP is None:
            raise RuntimeError("UI app not initialized")
        return CURRENT_APP

    def action_wifi_scan(self):
        from .wifi import scanner
        from .utils.interfaces import get_wifi_interfaces
        app = self._app()
        iface = app.choose_from_list("WiFi interface", get_wifi_interfaces())
        if not iface:
            app.status = "Canceled"
            return
        networks = app.run_action_in_app("Scan Networks", scanner.scan, iface)
        self.last_wifi_networks = networks or []
        rows = [
            [
                n.get("bssid", ""),
                (n.get("ssid") or "<hidden>"),
                str(n.get("channel", "")),
                str(n.get("signal", "")),
                n.get("encryption", "Open"),
            ]
            for n in self.last_wifi_networks
        ]
        app.show_table_view("WiFi Scan Results", ["BSSID", "SSID", "CH", "Signal", "Enc"], rows)
        app._log(f"WiFi scan results: {len(self.last_wifi_networks)} networks")

    def action_deauth(self):
        from .wifi import deauth
        from .utils.interfaces import get_wifi_interfaces
        app = self._app()
        iface = app.choose_from_list("WiFi interface", get_wifi_interfaces())
        if not iface:
            return

        ap = None
        if self.last_wifi_networks:
            opts = [f"{n.get('ssid') or '<hidden>'} | {n.get('bssid')} | ch {n.get('channel')} | {n.get('signal')}" for n in self.last_wifi_networks[:20]]
            pick = app.choose_from_list("Pick AP from last scan (or cancel for manual)", opts)
            if pick:
                idx = opts.index(pick)
                ap = self.last_wifi_networks[idx].get("bssid")

        if not ap:
            ap = app.prompt_text("Target AP BSSID", remember_key="ap_bssid")
        if not ap:
            return

        client = app.prompt_text("Target client MAC (blank=broadcast)", "")
        app.run_action_in_app("Deauth Attack", deauth.attack, iface, client or None, ap)

    def action_handshake(self):
        from .wifi import handshake
        from .utils.interfaces import get_wifi_interfaces, enable_monitor_mode, disable_monitor_mode
        app = self._app()
        iface = app.choose_from_list("WiFi interface", get_wifi_interfaces())
        if not iface:
            return

        ap = None
        ch = None
        if self.last_wifi_networks:
            opts = [f"{n.get('ssid') or '<hidden>'} | {n.get('bssid')} | ch {n.get('channel')} | {n.get('signal')}" for n in self.last_wifi_networks[:20]]
            pick = app.choose_from_list("Pick AP from last scan (or cancel for manual)", opts)
            if pick:
                idx = opts.index(pick)
                chosen = self.last_wifi_networks[idx]
                ap = chosen.get("bssid")
                ch = str(chosen.get("channel") or "1")

        if not ap:
            ap = app.prompt_text("Target AP BSSID", remember_key="ap_bssid")
        if not ch:
            ch = app.prompt_text("Channel", "1", remember_key="wifi_channel")

        if not ap or not ch:
            return
        if not app.run_action_in_app("Enable Monitor", enable_monitor_mode, iface):
            return
        try:
            app.run_action_in_app("Capture Handshake", handshake.capture, iface, ap, ch)
        finally:
            app.run_action_in_app("Disable Monitor", disable_monitor_mode, iface)

    def action_evil_twin(self):
        from .wifi import evil_twin
        from .utils.interfaces import get_wifi_interfaces
        app = self._app()
        iface = app.choose_from_list("WiFi interface", get_wifi_interfaces())
        ssid = app.prompt_text("SSID to impersonate", remember_key="evil_ssid")
        ch = app.prompt_text("Channel", "6", remember_key="wifi_channel")
        if iface and ssid:
            app.run_action_in_app("Evil Twin AP", evil_twin.setup, iface, ssid, int(ch or "6"))

    def action_portscan(self):
        from .network import portscan
        app = self._app()
        target = app.prompt_text("Target IP/hostname", remember_key="target_host")
        ports = app.prompt_text("Ports", "1-1000", remember_key="ports")
        if target:
            app.run_action_in_app("Port Scanner", portscan.scan, target, ports)

    def action_arp_spoof(self):
        from .network import arp_spoof
        app = self._app()
        target = app.prompt_text("Target IP", remember_key="target_ip")
        gateway = app.prompt_text("Gateway (blank=auto)", "", remember_key="gateway")
        if target:
            app.run_action_in_app("ARP Spoof", arp_spoof.attack, target, gateway or None)

    def action_sniffer(self):
        from .network import sniffer
        app = self._app()
        iface = app.prompt_text("Interface (blank=any)", "", remember_key="sniff_iface")
        filt = app.prompt_text("BPF filter (blank=none)", "", remember_key="sniff_filter")
        count = app.prompt_text("Packet count", "200")
        app.run_action_in_app("Packet Sniffer", sniffer.capture, iface or None, filt or None, None, int(count or "200"))

    def action_harvester(self):
        from .network import harvester
        app = self._app()
        app.run_action_in_app("Credential Harvester", harvester.run)

    def action_ble_scan(self):
        from .bluetooth import ble_scan
        app = self._app()
        dur = app.prompt_text("BLE scan duration seconds", "10")
        devices = app.run_action_in_app("BLE Scan", ble_scan.scan, int(dur or "10"))
        self.last_ble_devices = devices or []
        rows = [[d.get("mac", ""), d.get("name", "<unnamed>")] for d in self.last_ble_devices]
        app.show_table_view("BLE Scan Results", ["MAC", "Name"], rows)
        app._log(f"BLE scan results: {len(self.last_ble_devices)} devices")

    def action_bt_recon(self):
        from .bluetooth import recon
        app = self._app()

        mac = None
        if self.last_ble_devices:
            opts = [f"{d.get('mac')} | {d.get('name', '<unnamed>')}" for d in self.last_ble_devices[:20]]
            pick = app.choose_from_list("Pick device from last BLE scan (or cancel for manual)", opts)
            if pick:
                idx = opts.index(pick)
                mac = self.last_ble_devices[idx].get("mac")

        if not mac:
            mac = app.prompt_text("Bluetooth MAC", remember_key="bt_mac")
        if mac:
            app.run_action_in_app("Bluetooth Recon", recon.gather, mac)

    def action_bt_spoof(self):
        from .bluetooth import spoof
        from .utils.interfaces import get_bt_interfaces
        app = self._app()
        iface = app.choose_from_list("Bluetooth interface", get_bt_interfaces()) or "hci0"
        name = app.prompt_text("Spoof name", "BHTK-Device")
        device_class = app.prompt_text("Device class hex", "0x5a020c")
        random_mac = app.prompt_text("Random MAC? y/N", "y").lower() == "y"
        mac = spoof.generate_random_mac() if random_mac else app.prompt_text("Custom MAC", "")
        app.run_action_in_app("Spoof Device", spoof.run, iface, name or None, mac or None, device_class or None)

    def action_banner(self):
        from .recon import banner
        app = self._app()
        target = app.prompt_text("Target host/IP", remember_key="target_host")
        ports = app.prompt_text("Ports comma/range (blank=common)", "", remember_key="ports")
        parsed = None
        if ports:
            parsed = []
            for part in ports.split(','):
                part = part.strip()
                if '-' in part:
                    a,b = part.split('-',1)
                    parsed.extend(list(range(int(a), int(b)+1)))
                elif part:
                    parsed.append(int(part))
        if target:
            app.run_action_in_app("Banner Grabber", banner.grab, target, parsed)

    def action_services(self):
        from .recon import services
        app = self._app()
        target = app.prompt_text("Target host/IP", remember_key="target_host")
        ports = app.prompt_text("Ports", "1-1000", remember_key="ports")
        if target:
            app.run_action_in_app("Service Detection", services.detect, target, ports)

    def action_subdomain(self):
        from .recon import subdomain
        app = self._app()
        dom = app.prompt_text("Target domain", remember_key="target_domain")
        if dom:
            dom = dom.replace("http://", "").replace("https://", "").split('/')[0]
            app.run_action_in_app("Subdomain Finder", subdomain.find, dom)

    def action_wifi_audit(self):
        app = self._app()
        app._log("Workflow: WiFi Audit")
        self.action_wifi_scan()
        ap = app.prompt_text("Audit target AP BSSID for handshake (blank skip)", "")
        if ap:
            ch = app.prompt_text("AP channel", "1")
            from .wifi import handshake
            from .utils.interfaces import get_wifi_interfaces, enable_monitor_mode, disable_monitor_mode
            iface = app.choose_from_list("WiFi interface", get_wifi_interfaces())
            if iface and enable_monitor_mode(iface):
                try:
                    app.run_action_in_app("Handshake Capture", handshake.capture, iface, ap, ch)
                finally:
                    app.run_action_in_app("Disable Monitor", disable_monitor_mode, iface)

    def action_network_discovery(self):
        app = self._app()
        target = app.prompt_text("Network CIDR or host (e.g. 192.168.1.0/24)")
        if not target:
            return
        from .network import portscan
        from .recon import services
        app.run_action_in_app("Quick Port Scan", portscan.scan, target, "22,53,80,443,445,3389")
        deep = app.prompt_text("Run service detection too? y/N", "n").lower() == "y"
        if deep:
            app.run_action_in_app("Service Detection", services.detect, target, "1-1000")

    def action_quick_recon(self):
        app = self._app()
        target = app.prompt_text("Target domain/IP")
        if not target:
            return
        from .network import portscan
        from .recon import banner, subdomain
        app.run_action_in_app("Quick Scan", portscan.quick_scan, target)
        app.run_action_in_app("Banner Grab", banner.grab, target)
        if any(c.isalpha() for c in target):
            dom = target.replace("http://", "").replace("https://", "").split('/')[0]
            app.run_action_in_app("Subdomain Finder", subdomain.find, dom, subdomain.COMMON_SUBDOMAINS[:20])

    def action_system_info(self):
        from .utils.interfaces import get_wifi_interfaces, get_bt_interfaces
        self._app().run_action_in_app("System Info", _print_system_info, get_wifi_interfaces, get_bt_interfaces)

    def _build_tree(self) -> MenuNode:
        from .wifi import scanner, deauth, handshake, evil_twin
        from .network import portscan, arp_spoof, sniffer, harvester
        from .bluetooth import ble_scan, recon as bt_recon, spoof
        from .recon import banner, services, subdomain
        from .automation import workflows
        from .utils.interfaces import get_wifi_interfaces, get_bt_interfaces

        return MenuNode(
            title="Main",
            subtitle="Select a module",
            description="BlackHat ToolKit operational launcher.",
            children=[
                MenuNode(
                    title="WiFi Attacks",
                    subtitle="Wireless attack and audit tooling",
                    risk="high",
                    description="Wireless operations: scanning, handshake capture, deauth, and AP impersonation.",
                    children=[
                        MenuNode("Scan Networks", handler=self.action_wifi_scan, risk="low", description="Discover nearby WiFi APs and metadata."),
                        MenuNode("Deauth Attack", handler=self.action_deauth, risk="high", description="Transmit deauthentication frames to disconnect clients."),
                        MenuNode("Capture Handshake", handler=self.action_handshake, risk="medium", description="Capture WPA handshakes for offline analysis."),
                        MenuNode("Evil Twin AP", handler=self.action_evil_twin, risk="high", description="Clone a target SSID and lure clients to rogue AP."),
                    ],
                ),
                MenuNode(
                    title="Network Attacks",
                    subtitle="LAN discovery and active testing",
                    risk="high",
                    description="Local network enumeration, interception, and active traffic operations.",
                    children=[
                        MenuNode("Port Scanner", handler=self.action_portscan, risk="low", description="Scan host(s) for open TCP/UDP services."),
                        MenuNode("ARP Spoof", handler=self.action_arp_spoof, risk="high", description="Poison ARP tables for man-in-the-middle positioning."),
                        MenuNode("Packet Sniffer", handler=self.action_sniffer, risk="medium", description="Capture and inspect traffic on selected interface."),
                        MenuNode("Credential Harvester", handler=self.action_harvester, risk="high", description="Run credential collection workflow."),
                    ],
                ),
                MenuNode(
                    title="Bluetooth Attacks",
                    subtitle="BLE and BT recon/spoof",
                    risk="medium",
                    description="Bluetooth reconnaissance and identity spoof capabilities.",
                    children=[
                        MenuNode("BLE Scanner", handler=self.action_ble_scan, risk="low", description="Scan for BLE advertisers and metadata."),
                        MenuNode("Device Recon", handler=self.action_bt_recon, risk="low", description="Gather data about discovered Bluetooth devices."),
                        MenuNode("Spoof Device", handler=self.action_bt_spoof, risk="high", description="Emulate or spoof Bluetooth identity parameters."),
                    ],
                ),
                MenuNode(
                    title="Reconnaissance",
                    subtitle="Passive/active recon modules",
                    risk="medium",
                    description="Target profiling and service intelligence modules.",
                    children=[
                        MenuNode("Banner Grabber", handler=self.action_banner, risk="low", description="Collect service banners from target endpoints."),
                        MenuNode("Service Detection", handler=self.action_services, risk="low", description="Identify network services and likely versions."),
                        MenuNode("Subdomain Finder", handler=self.action_subdomain, risk="low", description="Enumerate subdomains for target domain."),
                    ],
                ),
                MenuNode(
                    title="Automation",
                    subtitle="Prebuilt workflows",
                    risk="high",
                    description="Multi-step workflows for fast assessments.",
                    children=[
                        MenuNode("Full WiFi Audit", handler=self.action_wifi_audit, risk="high", description="Run chained wireless assessment workflow."),
                        MenuNode("Network Discovery", handler=self.action_network_discovery, risk="medium", description="Automated host and service discovery pass."),
                        MenuNode("Quick Recon", handler=self.action_quick_recon, risk="low", description="Fast reconnaissance summary collection."),
                    ],
                ),
                MenuNode(
                    title="System Info",
                    subtitle="Quick interface inventory",
                    risk="low",
                    description="Display current wireless and Bluetooth interfaces.",
                    handler=self.action_system_info,
                ),
            ],
        )
