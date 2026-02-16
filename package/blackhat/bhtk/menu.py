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
import json
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple


LOG_PATH = Path("/tmp/bhtk-ui.log")
SETTINGS_PATH = Path.home() / ".config" / "bhtk" / "ui.json"

DEFAULT_KEYBINDS = {
    "up": ["KEY_UP", "k"],
    "down": ["KEY_DOWN", "j"],
    "select": ["ENTER"],
    "back": ["KEY_BACKSPACE", "ESC"],
    "palette": ["/"],
    "theme": ["t"],
    "dashboard": ["d"],
    "quit": ["q"],
}


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

        settings = self._load_settings()
        self.theme_index = self._theme_index_from_name(settings.get("default_theme", "Flipper"))
        self.keybinds = settings.get("keybinds", DEFAULT_KEYBINDS)

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
        curses.wrapper(self._main)

    def _main(self, stdscr):
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
        hints = "↑/↓ move Enter select / global t theme d dash 1..9 hotkeys Backspace/Esc back q quit"
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

        curses.def_prog_mode()
        curses.endwin()

        try:
            selected.handler()
            input("\nPress Enter to return to menu...")
            self.status = f"Completed {selected.title}"
            self._log(self.status)
        except KeyboardInterrupt:
            self.status = f"Interrupted {selected.title}"
            self._log(self.status)
        except Exception as exc:
            print(f"\n[!] Error running {selected.title}: {exc}")
            input("\nPress Enter to return to menu...")
            self.status = f"Error in {selected.title}"
            self._log(f"Error: {selected.title}: {exc}")
        finally:
            curses.reset_prog_mode()
            stdscr.refresh()

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
                        MenuNode("Scan Networks", handler=scanner.interactive, risk="low", description="Discover nearby WiFi APs and metadata."),
                        MenuNode("Deauth Attack", handler=deauth.interactive, risk="high", description="Transmit deauthentication frames to disconnect clients."),
                        MenuNode("Capture Handshake", handler=handshake.interactive, risk="medium", description="Capture WPA handshakes for offline analysis."),
                        MenuNode("Evil Twin AP", handler=evil_twin.interactive, risk="high", description="Clone a target SSID and lure clients to rogue AP."),
                    ],
                ),
                MenuNode(
                    title="Network Attacks",
                    subtitle="LAN discovery and active testing",
                    risk="high",
                    description="Local network enumeration, interception, and active traffic operations.",
                    children=[
                        MenuNode("Port Scanner", handler=portscan.interactive, risk="low", description="Scan host(s) for open TCP/UDP services."),
                        MenuNode("ARP Spoof", handler=arp_spoof.interactive, risk="high", description="Poison ARP tables for man-in-the-middle positioning."),
                        MenuNode("Packet Sniffer", handler=sniffer.interactive, risk="medium", description="Capture and inspect traffic on selected interface."),
                        MenuNode("Credential Harvester", handler=harvester.interactive, risk="high", description="Run credential collection workflow."),
                    ],
                ),
                MenuNode(
                    title="Bluetooth Attacks",
                    subtitle="BLE and BT recon/spoof",
                    risk="medium",
                    description="Bluetooth reconnaissance and identity spoof capabilities.",
                    children=[
                        MenuNode("BLE Scanner", handler=ble_scan.interactive, risk="low", description="Scan for BLE advertisers and metadata."),
                        MenuNode("Device Recon", handler=bt_recon.interactive, risk="low", description="Gather data about discovered Bluetooth devices."),
                        MenuNode("Spoof Device", handler=spoof.interactive, risk="high", description="Emulate or spoof Bluetooth identity parameters."),
                    ],
                ),
                MenuNode(
                    title="Reconnaissance",
                    subtitle="Passive/active recon modules",
                    risk="medium",
                    description="Target profiling and service intelligence modules.",
                    children=[
                        MenuNode("Banner Grabber", handler=banner.interactive, risk="low", description="Collect service banners from target endpoints."),
                        MenuNode("Service Detection", handler=services.interactive, risk="low", description="Identify network services and likely versions."),
                        MenuNode("Subdomain Finder", handler=subdomain.interactive, risk="low", description="Enumerate subdomains for target domain."),
                    ],
                ),
                MenuNode(
                    title="Automation",
                    subtitle="Prebuilt workflows",
                    risk="high",
                    description="Multi-step workflows for fast assessments.",
                    children=[
                        MenuNode("Full WiFi Audit", handler=workflows.wifi_audit, risk="high", description="Run chained wireless assessment workflow."),
                        MenuNode("Network Discovery", handler=workflows.network_discovery, risk="medium", description="Automated host and service discovery pass."),
                        MenuNode("Quick Recon", handler=workflows.quick_recon, risk="low", description="Fast reconnaissance summary collection."),
                    ],
                ),
                MenuNode(
                    title="System Info",
                    subtitle="Quick interface inventory",
                    risk="low",
                    description="Display current wireless and Bluetooth interfaces.",
                    handler=lambda: _print_system_info(get_wifi_interfaces, get_bt_interfaces),
                ),
            ],
        )
