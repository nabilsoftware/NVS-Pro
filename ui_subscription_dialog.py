"""
Subscription Info Dialog for Nabil Video Studio Pro
Modern premium design with gradients, icons, and animations
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QMessageBox, QWidget, QGraphicsDropShadowEffect,
    QApplication
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QLinearGradient, QBrush, QIcon

try:
    import qtawesome as qta
    QTA_AVAILABLE = True
except ImportError:
    QTA_AVAILABLE = False

try:
    from license_manager import LicenseManager
    LICENSE_AVAILABLE = True
except ImportError:
    LICENSE_AVAILABLE = False


class GradientProgressRing(QWidget):
    """Modern gradient progress ring with animation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self._value = 0
        self.max_value = 100
        self.start_color = "#4CAF50"
        self.end_color = "#81C784"
        self.text = ""
        self.sub_text = ""

        # Animation
        self._animation = QPropertyAnimation(self, b"animatedValue")
        self._animation.setDuration(1000)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def get_animated_value(self):
        return self._value

    def set_animated_value(self, value):
        self._value = value
        self.update()

    animatedValue = pyqtProperty(float, get_animated_value, set_animated_value)

    def set_value(self, value, max_value, start_color="#4CAF50", end_color="#81C784", text="", sub_text=""):
        self.max_value = max_value
        self.start_color = start_color
        self.end_color = end_color
        self.text = text
        self.sub_text = sub_text

        # Animate to new value
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(min(value, max_value))
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        radius = 60

        # Background circle (track)
        pen = QPen(QColor("#2a2a2a"), 14)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(20, 20, 120, 120, 0, 360 * 16)

        # Progress arc with gradient effect
        if self.max_value > 0 and self._value > 0:
            span = int(360 * 16 * self._value / self.max_value)

            # Create gradient
            gradient = QLinearGradient(20, 20, 140, 140)
            gradient.setColorAt(0, QColor(self.start_color))
            gradient.setColorAt(1, QColor(self.end_color))

            pen = QPen(QBrush(gradient), 14)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(20, 20, 120, 120, 90 * 16, -span)

        # Main text
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 24, QFont.Bold)
        painter.setFont(font)

        text_rect = self.rect()
        text_rect.setTop(text_rect.top() - 10)
        painter.drawText(text_rect, Qt.AlignCenter, self.text)

        # Sub text
        if self.sub_text:
            painter.setPen(QColor("#888888"))
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            text_rect = self.rect()
            text_rect.setTop(text_rect.top() + 35)
            painter.drawText(text_rect, Qt.AlignCenter, self.sub_text)


class SubscriptionDialog(QDialog):
    """Modern subscription dialog with premium design"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Subscription")
        self.setFixedSize(520, 820)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.license_manager = LicenseManager() if LICENSE_AVAILABLE else None
        self.expiry_date = None  # Store expiry for timer

        # Live countdown timer
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)

        self.setup_style()
        self.create_ui()
        self.load_subscription_info()

    def setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #e0e0e0;
                background: transparent;
            }
            QFrame#headerCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #238636, stop:0.5 #2ea043, stop:1 #E67E22);
                border-radius: 16px;
                border: none;
            }
            QFrame#detailsCard {
                background-color: #252525;
                border-radius: 12px;
                border: none;
            }
            QFrame#timerCard {
                background-color: rgba(0, 0, 0, 0.3);
                border-radius: 8px;
                border: none;
            }
            QFrame#fieldRow {
                background-color: #2a2a2a;
                border-radius: 8px;
                border: none;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #888888;
            }
            QPushButton#primary {
                background-color: #238636;
                border-color: #238636;
                color: #ffffff;
            }
            QPushButton#primary:hover {
                background-color: #2ea043;
                border-color: #2ea043;
            }
            QPushButton#danger {
                background-color: #da3633;
                border-color: #da3633;
            }
            QPushButton#danger:hover {
                background-color: #f85149;
            }
            QPushButton#copy {
                background-color: transparent;
                border: none;
                padding: 5px 10px;
                border-radius: 6px;
            }
            QPushButton#copy:hover {
                background-color: #3a3a3a;
            }
        """)

    def create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header Card with gradient
        header_card = QFrame()
        header_card.setObjectName("headerCard")
        header_card.setMinimumHeight(180)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(30, 25, 30, 25)
        header_layout.setSpacing(15)

        # Status icon and text row
        status_row = QHBoxLayout()

        # Progress ring
        self.progress_ring = GradientProgressRing()
        status_row.addWidget(self.progress_ring)

        status_row.addSpacing(20)

        # Status text
        status_text_layout = QVBoxLayout()
        status_text_layout.setSpacing(8)

        self.status_label = QLabel("Loading...")
        self.status_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        status_text_layout.addWidget(self.status_label)

        self.status_detail = QLabel("")
        self.status_detail.setFont(QFont("Segoe UI", 12))
        self.status_detail.setStyleSheet("color: rgba(255,255,255,0.8);")
        status_text_layout.addWidget(self.status_detail)

        self.days_label = QLabel("")
        self.days_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        status_text_layout.addWidget(self.days_label)

        status_text_layout.addStretch()
        status_row.addLayout(status_text_layout, 1)

        header_layout.addLayout(status_row)
        layout.addWidget(header_card)

        # Details Card
        details_card = QFrame()
        details_card.setObjectName("detailsCard")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(20, 20, 20, 20)
        details_layout.setSpacing(12)

        # Title
        details_title = QLabel("License Details")
        details_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        details_title.setStyleSheet("color: #888; margin-bottom: 5px;")
        details_layout.addWidget(details_title)

        # License Key with copy button
        key_row = self._create_field_row("fa5s.key", "License Key")
        self.key_label = key_row.findChild(QLabel, "value")
        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("copy")
        if QTA_AVAILABLE:
            self.copy_btn.setIcon(qta.icon('fa5s.copy', color='#888'))
        else:
            self.copy_btn.setText("Copy")
        self.copy_btn.setFixedSize(32, 32)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_license_key)
        self.copy_btn.setToolTip("Copy license key")
        key_row.layout().addWidget(self.copy_btn)
        details_layout.addWidget(key_row)

        # Plan Type
        type_row = self._create_field_row("fa5s.crown", "Plan")
        self.type_label = type_row.findChild(QLabel, "value")
        details_layout.addWidget(type_row)

        # Price Paid
        price_row = self._create_field_row("fa5s.dollar-sign", "Price")
        self.price_label = price_row.findChild(QLabel, "value")
        details_layout.addWidget(price_row)

        # Customer Name
        name_row = self._create_field_row("fa5s.user", "Name")
        self.name_label = name_row.findChild(QLabel, "value")
        details_layout.addWidget(name_row)

        # Email
        email_row = self._create_field_row("fa5s.envelope", "Email")
        self.email_label = email_row.findChild(QLabel, "value")
        details_layout.addWidget(email_row)

        # Purchase Date
        purchase_row = self._create_field_row("fa5s.shopping-cart", "Purchased")
        self.purchase_label = purchase_row.findChild(QLabel, "value")
        details_layout.addWidget(purchase_row)

        # Expires On
        expires_row = self._create_field_row("fa5s.calendar-times", "Expires")
        self.expires_label = expires_row.findChild(QLabel, "value")
        details_layout.addWidget(expires_row)

        # Machine ID
        machine_row = self._create_field_row("fa5s.desktop", "Machine")
        self.machine_label = machine_row.findChild(QLabel, "value")
        self.machine_label.setStyleSheet("color: #666; font-size: 12px;")
        details_layout.addWidget(machine_row)

        # Time Remaining (same style as other rows)
        timer_row = self._create_field_row("fa5s.hourglass-half", "Time Left")
        self.countdown_label = timer_row.findChild(QLabel, "value")
        self.countdown_label.setFont(QFont("Consolas", 13, QFont.Bold))
        self.countdown_label.setText("--:--:--:--")
        details_layout.addWidget(timer_row)

        layout.addWidget(details_card)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.refresh_btn = QPushButton("  Refresh")
        if QTA_AVAILABLE:
            self.refresh_btn.setIcon(qta.icon('fa5s.sync', color='white'))
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_subscription_info)
        button_layout.addWidget(self.refresh_btn)

        self.upgrade_btn = QPushButton("  Upgrade License")
        self.upgrade_btn.setObjectName("primary")
        if QTA_AVAILABLE:
            self.upgrade_btn.setIcon(qta.icon('fa5s.rocket', color='white'))
        self.upgrade_btn.setCursor(Qt.PointingHandCursor)
        self.upgrade_btn.clicked.connect(self.open_upgrade)
        button_layout.addWidget(self.upgrade_btn)

        layout.addLayout(button_layout)

        # Bottom row
        bottom_layout = QHBoxLayout()

        self.deactivate_btn = QPushButton("Deactivate")
        self.deactivate_btn.setObjectName("danger")
        self.deactivate_btn.setFixedWidth(120)
        self.deactivate_btn.setCursor(Qt.PointingHandCursor)
        self.deactivate_btn.clicked.connect(self.deactivate_license)
        bottom_layout.addWidget(self.deactivate_btn)

        bottom_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _create_field_row(self, icon_name, label_text):
        """Create a styled field row with icon"""
        row = QFrame()
        row.setObjectName("fieldRow")
        row.setFixedHeight(50)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(15, 8, 15, 8)
        row_layout.setSpacing(12)

        # Icon
        if QTA_AVAILABLE:
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon_name, color='#E67E22').pixmap(18, 18))
            icon_label.setFixedWidth(20)
            row_layout.addWidget(icon_label)

        # Label
        label = QLabel(label_text)
        label.setFont(QFont("Segoe UI", 11))
        label.setStyleSheet("color: #888;")
        label.setFixedWidth(85)
        row_layout.addWidget(label)

        # Value
        value = QLabel("—")
        value.setObjectName("value")
        value.setFont(QFont("Segoe UI", 12, QFont.Bold))
        value.setStyleSheet("color: #fff;")
        row_layout.addWidget(value, 1)

        return row

    def copy_license_key(self):
        """Copy license key to clipboard"""
        if self.license_manager:
            info = self.license_manager.get_subscription_info()
            if info and info.get('license_key'):
                clipboard = QApplication.clipboard()
                clipboard.setText(info['license_key'])

                # Show feedback
                old_text = self.copy_btn.toolTip()
                self.copy_btn.setToolTip("Copied!")
                if QTA_AVAILABLE:
                    self.copy_btn.setIcon(qta.icon('fa5s.check', color='#4CAF50'))

                QTimer.singleShot(2000, lambda: self._reset_copy_btn(old_text))

    def _reset_copy_btn(self, old_text):
        self.copy_btn.setToolTip(old_text)
        if QTA_AVAILABLE:
            self.copy_btn.setIcon(qta.icon('fa5s.copy', color='#888'))

    def update_countdown(self):
        """Update the live countdown timer"""
        if not self.expiry_date:
            self.countdown_label.setText("--:--:--:--")
            return

        from datetime import datetime
        now = datetime.now()
        remaining = self.expiry_date - now

        if remaining.total_seconds() <= 0:
            self.countdown_label.setText("EXPIRED")
            self.countdown_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            self.countdown_timer.stop()
            return

        # Calculate days, hours, minutes, seconds
        total_seconds = int(remaining.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # Format display
        if days > 0:
            countdown_text = f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        elif hours > 0:
            countdown_text = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
        else:
            countdown_text = f"{minutes:02d}m {seconds:02d}s"

        self.countdown_label.setText(countdown_text)

        # Change color based on urgency
        if days == 0 and hours < 1:
            self.countdown_label.setStyleSheet("color: #ef4444; font-weight: bold;")  # Red
        elif days == 0:
            self.countdown_label.setStyleSheet("color: #f59e0b; font-weight: bold;")  # Orange
        else:
            self.countdown_label.setStyleSheet("color: #ffffff; font-weight: bold;")  # White

    def load_subscription_info(self):
        """Load and display subscription information"""
        if not self.license_manager:
            self.show_no_license()
            return

        info = self.license_manager.get_subscription_info()

        if not info:
            self.show_no_license()
            return

        # Update status
        status = info.get('status', 'Unknown')
        is_trial = info.get('is_trial', False)
        is_expired = info.get('is_expired', False)
        days_left = info.get('days_left', 0)
        hours_left = info.get('hours_left', 0)
        license_type = info.get('license_type', 'standard')

        self.status_label.setText(status.split(' - ')[0] if ' - ' in status else status)

        # Update progress ring based on status
        if license_type == 'lifetime':
            self.progress_ring.set_value(100, 100, "#10b981", "#34d399", "∞", "LIFETIME")
            self.days_label.setText("Never expires")
            self.status_detail.setText("Thank you for your support!")
        elif is_expired:
            self.progress_ring.set_value(0, 100, "#ef4444", "#f87171", "0", "EXPIRED")
            self.days_label.setText("License expired")
            self.status_detail.setText("Please renew to continue")
        elif is_trial:
            total_days = info.get('trial_days', 7) if 'trial_days' in info else 7
            if days_left == 0 and hours_left > 0:
                self.progress_ring.set_value(hours_left, 24, "#f59e0b", "#fbbf24", str(hours_left), "HOURS LEFT")
                self.days_label.setText(f"Trial ends in {hours_left} hours!")
            else:
                self.progress_ring.set_value(days_left, total_days, "#3b82f6", "#60a5fa", str(days_left), "DAYS LEFT")
                self.days_label.setText(f"{days_left} days remaining")
            self.status_detail.setText("Upgrade to unlock forever")
        else:
            self.progress_ring.set_value(min(days_left, 365), 365, "#10b981", "#34d399", str(days_left), "DAYS LEFT")
            self.days_label.setText(f"Valid for {days_left} more days")
            self.status_detail.setText("License is active")

        # Update details
        license_key = info.get('license_key', '—')
        if license_key and len(license_key) > 8:
            masked_key = license_key[:4] + "-••••-••••-" + license_key[-4:]
            self.key_label.setText(masked_key)
        else:
            self.key_label.setText(license_key)

        # Plan type
        type_display = info.get('license_type_display', info.get('plan_type', info.get('license_type', '—')).title())
        self.type_label.setText(type_display)

        # Price paid
        price_display = info.get('price_display', '—')
        self.price_label.setText(price_display)

        # Customer name
        customer_name = info.get('customer_name', '—')
        self.name_label.setText(customer_name or '—')

        # Email (masked)
        email = info.get('customer_email', '—')
        if email and '@' in email:
            parts = email.split('@')
            masked_email = parts[0][:2] + "•••@" + parts[1]
            self.email_label.setText(masked_email)
        else:
            self.email_label.setText(email or '—')

        # Purchase date
        purchase_date = info.get('purchase_date_formatted', '')
        if not purchase_date and info.get('purchase_date'):
            purchase_date = info.get('purchase_date', '')[:10]
        self.purchase_label.setText(purchase_date or '—')

        expiry = info.get('expiry_date_formatted', '')
        if not expiry and info.get('expiry_date'):
            expiry = info.get('expiry_date', '')[:10]
        if license_type == 'lifetime':
            expiry = 'Never'
        self.expires_label.setText(expiry or '—')

        # Start countdown timer
        from datetime import datetime
        expiry_str = info.get('expiry_date')
        if expiry_str and license_type != 'lifetime':
            try:
                self.expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '').split('+')[0])
                self.update_countdown()  # Update immediately
                self.countdown_timer.start(1000)  # Update every second
            except:
                self.expiry_date = None
                self.countdown_label.setText("--:--:--:--")
        elif license_type == 'lifetime':
            self.expiry_date = None
            self.countdown_label.setText("FOREVER")
            self.countdown_label.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.expiry_date = None
            self.countdown_label.setText("--:--:--:--")

        # Machine ID
        machine_id = info.get('machine_id', '—')
        if machine_id and len(machine_id) > 8:
            machine_id = machine_id[:8] + "•••"
        self.machine_label.setText(machine_id)

        # Hide upgrade for lifetime
        if license_type == 'lifetime':
            self.upgrade_btn.hide()
        else:
            self.upgrade_btn.show()

    def show_no_license(self):
        """Show UI when no license is found"""
        self.status_label.setText("No License")
        self.status_detail.setText("Activate to get started")
        self.days_label.setText("")
        self.progress_ring.set_value(0, 100, "#ef4444", "#f87171", "!", "NO LICENSE")

        self.key_label.setText("—")
        self.type_label.setText("—")
        self.price_label.setText("—")
        self.name_label.setText("—")
        self.email_label.setText("—")
        self.purchase_label.setText("—")
        self.expires_label.setText("—")
        self.machine_label.setText("—")

        # Stop timer
        self.countdown_timer.stop()
        self.expiry_date = None
        self.countdown_label.setText("NO LICENSE")
        self.countdown_label.setStyleSheet("color: #ef4444; font-weight: bold;")

        self.upgrade_btn.setText("  Activate License")
        self.deactivate_btn.hide()

    def open_upgrade(self):
        """Open upgrade/purchase page"""
        import webbrowser
        webbrowser.open("https://nabilsoftware.com/upgrade")

    def deactivate_license(self):
        """Deactivate the current license and restart app"""
        reply = QMessageBox.question(
            self,
            "Deactivate License?",
            "Are you sure you want to deactivate?\n\n"
            "The application will restart and you'll need to enter your license key again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.license_manager:
                self.license_manager.deactivate_license()

            # Auto restart the application
            self._restart_application()

    def _restart_application(self):
        """Restart the application after deactivation"""
        import sys
        import os
        import subprocess

        # Get the executable path
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            exe_path = sys.executable
        else:
            # Running as script
            exe_path = sys.executable
            script_path = os.path.abspath(sys.argv[0])

        try:
            # Show brief message
            msg = QMessageBox(self)
            msg.setWindowTitle("Restarting...")
            msg.setText("Deactivated! Restarting application...")
            msg.setStandardButtons(QMessageBox.NoButton)
            msg.show()
            QApplication.processEvents()

            # Small delay for user to see message
            QTimer.singleShot(1000, lambda: self._do_restart(exe_path if getattr(sys, 'frozen', False) else None))
        except Exception as e:
            # Fallback - just close
            QMessageBox.information(
                self,
                "Deactivated",
                "License deactivated.\nPlease restart the app manually."
            )
            QApplication.quit()

    def _do_restart(self, exe_path=None):
        """Perform the actual restart"""
        import sys
        import os
        import subprocess

        try:
            if exe_path:
                # Compiled exe - start new instance
                subprocess.Popen([exe_path], creationflags=subprocess.DETACHED_PROCESS)
            else:
                # Script mode - restart with python
                script_path = os.path.abspath(sys.argv[0])
                subprocess.Popen([sys.executable, script_path], creationflags=subprocess.DETACHED_PROCESS)
        except Exception as e:
            print(f"Restart failed: {e}")
        finally:
            # Close current instance
            QApplication.quit()


def show_subscription_dialog(parent=None):
    """Show the subscription dialog"""
    dialog = SubscriptionDialog(parent)
    return dialog.exec_()


# Test
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = SubscriptionDialog()
    dialog.exec_()
