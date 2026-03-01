"""
Custom Widgets - Reusable UI components
Professional, icon-based widgets for studio-grade UI
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QLineEdit, QPushButton, QSlider, QFileDialog,
                             QColorDialog, QCheckBox, QSpinBox, QDoubleSpinBox,
                             QComboBox, QTextEdit, QGroupBox, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont


class NoWheelSlider(QSlider):
    """Slider that ignores mouse wheel events - prevents accidental changes when scrolling"""
    def wheelEvent(self, event):
        # Ignore wheel events, pass to parent for scrolling
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """SpinBox that ignores mouse wheel events - prevents accidental changes when scrolling"""
    def wheelEvent(self, event):
        # Ignore wheel events, pass to parent for scrolling
        event.ignore()


from pathlib import Path

# Try to import qtawesome for icons
try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False

# Import color constants
try:
    from ui_styles import COLORS, get_icon, get_accent_color
except ImportError:
    COLORS = {
        'accent_primary': '#00bcd4',
        'accent_success': '#4caf50',
        'accent_warning': '#ff9800',
        'accent_error': '#f44336',
        'text_primary': '#ffffff',
        'text_secondary': '#b0b0b0',
        'bg_medium': '#1e1e1e',
        'border_dark': '#333333',
    }
    def get_icon(name, color=None):
        return None
    def get_accent_color():
        return '#E85D04'


class PathSelector(QWidget):
    """Widget for selecting file or folder paths with icon status"""
    pathChanged = pyqtSignal(str)

    def __init__(self, label: str = "", is_file: bool = False, file_filter: str = "", label_width: int = 150, parent=None):
        super().__init__(parent)
        self.is_file = is_file
        self.file_filter = file_filter
        self.label_width = label_width
        self.init_ui(label)

    def init_ui(self, label: str):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            lbl = QLabel(label)
            lbl.setMinimumWidth(self.label_width)
            layout.addWidget(lbl)

        # Path field
        self.path_field = QLineEdit()
        self.path_field.setPlaceholderText("Select path...")
        self.path_field.setMinimumWidth(500)  # Ensure path is readable
        self.path_field.setMinimumHeight(35)  # Taller input field
        self.path_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Expand horizontally
        self.path_field.textChanged.connect(self._on_path_changed)
        layout.addWidget(self.path_field)

        # Status indicator (icon-based)
        self.indicator = QLabel()
        self.indicator.setFixedWidth(24)
        self.indicator.setAlignment(Qt.AlignCenter)
        self._update_indicator(False, "empty")
        layout.addWidget(self.indicator)

        # Browse button with folder icon
        self.btn_browse = QPushButton()
        if HAS_ICONS:
            self.btn_browse.setIcon(qta.icon('fa5s.folder-open', color=COLORS['text_primary']))
        else:
            self.btn_browse.setText("...")
        self.btn_browse.setFixedWidth(40)
        self.btn_browse.setToolTip("Browse...")
        self.btn_browse.clicked.connect(self.browse)
        layout.addWidget(self.btn_browse)

        self.setLayout(layout)

    def _update_indicator(self, exists: bool, status: str):
        """Update the status indicator icon"""
        if HAS_ICONS:
            if status == "empty":
                self.indicator.setPixmap(qta.icon('fa5s.times-circle', color=COLORS['accent_error']).pixmap(18, 18))
            elif exists:
                self.indicator.setPixmap(qta.icon('fa5s.check-circle', color=COLORS['accent_success']).pixmap(18, 18))
            else:
                self.indicator.setPixmap(qta.icon('fa5s.exclamation-triangle', color=COLORS['accent_warning']).pixmap(18, 18))
        else:
            if status == "empty":
                self.indicator.setText("X")
                self.indicator.setStyleSheet(f"color: {COLORS['accent_error']};")
            elif exists:
                self.indicator.setText("OK")
                self.indicator.setStyleSheet(f"color: {COLORS['accent_success']};")
            else:
                self.indicator.setText("!")
                self.indicator.setStyleSheet(f"color: {COLORS['accent_warning']};")

    def browse(self):
        """Open file/folder browser"""
        if self.is_file:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select File",
                self.path_field.text() or str(Path.home()),
                self.file_filter
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                "Select Folder",
                self.path_field.text() or str(Path.home())
            )

        if path:
            self.path_field.setText(path)

    def _on_path_changed(self, path: str):
        """Update validation indicator"""
        if not path:
            self._update_indicator(False, "empty")
        else:
            p = Path(path)
            self._update_indicator(p.exists(), "exists" if p.exists() else "missing")

        self.pathChanged.emit(path)

    def get_path(self) -> str:
        """Get current path"""
        return self.path_field.text()

    def set_path(self, path: str):
        """Set path"""
        self.path_field.setText(path)


class ColorPicker(QWidget):
    """Widget for selecting colors"""
    colorChanged = pyqtSignal(str)

    def __init__(self, label: str = "", default_color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self.current_color = default_color
        self.init_ui(label)

    def init_ui(self, label: str):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            layout.addWidget(lbl)

        # Color preview
        self.color_preview = QPushButton()
        self.color_preview.setFixedSize(40, 30)
        self.color_preview.clicked.connect(self.pick_color)
        self._update_preview()
        layout.addWidget(self.color_preview)

        # Hex field
        self.hex_field = QLineEdit(self.current_color)
        self.hex_field.setMaxLength(7)
        self.hex_field.setPlaceholderText("#RRGGBB")
        self.hex_field.textChanged.connect(self._on_hex_changed)
        layout.addWidget(self.hex_field)

        # Pick button with icon
        btn_pick = QPushButton()
        if HAS_ICONS:
            btn_pick.setIcon(qta.icon('fa5s.eye-dropper', color=COLORS['text_primary']))
            btn_pick.setText(" Pick")
        else:
            btn_pick.setText("Pick Color")
        btn_pick.clicked.connect(self.pick_color)
        layout.addWidget(btn_pick)

        self.setLayout(layout)

    def pick_color(self):
        """Open color picker dialog"""
        color = QColorDialog.getColor(
            QColor(self.current_color),
            self,
            "Select Color"
        )
        if color.isValid():
            self.current_color = color.name()
            self.hex_field.setText(self.current_color)
            self._update_preview()
            self.colorChanged.emit(self.current_color)

    def _on_hex_changed(self, text: str):
        """Handle hex field changes"""
        if text.startswith("#") and len(text) == 7:
            try:
                QColor(text)  # Validate
                self.current_color = text
                self._update_preview()
                self.colorChanged.emit(self.current_color)
            except:
                pass

    def _update_preview(self):
        """Update color preview button"""
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color}; border: 1px solid #444; border-radius: 4px;"
        )

    def get_color(self) -> str:
        """Get current color"""
        return self.current_color

    def set_color(self, color: str):
        """Set color"""
        self.current_color = color
        self.hex_field.setText(color)
        self._update_preview()


class LabeledSlider(QWidget):
    """Slider with label and value display"""
    valueChanged = pyqtSignal(float)

    def __init__(self, label: str = "", min_val: float = 0.0, max_val: float = 1.0,
                 default: float = 0.5, decimals: int = 2, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals
        self.multiplier = 10 ** decimals
        self.tooltip_text = tooltip
        self.init_ui(label, default)

    def init_ui(self, label: str, default: float):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            layout.addWidget(lbl)

        # Slider (NoWheelSlider ignores scroll wheel)
        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setMinimum(int(self.min_val * self.multiplier))
        self.slider.setMaximum(int(self.max_val * self.multiplier))
        self.slider.setValue(int(default * self.multiplier))
        self.slider.valueChanged.connect(self._on_slider_changed)
        if self.tooltip_text:
            self.slider.setToolTip(self.tooltip_text)
        layout.addWidget(self.slider)

        # Value display
        self.value_label = QLabel(f"{default:.{self.decimals}f}")
        self.value_label.setFixedWidth(60)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(f"color: {COLORS['accent_primary']}; font-weight: bold;")
        layout.addWidget(self.value_label)

        self.setLayout(layout)

    def _on_slider_changed(self, value: int):
        """Handle slider changes"""
        float_val = value / self.multiplier
        self.value_label.setText(f"{float_val:.{self.decimals}f}")
        self.valueChanged.emit(float_val)

    def get_value(self) -> float:
        """Get current value"""
        return self.slider.value() / self.multiplier

    def set_value(self, value: float):
        """Set value"""
        self.slider.setValue(int(value * self.multiplier))


class LabeledSpinBox(QWidget):
    """SpinBox with label"""
    valueChanged = pyqtSignal(int)

    def __init__(self, label: str = "", min_val: int = 0, max_val: int = 100,
                 default: int = 0, suffix: str = "", parent=None):
        super().__init__(parent)
        self.init_ui(label, min_val, max_val, default, suffix)

    def init_ui(self, label: str, min_val: int, max_val: int, default: int, suffix: str):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            layout.addWidget(lbl)

        # SpinBox (NoWheelSpinBox ignores scroll wheel)
        self.spinbox = NoWheelSpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setValue(default)
        if suffix:
            self.spinbox.setSuffix(f" {suffix}")
        self.spinbox.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.spinbox)

        layout.addStretch()
        self.setLayout(layout)

    def get_value(self) -> int:
        """Get current value"""
        return self.spinbox.value()

    def set_value(self, value: int):
        """Set value"""
        self.spinbox.setValue(value)


class LabeledCheckBox(QWidget):
    """CheckBox with label"""
    stateChanged = pyqtSignal(bool)

    def __init__(self, label: str = "", default: bool = False, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.init_ui(label, default, tooltip)

    def init_ui(self, label: str, default: bool, tooltip: str):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # CheckBox
        self.checkbox = QCheckBox(label)
        self.checkbox.setChecked(default)
        if tooltip:
            self.checkbox.setToolTip(tooltip)
        self.checkbox.stateChanged.connect(lambda: self.stateChanged.emit(self.checkbox.isChecked()))
        layout.addWidget(self.checkbox)

        layout.addStretch()
        self.setLayout(layout)

    def is_checked(self) -> bool:
        """Get checked state"""
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        """Set checked state"""
        self.checkbox.setChecked(checked)


class LabeledComboBox(QWidget):
    """ComboBox with label"""
    currentTextChanged = pyqtSignal(str)

    def __init__(self, label: str = "", items: list = None, parent=None):
        super().__init__(parent)
        self.init_ui(label, items or [])

    def init_ui(self, label: str, items: list):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            layout.addWidget(lbl)

        # ComboBox
        self.combobox = QComboBox()
        self.combobox.addItems(items)
        self.combobox.currentTextChanged.connect(self.currentTextChanged)
        layout.addWidget(self.combobox)

        self.setLayout(layout)

    def get_current_text(self) -> str:
        """Get current selection"""
        return self.combobox.currentText()

    def set_current_text(self, text: str):
        """Set current selection"""
        index = self.combobox.findText(text)
        if index >= 0:
            self.combobox.setCurrentIndex(index)

    def add_items(self, items: list):
        """Add items"""
        self.combobox.addItems(items)

    def clear(self):
        """Clear all items"""
        self.combobox.clear()


class LabeledLineEdit(QWidget):
    """Line edit with label and optional suggestions (autocomplete)"""
    textChanged = pyqtSignal(str)

    def __init__(self, label: str = "", placeholder: str = "", suggestions: list = None, parent=None):
        super().__init__(parent)
        self.init_ui(label, placeholder, suggestions or [])

    def init_ui(self, label: str, placeholder: str, suggestions: list):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            layout.addWidget(lbl)

        # Line Edit with completer
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e0e0e0;
                font-size: 12px;
            }
            QLineEdit:focus {{
                border-color: {get_accent_color()};
            }}
        """.format(get_accent_color=get_accent_color))
        self.line_edit.textChanged.connect(self.textChanged)

        # Add autocomplete if suggestions provided
        if suggestions:
            from PyQt5.QtWidgets import QCompleter
            from PyQt5.QtCore import Qt
            completer = QCompleter(suggestions)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            completer.popup().setStyleSheet("""
                QListView {
                    background-color: #252525;
                    border: 1px solid #3a3a3a;
                    color: #e0e0e0;
                    selection-background-color: """ + get_accent_color() + """;
                }
            """)
            self.line_edit.setCompleter(completer)

        layout.addWidget(self.line_edit)
        self.setLayout(layout)

    def get_text(self) -> str:
        """Get current text"""
        return self.line_edit.text()

    def set_text(self, text: str):
        """Set text"""
        self.line_edit.setText(text)

    def set_suggestions(self, suggestions: list):
        """Update suggestions"""
        from PyQt5.QtWidgets import QCompleter
        from PyQt5.QtCore import Qt
        completer = QCompleter(suggestions)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.line_edit.setCompleter(completer)


class SectionHeader(QLabel):
    """Section header label - professional style"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.setStyleSheet(f"color: {COLORS['accent_primary']}; padding: 10px 0px;")


class SettingsGroup(QGroupBox):
    """Grouped settings section - professional dark style"""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12px;
                border: 1px solid {COLORS['border_dark']};
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 14px;
                background-color: {COLORS['bg_medium']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: {COLORS['accent_primary']};
            }}
        """)
        self.inner_layout = QVBoxLayout()
        self.inner_layout.setSpacing(8)
        self.setLayout(self.inner_layout)

    def add_widget(self, widget: QWidget):
        """Add widget to group"""
        self.inner_layout.addWidget(widget)

    def add_layout(self, layout):
        """Add layout to group"""
        self.inner_layout.addLayout(layout)


class StatCard(QFrame):
    """Statistics card widget for dashboard - responsive"""

    def __init__(self, icon_name: str, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.init_ui(icon_name, title, value)

    def init_ui(self, icon_name: str, title: str, value: str):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border: 2px solid {self.color};
                border-radius: 10px;
                padding: 15px;
            }}
        """)

        # Make card expand horizontally, fixed height
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumSize(100, 100)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Icon
        icon_label = QLabel()
        if HAS_ICONS:
            icon_label.setPixmap(qta.icon(icon_name, color=self.color).pixmap(32, 32))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Value - larger font
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {self.color}; background: transparent;")
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setWordWrap(True)
        layout.addWidget(value_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 10px; color: {COLORS['text_secondary']}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        self.setLayout(layout)


class ActionButton(QPushButton):
    """Large action button with icon for dashboard - responsive"""

    def __init__(self, icon_name: str, title: str, description: str, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.init_ui(icon_name, title, description)

    def init_ui(self, icon_name: str, title: str, description: str):
        # Calculate darker color for hover
        r, g, b = int(self.color[1:3], 16), int(self.color[3:5], 16), int(self.color[5:7], 16)
        darker = f"#{max(0,int(r*0.8)):02x}{max(0,int(g*0.8)):02x}{max(0,int(b*0.8)):02x}"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color};
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 12px 15px;
                border-radius: 8px;
                border: none;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {darker};
            }}
        """)

        # Make button expand
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumSize(100, 60)

        if HAS_ICONS:
            self.setIcon(qta.icon(icon_name, color='white'))
            self.setIconSize(self.iconSize().scaled(20, 20, Qt.KeepAspectRatio))

        self.setText(f"{title}\n{description}")
        self.setToolTip(description)


class IconButton(QPushButton):
    """Small icon-only button"""

    def __init__(self, icon_name: str, tooltip: str = "", color: str = None, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_color = color or COLORS['text_primary']
        self.init_ui(tooltip)

    def init_ui(self, tooltip: str):
        if HAS_ICONS:
            self.setIcon(qta.icon(self.icon_name, color=self.icon_color))
        self.setToolTip(tooltip)
        self.setFixedSize(32, 32)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS['border_dark']};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_medium']};
                border-color: {COLORS['accent_primary']};
            }}
        """)


class TerminalLog(QTextEdit):
    """Terminal-style log viewer"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0a0a0a;
                color: #00ff00;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 11px;
                border: 2px solid #1a1a1a;
                border-radius: 4px;
                padding: 8px;
            }}
        """)

    def append_log(self, message: str, level: str = "info"):
        """Append a log message with color based on level"""
        colors = {
            "info": "#00ff00",
            "warning": "#ffaa00",
            "error": "#ff4444",
            "success": "#44ff44",
            "debug": "#888888",
        }
        color = colors.get(level, "#00ff00")
        self.append(f'<span style="color: {color};">{message}</span>')


class StatusIndicator(QLabel):
    """Status indicator with icon"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.set_status("unknown")

    def set_status(self, status: str):
        """Set status: 'ok', 'error', 'warning', 'unknown', 'loading'"""
        if HAS_ICONS:
            icons = {
                "ok": ('fa5s.check-circle', COLORS['accent_success']),
                "error": ('fa5s.times-circle', COLORS['accent_error']),
                "warning": ('fa5s.exclamation-triangle', COLORS['accent_warning']),
                "unknown": ('fa5s.question-circle', COLORS['text_secondary']),
                "loading": ('fa5s.spinner', COLORS['accent_primary']),
            }
            icon_name, color = icons.get(status, icons['unknown'])
            self.setPixmap(qta.icon(icon_name, color=color).pixmap(18, 18))
        else:
            symbols = {"ok": "OK", "error": "X", "warning": "!", "unknown": "?", "loading": "..."}
            self.setText(symbols.get(status, "?"))
