# ==============================================================================
# FreesIA - Custom GUI Application
# Clean, minimal interface with centered logo and modern design
# ==============================================================================

# Suppress console output for cleaner GUI launch
import sys
import os
if hasattr(sys, 'frozen') or os.environ.get('PYTHONW_LAUNCHER'):
    # Redirect stdout/stderr to null when running as frozen app or pythonw
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# ==================== IMPORTS ====================
import re
import json
import html
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel,
                            QScrollArea, QFrame, QSplashScreen, QGraphicsOpacityEffect,
                            QMenu, QInputDialog, QCheckBox, QDialog, QComboBox, QStackedWidget,
                            QSizePolicy, QFileDialog, QSystemTrayIcon, QListWidget, QListWidgetItem, QGridLayout, QSlider, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPointF, QEvent, QUrl, QPoint
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPainter, QColor, QMovie, QPolygonF, QImage, QShortcut, QKeySequence, QDesktopServices, QCursor

# Import FreesIA
import importlib.util
spec = importlib.util.spec_from_file_location("project_freesia", Path(__file__).parent / "Project FreesIA.py")
project_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project_module)
FreesIA = project_module.FreesIA


# ==================== THEME ====================
# Centralized color tokens instead of hardcoded hex scattered across ~140
# setStyleSheet() calls. Widgets built with THEME[...] pick up light/dark
# automatically; toggling in Settings persists the preference and applies on
# next launch (this app's existing pattern for settings that affect broad
# styling, same as personality mode).

LIGHT_THEME = {
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F5F5F5",
    "bg_tertiary": "#F0F0F0",
    "bubble_user": "#E8E8E8",
    "bubble_ai": "#ECECEC",
    "bubble_ai_border": "#D8D8D8",
    "border": "#E0E0E0",
    "border_strong": "#D0D0D0",
    "text_primary": "#1A1A1A",
    "text_secondary": "#6B6B6B",
    "text_muted": "#8A8A8A",
    "hover": "#ECECEC",
    "hover_strong": "#E4E4E4",
    "accent_bg": "#1A1A1A",
    "accent_text": "#FFFFFF",
    "accent": "#8A6F3B",
    "scrollbar_handle": "rgba(0, 0, 0, 0.15)",
    "scrollbar_handle_hover": "rgba(0, 0, 0, 0.3)",
}

DARK_THEME = {
    "bg_primary": "#18181B",
    "bg_secondary": "#131316",
    "bg_tertiary": "#222228",
    "bubble_user": "#2E2E37",
    "bubble_ai": "#222228",
    "bubble_ai_border": "#2C2C34",
    "border": "#2A2A31",
    "border_strong": "#3A3A44",
    "text_primary": "#ECECF1",
    "text_secondary": "#B0B0BB",
    "text_muted": "#9797A3",
    "hover": "#25252C",
    "hover_strong": "#2F2F38",
    "accent_bg": "#E8E8EE",
    "accent_text": "#18181B",
    "accent": "#C9B79C",
    "scrollbar_handle": "rgba(255, 255, 255, 0.15)",
    "scrollbar_handle_hover": "rgba(255, 255, 255, 0.3)",
}


def load_dark_mode_setting() -> bool:
    try:
        gui_settings_file = Path.home() / ".freesia" / "gui_settings.json"
        if gui_settings_file.exists():
            with open(gui_settings_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('dark_mode_enabled', True)
    except Exception:
        pass
    return True


def save_dark_mode_setting(enabled: bool):
    try:
        config_dir = Path.home() / ".freesia"
        config_dir.mkdir(exist_ok=True)
        with open(config_dir / "gui_settings.json", 'w', encoding='utf-8') as f:
            json.dump({'dark_mode_enabled': enabled}, f)
    except Exception as e:
        print(f"Couldn't save GUI settings: {e}")


THEME = DARK_THEME if load_dark_mode_setting() else LIGHT_THEME

AI_NAME = "FreesIA"  # what the assistant is called; set from the backend at start-up and in Settings -> Persona


def set_ai_name(name: str):
    global AI_NAME
    AI_NAME = (name or "").strip() or "FreesIA"


def themed_icon(path, color_hex: str = None) -> QIcon:
    """
    The icon assets (attach/mic/send/settings/profile) are solid black
    silhouettes on a transparent background - fine on the light theme, but
    invisible against a dark one. Recolors the icon's opaque pixels to the
    current theme's text color at load time instead of needing separate
    light/dark asset files.
    """
    color_hex = color_hex or THEME['text_primary']
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QIcon()
    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color_hex))
    painter.end()
    return QIcon(tinted)


def pin_icon(color_hex: str, size: int = 16) -> QIcon:
    """
    Draws a simple pushpin glyph (round head + pointed tip) directly via
    QPainter instead of using an emoji character - emoji glyphs render
    inconsistently (colorful, cartoonish, font-dependent) and don't take a
    theme color the way the rest of the app's flat monochrome icons do.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color_hex))
    painter.setPen(Qt.PenStyle.NoPen)

    head_d = size * 0.58
    painter.drawEllipse(QRectF((size - head_d) / 2, 0, head_d, head_d))

    cx = size / 2
    tip = QPolygonF([
        QPointF(cx - head_d * 0.2, head_d * 0.8),
        QPointF(cx + head_d * 0.2, head_d * 0.8),
        QPointF(cx, size),
    ])
    painter.drawPolygon(tip)
    painter.end()
    return QIcon(pixmap)


def avatar_label(size: int = 40, text: str = None) -> QLabel:
    """Round monogram avatar used in the chat header, intro and right panel."""
    text = text or (AI_NAME[:1].upper() or "F")
    label = QLabel(text)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(f"""
        QLabel {{
            background-color: {THEME['bubble_user']};
            border: 1px solid {THEME['border_strong']};
            border-radius: {size // 2}px;
            color: {THEME['accent']};
            font-weight: bold;
            font-size: {max(11, int(size * 0.34))}px;
        }}
    """)
    return label


try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:  # QtSvg ships with the PyQt6 wheel; guard anyway
    QSvgRenderer = None

# 24x24 line icons (stroke = the colour passed in, round caps/joins).
_ICON_SVG = {
    "image":      '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 8"/>',
    "mic":        '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "arrow-up":   '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "stop":       '<rect x="7" y="7" width="10" height="10" rx="2.2" fill="currentColor"/>',
    "plus":       '<path d="M12 5v14M5 12h14"/>',
    "user":       '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    "settings":   '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "panel-left": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
    "panel-right":'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M15 4v16"/>',
    "dots":       '<circle cx="12" cy="5" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="19" r="1.5" fill="currentColor"/>',
    "pencil":     '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "refresh":    '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    "thumb-down": '<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>',
    "chev-left":  '<path d="M15 6l-6 6 6 6"/>',
    "chev-right": '<path d="M9 6l6 6-6 6"/>',
    "chev-down":  '<path d="M6 9l6 6 6-6"/>',
    "close":      '<path d="M6 6l12 12M18 6L6 18"/>',
    "book":       '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 5.5v16"/>',
    "trash":      '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/>',
    "download":   '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "clock":      '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "copy":       '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    "star":       '<path d="M12 3l2.7 5.7 6.3.8-4.6 4.3 1.2 6.2L12 17l-5.6 3 1.2-6.2L3 9.5l6.3-.8z"/>',
    "pin":        '<circle cx="12" cy="8" r="6"/><path d="M9 14l3 8 3-8"/>',
    "message":    '<path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12z"/>',
    "sliders":    '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "bolt":       '<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>',
    "grid":       '<rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/>',
    "shield":     '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/>',
    "folder":     '<path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/>',
    "power":      '<path d="M12 3v9M6.4 6.4a8 8 0 1 0 11.2 0"/>',
    "cpu":        '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "upload":     '<path d="M12 4v11M7 9l5-5 5 5M5 20h14"/>',
    "sparkle":    '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
    "activity":   '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "search":     '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
}
_ICON_CACHE = {}


def line_pixmap(name: str, color_hex: str = None, size: int = 18, stroke: float = 1.8) -> QPixmap:
    """Crisp vector icon rendered at 2x for HiDPI. Returns an empty pixmap if the icon/QtSvg is unavailable."""
    from PyQt6.QtCore import QByteArray
    color_hex = color_hex or THEME['text_primary']
    key = (name, color_hex, size, stroke)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.GlobalColor.transparent)
    body = _ICON_SVG.get(name)
    if body and QSvgRenderer is not None:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color_hex}" '
               f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
               f'{body.replace("currentColor", color_hex)}</svg>')
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
    pm.setDevicePixelRatio(dpr)
    _ICON_CACHE[key] = pm
    return pm


def line_icon(name: str, color_hex: str = None, size: int = 18, stroke: float = 1.8) -> QIcon:
    return QIcon(line_pixmap(name, color_hex, size, stroke))


def app_logo_pixmap(width: int, emblem_only: bool = False) -> QPixmap:
    """The FreesIA logo (transparent PNG; white variant on the dark theme),
    trimmed to its artwork. emblem_only drops the FREESIA wordmark below it."""
    from PyQt6.QtGui import QBitmap, QRegion
    logo_name = "FreesIA Logo white.png" if THEME is DARK_THEME else "FreesIA Logo.png"
    image = QImage(str(Path(__file__).parent / logo_name))
    if image.isNull():
        return QPixmap()
    box = QRegion(QBitmap.fromImage(image.createAlphaMask())).boundingRect()
    if box.isEmpty():
        return QPixmap()
    if emblem_only:
        box.setHeight(int(box.height() * 0.83))
    return QPixmap.fromImage(image.copy(box)).scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)


def themed_scrollbar_css() -> str:
    """Thin, minimal vertical scrollbar matching the main chat area's - shared so every scroll area in the app looks consistent."""
    return f"""
        QScrollBar:vertical {{
            background-color: transparent;
            width: 6px;
            margin: 2px 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {THEME['scrollbar_handle']};
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {THEME['scrollbar_handle_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
    """


# ==================== LOADING THREAD ====================

class LoadingThread(QThread):
    """Load FreesIA in background"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("Initializing FreesIA...")
            assistant = FreesIA()
            self.progress.emit("Ready!")
            self.finished.emit(assistant)
        except Exception as e:
            import traceback
            error_message = f"Error: {str(e)}\n" + traceback.format_exc()
            # Log error to file
            with open(str(Path(__file__).parent / "freesia_error.log"), "w", encoding="utf-8") as f:
                f.write(error_message)
            self.progress.emit(error_message)
            self.finished.emit(None)


class RescanAppsThread(QThread):
    """
    Run the (slow-ish, ~2-3s) full app rescan off the UI thread so Settings
    doesn't freeze while it runs.
    """
    finished = pyqtSignal(int)

    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant

    def run(self):
        self.assistant.rescan_apps()
        self.finished.emit(len(self.assistant.installed_apps))


class RescanFoldersThread(QThread):
    """Run the Desktop folder rescan off the UI thread, mirroring RescanAppsThread."""
    finished = pyqtSignal(int)

    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant

    def run(self):
        count = self.assistant.rescan_folders()
        self.finished.emit(count)


# ==================== CHECK-INS (the assistant messages first) ====================
import time as _time
import random as _random

CHECKIN_FILE = Path.home() / ".freesia" / "checkin.json"
CHECKIN_DEFAULTS = {"enabled": False, "frequency": "sometimes", "quiet_start": "23:00", "quiet_end": "08:00",
                    "hold_fullscreen": True, "notify": True, "unanswered": 0}
CHECKIN_MINUTES = {"rarely": 480, "sometimes": 180, "often": 75}
CHECKIN_IDLE_MIN = 25  # never check in right after you were chatting


def load_checkin_cfg() -> dict:
    cfg = dict(CHECKIN_DEFAULTS)
    try:
        with open(CHECKIN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, default in CHECKIN_DEFAULTS.items():
                v = data.get(k, default)
                if isinstance(default, bool):
                    cfg[k] = v if isinstance(v, bool) else default
                elif isinstance(default, int):
                    cfg[k] = v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else default
                else:
                    cfg[k] = v if isinstance(v, str) else default
    except Exception:
        pass
    if cfg["frequency"] not in CHECKIN_MINUTES:
        cfg["frequency"] = "sometimes"
    for k in ("quiet_start", "quiet_end"):
        if _hhmm_to_min(cfg[k]) is None:
            cfg[k] = CHECKIN_DEFAULTS[k]
    return cfg


def save_checkin_cfg(cfg: dict):
    try:
        CHECKIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CHECKIN_FILE, "w", encoding="utf-8") as f:
            json.dump({k: cfg.get(k, d) for k, d in CHECKIN_DEFAULTS.items()}, f, indent=2)
    except Exception:
        pass


def _hhmm_to_min(s):
    try:
        h, m = str(s).split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h * 60 + m
    except Exception:
        pass
    return None


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    s, e = _hhmm_to_min(start), _hhmm_to_min(end)
    if s is None or e is None or s == e:
        return False
    cur = now.hour * 60 + now.minute
    return (s <= cur < e) if s < e else (cur >= s or cur < e)


def fullscreen_app_running(own_hwnd: int = 0) -> bool:
    """True when the foreground window covers its whole monitor (a game / video / presentation). Windows only."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        u.GetForegroundWindow.restype = wintypes.HWND
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        hwnd = u.GetForegroundWindow()
        if not hwnd or (own_hwnd and int(hwnd) == int(own_hwnd)):
            return False
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False
        rect = wintypes.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(mi)):
            return False
        m = mi.rcMonitor
        return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    except Exception:
        return False


def _hour_label(h: int) -> str:
    return f"{(h % 12) or 12}:00 {'AM' if h < 12 else 'PM'}"


class CheckinThread(QThread):
    """Writes one check-in line off the UI thread."""
    done = pyqtSignal(str)

    def __init__(self, assistant, recent, when):
        super().__init__()
        self.assistant, self.recent, self.when = assistant, recent, when

    def run(self):
        try:
            text = self.assistant.generate_checkin(self.recent, self.when)
        except Exception:
            text = "Still up?"
        self.done.emit(text or "Still up?")


class VoiceJobThread(QThread):
    """Voice engine install / voice download / preview, off the UI thread."""
    progress = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, voice, kind, key=None):
        super().__init__()
        self.voice, self.kind, self.key = voice, kind, key

    def run(self):
        try:
            if self.kind == "install":
                import subprocess
                if getattr(sys, "frozen", False):
                    raise RuntimeError("This build can't install packages. Run: pip install piper-tts")
                flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
                self.progress.emit("Installing the voice engine...")
                r = subprocess.run([sys.executable, "-m", "pip", "install", "piper-tts"], capture_output=True,
                                   text=True, creationflags=flags)
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or r.stdout or "pip failed").strip().splitlines()[-1][:200])
                import importlib
                importlib.invalidate_caches()
                self.done.emit(True, "Voice engine installed")
            elif self.kind == "download":
                def cb(done, total):
                    pct = f" {done * 100 // total}%" if total else ""
                    self.progress.emit(f"Downloading voice...{pct}")
                self.voice.download(self.key, cb)
                self.done.emit(True, "Voice downloaded")
            else:  # preview
                ok = self.voice.preview(self.key)
                self.done.emit(bool(ok), "" if ok else (self.voice.last_error or "Couldn't play this voice"))
        except Exception as e:
            self.done.emit(False, str(e)[:200] or "Failed")


class ChatTitleThread(QThread):
    """Generate a short auto-title from the opening exchange, off the UI thread."""
    finished = pyqtSignal(str, str)  # chat_id, title

    def __init__(self, assistant, chat_id, first_message, first_response=""):
        super().__init__()
        self.assistant = assistant
        self.chat_id = chat_id
        self.first_message = first_message
        self.first_response = first_response

    def run(self):
        title = self.assistant.generate_chat_title(self.first_message, self.first_response)
        self.finished.emit(self.chat_id, title)


class MemoryExtractThread(QThread):
    """Fire-and-forget: check one exchange for a fact worth remembering across future chats."""
    def __init__(self, assistant, user_message, ai_response):
        super().__init__()
        self.assistant = assistant
        self.user_message = user_message
        self.ai_response = ai_response

    def run(self):
        self.assistant.maybe_remember(self.user_message, self.ai_response)


class ImageGenThread(QThread):
    """
    Run image generation or editing (FastSD CPU, seconds-to-a-minute+) off the
    UI thread. Pass source_image_path to edit an existing/uploaded image instead
    of generating a fresh one.
    """
    finished = pyqtSignal(dict)

    def __init__(self, assistant, prompt, source_image_path=None, size="square"):
        super().__init__()
        self.assistant = assistant
        self.prompt = prompt
        self.source_image_path = source_image_path
        self.size = size

    def run(self):
        if self.source_image_path:
            result = self.assistant.edit_image(self.prompt, self.source_image_path)
        else:
            clean_prompt, parsed_size, count, negative_prompt = self.assistant._parse_image_gen_options(self.prompt)
            # An explicit size word in the prompt itself wins; otherwise use the UI picker
            size = parsed_size if parsed_size != "square" else self.size
            result = self.assistant.generate_image(clean_prompt, size=size, count=count, negative_prompt=negative_prompt)
            result["prompt"] = clean_prompt
        self.finished.emit(result)


class ImageWarmupThread(QThread):
    """
    Fire-and-forget throwaway generation shortly after startup so the image
    model is already loaded into memory by the time the user asks for a real
    one, instead of eating the ~1min first-load cost on their first request.
    Silent: no UI bubble, failures (e.g. FastSD CPU not running yet) are just
    swallowed.
    """
    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant

    def run(self):
        try:
            result = self.assistant.generate_image("a simple gray circle", size="square")
            if result.get("success") and result.get("path"):
                warmup_path = result["path"]
                try:
                    Path(warmup_path).unlink()
                except Exception:
                    pass
                # generate_image() sets last_generated_image_path as a side
                # effect - undo that, otherwise the throwaway warmup circle
                # (now deleted) looks like "the last generated image" to any
                # follow-up "edit that image" request, and it 404s on a dead
                # path. Only clear it if it's still ours - if the user
                # generated a real image while warmup was still running, that
                # legitimate path must not get clobbered.
                if self.assistant.last_generated_image_path == warmup_path:
                    self.assistant.last_generated_image_path = None
                    self.assistant.last_image_gen_time = None
        except Exception:
            pass


# ==================== SPLASH SCREEN ====================

class SidebarResizeHandle(QFrame):
    """
    Thin draggable strip between the sidebar and the chat area, letting the
    user resize the sidebar to their liking.

    The sidebar has a Fixed horizontal size policy, so a Fixed-policy widget
    always renders at its sizeHint() clamped to [minimumWidth, maximumWidth]
    - raising maximumWidth alone doesn't grow it past sizeHint, only shrinking
    below sizeHint actually has any visible effect. So dragging wider did
    nothing. Pinning minimumWidth == maximumWidth to the exact target width
    while dragging forces the real rendered size in both directions.
    """
    MIN_WIDTH = 180
    MAX_WIDTH = 480

    def __init__(self, sidebar, main_window):
        super().__init__()
        self.sidebar = sidebar
        self.main_window = main_window
        self.setFixedWidth(6)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setStyleSheet("QFrame { background-color: transparent; }")
        self._dragging = False

    def enterEvent(self, event):
        self.setStyleSheet("QFrame { background-color: #C8C8C8; }")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._dragging:
            self.setStyleSheet("QFrame { background-color: transparent; }")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            sidebar_left = self.sidebar.mapToGlobal(self.sidebar.rect().topLeft()).x()
            new_width = int(event.globalPosition().x() - sidebar_left)
            new_width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, new_width))
            self.sidebar.setMinimumWidth(new_width)
            self.sidebar.setMaximumWidth(new_width)
            self.main_window.sidebar_width = new_width
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self.setStyleSheet("QFrame { background-color: transparent; }")
        super().mouseReleaseEvent(event)


class SplashScreen(QWidget):
    """Loading splash screen"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set splash screen size and center it
        splash_width = 600
        splash_height = 500
        self.setFixedSize(splash_width, splash_height)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - splash_width) // 2
        y = (screen.height() - splash_height) // 2
        self.move(x, y)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo (already contains FreesIA text)
        logo_path = Path(__file__).parent / "FreesIA Logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("margin-bottom: 40px;")
            layout.addWidget(logo_label)
        
        # Loading spinner (using text animation)
        self.spinner = QLabel("◐")
        self.spinner.setStyleSheet("""
            font-size: 32px;
            color: #6B6B6B;
        """)
        self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.spinner)
        
        # Loading text
        self.status_label = QLabel("Loading Assets... This might take awhile...")
        self.status_label.setStyleSheet("""
            font-size: 14px;
            color: #6B6B6B;
            margin-top: 20px;
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
            }
        """)
        
        # Animate spinner
        self.spinner_chars = ['◐', '◓', '◑', '◒']
        self.spinner_index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_spinner)
        self.timer.start(150)
    
    def update_spinner(self):
        """Animate the loading spinner"""
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        self.spinner.setText(self.spinner_chars[self.spinner_index])
    
    def update_status(self, text):
        """Update status text"""
        self.status_label.setText(text)


# ==================== AI THREAD (STREAMING RESPONSES) ====================

class AIThread(QThread):
    """Process AI requests in background with streaming"""
    response = pyqtSignal(str)
    chunk = pyqtSignal(str)  # New signal for streaming chunks
    finished_streaming = pyqtSignal(str)  # Signal when streaming completes with full text
    
    def __init__(self, assistant, message, original_message=None, extra_instruction=""):
        super().__init__()
        self.assistant = assistant
        self.message = message
        self.original_message = original_message or message  # Store original before context added
        self.extra_instruction = extra_instruction  # one-time nudge for just this call, e.g. a dodge-retry
        self._is_running = True

    def stop(self):
        """
        Signal the streaming loop to stop after the current chunk. Was called
        from two places (new_chat, send_message) but never actually defined -
        those calls would have raised AttributeError whenever a user started a
        new chat while a response was still streaming.
        """
        self._is_running = False

    def run(self):
        try:
            if not self._is_running:
                return
            
            # Collect full response while streaming
            full_response = ""
            
            # Use original message for streaming (without context) to detect quick responses and proper model selection
            for chunk_text in self.assistant.chat_with_ai_streaming(
                self.message, original_message=self.original_message, extra_instruction=self.extra_instruction
            ):
                if not self._is_running:
                    return
                full_response += chunk_text
                self.chunk.emit(chunk_text)
            
            # Emit the full response (not empty string)
            self.finished_streaming.emit(full_response)
        except Exception as e:
            self.response.emit(f"Error: {str(e)}")
# Move main() to the bottom of the file

def main():
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()

    def on_loading_finished(assistant):
        splash.close()
        if assistant is None:
            # Show error dialog if loading failed
            error_dialog = QDialog()
            error_dialog.setWindowTitle("FreesIA - Error")
            layout = QVBoxLayout(error_dialog)
            label = QLabel("Failed to initialize FreesIA. Please check your setup.\n\nSee freesia_error.log for details.")
            layout.addWidget(label)
            # Show error details if available
            try:
                with open(str(Path(__file__).parent / "freesia_error.log"), "r", encoding="utf-8") as f:
                    error_details = f.read()
                error_box = QTextEdit()
                error_box.setReadOnly(True)
                error_box.setText(error_details)
                error_box.setMinimumHeight(200)
                layout.addWidget(error_box)
            except Exception:
                pass
            error_dialog.exec()
            sys.exit(1)
        window = MainWindow(assistant)
        window.show()

    def on_progress(status):
        splash.update_status(status)

    # Start loading
    loader = LoadingThread()
    loader.finished.connect(on_loading_finished)
    loader.progress.connect(on_progress)
    loader.start()

    sys.exit(app.exec())

# ==================== UI COMPONENTS ====================

class _BubbleTextEdit(QTextEdit):
    """Read-only message text whose preferred width follows its content, so short
    messages get a snug bubble instead of the default 256px-wide text box.
    Also reports clicks on links (code-block Copy, URLs)."""
    link_clicked = pyqtSignal(str)
    want_width = 0

    def mouseMoveEvent(self, event):
        if self.isReadOnly():
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if self.anchorAt(event.pos()) else Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isReadOnly() and event.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            href = self.anchorAt(event.pos())
            if href:
                self.link_clicked.emit(href)
                return
        super().mouseReleaseEvent(event)

    def sizeHint(self):
        base = super().sizeHint()
        return QSize(self.want_width or base.width(), base.height())


class MessageBubble(QFrame):
    """Individual message bubble with code highlighting and copy support"""

    # Set once by MainWindow so every bubble supports "Pin Message" without
    # each of its many construction sites needing to wire on_pin individually.
    # An instance can still override self.on_pin if it ever needs different
    # pin behavior (e.g. the Chat Reader, which pins into a different source).
    default_on_pin = None

    def __init__(self, text, is_user=False, show_regen_controls=True):
        super().__init__()
        self.setObjectName("Bubble")
        self.setMaximumWidth(700)
        # Only as tall as its content - otherwise the chat column hands it all the spare height.
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.is_user = is_user
        self.on_edit = None  # set by caller for user bubbles to enable edit-and-resubmit
        self._editing = False
        self.on_reassign_speaker = None  # Chat Reader only: set to enable "Reassign Speaker"
        self._apply_bubble_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Message text with code highlighting - using QTextEdit for better copy/paste support
        self.msg_text = _BubbleTextEdit()
        self.msg_text.setReadOnly(True)
        from PyQt6.QtGui import QTextOption
        self.msg_text.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        # Auto-grow to fit content instead of scrolling internally - a fixed
        # height with a scrollbar inside a chat bubble reads as broken.
        self.msg_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.msg_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.msg_text.document().documentLayout().documentSizeChanged.connect(self._update_text_height)
        self.msg_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                color: {THEME['text_primary']};
                font-size: 15px;
                margin: 0px;
                padding: 0px;
            }}
            QTextEdit:focus {{
                border: none;
            }}
        """)
        # Enable text selection and copying via keyboard shortcuts
        self.msg_text.setCursor(Qt.CursorShape.IBeamCursor)
        self._code_blocks = []
        self.msg_text.link_clicked.connect(self._on_link_clicked)
        self.set_text(text)
        layout.addWidget(self.msg_text)

        self.on_pin = None  # set by caller to override the default pin behavior (e.g. Chat Reader)
        self.msg_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.msg_text.customContextMenuRequested.connect(self._show_context_menu)

        self.pin_id = None
        # A floating circular badge in the bubble's top-right corner, not
        # part of the vertical layout - positioned manually (see
        # _position_pin_btn/resizeEvent) so it overlays the corner instead
        # of taking up a row of its own.
        self.pin_btn = QPushButton(self)
        self.pin_btn.setFixedSize(22, 22)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setIconSize(QSize(11, 11))
        self.pin_btn.clicked.connect(self._trigger_pin)
        self._update_pin_btn_style()
        self._position_pin_btn(self.maximumWidth())  # best-effort placement before any real resizeEvent lands
        self.pin_btn.raise_()

        self.response_versions = None
        self.version_index = 0
        self.on_version_change = None  # set by caller to persist history when the user flips versions
        self.prev_btn = None
        self.next_btn = None
        self.version_label = None
        self.regen_btn = None
        self.on_regenerate = None

        self.edit_btn = None
        self.edit_actions_row = None
        if is_user:
            self.edit_btn = QPushButton()
            self.edit_btn.setIcon(line_icon("pencil", THEME['text_muted'], 14))
            self.edit_btn.setIconSize(QSize(14, 14))
            self.edit_btn.setFixedSize(22, 22)
            self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.edit_btn.setToolTip("Edit message")
            self.edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    color: {THEME['text_muted']};
                    font-size: 12px;
                }}
                QPushButton:hover {{ color: {THEME['text_primary']}; }}
            """)
            self.edit_btn.clicked.connect(self.start_editing)
            edit_row = QHBoxLayout()
            edit_row.addStretch()
            edit_row.addWidget(self.edit_btn)
            layout.addLayout(edit_row)

        if not is_user and show_regen_controls:
            self.response_versions = [text]
            self.version_index = 0

            self.regen_btn = QPushButton()
            self.regen_btn.setIcon(line_icon("refresh", THEME['text_muted'], 15))
            self.regen_btn.setIconSize(QSize(15, 15))
            self.regen_btn.setFixedSize(22, 22)
            self.regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.regen_btn.setToolTip("Regenerate response")
            nav_btn_style = f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    color: {THEME['text_muted']};
                    font-size: 13px;
                }}
                QPushButton:hover {{ color: {THEME['text_primary']}; }}
                QPushButton:disabled {{ color: {THEME['border_strong']}; }}
            """
            self.regen_btn.setStyleSheet(nav_btn_style)
            self.regen_btn.clicked.connect(self._trigger_regenerate)

            self.prev_btn = QPushButton()
            self.prev_btn.setIcon(line_icon("chev-left", THEME['text_muted'], 14))
            self.prev_btn.setIconSize(QSize(14, 14))
            self.prev_btn.setFixedSize(20, 22)
            self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.prev_btn.setToolTip("Previous response")
            self.prev_btn.setStyleSheet(nav_btn_style)
            self.prev_btn.clicked.connect(self.show_prev_version)

            self.version_label = QLabel("1/1")
            self.version_label.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 11px; background: transparent; }}")

            self.next_btn = QPushButton()
            self.next_btn.setIcon(line_icon("chev-right", THEME['text_muted'], 14))
            self.next_btn.setIconSize(QSize(14, 14))
            self.next_btn.setFixedSize(20, 22)
            self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.next_btn.setToolTip("Next response")
            self.next_btn.setStyleSheet(nav_btn_style)
            self.next_btn.clicked.connect(self.show_next_version)

            regen_row = QHBoxLayout()
            self.flag_btn = QPushButton()
            self.flag_btn.setIcon(line_icon("thumb-down", THEME['text_muted'], 14))
            self.flag_btn.setIconSize(QSize(14, 14))
            self.flag_btn.setFixedSize(22, 22)
            self.flag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.flag_btn.setToolTip("That was a dodge - regenerate with a stronger nudge to be decisive")
            self.flag_btn.setStyleSheet(nav_btn_style)
            self.flag_btn.clicked.connect(self._trigger_flag_dodge)
            self.on_flag_dodge = None  # set by caller: fn() - no argument, doesn't dictate content

            self.copy_btn = QPushButton()
            self.copy_btn.setIcon(line_icon("copy", THEME['text_muted'], 15))
            self.copy_btn.setIconSize(QSize(15, 15))
            self.copy_btn.setFixedSize(22, 22)
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.setToolTip("Copy message")
            self.copy_btn.setStyleSheet(nav_btn_style)
            self.copy_btn.clicked.connect(self._copy_whole_message)

            regen_row.addWidget(self.regen_btn)
            regen_row.addWidget(self.copy_btn)
            regen_row.addSpacing(6)
            regen_row.addWidget(self.prev_btn)
            regen_row.addWidget(self.version_label)
            regen_row.addWidget(self.next_btn)
            regen_row.addSpacing(6)
            regen_row.addWidget(self.flag_btn)
            regen_row.addStretch()
            layout.addLayout(regen_row)
            self._update_version_nav()

    def _copy_whole_message(self):
        try:
            raw = self.response_versions[self.version_index] if self.response_versions else self.msg_text.toPlainText()
        except Exception:
            raw = self.msg_text.toPlainText()
        QApplication.clipboard().setText(raw)
        from PyQt6.QtWidgets import QToolTip
        QToolTip.showText(QCursor.pos(), "Copied", self.copy_btn)

    def _trigger_flag_dodge(self):
        if self.on_flag_dodge:
            self.on_flag_dodge()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.msg_text.document().setTextWidth(self.msg_text.viewport().width())
        self._update_text_height()
        self._position_pin_btn()

    def _position_pin_btn(self, width=None):
        w = width if width is not None else self.width()
        self.pin_btn.move(max(0, w - self.pin_btn.width() - 6), 6)

    def _update_text_height(self):
        doc_height = self.msg_text.document().size().height()
        self.msg_text.setFixedHeight(int(doc_height) + 8)

    def _trigger_regenerate(self):
        if self.on_regenerate:
            self.on_regenerate()

    def _update_version_nav(self):
        if not self.response_versions:
            return
        total = len(self.response_versions)
        self.version_label.setText(f"{self.version_index + 1}/{total}")
        self.prev_btn.setEnabled(self.version_index > 0)
        self.next_btn.setEnabled(self.version_index < total - 1)
        self.prev_btn.setVisible(total > 1)
        self.next_btn.setVisible(total > 1)
        self.version_label.setVisible(total > 1)

    def show_prev_version(self):
        if self.version_index > 0:
            self.version_index -= 1
            self._apply_current_version()

    def show_next_version(self):
        if self.version_index < len(self.response_versions) - 1:
            self.version_index += 1
            self._apply_current_version()

    def _apply_current_version(self):
        text = self.response_versions[self.version_index]
        self.set_text(text)
        self._update_version_nav()
        if self.on_version_change:
            self.on_version_change(text)

    def add_version(self, text: str):
        """Register a freshly-regenerated response and switch to showing it."""
        self.response_versions.append(text)
        self.version_index = len(self.response_versions) - 1
        self.set_text(text)
        self._update_version_nav()

    def start_editing(self):
        self._editing = True
        self.edit_btn.hide()
        self.msg_text.setReadOnly(False)
        self.msg_text.setPlainText(self._raw_text)
        self.msg_text.setFocus()
        cursor = self.msg_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.msg_text.setTextCursor(cursor)

        if self.edit_actions_row is None:
            self.edit_actions_row = QHBoxLayout()
            cancel_btn = QPushButton("Cancel")
            save_btn = QPushButton("Save & Submit")
            for b in (cancel_btn, save_btn):
                b.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; border: none; color: {THEME['text_secondary']}; font-size: 12px; padding: 4px 8px; }}
                QPushButton:hover {{ color: {THEME['text_primary']}; }}
            """)
            save_btn.setStyleSheet(f"""
                QPushButton {{ background-color: {THEME['accent_bg']}; color: {THEME['accent_text']}; border: none; border-radius: 6px; font-size: 12px; padding: 4px 10px; }}
                QPushButton:hover {{ background-color: {THEME['hover_strong']}; }}
            """)
            cancel_btn.clicked.connect(self.cancel_edit)
            save_btn.clicked.connect(self.confirm_edit)
            self.edit_actions_row.addStretch()
            self.edit_actions_row.addWidget(cancel_btn)
            self.edit_actions_row.addWidget(save_btn)
            self.layout().addLayout(self.edit_actions_row)
        else:
            for i in range(self.edit_actions_row.count()):
                w = self.edit_actions_row.itemAt(i).widget()
                if w:
                    w.show()

    def cancel_edit(self):
        self._editing = False
        self.msg_text.setReadOnly(True)
        self.set_text(self._raw_text)
        self._hide_edit_actions()
        if self.edit_btn:
            self.edit_btn.show()

    def confirm_edit(self):
        new_text = self.msg_text.toPlainText().strip()
        self._editing = False
        self.msg_text.setReadOnly(True)
        self._hide_edit_actions()
        if new_text and new_text != self._raw_text and self.on_edit:
            self.set_text(new_text)
            self.on_edit(new_text)
        else:
            self.set_text(self._raw_text)

    def _hide_edit_actions(self):
        if self.edit_actions_row:
            for i in range(self.edit_actions_row.count()):
                w = self.edit_actions_row.itemAt(i).widget()
                if w:
                    w.hide()

    def set_text(self, text):
        """Set text with code block highlighting"""
        self._raw_text = text
        # Detect and highlight code blocks
        formatted_text = self.format_code_blocks(text)
        self.msg_text.setHtml(formatted_text)
        self._update_want_width()

    def _on_link_clicked(self, href: str):
        from PyQt6.QtWidgets import QToolTip
        if href.startswith("copy:"):
            try:
                QApplication.clipboard().setText(self._code_blocks[int(href[5:])])
                QToolTip.showText(QCursor.pos(), "Copied")
            except Exception:
                pass
        elif href.startswith(("http://", "https://")):
            QDesktopServices.openUrl(QUrl(href))

    def _update_want_width(self):
        """Preferred text width = the longest unwrapped line (capped), so the bubble hugs short messages."""
        try:
            te = self.msg_text
            te.ensurePolished()
            probe = te.document().clone()
            probe.setTextWidth(-1)
            te.want_width = int(min(max(probe.idealWidth() + 14, 48), 640))
            te.updateGeometry()
            self.updateGeometry()
        except Exception:
            pass

    def set_pinned(self, pin_id):
        """pin_id: the pin's id string, or None to mark this bubble unpinned."""
        self.pin_id = pin_id
        self._update_pin_btn_style()

    def _update_pin_btn_style(self):
        pinned = self.pin_id is not None
        glyph_color = THEME['bg_primary'] if pinned else THEME['text_muted']
        bg_color = THEME['text_primary'] if pinned else "rgba(128, 128, 128, 0.15)"
        hover_bg = THEME['text_primary'] if pinned else "rgba(128, 128, 128, 0.3)"
        self.pin_btn.setIcon(pin_icon(glyph_color))
        self.pin_btn.setToolTip("Unpin message" if pinned else "Pin message")
        self.pin_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                border: none;
                border-radius: 11px;
            }}
            QPushButton:hover {{ background-color: {hover_bg}; }}
        """)

    def _trigger_pin(self):
        pin_handler = self.on_pin or MessageBubble.default_on_pin
        if pin_handler:
            pin_handler(self)

    def _apply_bubble_style(self):
        """AI bubble gets a border since its fill color was too close to the page background to read as a distinct bubble."""
        if self.is_user:
            self.setStyleSheet(f"""
                QFrame#Bubble {{
                    background-color: {THEME['bubble_user']};
                    border-radius: 20px;
                    border-top-right-radius: 6px;
                    padding: 12px 18px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#Bubble {{
                    background-color: {THEME['bubble_ai']};
                    border: 1px solid {THEME['bubble_ai_border']};
                    border-radius: 20px;
                    border-top-left-radius: 6px;
                    padding: 12px 18px;
                }}
            """)

    def set_is_user(self, is_user: bool):
        """Chat Reader only: re-style a bubble in place after Reassign Speaker changes who it belongs to."""
        self.is_user = is_user
        self._apply_bubble_style()

    def _show_context_menu(self, pos):
        """Standard copy/select-all menu, plus Pin/Unpin Message when on_pin is wired up."""
        menu = self.msg_text.createStandardContextMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {THEME['bg_primary']};
                border: 1px solid {THEME['border_strong']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
                color: {THEME['text_primary']};
            }}
            QMenu::item:selected {{
                background-color: {THEME['bg_tertiary']};
            }}
        """)
        pin_handler = self.on_pin or MessageBubble.default_on_pin
        pin_action = None
        reassign_action = None
        if pin_handler or self.on_reassign_speaker:
            menu.addSeparator()
        if pin_handler:
            pin_action = menu.addAction("Unpin Message" if self.pin_id else "Pin Message")
        if self.on_reassign_speaker:
            reassign_action = menu.addAction("Reassign Speaker")
        action = menu.exec(self.msg_text.mapToGlobal(pos))
        if pin_action is not None and action == pin_action:
            pin_handler(self)
        elif reassign_action is not None and action == reassign_action:
            self.on_reassign_speaker(self)

    def append_text(self, text):
        """Append text for streaming (without formatting until complete)"""
        current = self.msg_text.toPlainText()
        self.msg_text.setPlainText(current + text)

    def sync_first_version(self, text: str):
        """
        Streaming builds up the shown text via append_text() outside of
        add_version() - call once streaming finishes so response_versions[0]
        matches what's actually displayed (it starts as "" at construction).
        """
        if self.response_versions:
            self.response_versions[0] = text
    
    _CODE_TOKEN = re.compile(
        r"(?P<comment>#[^\n]*|//[^\n]*)"
        r"|(?P<string>\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"
        r"|(?P<number>\b\d+(?:\.\d+)?\b)"
        r"|(?P<word>\b[A-Za-z_][A-Za-z_0-9]*\b)")
    _CODE_KEYWORDS = {
        "def", "class", "return", "if", "elif", "else", "for", "while", "in", "import", "from", "as", "with",
        "try", "except", "finally", "raise", "lambda", "None", "True", "False", "and", "or", "not", "is",
        "pass", "break", "continue", "yield", "async", "await", "global", "const", "let", "var", "function",
        "new", "this", "switch", "case", "default", "throw", "catch", "null", "true", "false", "int", "void",
        "public", "private", "static", "struct", "enum", "fn", "mut", "use", "impl", "echo", "SELECT", "FROM", "WHERE"}
    _CODE_BUILTINS = {"print", "range", "len", "str", "int", "float", "list", "dict", "set", "open", "self",
                      "console", "log", "printf", "input", "type", "min", "max", "sum", "enumerate", "zip"}

    def _code_colors(self):
        if THEME is DARK_THEME:
            return {"bg": "#16161A", "bar": "#1C1C21", "border": "#2A2A31", "text": "#ECECF1", "muted": "#9797A3",
                    "keyword": "#C9B79C", "string": "#9FD3A8", "comment": "#6E6E7A", "func": "#8FB8F0", "number": "#E0A97D"}
        return {"bg": "#F4F4F6", "bar": "#EAEAEE", "border": "#D8D8DE", "text": "#1A1A1A", "muted": "#6B6B6B",
                "keyword": "#8A6F3B", "string": "#2E7D4F", "comment": "#8A8A8A", "func": "#2F6DB5", "number": "#B5651D"}

    def _highlight_code(self, code_escaped, colors):
        def repl(m):
            kind = m.lastgroup
            text = m.group(0)
            if kind == "word":
                if text in self._CODE_KEYWORDS:
                    return f'<span style="color:{colors["keyword"]}">{text}</span>'
                if text in self._CODE_BUILTINS:
                    return f'<span style="color:{colors["func"]}">{text}</span>'
                return text
            return f'<span style="color:{colors[kind]}">{text}</span>'
        out = self._CODE_TOKEN.sub(repl, code_escaped)
        # Qt rich text collapses spaces: keep indentation and line breaks explicit
        lines = out.split("\n")
        fixed = []
        for line in lines:
            stripped = line.lstrip(" ")
            lead = len(line) - len(stripped)
            fixed.append("&nbsp;" * lead + stripped.replace("  ", "&nbsp; "))
        return "<br>".join(fixed)

    def format_code_blocks(self, text):
        """Format code blocks (bar with language + Copy link, monospace, light highlighting)."""
        import html as _html
        colors = self._code_colors()
        self._code_blocks = []
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        stash = []

        def replace_code(match):
            code = match.group(1).strip("\n")
            lines = code.split('\n')
            lang = ''
            if lines and ' ' not in lines[0].strip() and 0 < len(lines[0].strip()) < 20 and len(lines) > 1:
                lang = lines[0].strip()
                code = '\n'.join(lines[1:])
            code = code.strip("\n")
            idx = len(self._code_blocks)
            self._code_blocks.append(_html.unescape(code))
            body = self._highlight_code(code, colors)
            block = (
                f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:8px; margin-bottom:6px;">'
                f'<tr><td bgcolor="{colors["bar"]}" style="padding:6px 12px;"><span style="color:{colors["muted"]}; font-size:12px;">{lang or "code"}</span></td>'
                f'<td bgcolor="{colors["bar"]}" align="right" style="padding:6px 12px;"><a href="copy:{idx}" style="color:{colors["muted"]}; text-decoration:none; font-size:12px;">Copy</a></td></tr>'
                f'<tr><td colspan="2" bgcolor="{colors["bg"]}" style="padding:10px 12px; color:{colors["text"]}; font-family:Consolas,\'JetBrains Mono\',monospace; font-size:13px;">{body}</td></tr>'
                f'</table>')
            stash.append(block)
            return f"\x00CODE{len(stash) - 1}\x00"

        text = re.sub(r'```([\s\S]*?)```', replace_code, text)
        text = re.sub(r'`([^`]+)`',
                      rf'<code style="background-color: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]}; font-family: Consolas, monospace; font-size: 13px;">\1</code>',
                      text)
        text = re.sub(r'(https?://[^\s<]+)', r'<a href="\1" style="color:' + THEME["accent"] + r'">\1</a>', text)
        text = text.replace('\n', '<br>')
        for i, block in enumerate(stash):
            text = text.replace(f"\x00CODE{i}\x00", block)
        return text


class ClickableImageLabel(QLabel):
    """QLabel that emits a signal on click - used to make chat thumbnails expandable"""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class ImageViewerDialog(QDialog):
    """
    Full-size view of a generated image, opened by clicking its chat thumbnail.
    Frameless (matches SettingsDialog) so it reads as an in-app overlay rather
    than a separate OS window popping up.
    """
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A1A;
                border: 1px solid #3A3A3A;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton()
        close_btn.setIcon(line_icon("close", "#FFFFFF", 16, 2.0))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 15px;
                border-radius: 14px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }
        """)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        pixmap = QPixmap(str(image_path))
        screen = QApplication.primaryScreen().geometry()
        max_w, max_h = int(screen.width() * 0.8), int(screen.height() * 0.8)
        scaled = pixmap.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)

        image_label = QLabel()
        image_label.setPixmap(scaled)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_label)

        self.resize(scaled.width() + 24, scaled.height() + 60)


class UploadedImagePreview(QFrame):
    """
    Small thumbnail bubble showing a photo the user attached for editing,
    placed above their message text (like ChatGPT/Grok show an uploaded
    image inline with the prompt) - so there's a visible record of what was
    uploaded once the pre-send attachment chip disappears.
    """
    def __init__(self, image_path, parent_window=None):
        super().__init__()
        self.image_path = Path(image_path)
        self.parent_window = parent_window
        self.setMaximumWidth(220)
        self.setStyleSheet(f"QFrame {{ background-color: {THEME['bubble_user']}; border-radius: 16px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.image_label = ClickableImageLabel()
        self.image_label.setFixedSize(200, 200)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.setStyleSheet(f"QLabel {{ background-color: {THEME['bg_primary']}; border-radius: 10px; }}")
        pixmap = QPixmap(str(self.image_path))
        scaled = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.clicked.connect(self.expand_image)
        layout.addWidget(self.image_label)

    def expand_image(self):
        dialog = ImageViewerDialog(self.image_path, self.parent_window)
        dialog.exec()


class ImageMessageBubble(QFrame):
    """
    Chat bubble for a generated image - click the thumbnail to view it full-size,
    plus Download, Regenerate (same prompt, new variation), and Delete actions.
    Editing happens by typing a follow-up message (like ChatGPT/Grok), not a
    button here - there's deliberately no in-bubble edit UI.
    """
    def __init__(self, image_path, prompt: str, assistant, parent_window=None, on_delete=None):
        super().__init__()
        self.image_path = Path(image_path)
        self.prompt = prompt
        self.assistant = assistant
        self.parent_window = parent_window
        self.on_delete = on_delete
        self._regen_thread = None

        self.setMaximumWidth(340)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_tertiary']};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.image_label = ClickableImageLabel()
        self.image_label.setFixedSize(300, 300)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.setStyleSheet(f"QLabel {{ background-color: {THEME['bg_primary']}; border-radius: 10px; }}")
        self.image_label.clicked.connect(self.expand_image)
        self._load_pixmap()
        layout.addWidget(self.image_label)

        caption = QLabel(prompt)
        caption.setWordWrap(True)
        caption.setStyleSheet(f"QLabel {{ color: {THEME['text_secondary']}; font-size: 12px; background: transparent; }}")
        layout.addWidget(caption)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.download_btn = self._make_icon_btn("⬇", "Download")  # ⬇
        self.download_btn.clicked.connect(self.download_image)
        self.regen_btn = self._make_icon_btn("⟳", "Regenerate (same prompt, new variation)")  # ⟳
        self.regen_btn.clicked.connect(self.regenerate_image)
        self.star_btn = self._make_icon_btn("★", "Star this image (starred images are kept when you clear the rest)")
        self.star_btn.clicked.connect(self.toggle_star)
        self.delete_btn = self._make_icon_btn("🗑", "Delete this image")
        self.delete_btn.clicked.connect(self.delete_image)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.regen_btn)
        btn_row.addWidget(self.star_btn)
        btn_row.addWidget(self.delete_btn)
        self._refresh_star()
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Size/ratio picker - clicking a different ratio regenerates this
        # image at that size (same prompt).
        self._ratio_labels = {"square": "1:1", "landscape": "16:9 H", "portrait": "16:9 V"}
        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(6)
        self.ratio_buttons = {}
        for key, label in self._ratio_labels.items():
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.clicked.connect(lambda checked=False, k=key: self.change_size(k))
            ratio_row.addWidget(btn)
            self.ratio_buttons[key] = btn
        ratio_row.addStretch()
        layout.addLayout(ratio_row)
        self._update_ratio_button_styles()

    def _update_ratio_button_styles(self):
        for key, btn in self.ratio_buttons.items():
            active = key == self.size_name
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME['accent_bg'] if active else THEME['hover_strong']};
                    color: {THEME['accent_text'] if active else THEME['text_secondary']};
                    border: none;
                    border-radius: 10px;
                    font-size: 11px;
                    padding: 3px 8px;
                }}
                QPushButton:hover {{ background-color: {THEME['text_muted'] if active else THEME['border_strong']}; }}
                QPushButton:disabled {{ color: {THEME['text_muted']}; }}
            """)

    def change_size(self, size_name: str):
        if size_name == self.size_name or not self.regen_btn.isEnabled():
            return
        self.regenerate_image(size_override=size_name)

    def _make_icon_btn(self, glyph: str, tooltip: str):
        btn = QPushButton()
        icon_name = {"⬇": "download", "⟳": "refresh", "🗑": "trash", "★": "star"}.get(glyph)
        if icon_name:
            btn.setIcon(line_icon(icon_name, THEME['text_primary'], 16))
            btn.setIconSize(QSize(16, 16))
        else:
            btn.setText(glyph)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(30, 30)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['hover_strong']};
                color: {THEME['text_primary']};
                border: none;
                border-radius: 15px;
                font-size: 15px;
            }}
            QPushButton:hover {{ background-color: {THEME['border_strong']}; }}
            QPushButton:disabled {{ color: {THEME['text_muted']}; }}
        """)
        return btn

    def _load_pixmap(self):
        pixmap = QPixmap(str(self.image_path))
        self.size_name = self.assistant._infer_size_name(pixmap.width(), pixmap.height())
        scaled = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def expand_image(self):
        dialog = ImageViewerDialog(self.image_path, self.parent_window)
        dialog.exec()

    def download_image(self):
        default_path = str(Path.home() / "Desktop" / self.image_path.name)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", default_path, "JPEG Image (*.jpg)"
        )
        if save_path:
            import shutil
            try:
                shutil.copy(str(self.image_path), save_path)
            except Exception as e:
                print(f"Couldn't save image: {e}")

    def regenerate_image(self, size_override: str = None):
        self.regen_btn.setEnabled(False)
        self.regen_btn.setIcon(line_icon("clock", THEME['text_muted'], 16))
        self.regen_btn.setToolTip("Generating...")
        for btn in self.ratio_buttons.values():
            btn.setEnabled(False)
        size = size_override or self.size_name
        self._regen_thread = ImageGenThread(self.assistant, self.prompt, size=size)
        self._regen_thread.finished.connect(self._on_regenerate_finished)
        self._regen_thread.start()

    def _on_regenerate_finished(self, result: dict):
        self.regen_btn.setEnabled(True)
        self.regen_btn.setIcon(line_icon("refresh", THEME['text_primary'], 16))
        self.regen_btn.setToolTip("Regenerate (same prompt, new variation)")
        for btn in self.ratio_buttons.values():
            btn.setEnabled(True)
        if result.get("success"):
            self.image_path = result["path"]
            self._load_pixmap()
            self._update_ratio_button_styles()
            self._refresh_star()
        else:
            self.regen_btn.setToolTip(f"Failed: {result.get('error', 'unknown error')}")

    def _is_starred(self) -> bool:
        try:
            return any(i["starred"] for i in self.assistant.list_generated_images() if Path(i["path"]) == Path(self.image_path))
        except Exception:
            return False

    def _refresh_star(self):
        on = self._is_starred()
        self.star_btn.setIcon(line_icon("star", THEME['accent'] if on else THEME['text_primary'], 16))
        self.star_btn.setToolTip("Starred - kept when you clear the rest" if on else "Star this image (starred images are kept when you clear the rest)")

    def toggle_star(self):
        try:
            self.assistant.set_image_starred(self.image_path, not self._is_starred())
        except Exception as e:
            print(f"Couldn't star image: {e}")
        self._refresh_star()

    def delete_image(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete Image", "Delete this image from disk?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if hasattr(self.assistant, "delete_generated_image"):
                self.assistant.delete_generated_image(self.image_path)
            elif self.image_path.exists():
                self.image_path.unlink()
        except Exception as e:
            print(f"Couldn't delete image: {e}")
            return
        if self.on_delete:
            self.on_delete(self)
        else:
            self.setParent(None)
            self.deleteLater()


class ChatInputBox(QTextEdit):
    """
    Multi-line chat input that shows the full message as it's typed (like
    Claude/ChatGPT) instead of a single-line QLineEdit scrolling
    horizontally. Auto-grows with content up to a max height, then scrolls.
    Enter sends (emits returnPressed, same signal name QLineEdit uses, so
    existing .returnPressed.connect(...) call sites don't need to change);
    Shift+Enter inserts a newline. text()/setText() shim QLineEdit's API so
    the rest of the codebase can keep treating this like one.
    """
    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._min_height = 40
        self._max_height = 160  # roughly 6 lines before it starts scrolling
        self.setFixedHeight(self._min_height)
        self.textChanged.connect(self._adjust_height)

    def keyPressEvent(self, event):
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if is_enter and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)

    def _adjust_height(self):
        doc_height = self.document().size().height()
        new_height = min(max(int(doc_height) + 16, self._min_height), self._max_height)
        self.setFixedHeight(new_height)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.setPlainText(text)


class LoadingBubble(QFrame):
    """Typing indicator: three softly pulsing dots in an AI-style bubble."""
    def __init__(self):
        super().__init__()
        self.setObjectName("TypingBubble")
        self.setFixedSize(76, 44)
        self.setStyleSheet(f"""
            QFrame#TypingBubble {{
                background-color: {THEME['bubble_ai']};
                border: 1px solid {THEME['bubble_ai_border']};
                border-radius: 20px;
                border-top-left-radius: 6px;
            }}
        """)
        self._phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(60)

    def _tick(self):
        self._phase = (self._phase + 0.09) % 1.0
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QColor(THEME['text_muted'])
        for i in range(3):
            t = (self._phase - i * 0.16) % 1.0
            wave = max(0.0, math.sin(t * math.pi * 2)) if t < 0.5 else 0.0
            c = QColor(base)
            c.setAlphaF(0.35 + 0.65 * wave)
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(24 + i * 14, 22 - 3 * wave), 3.5, 3.5)
        p.end()

    def stop_animation(self):
        """Stop the timer when removing the bubble"""
        if self.timer:
            self.timer.stop()


# ==================== CHAT HISTORY ITEM ====================

class ElidedChatNameButton(QPushButton):
    """
    QPushButton doesn't truncate its own text - a long chat title just grows
    the button past the sidebar's width, forcing an unwanted horizontal
    scrollbar in the history list. This elides to "..." on resize instead,
    and keeps the full name available as a tooltip.
    """
    def __init__(self, full_text):
        super().__init__()
        self.full_text = full_text
        self.setToolTip(full_text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(full_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elided_text()

    def _apply_elided_text(self):
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.font())
        available = max(self.width() - 24, 10)  # account for horizontal padding
        elided = metrics.elidedText(self.full_text, Qt.TextElideMode.ElideRight, available)
        super().setText(elided)

    def set_full_text(self, text: str):
        self.full_text = text
        self.setToolTip(text)
        self._apply_elided_text()


# ---- Stage 2 components (inserted before ChatHistoryItem) ----

class ElidedLabel(QLabel):
    """Single-line label that elides with ... instead of forcing its parent wider."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(10)
        self._apply()

    def set_full_text(self, text: str):
        self._full = text
        self._apply()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply()

    def _apply(self):
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self._full, Qt.TextElideMode.ElideRight, max(self.width(), 10)))


class ChatHistoryItem(QFrame):
    """Sidebar row: title + last-message preview, pin marker, and an options menu."""
    def __init__(self, chat_id, chat_name, parent_window, preview="", pinned=False):
        super().__init__()
        self.chat_id = chat_id
        self.chat_name = chat_name
        self.parent_window = parent_window
        self.pinned = pinned
        self.setObjectName("ChatItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#ChatItem {{ background-color: transparent; border-radius: 12px; }}
            QFrame#ChatItem:hover {{ background-color: {THEME['hover']}; }}
            QFrame#ChatItem[active="true"] {{ background-color: {THEME['bubble_user']}; }}
            QLabel#CiTitle {{ color: {THEME['text_primary']}; font-size: 14px; font-weight: 600; background: transparent; }}
            QLabel#CiPrev {{ color: {THEME['text_muted']}; font-size: 12px; background: transparent; }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 6, 8)
        lay.setSpacing(4)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.title_label = ElidedLabel(chat_name)
        self.title_label.setObjectName("CiTitle")
        self.preview_label = ElidedLabel(preview or "No messages yet")
        self.preview_label.setObjectName("CiPrev")
        col.addWidget(self.title_label)
        col.addWidget(self.preview_label)
        lay.addLayout(col, 1)
        self.name_btn = self.title_label  # compatibility: callers use name_btn.set_full_text()

        self.options_btn = QPushButton()
        self.options_btn.setIcon(line_icon("dots", THEME['text_secondary'], 16))
        self.options_btn.setIconSize(QSize(16, 16))
        self.options_btn.setFixedSize(26, 26)
        self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; border-radius: 6px; }}
            QPushButton:hover {{ background-color: {THEME['hover_strong']}; }}
        """)
        self.options_btn.clicked.connect(self.show_options_menu)
        lay.addWidget(self.options_btn)

    def set_active(self, active: bool):
        self.setProperty("active", bool(active))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_preview(self, text: str):
        self.preview_label.set_full_text(text or "No messages yet")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.load_chat()
        super().mousePressEvent(event)

    def load_chat(self):
        self.parent_window.load_chat(self.chat_id)

    def show_options_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {THEME['bg_primary']}; border: 1px solid {THEME['border_strong']}; border-radius: 10px; padding: 4px; }}
            QMenu::item {{ padding: 8px 16px; border-radius: 6px; color: {THEME['text_primary']}; }}
            QMenu::item:selected {{ background-color: {THEME['bg_tertiary']}; }}
        """)
        pin_action = menu.addAction("Unpin chat" if self.pinned else "Pin chat to top")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.options_btn.mapToGlobal(self.options_btn.rect().bottomLeft()))
        if action == pin_action:
            self.parent_window.toggle_pin_chat(self.chat_id)
        elif action == rename_action:
            self.rename_chat()
        elif action == delete_action:
            self.delete_chat()

    def rename_chat(self):
        new_name = themed_prompt(self.window(), "Rename chat", "Chat name", initial=self.chat_name, ok_text="Rename")
        if new_name and new_name.strip():
            self.chat_name = new_name.strip()
            self.title_label.set_full_text(self.chat_name)
            self.parent_window.rename_chat(self.chat_id, self.chat_name)

    def delete_chat(self):
        if themed_confirm(self.window(), "Delete this chat?", f"\"{self.chat_name}\" will be removed. This can't be undone.",
                          ok_text="Delete", danger=True):
            self.parent_window.delete_chat(self.chat_id)


class StatusLabel(QLabel):
    """Header status line (coloured dot + text). Clickable."""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTextFormat(Qt.TextFormat.RichText)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class OllamaRetryThread(QThread):
    """Re-run the assistant's Ollama check off the UI thread (status light 'retry')."""
    done = pyqtSignal()

    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant

    def run(self):
        try:
            self.assistant.initialize_ollama()
        except Exception:
            pass
        self.done.emit()


# What the Ctrl+K palette can jump to in Settings: (title, page, keywords)
SETTINGS_INDEX = [
    ("Dark mode", "General", "theme appearance light"),
    ("Language", "General", "english"),
    ("Personality", "General", "persona character neutral"),
    ("Export current chat", "General", "save text file"),
    ("Image safety checker", "General", "images filter safety"),
    ("Image model", "General", "checkpoint safetensors sdxl"),
    ("Generated images", "General", "delete folder"),
    ("Launch with Windows", "General", "startup boot"),
    ("Rescan folders", "General", "desktop"),
    ("Clear memory", "General", "remembered facts"),
    ("About you", "Personalization", "nickname occupation profile likes dislikes"),
    ("Reset relationship", "Personalization", "memories level"),
    ("Shortcuts", "Shortcuts", "macro commands create"),
    ("Installed apps", "Apps", "rescan programs"),
    ("Persona", "Persona", "personality character custom text file presets soft gentle balanced blunt cold"),
    ("Diagnostics", "Diagnostics", "status health check report problems"),
    ("Models", "Models", "ollama phi llama"),
    ("Image speed", "Models", "taesd tome token merging faster images benchmark"),
    ("Permissions", "Security", "file access power system"),
    ("PIN protection", "Security", "lock password"),
    ("Command history", "Security", "audit log"),
    ("Export all personal data", "Security", "backup"),
    ("Clear chat history", "Security", "delete chats"),
    ("Factory reset", "Security", "delete everything"),
]


class CommandPalette(QDialog):
    """Ctrl+K: one search box for actions, settings, chats and shortcuts."""
    SECTION_ORDER = ["Actions", "Chats", "Shortcuts", "Settings"]

    def __init__(self, parent, items):
        super().__init__(parent)
        self.setObjectName("ThemedDlg")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(640)
        self.setStyleSheet(settings_qss())
        self._items = items
        self._visible = []
        p = settings_palette()
        self._p = p

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QFrame()
        box.setObjectName("DlgBox")
        outer.addWidget(box)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(18, 0, 18, 0)
        top.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(line_pixmap("search", p['sub'], 18))
        top.addWidget(icon)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search chats, settings, shortcuts and actions")
        self.input.setFixedHeight(60)
        self.input.setStyleSheet("QLineEdit { border: none; background: transparent; font-size: 16px; padding: 0; }")
        self.input.textChanged.connect(self._render)
        self.input.installEventFilter(self)
        top.addWidget(self.input, 1)
        esc = QLabel("Esc")
        esc.setStyleSheet(f"QLabel {{ color: {p['sub']}; border: 1px solid {p['btn_border']}; border-radius: 6px; padding: 1px 6px; font-size: 11px; }}")
        esc.setFixedHeight(20)
        top.addWidget(esc, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(top)
        line = QFrame()
        line.setObjectName("HeaderLine")
        line.setFixedHeight(1)
        lay.addWidget(line)

        self.list = QListWidget()
        self.list.setFixedHeight(380)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; outline: 0; padding: 6px 8px; }}"
            f"QListWidget::item {{ border-radius: 12px; }}"
            f"QListWidget::item:selected {{ background: {p['active']}; }}"
            f"QListWidget::item:hover {{ background: {p['hover']}; }}")
        self.list.itemActivated.connect(self._activate)
        self.list.itemClicked.connect(self._activate)
        lay.addWidget(self.list)

        foot = QLabel("↑↓ move    ↵ open")
        foot.setStyleSheet(f"QLabel {{ color: {p['sub']}; font-size: 12px; padding: 10px 18px; border-top: 1px solid {p['line']}; background: transparent; }}")
        lay.addWidget(foot)
        self._render("")

    def _row_widget(self, it):
        p = self._p
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 0, 12, 0)
        h.setSpacing(12)
        tile = QLabel()
        tile.setFixedSize(30, 30)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(line_pixmap(it.get("icon", "settings"), p['accent'], 16))
        tile.setStyleSheet(f"QLabel {{ background: {p['tile']}; border-radius: 9px; }}")
        h.addWidget(tile)
        t = ElidedLabel(it["title"])
        t.setStyleSheet(f"QLabel {{ color: {p['text']}; font-size: 14px; font-weight: 600; background: transparent; }}")
        h.addWidget(t, 1)
        if it.get("desc"):
            d = QLabel(it["desc"])
            d.setStyleSheet(f"QLabel {{ color: {p['sub']}; font-size: 12px; background: transparent; }}")
            h.addWidget(d)
        return w

    def _render(self, query=""):
        q = (query or "").strip().lower()
        self.list.clear()
        self._visible = []
        for section in self.SECTION_ORDER:
            rows = []
            for it in self._items:
                if it["section"] != section:
                    continue
                if not q:
                    if section == "Settings":
                        continue
                    rows.append((0, it))
                    continue
                title = it["title"].lower()
                hay = f"{title} {it.get('keywords', '')}"
                if title.startswith(q):
                    rows.append((0, it))
                elif q in title:
                    rows.append((1, it))
                elif q in hay:
                    rows.append((2, it))
                elif it.get("text") and q in it["text"]:
                    rows.append((3, it))
            if not q and section == "Chats":
                rows = rows[:5]
            rows.sort(key=lambda r: r[0])
            rows = rows[:6]
            if not rows:
                continue
            header = QListWidgetItem()
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            lab = QLabel(section.upper())
            f = lab.font()
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            lab.setFont(f)
            lab.setStyleSheet(f"QLabel {{ color: {self._p['sub']}; font-size: 11px; font-weight: 600; padding: 10px 12px 2px 12px; background: transparent; }}")
            header.setSizeHint(QSize(100, 32))
            self.list.addItem(header)
            self.list.setItemWidget(header, lab)
            for _rank, it in rows:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, len(self._visible))
                item.setSizeHint(QSize(100, 46))
                self._visible.append(it)
                self.list.addItem(item)
                self.list.setItemWidget(item, self._row_widget(it))
        self._select_first()

    def _selectable_rows(self):
        return [i for i in range(self.list.count()) if self.list.item(i).flags() & Qt.ItemFlag.ItemIsSelectable]

    def _select_first(self):
        rows = self._selectable_rows()
        if rows:
            self.list.setCurrentRow(rows[0])

    def _move(self, delta):
        rows = self._selectable_rows()
        if not rows:
            return
        cur = self.list.currentRow()
        idx = rows.index(cur) if cur in rows else 0
        self.list.setCurrentRow(rows[(idx + delta) % len(rows)])

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                cur = self.list.currentItem()
                if cur is not None:
                    self._activate(cur)
                return True
        return super().eventFilter(obj, event)

    def _activate(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        action = self._visible[idx]["action"]
        self.accept()
        QTimer.singleShot(0, action)

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtCore import QPoint
        self.adjustSize()
        p = self.parentWidget()
        if p is not None:
            top_center = p.mapToGlobal(p.rect().center())
            self.move(top_center.x() - self.width() // 2, p.mapToGlobal(p.rect().topLeft()).y() + 110)
        self.input.setFocus()


class AppListItem(QWidget):
    """Individual app list item"""
    def __init__(self, app_name, icon_path=None):
        super().__init__()
        self.app_name = app_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # App icon
        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        
        # Try to load actual icon
        if icon_path and self.load_icon(icon_path, icon_label):
            pass  # Icon loaded successfully
        else:
            # Fallback to emoji
            icon_label.setPixmap(line_pixmap("grid", THEME['text_muted'], 18))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedSize(24, 24)
        
        layout.addWidget(icon_label)
        
        # App name
        name_label = QLabel(app_name)
        name_label.setStyleSheet(f"""
            QLabel {{
                color: {THEME['text_primary']};
                font-size: 13px;
            }}
        """)
        layout.addWidget(name_label, 1)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
                border-radius: 8px;
            }}
            QWidget:hover {{
                background-color: {THEME['bg_tertiary']};
            }}
        """)
    
    def load_icon(self, icon_path, label):
        """Load icon from path, handling .exe and .ico files"""
        try:
            import os
            
            # Clean up icon path (remove quotes and parameters)
            icon_path = icon_path.strip('"').split(',')[0]
            
            if not os.path.exists(icon_path):
                return False
            
            # Use QIcon to load from .exe or .ico
            icon = QIcon(icon_path)
            if not icon.isNull():
                pixmap = icon.pixmap(20, 20)
                label.setPixmap(pixmap)
                label.setScaledContents(False)
                return True
            
            return False
        except:
            return False


# ==============================================================================
# SETTINGS: reusable components
# ==============================================================================

MODEL_OVERRIDES_FILE = Path.home() / ".freesia" / "gui_models.json"
MODEL_SLOTS = [
    ("ollama_model", "Complex questions", "Longer, harder prompts. Bigger models are smarter but slower."),
    ("ollama_fast_model", "Fast replies", "Quick, simple questions where speed matters most."),
]


def load_model_overrides() -> dict:
    try:
        if MODEL_OVERRIDES_FILE.exists():
            with open(MODEL_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, str) and v}
    except Exception:
        pass
    return {}


def save_model_overrides(data: dict):
    try:
        MODEL_OVERRIDES_FILE.parent.mkdir(exist_ok=True)
        with open(MODEL_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Couldn't save model choices: {e}")


def apply_model_overrides(assistant):
    """Apply the model choices saved from Settings > Models (called once after FreesIA loads)."""
    if not assistant:
        return
    valid = {slot for slot, _t, _d in MODEL_SLOTS}
    for slot, name in load_model_overrides().items():
        if slot in valid:
            try:
                setattr(assistant, slot, name)
            except Exception:
                pass
    # If startup couldn't use the default models, retry now with the saved choices.
    try:
        if getattr(assistant, 'ollama_enabled', True) is False:
            assistant.initialize_ollama()
    except Exception:
        pass


class OllamaModelsThread(QThread):
    """Ask the local Ollama server which models are installed, off the UI thread."""
    finished = pyqtSignal(bool, list)  # reachable, model names

    def run(self):
        try:
            import ollama
            res = ollama.list()
            models = getattr(res, 'models', None)
            if models is None and isinstance(res, dict):
                models = res.get('models', [])
            names = []
            for m in models or []:
                if isinstance(m, dict):
                    n = m.get('model') or m.get('name')
                else:
                    n = getattr(m, 'model', None) or getattr(m, 'name', None)
                if n:
                    names.append(str(n))
            self.finished.emit(True, sorted(set(names)))
        except Exception:
            self.finished.emit(False, [])


def settings_palette() -> dict:
    dark = THEME is DARK_THEME
    return {
        "root": THEME['bg_primary'],
        "nav": THEME['bg_secondary'],
        "card": "#1F1F25" if dark else "#F7F7F8",
        "line": THEME['border'],
        "text": THEME['text_primary'],
        "text2": THEME['text_secondary'],
        "sub": THEME['text_muted'] if dark else THEME['text_secondary'],
        "btn_bg": "#2A2A31" if dark else "#EDEDEF",
        "btn_border": THEME['border_strong'],
        "btn_hover": THEME['hover_strong'],
        "primary_bg": THEME['accent_bg'],
        "primary_fg": THEME['accent_text'],
        "primary_hover": "#FFFFFF" if dark else "#333333",
        "danger": "#F0877F" if dark else "#C0392B",
        "danger_border": "#5A3532" if dark else "#E6B8B3",
        "danger_hover": "rgba(240,135,127,0.10)" if dark else "rgba(192,57,43,0.08)",
        "warn_border": "#4A2D2B" if dark else "#E6B8B3",
        "input_bg": THEME['bg_primary'],
        "input_border": "#33333C" if dark else "#D0D0D0",
        "accent": THEME['accent'],
        "active": THEME['bubble_user'],
        "hover": THEME['hover'],
        "tile": "#2A2A31" if dark else "#EDEDEF",
    }


def _settings_chevron_url() -> str:
    """Write a small chevron PNG for combo boxes (QSS can only reference files)."""
    try:
        import tempfile
        p = settings_palette()
        color = p['sub']
        path = Path(tempfile.gettempdir()) / f"freesia_chev_{color.strip('#')}.png"
        if not path.exists():
            line_pixmap("chev-down", color, 14, 2.0).save(str(path), "PNG")
        return str(path).replace("\\", "/")
    except Exception:
        return ""


_SETTINGS_QSS = """
QWidget { background: transparent; }
QDialog#SettingsDlg, QDialog#ThemedDlg { background: transparent; }
QFrame#SettingsRoot { background: @root@; border: 1px solid @line@; border-radius: 20px; }
QWidget#NavPanel { background: @nav@; border-right: 1px solid @line@; border-top-left-radius: 19px; border-bottom-left-radius: 19px; }
QLabel#NavTitle { color: @text@; font-size: 18px; font-weight: bold; padding: 6px 14px 10px 14px; background: transparent; }
QLabel#PageTitle { color: @text@; font-size: 22px; font-weight: bold; background: transparent; }
QLabel#PageSub { color: @sub@; font-size: 13px; background: transparent; }
QFrame#HeaderLine, QFrame#RowSep { background: @line@; border: none; }
QWidget#PageBody { background: transparent; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QLabel#Sec { color: @sub@; font-size: 12px; font-weight: 600; background: transparent; }
QLabel#SecDanger { color: @danger@; font-size: 12px; font-weight: 600; background: transparent; }
QFrame#SCard { background: @card@; border: 1px solid @line@; border-radius: 16px; }
QFrame#SCard[warn="true"] { border-color: @warn_border@; }
QLabel#RT { color: @text@; font-size: 14px; font-weight: 600; background: transparent; }
QLabel#RD { color: @sub@; font-size: 12px; background: transparent; }
QLabel#FieldLabel { color: @text2@; font-size: 12px; font-weight: 600; background: transparent; }
QLabel#IconTile { background: @tile@; border-radius: 10px; }
QLabel#Foot { color: @sub@; font-size: 12px; background: transparent; }
QLabel#Toast { background: @primary_bg@; color: @primary_fg@; border-radius: 18px; padding: 8px 18px; font-size: 13px; font-weight: 600; }
QPushButton#Nav { background: transparent; border: none; color: @text2@; font-size: 14px; text-align: left; padding-left: 14px; border-radius: 12px; }
QPushButton#Nav:hover { background: @hover@; }
QPushButton#Nav:checked { background: @active@; color: @text@; font-weight: 600; }
QPushButton#CloseBtn { background: transparent; border: none; border-radius: 18px; }
QPushButton#CloseBtn:hover { background: @hover@; }
QPushButton#IconBtn { background: transparent; border: none; border-radius: 8px; }
QPushButton#IconBtn:hover { background: @danger_hover@; }
QPushButton[kind="secondary"] { background: @btn_bg@; color: @text@; border: 1px solid @btn_border@; border-radius: 10px; padding: 0 16px; font-size: 13px; font-weight: 600; }
QPushButton[kind="secondary"]:hover { background: @btn_hover@; }
QPushButton[kind="secondary"]:disabled { color: @sub@; }
QPushButton[kind="danger"] { background: transparent; color: @danger@; border: 1px solid @danger_border@; border-radius: 10px; padding: 0 16px; font-size: 13px; font-weight: 600; }
QPushButton[kind="danger"]:hover { background: @danger_hover@; }
QPushButton[kind="danger"]:disabled { color: @sub@; border-color: @line@; }
QPushButton[kind="primary"] { background: @primary_bg@; color: @primary_fg@; border: 1px solid @primary_bg@; border-radius: 10px; padding: 0 18px; font-size: 13px; font-weight: 600; }
QPushButton[kind="primary"]:hover { background: @primary_hover@; }
QPushButton[kind="primary"]:disabled { background: @btn_bg@; color: @sub@; border-color: @btn_border@; }
QLineEdit, QTextEdit { background: @input_bg@; border: 1px solid @input_border@; border-radius: 10px; padding: 8px 12px; color: @text@; font-size: 13px; selection-background-color: @accent@; selection-color: @primary_fg@; }
QLineEdit:focus, QTextEdit:focus { border: 1px solid @accent@; }
QComboBox { background: @input_bg@; border: 1px solid @btn_border@; border-radius: 10px; padding: 0 14px; min-height: 34px; color: @text@; font-size: 13px; }
QComboBox:hover { border-color: @sub@; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url("@chev@"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: @card@; border: 1px solid @btn_border@; border-radius: 8px; color: @text@; selection-background-color: @active@; selection-color: @text@; outline: 0; padding: 4px; }
QSlider::groove:horizontal { height: 4px; background: @btn_border@; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @accent@; border-radius: 2px; }
QSlider::handle:horizontal { background: @text@; border: 3px solid @accent@; width: 10px; height: 10px; margin: -8px 0; border-radius: 8px; }
QSlider::groove:horizontal:disabled, QSlider::sub-page:horizontal:disabled { background: @line@; }
QSlider::handle:horizontal:disabled { background: @line@; border-color: @btn_border@; }
QFrame#SrcTile { background: @card@; border: 1px solid @line@; border-radius: 16px; }
QFrame#SrcTile:hover { background: @hover@; }
QFrame#SrcTile[sel="true"] { background: @active@; border: 1px solid @accent@; }
QFrame#DlgBox { background: @card@; border: 1px solid @btn_border@; border-radius: 16px; }
QLabel#DlgTitle { color: @text@; font-size: 17px; font-weight: bold; background: transparent; }
QLabel#DlgText { color: @text2@; font-size: 13px; background: transparent; }
"""


def settings_qss() -> str:
    p = dict(settings_palette())
    p["chev"] = _settings_chevron_url()
    qss = _SETTINGS_QSS
    for k, v in p.items():
        qss = qss.replace(f"@{k}@", v)
    return qss + themed_scrollbar_css()


class ToggleSwitch(QCheckBox):
    """Pill switch. Still a QCheckBox underneath, so isChecked/setChecked/toggled/stateChanged all work."""
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setChecked(checked)

    def sizeHint(self):
        return QSize(42, 24)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        from PyQt6.QtCore import QRectF
        dark = THEME is DARK_THEME
        on = self.isChecked()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor(THEME['accent']) if on else QColor(THEME['border_strong'] if dark else "#C8C8CE")
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 42, 24), 12, 12)
        if on:
            knob = QColor("#18181B" if dark else "#FFFFFF")
        else:
            knob = QColor(THEME['text_muted'] if dark else "#FFFFFF")
        p.setBrush(knob)
        p.drawEllipse(QRectF(21 if on else 3, 3, 18, 18))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            ring = QColor(THEME['accent'])
            p.setPen(ring)
            p.drawRoundedRect(QRectF(0.5, 0.5, 41, 23), 11.5, 11.5)
        p.end()


def settings_button(text: str, kind: str = "secondary", icon: str = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("kind", kind)
    btn.setFixedHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon:
        p = settings_palette()
        color = {"danger": p['danger'], "primary": p['primary_fg']}.get(kind, p['text'])
        btn.setIcon(line_icon(icon, color, 16))
        btn.setIconSize(QSize(16, 16))
    return btn


class ThemedDialog(QDialog):
    """Small in-app confirm / message / prompt dialog that matches the Settings look
    (replaces QMessageBox / QInputDialog). Optional type-to-confirm for destructive actions."""
    def __init__(self, parent, title, text="", ok_text="OK", cancel_text="Cancel", danger=False,
                 input_label=None, password=False, confirm_phrase=None, extra_widget=None, width=460, initial=""):
        super().__init__(parent)
        self.setObjectName("ThemedDlg")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(width)
        self.setStyleSheet(settings_qss())
        self._confirm_phrase = confirm_phrase
        self._input = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QFrame()
        box.setObjectName("DlgBox")
        outer.addWidget(box)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)

        t = QLabel(title)
        t.setObjectName("DlgTitle")
        t.setWordWrap(True)
        lay.addWidget(t)
        if text:
            d = QLabel(text)
            d.setObjectName("DlgText")
            d.setWordWrap(True)
            lay.addWidget(d)
        if extra_widget is not None:
            lay.addWidget(extra_widget)

        label = input_label
        if confirm_phrase:
            label = f"Type {confirm_phrase} to confirm"
        if label:
            lbl = QLabel(label)
            lbl.setObjectName("FieldLabel")
            lay.addSpacing(4)
            lay.addWidget(lbl)
            self._input = QLineEdit()
            if password:
                self._input.setEchoMode(QLineEdit.EchoMode.Password)
            self._input.setFixedHeight(40)
            lay.addWidget(self._input)

        lay.addSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        if cancel_text:
            cancel = settings_button(cancel_text, "secondary")
            cancel.clicked.connect(self.reject)
            row.addWidget(cancel)
        self.ok_btn = settings_button(ok_text, "danger" if danger else "primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        row.addWidget(self.ok_btn)
        lay.addLayout(row)

        if self._input is not None:
            self.ok_btn.setEnabled(False)
            self._input.textChanged.connect(self._on_input_changed)
            self._input.returnPressed.connect(self._try_accept)
            if initial:
                self._input.setText(initial)
                self._input.selectAll()
            self._input.setFocus()

    def _on_input_changed(self, text):
        if self._confirm_phrase:
            self.ok_btn.setEnabled(text.strip().lower() == self._confirm_phrase.lower())
        else:
            self.ok_btn.setEnabled(bool(text))

    def _try_accept(self):
        if self.ok_btn.isEnabled():
            self.accept()

    def value(self) -> str:
        return self._input.text() if self._input is not None else ""

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtCore import QPoint
        self.adjustSize()
        p = self.parentWidget()
        if p is not None:
            center = p.mapToGlobal(p.rect().center())
            self.move(center - QPoint(self.width() // 2, self.height() // 2))


def themed_confirm(parent, title, text, ok_text="Confirm", danger=False, confirm_phrase=None) -> bool:
    dlg = ThemedDialog(parent, title, text, ok_text=ok_text, danger=danger, confirm_phrase=confirm_phrase)
    return dlg.exec() == QDialog.DialogCode.Accepted


def themed_message(parent, title, text=""):
    ThemedDialog(parent, title, text, ok_text="OK", cancel_text=None).exec()


def themed_prompt(parent, title, label, text="", password=False, ok_text="Continue", initial=""):
    dlg = ThemedDialog(parent, title, text, ok_text=ok_text, input_label=label, password=password, initial=initial)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.value()
    return None


# ==============================================================================
# SETTINGS DIALOG
# ==============================================================================

def _star_polygon(cx, cy, r):
    import math
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append(QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return QPolygonF(pts)


def _cover_crop(pm: QPixmap, size: int) -> QPixmap:
    scaled = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    return scaled.copy(x, y, size, size)


class GalleryTile(QWidget):
    """One square thumbnail: star badge, and download/delete on hover."""
    opened = pyqtSignal(int)
    star_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    download_clicked = pyqtSignal(int)

    def __init__(self, index, item, size):
        super().__init__()
        self.index = index
        self.item = item
        self._pix = None
        self._hover = False
        self.setFixedSize(size, size)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(item.get("prompt", ""))

    def set_pixmap(self, pm):
        self._pix = pm
        self.update()

    def _star_rect(self):
        return QRectF(self.width() - 38, 8, 30, 30)

    def _del_rect(self):
        return QRectF(self.width() - 34, self.height() - 32, 26, 24)

    def _dl_rect(self):
        return QRectF(self.width() - 64, self.height() - 32, 26, 24)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._star_rect().contains(pos):
            self.star_clicked.emit(self.index)
        elif self._hover and self._del_rect().contains(pos):
            self.delete_clicked.emit(self.index)
        elif self._hover and self._dl_rect().contains(pos):
            self.download_clicked.emit(self.index)
        else:
            self.opened.emit(self.index)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainterPath, QLinearGradient, QPen, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor(THEME['bg_tertiary']))
        if self._pix is not None:
            p.drawPixmap(0, 0, self._pix)
        if self._hover:
            grad = QLinearGradient(0, h - 52, 0, h)
            grad.setColorAt(0, QColor(0, 0, 0, 0))
            grad.setColorAt(1, QColor(0, 0, 0, 175))
            p.fillRect(QRectF(0, h - 52, w, 52), QBrush(grad))
            p.setPen(QColor("#ECECF1"))
            f = p.font()
            f.setPixelSize(11)
            p.setFont(f)
            when = datetime.fromtimestamp(self.item["mtime"]).strftime("%b %d")
            p.drawText(QRectF(10, h - 30, w - 90, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, when)
            for rect, icon, col in ((self._dl_rect(), "download", "#ECECF1"), (self._del_rect(), "trash", "#F0877F")):
                pm = line_pixmap(icon, col, 15)
                p.drawPixmap(int(rect.x() + (rect.width() - 15) / 2), int(rect.y() + (rect.height() - 15) / 2), pm)
        starred = bool(self.item.get("starred"))
        if starred or self._hover:
            sr = self._star_rect()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(19, 19, 22, 185))
            p.drawEllipse(sr)
            poly = _star_polygon(sr.center().x(), sr.center().y() + 0.5, 8.5)
            if starred:
                p.setBrush(QColor(THEME['accent']))
                p.setPen(QPen(QColor(THEME['accent']), 1.2))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor("#ECECF1"), 1.4))
            p.drawPolygon(poly)
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(THEME['accent'] if self._hover else THEME['border']), 1.2 if self._hover else 1))
        p.drawPath(path)
        p.end()


class GalleryDialog(QDialog):
    """Everything the assistant has drawn: a grid, a large viewer, stars, and clean-up."""
    COLUMNS = 4

    def __init__(self, parent, assistant, main_window=None):
        super().__init__(parent)
        self.assistant = assistant
        self.main_window = main_window or parent
        self.setObjectName("SettingsDlg")
        self.setWindowTitle("Image gallery")
        ref = self.main_window if self.main_window is not None else parent
        w, h = 900, 740
        if ref is not None:
            w = max(640, min(w, ref.width() - 40))
            h = max(520, min(h, ref.height() - 40))
        self.setFixedSize(w, h)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(settings_qss())
        self._p = settings_palette()
        self._all = []
        self._visible = []
        self._filter = "all"
        self._thumbs = {}
        self._tiles = []
        self._load_queue = []
        self._viewer_index = -1
        self._tile_size = (w - 56 - 14 - (self.COLUMNS - 1) * 12) // self.COLUMNS

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        root = QFrame()
        root.setObjectName("SettingsRoot")
        outer.addWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title_lbl = QLabel("Image gallery")
        self.title_lbl.setObjectName("PageTitle")
        self.sub_lbl = QLabel("")
        self.sub_lbl.setObjectName("PageSub")
        titles.addWidget(self.title_lbl)
        titles.addWidget(self.sub_lbl)
        head.addLayout(titles, 1)
        open_btn = settings_button("Open folder", "secondary", "folder")
        open_btn.clicked.connect(self._open_folder)
        head.addWidget(open_btn)
        close_btn = QPushButton()
        close_btn.setObjectName("CloseBtn")
        close_btn.setIcon(line_icon("close", self._p['sub'], 18))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        head.addWidget(close_btn)
        lay.addLayout(head)
        lay.addSpacing(14)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_grid_page())
        self.stack.addWidget(self._build_viewer_page())

        self._load_timer = QTimer(self)
        self._load_timer.setInterval(5)
        self._load_timer.timeout.connect(self._load_some)
        self.reload()

    # ---------------------------------------------------------------- pages

    def _chip_css(self):
        p = self._p
        return (f"QPushButton {{ background: {p['card']}; color: {p['text2']}; border: 1px solid {p['line']}; border-radius: 16px; padding: 0 16px; font-size: 13px; }}"
                f"QPushButton:hover {{ background: {p['hover']}; }}"
                f"QPushButton:checked {{ background: {p['active']}; color: {p['text']}; font-weight: 600; border-color: {p['btn_border']}; }}")

    def _build_grid_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self._chips = {}
        for key, label in (("all", "All"), ("starred", "Starred"), ("week", "This week")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setFixedHeight(32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(self._chip_css())
            b.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            self._chips[key] = b
            chips.addWidget(b)
        chips.addStretch()
        v.addLayout(chips)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_host)
        v.addWidget(self.scroll, 1)

        self.empty_lbl = QLabel("")
        self.empty_lbl.setObjectName("RD")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setWordWrap(True)
        v.addWidget(self.empty_lbl)

        card = QFrame()
        card.setObjectName("SCard")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(18, 12, 14, 12)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel("Clean up")
        t.setObjectName("RT")
        self.cleanup_desc = QLabel("")
        self.cleanup_desc.setObjectName("RD")
        col.addWidget(t)
        col.addWidget(self.cleanup_desc)
        cl.addLayout(col, 1)
        self.cleanup_btn = settings_button("Delete unstarred", "danger", "trash")
        self.cleanup_btn.clicked.connect(self._delete_unstarred)
        cl.addWidget(self.cleanup_btn)
        v.addWidget(card)
        return page

    def _build_viewer_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        top = QHBoxLayout()
        back = settings_button("Gallery", "secondary", "chev-left")
        back.clicked.connect(self._show_grid)
        top.addWidget(back)
        top.addStretch()
        self.pos_lbl = QLabel("")
        self.pos_lbl.setObjectName("RD")
        top.addWidget(self.pos_lbl)
        prev_b = QPushButton()
        prev_b.setObjectName("IconBtn")
        prev_b.setIcon(line_icon("chev-left", self._p['text'], 18))
        prev_b.setFixedSize(34, 34)
        prev_b.clicked.connect(lambda: self._step(-1))
        next_b = QPushButton()
        next_b.setObjectName("IconBtn")
        next_b.setIcon(line_icon("chev-right", self._p['text'], 18))
        next_b.setFixedSize(34, 34)
        next_b.clicked.connect(lambda: self._step(1))
        top.addWidget(prev_b)
        top.addWidget(next_b)
        v.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(18)
        self.big_lbl = QLabel()
        self.big_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_lbl.setStyleSheet(f"QLabel {{ background: {self._p['card']}; border: 1px solid {self._p['line']}; border-radius: 16px; }}")
        self.big_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.big_lbl.setMinimumSize(200, 200)
        body.addWidget(self.big_lbl, 1)

        side = QVBoxLayout()
        side.setSpacing(10)
        self.star_btn = settings_button("Star", "secondary", "star")
        self.star_btn.clicked.connect(self._viewer_toggle_star)
        side.addWidget(self.star_btn)
        pc = QFrame()
        pc.setObjectName("SCard")
        pl = QVBoxLayout(pc)
        pl.setContentsMargins(16, 12, 16, 14)
        pl.setSpacing(4)
        pt = QLabel("PROMPT")
        pt.setObjectName("Sec")
        self.prompt_lbl = QLabel("")
        self.prompt_lbl.setObjectName("RT")
        self.prompt_lbl.setStyleSheet("font-weight: 400;")
        self.prompt_lbl.setWordWrap(True)
        self.prompt_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        pl.addWidget(pt)
        pl.addWidget(self.prompt_lbl)
        side.addWidget(pc)
        dl = settings_button("Download", "secondary", "download")
        dl.clicked.connect(lambda: self._download(self._viewer_index))
        cp = settings_button("Copy prompt", "secondary", "copy")
        cp.clicked.connect(self._copy_prompt)
        ed = settings_button("Edit in chat", "secondary", "pencil")
        ed.clicked.connect(self._edit_in_chat)
        de = settings_button("Delete", "danger", "trash")
        de.clicked.connect(lambda: self._delete(self._viewer_index))
        for b in (dl, cp, ed, de):
            side.addWidget(b)
        side.addStretch()
        self.info_lbl = QLabel("")
        self.info_lbl.setObjectName("RD")
        side.addWidget(self.info_lbl)
        hint = QLabel("← → to browse   Esc to go back")
        hint.setObjectName("Foot")
        side.addWidget(hint)
        sw = QWidget()
        sw.setFixedWidth(270)
        sw.setLayout(side)
        body.addWidget(sw)
        v.addLayout(body, 1)
        return page

    # ---------------------------------------------------------------- data

    def reload(self):
        try:
            self._all = list(self.assistant.list_generated_images())
        except Exception:
            self._all = []
        self._apply_filter()

    def _set_filter(self, key):
        self._filter = key
        self._apply_filter()

    def _apply_filter(self):
        import time as _t
        for k, b in self._chips.items():
            b.setChecked(k == self._filter)
        week_ago = _t.time() - 7 * 86400
        if self._filter == "starred":
            self._visible = [i for i in self._all if i["starred"]]
        elif self._filter == "week":
            self._visible = [i for i in self._all if i["mtime"] >= week_ago]
        else:
            self._visible = list(self._all)
        starred = sum(1 for i in self._all if i["starred"])
        n = len(self._all)
        self.sub_lbl.setText(f"{n} image{'s' if n != 1 else ''}" + (f"  ·  {starred} starred" if starred else ""))
        self.cleanup_desc.setText(f"Keeps your {starred} starred image{'s' if starred != 1 else ''}." if starred else "Removes every image. Star the ones you want to keep first.")
        self.cleanup_btn.setEnabled(n - starred > 0)
        self._populate()

    def _populate(self):
        self._load_timer.stop()
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
                it.widget().deleteLater()
        self._tiles = []
        self._load_queue = []
        for idx, item in enumerate(self._visible):
            tile = GalleryTile(idx, item, self._tile_size)
            tile.opened.connect(self._open_viewer)
            tile.star_clicked.connect(self._toggle_star)
            tile.delete_clicked.connect(self._delete)
            tile.download_clicked.connect(self._download)
            self.grid.addWidget(tile, idx // self.COLUMNS, idx % self.COLUMNS)
            self._tiles.append(tile)
            key = str(item["path"])
            if key in self._thumbs:
                tile.set_pixmap(self._thumbs[key])
            else:
                self._load_queue.append(idx)
        if not self._visible:
            if self._all:
                self.empty_lbl.setText("Nothing here yet. Star an image and it shows up in Starred." if self._filter == "starred" else "No images from the last 7 days.")
            else:
                self.empty_lbl.setText(f"No images yet. Ask {AI_NAME} to draw something and it will show up here.")
            self.empty_lbl.show()
        else:
            self.empty_lbl.hide()
        if self._load_queue:
            self._load_timer.start()

    def _load_some(self):
        dpr = self.devicePixelRatioF() or 1.0
        px = int(self._tile_size * dpr)
        for _ in range(6):
            if not self._load_queue:
                self._load_timer.stop()
                return
            idx = self._load_queue.pop(0)
            if idx >= len(self._tiles):
                continue
            item = self._visible[idx]
            pm = QPixmap(str(item["path"]))
            if pm.isNull():
                continue
            thumb = _cover_crop(pm, px)
            thumb.setDevicePixelRatio(dpr)
            self._thumbs[str(item["path"])] = thumb
            self._tiles[idx].set_pixmap(thumb)

    # ---------------------------------------------------------------- actions

    def _open_folder(self):
        gen_dir = self.assistant.config_dir / "generated_images"
        gen_dir.mkdir(exist_ok=True)
        try:
            os.startfile(str(gen_dir))
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(gen_dir)))

    def _toggle_star(self, idx):
        if not (0 <= idx < len(self._visible)):
            return
        item = self._visible[idx]
        item["starred"] = not item["starred"]
        try:
            self.assistant.set_image_starred(item["path"], item["starred"])
        except Exception as e:
            print(f"Couldn't save star: {e}")
        if self._filter == "starred" and not item["starred"] and self.stack.currentIndex() == 0:
            self._apply_filter()
            return
        starred = sum(1 for i in self._all if i["starred"])
        n = len(self._all)
        self.sub_lbl.setText(f"{n} image{'s' if n != 1 else ''}" + (f"  ·  {starred} starred" if starred else ""))
        self.cleanup_desc.setText(f"Keeps your {starred} starred image{'s' if starred != 1 else ''}." if starred else "Removes every image. Star the ones you want to keep first.")
        self.cleanup_btn.setEnabled(n - starred > 0)
        if idx < len(self._tiles):
            self._tiles[idx].update()
        if self.stack.currentIndex() == 1:
            self._refresh_viewer()

    def _delete(self, idx):
        if not (0 <= idx < len(self._visible)):
            return
        item = self._visible[idx]
        msg = "This image is starred. It will be removed from disk. This can't be undone." if item["starred"] else "It will be removed from disk. This can't be undone."
        if not themed_confirm(self, "Delete this image?", msg, ok_text="Delete", danger=True):
            return
        self.assistant.delete_generated_image(item["path"])
        self._thumbs.pop(str(item["path"]), None)
        in_viewer = self.stack.currentIndex() == 1
        self.reload()
        if in_viewer:
            if self._visible:
                self._viewer_index = min(idx, len(self._visible) - 1)
                self._refresh_viewer()
            else:
                self._show_grid()

    def _delete_unstarred(self):
        starred = sum(1 for i in self._all if i["starred"])
        n = len(self._all) - starred
        if n <= 0:
            return
        keep = f" Your {starred} starred image{'s' if starred != 1 else ''} will be kept." if starred else ""
        if not themed_confirm(self, "Delete unstarred images?", f"{n} image{'s' if n != 1 else ''} will be removed from disk.{keep} This can't be undone.",
                              ok_text="Delete images", danger=True):
            return
        self.assistant.delete_all_generated_images()
        self._thumbs.clear()
        self.reload()

    def _download(self, idx):
        if not (0 <= idx < len(self._visible)):
            return
        src = Path(self._visible[idx]["path"])
        dest, _ = QFileDialog.getSaveFileName(self, "Save image", str(Path.home() / "Desktop" / src.name), "JPEG image (*.jpg)")
        if dest:
            try:
                import shutil
                shutil.copyfile(src, dest)
            except Exception as e:
                themed_message(self, "Couldn't save", str(e))

    def _copy_prompt(self):
        if 0 <= self._viewer_index < len(self._visible):
            QApplication.clipboard().setText(self._visible[self._viewer_index]["prompt"])

    def _edit_in_chat(self):
        if not (0 <= self._viewer_index < len(self._visible)):
            return
        path = Path(self._visible[self._viewer_index]["path"])
        mw = self.main_window
        if mw is not None and hasattr(mw, "attach_image_path"):
            self.accept()
            mw.attach_image_path(path)

    # ---------------------------------------------------------------- viewer

    def _open_viewer(self, idx):
        self._viewer_index = idx
        self.stack.setCurrentIndex(1)
        self._refresh_viewer()
        QTimer.singleShot(0, self._refresh_viewer)

    def _show_grid(self):
        self.stack.setCurrentIndex(0)

    def _step(self, delta):
        if not self._visible:
            return
        self._viewer_index = (self._viewer_index + delta) % len(self._visible)
        self._refresh_viewer()

    def _viewer_toggle_star(self):
        self._toggle_star(self._viewer_index)

    def _refresh_viewer(self):
        if not (0 <= self._viewer_index < len(self._visible)):
            return
        item = self._visible[self._viewer_index]
        pm = QPixmap(str(item["path"]))
        dpr = self.devicePixelRatioF() or 1.0
        box = self.big_lbl.size()
        bw, bh = max(200, box.width() - 24), max(200, box.height() - 24)
        if not pm.isNull():
            info = f"{pm.width()} × {pm.height()}  ·  " + datetime.fromtimestamp(item["mtime"]).strftime("%b %d, %Y")
            scaled = pm.scaled(int(bw * dpr), int(bh * dpr), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            self.big_lbl.setPixmap(scaled)
        else:
            info = "Couldn't open this file"
            self.big_lbl.setText("Couldn't open this file")
        self.info_lbl.setText(info)
        self.prompt_lbl.setText(item["prompt"])
        self.pos_lbl.setText(f"{self._viewer_index + 1} of {len(self._visible)}")
        self.star_btn.setText("Starred" if item["starred"] else "Star")
        color = self._p['accent'] if item["starred"] else self._p['text']
        self.star_btn.setIcon(line_icon("star", color, 16))

    def keyPressEvent(self, event):
        key = event.key()
        if self.stack.currentIndex() == 1:
            if key == Qt.Key.Key_Left:
                self._step(-1)
                return
            if key == Qt.Key.Key_Right:
                self._step(1)
                return
            if key == Qt.Key.Key_Escape:
                self._show_grid()
                return
        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self.stack.currentIndex() == 1:
            QTimer.singleShot(0, self._refresh_viewer)


class ImageBenchThread(QThread):
    """Runs the backend's TAESD/ToMe speed test off the UI thread."""
    progress = pyqtSignal(str)
    done = pyqtSignal(list)

    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant

    def run(self):
        try:
            results = self.assistant.benchmark_image_speed(self.progress.emit)
        except Exception as e:
            results = [{"label": "Speed test", "seconds": None, "error": str(e)}]
        self.done.emit(results)


PERSONA_LEVELS = [
    ("Soft", "Warm and patient. Comfort first, advice second.", "It's okay. Take your time. I'm here."),
    ("Gentle", "Calm and friendly, with a light touch.", "You'll manage. I'm here if you need me."),
    ("Balanced", "Direct and practical, with a dry sense of humor.", "Fine. Use range. Starts at zero."),
    ("Blunt", "Short sentences, little small talk, gets to the point.", "Use range. Remember it starts at zero."),
    ("Cold", "Clipped and detached. Answers only what was asked.", "Range. Zero-indexed. Next question."),
]

PERSONA_TEMPLATES = [
    ("Blunt and loyal", "Short sentences, guarded, shows care through actions.",
     "You speak in short sentences and avoid pleasantries. You are guarded with strangers and fiercely loyal once someone earns your trust. You show care through actions, not speeches. You never claim to be human."),
    ("Warm companion", "Kind, curious, remembers little details about you.",
     "You are warm, curious and attentive. You remember small details about the user and ask about them later. You speak naturally and kindly, with gentle humor, and you are honest when you disagree. You never claim to be human."),
    ("Dry and witty", "Deadpan humor, sharp, never mean.",
     "You have a dry, deadpan sense of humor and a sharp mind. You tease lightly but never cruelly. You give clear answers first and jokes second. You never claim to be human."),
    ("Plain assistant", "Neutral, clear, no character.",
     "You are a clear and helpful assistant. Be concise, accurate and neutral. Do not roleplay a character. Ask a question when something is ambiguous."),
]


def read_text_file_loose(path, limit=200_000) -> str:
    """Read a text file the way people actually save them (UTF-8, UTF-8 with BOM, or Windows-1252)."""
    data = Path(path).read_bytes()[:limit]
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class PersonaTextEdit(QTextEdit):
    """Big text box for the assistant's personality. Drop a .txt file on it to fill it in."""
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAcceptRichText(False)
        self.setProperty("drag", False)

    def _is_txt_drop(self, mime):
        if not mime.hasUrls():
            return False
        return any(u.isLocalFile() and u.toLocalFile().lower().endswith((".txt", ".md")) for u in mime.urls())

    def _set_drag(self, on):
        self.setProperty("drag", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if self._is_txt_drop(event.mimeData()):
            self._set_drag(True)
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._is_txt_drop(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._set_drag(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._set_drag(False)
        if self._is_txt_drop(event.mimeData()):
            for u in event.mimeData().urls():
                if u.isLocalFile() and u.toLocalFile().lower().endswith((".txt", ".md")):
                    try:
                        self.file_dropped.emit(read_text_file_loose(u.toLocalFile()))
                    except Exception as e:
                        print(f"Couldn't read dropped file: {e}")
                    break
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class SourceTile(QFrame):
    """Selectable card: 'My own text' vs 'Presets'."""
    clicked = pyqtSignal()

    def __init__(self, title, desc):
        super().__init__()
        self.setObjectName("SrcTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("RT")
        self.badge = QLabel("in use")
        self.badge.setObjectName("RD")
        row.addWidget(self.title_lbl)
        row.addWidget(self.badge)
        row.addStretch()
        lay.addLayout(row)
        d = QLabel(desc)
        d.setObjectName("RD")
        d.setWordWrap(True)
        lay.addWidget(d)
        self.set_selected(False)

    def set_selected(self, on):
        self.setProperty("sel", bool(on))
        self.badge.setVisible(bool(on))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class DiagnosticsThread(QThread):
    """Checks everything the assistant depends on, off the UI thread. Emits {key: (level, status, desc, action)}."""
    done = pyqtSignal(dict)

    def __init__(self, assistant):
        super().__init__()
        self.a = assistant

    def run(self):
        a, res = self.a, {}
        names, reachable = [], False
        try:
            import ollama
            r = ollama.list()
            models = getattr(r, 'models', None)
            if models is None and isinstance(r, dict):
                models = r.get('models', [])
            for m in models or []:
                n = (m.get('model') or m.get('name')) if isinstance(m, dict) else (getattr(m, 'model', None) or getattr(m, 'name', None))
                if n:
                    names.append(str(n))
            reachable = True
        except Exception:
            reachable = False
        names = sorted(set(names))
        self.names = names
        if reachable:
            res["ollama"] = ("ok", "Running", f"{len(names)} model{'s' if len(names) != 1 else ''} installed", None)
        else:
            res["ollama"] = ("bad", "Not reachable", "Start the Ollama app, then press Recheck.", None)

        def model_row(attr, label):
            wanted = getattr(a, attr, "")
            wanted = wanted if isinstance(wanted, str) else ""
            if not reachable:
                return ("none", "Unknown", wanted or label, None)
            try:
                matched = a._match_installed_model(wanted, names)
            except Exception:
                matched = wanted if wanted in names else None
            if matched:
                return ("ok", "Installed", matched, None)
            return ("warn", "Not installed", f"{wanted or label} is missing. Install it with: ollama pull {wanted}", ("Open Models", "models"))
        res["chat_model"] = model_row("ollama_model", "Chat model")
        res["fast_model"] = model_row("ollama_fast_model", "Fast model")

        # image generator
        try:
            fdir = getattr(a, "fastsdcpu_dir", None)
            installed = bool(fdir) and Path(fdir).exists()
        except Exception:
            installed = False
        try:
            import requests
            requests.get(f"{a.fastsdcpu_api_url}/api/", timeout=2)
            up = True
        except Exception:
            up = False
        if up:
            res["image"] = ("ok", "Running", "FastSD CPU is answering.", None)
        elif not installed:
            res["image"] = ("bad", "Not installed", "The fastsdcpu folder wasn't found next to this project.", None)
        else:
            res["image"] = ("warn", "Not running", "Starts by itself when you ask for an image. Start it now to skip the wait.", ("Start it", "start_image"))

        # voice
        engine = getattr(a, "tts_engine", None)
        if engine is None:
            res["voice"] = ("bad", "Unavailable", "No text-to-speech engine could start.", None)
        elif getattr(a, "tts_enabled", True) is False:
            res["voice"] = ("warn", "Muted", "Voice is installed but turned off.", None)
        else:
            res["voice"] = ("ok", "Working", "System voice (SAPI)", None)

        # microphone
        try:
            import speech_recognition as sr
            mics = sr.Microphone.list_microphone_names()
            if mics:
                res["mic"] = ("ok", "Found", str(mics[0]), None)
            else:
                res["mic"] = ("bad", "No microphone", "Plug one in or check Windows sound settings.", None)
        except Exception:
            res["mic"] = ("warn", "Can't check", "The microphone library isn't available here.", None)

        # memory and disk
        import shutil
        ram_free = None
        try:
            import psutil
            ram_free = psutil.virtual_memory().available / 1e9
        except Exception:
            try:
                import ctypes

                class MEMSTAT(ctypes.Structure):
                    _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                                ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                                ("ave", ctypes.c_ulonglong)]
                m = MEMSTAT()
                m.l = ctypes.sizeof(MEMSTAT)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
                ram_free = m.ap / 1e9
            except Exception:
                ram_free = None
        try:
            disk_free = shutil.disk_usage(str(Path.home())).free / 1e9
        except Exception:
            disk_free = None
        parts = []
        level = "ok"
        if ram_free is not None:
            parts.append(f"{ram_free:.1f} GB RAM free")
            if ram_free < 2:
                level = "warn"
        if disk_free is not None:
            parts.append(f"{disk_free:.0f} GB disk free")
            if disk_free < 5:
                level = "warn"
        res["system"] = (level, "OK" if level == "ok" else "Low", " · ".join(parts) or "Couldn't read", None)
        self.done.emit(res)


class ImageServerStartThread(QThread):
    done = pyqtSignal(bool)

    def __init__(self, assistant):
        super().__init__()
        self.a = assistant

    def run(self):
        try:
            import requests
            self.done.emit(bool(self.a._ensure_fastsdcpu_running(requests)))
        except Exception:
            self.done.emit(False)


class SettingsDialog(QDialog):
    """Settings panel popup: grouped cards, switches, searchable, live theme switch."""

    PAGE_DEFS = [
        ("General", "sliders", "General", "Appearance, chat behavior, images and startup"),
        ("Persona", "sparkle", "Persona", "Name, character and how it talks"),
        ("Personalization", "user", "Personalization", "Tell your assistant about you so conversations feel personal"),
        ("Shortcuts", "bolt", "Shortcuts", "Run several commands with one phrase"),
        ("Apps", "grid", "Apps", "Applications FreesIA can open for you"),
        ("Models", "cpu", "Models", "Choose which local AI models answer you"),
        ("Security", "shield", "Security", "What your assistant may do on this PC, and how your data is handled"),
        ("Diagnostics", "activity", "Diagnostics", "Is everything your assistant needs working?"),
    ]

    def __init__(self, parent=None, initial_page="General"):
        super().__init__(parent)
        self.setObjectName("SettingsDlg")
        self.setWindowTitle("Settings")
        w, h = 1000, 720
        if parent is not None:
            w = max(760, min(w, parent.width() - 40))
            h = max(560, min(h, parent.height() - 40))
        self.setFixedSize(w, h)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(settings_qss())
        self._p = settings_palette()
        self._groups = []
        self._threads = []
        self._cur_page_idx = 0
        self._page_names = [d[0] for d in self.PAGE_DEFS]
        if initial_page == "Account":  # old name of the (empty) page that became Models
            initial_page = "Models"
        self._initial_page = initial_page

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.root = QFrame()
        self.root.setObjectName("SettingsRoot")
        outer.addWidget(self.root)
        main_layout = QHBoxLayout(self.root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- left navigation ----
        nav_panel = QWidget()
        nav_panel.setObjectName("NavPanel")
        nav_panel.setFixedWidth(232)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(12, 20, 12, 16)
        nav_layout.setSpacing(4)

        nav_title = QLabel("Settings")
        nav_title.setObjectName("NavTitle")
        nav_layout.addWidget(nav_title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search settings")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(38)
        self.search_input.addAction(line_icon("search", self._p['sub'], 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.on_search_changed)
        nav_layout.addWidget(self.search_input)
        nav_layout.addSpacing(8)

        self.nav_buttons = {}
        for name, icon, _title, _sub in self.PAGE_DEFS:
            btn = QPushButton("  " + name)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIconSize(QSize(18, 18))
            btn.setProperty("icon_name", icon)
            btn.setIcon(line_icon(icon, self._p['sub'], 18))
            btn.clicked.connect(lambda _=False, n=name: self.switch_page(n))
            nav_layout.addWidget(btn)
            self.nav_buttons[name] = btn
        nav_layout.addStretch()
        main_layout.addWidget(nav_panel)

        # ---- right content ----
        content_panel = QWidget()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(32, 22, 20, 16)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.page_title = QLabel("General")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel("")
        self.page_subtitle.setObjectName("PageSub")
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        header_layout.addLayout(titles, 1)
        close_btn = QPushButton()
        close_btn.setObjectName("CloseBtn")
        close_btn.setIcon(line_icon("close", self._p['text2'], 18, 2.0))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close settings")
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(header)
        line = QFrame()
        line.setObjectName("HeaderLine")
        line.setFixedHeight(1)
        content_layout.addWidget(line)

        self.content_stack = QStackedWidget()
        builders = [
            self._build_general_page, self._build_persona_page, self._build_personalization_page, self._build_shortcuts_page,
            self._build_apps_page, self._build_models_page, self._build_security_page, self._build_diagnostics_page,
        ]
        for i, build in enumerate(builders):
            self._cur_page_idx = i
            self.content_stack.addWidget(build())
        content_layout.addWidget(self.content_stack, 1)
        main_layout.addWidget(content_panel, 1)

        self.switch_page(self._initial_page)
        self.nav_buttons[self._initial_page if self._initial_page in self.nav_buttons else 'General'].setFocus()

    # ------------------------------------------------------------------ chrome

    def switch_page(self, page_name):
        if page_name == "Account":
            page_name = "Models"
        if page_name not in self._page_names:
            return
        idx = self._page_names.index(page_name)
        self.content_stack.setCurrentIndex(idx)
        _n, _i, title, sub = self.PAGE_DEFS[idx]
        self.page_title.setText(title)
        self.page_subtitle.setText(sub)
        for name, btn in self.nav_buttons.items():
            on = name == page_name
            btn.setChecked(on)
            btn.setIcon(line_icon(btn.property("icon_name"), self._p['accent'] if on else self._p['sub'], 18))

    def toast(self, text: str):
        if not hasattr(self, '_toast'):
            self._toast = QLabel(self.root)
            self._toast.setObjectName("Toast")
            self._toast_timer = QTimer(self)
            self._toast_timer.setSingleShot(True)
            self._toast_timer.timeout.connect(self._toast.hide)
        self._toast.setText(text)
        self._toast.adjustSize()
        self._toast.move((self.width() - self._toast.width()) // 2, self.height() - self._toast.height() - 28)
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(2600)

    def done(self, result):
        for t in self._threads:
            try:
                if t.isRunning():
                    t.wait(2000)
            except RuntimeError:
                pass
        super().done(result)

    # ------------------------------------------------------------------ builders

    def _assistant(self):
        return getattr(self.parent(), 'assistant', None)

    def _new_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        body = QWidget()
        body.setObjectName("PageBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 24, 32, 32)
        lay.setSpacing(0)
        scroll.setWidget(body)
        return scroll, lay

    def _card(self, page_layout, name, warn=False, keywords=""):
        first = page_layout.count() == 0
        lbl = QLabel(name.upper())
        lbl.setObjectName("SecDanger" if warn else "Sec")
        f = lbl.font()
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        lbl.setFont(f)
        lbl.setContentsMargins(4, 0 if first else 28, 0, 10)
        page_layout.addWidget(lbl)
        card = QFrame()
        card.setObjectName("SCard")
        card.setProperty("warn", warn)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(1, 1, 1, 1)  # plain QFrame doesn't inset for its QSS border
        cl.setSpacing(0)
        page_layout.addWidget(card)
        group = {"page": self._cur_page_idx, "name": name.lower(), "label": lbl, "card": card,
                 "layout": cl, "rows": [], "keywords": keywords.lower(), "first": first}
        self._groups.append(group)
        return group

    def _add_row(self, group, title, desc=None, controls=(), icon=None):
        cont = QWidget()
        v = QVBoxLayout(cont)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        sep = QFrame()
        sep.setObjectName("RowSep")
        sep.setFixedHeight(1)
        v.addWidget(sep)
        inner = QWidget()
        h = QHBoxLayout(inner)
        h.setContentsMargins(20, 16, 20, 16)
        h.setSpacing(12)
        if icon:
            tile = QLabel()
            tile.setObjectName("IconTile")
            tile.setFixedSize(36, 36)
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setPixmap(line_pixmap(icon, self._p['accent'], 18))
            h.addWidget(tile)
            h.addSpacing(4)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("RT")
        col.addWidget(t)
        desc_label = None
        if desc:
            desc_label = QLabel(desc)
            desc_label.setObjectName("RD")
            desc_label.setWordWrap(True)
            col.addWidget(desc_label)
        h.addLayout(col, 1)
        for w in controls:
            h.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addWidget(inner)
        group["layout"].addWidget(cont)
        sep.setVisible(bool(group["rows"]))
        group["rows"].append({"w": cont, "sep": sep, "text": f"{title} {desc or ''}".lower()})
        return desc_label

    def _custom_body(self, group, margins=(20, 20, 20, 20), spacing=14):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(*margins)
        lay.setSpacing(spacing)
        group["layout"].addWidget(body)
        return lay

    def _field(self, label, widget):
        box = QVBoxLayout()
        box.setSpacing(6)
        lab = QLabel(label)
        lab.setObjectName("FieldLabel")
        box.addWidget(lab)
        box.addWidget(widget)
        return box

    def _finish_page(self, lay):
        lay.addStretch(1)

    # ------------------------------------------------------------------ search

    def on_search_changed(self, text):
        q = text.strip().lower()
        current = self.content_stack.currentIndex()
        pages_with_match = []
        seen_pages = set()
        for g in self._groups:
            if not q:
                visible = True
                for r in g["rows"]:
                    r["w"].setVisible(True)
                for i, r in enumerate(g["rows"]):
                    r["sep"].setVisible(i > 0)
            elif q in g["name"] or q in g["keywords"]:
                visible = True
                for r in g["rows"]:
                    r["w"].setVisible(True)
                for i, r in enumerate(g["rows"]):
                    r["sep"].setVisible(i > 0)
            else:
                shown = 0
                for r in g["rows"]:
                    m = q in r["text"]
                    r["w"].setVisible(m)
                    r["sep"].setVisible(m and shown > 0)
                    shown += 1 if m else 0
                visible = shown > 0
            g["label"].setVisible(visible)
            g["card"].setVisible(visible)
            if visible:
                top = 28 if g["page"] in seen_pages else 0
                g["label"].setContentsMargins(4, top, 0, 10)
                seen_pages.add(g["page"])
            if visible and q and g["page"] not in pages_with_match:
                pages_with_match.append(g["page"])
        if q:
            if pages_with_match and current not in pages_with_match:
                self.switch_page(self._page_names[pages_with_match[0]])
            elif not pages_with_match:
                self.page_subtitle.setText("No settings match your search")
            if pages_with_match and current in pages_with_match:
                self.page_subtitle.setText(self.PAGE_DEFS[current][3])
        else:
            self.page_subtitle.setText(self.PAGE_DEFS[self.content_stack.currentIndex()][3])

    # ------------------------------------------------------------------ GENERAL

    def _build_general_page(self):
        scroll, lay = self._new_page()
        a = self._assistant()

        g = self._card(lay, "Appearance")
        self.dark_mode_checkbox = ToggleSwitch(load_dark_mode_setting())
        self.dark_mode_checkbox.toggled.connect(self.on_dark_mode_toggled)
        self._add_row(g, "Dark mode", "Switches right away. FreesIA reopens this window in the new look.", [self.dark_mode_checkbox])
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English (United States)"])
        self.language_combo.setFixedHeight(36)
        self.language_combo.setMinimumWidth(210)
        self._add_row(g, "Language", "Replies and voice are English-only for now.", [self.language_combo])

        g = self._card(lay, "Chat")
        self.personality_mode_checkbox = ToggleSwitch(a.personality_mode_enabled if a else True)
        self.personality_mode_checkbox.toggled.connect(self.on_personality_mode_toggled)
        self._add_row(g, "Personality", "Turn off for a plain, neutral assistant with no character persona.", [self.personality_mode_checkbox])
        export_btn = settings_button("Export", "secondary", "download")
        export_btn.clicked.connect(self.on_export_chat_clicked)
        self._add_row(g, "Export current chat", "Save this conversation as a text file.", [export_btn])

        g = self._card(lay, "Image generation")
        self.image_safety_checkbox = ToggleSwitch(a.image_safety_checker if a else True)
        self.image_safety_checkbox.toggled.connect(self.on_image_safety_toggled)
        self._add_row(g, "Image safety checker", "Runs FastSD CPU's safety checker on generated images. On by default.", [self.image_safety_checkbox])
        model_btn = settings_button("Choose file", "secondary", "folder")
        model_btn.clicked.connect(self.on_choose_image_model_clicked)
        self._add_row(g, "Image model", "An SDXL .safetensors checkpoint. Leave unset to auto-detect from fastsdcpu/models/custom.", [model_btn])
        gallery_btn = settings_button("Gallery", "secondary", "image")
        gallery_btn.clicked.connect(self.on_open_gallery_clicked)
        open_btn = settings_button("Open folder", "secondary", "folder")
        open_btn.clicked.connect(self.on_open_images_folder_clicked)
        del_btn = settings_button("Delete unstarred", "danger", "trash")
        del_btn.clicked.connect(self.on_delete_generated_images_clicked)
        self._add_row(g, "Generated images", f"Browse and star what {AI_NAME} has drawn, open the folder, or clear out the rest.", [gallery_btn, open_btn, del_btn])

        g = self._card(lay, "Startup")
        self.startup_checkbox = ToggleSwitch(a.is_startup_enabled() if a else False)
        self.startup_checkbox.toggled.connect(self.on_startup_toggled)
        self._add_row(g, "Launch with Windows", "Start FreesIA automatically when you sign in.", [self.startup_checkbox])

        g = self._card(lay, "Folders")
        self.rescan_folders_btn = settings_button("Rescan", "secondary", "refresh")
        self.rescan_folders_btn.clicked.connect(self.on_rescan_folders_clicked)
        self.rescan_folders_status_label = self._add_row(
            g, "Desktop folders",
            "Finds Desktop folders and shortcuts by name so \"open X\" works for more than the standard folders. Run again after adding new ones.",
            [self.rescan_folders_btn])

        g = self._card(lay, "Memory")
        memory_count = len(getattr(a, 'memory_bank', []) or []) if a else 0
        clear_mem = settings_button("Clear", "danger", "trash")
        clear_mem.clicked.connect(self.on_clear_memory_clicked)
        self.memory_desc_label = self._add_row(
            g, "Remembered facts",
            f"{memory_count} fact(s) learned across chats. This happens automatically as you talk.",
            [clear_mem])

        self._finish_page(lay)
        return scroll

    def on_clear_memory_clicked(self):
        a = self._assistant()
        if not a:
            return
        if not themed_confirm(self, "Clear memory?", "FreesIA will forget everything it has learned about you across chats. This can't be undone.",
                              ok_text="Clear memory", danger=True):
            return
        a.clear_memory_bank()
        self.memory_desc_label.setText("0 fact(s) learned across chats. This happens automatically as you talk.")
        self.toast("Memory cleared")

    def on_rescan_folders_clicked(self):
        a = self._assistant()
        if not a:
            self.rescan_folders_status_label.setText("Couldn't reach FreesIA to rescan.")
            return
        self.rescan_folders_btn.setEnabled(False)
        self.rescan_folders_status_label.setText("Rescanning... this takes a moment.")
        self._rescan_folders_thread = RescanFoldersThread(a)
        self._rescan_folders_thread.finished.connect(self._on_rescan_folders_finished)
        self._threads.append(self._rescan_folders_thread)
        self._rescan_folders_thread.start()

    def _on_rescan_folders_finished(self, folder_count: int):
        self.rescan_folders_btn.setEnabled(True)
        self.rescan_folders_status_label.setText(f"Found {folder_count} folders. Up to date!")

    def on_dark_mode_toggled(self, checked: bool):
        save_dark_mode_setting(checked)
        mw = self.parent()
        if hasattr(mw, 'request_theme_switch') and mw.request_theme_switch(checked):
            self.accept()
        else:
            self.toast("Saved. It will apply the next time FreesIA opens.")

    def on_startup_toggled(self, checked: bool):
        a = self._assistant()
        if not a:
            return
        if not a.set_startup_enabled(checked):
            # Registry write failed: put the switch back so the UI doesn't claim a state that isn't true.
            self.startup_checkbox.blockSignals(True)
            self.startup_checkbox.setChecked(not checked)
            self.startup_checkbox.blockSignals(False)
            self.startup_checkbox.update()
            self.toast("Couldn't change the startup setting")

    def on_export_chat_clicked(self):
        main_window = self.parent()
        messages = getattr(main_window, 'current_chat_messages', None)
        if not messages:
            self.toast("No active chat to export")
            return
        chat_name = "chat"
        chat_id = getattr(main_window, 'current_chat_id', None)
        item = getattr(main_window, '_chat_item_widgets', {}).get(chat_id)
        if item:
            chat_name = item.chat_name
        safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', chat_name).strip('_') or "chat"
        default_path = str(Path.home() / "Desktop" / f"{safe_name}.txt")
        save_path, _ = QFileDialog.getSaveFileName(self, "Export Chat", default_path, "Text File (*.txt)")
        if not save_path:
            return
        lines = []
        for msg in messages:
            speaker = "You" if msg.get("role") == "user" else "FreesIA"
            lines.append(f"{speaker}: {msg.get('content', '')}")
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(lines))
            self.toast(f"Exported to {Path(save_path).name}")
        except Exception as e:
            themed_message(self, "Export failed", str(e))

    def on_image_safety_toggled(self, checked: bool):
        a = self._assistant()
        if a:
            a.set_image_safety_checker(checked)

    def on_choose_image_model_clicked(self):
        a = self._assistant()
        if not a:
            return
        start = a.image_model_path or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Choose image model", start, "SDXL checkpoint (*.safetensors)")
        if path:
            a.set_image_model_path(path)
            self.toast("Image model set")

    def on_personality_mode_toggled(self, checked: bool):
        a = self._assistant()
        if a:
            a.set_personality_mode(checked)

    def on_open_images_folder_clicked(self):
        a = self._assistant()
        if not a:
            return
        gen_dir = a.config_dir / "generated_images"
        gen_dir.mkdir(exist_ok=True)  # so this never fails just because nothing's been generated yet
        os.startfile(str(gen_dir))

    def on_open_gallery_clicked(self):
        a = self._assistant()
        if a:
            GalleryDialog(self, a, main_window=self.parent()).exec()

    def on_delete_generated_images_clicked(self):
        a = self._assistant()
        if not a:
            return
        if not themed_confirm(self, "Delete unstarred images?", "Every image FreesIA has made will be removed from disk, except the ones you starred. This can't be undone.",
                              ok_text="Delete images", danger=True):
            return
        count = a.delete_all_generated_images()
        self.toast(f"Deleted {count} image(s)")

    # ------------------------------------------------------------------ PERSONA

    def _build_persona_page(self):
        scroll, lay = self._new_page()
        a = self._assistant()
        info = {}
        try:
            info = a.get_persona_info() if a else {}
        except Exception:
            info = {}
        if not isinstance(info, dict):
            info = {}
        saved = info.get("custom_text")
        self._persona_saved = saved if isinstance(saved, str) else ""
        src = info.get("source")
        self._persona_source = src if src in ("custom", "preset") else "custom"
        pre = info.get("preset")
        pre = pre if isinstance(pre, int) and not isinstance(pre, bool) and 0 <= pre < len(PERSONA_LEVELS) else 3
        p = self._p

        g = self._card(lay, "Assistant name", keywords="name rename call assistant")
        nb = self._custom_body(g, margins=(16, 14, 16, 14), spacing=8)
        self.ai_name_input = QLineEdit()
        self.ai_name_input.setMaxLength(40)
        self.ai_name_input.setFixedHeight(40)
        self.ai_name_input.setText(str(info.get("name") or AI_NAME))
        self.ai_name_input.editingFinished.connect(self._ai_name_changed)
        nb.addLayout(self._field("Name", self.ai_name_input))
        name_hint = QLabel("What your assistant calls itself. It appears on its messages and in its instructions.")
        name_hint.setObjectName("RD")
        name_hint.setWordWrap(True)
        nb.addWidget(name_hint)

        g = self._card(lay, "Personality source", keywords="persona character custom presets")
        body = self._custom_body(g, margins=(16, 16, 16, 16), spacing=10)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.src_custom = SourceTile("My own text", "Exactly what you write below. Nothing is changed.")
        self.src_preset = SourceTile("Presets", "Soft, Gentle, Balanced, Blunt, Cold.")
        self.src_custom.clicked.connect(lambda: self._persona_set_source("custom"))
        self.src_preset.clicked.connect(lambda: self._persona_set_source("preset"))
        row.addWidget(self.src_custom, 1)
        row.addWidget(self.src_preset, 1)
        body.addLayout(row)

        # ---- own text
        self._g_text = self._card(lay, "Your personality text", keywords="personality txt file drop type write edit")
        tb = self._custom_body(self._g_text, margins=(16, 14, 16, 14), spacing=10)
        head = QHBoxLayout()
        self.persona_hint_title = QLabel("Type here, or drop a .txt file onto the box.")
        self.persona_hint_title.setObjectName("RD")
        self.persona_hint_title.setWordWrap(True)
        head.addWidget(self.persona_hint_title, 1)
        self.persona_count = QLabel("")
        self.persona_count.setObjectName("RD")
        head.addWidget(self.persona_count)
        tb.addLayout(head)
        self.persona_edit = PersonaTextEdit()
        self.persona_edit.setPlaceholderText("Describe your assistant: how it talks, what it cares about, what it would never say.")
        self.persona_edit.setFixedHeight(230)
        self.persona_edit.setStyleSheet(
            f"QTextEdit {{ background: {p['input_bg']}; border: 1.5px dashed {p['btn_border']}; border-radius: 12px; padding: 12px 14px; color: {p['text']}; font-size: 13px; }}"
            f"QTextEdit:focus {{ border: 1.5px solid {p['accent']}; }}"
            f"QTextEdit[drag=\"true\"] {{ border: 2px dashed {p['accent']}; background: {p['active']}; }}")
        self.persona_edit.setPlainText(self._persona_saved)
        self.persona_edit.textChanged.connect(self._persona_changed)
        self.persona_edit.file_dropped.connect(self._persona_filled_from_file)
        tb.addWidget(self.persona_edit)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.persona_status = QLabel("")
        self.persona_status.setObjectName("RD")
        self.persona_status.setWordWrap(True)
        btns.addWidget(self.persona_status, 1)
        self.persona_discard = settings_button("Discard", "secondary")
        self.persona_discard.clicked.connect(self._persona_discard)
        load_btn = settings_button("Load file...", "secondary", "upload")
        load_btn.clicked.connect(self._persona_load_file)
        reload_btn = settings_button("Reload", "secondary", "refresh")
        reload_btn.clicked.connect(self._persona_reload)
        self.persona_save = settings_button("Save", "primary")
        self.persona_save.clicked.connect(self._persona_save)
        for b in (self.persona_discard, load_btn, reload_btn, self.persona_save):
            btns.addWidget(b)
        tb.addLayout(btns)

        # ---- templates
        self._g_tpl = self._card(lay, "Or start from a template", keywords="template starter example")
        tpl_body = self._custom_body(self._g_tpl, margins=(16, 14, 16, 14), spacing=10)
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (title, desc, text) in enumerate(PERSONA_TEMPLATES):
            tile = SourceTile(title, desc)
            tile.badge.hide()
            tile.badge.setText("")
            tile.setProperty("sel", False)
            tile.clicked.connect(lambda t=text: self._persona_use_template(t))
            grid.addWidget(tile, i // 2, i % 2)
        tpl_body.addLayout(grid)

        # ---- presets
        self._g_slider = self._card(lay, "How it talks to you", keywords="presets slider soft gentle balanced blunt cold")
        sb = self._custom_body(self._g_slider, margins=(20, 18, 20, 16), spacing=6)
        top = QHBoxLayout()
        self.level_name = QLabel("")
        self.level_name.setObjectName("RT")
        self.level_name.setStyleSheet(f"color: {p['accent']}; font-weight: 700; font-size: 14px; background: transparent;")
        top.addWidget(self.level_name)
        top.addStretch()
        sb.addLayout(top)
        self.level_desc = QLabel("")
        self.level_desc.setObjectName("RD")
        sb.addWidget(self.level_desc)
        self.persona_slider = QSlider(Qt.Orientation.Horizontal)
        self.persona_slider.setRange(0, len(PERSONA_LEVELS) - 1)
        self.persona_slider.setPageStep(1)
        self.persona_slider.setMinimumHeight(30)
        self.persona_slider.setValue(pre)
        sb.addSpacing(6)
        sb.addWidget(self.persona_slider)
        labs = QHBoxLayout()
        labs.setContentsMargins(0, 0, 0, 0)
        self._level_btns = []
        for i, (name, _b, _e) in enumerate(PERSONA_LEVELS):
            b = QPushButton(name)
            b.setFlat(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=i: self.persona_slider.setValue(v))
            self._level_btns.append(b)
            labs.addWidget(b)
            if i < len(PERSONA_LEVELS) - 1:
                labs.addStretch()
        sb.addLayout(labs)
        self._persona_timer = QTimer(self)
        self._persona_timer.setSingleShot(True)
        self._persona_timer.setInterval(350)
        self._persona_timer.timeout.connect(self._persona_apply_preset)
        self.persona_slider.valueChanged.connect(self._persona_level_changed)

        self._g_examples = self._card(lay, "Same question, each setting", keywords="examples preview")
        eb = self._custom_body(self._g_examples, margins=(18, 12, 18, 12), spacing=0)
        q = QLabel("You: how do I loop three times in python?")
        q.setObjectName("RD")
        eb.addWidget(q)
        eb.addSpacing(6)
        self._example_rows = []
        for i, (name, _b, ex) in enumerate(PERSONA_LEVELS):
            r = QHBoxLayout()
            r.setContentsMargins(0, 7, 0, 7)
            n = QLabel(name)
            n.setFixedWidth(70)
            t = QLabel(ex)
            t.setWordWrap(True)
            r.addWidget(n)
            r.addWidget(t, 1)
            eb.addLayout(r)
            self._example_rows.append((n, t))

        foot = QLabel(f"Switching to Presets never deletes your text: it stays saved in Personality.txt. Changes apply to new messages, and {AI_NAME}'s short-term memory of the current conversation resets so the new personality takes effect.")
        foot.setObjectName("Foot")
        foot.setWordWrap(True)
        foot.setContentsMargins(4, 12, 0, 0)
        lay.addWidget(foot)
        self._build_checkin_card(lay)
        self._build_voice_card(lay)
        self._finish_page(lay)
        self._persona_level_changed(pre, apply=False)
        self._persona_changed()
        self._persona_refresh_visibility()
        return scroll

    # ------------------------------------------------------------------ check-ins card

    def _build_checkin_card(self, lay):
        cfg = load_checkin_cfg()
        g = self._card(lay, "Check-ins", keywords="proactive message first quiet hours notification assistant messages me")
        self.ci_enabled = ToggleSwitch(cfg["enabled"])
        self._add_row(g, f"Let {AI_NAME} message me first",
                      "Off by default. It picks a moment and writes one short line from your recent chats and the time of day.",
                      [self.ci_enabled])
        self.ci_freq = QComboBox()
        self.ci_freq.addItems(["Rarely", "Sometimes", "Often"])
        self.ci_freq.setCurrentIndex(["rarely", "sometimes", "often"].index(cfg["frequency"]))
        self.ci_freq.setFixedHeight(36)
        self.ci_freq.setMinimumWidth(130)
        self._add_row(g, "How often", "A rough ceiling, not a schedule. It skips the message if you were just chatting.", [self.ci_freq])
        self.ci_qs, self.ci_qe = QComboBox(), QComboBox()
        for c, key in ((self.ci_qs, "quiet_start"), (self.ci_qe, "quiet_end")):
            for h in range(24):
                c.addItem(_hour_label(h), f"{h:02d}:00")
            idx = c.findData(cfg[key])
            if idx < 0:  # saved value isn't on the hour grid
                mins = _hhmm_to_min(cfg[key])
                c.addItem(f"{(mins // 60 % 12) or 12}:{mins % 60:02d} {'AM' if mins < 720 else 'PM'}", cfg[key])
                idx = c.count() - 1
            c.setCurrentIndex(idx)
            c.setFixedHeight(36)
            c.setMinimumWidth(110)
        to_lbl = QLabel("to")
        to_lbl.setObjectName("RD")
        self._add_row(g, "Quiet hours", "No check-ins in this window.", [self.ci_qs, to_lbl, self.ci_qe])
        self.ci_hold = ToggleSwitch(cfg["hold_fullscreen"])
        self._add_row(g, "Stay out of the way",
                      "Hold while a game or fullscreen app is running, then show it afterwards.", [self.ci_hold])
        self.ci_notify = ToggleSwitch(cfg["notify"])
        self._add_row(g, "Show as a Windows notification",
                      "Otherwise it just appears in the chat when you open FreesIA.", [self.ci_notify])
        test = settings_button("Send a test", "secondary", "message")
        test.clicked.connect(self._ci_test)
        self._add_row(g, "Try it now", "Sends one check-in immediately, ignoring frequency and quiet hours.", [test])
        for w in (self.ci_enabled, self.ci_hold, self.ci_notify):
            w.toggled.connect(lambda *_: self._ci_save())
        for c in (self.ci_freq, self.ci_qs, self.ci_qe):
            c.currentIndexChanged.connect(lambda *_: self._ci_save())

    def _ci_save(self):
        cfg = load_checkin_cfg()
        cfg.update({
            "enabled": self.ci_enabled.isChecked(),
            "frequency": ["rarely", "sometimes", "often"][max(0, self.ci_freq.currentIndex())],
            "quiet_start": self.ci_qs.currentData() or cfg["quiet_start"],
            "quiet_end": self.ci_qe.currentData() or cfg["quiet_end"],
            "hold_fullscreen": self.ci_hold.isChecked(),
            "notify": self.ci_notify.isChecked(),
        })
        save_checkin_cfg(cfg)
        mw = self.parent()
        if hasattr(mw, "_checkin_reschedule"):
            mw._checkin_reschedule()

    def _ci_test(self):
        mw = self.parent()
        if not hasattr(mw, "start_checkin") or not mw.start_checkin(force=True):
            self.toast("Wait for the current reply to finish first")
        else:
            self.toast(f"{AI_NAME} is writing one...")

    # ------------------------------------------------------------------ voice card

    def _build_voice_card(self, lay):
        a = self._assistant()
        v = getattr(a, "local_voice", None) if a else None
        g = self._card(lay, "Voice", keywords="speak read aloud tts local voice piper speed volume")
        if not isinstance(getattr(v, "cfg", None), dict):
            self._voice = None
            self._add_row(g, "Voice isn't available", f"This FreesIA backend doesn't include the local voice yet.")
            return
        self._voice = v
        cfg = v.cfg
        self.vc_read = ToggleSwitch(cfg["read_aloud"])
        self.vc_read.toggled.connect(lambda on: v.set_cfg(read_aloud=bool(on)))
        self._add_row(g, "Read replies aloud", f"{AI_NAME} speaks each reply when it finishes. Starting a new message stops it.", [self.vc_read])
        self.vc_engine = QComboBox()
        self.vc_engine.addItem("Windows voice", "system")
        self.vc_engine.addItem("Local voice", "local")
        self.vc_engine.setCurrentIndex(1 if cfg["engine"] == "local" else 0)
        self.vc_engine.setFixedHeight(36)
        self.vc_engine.setMinimumWidth(160)
        self.vc_engine.currentIndexChanged.connect(self._vc_engine_changed)
        self._add_row(g, "Voice", f"The local voice is a neural voice that runs on this PC. If it can't load, the Windows voice takes over.", [self.vc_engine])
        self.vc_setup_btn = settings_button("Set up", "primary", "download")
        self.vc_setup_btn.clicked.connect(self._vc_setup)
        self.vc_setup_desc = self._add_row(g, "Local voice setup", "...", [self.vc_setup_btn])
        self.vc_rows = {}
        for item in v.VOICES:
            prev = settings_button("Preview", "secondary", "play" if "play" in _ICON_SVG else None)
            use = settings_button("Use", "secondary")
            prev.clicked.connect(lambda _=False, k=item["key"]: self._vc_preview(k))
            use.clicked.connect(lambda _=False, k=item["key"]: self._vc_use(k))
            desc = self._add_row(g, item["name"], item["desc"], [prev, use])
            self.vc_rows[item["key"]] = (desc, prev, use, item)
        self.vc_speed = QSlider(Qt.Orientation.Horizontal)
        self.vc_speed.setRange(60, 150)
        self.vc_speed.setValue(int(round(cfg["speed"] * 100)))
        self.vc_speed.setFixedWidth(200)
        self.vc_speed_lbl = QLabel("")
        self.vc_speed_lbl.setObjectName("RD")
        self.vc_speed_lbl.setMinimumWidth(44)
        self._add_row(g, "Speed", "Applies to both voices.", [self.vc_speed, self.vc_speed_lbl])
        self.vc_vol = QSlider(Qt.Orientation.Horizontal)
        self.vc_vol.setRange(0, 100)
        self.vc_vol.setValue(int(round(cfg["volume"] * 100)))
        self.vc_vol.setFixedWidth(200)
        self.vc_vol_lbl = QLabel("")
        self.vc_vol_lbl.setObjectName("RD")
        self.vc_vol_lbl.setMinimumWidth(44)
        self._add_row(g, "Volume", None, [self.vc_vol, self.vc_vol_lbl])
        self._vc_save_timer = QTimer(self)
        self._vc_save_timer.setSingleShot(True)
        self._vc_save_timer.setInterval(300)
        self._vc_save_timer.timeout.connect(lambda: v.set_cfg(speed=self.vc_speed.value() / 100.0, volume=self.vc_vol.value() / 100.0))
        for s in (self.vc_speed, self.vc_vol):
            s.valueChanged.connect(self._vc_sliders_changed)
        self.vc_remove_btn = settings_button("Remove", "danger", "trash")
        self.vc_remove_btn.clicked.connect(self._vc_remove)
        self.vc_files_desc = self._add_row(g, "Voice files", "...", [self.vc_remove_btn])
        self._vc_sliders_changed()
        self._vc_refresh()

    def _vc_sliders_changed(self, *_):
        self.vc_speed_lbl.setText(f"{self.vc_speed.value() / 100:.2f}x")
        self.vc_vol_lbl.setText(f"{self.vc_vol.value()}%")
        self._vc_save_timer.start()

    def _vc_refresh(self):
        v = self._voice
        if v is None:
            return
        eng = v.engine_installed()
        ready = v.is_ready()
        if not eng:
            self.vc_setup_desc.setText("The voice engine isn't installed yet (small, one time). Needs internet once.")
            self.vc_setup_btn.setText("Install engine")
            self.vc_setup_btn.setVisible(True)
        elif not v.installed():
            self.vc_setup_desc.setText(f"Engine ready. Download a voice below to start using the local voice.")
            self.vc_setup_btn.setVisible(False)
        else:
            self.vc_setup_desc.setText("Ready. Everything runs on this PC.")
            self.vc_setup_btn.setVisible(False)
        for key, (desc, prev, use, item) in self.vc_rows.items():
            have = v.installed(key)
            sel = key == v.cfg["voice"]
            desc.setText(f"{item['desc']}  -  " + (f"In use" if sel and have else "Downloaded" if have else f"Not downloaded (~{item['mb']} MB)"))
            use.setText("In use" if sel else "Use")
            use.setEnabled(not sel)
        mb = v.disk_bytes() / (1024 * 1024)
        self.vc_files_desc.setText(f"{mb:.0f} MB on disk. Voices are downloaded once and kept here." if mb >= 1 else "Nothing downloaded yet.")
        self.vc_remove_btn.setEnabled(mb >= 1)

    def _vc_engine_changed(self, *_):
        v = self._voice
        v.set_cfg(engine=self.vc_engine.currentData())
        if self.vc_engine.currentData() == "local" and not v.is_ready():
            self.toast(f"Finish the local voice setup below, or the Windows voice will be used")

    def _vc_job(self, kind, key=None, then=None):
        v = self._voice
        t = VoiceJobThread(v, kind, key)
        self._vc_busy = True
        for _d, prev_b, use_b, _i in self.vc_rows.values():
            prev_b.setEnabled(False)
            use_b.setEnabled(False)
        self.vc_setup_btn.setEnabled(False)
        t.progress.connect(self.toast)

        def fin(ok, msg):
            self._vc_busy = False
            for _d, prev_b, _u, _i in self.vc_rows.values():
                prev_b.setEnabled(True)
            self.vc_setup_btn.setEnabled(True)
            self._vc_refresh()
            if msg and (not ok or kind != "preview"):
                self.toast(msg if ok else f"Failed: {msg}")
            if ok and then:
                then()
        t.done.connect(fin)
        self._threads.append(t)
        t.start()

    def _vc_setup(self):
        if getattr(self, "_vc_busy", False):
            return
        v = self._voice
        if not v.engine_installed():
            self._vc_job("install")
        elif not v.installed():
            self._vc_download(v.cfg["voice"])

    def _vc_download(self, key, then=None):
        item = next(i for i in self._voice.VOICES if i["key"] == key)
        if themed_confirm(self, f"Download {item['name']}?",
                          f"This is a one-time download of about {item['mb']} MB from Hugging Face. The voice then runs offline.",
                          ok_text="Download"):
            self._vc_job("download", key, then)

    def _vc_preview(self, key):
        v = self._voice
        if getattr(self, "_vc_busy", False):
            return
        if not v.engine_installed():
            self.toast("Install the voice engine first")
            return
        if not v.installed(key):
            self._vc_download(key, then=lambda: self._vc_job("preview", key))
            return
        v.stop()
        self._vc_job("preview", key)

    def _vc_use(self, key):
        v = self._voice
        if getattr(self, "_vc_busy", False):
            return
        if not v.installed(key):
            self._vc_download(key, then=lambda: self._vc_use(key))
            return
        v.set_cfg(voice=key)
        self._vc_refresh()

    def _vc_remove(self):
        v = self._voice
        if themed_confirm(self, "Remove voice files?", "The downloaded voices are deleted. The Windows voice is used until you download one again.",
                          ok_text="Remove", danger=True):
            v.remove_all()
            v.set_cfg(engine="system")
            self.vc_engine.blockSignals(True)
            self.vc_engine.setCurrentIndex(0)
            self.vc_engine.blockSignals(False)
            self._vc_refresh()

    def _persona_refresh_visibility(self):
        custom = self._persona_source == "custom"
        self.src_custom.set_selected(custom)
        self.src_preset.set_selected(not custom)
        empty = not self.persona_edit.toPlainText().strip()
        for g, show in ((self._g_text, custom), (self._g_tpl, custom and empty),
                        (self._g_slider, not custom), (self._g_examples, not custom)):
            g["label"].setVisible(show)
            g["card"].setVisible(show)

    def _ai_name_changed(self):
        a = self._assistant()
        new = (self.ai_name_input.text() or "").strip() or "FreesIA"
        if new == AI_NAME:
            self.ai_name_input.setText(AI_NAME)
            return
        if a and hasattr(a, "set_assistant_name"):
            try:
                a.set_assistant_name(new)
                new = getattr(a, "assistant_name", new)
            except Exception:
                pass
        set_ai_name(new)
        self.ai_name_input.setText(AI_NAME)
        w = self.parent()
        if w is not None and hasattr(w, "refresh_ai_name"):
            w.refresh_ai_name()
        self.toast("Name saved")

    def _persona_set_source(self, src):
        if src == self._persona_source:
            return
        self._persona_source = src
        a = self._assistant()
        if a:
            try:
                a.set_persona(source=src)
            except Exception as e:
                print(f"Couldn't switch persona: {e}")
        self._persona_refresh_visibility()
        self.toast("Using your own text" if src == "custom" else "Using presets")

    def _persona_changed(self):
        text = self.persona_edit.toPlainText().strip()
        dirty = text != self._persona_saved.strip()
        n = len(text)
        self.persona_count.setText(f"{n:,} characters")
        self.persona_status.setText("Unsaved changes. Nothing is used until you press Save." if dirty else "")
        self.persona_discard.setVisible(dirty)
        self.persona_save.setEnabled(dirty and bool(text))
        if hasattr(self, "_g_tpl"):
            self._persona_refresh_visibility()

    def _persona_filled_from_file(self, text):
        self.persona_edit.setPlainText(text.strip())

    def _persona_load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load personality text", str(Path.home() / "Desktop"), "Text files (*.txt *.md)")
        if path:
            try:
                self.persona_edit.setPlainText(read_text_file_loose(path).strip())
            except Exception as e:
                themed_message(self, "Couldn't read that file", str(e))

    def _persona_use_template(self, text):
        self.persona_edit.setPlainText(text)
        self.persona_edit.setFocus()

    def _persona_discard(self):
        self.persona_edit.setPlainText(self._persona_saved)

    def _persona_reload(self):
        a = self._assistant()
        if not a:
            return
        dirty = self.persona_edit.toPlainText().strip() != self._persona_saved.strip()
        if dirty and not themed_confirm(self, "Discard your changes?", "The box will be replaced with what is saved in Personality.txt.", ok_text="Reload"):
            return
        try:
            self._persona_saved = a.read_custom_personality()
        except Exception:
            self._persona_saved = ""
        self.persona_edit.setPlainText(self._persona_saved)
        self.toast("Reloaded from Personality.txt")

    def _persona_save(self):
        a = self._assistant()
        text = self.persona_edit.toPlainText().strip()
        if not a or not text:
            return
        if a.save_custom_personality(text):
            self._persona_saved = text
            self._persona_changed()
            self.toast("Personality saved")
        else:
            themed_message(self, "Couldn't save", "Personality.txt couldn't be written. Check that the file isn't read-only.")

    def _persona_level_changed(self, value, apply=True):
        name, blurb, _ex = PERSONA_LEVELS[value]
        self.level_name.setText(name)
        self.level_desc.setText(blurb)
        p = self._p
        for i, b in enumerate(self._level_btns):
            on = i == value
            b.setStyleSheet(f"QPushButton {{ border: none; background: transparent; color: {p['text'] if on else p['sub']}; font-size: 12px; font-weight: {'700' if on else '400'}; padding: 2px 0; }}")
        for i, (n, t) in enumerate(self._example_rows):
            on = i == value
            n.setStyleSheet(f"color: {p['accent'] if on else p['sub']}; font-size: 12px; font-weight: {'700' if on else '500'}; background: transparent;")
            t.setStyleSheet(f"color: {p['text'] if on else p['text2']}; font-size: 13px; background: transparent;")
        if apply:
            self._persona_timer.start()

    def _persona_apply_preset(self):
        a = self._assistant()
        if a:
            try:
                a.set_persona(source="preset", preset=self.persona_slider.value())
                self._persona_source = "preset"
                self.toast(f"Personality: {PERSONA_LEVELS[self.persona_slider.value()][0]}")
            except Exception as e:
                print(f"Couldn't set preset: {e}")

    # ------------------------------------------------------------------ DIAGNOSTICS

    DIAG_ROWS = [
        ("ollama", "Ollama", "Local AI server"),
        ("chat_model", "Chat model", "Used for longer, harder messages"),
        ("fast_model", "Fast model", "Used for quick replies"),
        ("image", "Image generator", "FastSD CPU"),
        ("voice", "Voice", "Text to speech"),
        ("mic", "Microphone", "Speech input"),
        ("system", "Memory and disk", "This PC"),
    ]

    def _build_diagnostics_page(self):
        scroll, lay = self._new_page()
        g = self._card(lay, "Status", keywords="health check problems")
        self._diag_widgets = {}
        for key, title, desc in self.DIAG_ROWS:
            status = QLabel("Checking...")
            status.setObjectName("RD")
            btn = settings_button("", "secondary")
            btn.setFixedHeight(32)
            btn.setVisible(False)
            desc_lbl = self._add_row(g, title, desc, [status, btn])
            self._diag_widgets[key] = (status, btn, desc_lbl, desc)
        self._diag_results = {}
        self._diag_thread = None

        g = self._card(lay, "Report", keywords="copy support")
        self.diag_recheck = settings_button("Recheck", "secondary", "refresh")
        self.diag_recheck.clicked.connect(self._run_diagnostics)
        copy_btn = settings_button("Copy report", "secondary", "copy")
        copy_btn.clicked.connect(self._copy_diag_report)
        self._add_row(g, "Copy a report", "Plain text with versions and statuses. It contains no chats or personal info, which makes it safe to paste when asking for help.", [self.diag_recheck, copy_btn])
        foot = QLabel("Amber and red rows say what to do next. Nothing here changes anything unless you press its button.")
        foot.setObjectName("Foot")
        foot.setWordWrap(True)
        foot.setContentsMargins(4, 12, 0, 0)
        lay.addWidget(foot)
        self._finish_page(lay)
        QTimer.singleShot(0, self._run_diagnostics)
        return scroll

    def _run_diagnostics(self):
        a = self._assistant()
        if not a or (self._diag_thread is not None and self._diag_thread.isRunning()):
            return
        for key, (status, btn, desc_lbl, desc) in self._diag_widgets.items():
            status.setText("Checking...")
            status.setStyleSheet("")
            btn.setVisible(False)
        self.diag_recheck.setEnabled(False)
        t = DiagnosticsThread(a)
        t.done.connect(self._on_diag_done)
        self._diag_thread = t
        self._threads.append(t)
        t.start()

    def _on_diag_done(self, res):
        self.diag_recheck.setEnabled(True)
        self._diag_results = res
        self._diag_models = getattr(self._diag_thread, "names", [])
        colors = {"ok": "#5FB878", "warn": "#E0B15A", "bad": self._p['danger'], "none": self._p['sub']}
        for key, (status, btn, desc_lbl, desc) in self._diag_widgets.items():
            level, text, detail, action = res.get(key, ("none", "Unknown", desc, None))
            status.setText(f"● {text}")
            status.setStyleSheet(f"color: {colors.get(level, self._p['sub'])}; font-size: 12px; font-weight: 600; background: transparent;")
            if desc_lbl is not None:
                desc_lbl.setText(detail)
            try:
                btn.clicked.disconnect()
            except TypeError:
                pass
            if action:
                btn.setText(action[0])
                btn.clicked.connect(lambda _=False, act=action[1], k=key: self._diag_action(act, k))
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _diag_action(self, act, key):
        if act == "models":
            self.switch_page("Models")
        elif act == "start_image":
            a = self._assistant()
            status, btn, desc_lbl, _d = self._diag_widgets[key]
            btn.setEnabled(False)
            status.setText("● Starting...")
            t = ImageServerStartThread(a)
            t.done.connect(lambda ok: (btn.setEnabled(True), self._run_diagnostics()))
            self._threads.append(t)
            t.start()

    def _copy_diag_report(self):
        import platform
        from datetime import datetime as _dt
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR
        except Exception:
            PYQT_VERSION_STR = "?"
        lines = ["FreesIA diagnostics report", _dt.now().strftime("%Y-%m-%d %H:%M"),
                 f"Python {platform.python_version()} / PyQt6 {PYQT_VERSION_STR} / {platform.platform()}", ""]
        for key, title, _d in self.DIAG_ROWS:
            level, text, detail, _a = self._diag_results.get(key, ("none", "Not checked", "", None))
            lines.append(f"{title}: {text} - {detail}")
        models = getattr(self, "_diag_models", [])
        if models:
            lines += ["", "Installed Ollama models: " + ", ".join(models)]
        QApplication.clipboard().setText("\n".join(lines))
        self.toast("Report copied")

    # ------------------------------------------------------------------ PERSONALIZATION

    def _build_personalization_page(self):
        scroll, lay = self._new_page()
        profile = self.parent().assistant.user_profile

        g = self._card(lay, "About you", keywords="nickname occupation visual description likes dislikes profile")
        body = self._custom_body(g)

        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText(f"What should {AI_NAME} call you?")
        self.nickname_input.setText(profile.get("nickname", ""))
        self.occupation_input = QLineEdit()
        self.occupation_input.setPlaceholderText("What do you do?")
        self.occupation_input.setText(profile.get("occupation", ""))
        self.visual_input = QLineEdit()
        self.visual_input.setPlaceholderText("How you look, so image requests can include you")
        self.visual_input.setText(profile.get("visual_description", ""))
        for le in (self.nickname_input, self.occupation_input, self.visual_input):
            le.setFixedHeight(40)

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(self._field("Nickname", self.nickname_input), 1)
        row1.addLayout(self._field("Occupation", self.occupation_input), 1)
        body.addLayout(row1)
        body.addLayout(self._field("Visual description", self.visual_input))

        self.likes_input = QTextEdit()
        self.likes_input.setPlaceholderText("Things you enjoy")
        self.likes_input.setPlainText(profile.get("likes", ""))
        self.dislikes_input = QTextEdit()
        self.dislikes_input.setPlaceholderText("Things to avoid")
        self.dislikes_input.setPlainText(profile.get("dislikes", ""))
        self.other_input = QTextEdit()
        self.other_input.setPlaceholderText(f"Anything else {AI_NAME} should know about you")
        self.other_input.setPlainText(profile.get("other_info", ""))
        for te in (self.likes_input, self.dislikes_input, self.other_input):
            te.setFixedHeight(76)
            te.setTabChangesFocus(True)
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addLayout(self._field("Likes and interests", self.likes_input), 1)
        row2.addLayout(self._field("Dislikes", self.dislikes_input), 1)
        body.addLayout(row2)
        body.addLayout(self._field("Anything else", self.other_input))

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = settings_button("Save profile", "primary")
        save_btn.setMinimumWidth(130)
        save_btn.clicked.connect(self.save_user_profile)
        save_row.addWidget(save_btn)
        body.addLayout(save_row)

        g = self._card(lay, "Relationship")
        reset_btn = settings_button("Reset", "danger")
        reset_btn.clicked.connect(self.reset_relationship)
        self._add_row(g, "Reset relationship and memories",
                      f"Clears your progress with {AI_NAME} and everything it has remembered about you. This can't be undone.", [reset_btn])

        self._finish_page(lay)
        return scroll

    def save_user_profile(self):
        a = self.parent().assistant
        a.user_profile["nickname"] = self.nickname_input.text().strip()
        a.user_profile["occupation"] = self.occupation_input.text().strip()
        a.user_profile["visual_description"] = self.visual_input.text().strip()
        a.user_profile["likes"] = self.likes_input.toPlainText().strip()
        a.user_profile["dislikes"] = self.dislikes_input.toPlainText().strip()
        a.user_profile["other_info"] = self.other_input.toPlainText().strip()
        a.save_user_profile()
        self.toast("Profile saved")

    def reset_relationship(self):
        if not themed_confirm(
                self, "Reset relationship?",
                "This erases all relationship progress, deletes shared memories and returns to Level 1 (Strangers). It can't be undone.",
                ok_text="Reset", danger=True, confirm_phrase="RESET"):
            return
        self.parent().assistant.relationship_manager.reset()
        self.toast("Relationship reset to a fresh start")

    # ------------------------------------------------------------------ SHORTCUTS

    def _drop_groups_for_page(self, idx):
        self._groups = [g for g in self._groups if g["page"] != idx]

    def _build_shortcuts_page(self):
        idx = self._page_names.index("Shortcuts")
        self._cur_page_idx = idx
        self._drop_groups_for_page(idx)
        scroll, lay = self._new_page()
        shortcuts = self.parent().assistant.custom_shortcuts

        g = self._card(lay, "Your shortcuts", keywords="custom commands macro")
        if shortcuts:
            for name, actions in shortcuts.items():
                del_btn = QPushButton()
                del_btn.setObjectName("IconBtn")
                del_btn.setIcon(line_icon("trash", self._p['danger'], 16))
                del_btn.setIconSize(QSize(16, 16))
                del_btn.setFixedSize(34, 34)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setToolTip(f"Delete '{name}'")
                del_btn.clicked.connect(lambda _=False, n=name: self.delete_shortcut(n))
                self._add_row(g, name, "  →  ".join(actions), [del_btn], icon="bolt")
        else:
            self._add_row(g, "No shortcuts yet", "Create one below, then say its name to run all of its actions.")

        g = self._card(lay, "Create a shortcut", keywords="new add shortcut name actions")
        body = self._custom_body(g)
        self.shortcut_name_input = QLineEdit()
        self.shortcut_name_input.setPlaceholderText("e.g. work, gaming, morning")
        self.shortcut_name_input.setFixedHeight(40)
        body.addLayout(self._field("Shortcut name", self.shortcut_name_input))
        self.shortcut_actions_input = QTextEdit()
        self.shortcut_actions_input.setPlaceholderText("open chrome\nopen spotify\ncheck weather")
        self.shortcut_actions_input.setFixedHeight(96)
        self.shortcut_actions_input.setTabChangesFocus(True)
        body.addLayout(self._field("Actions (one per line)", self.shortcut_actions_input))
        row = QHBoxLayout()
        row.addStretch()
        create_btn = settings_button("Create shortcut", "primary", "plus")
        create_btn.clicked.connect(self.create_shortcut)
        row.addWidget(create_btn)
        body.addLayout(row)

        self._finish_page(lay)
        return scroll

    def create_shortcut(self):
        name = self.shortcut_name_input.text().strip()
        actions_text = self.shortcut_actions_input.toPlainText().strip()
        if not name or not actions_text:
            themed_message(self, "Missing information", "Please provide both a shortcut name and at least one action.")
            return
        actions = [x.strip() for x in actions_text.split('\n') if x.strip()]
        self.parent().assistant.add_shortcut(name, actions)
        self.refresh_shortcuts_page()
        self.toast(f"Shortcut '{name}' created. Say \"{name}\" or \"run {name}\" to use it")

    def delete_shortcut(self, name):
        if not themed_confirm(self, "Delete shortcut?", f"The '{name}' shortcut will be removed.", ok_text="Delete", danger=True):
            return
        self.parent().assistant.remove_shortcut(name)
        self.refresh_shortcuts_page()

    def refresh_shortcuts_page(self):
        current = self.content_stack.currentIndex()
        new_page = self._build_shortcuts_page()
        sidx = self._page_names.index("Shortcuts")
        old = self.content_stack.widget(sidx)
        self.content_stack.removeWidget(old)
        old.deleteLater()
        self.content_stack.insertWidget(sidx, new_page)
        self.content_stack.setCurrentIndex(current)
        if self.search_input.text().strip():
            self.on_search_changed(self.search_input.text())

    # ------------------------------------------------------------------ APPS

    def _build_apps_page(self):
        scroll, lay = self._new_page()

        g = self._card(lay, "Library")
        self.rescan_apps_btn = settings_button("Rescan apps", "secondary", "refresh")
        self.rescan_apps_btn.clicked.connect(self.on_rescan_apps_clicked)
        self.rescan_status_label = self._add_row(
            g, "Installed apps", "Takes a few seconds. Run it after installing something new so it opens instantly.",
            [self.rescan_apps_btn])

        g = self._card(lay, "Installed applications", keywords="apps programs open")
        holder = QWidget()
        self.apps_layout = QVBoxLayout(holder)
        self.apps_layout.setContentsMargins(8, 8, 8, 8)
        self.apps_layout.setSpacing(2)
        g["layout"].addWidget(holder)
        self.populate_apps_list(self.apps_layout)

        self._finish_page(lay)
        return scroll

    def populate_apps_list(self, apps_layout):
        """(Re)build the visible app list. Shared by page creation and the rescan handler."""
        while apps_layout.count():
            item = apps_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        apps = self.get_installed_apps()
        if apps:
            for app_name, icon_path in apps:
                apps_layout.addWidget(AppListItem(app_name, icon_path))
        else:
            no_apps = QLabel("No applications found")
            no_apps.setObjectName("RD")
            no_apps.setContentsMargins(12, 12, 12, 12)
            apps_layout.addWidget(no_apps)

    def on_rescan_apps_clicked(self):
        a = self._assistant()
        if not a:
            self.rescan_status_label.setText("Couldn't reach FreesIA to rescan.")
            return
        self.rescan_apps_btn.setEnabled(False)
        self.rescan_status_label.setText("Rescanning... this takes a few seconds.")
        self._rescan_thread = RescanAppsThread(a)
        self._rescan_thread.finished.connect(self.on_rescan_apps_finished)
        self._threads.append(self._rescan_thread)
        self._rescan_thread.start()

    def on_rescan_apps_finished(self, app_count):
        self.rescan_apps_btn.setEnabled(True)
        self.rescan_status_label.setText(f"Found {app_count} apps. Up to date!")
        self.populate_apps_list(self.apps_layout)

    def get_installed_apps(self):
        """Sourced from assistant.installed_apps, the same data FreesIA uses to resolve "open X" commands."""
        a = self._assistant()
        if not a:
            return []
        apps = [(name.title(), path) for name, path in a.installed_apps.items()]
        apps.sort(key=lambda x: x[0])
        return apps

    # ------------------------------------------------------------------ MODELS

    def _build_models_page(self):
        scroll, lay = self._new_page()
        a = self._assistant()
        self._installed_models = []

        g = self._card(lay, "Ollama", keywords="local ai server status")
        self.models_status_dot = QLabel("Checking...")
        self.models_status_dot.setObjectName("RD")
        refresh = settings_button("Refresh", "secondary", "refresh")
        refresh.clicked.connect(self.refresh_models)
        self.models_refresh_btn = refresh
        self.models_status_desc = self._add_row(g, "Local AI server", "Looking for Ollama on this PC...", [self.models_status_dot, refresh])

        g = self._card(lay, "Model slots", keywords="ollama phi llama choose model")
        self.model_combos = {}
        overrides = load_model_overrides()
        for slot, title, desc in MODEL_SLOTS:
            current = overrides.get(slot) or (getattr(a, slot, "") if a else "")
            if not isinstance(current, str):
                current = ""
            combo = QComboBox()
            combo.setFixedHeight(36)
            combo.setMinimumWidth(240)
            combo.addItem(current or "(none)", current)
            combo.setProperty("slot", slot)
            combo.activated.connect(lambda _i, s=slot, c=combo: self.on_model_chosen(s, c))
            self.model_combos[slot] = combo
            self._add_row(g, title, desc, [combo])

        g = self._card(lay, "Image speed", keywords="taesd tome token merging faster images benchmark")
        def _b(v, d=False):
            return v if isinstance(v, bool) else d
        def _f(v, d=0.4):
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else d
        self.taesd_switch = ToggleSwitch(_b(getattr(a, "use_tiny_autoencoder", False)))
        self.taesd_switch.toggled.connect(lambda on: self._set_speed(tiny_autoencoder=on))
        self._add_row(g, "Fast previews (TAESD)", "A tiny image decoder that finishes each picture sooner. Slightly softer fine detail.", [self.taesd_switch])
        self.tome_switch = ToggleSwitch(_b(getattr(a, "tome_enabled", False)))
        self.tome_switch.toggled.connect(lambda on: self._set_speed(tome_enabled=on))
        self._add_row(g, "Token merging (ToMe), beta", "Skips repeated work inside the model. Faster on CPU, small quality cost.", [self.tome_switch])
        self.tome_slider = QSlider(Qt.Orientation.Horizontal)
        self.tome_slider.setRange(10, 70)
        self.tome_slider.setSingleStep(5)
        self.tome_slider.setPageStep(10)
        self.tome_slider.setFixedWidth(150)
        self.tome_slider.setValue(int(round(_f(getattr(a, "tome_strength", 0.4)) * 100)))
        self.tome_slider.setEnabled(self.tome_switch.isChecked())
        self.tome_value_lbl = QLabel(f"{self.tome_slider.value()}%")
        self.tome_value_lbl.setObjectName("RD")
        self.tome_value_lbl.setMinimumWidth(34)
        self.tome_slider.valueChanged.connect(self._on_tome_strength)
        self._add_row(g, "Merge strength", "Higher is faster but less detailed.", [self.tome_slider, self.tome_value_lbl])
        self.bench_btn = settings_button("Run test", "secondary", "bolt")
        self.bench_btn.clicked.connect(self._run_bench)
        self.use_best_btn = settings_button("Use fastest", "secondary")
        self.use_best_btn.setEnabled(False)
        self.use_best_btn.clicked.connect(self._use_best)
        self._bench_best = None
        self.bench_desc = self._add_row(g, "Speed test",
            "Makes a few small test images with each option and tells you which is fastest. Takes a few minutes.",
            [self.use_best_btn, self.bench_btn])

        foot = QLabel("Need another model? Install it in a terminal with:  ollama pull <model name>  then press Refresh.")
        foot.setObjectName("Foot")
        foot.setWordWrap(True)
        foot.setContentsMargins(4, 12, 0, 0)
        lay.addWidget(foot)

        self._finish_page(lay)
        QTimer.singleShot(0, self.refresh_models)
        return scroll

    def _set_speed(self, **kw):
        a = self._assistant()
        if a:
            a.set_image_speed(**kw)
        if "tome_enabled" in kw:
            self.tome_slider.setEnabled(bool(kw["tome_enabled"]))

    def _on_tome_strength(self, value):
        self.tome_value_lbl.setText(f"{value}%")
        a = self._assistant()
        if a:
            a.set_image_speed(tome_strength=value / 100.0)

    def _run_bench(self):
        a = self._assistant()
        mw = self.parent()
        if not a:
            return
        if getattr(mw, "active_operation", None):
            self.toast("Wait for the current reply to finish first")
            return
        self.bench_btn.setEnabled(False)
        self.use_best_btn.setEnabled(False)
        self.bench_desc.setText("Starting... the first run loads the image model, so this takes a while.")
        t = ImageBenchThread(a)
        t.progress.connect(self.bench_desc.setText)
        t.done.connect(self._on_bench_done)
        self._bench_thread = t
        self._threads.append(t)
        t.start()

    def _on_bench_done(self, results):
        self.bench_btn.setEnabled(True)
        ok = [r for r in results if r.get("seconds")]
        parts = []
        for r in results:
            if r.get("seconds"):
                parts.append(f"{r['label']} {r['seconds']:.1f}s")
            else:
                parts.append(f"{r['label']} unavailable ({r.get('error') or 'failed'})")
        if ok:
            best = min(ok, key=lambda r: r["seconds"])
            self._bench_best = best["label"]
            self.use_best_btn.setEnabled(True)
            self.bench_desc.setText("  ·  ".join(parts) + f".  Fastest: {best['label']}.")
        else:
            self._bench_best = None
            self.bench_desc.setText("  ·  ".join(parts))

    def _use_best(self):
        best = self._bench_best
        if not best:
            return
        self.taesd_switch.setChecked(best in ("TAESD", "TAESD + ToMe"))
        self.tome_switch.setChecked(best == "TAESD + ToMe")
        self.toast(f"Using: {best}")

    def refresh_models(self):
        self.models_refresh_btn.setEnabled(False)
        self.models_status_dot.setText("Checking...")
        t = OllamaModelsThread()
        t.finished.connect(self._on_models_loaded)
        self._models_thread = t
        self._threads.append(t)
        t.start()

    def _on_models_loaded(self, reachable, names):
        self.models_refresh_btn.setEnabled(True)
        self._installed_models = names
        ok = settings_palette()
        if reachable:
            self.models_status_dot.setText(f"● Running · {len(names)} installed")
            self.models_status_dot.setStyleSheet("color: #5FB878; font-size: 12px; font-weight: 600; background: transparent;")
            self.models_status_desc.setText("Ollama is running and answering.")
        else:
            self.models_status_dot.setText("● Not reachable")
            self.models_status_dot.setStyleSheet(f"color: {ok['danger']}; font-size: 12px; font-weight: 600; background: transparent;")
            self.models_status_desc.setText("Start the Ollama app, then press Refresh.")
        for slot, combo in self.model_combos.items():
            current = combo.currentData() or ""
            combo.blockSignals(True)
            combo.clear()
            for n in names:
                combo.addItem(n, n)
            if current and current not in names:
                combo.insertItem(0, f"{current}  (not installed)", current)
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def on_model_chosen(self, slot, combo):
        name = combo.currentData()
        if not name:
            return
        a = self._assistant()
        if a:
            setattr(a, slot, name)
            try:
                if getattr(a, 'ollama_enabled', True) is False:
                    a.initialize_ollama()
            except Exception:
                pass
        data = load_model_overrides()
        data[slot] = name
        save_model_overrides(data)
        self.toast("Model saved")

    # ------------------------------------------------------------------ SECURITY

    def _build_security_page(self):
        scroll, lay = self._new_page()
        a = self.parent().assistant

        g = self._card(lay, "Permissions")
        for title, desc, key, icon in [
            ("File access", "Search, read and manage files", "file_access", "folder"),
            ("System settings", "Adjust volume and brightness, take screenshots", "system_settings", "sliders"),
            ("Power control", "Lock, sleep, shut down or restart", "power_control", "power"),
        ]:
            sw = ToggleSwitch(a.permissions.get(key, False))
            sw.toggled.connect(lambda checked, k=key: self.toggle_permission(k, checked))
            self._add_row(g, title, desc, [sw], icon=icon)

        g = self._card(lay, "Privacy")
        for title, desc, key in [
            ("Save chat history", "Store conversations for future reference", "save_chat_history"),
            ("Keep AI context", "Remember conversation context between sessions", "keep_ai_context"),
        ]:
            sw = ToggleSwitch(a.security_settings.get(key, True))
            sw.toggled.connect(lambda checked, k=key: self.toggle_security_setting(k, checked))
            self._add_row(g, title, desc, [sw])
        clear_ai = settings_button("Clear", "danger")
        clear_ai.clicked.connect(self.clear_ai_memory)
        self._add_row(g, "AI conversation memory", "Forget the running conversation context the AI keeps.", [clear_ai])

        g = self._card(lay, "App lock")
        self.pin_checkbox = ToggleSwitch(a.security_settings.get("pin_enabled", False))
        self.pin_checkbox.toggled.connect(self.toggle_pin_protection)
        self._add_row(g, "PIN protection", "Require a PIN to open FreesIA.", [self.pin_checkbox])
        sw = ToggleSwitch(a.security_settings.get("command_logging", True))
        sw.toggled.connect(lambda checked: self.toggle_security_setting("command_logging", checked))
        self._add_row(g, "Command logging", f"Keep an audit log of every command {AI_NAME} runs.", [sw])
        v = settings_button("View", "secondary")
        v.clicked.connect(self.view_command_log)
        e = settings_button("Export", "secondary")
        e.clicked.connect(self.export_command_log)
        c = settings_button("Clear", "danger")
        c.clicked.connect(self.clear_command_log)
        self._add_row(g, "Command history", f"Every command {AI_NAME} runs is logged here.", [v, e, c])

        g = self._card(lay, "Your data")
        ex = settings_button("Export", "secondary", "download")
        ex.clicked.connect(self.export_all_data)
        self._add_row(g, "Export all personal data", "Chats, memories and settings in one file.", [ex])
        cl = settings_button("Clear", "danger", "trash")
        cl.clicked.connect(self.clear_all_chat_history)
        self._add_row(g, "Clear chat history", "Removes every saved conversation.", [cl])

        g = self._card(lay, "Danger zone", warn=True)
        fr = settings_button("Delete everything", "danger")
        fr.clicked.connect(self.factory_reset)
        self._add_row(g, "Factory reset", "Deletes all data and returns FreesIA to a fresh install.", [fr])

        self._finish_page(lay)
        return scroll

    def toggle_permission(self, permission_type, enabled):
        self.parent().assistant.toggle_permission(permission_type, enabled)

    def toggle_security_setting(self, setting_key, enabled):
        a = self.parent().assistant
        a.security_settings[setting_key] = enabled
        a.save_security_settings()

    def _revert_pin_switch(self, value: bool):
        self.pin_checkbox.blockSignals(True)
        self.pin_checkbox.setChecked(value)
        self.pin_checkbox.blockSignals(False)
        self.pin_checkbox.update()

    def toggle_pin_protection(self, checked):
        a = self.parent().assistant
        if checked:
            pin = themed_prompt(self, "Set a PIN", "Choose a PIN", text="At least 4 characters. You'll need it to open FreesIA.", password=True)
            if not pin:
                self._revert_pin_switch(False)
                return
            if len(pin) < 4:
                themed_message(self, "PIN too short", "A PIN must be at least 4 characters.")
                self._revert_pin_switch(False)
                return
            again = themed_prompt(self, "Confirm PIN", "Enter the PIN again", password=True, ok_text="Confirm")
            if again != pin:
                themed_message(self, "PINs don't match", "Nothing was changed. Try again.")
                self._revert_pin_switch(False)
                return
            a.set_pin(pin)
            self.toast("PIN protection on")
        else:
            a.disable_pin()
            self.toast("PIN protection off")

    def clear_all_chat_history(self):
        if not themed_confirm(self, "Clear all chat history?", "Every saved conversation will be deleted. This can't be undone.",
                              ok_text="Clear history", danger=True):
            return
        mw = self.parent()
        chat_dir = getattr(mw, 'chat_dir', None) or (Path(__file__).parent / "ChatHistory")
        if chat_dir.exists():
            for file in chat_dir.glob("*.json"):
                try:
                    file.unlink()
                except Exception:
                    pass
        # Refresh the sidebar so deleted chats don't linger on screen.
        try:
            mw._chat_index.clear()
            mw.rebuild_chat_list()
            mw._chat_count_cache = 0
            mw._chat_metadata_cache = {}
            mw.new_chat()
        except Exception as e:
            print(f"Couldn't refresh sidebar after clearing history: {e}")
        self.toast("All chat history deleted")

    def clear_ai_memory(self):
        self.parent().assistant.clear_ai_history()
        self.toast("AI conversation memory cleared")

    def view_command_log(self):
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFixedHeight(320)
        log = self.parent().assistant.get_command_log()
        if log:
            out = ""
            for entry in reversed(log):  # most recent first
                out += f"[{entry['timestamp']}]\nCommand: {entry['command']}\nResult: {entry['result']}\n\n"
            text_edit.setPlainText(out)
        else:
            text_edit.setPlainText("No commands logged yet")
        ThemedDialog(self, "Command history", "", ok_text="Close", cancel_text=None, extra_widget=text_edit, width=640).exec()

    def export_command_log(self):
        result = self.parent().assistant.export_command_log()
        themed_message(self, "Export complete", str(result))

    def clear_command_log(self):
        if not themed_confirm(self, "Clear command history?", f"The audit log of commands {AI_NAME} has run will be erased.", ok_text="Clear log", danger=True):
            return
        self.parent().assistant.clear_command_log()
        self.toast("Command history cleared")

    def export_all_data(self):
        result = self.parent().assistant.export_all_data()
        themed_message(self, "Export complete", str(result))

    def factory_reset(self):
        if not themed_confirm(
                self, "Factory reset?",
                "This deletes ALL personal data: permissions, security settings and PIN, the command log and AI conversation history. It can't be undone.",
                ok_text="Delete everything", danger=True, confirm_phrase="DELETE"):
            return
        result = self.parent().assistant.delete_all_data()
        themed_message(self, "Factory reset complete", str(result))


def _month_display(month_key: str) -> str:
    """'2024-02' -> 'February 2024'"""
    try:
        from datetime import datetime
        return datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
    except Exception:
        return month_key


def _reader_state_path() -> Path:
    return Path.home() / ".freesia" / "chat_reader" / "reader_state.json"


def load_reader_state() -> dict:
    try:
        with open(_reader_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_reader_state(state: dict):
    try:
        p = _reader_state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def _fmt_date(ts: str, fmt: str = "%d %b %Y") -> str:
    try:
        return datetime.fromisoformat(str(ts)[:19]).strftime(fmt).lstrip("0")
    except Exception:
        return ""


def _reader_btn_css(primary: bool = False) -> str:
    if primary:
        return (f"QPushButton {{ background-color: {THEME['accent']}; color: {THEME['bg_primary']}; border: none; "
                f"border-radius: 10px; padding: 8px 16px; font-size: 13px; font-weight: 600; }}"
                f"QPushButton:hover {{ background-color: {THEME['text_primary']}; }}")
    return (f"QPushButton {{ background-color: {THEME['bg_tertiary']}; color: {THEME['text_primary']}; "
            f"border: 1px solid {THEME['border_strong']}; border-radius: 10px; padding: 8px 14px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {THEME['hover_strong']}; }}"
            f"QPushButton:disabled {{ color: {THEME['text_muted']}; }}")


class ReaderSearchThread(QThread):
    """Searches a whole archive off the UI thread."""
    done = pyqtSignal(int, list)

    def __init__(self, assistant, archive, query, token):
        super().__init__()
        self.assistant, self.archive, self.query, self.token = assistant, archive, query, token

    def run(self):
        try:
            res = self.assistant.search_chat_reader(self.archive, self.query)
        except Exception:
            res = []
        self.done.emit(self.token, res if isinstance(res, list) else [])


class ArchiveCard(QFrame):
    """One imported chat on the library screen."""
    open_requested = pyqtSignal(str, bool)   # archive_name, resume
    rename_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, info: dict, months: int, last_text: str, pct: int):
        super().__init__()
        name = info["archive_name"]
        self.setObjectName("ArchiveCard")
        self.setStyleSheet(f"QFrame#ArchiveCard {{ background-color: {THEME['bg_tertiary']}; border: 1px solid {THEME['border']}; border-radius: 18px; }}"
                           f"QFrame#ArchiveCard QLabel {{ background: transparent; border: none; }}")
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 22, 22, 20)
        v.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(avatar_label(44, (info.get("display_name") or "?")[:1].upper()))
        col = QVBoxLayout()
        col.setSpacing(0)
        title = QLabel(info.get("display_name") or name)
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {THEME['text_primary']};")
        title.setWordWrap(True)
        col.addWidget(title)
        a, b = _fmt_date(info.get("date_range", ["", ""])[0], "%b %Y"), _fmt_date(info.get("date_range", ["", ""])[-1], "%b %Y")
        rng = QLabel(f"{a} – {b}" if a and b else "")
        rng.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']};")
        col.addWidget(rng)
        top.addLayout(col, 1)
        more = QPushButton()
        more.setIcon(line_icon("dots", THEME['text_muted'], 18))
        more.setFlat(True)
        more.setFixedSize(30, 30)
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setStyleSheet("QPushButton { border: none; background: transparent; }")
        more.clicked.connect(lambda: self._menu(more, name))
        top.addWidget(more, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(top)

        stats = QHBoxLayout()
        stats.setSpacing(24)
        for big, small in ((f"{int(info.get('message_count', 0)):,}", "messages"), (str(months), "months")):
            c = QVBoxLayout()
            c.setSpacing(0)
            x = QLabel(big)
            x.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {THEME['text_primary']};")
            y = QLabel(small)
            y.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']};")
            c.addWidget(x)
            c.addWidget(y)
            stats.addLayout(c)
        stats.addStretch()
        v.addLayout(stats)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(f"QProgressBar {{ background: {THEME['border_strong']}; border: none; border-radius: 2px; }}"
                          f"QProgressBar::chunk {{ background: {THEME['accent']}; border-radius: 2px; }}")
        v.addWidget(bar)
        self.last_label = QLabel(last_text)
        self.last_label.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']};")
        v.addWidget(self.last_label)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.resume_btn = None
        if last_text.startswith("Last read"):
            self.resume_btn = QPushButton("Continue reading")
            self.resume_btn.setStyleSheet(_reader_btn_css(True))
            self.resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.resume_btn.clicked.connect(lambda: self.open_requested.emit(name, True))
            btns.addWidget(self.resume_btn, 1)
            start = QPushButton("From start")
            start.setStyleSheet(_reader_btn_css())
            start.setCursor(Qt.CursorShape.PointingHandCursor)
            start.clicked.connect(lambda: self.open_requested.emit(name, False))
            btns.addWidget(start)
        else:
            self.open_btn = QPushButton("Open")
            self.open_btn.setStyleSheet(_reader_btn_css(True))
            self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.open_btn.clicked.connect(lambda: self.open_requested.emit(name, False))
            btns.addWidget(self.open_btn, 1)
        v.addLayout(btns)

    def _menu(self, anchor, name):
        m = QMenu(self)
        m.addAction("Rename", lambda: self.rename_requested.emit(name))
        m.addAction("Remove", lambda: self.remove_requested.emit(name))
        m.exec(anchor.mapToGlobal(QPoint(0, anchor.height())))


class ChatReaderView(QWidget):
    """
    Browse imported chat archives (currently: Character.AI exports) in
    FreesIA's own bubble UI.

    Two screens: a library of imported chats (nothing is opened until you pick
    one), and the reading view. Reading keeps your place per archive so
    "Continue reading" returns to the exact message. Only a few months are
    ever kept as real widgets: the next/previous month loads as you scroll
    and far-off months are unloaded, so a 60k+ message chat stays light.
    """

    CHUNK = 60            # messages per rendered block: a block of real widgets costs ~4 ms/message
    MAX_LOADED_UNITS = 8  # blocks kept as widgets at once (about 480 messages)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_archive = None
        self.current_manifest = None
        self.loaded_units = []        # [(month_key, chunk_no)] currently rendered, in reading order
        self._loading_next = False
        self._loading_prev = False
        self._insert_pos = None  # None = append; an int = insert at the top (loading an earlier block)
        self._unit_marker = {}        # unit -> 1px marker widget at the start of the block
        self._unit_widgets = {}       # unit -> [message container widgets, in message order]
        self._unit_all = {}           # unit -> every widget of that block (marker, day chips, messages)
        self._month_cache = {}        # month_key -> parsed message list (few kept)
        self._month_cache_order = []
        self._search_results = []
        self._search_token = 0
        self._search_threads = []
        self._jump_origin = None
        self._state = load_reader_state()
        self.setAcceptDrops(True)  # drop an export folder anywhere on this view to import it

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.stack.addWidget(self._build_library())
        self.stack.addWidget(self._build_reading())

        self._pos_timer = QTimer(self)
        self._pos_timer.setSingleShot(True)
        self._pos_timer.setInterval(700)
        self._pos_timer.timeout.connect(self._save_position)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)
        self._tl_timer = QTimer(self)
        self._tl_timer.setSingleShot(True)
        self._tl_timer.setInterval(350)
        self._tl_timer.timeout.connect(self._timeline_jump)
        self._back_timer = QTimer(self)
        self._back_timer.setSingleShot(True)
        self._back_timer.setInterval(30000)
        self._back_timer.timeout.connect(lambda: self.jump_back_btn.hide())

    # ================================================================ library screen

    def _build_library(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(48, 30, 48, 20)
        v.setSpacing(18)
        top = QHBoxLayout()
        back = QPushButton("← Back to chat")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet(_reader_btn_css())
        back.clicked.connect(lambda: self.main_window.content_stack.setCurrentIndex(0))
        top.addWidget(back)
        top.addStretch()
        v.addLayout(top)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel("Chat Reader")
        t.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {THEME['text_primary']};")
        s = QLabel("Old chats you imported. Read them like a chat, jump to any date, search every message.")
        s.setStyleSheet(f"font-size: 13.5px; color: {THEME['text_muted']};")
        col.addWidget(t)
        col.addWidget(s)
        head.addLayout(col, 1)
        self.import_btn = QPushButton("Import chat")
        self.import_btn.setIcon(line_icon("upload", THEME['text_primary'], 16))
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setStyleSheet(_reader_btn_css())
        self.import_btn.clicked.connect(self.import_chat)
        head.addWidget(self.import_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(head)

        self.lib_scroll = QScrollArea()
        self.lib_scroll.setWidgetResizable(True)
        self.lib_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.lib_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }" + themed_scrollbar_css())
        self.lib_body = QWidget()
        self.lib_body.setStyleSheet("background: transparent;")
        self.lib_layout = QVBoxLayout(self.lib_body)
        self.lib_layout.setContentsMargins(0, 4, 0, 10)
        self.lib_layout.setSpacing(20)
        self.lib_scroll.setWidget(self.lib_body)
        v.addWidget(self.lib_scroll, 1)
        return page

    def show_library(self):
        """Back to the list of imported chats. Never opens a chat by itself."""
        if self.current_archive and self.stack.currentIndex() == 1:
            self._save_position()
        self.stack.setCurrentIndex(0)
        self._rebuild_library()

    def refresh_archive_list(self):
        self.show_library()

    def _clear_layout(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _rebuild_library(self):
        self._clear_layout(self.lib_layout)
        assistant = self.main_window.assistant
        archives = []
        try:
            archives = assistant.list_chat_reader_archives() if assistant else []
        except Exception:
            archives = []
        if not isinstance(archives, list):
            archives = []
        self._state = load_reader_state()
        grid = QGridLayout()
        grid.setSpacing(20)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        cells = 0
        for info in archives:
            name = info.get("archive_name")
            if not name:
                continue
            manifest = assistant.get_chat_reader_manifest(name) or {}
            months = manifest.get("months") or []
            saved = self._state.get(name) or {}
            if saved.get("month") in months:
                pct = int(round((months.index(saved["month"]) + 1) * 100 / max(1, len(months))))
                last = f"Last read: {_month_display(saved['month'])}  ·  {pct}%"
            else:
                pct, last = 0, "Not started yet"
            card = ArchiveCard(info, len(months), last, pct)
            card.open_requested.connect(lambda n, resume: self.open_archive(n, resume=resume))
            card.rename_requested.connect(self._rename_archive)
            card.remove_requested.connect(self._remove_archive)
            grid.addWidget(card, cells // 3, cells % 3, Qt.AlignmentFlag.AlignTop)
            cells += 1
        drop = QFrame()
        drop.setObjectName("ReaderDrop")
        drop.setMinimumHeight(190)
        drop.setCursor(Qt.CursorShape.PointingHandCursor)
        drop.setStyleSheet(f"QFrame#ReaderDrop {{ border: 2px dashed {THEME['border_strong']}; border-radius: 18px; background: transparent; }}"
                           f"QFrame#ReaderDrop QLabel {{ background: transparent; border: none; }}")
        dl = QVBoxLayout(drop)
        dl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic = QLabel()
        ic.setPixmap(line_pixmap("upload", THEME['accent'], 30))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d1 = QLabel("Drop an export folder here")
        d1.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {THEME['text_primary']};")
        d1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d2 = QLabel("or click to choose one. You can drop several at once.\nFreesIA finds message.json itself.")
        d2.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']};")
        d2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (ic, d1, d2):
            dl.addWidget(w)
        drop.mousePressEvent = lambda e: self.import_chat()
        grid.addWidget(drop, cells // 3, cells % 3, Qt.AlignmentFlag.AlignTop)
        self.lib_layout.addLayout(grid)

        pins = self._reader_pins()
        if pins:
            cap = QLabel("BOOKMARKS ACROSS ALL CHATS")
            cap.setStyleSheet(f"font-size: 12px; font-weight: 600; letter-spacing: 1px; color: {THEME['text_muted']};")
            self.lib_layout.addWidget(cap)
            box = QFrame()
            box.setObjectName("BmBox")
            box.setStyleSheet(f"QFrame#BmBox {{ background-color: {THEME['bg_tertiary']}; border: 1px solid {THEME['border']}; border-radius: 18px; }}"
                              f"QFrame#BmBox QLabel {{ background: transparent; border: none; }}")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(1, 6, 1, 6)
            bl.setSpacing(0)
            names = {a.get("archive_name"): a.get("display_name") for a in archives}
            for pin in pins[:6]:
                bl.addWidget(self._bookmark_row(pin, names))
            self.lib_layout.addWidget(box)
        self.lib_layout.addStretch(1)

    def _reader_pins(self, archive=None):
        assistant = self.main_window.assistant
        pins = getattr(assistant, "pinned_messages", None)
        if not isinstance(pins, list):
            return []
        out = []
        for p in pins:
            src = p.get("source", "") if isinstance(p, dict) else ""
            if src.startswith("chat_reader:") and (archive is None or src == f"chat_reader:{archive}"):
                out.append(p)
        out.sort(key=lambda p: p.get("pinned_at", ""), reverse=True)
        return out

    def _pin_when(self, pin) -> str:
        month = pin.get("chat_id", "")
        ts = pin.get("timestamp", "")
        if ts[:7] == month and month:
            return _fmt_date(ts)
        return _month_display(month) if month else ""

    def _bookmark_row(self, pin, names):
        src = pin.get("source", "")[len("chat_reader:"):]
        row = QPushButton()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(f"QPushButton {{ background: transparent; border: none; text-align: left; padding: 0; }}"
                          f"QPushButton:hover {{ background-color: {THEME['hover']}; }}")
        row.setMinimumHeight(62)
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 10, 20, 10)
        h.setSpacing(12)
        star = QLabel()
        star.setPixmap(line_pixmap("star", THEME['accent'], 16))
        star.setStyleSheet("background: transparent;")
        h.addWidget(star)
        col = QVBoxLayout()
        col.setSpacing(0)
        snippet = re.sub(r"\s+", " ", pin.get("content", "")).strip()
        a = QLabel("“" + (snippet[:110] + ("…" if len(snippet) > 110 else "")) + "”")
        a.setStyleSheet(f"font-size: 14px; color: {THEME['text_primary']}; background: transparent;")
        b = QLabel(f"{names.get(src) or src}  ·  {self._pin_when(pin)}")
        b.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']}; background: transparent;")
        for w in (a, b):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            col.addWidget(w)
        h.addLayout(col, 1)
        star.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.clicked.connect(lambda _=False, p=pin: self.open_at_pin(src, p))
        return row

    def _rename_archive(self, name):
        a = self.main_window.assistant
        info = next((x for x in a.list_chat_reader_archives() if x.get("archive_name") == name), {})
        new, ok = themed_prompt(self, "Rename chat", "Name", initial=info.get("display_name", ""), ok_text="Rename")
        if ok and new.strip():
            a.rename_chat_reader_archive(name, new.strip())
            self._rebuild_library()

    def _remove_archive(self, name):
        a = self.main_window.assistant
        if themed_confirm(self, "Remove this chat?",
                          "The imported copy and its bookmarks are deleted from FreesIA. Your original export is not touched.",
                          ok_text="Remove", danger=True):
            a.delete_chat_reader_archive(name)
            self._state.pop(name, None)
            save_reader_state(self._state)
            self._rebuild_library()

    # ================================================================ reading screen

    def _build_reading(self):
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("ReadBar")
        bar.setStyleSheet(f"QFrame#ReadBar {{ border-bottom: 1px solid {THEME['border']}; }}")
        top = QHBoxLayout(bar)
        top.setContentsMargins(28, 14, 28, 14)
        top.setSpacing(10)
        back = QPushButton("← Library")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet(_reader_btn_css())
        back.clicked.connect(self.show_library)
        top.addWidget(back)
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        self.title_label = QLabel("")
        self.title_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {THEME['text_primary']};")
        self.sub_label = QLabel("")
        self.sub_label.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']};")
        tcol.addWidget(self.title_label)
        tcol.addWidget(self.sub_label)
        top.addLayout(tcol)
        top.addSpacing(8)
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(150)
        self.month_combo.setStyleSheet(f"QComboBox {{ background-color: {THEME['bg_tertiary']}; color: {THEME['text_primary']}; "
                                       f"border: 1px solid {THEME['border_strong']}; border-radius: 10px; padding: 7px 12px; font-weight: 600; }}")
        self.month_combo.currentIndexChanged.connect(self._on_month_jump)
        top.addWidget(self.month_combo)
        self.first_btn = QPushButton("First")
        self.latest_btn = QPushButton("Latest")
        for b, fn in ((self.first_btn, self._go_first), (self.latest_btn, self._go_latest)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_reader_btn_css())
            b.clicked.connect(fn)
            top.addWidget(b)
        top.addStretch()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search this chat...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(300)
        self.search_box.setStyleSheet(f"QLineEdit {{ background-color: {THEME['bg_secondary']}; color: {THEME['text_primary']}; "
                                      f"border: 1px solid {THEME['border_strong']}; border-radius: 10px; padding: 8px 12px; }}"
                                      f"QLineEdit:focus {{ border: 1px solid {THEME['accent']}; }}")
        self.search_box.textChanged.connect(lambda _t: self._search_timer.start())
        self.search_box.returnPressed.connect(self._search_enter)
        self.search_box.installEventFilter(self)
        top.addWidget(self.search_box)
        root.addWidget(bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }" + themed_scrollbar_css())
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(40, 16, 40, 16)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(14)
        self.scroll.setWidget(self.messages_widget)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.scroll.viewport().installEventFilter(self)  # wheel-up at the very top loads the previous month
        self.scroll.installEventFilter(self)
        body.addWidget(self.scroll, 1)

        rail = QFrame()
        rail.setObjectName("ReadRail")
        rail.setFixedWidth(280)
        rail.setStyleSheet(f"QFrame#ReadRail {{ border-left: 1px solid {THEME['border']}; }}")
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(22, 20, 22, 20)
        rl.setSpacing(10)
        cap = QLabel("TIMELINE")
        cap.setStyleSheet(f"font-size: 12px; font-weight: 600; letter-spacing: 1px; color: {THEME['text_muted']};")
        rl.addWidget(cap)
        tl = QHBoxLayout()
        tl.setSpacing(12)
        self.timeline = QSlider(Qt.Orientation.Vertical)
        self.timeline.setFixedHeight(190)
        self.timeline.setInvertedAppearance(True)  # oldest at the top
        self.timeline.setStyleSheet(
            f"QSlider::groove:vertical {{ width: 4px; background: {THEME['border_strong']}; border-radius: 2px; }}"
            f"QSlider::sub-page:vertical {{ background: {THEME['border_strong']}; border-radius: 2px; }}"
            f"QSlider::add-page:vertical {{ background: {THEME['border_strong']}; border-radius: 2px; }}"
            f"QSlider::handle:vertical {{ background: {THEME['text_primary']}; border: 3px solid {THEME['accent']}; "
            f"height: 10px; width: 10px; margin: 0 -8px; border-radius: 8px; }}")
        self.timeline.valueChanged.connect(self._timeline_changed)
        tl.addWidget(self.timeline)
        tlab = QVBoxLayout()
        self.tl_first = QLabel("")
        self.tl_now = QLabel("")
        self.tl_last = QLabel("")
        for w, bold in ((self.tl_first, False), (self.tl_now, True), (self.tl_last, False)):
            w.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_primary'] if bold else THEME['text_muted']}; font-weight: {'700' if bold else '400'};")
        tlab.addWidget(self.tl_first)
        tlab.addStretch()
        tlab.addWidget(self.tl_now)
        tlab.addStretch()
        tlab.addWidget(self.tl_last)
        tl.addLayout(tlab, 1)
        rl.addLayout(tl)
        cap2 = QLabel("BOOKMARKS IN THIS CHAT")
        cap2.setStyleSheet(f"font-size: 12px; font-weight: 600; letter-spacing: 1px; color: {THEME['text_muted']}; margin-top: 10px;")
        rl.addWidget(cap2)
        self.bookmark_list = QListWidget()
        self.bookmark_list.setFrameShape(QFrame.Shape.NoFrame)
        self.bookmark_list.setWordWrap(True)
        self.bookmark_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; outline: none; }}"
            f"QListWidget::item {{ background-color: {THEME['bg_tertiary']}; border: 1px solid {THEME['border']}; border-radius: 12px; "
            f"padding: 9px 11px; margin-bottom: 8px; color: {THEME['text_primary']}; }}"
            f"QListWidget::item:hover {{ background-color: {THEME['hover_strong']}; }}")
        self.bookmark_list.itemClicked.connect(self._on_bookmark_clicked)
        rl.addWidget(self.bookmark_list, 1)
        self.bookmark_hint = QLabel("Pin a message (the pin on its bubble) to bookmark it here.")
        self.bookmark_hint.setWordWrap(True)
        self.bookmark_hint.setStyleSheet(f"font-size: 12.5px; color: {THEME['text_muted']};")
        rl.addWidget(self.bookmark_hint)
        body.addWidget(rail)
        root.addLayout(body, 1)

        # floating widgets
        self.jump_back_btn = QPushButton("", self.scroll)
        self.jump_back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.jump_back_btn.setStyleSheet(_reader_btn_css())
        self.jump_back_btn.clicked.connect(self._jump_back)
        self.jump_back_btn.hide()

        self.search_results_list = QListWidget(page)
        self.search_results_list.setFrameShape(QFrame.Shape.NoFrame)
        self.search_results_list.setStyleSheet(
            f"QListWidget {{ background-color: {THEME['bg_tertiary']}; border: 1px solid {THEME['border_strong']}; border-radius: 14px; outline: none; }}"
            f"QListWidget::item {{ border-bottom: 1px solid {THEME['border']}; padding: 0; }}"
            f"QListWidget::item:selected {{ background-color: {THEME['hover_strong']}; }}")
        self.search_results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.search_results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.search_results_list.itemClicked.connect(self._on_search_result_clicked)
        self.search_results_list.hide()
        self._reading_page = page
        return page

    # ---- events / floating layout

    def eventFilter(self, obj, event):
        t = event.type()
        if not isinstance(self.scroll, QScrollArea):
            return False  # still being built (QWidget.scroll is a method until we assign ours)
        if obj is self.scroll.viewport() and t == QEvent.Type.Wheel:
            bar = self.scroll.verticalScrollBar()
            if event.angleDelta().y() > 0 and bar.value() <= 0:
                QTimer.singleShot(0, self._load_prev_month_if_available)
        elif obj is self.scroll and t == QEvent.Type.Resize:
            self._place_jump_back()
        elif obj is self.search_box and t == QEvent.Type.KeyPress:
            key = event.key()
            lst = self.search_results_list
            if key == Qt.Key.Key_Escape:
                lst.hide()
                return True
            if lst.isVisible() and key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                rows = [i for i in range(lst.count()) if lst.item(i).data(Qt.ItemDataRole.UserRole)]
                if rows:
                    cur = lst.currentRow()
                    pos = rows.index(cur) if cur in rows else -1
                    pos = (pos + (1 if key == Qt.Key.Key_Down else -1)) % len(rows)
                    lst.setCurrentRow(rows[pos])
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_search_list()
        self._place_jump_back()

    def _place_search_list(self):
        lst = self.search_results_list
        pt = self.search_box.mapTo(self._reading_page, QPoint(0, self.search_box.height() + 6))
        w = 440
        h = 60
        if lst.count():
            h = sum(lst.sizeHintForRow(i) for i in range(min(lst.count(), 6))) + 6
            if lst.count() > 6:
                h += lst.sizeHintForRow(lst.count() - 1)
        lst.setGeometry(max(8, pt.x() + self.search_box.width() - w), pt.y(), w, min(480, max(60, h)))
        lst.raise_()

    def _place_jump_back(self):
        b = self.jump_back_btn
        b.adjustSize()
        b.move(max(8, (self.scroll.width() - b.width()) // 2), self.scroll.height() - b.height() - 18)
        b.raise_()

    # ================================================================ opening an archive

    def open_archive(self, archive_name, resume=False, target=None, highlight=False):
        assistant = self.main_window.assistant
        manifest = assistant.get_chat_reader_manifest(archive_name) if assistant else None
        months = (manifest or {}).get("months") or []
        if not manifest or not months:
            themed_message(self, "Can't open this chat", "Its files are missing or empty. Try importing it again.")
            return
        self.current_archive = archive_name
        self.current_manifest = manifest
        self._month_cache.clear()
        self._month_cache_order.clear()
        self._state = load_reader_state()
        self.search_results_list.hide()
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self._search_results = []
        self.jump_back_btn.hide()
        self._jump_origin = None

        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        for mk in months:
            self.month_combo.addItem(_month_display(mk), mk)
        self.month_combo.blockSignals(False)
        self.timeline.blockSignals(True)
        self.timeline.setRange(0, len(months) - 1)
        self.timeline.setValue(0)
        self.timeline.blockSignals(False)
        self.tl_first.setText(_month_display(months[0]))
        self.tl_last.setText(_month_display(months[-1]))
        self.title_label.setText(manifest.get("display_name") or archive_name)

        saved = self._state.get(archive_name) or {}
        sub = "From the start"
        if target:
            month, idx = target
        elif resume and saved.get("month") in months:
            month, idx = saved["month"], int(saved.get("index", 0) or 0)
        else:
            month, idx = months[0], 0
        self.stack.setCurrentIndex(1)
        self._clear_messages()
        idx = self._ensure_loaded(month, idx)
        self._scroll_to(month, idx, highlight=highlight)
        msgs = self._get_msgs(month)
        if target:
            sub = "Jumped to a bookmark"
        elif resume and saved.get("month") == month:
            when = _fmt_date(msgs[min(idx, len(msgs) - 1)].get("timestamp", "")) if msgs else ""
            sub = f"Resumed at {when}" if when else f"Resumed at {_month_display(month)}"
        self.sub_label.setText(sub)
        self._sync_position_widgets(month)
        self._refresh_bookmarks()

    def open_at_pin(self, archive_name, pin):
        """Open an archive on a bookmarked message (used by the library and the Pinned panel)."""
        assistant = self.main_window.assistant
        manifest = assistant.get_chat_reader_manifest(archive_name) if assistant else None
        months = (manifest or {}).get("months") or []
        month = pin.get("chat_id", "")
        if month not in months:
            self.open_archive(archive_name, resume=True)
            return
        idx = 0
        for i, m in enumerate(assistant.load_chat_reader_month(archive_name, month)):
            if m.get("content") == pin.get("content") and m.get("speaker") == pin.get("speaker"):
                idx = i
                break
        self.open_archive(archive_name, target=(month, idx), highlight=True)

    # ================================================================ rendering

    def _clear_messages(self):
        while self.messages_layout.count():
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.loaded_units = []
        self._unit_marker = {}
        self._unit_widgets = {}
        self._unit_all = {}

    @property
    def loaded_months(self):
        out = []
        for m, _c in self.loaded_units:
            if m not in out:
                out.append(m)
        return out

    def _get_msgs(self, month_key):
        """Parsed messages of a month (cached; a month file is cheap to read, its widgets are what's costly)."""
        if month_key in self._month_cache:
            return self._month_cache[month_key]
        msgs = self.main_window.assistant.load_chat_reader_month(self.current_archive, month_key) or []
        self._month_cache[month_key] = msgs
        self._month_cache_order.append(month_key)
        while len(self._month_cache_order) > 4:
            self._month_cache.pop(self._month_cache_order.pop(0), None)
        return msgs

    def _nchunks(self, month_key):
        return max(1, -(-len(self._get_msgs(month_key)) // self.CHUNK))

    def _next_unit(self, unit):
        m, c = unit
        if c + 1 < self._nchunks(m):
            return (m, c + 1)
        months = self.current_manifest["months"]
        i = months.index(m)
        return (months[i + 1], 0) if i + 1 < len(months) else None

    def _prev_unit(self, unit):
        m, c = unit
        if c > 0:
            return (m, c - 1)
        months = self.current_manifest["months"]
        i = months.index(m)
        if i == 0:
            return None
        pm = months[i - 1]
        return (pm, self._nchunks(pm) - 1)

    def _place(self, widget, unit=None):
        if self._insert_pos is None:
            self.messages_layout.addWidget(widget)
        else:
            self.messages_layout.insertWidget(self._insert_pos, widget)
            self._insert_pos += 1
        if unit is not None:
            self._unit_all.setdefault(unit, []).append(widget)

    def _render_unit(self, unit, prepend: bool = False):
        month_key, chunk = unit
        all_msgs = self._get_msgs(month_key)
        i0 = chunk * self.CHUNK
        msgs = all_msgs[i0:i0 + self.CHUNK]
        self._unit_widgets[unit] = []
        self._unit_all[unit] = []
        self._insert_pos = 0 if prepend else None

        marker = QLabel(month_key)
        marker.setFixedHeight(1)
        marker.setStyleSheet("QLabel { color: transparent; background: transparent; }")
        self._place(marker, unit)
        self._unit_marker[unit] = marker

        pin_source = f"chat_reader:{self.current_archive}"
        pinned = {}
        for p in self._reader_pins(self.current_archive):
            pinned[(p.get("chat_id"), p.get("speaker"), p.get("content"))] = p.get("id")

        last_day = str(all_msgs[i0 - 1].get("timestamp", ""))[:10] if i0 > 0 else None
        for j, m in enumerate(msgs):
            i = i0 + j
            day = str(m.get("timestamp", ""))[:10]
            if day and day != last_day:
                last_day = day
                chip = QLabel(_fmt_date(day, "%A, %d %B %Y").replace(" 0", " "))
                chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chip.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; background-color: {THEME['bg_tertiary']}; "
                                   f"border: 1px solid {THEME['border']}; border-radius: 11px; padding: 3px 14px; font-size: 12px; }}")
                chip_row = QHBoxLayout()
                chip_row.addStretch()
                chip_row.addWidget(chip)
                chip_row.addStretch()
                chip_w = QWidget()
                chip_w.setLayout(chip_row)
                self._place(chip_w, unit)

            is_user = (m['speaker'] == 'You')
            bubble = MessageBubble(m['content'], is_user=is_user, show_regen_controls=False)
            bubble.on_pin = lambda b, mk=month_key, idx=i, content=m['content'], speaker=m['speaker'], ts=m.get('timestamp', ''): \
                self._handle_reader_pin(b, mk, idx, content, speaker, pin_source, ts)
            bubble.on_reassign_speaker = lambda b, mk=month_key, idx=i: self._handle_reassign(b, mk, idx)
            pin_id = pinned.get((month_key, m['speaker'], m['content']))
            if pin_id:
                bubble.set_pinned(pin_id)

            column = QVBoxLayout()
            column.setSpacing(2)
            if not is_user:
                name_label = QLabel(m['speaker'])
                name_label.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 11px; background: transparent; }}")
                column.addWidget(name_label)
            bubble_row = QHBoxLayout()
            if is_user:
                bubble_row.addStretch()
                bubble_row.addWidget(bubble)
            else:
                bubble_row.addWidget(bubble)
                bubble_row.addStretch()
            column.addLayout(bubble_row)

            container = QWidget()
            container.setObjectName("rdmsg")
            container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            container.setLayout(column)
            self._place(container, unit)
            self._unit_widgets[unit].append(container)

        if prepend:
            self.loaded_units.insert(0, unit)
        else:
            self.loaded_units.append(unit)
        self._insert_pos = None
        QApplication.processEvents()  # lets Qt size the new bubbles before callers measure positions

    def _unload_unit(self, unit):
        for w in self._unit_all.pop(unit, []):
            self.messages_layout.removeWidget(w)
            w.hide()
            w.deleteLater()
        self._unit_widgets.pop(unit, None)
        self._unit_marker.pop(unit, None)
        if unit in self.loaded_units:
            self.loaded_units.remove(unit)

    def _trim_loaded(self, keep_end: bool):
        """Drop the blocks farthest from where you're reading so only a few stay as widgets."""
        bar = self.scroll.verticalScrollBar()
        while len(self.loaded_units) > self.MAX_LOADED_UNITS:
            if keep_end:
                first, second = self.loaded_units[0], self.loaded_units[1]
                m1, m2 = self._unit_marker.get(first), self._unit_marker.get(second)
                height = (m2.y() - m1.y()) if (m1 and m2) else 0
                value = bar.value()
                self._unload_unit(first)
                QApplication.processEvents()
                bar.setValue(max(0, value - height))
            else:
                self._unload_unit(self.loaded_units[-1])
                QApplication.processEvents()

    def _load_prev_month_if_available(self):
        if self._loading_prev or self._loading_next or not self.current_manifest or not self.loaded_units:
            return
        prev = self._prev_unit(self.loaded_units[0])
        if prev is None:
            return
        self._loading_prev = True
        try:
            bar = self.scroll.verticalScrollBar()
            old_max, old_value = bar.maximum(), bar.value()
            self._render_unit(prev, prepend=True)
            bar.setValue(old_value + (bar.maximum() - old_max))  # keep the same message under the cursor
            self._trim_loaded(keep_end=False)
        finally:
            self._loading_prev = False

    def _load_next_month_if_available(self):
        if self._loading_next or self._loading_prev or not self.current_manifest or not self.loaded_units:
            return
        nxt = self._next_unit(self.loaded_units[-1])
        if nxt is None:
            return
        self._loading_next = True
        try:
            self._render_unit(nxt)
            self._trim_loaded(keep_end=True)
        finally:
            self._loading_next = False

    # ================================================================ position / scrolling

    def _current_position(self):
        """(month, message index) of the first message at the top of the view, or None."""
        if not self.loaded_units:
            return None
        top = self.scroll.verticalScrollBar().value()
        unit = self.loaded_units[0]
        for u in self.loaded_units:
            marker = self._unit_marker.get(u)
            if marker is not None and marker.y() <= top + 40:
                unit = u
        widgets = self._unit_widgets.get(unit) or []
        lo, hi = 0, len(widgets)
        while lo < hi:
            mid = (lo + hi) // 2
            w = widgets[mid]
            if w.y() + w.height() <= top:
                lo = mid + 1
            else:
                hi = mid
        return unit[0], unit[1] * self.CHUNK + min(lo, max(0, len(widgets) - 1))

    def _save_position(self):
        if not self.current_archive:
            return
        pos = self._current_position()
        if not pos:
            return
        self._state[self.current_archive] = {"month": pos[0], "index": pos[1], "ts": datetime.now().isoformat()}
        save_reader_state(self._state)

    def _ensure_loaded(self, month, idx):
        """Make sure the block holding message `idx` of `month` is rendered (rendering only that block if not)."""
        msgs = self._get_msgs(month)
        idx = max(0, min(idx, len(msgs) - 1)) if msgs else 0
        unit = (month, idx // self.CHUNK)
        if unit not in self.loaded_units:
            self._clear_messages()
            self._render_unit(unit)
        return idx

    def _scroll_to(self, month, idx, highlight=False):
        idx = max(0, idx)
        unit = (month, idx // self.CHUNK)
        widgets = self._unit_widgets.get(unit) or []
        if not widgets:
            return
        local = max(0, min(idx - unit[1] * self.CHUNK, len(widgets) - 1))
        w = widgets[local]
        bar = self.scroll.verticalScrollBar()
        at_top = (local == 0)

        def go():
            try:
                bar.setValue(max(0, w.y() - (0 if at_top else self.scroll.viewport().height() // 3)))
            except RuntimeError:
                pass
        go()
        for ms in (0, 150, 450):  # bubbles finish sizing a moment after they're added
            QTimer.singleShot(ms, go)
        if highlight:
            QTimer.singleShot(160, lambda: self._flash(w))

    def _flash(self, w):
        try:
            w.setStyleSheet(f"QWidget#rdmsg {{ border: 2px solid {THEME['accent']}; border-radius: 16px; }}")
            QTimer.singleShot(3500, lambda: self._unflash(w))
        except RuntimeError:
            pass

    @staticmethod
    def _unflash(w):
        try:
            w.setStyleSheet("")
        except RuntimeError:
            pass

    def _jump_to(self, month, idx, highlight=False, track=True):
        if not self.current_archive or not self.current_manifest or month not in self.current_manifest["months"]:
            return
        origin = self._current_position() if track else None
        idx = self._ensure_loaded(month, idx)
        self._scroll_to(month, idx, highlight=highlight)
        if origin and (origin[0] != month or abs(origin[1] - idx) > 30):
            self._jump_origin = origin
            when = _month_display(origin[0])
            msgs = self._get_msgs(origin[0])
            if msgs:
                when = _fmt_date(msgs[min(origin[1], len(msgs) - 1)].get("timestamp", "")) or when
            self.jump_back_btn.setText(f"Jump back to where I was ({when})")
            self.jump_back_btn.show()
            self._place_jump_back()
            self._back_timer.start()
        QTimer.singleShot(200, lambda: self._sync_position_widgets())
        self._pos_timer.start()

    def _jump_back(self):
        if self._jump_origin:
            m, i = self._jump_origin
            self._jump_origin = None
            self.jump_back_btn.hide()
            self._jump_to(m, i, track=False)

    def _go_first(self):
        if self.current_manifest:
            self._jump_to(self.current_manifest["months"][0], 0)

    def _go_latest(self):
        if self.current_manifest:
            self._jump_to(self.current_manifest["months"][-1], 10 ** 9)

    def _on_month_jump(self, index):
        if index < 0 or not self.current_archive:
            return
        month_key = self.month_combo.itemData(index)
        if month_key:
            self._jump_to(month_key, 0)

    def _on_scroll(self, value):
        bar = self.scroll.verticalScrollBar()
        load_margin = max(1500, bar.pageStep() * 3)
        if bar.maximum() > 0 and value >= bar.maximum() - load_margin:
            self._load_next_month_if_available()
        elif value <= min(load_margin, 600) and not self._loading_prev:
            self._load_prev_month_if_available()
        self._update_sticky_header()
        self._pos_timer.start()

    def _update_sticky_header(self):
        """Keeps the month box and the timeline in step with where you're reading."""
        pos = self._current_position()
        if pos:
            self._sync_position_widgets(pos[0])

    def _sync_position_widgets(self, month=None):
        if not self.current_manifest:
            return
        if month is None:
            pos = self._current_position()
            month = pos[0] if pos else None
        months = self.current_manifest["months"]
        if month not in months:
            return
        i = months.index(month)
        self.month_combo.blockSignals(True)
        self.month_combo.setCurrentIndex(i)
        self.month_combo.blockSignals(False)
        if not self.timeline.isSliderDown():
            self.timeline.blockSignals(True)
            self.timeline.setValue(i)
            self.timeline.blockSignals(False)
        self.tl_now.setText(_month_display(month) + "  ◂ you")

    def _timeline_changed(self, value):
        months = (self.current_manifest or {}).get("months") or []
        if 0 <= value < len(months):
            self.tl_now.setText(_month_display(months[value]))
            self._tl_timer.start()

    def _timeline_jump(self):
        months = (self.current_manifest or {}).get("months") or []
        v = self.timeline.value()
        if self.timeline.isSliderDown():
            self._tl_timer.start()
            return
        if 0 <= v < len(months):
            self._jump_to(months[v], 0)

    # ================================================================ search

    def _do_search(self):
        if not self.current_archive:
            return
        query = self.search_box.text().strip()
        self._search_token += 1
        if len(query) < 2:
            self.search_results_list.hide()
            self._search_results = []
            return
        t = ReaderSearchThread(self.main_window.assistant, self.current_archive, query, self._search_token)
        t.done.connect(lambda token, res, q=query: self._on_search_done(token, res, q))
        t.finished.connect(lambda th=t: self._search_threads.remove(th) if th in self._search_threads else None)
        self._search_threads.append(t)
        t.start()

    def _on_search_done(self, token, results, query):
        if token != self._search_token:
            return  # a newer search is already running
        self._search_results = results
        lst = self.search_results_list
        lst.clear()
        if not results:
            it = QListWidgetItem("")
            lst.addItem(it)
            lab = QLabel(f"No matches for “{html.escape(query)}”.")
            lab.setStyleSheet(f"padding: 14px 16px; color: {THEME['text_muted']}; font-size: 13px; background: transparent;")
            lst.setItemWidget(it, lab)
            it.setSizeHint(lab.sizeHint())
        else:
            pat = re.compile(re.escape(html.escape(query)), re.I)
            for n, r in enumerate(results[:30]):
                content = re.sub(r"\s+", " ", r.get("content", ""))
                pos = content.lower().find(query.lower())
                start = max(0, pos - 40)
                snippet = ("…" if start else "") + content[start:start + 150] + ("…" if len(content) > start + 150 else "")
                esc = pat.sub(lambda m: f"<span style=\"background-color:{THEME['accent']}55; color:{THEME['text_primary']};\">{m.group(0)}</span>", html.escape(snippet))
                when = _fmt_date(r.get("timestamp", "")) or _month_display(r.get("month", ""))
                lab = QLabel(f"<div style='color:{THEME['text_muted']}; font-size:11.5px;'>{html.escape(when)} · {html.escape(str(r.get('speaker', '')))}</div>"
                             f"<div style='font-size:13px;'>{esc}</div>")
                lab.setWordWrap(True)
                lab.setTextFormat(Qt.TextFormat.RichText)
                lab.setStyleSheet(f"padding: 9px 16px; color: {THEME['text_primary']}; background: transparent;")
                it = QListWidgetItem("")
                it.setData(Qt.ItemDataRole.UserRole, n)
                lst.addItem(it)
                lab.setFixedWidth(436)
                lst.setItemWidget(it, lab)
                it.setSizeHint(QSize(436, lab.sizeHint().height() + 2))
            foot = QListWidgetItem("")
            lst.addItem(foot)
            more = f"{len(results)}{'+' if len(results) >= 200 else ''} results" + (" (showing 30)" if len(results) > 30 else "")
            fl = QLabel(f"{more}  ·  ↑↓ to move, Enter to open, Esc to close")
            fl.setStyleSheet(f"padding: 8px 16px; color: {THEME['text_muted']}; font-size: 11.5px; background: transparent;")
            lst.setItemWidget(foot, fl)
            foot.setSizeHint(fl.sizeHint())
            foot.setFlags(Qt.ItemFlag.NoItemFlags)
            lst.setCurrentRow(0)
        self._place_search_list()
        lst.show()
        lst.raise_()

    def _open_result(self, n):
        if not (0 <= n < len(self._search_results)):
            return
        r = self._search_results[n]
        self._result_pos = n
        self.search_results_list.hide()
        self._jump_to(r["month"], r["index"], highlight=True)

    def _search_enter(self):
        lst = self.search_results_list
        if lst.isVisible():
            it = lst.currentItem()
            n = it.data(Qt.ItemDataRole.UserRole) if it else None
            if n is not None:
                self._open_result(n)
        elif self._search_results:
            n = (getattr(self, "_result_pos", -1) + 1) % len(self._search_results)
            self._open_result(n)  # Enter again = next match
        else:
            self._search_timer.start(0)

    def _on_search_result_clicked(self, item):
        n = item.data(Qt.ItemDataRole.UserRole)
        if n is not None:
            self._open_result(n)

    # ================================================================ bookmarks / pin / reassign

    def _refresh_bookmarks(self):
        self.bookmark_list.clear()
        pins = self._reader_pins(self.current_archive) if self.current_archive else []
        order = {m: i for i, m in enumerate((self.current_manifest or {}).get("months") or [])}
        pins.sort(key=lambda p: order.get(p.get("chat_id"), 0))
        for p in pins:
            snippet = re.sub(r"\s+", " ", p.get("content", "")).strip()
            it = QListWidgetItem(f"“{snippet[:70]}{'…' if len(snippet) > 70 else ''}”\n{self._pin_when(p)}")
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.bookmark_list.addItem(it)
        self.bookmark_hint.setVisible(not pins)

    def _on_bookmark_clicked(self, item):
        pin = item.data(Qt.ItemDataRole.UserRole)
        if not pin:
            return
        assistant = self.main_window.assistant
        month = pin.get("chat_id", "")
        idx = 0
        for i, m in enumerate(assistant.load_chat_reader_month(self.current_archive, month)):
            if m.get("content") == pin.get("content") and m.get("speaker") == pin.get("speaker"):
                idx = i
                break
        self._jump_to(month, idx, highlight=True)

    def _handle_reader_pin(self, bubble, month_key, msg_index, content, speaker, pin_source, timestamp=""):
        assistant = self.main_window.assistant
        if bubble.pin_id:
            assistant.unpin_message(bubble.pin_id)
            bubble.set_pinned(None)
        else:
            pin = assistant.pin_message(content=content, speaker=speaker, source=pin_source, chat_id=month_key, timestamp=timestamp)
            bubble.set_pinned(pin['id'])
        self._refresh_bookmarks()

    def _handle_reassign(self, bubble, month_key, msg_index):
        assistant = self.main_window.assistant
        choices = ["You"] + [n for n in (self.current_manifest.get('character_names') or []) if n not in ("You",)]
        new_speaker, ok = QInputDialog.getItem(
            self, "Reassign Speaker", "Who actually said this?", choices,
            editable=False,
        )
        if not ok or not new_speaker:
            return
        if assistant.reassign_chat_reader_speaker(self.current_archive, month_key, msg_index, new_speaker):
            self._month_cache.pop(month_key, None)
            bubble.set_is_user(new_speaker == "You")

    # ================================================================ import

    def import_chat(self):
        folder = QFileDialog.getExistingDirectory(self, "Select the exported chat folder")
        if not folder:
            return
        self._import_from_folder(folder)

    def _resolve_export_data_dir(self, path):
        """Accepts either the export's data/ folder directly, or its parent (e.g. dropping the whole export folder)."""
        path = Path(path)
        if (path / "message.json").exists():
            return path
        if (path / "data" / "message.json").exists():
            return path / "data"
        return None

    def _import_from_folder(self, folder):
        """
        Shared by the "Import Chat..." button and drag-and-drop. Character
        names are auto-detected (see FreesIA._detect_character_names), so
        the only decision left for the user is which chat to import.
        """
        from PyQt6.QtWidgets import QMessageBox
        assistant = self.main_window.assistant
        if not assistant:
            return
        data_dir = self._resolve_export_data_dir(folder)
        if not data_dir:
            QMessageBox.warning(self, "Import Failed", f"Couldn't find message.json in {folder} (or its data/ subfolder).")
            return
        result = assistant.inspect_character_ai_export(data_dir)
        if not result['success']:
            QMessageBox.warning(self, "Import Failed", result['error'])
            return
        if not result['chats']:
            QMessageBox.information(self, "Nothing to Import", "No chats with more than 10 messages were found in this export.")
            return

        options = []
        for c in result['chats']:
            names = ", ".join(c['detected_names']) if c['detected_names'] else "unknown speaker"
            options.append(f"{names} — {c['count']:,} messages ({c['first_time'][:10]} to {c['last_time'][:10]})")
        choice, ok = QInputDialog.getItem(self, "Import Chat", "Which chat do you want to import?", options, editable=False)
        if not ok:
            return
        chosen = result['chats'][options.index(choice)]
        character_names = chosen['detected_names']
        display_name = " & ".join(character_names) if character_names else f"Chat {chosen['chat_id'][:8]}"

        archive_name = re.sub(r'[^a-zA-Z0-9]+', '_', display_name).strip('_') or "archive"
        import_result = assistant.import_character_ai_chat(
            str(data_dir), chosen['chat_id'], archive_name, display_name, character_names
        )
        if not import_result['success']:
            QMessageBox.warning(self, "Import Failed", import_result['error'])
            return
        self.refresh_archive_list()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if local_path:
                self._import_from_folder(local_path)


class PinnedMessagesView(QWidget):
    """
    Right-side info panel docked to the window's right edge (Character.AI-
    style side panel), sitting alongside the chat rather than replacing it.
    A header (avatar/name/tagline) followed by a menu of rows - "Pinned"
    expands in place to show every pinned message (from either the live
    chat or the Chat Reader); "Persona" and "Settings" deep-link into the
    existing Settings dialog rather than duplicating that UI here.
    """

    PANEL_WIDTH = 340

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._pinned_expanded = True
        self.setFixedWidth(self.PANEL_WIDTH)
        # Scoped by object name: a bare `QWidget {}` rule cascades to every
        # child, which painted a stray left border on each menu row/label.
        self.setObjectName("PinnedPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            #PinnedPanel {{
                background-color: {THEME['bg_secondary']};
                border-left: 1px solid {THEME['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        # --- Header: avatar, name, tagline, close button ---
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        avatar = avatar_label(44)
        header_row.addWidget(avatar)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        self.ai_name_label = name_label = QLabel(AI_NAME)
        name_label.setStyleSheet(f"QLabel {{ color: {THEME['text_primary']}; font-size: 15px; font-weight: bold; background: transparent; }}")
        name_col.addWidget(name_label)
        tagline_label = QLabel("Local AI assistant")
        tagline_label.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 11px; background: transparent; }}")
        name_col.addWidget(tagline_label)
        header_row.addLayout(name_col)
        header_row.addStretch()

        close_btn = QPushButton()
        close_btn.setIcon(line_icon("close", THEME['text_secondary'], 16))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; color: {THEME['text_secondary']}; font-size: 13px; }}
            QPushButton:hover {{ color: {THEME['text_primary']}; }}
        """)
        close_btn.clicked.connect(lambda: self.main_window.toggle_pinned_panel(False))
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        layout.addSpacing(6)

        # --- Menu rows ---
        self.pinned_row, self.pinned_chevron = self._add_menu_row(layout, "pin", "Pinned", clickable=True)
        self.pinned_row.mousePressEvent = lambda e: self._toggle_pinned_section()
        self._add_menu_row(layout, "person", "Persona", clickable=True,
                            on_click=lambda: self.main_window.show_settings(initial_page="Persona"))
        self._add_menu_row(layout, "gear", "Settings", clickable=True,
                            on_click=lambda: self.main_window.show_settings(initial_page="General"))

        layout.addSpacing(4)

        # --- Pinned section content (collapsible under the Pinned row) ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }}" + themed_scrollbar_css())
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.list_widget)
        layout.addWidget(self.scroll, 1)

        self.empty_label = QLabel("Nothing pinned yet. Pin a message from the chat or Chat Reader to see it here.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 14px; }}")

    def _add_menu_row(self, layout, icon: str, label_text: str, clickable=False, on_click=None):
        row = QFrame()
        row.setFrameShape(QFrame.Shape.NoFrame)
        row.setFixedHeight(44)
        row.setMaximumHeight(44)
        # Belt-and-suspenders beyond setFixedHeight: Windows' native widget
        # style computes its own size hint for QFrame that can pad it out
        # taller than the fixed height under the real "windows" platform
        # plugin (didn't reproduce under the offscreen test platform used
        # for verification, only showed up live) - locking the size policy
        # to Fixed stops the layout from ever honoring that inflated hint.
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
        row.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border-radius: 10px; }}
            QFrame:hover {{ background-color: {THEME['hover']}; }}
        """)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 0, 8, 0)
        row_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(18, 18)
        if icon == "pin":
            icon_label.setPixmap(pin_icon(THEME['accent'], 16).pixmap(16, 16))
        else:
            icon_label.setPixmap(line_pixmap("user" if icon == "person" else "settings", THEME['text_primary'], 16))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("QLabel { background: transparent; }")
        row_layout.addWidget(icon_label)

        text_label = QLabel(label_text)
        text_label.setStyleSheet(f"QLabel {{ font-size: 13px; background: transparent; color: {THEME['text_primary']}; }}")
        row_layout.addWidget(text_label)
        row_layout.addStretch()

        chevron = QLabel()
        chevron.setPixmap(line_pixmap("chev-right", THEME['text_muted'], 14, 2.0))
        chevron.setStyleSheet("QLabel { background: transparent; }")
        row_layout.addWidget(chevron)

        if on_click:
            row.mousePressEvent = lambda e: on_click()
        layout.addWidget(row)
        return row, chevron

    def _toggle_pinned_section(self):
        self._pinned_expanded = not self._pinned_expanded
        self.scroll.setVisible(self._pinned_expanded)
        self.pinned_chevron.setPixmap(line_pixmap("chev-down" if self._pinned_expanded else "chev-right", THEME['text_muted'], 14, 2.0))

    def refresh(self):
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        assistant = self.main_window.assistant
        pins = assistant.pinned_messages if assistant else []
        if not pins:
            self.list_layout.addWidget(self.empty_label)
            return

        for pin in sorted(pins, key=lambda p: p.get('pinned_at', ''), reverse=True):
            self.list_layout.addWidget(self._build_entry(pin))
        self.list_layout.addStretch(1)  # soak up leftover height so cards stay compact at the top

    def _source_label(self, pin) -> str:
        source = pin.get('source', 'live_chat')
        if source == 'live_chat':
            return "Live Chat"
        if source.startswith('chat_reader:'):
            archive_name = source[len('chat_reader:'):]
            manifest = self.main_window.assistant.get_chat_reader_manifest(archive_name) if self.main_window.assistant else None
            return manifest['display_name'] if manifest else archive_name
        return source

    def _build_entry(self, pin):
        """
        Renders each pin as an actual MessageBubble - the same widget and
        styling the chat itself uses - rather than a separate summary-card
        design, so a pinned message looks exactly like it did in the
        conversation it came from.
        """
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        # Maximum (not Preferred) vertical policy: keeps each card at its
        # content height instead of splitting the panel's spare height.
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        is_user = pin.get('speaker') == 'You'
        bubble = MessageBubble(pin.get('content', ''), is_user=is_user, show_regen_controls=False)
        bubble.setMaximumWidth(self.PANEL_WIDTH - 40)
        if bubble.edit_btn:
            bubble.edit_btn.hide()  # pinned cards are read-only; the pencil just adds dead space
        bubble.set_pinned(pin['id'])  # already pinned - shows the filled badge; clicking it unpins
        bubble.on_pin = lambda b, p=pin: self._unpin(p)

        bubble_row = QHBoxLayout()
        if is_user:
            bubble_row.addStretch()
            bubble_row.addWidget(bubble)
        else:
            bubble_row.addWidget(bubble)
            bubble_row.addStretch()
        col.addLayout(bubble_row)

        jump_btn = QPushButton(f"↳ {self._source_label(pin)} · Jump to message")
        jump_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        jump_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {THEME['text_muted']};
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{ color: {THEME['text_primary']}; }}
        """)
        jump_btn.clicked.connect(lambda: self._jump_to(pin))
        jump_row = QHBoxLayout()
        if is_user:
            jump_row.addStretch()
            jump_row.addWidget(jump_btn)
        else:
            jump_row.addWidget(jump_btn)
            jump_row.addStretch()
        col.addLayout(jump_row)

        return container

    def _unpin(self, pin):
        assistant = self.main_window.assistant
        if assistant:
            assistant.unpin_message(pin['id'])
        self.refresh()

    def _jump_to(self, pin):
        source = pin.get('source', 'live_chat')
        if source == 'live_chat':
            chat_id = pin.get('chat_id')
            if not chat_id:
                return
            self.main_window.content_stack.setCurrentIndex(0)
            self.main_window.load_chat(chat_id)
        elif source.startswith('chat_reader:'):
            archive_name = source[len('chat_reader:'):]
            self.main_window.content_stack.setCurrentIndex(1)
            self.main_window.chat_reader_view.open_at_pin(archive_name, pin)


# ==============================================================================
# MAIN WINDOW
# ==============================================================================

class MainWindow(QMainWindow):
    def __init__(self, assistant=None):
        super().__init__()
        self.assistant = assistant
        try:
            set_ai_name(getattr(assistant, "assistant_name", "") if isinstance(getattr(assistant, "assistant_name", ""), str) else "")
        except Exception:
            pass
        MessageBubble.default_on_pin = self.handle_pin_message
        self.thread = None
        self.loading_bubble_widget = None  # Track loading bubble
        self.pending_attached_image_path = None  # image queued up to edit, if any
        self.active_operation = None  # None / "chat" / "image" - drives the send/stop button
        
        # Chat history management
        self.chat_dir = Path(__file__).parent / "ChatHistory"
        self.chat_dir.mkdir(exist_ok=True)
        self.current_chat_id = None
        self.current_chat_messages = []  # List of {"role": "user"/"ai", "content": "..."}
        self.chat_history_layout = None  # Will store the history layout for adding items
        self._chat_count_cache = None  # Cache for chat count
        self._chat_metadata_cache = {}  # Cache for chat metadata {chat_id: {name, created_at}}
        self._chat_item_widgets = {}  # chat_id -> ChatHistoryItem, so auto-titling can update the sidebar label
        self._chat_index = {}  # chat_id -> {name, created, updated, preview, pinned, blob} - drives the sidebar
        self._chat_search = ""
        self._sidebar_order = []
        self._status_retry = None
        self._status_ticks = 0
        self._title_thread = None
        self._memory_thread = None
        self._last_user_container_widget = None  # for the AI response's "regenerate" button
        self._last_user_text = None
        self._regen_target_bubble = None  # in-place regenerate (versioned) state
        self._regen_accum = ""
        self._regen_thread_obj = None
        
        # Sidebar state
        self.sidebar_visible = True
        self.sidebar_animation = None
        self.sidebar_width = 260  # user-adjustable via the drag handle
        self._install_shortcuts()
        
        self.init_ui()

        # Warm up the image model shortly after launch so it's already loaded
        # by the time the user makes their first real request.
        self._warmup_thread = None
        if self.assistant:
            QTimer.singleShot(3000, self.start_image_warmup)

    def start_image_warmup(self):
        self._warmup_thread = ImageWarmupThread(self.assistant)
        self._warmup_thread.start()

    # ==================== WINDOW INITIALIZATION ====================
    
    def init_ui(self):
        self.setWindowTitle("FreesIA")
                # Set window icon (taskbar and title bar)
        icon_path = Path(__file__).parent / "FreesIA Icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Tray icon used only to surface desktop toast notifications (chat
        # replies / finished images) when the window isn't focused - Qt
        # requires a tray icon instance to show these on Windows.
        self.tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            if icon_path.exists():
                self.tray_icon.setIcon(QIcon(str(icon_path)))
            self.tray_icon.setVisible(True)
                # Set window size (1400x900) and center on screen
        self.setGeometry(100, 100, 1400, 900)
        
        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 1400) // 2
        y = (screen.height() - 900) // 2
        self.move(x, y)
        
        # Main container
        main_container = QWidget()
        main_container.setStyleSheet(f"QWidget {{ background-color: {THEME['bg_primary']}; }}")
        self.setCentralWidget(main_container)
        main_layout = QHBoxLayout(main_container)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create overlay widget for dimming background (hidden by default)
        self.overlay = QWidget(main_container)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.overlay.setGeometry(main_container.rect())
        self.overlay.hide()
        self.overlay.raise_()
        
        # Sidebar
        self.create_sidebar(main_layout)

        self.sidebar_resize_handle = SidebarResizeHandle(self.sidebar, self)
        main_layout.addWidget(self.sidebar_resize_handle)

        # Main content area - a QStackedWidget so the Chat Reader can swap in
        # over the normal chat without needing its own top-level window.
        self.content_stack = QStackedWidget()
        chat_page = self.create_main_area(main_layout)
        self.content_stack.addWidget(chat_page)  # index 0: normal chat
        self.chat_reader_view = ChatReaderView(self)
        self.content_stack.addWidget(self.chat_reader_view)  # index 1: Chat Reader
        main_layout.addWidget(self.content_stack, 1)

        # Pinned Messages panel - docked to the right edge, sits alongside
        # whichever page is showing in content_stack (Character.AI-style
        # side panel) rather than replacing it. Hidden until toggled.
        self.pinned_messages_view = PinnedMessagesView(self)
        self.pinned_messages_view.hide()
        main_layout.addWidget(self.pinned_messages_view)

        # Apply global styles
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {THEME['bg_primary']};
                color: {THEME['text_primary']};
            }}
        """)
    
    # ==================== SIDEBAR (CHAT HISTORY) ====================
    
    def get_chat_count(self):
        """Get total number of chats (cached)"""
        if self._chat_count_cache is None:
            self._chat_count_cache = len(list(self.chat_dir.glob('*.json')))
        return self._chat_count_cache
    
    def increment_chat_count(self):
        """Increment chat count cache when creating new chat"""
        if self._chat_count_cache is None:
            self._chat_count_cache = len(list(self.chat_dir.glob('*.json')))
        self._chat_count_cache += 1
    
    def decrement_chat_count(self):
        """Decrement chat count cache when deleting a chat"""
        if self._chat_count_cache is None:
            self._chat_count_cache = len(list(self.chat_dir.glob('*.json')))
        else:
            self._chat_count_cache = max(0, self._chat_count_cache - 1)
    
    def create_sidebar(self, parent_layout):
        """Create left sidebar"""
        self.sidebar = QFrame()
        # Pinned to an exact width (not just a ceiling) so it reliably
        # renders at sidebar_width instead of whatever its Fixed-policy
        # sizeHint() happens to compute. Collapse/expand temporarily
        # releases minimumWidth to 0 so the shrink animation still works.
        self.sidebar.setMinimumWidth(self.sidebar_width)
        self.sidebar.setMaximumWidth(self.sidebar_width)
        
        # Set size policy to prevent unwanted resizing
        size_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.sidebar.setSizePolicy(size_policy)
        
        # Scoped by object name so the border doesn't cascade onto every
        # child QFrame (scroll area, buttons' frames) inside the sidebar.
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setStyleSheet(f"""
            #Sidebar {{
                background-color: {THEME['bg_secondary']};
                border-right: 1px solid {THEME['border']};
            }}
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(12)
        
        # Brand row: FreesIA emblem + wordmark
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(8, 0, 0, 4)
        brand_row.setSpacing(10)
        emblem = app_logo_pixmap(26, emblem_only=True)
        if not emblem.isNull():
            emblem_label = QLabel()
            emblem_label.setPixmap(emblem)
            emblem_label.setStyleSheet("QLabel { background: transparent; }")
            brand_row.addWidget(emblem_label)
        brand_text = QLabel("FREESIA")
        brand_font = QFont(brand_text.font())
        brand_font.setPixelSize(15)
        brand_font.setBold(True)
        brand_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        brand_text.setFont(brand_font)
        brand_text.setStyleSheet(f"QLabel {{ color: {THEME['text_primary']}; background: transparent; }}")
        brand_row.addWidget(brand_text)
        brand_row.addStretch()
        sidebar_layout.addLayout(brand_row)

        # Header with collapse button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self.sidebar_header = QLabel("Chat History")
        self.sidebar_header.setStyleSheet(f"""
            background: transparent;
            color: {THEME['text_muted']};
            font-size: 13px;
            font-weight: 500;
            padding: 8px 12px;
        """)
        header_layout.addWidget(self.sidebar_header)
        
        # Collapse button (in sidebar)
        self.collapse_btn = QPushButton()
        self.collapse_btn.setIcon(line_icon("panel-left", THEME['text_secondary'], 18))
        self.collapse_btn.setIconSize(QSize(18, 18))
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.setToolTip("Collapse sidebar")
        self.collapse_btn.setFixedSize(32, 32)
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {THEME['text_secondary']};
                font-size: 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover']};
            }}
        """)
        self.collapse_btn.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.collapse_btn)
        
        sidebar_layout.addLayout(header_layout)

        # New Chat button, under the header
        new_chat_btn = QPushButton("  New Chat")
        new_chat_btn.setIcon(line_icon("plus", THEME['text_primary'], 16, 2.0))
        new_chat_btn.setIconSize(QSize(16, 16))
        new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_tertiary']};
                border: 1px solid {THEME['border']};
                border-radius: 14px;
                padding: 12px 14px;
                color: {THEME['text_primary']};
                font-size: 14px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover_strong']};
            }}
        """)
        new_chat_btn.clicked.connect(self.create_new_chat)
        sidebar_layout.addWidget(new_chat_btn)

        # Search across chat titles and message text
        self.chat_search_box = QLineEdit()
        self.chat_search_box.setPlaceholderText("Search chats")
        self.chat_search_box.setClearButtonEnabled(True)
        self.chat_search_box.addAction(line_icon("search", THEME['text_muted'], 16), QLineEdit.ActionPosition.LeadingPosition)
        self.chat_search_box.setFixedHeight(38)
        self.chat_search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: transparent;
                border: 1px solid {THEME['border']};
                border-radius: 12px;
                padding: 0 10px;
                color: {THEME['text_primary']};
                font-size: 13.5px;
            }}
            QLineEdit:focus {{ border: 1px solid {THEME['border_strong']}; }}
        """)
        self._chat_search_timer = QTimer(self)
        self._chat_search_timer.setSingleShot(True)
        self._chat_search_timer.setInterval(150)
        self._chat_search_timer.timeout.connect(self._apply_chat_search)
        self.chat_search_box.textChanged.connect(lambda _t: self._chat_search_timer.start())
        sidebar_layout.addWidget(self.chat_search_box)
        
        # Chat history scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """ + themed_scrollbar_css())
        
        history_widget = QWidget()
        history_widget.setStyleSheet("background: transparent;")
        self.chat_history_layout = QVBoxLayout(history_widget)
        self.chat_history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_history_layout.setSpacing(4)
        scroll.setWidget(history_widget)
        
        # Load existing chats
        self.load_all_chats()
        
        sidebar_layout.addWidget(scroll, 1)
        

        # Image gallery button
        gallery_btn = QPushButton("  Image Gallery")
        gallery_btn.setIcon(line_icon("image", THEME['text_primary'], 18))
        gallery_btn.setIconSize(QSize(18, 18))
        gallery_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gallery_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {THEME['border']};
                border-radius: 14px;
                padding: 12px;
                color: {THEME['text_primary']};
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover']};
            }}
        """)
        gallery_btn.clicked.connect(self.open_gallery)
        sidebar_layout.addWidget(gallery_btn)

        # Chat Reader button - browse imported chat archives (e.g. Character.AI exports)
        chat_reader_btn = QPushButton("  Chat Reader")
        chat_reader_btn.setIcon(line_icon("book", THEME['text_primary'], 18))
        chat_reader_btn.setIconSize(QSize(18, 18))
        chat_reader_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        chat_reader_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {THEME['border']};
                border-radius: 14px;
                padding: 12px;
                color: {THEME['text_primary']};
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover']};
            }}
        """)
        chat_reader_btn.clicked.connect(self.open_chat_reader)
        sidebar_layout.addWidget(chat_reader_btn)

        # Bottom icons (user profile and settings)
        bottom_icons_layout = QHBoxLayout()
        
        # User profile icon
        self.user_icon = QPushButton()
        user_icon_path = Path(__file__).parent / "Icons" / "UserProfileLogo.png"
        self.user_icon.setIcon(line_icon("user", THEME['text_secondary'], 20))
        self.user_icon.setIconSize(QSize(20, 20))
        self.user_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.user_icon.setFixedSize(36, 36)
        self.user_icon.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover']};
            }}
        """)
        bottom_icons_layout.addWidget(self.user_icon)

        # Settings icon at bottom
        self.settings_icon = QPushButton()
        settings_icon_path = Path(__file__).parent / "Icons" / "settingsLogo.png"
        self.settings_icon.setIcon(line_icon("settings", THEME['text_secondary'], 20))
        self.settings_icon.setIconSize(QSize(20, 20))
        self.settings_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_icon.setFixedSize(36, 36)
        self.settings_icon.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover']};
            }}
        """)
        self.settings_icon.clicked.connect(lambda: self.show_settings())
        bottom_icons_layout.addWidget(self.settings_icon)
        bottom_icons_layout.addStretch()
        
        sidebar_layout.addLayout(bottom_icons_layout)
        
        parent_layout.addWidget(self.sidebar)
    
    # ==================== MAIN CHAT AREA ====================
    
    def create_main_area(self, parent_layout):
        """Create main content area"""
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Expand sidebar button (shown when sidebar is collapsed)
        self.expand_btn = QPushButton()
        self.expand_btn.setIcon(line_icon("panel-left", THEME['text_primary'], 18))
        self.expand_btn.setIconSize(QSize(18, 18))
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.setToolTip("Show sidebar")
        self.expand_btn.setFixedSize(36, 36)
        self.expand_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_secondary']};
                border: 1px solid {THEME['border']};
                color: {THEME['text_primary']};
                font-size: 16px;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover']};
            }}
        """)
        self.expand_btn.clicked.connect(self.toggle_sidebar)
        self.expand_btn.hide()  # Hidden by default

        # Pinned Messages panel toggle - its own button, deliberately not
        # grouped with the chat-history controls in the left sidebar, since
        # it opens a side panel next to the chat rather than navigating away.
        self.pinned_toggle_btn = QPushButton()
        self.pinned_toggle_btn.setFixedSize(40, 40)
        self.pinned_toggle_btn.setIcon(line_icon("panel-right", THEME['accent'], 18))
        self.pinned_toggle_btn.setIconSize(QSize(18, 18))
        self.pinned_toggle_btn.setToolTip("Pinned messages and settings panel")
        self.pinned_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pinned_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_tertiary']};
                border: none;
                border-radius: 20px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover_strong']};
            }}
        """)
        self.pinned_toggle_btn.clicked.connect(lambda: self.toggle_pinned_panel())

        # Header bar: [expand] avatar + name/tagline ............ [pinned panel]
        header = QWidget()
        header.setObjectName("ChatHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setStyleSheet(f"#ChatHeader {{ background-color: {THEME['bg_primary']}; border-bottom: 1px solid {THEME['border']}; }}")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 12, 28, 12)
        header_layout.setSpacing(12)
        header_layout.addWidget(self.expand_btn)
        header_layout.addWidget(avatar_label(40))
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self.ai_title_label = title_name = QLabel(AI_NAME)
        title_name.setStyleSheet(f"QLabel {{ color: {THEME['text_primary']}; font-size: 15px; font-weight: bold; background: transparent; }}")
        self.status_label = StatusLabel()
        self.status_label.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 12px; background: transparent; }}")
        self.status_label.clicked.connect(self._on_status_clicked)
        title_col.addWidget(title_name)
        title_col.addWidget(self.status_label)
        self._refresh_status()
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(4000)
        self._status_timer.timeout.connect(self._status_tick)
        self._status_timer.start()
        self._init_checkins()
        header_layout.addLayout(title_col)
        header_layout.addStretch()
        header_layout.addWidget(self.pinned_toggle_btn)
        main_layout.addWidget(header)
        
        # Chat display area (scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """ + themed_scrollbar_css())
        
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chat_layout.setSpacing(24)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initial centered welcome screen
        self.welcome_container = self._build_welcome()
        self.chat_layout.addWidget(self.welcome_container)
        
        # Centered conversation column (max ~800px) like Character.AI, instead
        # of bubbles spreading edge to edge on a wide window.
        self.chat_widget.setMaximumWidth(800)
        chat_holder = QWidget()
        chat_holder.setStyleSheet("background: transparent;")
        holder_layout = QHBoxLayout(chat_holder)
        holder_layout.setContentsMargins(28, 24, 28, 8)
        holder_layout.setSpacing(0)
        holder_layout.addStretch(1)
        holder_layout.addWidget(self.chat_widget, 100)
        holder_layout.addStretch(1)
        self.chat_scroll.setWidget(chat_holder)
        main_layout.addWidget(self.chat_scroll, 1)

        # Input area at bottom
        self.create_input_area(main_layout)

        return main_area

    def _build_welcome(self):
        """Compact intro (avatar, name, blurb) plus suggestion chips. The chips
        live in self.welcome_prompts so they can be hidden after the first
        message while the intro stays at the top of the conversation."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        logo = app_logo_pixmap(200)
        if not logo.isNull():
            logo_label = QLabel()
            logo_label.setPixmap(logo)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("QLabel { background: transparent; }")
            logo_effect = QGraphicsOpacityEffect(logo_label)
            logo_effect.setOpacity(0.9)
            logo_label.setGraphicsEffect(logo_effect)
            layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignCenter)
            layout.addSpacing(16)
        blurb = QLabel("Ask anything, run a command, or ask for an image.\nPick a suggestion or just start typing.")
        blurb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        blurb.setStyleSheet(f"QLabel {{ color: {THEME['text_secondary']}; font-size: 14px; background: transparent; }}")
        layout.addWidget(blurb)

        self.welcome_prompts = QWidget()
        prompts_layout = QVBoxLayout(self.welcome_prompts)
        prompts_layout.setContentsMargins(0, 18, 0, 0)
        prompts_layout.setSpacing(10)
        for prompt_text in [
            "What's the weather like today?",
            "Help me debug this Python code",
            "Explain quantum computing simply",
            "Open my favorite app",
        ]:
            prompt_btn = QPushButton(prompt_text)
            prompt_btn.setFixedHeight(40)
            prompt_btn.setMaximumWidth(360)
            prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            prompt_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME['bg_tertiary']};
                    border: 1px solid {THEME['border_strong']};
                    border-radius: 20px;
                    padding: 8px 20px;
                    color: {THEME['text_primary']};
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {THEME['hover_strong']};
                }}
            """)
            prompt_btn.clicked.connect(lambda checked, p=prompt_text: self.use_suggested_prompt(p))
            prompts_layout.addWidget(prompt_btn, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.welcome_prompts, 0, Qt.AlignmentFlag.AlignCenter)
        return container

    # ==================== INPUT AREA ====================
    
    def create_input_area(self, parent_layout):
        """Create bottom input area"""
        input_container = QWidget()
        input_container.setMaximumWidth(800)
        input_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)

        outer_layout = QVBoxLayout(input_container)
        outer_layout.setContentsMargins(0, 20, 0, 0)
        outer_layout.setSpacing(6)

        # Attachment chip - hidden until an image is attached for editing.
        # Shows an actual thumbnail (like ChatGPT/Grok's attach preview), not
        # just a filename, so it's visually obvious a photo is queued up.
        self.attachment_chip = QWidget()
        self.attachment_chip.setStyleSheet(f"QWidget {{ background-color: {THEME['bg_tertiary']}; border-radius: 10px; }}")
        chip_layout = QHBoxLayout(self.attachment_chip)
        chip_layout.setContentsMargins(8, 6, 8, 6)
        chip_layout.setSpacing(8)
        self.attachment_thumb = QLabel()
        self.attachment_thumb.setFixedSize(40, 40)
        self.attachment_thumb.setStyleSheet(f"QLabel {{ background-color: {THEME['bg_primary']}; border-radius: 6px; }}")
        self.attachment_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.attachment_thumb.setScaledContents(False)
        chip_layout.addWidget(self.attachment_thumb)
        self.attachment_label = QLabel("")
        self.attachment_label.setStyleSheet(f"QLabel {{ color: {THEME['text_primary']}; font-size: 12px; background: transparent; }}")
        chip_layout.addWidget(self.attachment_label)
        chip_layout.addStretch()
        clear_attach_btn = QPushButton()
        clear_attach_btn.setIcon(line_icon("close", THEME['text_secondary'], 12, 2.2))
        clear_attach_btn.setIconSize(QSize(12, 12))
        clear_attach_btn.setFixedSize(20, 20)
        clear_attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_attach_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {THEME['text_secondary']}; font-size: 11px; }}
            QPushButton:hover {{ color: {THEME['text_primary']}; }}
        """)
        clear_attach_btn.clicked.connect(self.clear_attached_image)
        chip_layout.addWidget(clear_attach_btn)
        self.attachment_chip.hide()
        outer_layout.addWidget(self.attachment_chip)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)
        outer_layout.addLayout(input_layout)

        # Input wrapper for border and styling
        input_wrapper = QFrame()
        input_wrapper.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_tertiary']};
                border: 1px solid {THEME['border_strong']};
                border-radius: 28px;
            }}
        """)
        
        wrapper_layout = QHBoxLayout(input_wrapper)
        wrapper_layout.setContentsMargins(14, 8, 8, 8)
        wrapper_layout.setSpacing(8)
        
        # Attachment icon (optional)
        self.attach_btn = QPushButton()
        attach_icon_path = Path(__file__).parent / "Icons" / "ImageLogo.png"
        self.attach_btn.setIcon(line_icon("image", THEME['text_secondary'], 20))
        self.attach_btn.setIconSize(QSize(20, 20))
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setFixedSize(36, 36)
        self.attach_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_tertiary']};
                border-radius: 16px;
            }}
        """)
        self.attach_btn.clicked.connect(self.on_attach_clicked)
        self.attach_btn.setToolTip("Attach a photo to edit")
        wrapper_layout.addWidget(self.attach_btn)

        # Mic icon (optional)
        self.mic_btn = QPushButton()
        mic_icon_path = Path(__file__).parent / "Icons" / "MicLogo.png"
        self.mic_btn.setIcon(line_icon("mic", THEME['text_secondary'], 20))
        self.mic_btn.setIconSize(QSize(20, 20))
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_tertiary']};
                border-radius: 16px;
            }}
        """)

        self.mic_btn.clicked.connect(self.handle_mic_button)
        wrapper_layout.addWidget(self.mic_btn)

        # Text input
        self.input_box = ChatInputBox()
        self.input_box.setPlaceholderText(f"Message {AI_NAME}…  (type 'Help' for commands)")
        self.input_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                font-size: 15px;
                color: {THEME['text_primary']};
                padding: 4px;
            }}
        """)
        self.input_box.returnPressed.connect(self.send_message)
        wrapper_layout.addWidget(self.input_box, 1)
        # Send button
        self.send_btn = QPushButton()
        send_icon_path = Path(__file__).parent / "Icons" / "SendLogo.png"
        self.send_btn.setIcon(line_icon("arrow-up", THEME['bg_primary'], 22, 2.2))
        self.send_btn.setIconSize(QSize(22, 22))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['text_primary']};
                border: none;
                border-radius: 20px;
                color: {THEME['bg_primary']};
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME['text_secondary']};
            }}
            QPushButton:disabled {{
                background-color: {THEME['bubble_user']};
                color: {THEME['text_muted']};
            }}
        """)
        self._send_icon = self.send_btn.icon()  # kept to restore after showing the stop icon
        self.send_btn.clicked.connect(self.on_send_button_clicked)
        wrapper_layout.addWidget(self.send_btn)
        input_layout.addWidget(input_wrapper)
        # Center the input container
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(28, 8, 28, 22)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(input_container, 100)
        bottom_layout.addStretch(1)
        parent_layout.addLayout(bottom_layout)

    def handle_mic_button(self):
        """Handle mic button click: start voice recognition"""
        if hasattr(self, 'assistant') and self.assistant:
            self.assistant.start_listening_background()
            # Optionally, show feedback in the chat
            self.add_ai_message("Listening...")
        else:
            self.add_ai_message("Assistant not ready.")

    def new_chat(self):
        """Start a new chat"""
        # Stop any running AI thread
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(1000)  # Wait up to 1 second for thread to finish
            if self.thread.isRunning():
                self.thread.terminate()  # Force terminate if still running
        
        # Remove loading bubble if exists
        if self.loading_bubble_widget and self.loading_bubble_widget.parent():
            _lb = self.loading_bubble_widget.findChild(LoadingBubble)
            if _lb:
                _lb.stop_animation()
            self.loading_bubble_widget.deleteLater()
            self.loading_bubble_widget = None
        
        # Re-enable input
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        
        # Clear messages
        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Switch back to center alignment for welcome screen
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Show welcome screen again
        self.welcome_container = self._build_welcome()
        self.chat_layout.addWidget(self.welcome_container)
    
    # ==================== MESSAGE PROCESSING ====================

    def start_image_generation(self, prompt: str, source_image_path=None):
        """
        Kick off async image generation/editing and track it for the loading-bubble
        swap. Fresh (first-time) generations default to square - the size picker
        lives under each generated image bubble, not here, since it needs an
        existing image to attach to.
        """
        self.active_operation = "image"
        self.set_send_button_mode("stop")
        self._image_gen_thread = ImageGenThread(
            self.assistant, prompt, source_image_path=source_image_path
        )
        self._image_gen_thread.finished.connect(lambda result: self.on_image_generated(result, prompt))
        self._image_gen_thread.start()

    def on_attach_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Attach a Photo to Edit", str(Path.home() / "Desktop"),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.attach_image_path(file_path)

    def attach_image_path(self, file_path):
        """Queue an image to edit with the next message (file picker and the gallery both use this)."""
        self.pending_attached_image_path = Path(file_path)
        pixmap = QPixmap(str(file_path))
        if not pixmap.isNull():
            scaled = pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation)
            self.attachment_thumb.setPixmap(scaled)
        self.attachment_label.setText(f"{self.pending_attached_image_path.name} - describe the edit and send")
        self.attachment_chip.show()
        self.input_box.setFocus()

    def open_gallery(self):
        GalleryDialog(self, self.assistant, main_window=self).exec()

    def clear_attached_image(self):
        self.pending_attached_image_path = None
        self.attachment_chip.hide()

    def on_image_generated(self, result: dict, prompt: str):
        """Swap the loading bubble for either the generated image or an error message"""
        if self.loading_bubble_widget and self.loading_bubble_widget.parent():
            _lb = self.loading_bubble_widget.findChild(LoadingBubble)
            if _lb:
                _lb.stop_animation()
            self.loading_bubble_widget.deleteLater()
            self.loading_bubble_widget = None

        if result.get("success"):
            paths = result.get("paths") or [result["path"]]
            label = f"[Generated image: {prompt}]" + (f" ({len(paths)} variations)" if len(paths) > 1 else "")
            self.current_chat_messages.append({"role": "ai", "content": label})
            self.save_current_chat()
            self.maybe_generate_chat_title(label)
            for p in paths:
                bubble = ImageMessageBubble(p, prompt, self.assistant, self)
                bubble_container = self._ai_row(bubble)
                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                bubble.on_delete = lambda b, cw=container_widget: self.remove_image_bubble(cw)
                self.chat_layout.addWidget(container_widget)
            self.notify_if_unfocused("FreesIA - Image ready", prompt)
        else:
            error_text = f"Couldn't generate that: {result.get('error', 'unknown error')}"
            self.current_chat_messages.append({"role": "ai", "content": error_text})
            self.save_current_chat()
            self.maybe_generate_chat_title(prompt)
            bubble = MessageBubble(error_text, is_user=False)
            self._wire_regenerate(bubble)
            bubble_container = self._ai_row(bubble)
            container_widget = QWidget()
            container_widget.setLayout(bubble_container)
            self.chat_layout.addWidget(container_widget)

        self.scroll_chat_to_bottom()
        self.enable_input()

    def remove_image_bubble(self, container_widget):
        """Delete callback for ImageMessageBubble - drops it out of the chat layout"""
        index = self.chat_layout.indexOf(container_widget)
        if index != -1:
            item = self.chat_layout.takeAt(index)
            if item and item.widget():
                item.widget().deleteLater()

    def is_system_command(self, text: str) -> bool:
        """Check if text is a system command (not a conversation)"""
        text_lower = text.lower().strip()

        # Keywords that require a trailing object ("open notepad", "search for X")
        # - safe to match anywhere in the message, since normal conversation
        # rarely contains these phrases mid-sentence.
        prefix_keywords = [
            'open ', 'close ', 'launch ', 'start ',
            'find ', 'search ', 'create folder', 'recent files', 'open website',
            'media play', 'media pause', 'media next', 'media previous', 'media stop',
            'control panel', 'list apps', 'show apps',
            'mic on', 'mic off', 'tts on', 'tts off', 'toggle tts',
            'show permissions', 'revoke permissions',
            'clear ai history', 'clear conversation', 'reload personality', 'change model', 'switch model',
            'create shortcut', 'add shortcut', 'remove shortcut', 'delete shortcut',
            'list shortcuts', 'show shortcuts', 'my shortcuts',
            'run ', 'execute ',
            # Specific enough (2-3 words) that they're safe to match anywhere
            # in the message, not just short/leading - "what time is it in my
            # location?" should reach the real system clock the same as bare
            # "what time", not fall through to the AI hallucinating an answer.
            'what time', 'what date', 'weather',
        ]
        if any(keyword in text_lower for keyword in prefix_keywords):
            return True

        # Bare single-word commands ("help", "wifi", "battery"...) are also
        # ordinary English words used constantly in normal conversation
        # ("can you help me with...", "my wifi's been flaky"), so a blind
        # substring check misfires on those. Only treat them as commands when
        # they open a short, direct message - not when they show up
        # naturally partway through a longer sentence.
        bare_keywords = [
            'volume', 'brightness', 'screenshot', 'battery', 'system info',
            'lock', 'sleep', 'restart', 'shutdown',
            'wifi', 'bluetooth',
            'help', 'command', 'what can you do',
        ]
        words = text_lower.split()
        if len(words) <= 4 and any(text_lower.startswith(keyword) for keyword in bare_keywords):
            return True

        return False

    def scroll_chat_to_bottom(self):
        """
        Scroll the chat view to the bottom.
        Deferred via QTimer.singleShot(0, ...) because Qt hasn't recalculated the
        scroll area's layout yet immediately after addWidget() - calling
        setValue(maximum()) synchronously scrolls to the *previous* bottom, one
        message behind, which is why new messages required a manual scroll to see.
        """
        QTimer.singleShot(0, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def send_message(self):
        """Send user message with context awareness"""
        text = self.input_box.text().strip()
        if not text:
            return
        
        # Prevent sending if AI is already responding
        if self.thread and self.thread.isRunning():
            return
        
        self._checkin_user_active()
        self._stop_speaking()
        # Add context awareness to message
        context = self.assistant.get_active_window_context()
        message_with_context = f"{context}\n{text}" if context else text
        
        # Create new chat if none exists
        if not self.current_chat_id:
            self.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_chat_messages = []
            
            # Create initial chat file
            chat_name = f"Chat {self.get_chat_count() + 1}"
            chat_data = {
                "id": self.current_chat_id,
                "name": chat_name,
                "created_at": datetime.now().isoformat(),
                "messages": []
            }
            
            chat_file = self.chat_dir / f"{self.current_chat_id}.json"
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
            
            # Increment cache after creating
            self.increment_chat_count()
            
            # Cache metadata
            self._chat_metadata_cache[self.current_chat_id] = {
                "name": chat_name,
                "created_at": chat_data["created_at"]
            }
            
            # Add to sidebar (at the top)
            self._index_chat(self.current_chat_id, chat_name, chat_data["created_at"])
            self.rebuild_chat_list()
        
        # Keep welcome screen/logo visible, just switch to top alignment for messages
        if self.welcome_container and self.welcome_container.parent():
            # Switch to top alignment for messages; keep the intro, drop the suggestion chips
            self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            try:
                self.welcome_prompts.hide()
            except (AttributeError, RuntimeError):
                pass
        
        # Track message in current chat (without context)
        self.current_chat_messages.append({"role": "user", "content": text})
        msg_index = len(self.current_chat_messages) - 1

        # Add user message (align right) - if a photo's attached, show its
        # thumbnail above the text so there's a visible record of what was
        # uploaded once the pre-send attachment chip disappears.
        message_column = QVBoxLayout()
        message_column.setSpacing(6)
        if self.pending_attached_image_path:
            upload_preview = UploadedImagePreview(self.pending_attached_image_path, self)
            upload_row = QHBoxLayout()
            upload_row.addStretch()
            upload_row.addWidget(upload_preview)
            message_column.addLayout(upload_row)

        user_bubble = MessageBubble(text, is_user=True)
        bubble_container = QHBoxLayout()
        bubble_container.addStretch()
        bubble_container.addWidget(user_bubble)
        message_column.addLayout(bubble_container)

        container_widget = QWidget()
        container_widget.setLayout(message_column)
        container_widget._msg_index = msg_index
        user_bubble.on_edit = lambda new_text, cw=container_widget: self.handle_message_edit(cw, new_text)
        self.chat_layout.addWidget(container_widget)

        # Tracked so the AI response that follows can wire up its own
        # "regenerate" button - resubmitting this same user turn is the
        # exact same truncate-and-resend logic as an edit with no text change.
        self._last_user_container_widget = container_widget
        self._last_user_text = text

        self.input_box.clear()
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        self.scroll_chat_to_bottom()
        
        # Add loading bubble (align left like AI messages)
        loading_bubble = LoadingBubble()
        bubble_container = self._ai_row(loading_bubble, f"{AI_NAME} is typing…")
        
        self.loading_bubble_widget = QWidget()
        self.loading_bubble_widget.setLayout(bubble_container)
        self.chat_layout.addWidget(self.loading_bubble_widget)
        
        # Scroll to show loading bubble
        self.scroll_chat_to_bottom()

        # If a photo is attached, this message is an edit instruction for it -
        # takes priority over everything else, including image-gen/chat intent
        # detection, since attaching a photo is an explicit, unambiguous action.
        if self.pending_attached_image_path:
            source_path = self.pending_attached_image_path
            self.clear_attached_image()
            self.start_image_generation(text, source_image_path=source_path)
            return

        # Image generation/editing needs its own async path (seconds-to-a-minute+)
        # and a special inline bubble, so it's checked before both the instant
        # system-command path and the LLM streaming path.
        parsed = self.assistant.parse_natural_language(text)
        if parsed.lower().startswith("generateimage "):
            prompt = parsed[len("generateimage "):].strip()
            if prompt:
                self.start_image_generation(prompt)
                return
        if parsed.lower().startswith("editlast "):
            prompt = parsed[len("editlast "):].strip()
            if prompt and self.assistant.last_generated_image_path:
                self.start_image_generation(prompt, source_image_path=self.assistant.last_generated_image_path)
                return

        # No explicit trigger matched - if an image exists in context, check
        # whether this is actually a natural-language image request/edit
        # ("gimme a pic of a dog", "make the apple more red") via the LLM's
        # tool-calling, before falling through to system-command/chat.
        if self.assistant._image_context_is_fresh():
            intent = self.assistant.classify_image_intent(text)
            if intent and intent["action"] == "generate":
                self.start_image_generation(intent["prompt"])
                return
            elif intent and intent["action"] == "edit":
                self.start_image_generation(intent["change"], source_image_path=self.assistant.last_generated_image_path)
                return

        # Check if this is a system command (handle directly without AI for speed)
        if self.is_system_command(text):
            # Process command directly (instant execution)
            command_result = self.assistant.process_command(text)
            
            # Remove loading bubble
            if self.loading_bubble_widget and self.loading_bubble_widget.parent():
                _lb = self.loading_bubble_widget.findChild(LoadingBubble)
                if _lb:
                    _lb.stop_animation()
                self.loading_bubble_widget.deleteLater()
                self.loading_bubble_widget = None
            
            # Display command result if returned (for help/list commands)
            if command_result:
                self.current_chat_messages.append({"role": "ai", "content": command_result})
                self.save_current_chat()
                self.maybe_generate_chat_title(command_result)

                ai_bubble = MessageBubble(command_result, is_user=False)
                self._wire_regenerate(ai_bubble)
                bubble_container = self._ai_row(ai_bubble)

                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                self.chat_layout.addWidget(container_widget)
                
                self.scroll_chat_to_bottom()
            else:
                # Command was executed but returned nothing
                # Provide context-aware feedback with the assistant personality
                text_lower = text.lower()
                if 'open' in text_lower:
                    ack_message = "Opening."
                elif 'close' in text_lower:
                    ack_message = "Closing."
                elif 'volume' in text_lower or 'brightness' in text_lower:
                    ack_message = "Adjusted."
                elif 'screenshot' in text_lower:
                    ack_message = "Screenshot saved."
                elif any(word in text_lower for word in ['lock', 'sleep', 'restart', 'shutdown']):
                    ack_message = "Executing."
                elif 'shortcut' in text_lower:
                    ack_message = "Done."
                else:
                    ack_message = "Done."
                
                self.current_chat_messages.append({"role": "ai", "content": ack_message})
                self.save_current_chat()
                self.maybe_generate_chat_title(ack_message)

                ai_bubble = MessageBubble(ack_message, is_user=False)
                self._wire_regenerate(ai_bubble)
                bubble_container = self._ai_row(ai_bubble)

                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                self.chat_layout.addWidget(container_widget)
                
                self.scroll_chat_to_bottom()
            
            # Re-enable input
            self.input_box.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_box.setFocus()
            return
        
        # Get AI response with streaming
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(500)
        
        # Pass both message with context and original message (for quick response detection)
        self.thread = AIThread(self.assistant, message_with_context, original_message=text)
        self.thread.response.connect(self.add_ai_message)
        self.thread.chunk.connect(self.handle_ai_chunk)
        self.thread.finished_streaming.connect(self.finalize_ai_message)
        self.thread.finished.connect(self.enable_input)
        self.active_operation = "chat"
        self.set_send_button_mode("stop")
        self.thread.start()

        # Prepare for streaming
        self.streaming_bubble = None
    
    def _wire_regenerate(self, bubble):
        """Attach a 'regenerate this response' callback to an AI MessageBubble."""
        cw = self._last_user_container_widget
        t = self._last_user_text
        if cw is not None and t is not None:
            bubble.on_regenerate = lambda: self.handle_message_edit(cw, t)

    def _wire_regenerate_versioned(self, bubble):
        """
        Attach in-place regeneration to a genuine AI chat-text bubble: unlike
        _wire_regenerate (which truncates and resends the whole turn), this
        keeps the user's message untouched and keeps every past response
        version so the user can flip back if they liked an earlier one better
        - same "‹ 1/2 ›" pattern ChatGPT/Grok use.
        Callers must also set bubble._msg_index once the response text is
        actually appended to current_chat_messages (immediate for the
        non-streaming path, deferred until finalize_ai_message for streaming).
        """
        t = self._last_user_text
        if t is not None:
            bubble.on_regenerate = lambda: self.regenerate_ai_bubble(bubble, t)
            bubble.on_flag_dodge = lambda: self.regenerate_ai_bubble(bubble, t, extra_instruction=self.assistant.DODGE_RETRY_NUDGE)
        bubble.on_version_change = lambda text, b=bubble: self._sync_bubble_version_to_history(b, text)

    def _sync_bubble_version_to_history(self, bubble, text: str):
        idx = getattr(bubble, '_msg_index', None)
        if idx is not None and 0 <= idx < len(self.current_chat_messages):
            self.current_chat_messages[idx]["content"] = text
            self.save_current_chat()

    def regenerate_ai_bubble(self, bubble, user_text: str, extra_instruction: str = ""):
        """Regenerate a chat response in place, keeping prior versions for back/forward nav."""
        if self.active_operation or not user_text:
            return
        self.active_operation = "chat"
        bubble.regen_btn.setEnabled(False)
        bubble.prev_btn.setEnabled(False)
        bubble.next_btn.setEnabled(False)

        context = self.assistant.get_active_window_context()
        message_with_context = f"{context}\n{user_text}" if context else user_text

        self._regen_target_bubble = bubble
        self._regen_accum = ""
        self._regen_thread_obj = AIThread(
            self.assistant, message_with_context, original_message=user_text, extra_instruction=extra_instruction
        )
        self._regen_thread_obj.chunk.connect(self._on_regen_chunk)
        self._regen_thread_obj.finished_streaming.connect(self._on_regen_finished)
        self._regen_thread_obj.response.connect(self._on_regen_error_response)
        self._regen_thread_obj.finished.connect(self._on_regen_thread_done)
        self._regen_thread_obj.start()

    def _on_regen_chunk(self, chunk):
        self._regen_accum += chunk
        if self._regen_target_bubble:
            self._regen_target_bubble.set_text(self._regen_accum)

    def _on_regen_finished(self, full_text):
        bubble = self._regen_target_bubble
        if bubble:
            bubble.add_version(full_text)
            self._sync_bubble_version_to_history(bubble, full_text)

    def _on_regen_error_response(self, text):
        bubble = self._regen_target_bubble
        if bubble:
            bubble.add_version(text)
            self._sync_bubble_version_to_history(bubble, text)

    def _on_regen_thread_done(self):
        bubble = self._regen_target_bubble
        if bubble:
            bubble.regen_btn.setEnabled(True)
            bubble._update_version_nav()
        self._regen_target_bubble = None
        self.active_operation = None

    def open_chat_reader(self):
        self.content_stack.setCurrentIndex(1)
        self.chat_reader_view.show_library()

    def toggle_pinned_panel(self, show=None):
        """show: True to open, False to close, None to toggle the current state."""
        target = (not self.pinned_messages_view.isVisible()) if show is None else show
        if target:
            self.pinned_messages_view.refresh()
        self.pinned_messages_view.setVisible(target)

    def handle_pin_message(self, bubble):
        """Default Pin/Unpin Message handler for every bubble in the live chat (see MessageBubble.default_on_pin)."""
        if not self.assistant:
            return
        if bubble.pin_id:
            self.assistant.unpin_message(bubble.pin_id)
            bubble.set_pinned(None)
            print(f"{self.assistant.name}: Unpinned message.")
            return
        content = getattr(bubble, '_raw_text', None) or bubble.msg_text.toPlainText()
        speaker = "You" if bubble.is_user else AI_NAME
        pin = self.assistant.pin_message(
            content=content,
            speaker=speaker,
            source="live_chat",
            chat_id=self.current_chat_id or "",
        )
        bubble.set_pinned(pin['id'])
        print(f"{self.assistant.name}: Pinned message from {speaker}.")

    def handle_message_edit(self, container_widget, new_text):
        """
        ChatGPT/Grok-style edit: editing a past user message drops it and
        everything after it (its AI reply or generated image), then resends
        the edited text as a fresh message.
        """
        if self.active_operation:
            return  # don't allow editing mid-generation

        index = self.chat_layout.indexOf(container_widget)
        if index == -1:
            return

        msg_index = getattr(container_widget, '_msg_index', None)
        if msg_index is not None:
            self.current_chat_messages = self.current_chat_messages[:msg_index]
            self.save_current_chat()

        while self.chat_layout.count() > index:
            item = self.chat_layout.takeAt(index)
            w = item.widget() if item else None
            if w:
                w.deleteLater()

        self.loading_bubble_widget = None

        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setText(new_text)
        self.send_message()

    def add_ai_message(self, text):
        """Add AI response message (fallback for non-streaming)"""
        # Remove loading bubble if it exists
        if self.loading_bubble_widget and self.loading_bubble_widget.parent():
            # Stop the animation timer
            _lb = self.loading_bubble_widget.findChild(LoadingBubble)
            if _lb:
                _lb.stop_animation()
            self.loading_bubble_widget.deleteLater()
            self.loading_bubble_widget = None
        try:
            # Track message in current chat
            self.current_chat_messages.append({"role": "ai", "content": text})
            self.save_current_chat()  # Auto-save after each AI response
            self.maybe_generate_chat_title(text)
            self.maybe_remember_from_exchange(text)
            ai_bubble = MessageBubble(text, is_user=False)
            self._wire_regenerate_versioned(ai_bubble)
            ai_bubble._msg_index = len(self.current_chat_messages) - 1
        except Exception as e:
            import traceback
            error_msg = f"AI error: {str(e)}\n" + traceback.format_exc()
            # Log error to file
            with open(str(Path(__file__).parent / "freesia_error.log"), "a", encoding="utf-8") as f:
                f.write(error_msg + "\n")
            ai_bubble = MessageBubble("[AI Error] " + str(e), is_user=False)
            self._wire_regenerate(ai_bubble)
        bubble_container = self._ai_row(ai_bubble)
        container_widget = QWidget()
        container_widget.setLayout(bubble_container)
        self.chat_layout.addWidget(container_widget)
        self.scroll_chat_to_bottom()
        self.notify_if_unfocused("FreesIA", text)
        self._speak_reply(text)

    def handle_ai_chunk(self, chunk):
        """Handle streaming AI response chunks"""
        try:
            # Remove loading bubble on first chunk
            if self.loading_bubble_widget and self.loading_bubble_widget.parent():
                _lb = self.loading_bubble_widget.findChild(LoadingBubble)
                if _lb:
                    _lb.stop_animation()
                self.loading_bubble_widget.deleteLater()
                self.loading_bubble_widget = None

            # Create bubble on first chunk
            if not self.streaming_bubble:
                self.streaming_bubble = MessageBubble("", is_user=False)
                self._wire_regenerate_versioned(self.streaming_bubble)
                bubble_container = self._ai_row(self.streaming_bubble)

                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                self.chat_layout.addWidget(container_widget)

            # Append chunk to bubble
            self.streaming_bubble.append_text(chunk)

            self.scroll_chat_to_bottom()
        except Exception as e:
            import traceback
            error_msg = f"[AI Streaming Error] {str(e)}\n" + traceback.format_exc()
            # Log error to file
            with open("freesia_error.log", "a", encoding="utf-8") as f:
                f.write(error_msg + "\n")
            # Show error in chat
            ai_bubble = MessageBubble("[AI Error] " + str(e), is_user=False)
            self._wire_regenerate(ai_bubble)
            bubble_container = self._ai_row(ai_bubble)
            container_widget = QWidget()
            container_widget.setLayout(bubble_container)
            self.chat_layout.addWidget(container_widget)
            self.streaming_bubble = None
            self.scroll_chat_to_bottom()
    
    def finalize_ai_message(self, full_text):
        """Finalize streaming AI message - keep bubble intact with accumulated text."""
        try:
            # Don't overwrite bubble - it already has all the streamed chunks!
            # Just finalize the history tracking
            
            # Track message in current chat (accumulate all chunks)
            self.current_chat_messages.append({"role": "ai", "content": full_text})
            self.save_current_chat()
            self.maybe_generate_chat_title(full_text)
            self.maybe_remember_from_exchange(full_text)

            if self.streaming_bubble:
                self.streaming_bubble.sync_first_version(full_text)
                self.streaming_bubble._msg_index = len(self.current_chat_messages) - 1

            # Reset streaming bubble for next message
            self.streaming_bubble = None

            self.scroll_chat_to_bottom()
            self.notify_if_unfocused("FreesIA", full_text)
            self._speak_reply(full_text)
        except Exception as e:
            import traceback
            error_msg = f"[AI Finalize Error] {str(e)}\n" + traceback.format_exc()
            with open("freesia_error.log", "a", encoding="utf-8") as f:
                f.write(error_msg + "\n")
            ai_bubble = MessageBubble("[AI Error] " + str(e), is_user=False)
            self._wire_regenerate(ai_bubble)
            bubble_container = self._ai_row(ai_bubble)
            container_widget = QWidget()
            container_widget.setLayout(bubble_container)
            self.chat_layout.addWidget(container_widget)
            self.streaming_bubble = None
            self.scroll_chat_to_bottom()
    
    def use_suggested_prompt(self, prompt):
        """Use a suggested prompt"""
        self.input_box.setText(prompt)
        self.send_message()
    
    def load_all_chats(self):
        self._load_chat_index()
        self.rebuild_chat_list()

    # ==================== CHAT ROW / SIDEBAR INDEX ====================

    def refresh_ai_name(self):
        """Update the labels that show the assistant's name after it is renamed."""
        holders = [self] + list(self.findChildren(PinnedMessagesView))
        for h in holders:
            for attr in ("ai_name_label", "ai_title_label"):
                lab = getattr(h, attr, None)
                if isinstance(lab, QLabel):
                    lab.setText(AI_NAME)
        try:
            self.input_box.setPlaceholderText(f"Message {AI_NAME}…  (type 'Help' for commands)")
        except Exception:
            pass

    def _ai_row(self, widget, name=None):
        name = name or AI_NAME
        """Avatar + name above the bubble, the way Character.AI lays out a reply."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addWidget(avatar_label(36), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        nm = QLabel(name)
        nm.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 12.5px; background: transparent; }}")
        col.addWidget(nm)
        col.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft)
        row.addLayout(col)
        row.addStretch()
        return row

    @staticmethod
    def _parse_ts(value, fallback=None):
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=None)
        except Exception:
            return fallback or datetime.now()

    @staticmethod
    def _preview_text(messages):
        for msg in reversed(messages or []):
            text = re.sub(r"\s+", " ", (msg.get("content") or "").replace("```", " ")).strip()
            if text:
                return ("You: " + text if msg.get("role") == "user" else text)[:140]
        return ""

    @staticmethod
    def _search_blob(messages):
        return " ".join((m.get("content") or "") for m in (messages or [])).lower()[:30000]

    def _index_chat(self, chat_id, name, created_at, updated_at=None, preview="", pinned=False, blob=""):
        created = self._parse_ts(created_at)
        self._chat_index[chat_id] = {
            "name": name, "created": created,
            "updated": self._parse_ts(updated_at, created) if updated_at else created,
            "preview": preview, "pinned": bool(pinned), "blob": blob,
        }

    def _load_chat_index(self):
        self._chat_index.clear()
        if not self.chat_dir.exists():
            return
        for chat_file in self.chat_dir.glob("*.json"):
            try:
                with open(chat_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                chat_id = data.get("id", chat_file.stem)
                msgs = data.get("messages", [])
                mtime = datetime.fromtimestamp(chat_file.stat().st_mtime)
                created = self._parse_ts(data.get("created_at"), mtime)
                updated = self._parse_ts(data.get("updated_at"), mtime)
                self._chat_index[chat_id] = {
                    "name": data.get("name", f"Chat {chat_id}"), "created": created, "updated": updated,
                    "preview": self._preview_text(msgs), "pinned": bool(data.get("pinned")),
                    "blob": self._search_blob(msgs),
                }
            except Exception as e:
                print(f"Error loading chat {chat_file}: {e}")

    @staticmethod
    def _date_group(ts):
        days = (datetime.now().date() - ts.date()).days
        if days <= 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        if days <= 7:
            return "Previous 7 days"
        if days <= 30:
            return "Previous 30 days"
        return "Earlier"

    def _sidebar_sections(self):
        """[(heading or None, [chat_id, ...])] for the current search state."""
        q = (self._chat_search or "").strip().lower()
        by_recent = lambda kv: kv[1]["updated"]
        if q:
            hits = [kv for kv in self._chat_index.items() if q in kv[1]["name"].lower() or q in kv[1]["blob"]]
            hits.sort(key=by_recent, reverse=True)
            return [("Results" if hits else "No chats found", [k for k, _ in hits])]
        ordered = sorted(self._chat_index.items(), key=by_recent, reverse=True)
        sections = []
        pinned = [k for k, v in ordered if v["pinned"]]
        if pinned:
            sections.append(("Pinned", pinned))
        groups = {}
        for k, v in ordered:
            if not v["pinned"]:
                groups.setdefault(self._date_group(v["updated"]), []).append(k)
        for heading in ("Today", "Yesterday", "Previous 7 days", "Previous 30 days", "Earlier"):
            if heading in groups:
                sections.append((heading, groups[heading]))
        return sections

    def rebuild_chat_list(self):
        lay = self.chat_history_layout
        if lay is None:
            return
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._chat_item_widgets.clear()
        order = []
        for heading, ids in self._sidebar_sections():
            if heading:
                lab = QLabel(heading)
                lab.setStyleSheet(f"QLabel {{ color: {THEME['text_muted']}; font-size: 12px; background: transparent; padding: 12px 10px 4px 10px; }}")
                lay.addWidget(lab)
            for cid in ids:
                meta = self._chat_index[cid]
                item = ChatHistoryItem(cid, meta["name"], self, preview=meta["preview"], pinned=meta["pinned"])
                lay.addWidget(item)
                self._chat_item_widgets[cid] = item
                order.append(cid)
        self._sidebar_order = order
        self._refresh_active_chat_item()

    def _refresh_active_chat_item(self):
        for cid, item in self._chat_item_widgets.items():
            try:
                item.set_active(cid == self.current_chat_id)
            except RuntimeError:
                pass

    def _apply_chat_search(self):
        self._chat_search = self.chat_search_box.text()
        self.rebuild_chat_list()

    def _after_chat_saved(self):
        """Keep the sidebar preview/order in step with the chat that was just saved."""
        meta = self._chat_index.get(self.current_chat_id)
        if meta is None:
            return
        meta["updated"] = datetime.now()
        meta["preview"] = self._preview_text(self.current_chat_messages)
        meta["blob"] = self._search_blob(self.current_chat_messages)
        item = self._chat_item_widgets.get(self.current_chat_id)
        if item is not None:
            item.set_preview(meta["preview"])
        if not (self._chat_search or "").strip():
            new_order = [cid for _h, ids in self._sidebar_sections() for cid in ids]
            if new_order != self._sidebar_order:
                self.rebuild_chat_list()

    def toggle_pin_chat(self, chat_id):
        meta = self._chat_index.get(chat_id)
        if meta is None:
            return
        meta["pinned"] = not meta["pinned"]
        chat_file = self.chat_dir / f"{chat_id}.json"
        try:
            if chat_file.exists():
                with open(chat_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["pinned"] = meta["pinned"]
                with open(chat_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error pinning chat: {e}")
        self.rebuild_chat_list()

    # ==================== SHORTCUTS / COMMAND PALETTE ====================

    def _install_shortcuts(self):
        self._sc_palette = QShortcut(QKeySequence("Ctrl+K"), self)
        self._sc_palette.activated.connect(self.open_palette)
        self._sc_new_chat = QShortcut(QKeySequence("Ctrl+N"), self)
        self._sc_new_chat.activated.connect(self.create_new_chat)

    def palette_items(self):
        items = []
        def add(section, title, action, icon, desc="", keywords="", text=""):
            items.append({"section": section, "title": title, "desc": desc, "icon": icon,
                          "keywords": keywords, "text": text, "action": action})
        add("Actions", "New chat", self.create_new_chat, "plus", "Ctrl N", "start conversation")
        add("Actions", "Toggle sidebar", self.toggle_sidebar, "panel-left", "", "hide show history")
        add("Actions", "Toggle info panel", lambda: self.toggle_pinned_panel(), "panel-right", "", "pinned messages right panel")
        add("Actions", "Open Chat Reader", self.open_chat_reader, "book", "", "archive imported character ai")
        add("Actions", "Open image gallery", self.open_gallery, "image", "", "pictures images stars photos drawn")
        add("Actions", "Open Settings", lambda: self.show_settings(), "settings", "", "preferences options")
        for cid, meta in sorted(self._chat_index.items(), key=lambda kv: kv[1]["updated"], reverse=True):
            add("Chats", meta["name"], lambda c=cid: self.load_chat(c), "pin" if meta["pinned"] else "message",
                self._date_group(meta["updated"]), "", meta["blob"][:3000])
        shortcuts = getattr(self.assistant, "custom_shortcuts", None)
        if isinstance(shortcuts, dict):
            for name, actions in shortcuts.items():
                add("Shortcuts", f'Run "{name}"', lambda n=name: self.use_suggested_prompt(n), "bolt",
                    " → ".join(actions) if isinstance(actions, (list, tuple)) else "", name)
        for title, page, kw in SETTINGS_INDEX:
            add("Settings", title, lambda pg=page: self.show_settings(pg), "settings", page, kw)
        return items

    def open_palette(self):
        CommandPalette(self, self.palette_items()).exec()

    # ==================== STATUS LIGHT ====================

    def _status_info(self):
        green, amber, red = "#5FB878", "#E0B15A", "#E5604F"
        if self.active_operation == "chat":
            return amber, "Thinking…", f"{AI_NAME} is working on a reply"
        if self.active_operation == "image":
            return amber, "Drawing…", "Generating an image"
        a = self.assistant
        st = getattr(a, "ollama_status", "unknown")
        st = st if isinstance(st, str) else "unknown"
        model = getattr(a, "ollama_model", "")
        model = model if isinstance(model, str) else ""
        if st == "ready":
            return green, f"Online · {model}" if model else "Online", "Ollama is connected"
        if st == "model_missing":
            return amber, "Model missing · click to fix", "The chat model isn't installed in Ollama"
        if st == "offline":
            err = getattr(a, "ollama_error", "")
            return red, "Ollama offline · click to retry", err if isinstance(err, str) and err else "Couldn't reach Ollama"
        return THEME['text_muted'], "Checking…", "Looking for Ollama"

    def _refresh_status(self):
        try:
            color, text, tip = self._status_info()
            self.status_label.setText(f'<span style="color:{color}; font-size:10px;">●</span>&nbsp;&nbsp;{text}')
            self.status_label.setToolTip(tip)
        except RuntimeError:
            pass

    def _start_status_retry(self):
        if self._status_retry is not None and self._status_retry.isRunning():
            return
        if self.assistant is None:
            return
        self._status_retry = OllamaRetryThread(self.assistant)
        self._status_retry.done.connect(self._refresh_status)
        self._status_retry.start()

    def _status_tick(self):
        self._refresh_status()
        self._status_ticks += 1
        st = getattr(self.assistant, "ollama_status", "unknown")
        if self._status_ticks % 5 == 0 and st in ("offline", "unknown") and not self.active_operation:
            self._start_status_retry()

    def _on_status_clicked(self):
        st = getattr(self.assistant, "ollama_status", "unknown")
        if st == "model_missing":
            self.show_settings("Models")
        elif st == "ready":
            self.show_settings("Models")
        elif not self.active_operation:
            self.status_label.setText(f'<span style="color:{THEME["text_muted"]}; font-size:10px;">●</span>&nbsp;&nbsp;Connecting…')
            self._start_status_retry()


    # ==================== SIDEBAR TOGGLE ====================
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility with animation"""
        # Stop any ongoing animation
        if self.sidebar_animation and self.sidebar_animation.state() == QPropertyAnimation.State.Running:
            self.sidebar_animation.stop()
        
        # Create animation
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_animation.setDuration(200)  # 200ms for smooth animation
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        if self.sidebar_visible:
            # Collapse sidebar - release the pinned minimumWidth from any
            # prior drag first, otherwise it fights the animation shrinking
            # maximumWidth below it and the sidebar won't actually collapse.
            self.sidebar.setMinimumWidth(0)
            self.sidebar_animation.setStartValue(self.sidebar_width)
            self.sidebar_animation.setEndValue(0)
            self.sidebar_animation.finished.connect(lambda: self.sidebar.setVisible(False))
            self.collapse_btn.hide()
            self.expand_btn.show()
            self.sidebar_resize_handle.hide()
            self.sidebar_visible = False
        else:
            # Expand sidebar
            self.sidebar.setVisible(True)
            self.sidebar_animation.setStartValue(0)
            self.sidebar_animation.setEndValue(self.sidebar_width)
            self.sidebar_animation.finished.connect(lambda: self.sidebar.setMinimumWidth(self.sidebar_width))
            self.collapse_btn.show()
            self.expand_btn.hide()
            self.sidebar_resize_handle.show()
            self.sidebar_visible = True

        self.sidebar_animation.start()
    
    # ==================== CHAT OPERATIONS ====================
    
    def create_new_chat(self):
        """Create a new chat"""
        # Prevent creating new chat while AI is responding
        if self.thread and self.thread.isRunning():
            return
        
        # Save current chat if exists
        if self.current_chat_id and self.current_chat_messages:
            self.save_current_chat()
        
        # Generate new chat ID using Chat_N format for readable filenames
        chat_number = self.get_chat_count() + 1
        self.current_chat_id = f"Chat_{chat_number}"
        self.current_chat_messages = []
        
        # Clear the chat area
        self.new_chat()
        
        # Create initial chat file
        chat_name = f"Chat {chat_number}"
        chat_data = {
            "id": self.current_chat_id,
            "name": chat_name,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }
        
        chat_file = self.chat_dir / f"{self.current_chat_id}.json"
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
        
        # Increment cache after creating
        self.increment_chat_count()
        
        # Cache metadata
        self._chat_metadata_cache[self.current_chat_id] = {
            "name": chat_name,
            "created_at": chat_data["created_at"]
        }
        
        # Add to sidebar (at the top)
        self._index_chat(self.current_chat_id, chat_name, chat_data["created_at"])
        self.rebuild_chat_list()
    
    def load_chat(self, chat_id):
        """Load a specific chat by ID"""
        # Prevent loading chat while AI is responding
        if self.thread and self.thread.isRunning():
            return
        
        # Save current chat first
        if self.current_chat_id and self.current_chat_messages:
            self.save_current_chat()
        
        chat_file = self.chat_dir / f"{chat_id}.json"
        if not chat_file.exists():
            return
        
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            self.current_chat_id = chat_id
            self.current_chat_messages = chat_data.get("messages", [])
            self._refresh_active_chat_item()
            
            # Clear chat area
            while self.chat_layout.count():
                child = self.chat_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # If no messages, show welcome screen
            if not self.current_chat_messages:
                self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.welcome_container = self._build_welcome()
                self.chat_layout.addWidget(self.welcome_container)
            else:
                # Display all messages
                self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                
                for msg in self.current_chat_messages:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        bubble = MessageBubble(content, is_user=True)
                        bubble_container = QHBoxLayout()
                        bubble_container.addStretch()
                        bubble_container.addWidget(bubble)
                    else:  # AI message
                        bubble = MessageBubble(content, is_user=False)
                        bubble_container = self._ai_row(bubble)

                    if self.assistant:
                        speaker = "You" if role == "user" else AI_NAME
                        pin_id = self.assistant.find_pin_id(self.current_chat_id, content, speaker)
                        if pin_id:
                            bubble.set_pinned(pin_id)

                    container_widget = QWidget()
                    container_widget.setLayout(bubble_container)
                    self.chat_layout.addWidget(container_widget)
                
                self.scroll_chat_to_bottom()
        
        except Exception as e:
            print(f"Error loading chat {chat_id}: {e}")
    
    def maybe_generate_chat_title(self, first_response: str = ""):
        """
        Kick off an auto-title once the opening exchange (first user message +
        first response) has landed, like ChatGPT/Claude/Grok do. Only fires
        once per chat, right after that first pair, while the chat still has
        its default "Chat N" name.
        """
        if not self.current_chat_id or len(self.current_chat_messages) != 2:
            return
        meta = self._chat_metadata_cache.get(self.current_chat_id)
        if meta and not re.match(r'^Chat \d+$', meta.get("name", "")):
            return  # already renamed (manually or auto) - don't overwrite
        first_message = self.current_chat_messages[0].get("content", "")
        if not first_message:
            return
        self._title_thread = ChatTitleThread(self.assistant, self.current_chat_id, first_message, first_response)
        self._title_thread.finished.connect(self.on_chat_title_generated)
        self._title_thread.start()

    def on_chat_title_generated(self, chat_id: str, title: str):
        self.rename_chat(chat_id, title)
        chat_item = self._chat_item_widgets.get(chat_id)
        if chat_item:
            chat_item.chat_name = title
            chat_item.name_btn.set_full_text(title)

    def maybe_remember_from_exchange(self, ai_response: str):
        """
        Fire-and-forget check of the just-completed exchange for a fact worth
        remembering across future chats (name, preference, ongoing project...).
        Runs off the UI thread so it never delays the visible response.
        """
        user_text = self._last_user_text
        if not user_text or not ai_response:
            return
        self._memory_thread = MemoryExtractThread(self.assistant, user_text, ai_response)
        self._memory_thread.start()

    def save_current_chat(self):
        """Save the current chat to file"""
        if not self.current_chat_id:
            return
        
        chat_file = self.chat_dir / f"{self.current_chat_id}.json"
        
        try:
            # Use cached metadata if available
            if self.current_chat_id in self._chat_metadata_cache:
                chat_data = {
                    "id": self.current_chat_id,
                    "name": self._chat_metadata_cache[self.current_chat_id]["name"],
                    "created_at": self._chat_metadata_cache[self.current_chat_id]["created_at"]
                }
            else:
                # Load from file if not cached
                if chat_file.exists():
                    with open(chat_file, 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                else:
                    chat_data = {
                        "id": self.current_chat_id,
                        "name": f"Chat {self.get_chat_count()}",
                        "created_at": datetime.now().isoformat()
                    }
                
                # Cache it for next time
                self._chat_metadata_cache[self.current_chat_id] = {
                    "name": chat_data["name"],
                    "created_at": chat_data["created_at"]
                }
            
            # Update messages
            chat_data["messages"] = self.current_chat_messages
            chat_data["updated_at"] = datetime.now().isoformat()
            _meta = self._chat_index.get(self.current_chat_id)
            if _meta is not None:
                chat_data["pinned"] = bool(_meta.get("pinned"))
            
            # Save to file
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
            self._after_chat_saved()
        
        except Exception as e:
            print(f"Error saving chat: {e}")
    
    def rename_chat(self, chat_id, new_name):
        """Rename a chat"""
        chat_file = self.chat_dir / f"{chat_id}.json"
        if not chat_file.exists():
            return
        
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            chat_data["name"] = new_name
            
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
            
            # Update cache
            if chat_id in self._chat_metadata_cache:
                self._chat_metadata_cache[chat_id]["name"] = new_name
            if chat_id in self._chat_index:
                self._chat_index[chat_id]["name"] = new_name
        
        except Exception as e:
            print(f"Error renaming chat: {e}")
    
    def delete_chat(self, chat_id):
        """Delete a chat"""
        chat_file = self.chat_dir / f"{chat_id}.json"
        
        try:
            if chat_file.exists():
                chat_file.unlink()
            
            # Decrement chat count cache
            self.decrement_chat_count()
            
            # Remove from metadata cache
            if chat_id in self._chat_metadata_cache:
                del self._chat_metadata_cache[chat_id]
            self._chat_item_widgets.pop(chat_id, None)

            # Remove from sidebar
            self._chat_index.pop(chat_id, None)
            self.rebuild_chat_list()
            
            # If this was the current chat, start a new one
            if self.current_chat_id == chat_id:
                self.create_new_chat()
        
        except Exception as e:
            print(f"Error deleting chat: {e}")
    
    # ==================== LIVE THEME SWITCH ====================

    def request_theme_switch(self, dark: bool) -> bool:
        """Rebuild the window in the new theme without restarting. Returns False
        (setting is still saved for next launch) if a reply/image is in progress."""
        busy = (self.thread is not None and self.thread.isRunning()) or self.active_operation
        if busy:
            return False
        QTimer.singleShot(0, lambda: self._switch_theme(dark))
        return True

    def _switch_theme(self, dark: bool):
        global THEME
        THEME = DARK_THEME if dark else LIGHT_THEME
        _ICON_CACHE.clear()
        chat_id = self.current_chat_id
        if chat_id and self.current_chat_messages:
            self.save_current_chat()
        geo = self.geometry()
        maximized = self.isMaximized()
        new_window = MainWindow(self.assistant)
        new_window.setGeometry(geo)
        if maximized:
            new_window.showMaximized()
        else:
            new_window.show()
        app = QApplication.instance()
        app._freesia_main_window = new_window  # keep a reference so it isn't garbage collected
        if not hasattr(app, '_freesia_old_windows'):
            app._freesia_old_windows = []
        app._freesia_old_windows.append(self)  # old window may still own finishing background threads
        if chat_id and (self.chat_dir / f"{chat_id}.json").exists():
            new_window.load_chat(chat_id)
        if self.tray_icon:
            self.tray_icon.setVisible(False)
        self.hide()
        QTimer.singleShot(50, lambda: new_window.show_settings("General"))

    # ==================== SETTINGS DIALOG ====================
    
    def show_settings(self, initial_page="General"):
        """Show settings dialog with dimmed background"""
        # Update overlay size and show it
        self.overlay.setGeometry(self.centralWidget().rect())
        self.overlay.show()
        self.overlay.raise_()

        settings_dialog = SettingsDialog(self, initial_page=initial_page)
        # Center the dialog on the main window
        parent_center = self.rect().center()
        dialog_rect = settings_dialog.rect()
        dialog_rect.moveCenter(parent_center)
        settings_dialog.move(self.mapToGlobal(dialog_rect.topLeft()))
        
        # Show dialog and hide overlay when done
        settings_dialog.exec()
        self.overlay.hide()
    
    # ==================== UTILITY METHODS ====================

    # ==================== CHECK-INS ====================

    def _init_checkins(self):
        self._ci_thread = None
        self._ci_last_activity = _time.time()
        self._ci_next_due = None
        self._checkin_reschedule(first=True)
        self._ci_timer = QTimer(self)
        self._ci_timer.setInterval(60000)
        self._ci_timer.timeout.connect(self._checkin_tick)
        self._ci_timer.start()

    def _checkin_reschedule(self, first=False):
        cfg = load_checkin_cfg()
        base = CHECKIN_MINUTES[cfg["frequency"]] * 60
        lo, hi = (0.5, 1.0) if first else (0.7, 1.3)
        self._ci_next_due = _time.time() + base * _random.uniform(lo, hi)

    def _ci_busy(self):
        return bool(self.active_operation or (self.thread and self.thread.isRunning())
                    or (self._ci_thread and self._ci_thread.isRunning()))

    def _checkin_tick(self):
        cfg = load_checkin_cfg()
        if not cfg["enabled"] or self._ci_next_due is None or _time.time() < self._ci_next_due:
            return
        if in_quiet_hours(datetime.now(), cfg["quiet_start"], cfg["quiet_end"]):
            return
        if cfg["unanswered"] >= 2 or self._ci_busy():
            return
        if _time.time() - self._ci_last_activity < CHECKIN_IDLE_MIN * 60:
            return
        if cfg["hold_fullscreen"] and fullscreen_app_running(int(self.winId())):
            return
        self.start_checkin(force=False)

    def start_checkin(self, force=False) -> bool:
        if self._ci_busy():
            return False
        recent = "\n".join(
            f"{'User' if m.get('role') == 'user' else AI_NAME}: {(m.get('content') or '')[:200]}"
            for m in (self.current_chat_messages or [])[-6:])
        now = datetime.now()
        part = ("late night" if now.hour < 5 else "morning" if now.hour < 12 else "afternoon" if now.hour < 17
                else "evening" if now.hour < 22 else "night")
        when = f"{now.strftime('%A, %I:%M %p').replace(' 0', ' ')} ({part})"
        self._ci_thread = CheckinThread(self.assistant, recent, when)
        self._ci_thread.done.connect(lambda text, f=force: self._deliver_checkin(text, f))
        self._ci_thread.start()
        return True

    def _deliver_checkin(self, text, force=False):
        self._checkin_reschedule()
        if self.active_operation or (self.thread and self.thread.isRunning()):
            return  # you started talking while it was writing - drop it
        if not self.current_chat_id:
            self.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_chat_messages = []
            chat_name = f"Chat {self.get_chat_count() + 1}"
            created = datetime.now().isoformat()
            with open(self.chat_dir / f"{self.current_chat_id}.json", 'w', encoding='utf-8') as f:
                json.dump({"id": self.current_chat_id, "name": chat_name, "created_at": created, "messages": []},
                          f, indent=2, ensure_ascii=False)
            self.increment_chat_count()
            self._chat_metadata_cache[self.current_chat_id] = {"name": chat_name, "created_at": created}
            self._index_chat(self.current_chat_id, chat_name, created)
            self.rebuild_chat_list()
        if self.welcome_container and self.welcome_container.parent():
            self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            try:
                self.welcome_prompts.hide()
            except (AttributeError, RuntimeError):
                pass
        self.current_chat_messages.append({"role": "ai", "content": text})
        self.save_current_chat()
        bubble = MessageBubble(text, is_user=False)
        bubble._msg_index = len(self.current_chat_messages) - 1
        container = QWidget()
        container.setLayout(self._ai_row(bubble))
        self.chat_layout.addWidget(container)
        self.scroll_chat_to_bottom()
        cfg = load_checkin_cfg()
        if not force:
            cfg["unanswered"] += 1
            save_checkin_cfg(cfg)
        if cfg["notify"]:
            self.notify_if_unfocused(AI_NAME, text)
        self._speak_reply(text)

    def _speak_reply(self, text):
        try:
            self.assistant.speak_reply(text)
        except Exception:
            pass

    def _stop_speaking(self):
        try:
            self.assistant.stop_speaking()
        except Exception:
            pass

    def _checkin_user_active(self):
        self._ci_last_activity = _time.time()
        cfg = load_checkin_cfg()
        if cfg["unanswered"]:
            cfg["unanswered"] = 0
            save_checkin_cfg(cfg)

    def notify_if_unfocused(self, title: str, message: str):
        """Desktop toast for a finished response/image if the window isn't the active one."""
        if not self.tray_icon or self.isActiveWindow():
            return
        preview = message if len(message) <= 150 else message[:147] + "..."
        self.tray_icon.showMessage(title, preview, QSystemTrayIcon.MessageIcon.Information, 5000)

    def enable_input(self):
        """Re-enable input after response"""
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setFocus()
        self.active_operation = None
        self.set_send_button_mode("send")

    def set_send_button_mode(self, mode: str):
        """Toggle the send button between its normal send icon and a stop icon
        while a chat response or image generation is in progress - matches the
        stop-button pattern ChatGPT/Grok use during generation."""
        if mode == "stop":
            self.send_btn.setIcon(line_icon("stop", THEME['bg_primary'], 20))
            self.send_btn.setText("")
            self.send_btn.setToolTip("Stop")
        else:
            self.send_btn.setIcon(self._send_icon)
            self.send_btn.setText("")
            self.send_btn.setToolTip("Send")

    def on_send_button_clicked(self):
        """Single click handler for the send/stop button - dispatches based on
        whether something is currently running."""
        if self.active_operation == "chat":
            self.cancel_chat_response()
        elif self.active_operation == "image":
            self.cancel_image_generation()
        else:
            self.send_message()

    def cancel_chat_response(self):
        """Stop an in-progress streamed chat response, keeping whatever text
        already streamed in (matches ChatGPT/Grok - partial text stays, it just
        stops there) rather than discarding it."""
        partial_text = ""
        if self.streaming_bubble:
            partial_text = self.streaming_bubble.msg_text.toPlainText()
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(500)
            if self.thread.isRunning():
                self.thread.terminate()
        if self.streaming_bubble and partial_text:
            # Save whatever was already shown so history/state stay consistent
            self.finalize_ai_message(partial_text)
        self.enable_input()

    def cancel_image_generation(self):
        """
        Abandon an in-progress image generation/edit. FastSD CPU's API has no
        cancel endpoint (checked the source - only one POST route exists), so
        the actual backend request can't be told to stop; this discards our
        side of it immediately rather than waiting out the ~1-2 minute call.
        """
        if self._image_gen_thread and self._image_gen_thread.isRunning():
            self._image_gen_thread.terminate()
            self._image_gen_thread.wait(1000)

        if self.loading_bubble_widget and self.loading_bubble_widget.parent():
            _lb = self.loading_bubble_widget.findChild(LoadingBubble)
            if _lb:
                _lb.stop_animation()
            self.loading_bubble_widget.deleteLater()
            self.loading_bubble_widget = None

        message = "Cancelled."
        self.current_chat_messages.append({"role": "ai", "content": message})
        self.save_current_chat()
        bubble = MessageBubble(message, is_user=False)
        bubble_container = self._ai_row(bubble)
        container_widget = QWidget()
        container_widget.setLayout(bubble_container)
        self.chat_layout.addWidget(container_widget)
        self.scroll_chat_to_bottom()

        self.enable_input()

    def resizeEvent(self, event):
        """Handle window resize to update overlay size"""
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(self.centralWidget().rect())


# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

_CRASH_LOG = None


def enable_crash_log():
    """Hard crashes (native code) leave nothing in freesia_error.log; this writes a Python stack to ~/.freesia/crash.log."""
    global _CRASH_LOG
    try:
        import faulthandler
        p = Path.home() / ".freesia" / "crash.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        _CRASH_LOG = open(p, "a", buffering=1)
        _CRASH_LOG.write(f"\n--- FreesIA started {datetime.now().isoformat()} ---\n")
        faulthandler.enable(file=_CRASH_LOG, all_threads=True)
    except Exception:
        pass


def main():
    enable_crash_log()
    app = QApplication(sys.argv)
    
    # Set app-wide font
    font = QFont("Inter", 10)
    app.setFont(font)
    
    # Show splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    
    # Load FreesIA in background
    main_window = None
    
    def on_loading_finished(assistant):
        nonlocal main_window
        if assistant:
            # Create and show main window
            apply_model_overrides(assistant)
            main_window = MainWindow(assistant)
            main_window.show()
            splash.close()
        else:
            splash.update_status("Failed to load. Please restart.")
    
    def on_progress(status):
        splash.update_status(status)
    
    # Start loading
    loader = LoadingThread()
    loader.finished.connect(on_loading_finished)
    loader.progress.connect(on_progress)
    loader.start()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
