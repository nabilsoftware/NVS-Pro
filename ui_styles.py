"""
Professional Studio Theme for Nabil Video Studio Pro
Dark theme inspired by Adobe Premiere / DaVinci Resolve
Supports multiple color themes: Orange, Blue, Green
"""

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor, QFont

# =============================================================================
# THEME DEFINITIONS
# =============================================================================

THEMES = {
    "orange": {
        "name": "Orange (DaVinci)",
        "accent_primary": "#E85D04",
        "accent_secondary": "#F39C12",
        "accent_hover": "#FF6B1A",
        "accent_gradient_start": "#D35400",
        "accent_gradient_end": "#F39C12",
    },
    "blue": {
        "name": "Blue (Professional)",
        "accent_primary": "#0078D4",
        "accent_secondary": "#1A8CFF",
        "accent_hover": "#2997FF",
        "accent_gradient_start": "#0066B8",
        "accent_gradient_end": "#1A8CFF",
    },
    "green": {
        "name": "Green (Modern)",
        "accent_primary": "#10B981",
        "accent_secondary": "#34D399",
        "accent_hover": "#4ADE80",
        "accent_gradient_start": "#059669",
        "accent_gradient_end": "#34D399",
    },
}

# Current active theme (default: orange)
_current_theme = "orange"

def get_current_theme():
    """Get the current theme name"""
    return _current_theme

def set_current_theme(theme_name: str):
    """Set the current theme"""
    global _current_theme
    if theme_name in THEMES:
        _current_theme = theme_name
        _update_colors()

def get_theme_colors():
    """Get colors for the current theme"""
    return THEMES.get(_current_theme, THEMES["orange"])

def _update_colors():
    """Update the COLORS dict based on current theme"""
    theme = get_theme_colors()
    COLORS['accent_primary'] = theme['accent_primary']
    COLORS['accent_secondary'] = theme['accent_secondary']
    COLORS['border_accent'] = theme['accent_primary']


def apply_theme_live(app: QApplication = None):
    """Apply theme changes live without restart.
    Call this after set_current_theme() to update the entire UI.
    Returns the new stylesheet string.
    """
    _update_colors()

    # Get application if not provided
    if app is None:
        app = QApplication.instance()

    if app:
        # Re-apply the pro theme with updated colors
        apply_pro_theme(app)

    return True

# Color Palette - Dark Theme with configurable accent
COLORS = {
    # Backgrounds
    'bg_darkest': '#010409',
    'bg_dark': '#0d1117',
    'bg_medium': '#161b22',
    'bg_light': '#21262d',
    'bg_hover': '#30363d',

    # Accent Colors (will be updated based on theme)
    'accent_primary': '#E85D04',      # Default Orange
    'accent_secondary': '#F39C12',
    'accent_success': '#238636',
    'accent_warning': '#9e6a03',
    'accent_error': '#da3633',
    'accent_info': '#58a6ff',

    # Text Colors
    'text_primary': '#e6edf3',
    'text_secondary': '#8b949e',
    'text_disabled': '#484f58',
    'text_terminal': '#3fb950',

    # Border Colors
    'border_dark': '#30363d',
    'border_light': '#484f58',
    'border_accent': '#E85D04',

    # Special
    'card_bg': '#161b22',
    'input_bg': '#21262d',
    'button_bg': '#21262d',
}


def get_accent_color() -> str:
    """Get the primary accent color for current theme"""
    theme = get_theme_colors()
    return theme.get('accent_primary', '#E85D04')


def get_accent_secondary() -> str:
    """Get the secondary accent color for current theme"""
    theme = get_theme_colors()
    return theme.get('accent_secondary', '#F39C12')


def get_accent_hover() -> str:
    """Get the hover accent color for current theme"""
    theme = get_theme_colors()
    return theme.get('accent_hover', '#FF6B1A')


def get_accent_gradient() -> tuple:
    """Get gradient colors for current theme (start, end)"""
    theme = get_theme_colors()
    return (
        theme.get('accent_gradient_start', '#D35400'),
        theme.get('accent_gradient_end', '#F39C12')
    )


def apply_pro_theme(app: QApplication):
    """Apply professional dark studio theme to the application"""

    # Set application-wide font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Main stylesheet
    stylesheet = f"""
    /* ===== MAIN WINDOW ===== */
    QMainWindow {{
        background-color: {COLORS['bg_dark']};
        color: {COLORS['text_primary']};
    }}

    QWidget {{
        background-color: {COLORS['bg_dark']};
        color: {COLORS['text_primary']};
        font-family: "Segoe UI", Arial, sans-serif;
    }}

    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        border: 1px solid {COLORS['border_dark']};
        background-color: {COLORS['bg_medium']};
        border-radius: 4px;
    }}

    QTabBar::tab {{
        background-color: {COLORS['bg_light']};
        color: {COLORS['text_secondary']};
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        font-weight: bold;
    }}

    QTabBar::tab:selected {{
        background-color: {COLORS['accent_primary']};
        color: {COLORS['text_primary']};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {COLORS['bg_hover']};
        color: {COLORS['text_primary']};
    }}

    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {COLORS['button_bg']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border_light']};
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }}

    QPushButton:hover {{
        background-color: {COLORS['bg_hover']};
        border-color: {COLORS['accent_primary']};
    }}

    QPushButton:pressed {{
        background-color: {COLORS['accent_primary']};
    }}

    QPushButton:disabled {{
        background-color: {COLORS['bg_light']};
        color: {COLORS['text_disabled']};
        border-color: {COLORS['border_dark']};
    }}

    /* Primary Action Buttons */
    QPushButton[class="primary"] {{
        background-color: {COLORS['accent_primary']};
        color: {COLORS['text_primary']};
        border: none;
    }}

    QPushButton[class="primary"]:hover {{
        background-color: {COLORS['accent_secondary']};
    }}

    /* Success Buttons */
    QPushButton[class="success"] {{
        background-color: {COLORS['accent_success']};
        color: {COLORS['text_primary']};
        border: none;
    }}

    /* Danger Buttons */
    QPushButton[class="danger"] {{
        background-color: {COLORS['accent_error']};
        color: {COLORS['text_primary']};
        border: none;
    }}

    /* ===== INPUT FIELDS ===== */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {COLORS['input_bg']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border_dark']};
        border-radius: 4px;
        padding: 6px;
        selection-background-color: {COLORS['accent_primary']};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {COLORS['accent_primary']};
    }}

    QLineEdit:disabled, QTextEdit:disabled {{
        background-color: {COLORS['bg_light']};
        color: {COLORS['text_disabled']};
    }}

    /* ===== COMBO BOX ===== */
    QComboBox {{
        background-color: {COLORS['input_bg']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border_dark']};
        border-radius: 4px;
        padding: 6px;
        min-width: 100px;
    }}

    QComboBox:hover {{
        border-color: {COLORS['accent_primary']};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 30px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {COLORS['text_secondary']};
        margin-right: 10px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border_light']};
        selection-background-color: {COLORS['accent_primary']};
    }}

    /* ===== CHECKBOX & RADIO ===== */
    QCheckBox, QRadioButton {{
        color: {COLORS['text_primary']};
        spacing: 8px;
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {COLORS['border_light']};
        border-radius: 3px;
        background-color: {COLORS['input_bg']};
    }}

    QCheckBox::indicator:checked {{
        background-color: {COLORS['accent_primary']};
        border-color: {COLORS['accent_primary']};
    }}

    QRadioButton::indicator {{
        border-radius: 9px;
    }}

    QRadioButton::indicator:checked {{
        background-color: {COLORS['accent_primary']};
        border-color: {COLORS['accent_primary']};
    }}

    /* ===== GROUP BOX ===== */
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {COLORS['border_dark']};
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 12px;
        background-color: {COLORS['bg_medium']};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: {COLORS['accent_primary']};
    }}

    /* ===== SCROLL BARS ===== */
    QScrollBar:vertical {{
        background-color: {COLORS['bg_dark']};
        width: 12px;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {COLORS['bg_hover']};
        border-radius: 6px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS['accent_primary']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: {COLORS['bg_dark']};
        height: 12px;
        border-radius: 6px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {COLORS['bg_hover']};
        border-radius: 6px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS['accent_primary']};
    }}

    /* ===== LIST WIDGET ===== */
    QListWidget {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['border_dark']};
        border-radius: 4px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {COLORS['border_dark']};
    }}

    QListWidget::item:selected {{
        background-color: {COLORS['accent_primary']};
        color: {COLORS['text_primary']};
    }}

    QListWidget::item:hover:!selected {{
        background-color: {COLORS['bg_hover']};
    }}

    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {COLORS['bg_light']};
        border: none;
        border-radius: 4px;
        text-align: center;
        color: {COLORS['text_primary']};
    }}

    QProgressBar::chunk {{
        background-color: {COLORS['accent_primary']};
        border-radius: 4px;
    }}

    /* ===== SLIDER ===== */
    QSlider::groove:horizontal {{
        background-color: {COLORS['bg_light']};
        height: 6px;
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background-color: {COLORS['accent_primary']};
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}

    QSlider::handle:horizontal:hover {{
        background-color: {COLORS['accent_secondary']};
    }}

    /* ===== MENU BAR ===== */
    QMenuBar {{
        background-color: {COLORS['bg_darkest']};
        color: {COLORS['text_primary']};
        border-bottom: 1px solid {COLORS['border_dark']};
    }}

    QMenuBar::item {{
        padding: 8px 12px;
    }}

    QMenuBar::item:selected {{
        background-color: {COLORS['accent_primary']};
    }}

    QMenu {{
        background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border_dark']};
    }}

    QMenu::item {{
        padding: 8px 30px;
    }}

    QMenu::item:selected {{
        background-color: {COLORS['accent_primary']};
    }}

    /* ===== STATUS BAR ===== */
    QStatusBar {{
        background-color: {COLORS['bg_darkest']};
        color: {COLORS['text_secondary']};
        border-top: 1px solid {COLORS['border_dark']};
    }}

    /* ===== SPLITTER ===== */
    QSplitter::handle {{
        background-color: {COLORS['border_dark']};
    }}

    QSplitter::handle:hover {{
        background-color: {COLORS['accent_primary']};
    }}

    /* ===== LABELS ===== */
    QLabel {{
        color: {COLORS['text_primary']};
        background-color: transparent;
    }}

    /* ===== TOOL TIP ===== */
    QToolTip {{
        background-color: {COLORS['bg_light']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['accent_primary']};
        padding: 6px;
        border-radius: 4px;
    }}

    /* ===== SCROLL AREA ===== */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}

    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* ===== MESSAGE BOX ===== */
    QMessageBox {{
        background-color: {COLORS['bg_medium']};
    }}

    QMessageBox QLabel {{
        color: {COLORS['text_primary']};
    }}

    /* ===== DIALOG ===== */
    QDialog {{
        background-color: {COLORS['bg_dark']};
    }}
    """

    app.setStyleSheet(stylesheet)


def get_terminal_style():
    """Get hacker terminal style for log viewers"""
    return f"""
        QTextEdit {{
            background-color: #0a0a0a;
            color: #00ff00;
            font-family: "Consolas", "Courier New", monospace;
            font-size: 11px;
            border: 2px solid #1a1a1a;
            border-radius: 4px;
            padding: 8px;
        }}
    """


def get_card_style(accent_color: str = None):
    """Get card widget style"""
    border_color = accent_color or COLORS['border_light']
    return f"""
        QWidget {{
            background-color: {COLORS['card_bg']};
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
    """


def get_stat_card_style(color: str):
    """Get stat card style with custom accent color"""
    return f"""
        QWidget {{
            background-color: {COLORS['card_bg']};
            border: 2px solid {color};
            border-radius: 10px;
            padding: 15px;
        }}
    """


def get_action_button_style(color: str):
    """Get action button style with custom color"""
    # Calculate darker color for hover
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    darker = f"#{max(0,int(r*0.8)):02x}{max(0,int(g*0.8)):02x}{max(0,int(b*0.8)):02x}"

    return f"""
        QPushButton {{
            background-color: {color};
            color: white;
            font-size: 13px;
            font-weight: bold;
            padding: 15px 20px;
            border-radius: 8px;
            border: none;
            min-width: 120px;
            min-height: 70px;
        }}
        QPushButton:hover {{
            background-color: {darker};
        }}
        QPushButton:pressed {{
            background-color: {darker};
        }}
    """


def get_welcome_banner_style():
    """Get welcome banner gradient style"""
    return """
        QWidget {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1a237e, stop:0.5 #0d47a1, stop:1 #006064);
            border-radius: 10px;
            padding: 20px;
        }
    """


# Icon mappings for qtawesome
ICONS = {
    # Navigation
    'dashboard': 'fa5s.home',
    'quick_start': 'fa5s.rocket',
    'profiles': 'fa5s.user',
    'settings': 'fa5s.cog',
    'api_keys': 'fa5s.key',
    'voices': 'fa5s.microphone',
    'progress': 'fa5s.chart-bar',

    # Actions
    'play': 'fa5s.play',
    'stop': 'fa5s.stop',
    'pause': 'fa5s.pause',
    'save': 'fa5s.save',
    'delete': 'fa5s.trash',
    'edit': 'fa5s.edit',
    'add': 'fa5s.plus',
    'remove': 'fa5s.minus',
    'refresh': 'fa5s.sync',
    'browse': 'fa5s.folder-open',
    'folder': 'fa5s.folder',
    'file': 'fa5s.file',

    # Status
    'check': 'fa5s.check',
    'cross': 'fa5s.times',
    'warning': 'fa5s.exclamation-triangle',
    'info': 'fa5s.info-circle',
    'error': 'fa5s.times-circle',
    'success': 'fa5s.check-circle',

    # Media
    'video': 'fa5s.video',
    'audio': 'fa5s.volume-up',
    'image': 'fa5s.image',

    # Misc
    'eye': 'fa5s.eye',
    'eye_slash': 'fa5s.eye-slash',
    'globe': 'fa5s.globe',
    'download': 'fa5s.download',
    'upload': 'fa5s.upload',
    'test': 'fa5s.flask',
    'link': 'fa5s.link',
    'copy': 'fa5s.copy',
    'search': 'fa5s.search',
    'filter': 'fa5s.filter',
    'sort': 'fa5s.sort',
    'list': 'fa5s.list',
    'grid': 'fa5s.th',
    'terminal': 'fa5s.terminal',
    'code': 'fa5s.code',
    'magic': 'fa5s.magic',
    'clock': 'fa5s.clock',
    'calendar': 'fa5s.calendar',
    'star': 'fa5s.star',
    'heart': 'fa5s.heart',
    'bolt': 'fa5s.bolt',
    'shield': 'fa5s.shield-alt',
    'lock': 'fa5s.lock',
    'unlock': 'fa5s.unlock',
}


def get_icon(name: str, color: str = None):
    """Get a qtawesome icon by name"""
    try:
        import qtawesome as qta
        icon_name = ICONS.get(name, name)
        if color:
            return qta.icon(icon_name, color=color)
        return qta.icon(icon_name, color=COLORS['text_primary'])
    except ImportError:
        return None
