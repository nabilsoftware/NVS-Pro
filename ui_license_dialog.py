"""
License Activation Dialog for Nabil Video Studio Pro
Shows when customer first runs the application
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QTextEdit, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from license_manager import LicenseManager


class LicenseActivationDialog(QDialog):
    """Dialog for license activation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.license_manager = LicenseManager()
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Activate Nabil Video Studio Pro")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setModal(True)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit, QComboBox {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 10px;
                color: #e6edf3;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #E67E22;
            }
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #e0e0e0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #888888;
            }
            QTextEdit {
                background-color: #252525;
                border: none;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header_label = QLabel("Welcome to Nabil Video Studio Pro!")
        header_font = QFont("Segoe UI", 18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(header_label)

        # Subtitle
        subtitle = QLabel("Please enter your license key to activate the software")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #888888; margin-bottom: 10px;")
        layout.addWidget(subtitle)

        # Information box
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(130)
        info_text.setHtml("""
        <h3>How to Activate:</h3>
        <ol>
            <li>Enter your email address (used for purchase)</li>
            <li>Enter the license key you received via email</li>
            <li>Click 'Activate' button</li>
        </ol>
        <p><b>License Key Format:</b> XXXX-XXXX-XXXX-XXXX</p>
        <p style="color: #666;"><i>Don't have a license key? Contact support or visit our website.</i></p>
        """)
        layout.addWidget(info_text)

        layout.addSpacing(20)

        # Email input
        email_layout = QHBoxLayout()
        email_label = QLabel("Email:")
        email_label.setMinimumWidth(100)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("customer@example.com")
        email_layout.addWidget(email_label)
        email_layout.addWidget(self.email_input)
        layout.addLayout(email_layout)

        # License key input
        key_layout = QHBoxLayout()
        key_label = QLabel("License Key:")
        key_label.setMinimumWidth(100)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX (T=Trial, S=Starter, P=Pro, E=Enterprise)")
        self.key_input.setMaxLength(19)  # 16 chars + 3 dashes
        self.key_input.textChanged.connect(self.on_key_changed)  # Auto-detect license type
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)

        # License type display (read-only, auto-detected from key)
        type_layout = QHBoxLayout()
        type_label = QLabel("License Type:")
        type_label.setMinimumWidth(100)
        self.license_type_combo = QComboBox()
        self.license_type_combo.addItem("Trial (7 days, 1 channel) - FREE", "trial")
        self.license_type_combo.addItem("Starter (3 channels) - $500", "starter")
        self.license_type_combo.addItem("Pro (unlimited channels) - $1,000", "pro")
        self.license_type_combo.addItem("Enterprise (unlimited) - $5,000", "enterprise")
        self.license_type_combo.setCurrentIndex(1)  # Default to Starter
        self.license_type_combo.setEnabled(False)  # Disabled - auto-detected from key
        self.license_type_combo.setStyleSheet("background-color: #2a2a2a; color: #888888;")
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.license_type_combo)
        layout.addLayout(type_layout)

        # Important notice
        notice = QLabel("ℹ️ <b>License type is automatically detected from your key.</b> "
                       "The first character indicates: T=Trial, S=Starter, P=Pro, E=Enterprise")
        notice.setWordWrap(True)
        notice.setStyleSheet("color: #E67E22; background-color: #252525; padding: 10px; border-radius: 6px; border: none;")
        layout.addWidget(notice)

        layout.addSpacing(20)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setMinimumWidth(100)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                border: 1px solid #238636;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2ea043;
                border-color: #2ea043;
            }
        """)
        self.activate_btn.clicked.connect(self.activate_license)
        button_layout.addWidget(self.activate_btn)

        self.quit_btn = QPushButton("Quit")
        self.quit_btn.setMinimumWidth(100)
        self.quit_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.quit_btn)

        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def on_key_changed(self, text):
        """Auto-detect license type from key prefix"""
        if len(text) >= 1:
            # Get first character
            prefix = text[0].upper()

            # Map to license type index
            type_map = {
                "T": 0,  # Trial
                "S": 1,  # Starter
                "P": 2,  # Pro
                "E": 3   # Enterprise
            }

            # Update combo box selection
            if prefix in type_map:
                self.license_type_combo.setCurrentIndex(type_map[prefix])

    def activate_license(self):
        """Activate the license"""
        email = self.email_input.text().strip()
        license_key = self.key_input.text().strip().upper()

        # Validate inputs
        if not email:
            self.show_error("Please enter your email address")
            return

        if not license_key:
            self.show_error("Please enter your license key")
            return

        if "@" not in email:
            self.show_error("Please enter a valid email address")
            return

        # Get selected license type
        license_type = self.license_type_combo.currentData()

        # Map license type to days (all paid plans are lifetime)
        days_map = {
            "trial": 7,
            "starter": 36500,    # Lifetime
            "pro": 36500,        # Lifetime
            "enterprise": 36500  # Lifetime
        }
        days_valid = days_map.get(license_type, 36500)

        # Attempt activation
        self.status_label.setText("Activating...")
        self.activate_btn.setEnabled(False)

        success, message = self.license_manager.activate_license(
            license_key, email, license_type, days_valid
        )

        if success:
            QMessageBox.information(
                self,
                "Activation Successful",
                "Your license has been activated successfully!\n\n"
                "Thank you for purchasing Nabil Video Studio Pro."
            )
            self.accept()  # Close dialog and allow app to run
        else:
            self.show_error(message)

        self.activate_btn.setEnabled(True)
        self.status_label.setText("")

    def show_error(self, message):
        """Show error message"""
        self.status_label.setText(f"<span style='color: red;'>{message}</span>")
        QMessageBox.warning(self, "Activation Error", message)


class LicenseInfoDialog(QDialog):
    """Dialog showing current license information"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.license_manager = LicenseManager()
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("License Information")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        layout = QVBoxLayout()

        # Header
        header = QLabel("License Information")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        layout.addSpacing(10)

        # Get license info
        license_info = self.license_manager.get_license_info()

        if license_info:
            info_text = QTextEdit()
            info_text.setReadOnly(True)

            # Format dates nicely
            from datetime import datetime
            activated = license_info.get('activated_date', 'Unknown')
            expiry = license_info.get('expiry_date', 'Unknown')

            if activated != 'Unknown':
                try:
                    activated = datetime.fromisoformat(activated).strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            if expiry != 'Unknown':
                try:
                    expiry = datetime.fromisoformat(expiry).strftime("%Y-%m-%d")
                except:
                    pass

            html = f"""
            <table style="width: 100%;">
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Status:</td>
                    <td style="color: green; padding: 5px;">{license_info.get('status', 'Unknown').upper()}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">License Type:</td>
                    <td style="padding: 5px;">{license_info.get('license_type', 'Unknown').upper()}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Duration:</td>
                    <td style="padding: 5px;">{license_info.get('duration', 'Unknown')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Price:</td>
                    <td style="padding: 5px;">{license_info.get('price', 'Unknown')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">License Key:</td>
                    <td style="padding: 5px;">{license_info.get('license_key', 'Unknown')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Customer Email:</td>
                    <td style="padding: 5px;">{license_info.get('customer_email', 'Unknown')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Activated Date:</td>
                    <td style="padding: 5px;">{activated}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Expires:</td>
                    <td style="padding: 5px;">{expiry}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Use Case:</td>
                    <td style="padding: 5px;"><i>{license_info.get('use_case', 'Unknown')}</i></td>
                </tr>
                <tr>
                    <td style="font-weight: bold; padding: 5px;">Machine ID:</td>
                    <td style="padding: 5px; font-size: 10px;">{license_info.get('machine_id', 'Unknown')}</td>
                </tr>
            </table>
            """

            info_text.setHtml(html)
            layout.addWidget(info_text)
        else:
            no_license_label = QLabel("No license information available")
            no_license_label.setAlignment(Qt.AlignCenter)
            no_license_label.setStyleSheet("color: #da3633;")
            layout.addWidget(no_license_label)

        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if license_info:
            deactivate_btn = QPushButton("Deactivate License")
            deactivate_btn.clicked.connect(self.deactivate_license)
            button_layout.addWidget(deactivate_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def deactivate_license(self):
        """Deactivate the current license"""
        reply = QMessageBox.question(
            self,
            "Deactivate License",
            "Are you sure you want to deactivate your license?\n\n"
            "You will need to reactivate it to use the software again.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.license_manager.deactivate_license():
                QMessageBox.information(self, "Success", "License deactivated successfully")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to deactivate license")
