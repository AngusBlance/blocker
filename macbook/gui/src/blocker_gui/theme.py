"""Colours and stylesheet. Same palette as the TUI (Textual's dark theme) and
the Android app: near-black panels, square borders, orange accent."""

BG = "#121212"
SURFACE = "#1e1e1e"
PANEL = "#24272b"
FG = "#e0e0e0"
MUTED = "#8b8b8b"
BORDER = "#3a3a3a"
ACCENT = "#ffa62b"
ERROR = "#ba3c5b"
SUCCESS = "#4ebf71"

MONO = "Menlo, 'SF Mono', Consolas, 'DejaVu Sans Mono', monospace"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {FG};
    font-size: 14px;
}}
QLabel {{
    background: transparent;
}}

#sidebar {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
#brand {{
    font-family: {MONO};
    font-size: 18px;
    font-weight: 700;
}}
#nav QPushButton {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    color: {MUTED};
    font-family: {MONO};
    font-size: 14px;
    padding: 12px 16px;
    text-align: left;
}}
#nav QPushButton:hover {{
    color: {FG};
    background: {PANEL};
}}
#nav QPushButton:checked {{
    color: {ACCENT};
    border-left: 3px solid {ACCENT};
    background: {BG};
    font-weight: 700;
}}

QLabel[role="heading"] {{
    font-family: {MONO};
    font-size: 12px;
    font-weight: 700;
    color: {MUTED};
}}
QLabel[role="muted"] {{
    color: {MUTED};
}}
QLabel[role="mono"] {{
    font-family: {MONO};
}}

QFrame[role="card"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
}}
QFrame[role="card"][blocked="true"] {{
    border: 1px solid {ACCENT};
}}
QFrame[role="card"] QWidget, #status-card QWidget, #sidebar QWidget {{
    background: transparent;
}}
#status-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
}}
#status-card[blocked="true"] {{
    border: 1px solid {ACCENT};
}}
#big-state {{
    font-family: {MONO};
    font-size: 44px;
    font-weight: 800;
}}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    color: {FG};
    font-family: {MONO};
    font-weight: 700;
    padding: 12px 20px;
}}
QPushButton:hover {{
    border-color: {MUTED};
}}
QPushButton:disabled {{
    color: {BORDER};
    border-color: {BORDER};
}}
QPushButton[role="primary"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: {BG};
}}
QPushButton[role="primary"]:hover {{
    background: #ffb84f;
}}
QPushButton[role="primary"]:disabled {{
    background: {PANEL};
    border-color: {PANEL};
    color: {MUTED};
}}

QPushButton#tile {{
    background: {SURFACE};
    color: {MUTED};
    font-size: 15px;
    padding: 0;
}}
QPushButton#tile[blocked="true"] {{
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}
QPushButton#tile:hover {{
    border-color: {FG};
}}

QLineEdit {{
    background: {BG};
    border: 1px solid {BORDER};
    color: {FG};
    font-family: {MONO};
    padding: 10px;
    selection-background-color: {ACCENT};
    selection-color: {BG};
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QScrollArea {{
    border: none;
}}
QScrollBar:vertical {{
    background: {BG};
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}

QDialog {{
    background: {SURFACE};
}}
QDialog QWidget {{
    background: {SURFACE};
}}
QDialog QLineEdit {{
    background: {BG};
}}
#password-box {{
    background: {PANEL};
    font-family: {MONO};
    font-size: 13px;
    padding: 12px;
}}

#toast {{
    background: {PANEL};
    border: 1px solid {BORDER};
    font-family: {MONO};
    padding: 10px 16px;
}}
#toast[tone="error"] {{
    border-color: {ERROR};
    color: {ERROR};
}}
#toast[tone="ok"] {{
    border-color: {ACCENT};
}}
"""
