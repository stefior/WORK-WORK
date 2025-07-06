import sys
from ctypes import Structure, byref, c_uint, sizeof, windll
from types import TracebackType
from typing import Type

import psutil
import win32gui
import win32process
from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer, QElapsedTimer, QUrl
from PyQt6.QtGui import QFont, QFontDatabase, QIcon, QKeyEvent, QGuiApplication
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from border_windows import BorderWindows
from config_manager import ConfigManager
from hotkey_manager import HotkeyManager
import resources_rc


# Define asset paths using QRC prefixes
ALERT_PATH = ":/alert_sound"
FONT_PATH = ":/digital_font"
ICON_PATH = ":/timer_icon"


class ZeroPaddedSpinBox(QSpinBox):
    """A QSpinBox that displays values zero-padded to two digits."""

    def textFromValue(self, value: int) -> str:
        """Override to return zero-padded values.

        Args:
            value: The integer value to convert

        Returns:
            A string of the value zero-padded to two digits
        """
        return f"{value:02d}"


class CustomTimeEdit(QWidget):
    """A custom time input widget allowing hours up to 99, mimicking QTimeEdit."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hours_spin = ZeroPaddedSpinBox()
        self.minutes_spin = ZeroPaddedSpinBox()
        self.seconds_spin = ZeroPaddedSpinBox()

        # Configure ranges
        self.hours_spin.setRange(0, 99)
        self.minutes_spin.setRange(0, 59)
        self.seconds_spin.setRange(0, 59)

        # Set fixed width and alignment for a compact, uniform look
        for spin in (self.hours_spin, self.minutes_spin, self.seconds_spin):
            spin.setFixedWidth(30)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setButtonSymbols(
                QSpinBox.ButtonSymbols.NoButtons
            )  # Remove up/down arrows

        # Layout with separators
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(self.hours_spin)
        layout.addWidget(QLabel(":"))
        layout.addWidget(self.minutes_spin)
        layout.addWidget(QLabel(":"))
        layout.addWidget(self.seconds_spin)
        layout.addStretch(1)
        self.setLayout(layout)

        # Styling to resemble QTimeEdit
        self.setStyleSheet(
            """
            QSpinBox {
                border: none;
                background-color: transparent;
            }
            QLabel {
                font-size: 14px;
                padding: 0;
            }
        """
        )

    def set_time(self, hours: int, minutes: int, seconds: int) -> None:
        """Set the time values for the widget."""
        self.hours_spin.setValue(hours)
        self.minutes_spin.setValue(minutes)
        self.seconds_spin.setValue(seconds)

    def get_time(self) -> tuple[int, int, int]:
        """Get the current time values as a tuple (hours, minutes, seconds)."""
        return (
            self.hours_spin.value(),
            self.minutes_spin.value(),
            self.seconds_spin.value(),
        )


class ShortcutInputWidget(QLineEdit):
    """Custom widget for capturing keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Press a key combination...")
        self.setReadOnly(True)
        self.current_modifiers = set()
        self.current_key = None
        self.shortcut_captured = False

        # Set initial styling
        self.setStyleSheet(
            """
            QLineEdit {
                padding: 8px;
                font-size: 12px;
                border: 2px solid hsl(0, 0%, 80%);
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 2px solid hsl(204, 100%, 40%);
                outline: none;
            }
        """
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Capture key press events to build shortcut string."""
        key = event.key()

        # Handle Enter key specially - accept the dialog
        if key in [Qt.Key.Key_Enter, Qt.Key.Key_Return]:
            if self.parent():
                dialog = self.parent()
                while dialog and not isinstance(dialog, QDialog):
                    dialog = dialog.parent()
                if dialog:
                    dialog.accept()
            return

        # Handle Escape key specially - reject the dialog
        if key == Qt.Key.Key_Escape:
            if self.parent():
                dialog = self.parent()
                while dialog and not isinstance(dialog, QDialog):
                    dialog = dialog.parent()
                if dialog:
                    dialog.reject()
            return

        # Handle modifier keys
        if key in [
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Meta,
        ]:
            # Only update modifiers if we haven't captured a shortcut yet
            if not self.shortcut_captured:
                modifiers = event.modifiers()
                self.current_modifiers.clear()

                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    self.current_modifiers.add("ctrl")
                if modifiers & Qt.KeyboardModifier.AltModifier:
                    self.current_modifiers.add("alt")
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    self.current_modifiers.add("shift")
                if modifiers & Qt.KeyboardModifier.MetaModifier:
                    self.current_modifiers.add("win")

                self.current_key = None  # Clear any previous key
                self._update_display()
            return

        # Handle regular keys - this captures the shortcut
        if key != Qt.Key.Key_unknown:
            # Get current modifiers at the time of key press
            modifiers = event.modifiers()
            self.current_modifiers.clear()

            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.current_modifiers.add("ctrl")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                self.current_modifiers.add("alt")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.current_modifiers.add("shift")
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                self.current_modifiers.add("win")

            self.current_key = self._get_key_name(key)
            self.shortcut_captured = True
            self._update_display()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle key release events."""
        key = event.key()

        # Only update display on modifier release if shortcut not captured yet
        if not self.shortcut_captured and key in [
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Meta,
        ]:
            modifiers = event.modifiers()
            self.current_modifiers.clear()

            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.current_modifiers.add("ctrl")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                self.current_modifiers.add("alt")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.current_modifiers.add("shift")
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                self.current_modifiers.add("win")

            self.current_key = None  # Clear any previous key
            self._update_display()

    def _get_key_name(self, key: Qt.Key) -> str:
        """Convert Qt key to string representation."""
        key_map = {
            Qt.Key.Key_F1: "f1",
            Qt.Key.Key_F2: "f2",
            Qt.Key.Key_F3: "f3",
            Qt.Key.Key_F4: "f4",
            Qt.Key.Key_F5: "f5",
            Qt.Key.Key_F6: "f6",
            Qt.Key.Key_F7: "f7",
            Qt.Key.Key_F8: "f8",
            Qt.Key.Key_F9: "f9",
            Qt.Key.Key_F10: "f10",
            Qt.Key.Key_F11: "f11",
            Qt.Key.Key_F12: "f12",
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "pageup",
            Qt.Key.Key_PageDown: "pagedown",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Escape: "escape",
            Qt.Key.Key_Plus: "=",
            Qt.Key.Key_Minus: "-",
            Qt.Key.Key_Equal: "=",
            Qt.Key.Key_Underscore: "-",
        }

        if key in key_map:
            return key_map[key]

        # Handle regular characters
        if 32 <= key <= 126:  # Printable ASCII
            return chr(key).lower()

        return f"key_{key}"

    def _update_display(self) -> None:
        """Update the display text based on current modifiers and key."""
        parts = sorted(self.current_modifiers)
        if self.current_key:
            parts.append(self.current_key)

        if parts:
            self.setText("+".join(parts))
        else:
            self.setText("")

    def get_shortcut(self) -> str:
        """Get the current shortcut string."""
        return self.text()

    def set_shortcut(self, shortcut: str) -> None:
        """Set the shortcut string."""
        self.setText(shortcut)
        self.current_modifiers.clear()
        self.current_key = None
        self.shortcut_captured = bool(shortcut)

        if shortcut:
            parts = shortcut.lower().split("+")
            for part in parts[:-1]:
                if part in ["ctrl", "alt", "shift", "win"]:
                    self.current_modifiers.add(part)
            if parts:
                self.current_key = parts[-1]

    def clear_shortcut(self) -> None:
        """Clear the current shortcut and allow new input."""
        self.setText("")
        self.current_modifiers.clear()
        self.current_key = None
        self.shortcut_captured = False


class ShortcutInputDialog(QDialog):
    """Dialog for inputting keyboard shortcuts."""

    def __init__(self, parent=None, title="Set Shortcut", current_shortcut=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout()

        # Add instruction label
        instruction_label = QLabel("Press a key combination to set the shortcut:")
        layout.addWidget(instruction_label)

        # Add shortcut input widget
        self.shortcut_input = ShortcutInputWidget()
        self.shortcut_input.set_shortcut(current_shortcut)
        layout.addWidget(self.shortcut_input)

        # Add button layout (all buttons on same line)
        button_layout = QHBoxLayout()

        # Add clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.shortcut_input.clear_shortcut)
        button_layout.addWidget(clear_button)

        # Add spacer to push OK/Cancel to the right
        button_layout.addStretch()

        # Add OK and Cancel buttons
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Focus the input widget
        self.shortcut_input.setFocus()

    def get_shortcut(self) -> str:
        """Get the entered shortcut."""
        return self.shortcut_input.get_shortcut()


class MainWindow(QMainWindow):
    """Main application window for the work timer application.

    This window provides a time tracking interface for monitoring work on specific
    programs. Features include:

    - Time tracking with HH:MM:SS display
    - Program detection to start/stop timer automatically
    - Idle detection with optional visual and audio alerts
    - Color coding to indicate active/inactive states
    - Goal time setting with notifications
    - Global hotkeys for adding/removing tracked programs

    The window is designed to be compact and stay on top of other windows,
    typically positioned at the corner of the screen.
    """

    def __init__(self) -> None:
        """Initialize the main application window and its components.

        This constructor:
        - Sets up window properties (size, position)
        - Initializes configuration and settings from a file
        - Configures user interface elements
        - Sets up the timer system and time display
        - Establishes global hotkey bindings
        - Initializes idle detection and border windows

        The window initially shows inactive state until a tracked program is detected.
        """
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowStaysOnTopHint
        )

        # Initialize the configuration manager
        self.config = ConfigManager("qsettings.ini")

        # Save previous session to history if it exists
        if self.config.previous_time > 0:
            self.config.add_time_to_history(self.config.previous_time)

        self.window_size: QSize = QSize(220, 39)
        self.setFixedSize(self.window_size)

        # Geometry
        geometry = self.config.load_window_geometry()
        if geometry:
            self.restoreGeometry(geometry)
        else:
            primary_screen = QGuiApplication.primaryScreen()
            if primary_screen:
                bottom_right = primary_screen.availableGeometry().bottomRight()
                self.move(
                    bottom_right.x() - self.window_size.width(),
                    bottom_right.y() - self.window_size.height() * 2,
                )

        self.max_time_reached: bool = False
        self.goal_time_reached: bool = False
        self.idle_sound_played: bool = False

        self.active_color = "#B0FFFF"
        self.inactive_color = "#F07070"

        self.hide_time: bool = False  # Always start with time visible
        self.border_windows: BorderWindows = BorderWindows()
        self.wait_to_add_program: bool = False
        self.wait_to_remove_program: bool = False

        # Message display system
        self.showing_message: bool = False
        self.message_timer: QTimer = QTimer(self)
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(self.clear_message)

        # Register hotkeys
        self.hotkeys = HotkeyManager()
        self.hotkeys.register(self.config.add_program_hotkey, self.add_program)
        self.hotkeys.register(self.config.remove_program_hotkey, self.remove_program)

        self.setWindowTitle("WORK WORK")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setObjectName("MainWindow")

        self.foreground_is_tracked = False
        self.elapsed_seconds: float = 0.0  # Total finished work seconds
        self.active_timer = QElapsedTimer()
        self.active_timer.invalidate()  # Not running
        self.tick = QTimer(self)
        self.tick.setTimerType(Qt.TimerType.PreciseTimer)
        self.tick.timeout.connect(self.on_update)
        self.tick.start(200)  # 5 fps UI refresh

        # Timer for polling active window every 200ms
        self.active_window_timer = QTimer(self)
        self.active_window_timer.timeout.connect(self.check_active_window)
        self.active_window_timer.start(200)

        # Timer for periodic saving every 30 seconds to prevent data loss
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save_data)
        self.save_timer.start(30000)  # 30 seconds

        self.label: QLabel = QLabel("00:00:00", self)
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        digital_font_id: int = QFontDatabase.addApplicationFont(FONT_PATH)
        font_families: list[str] = QFontDatabase.applicationFontFamilies(
            digital_font_id
        )
        self.label.setFont(QFont(font_families[0], 24))
        self.label.setStyleSheet("color: black;")

        self.menu: QMenu = QMenu()
        self.menu.aboutToShow.connect(self.update_menu)

        # Set menu stylesheet for better keyboard navigation visibility
        # Detect if system is in dark mode
        app = QGuiApplication.instance()
        is_dark_mode = app.styleHints().colorScheme() == Qt.ColorScheme.Dark

        if is_dark_mode:
            # Dark theme: black background, white text
            menu_bg = "black"
            menu_border = "white"
            item_bg = "black"
            item_color = "white"
            disabled_color = "hsl(0, 0%, 47%)"
            separator_color = "hsl(0, 0%, 27%)"
        else:
            # Light theme: white background, black text
            menu_bg = "white"
            menu_border = "black"
            item_bg = "white"
            item_color = "black"
            disabled_color = "hsl(0, 0%, 53%)"
            separator_color = "hsl(0, 0%, 80%)"

        self.menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {menu_bg};
                border: 1px solid {menu_border};
                border-radius: 6px;
                padding: 4px;
                color: {item_color};
            }}
            QMenu::item {{
                background-color: {item_bg};
                color: {item_color};
                padding: 6px 12px;
                margin: 1px;
                border-radius: 4px;
                border: none;
            }}
            QMenu::item:selected {{
                background-color: hsl(218, 65%, 55%);
                color: white;
                border-radius: 4px;
            }}
            QMenu::item:disabled {{
                background-color: {item_bg};
                color: {disabled_color};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {separator_color};
                margin: 4px 8px;
            }}
        """
        )
        menu_button: QPushButton = QPushButton("MENU")
        menu_button.setStyleSheet(
            f"""QPushButton {{
                background-color: white;
                padding: 2px 4px;
                border: 1px solid black;
                font-size: 11px;
                color: black;
                margin: 0;
            }}

            QPushButton:focus {{
                outline: 1px solid black;
            }}

            QPushButton::menu-indicator {{
                width: 0;
            }}
            """
        )
        menu_button.setMenu(self.menu)

        checkbox: QCheckBox = QCheckBox("")
        checkbox.setCheckable(True)
        checkbox.clicked.connect(self.checkbox_was_toggled)
        checkbox.setChecked(self.hide_time)
        checkbox.setToolTip("Toggle time visibility")
        checkbox.setStyleSheet(
            """
            QCheckBox::indicator {
                background-color: white;
                border: 1px solid black;
            }
            QCheckBox::indicator:checked {
                background-color: black;
            }
            QCheckBox:focus {
                outline: 1px solid black;
            }
        """
        )

        layout: QHBoxLayout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.label)
        layout.addWidget(menu_button)
        layout.addWidget(checkbox)

        self.container: QWidget = QWidget()
        self.container.installEventFilter(self)
        self.container.setLayout(layout)

        self.setCentralWidget(self.container)

        # Initialize sound effect for alert sound
        self.sound_effect = QSoundEffect()
        self.sound_effect.setSource(QUrl.fromLocalFile(ALERT_PATH))

        self.show()

    def check_active_window(self):
        """Check the currently active window and update tracking state.

        Called every 200ms to poll the active window and determine if it's
        a tracked program. Updates the foreground_is_tracked state.
        Also handles program add/remove operations when waiting.
        """
        exe = self.get_active_exe()
        self.foreground_is_tracked = (
            exe and self.config.is_program_tracked(exe) and not self.is_self_focused()
        )

        # Handle program add/remove operations
        if (
            self.wait_to_add_program or self.wait_to_remove_program
        ) and not self.is_self_focused():
            self.click_handler()

        self.update_time_display()

    def on_update(self) -> None:
        """UI refresh and bookkeeping"""
        should_count = self.foreground_is_tracked and not self.is_idle()

        # Handle state changes
        if should_count and not self.active_timer.isValid():  # Just resumed
            self.active_timer.start()
        elif not should_count and self.active_timer.isValid():  # Just paused
            self.elapsed_seconds += self.active_timer.nsecsElapsed() / 1e9
            self.active_timer.invalidate()

        # Compute total seconds
        total = self.elapsed_seconds
        if self.active_timer.isValid():
            total += self.active_timer.nsecsElapsed() / 1e9

        # Alerts
        max_time = 99 * 3600 + 59 * 60 + 59
        if not self.max_time_reached and total >= max_time:
            self.max_time_reached = True
            self.show_alert("Maximum time reached!")
        if (
            not self.goal_time_reached
            and total >= self.config.goal_time
            and self.config.goal_time > 0
        ):
            self.goal_time_reached = True
            self.show_alert("Work goal reached!", 3)

        # Update UI
        if not should_count:
            if self.windowTitle() != "WORK WORK":
                self.setWindowTitle("BACK TO WORK")
            # Show border when not tracking time
            if (
                self.config.show_border_when_not_working
                and not self.border_windows.isVisible()
            ):
                self.border_windows.show()
        else:
            self.setWindowTitle("KEEP WORKING")
            # Hide border when tracking time
            if self.border_windows.isVisible():
                self.border_windows.hide()
        self.update_time_display()

    def save_data(self) -> None:
        """Save application state to persistent storage.

        Saves the window geometry and elapsed time to the settings file
        to be restored on next launch.
        """
        self.config.save_window_geometry(self.saveGeometry())
        self.config.save_previous_time(int(self.elapsed_seconds))

    def save_current_session(self) -> None:
        """Save the current session to history if it has meaningful time.

        This method captures the current total time (elapsed + active timer)
        and saves it to the history if it's greater than 0. This should be
        called before manual time changes, resets, or app closure.
        """
        # Calculate total current time including any active timer
        total_time = self.elapsed_seconds
        if self.active_timer.isValid():
            total_time += self.active_timer.nsecsElapsed() / 1e9

        # Save to history if it's meaningful (> 0)
        if total_time > 0:
            self.config.add_time_to_history(int(total_time))

    def handle_exception(
        self,
        exception_type: Type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        """Handle uncaught exceptions gracefully.

        Saves application data and cleans up hooks before exiting
        when an unhandled exception occurs.

        Args:
            exception_type: Type of the exception
            value: The exception instance
            traceback: The traceback object
        """
        # Save current session to history before exiting
        self.save_current_session()

        # Hide border windows to prevent them from staying visible
        if self.border_windows.isVisible():
            self.border_windows.hide()

        self.save_data()
        self.hotkeys.unregister_all()
        print(exception_type, value, traceback)
        sys.exit(0)

    def get_active_exe(self) -> str | None:
        """Get the executable path of the currently active window."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            return psutil.Process(pid).exe()
        except Exception:
            return None

    def update_label_safe(self, text: str) -> None:
        """Update the time display label in a thread-safe manner."""
        QTimer.singleShot(0, lambda: self.label.setText(text))

    def update_time_display(self) -> None:
        """Update the visual representation of tracked time.

        Updates the background color based on tracking state and
        formats the elapsed time for display. Handles time hiding
        and clamping to maximum displayable value.
        """
        if self.foreground_is_tracked and not self.is_idle():
            self.setStyleSheet(
                f"QMainWindow#MainWindow {{ background-color: {self.active_color}; }}"
            )
        else:
            self.setStyleSheet(
                f"QMainWindow#MainWindow {{ background-color: {self.inactive_color}; }}"
            )

        # Don't update text if we're showing a message
        if self.showing_message:
            return

        total = self.elapsed_seconds
        if self.active_timer.isValid():  # Still running
            total += self.active_timer.nsecsElapsed() / 1e9

        # Clamp displayed time to 99 h 59 m 59 s
        max_time = 99 * 3600 + 59 * 60 + 59
        total = min(total, max_time)

        if self.hide_time:
            text = "--:--:--"
        else:
            h, m, s = self.convert_seconds_to_hms(total)
            text = f"{h:02}:{m:02}:{s:02}"

        self.update_label_safe(text)

    def show_message(self, text: str, duration: int = 1000) -> None:
        """Display a temporary message in the timer display area.

        Args:
            text: The message text to display
            duration: Duration in milliseconds to show the message (default: 1000ms)
        """
        self.showing_message = True
        self.update_label_safe(text)
        self.message_timer.start(duration)

    def clear_message(self) -> None:
        """Clear the temporary message and return to normal time display."""
        self.showing_message = False
        self.update_time_display()

    def update_menu(self) -> None:
        """Refresh the context menu with current settings and options.

        Dynamically creates menu items with checkmarks for toggleable options
        and displays current settings values.
        """
        self.menu.clear()

        # Program management actions
        self.menu.addAction("Add program", self.add_program_mouse)
        self.menu.addAction("Remove program", self.remove_program_mouse)

        self.menu.addSeparator()

        # Idle timeout setting
        self.menu.addAction(
            f"Timeout seconds: {self.config.idle_timeout}", self.set_idle_timeout
        )

        # Goal time setting
        goal_h, goal_m, goal_s = self.convert_seconds_to_hms(self.config.goal_time)
        self.menu.addAction(
            f"Goal time: {goal_h:02}:{goal_m:02}:{goal_s:02}", self.set_goal_time
        )

        # Shortcut settings
        self.menu.addAction(
            f"Add program shortcut: {self.config.add_program_hotkey}",
            self.set_add_program_shortcut,
        )
        self.menu.addAction(
            f"Remove program shortcut: {self.config.remove_program_hotkey}",
            self.set_remove_program_shortcut,
        )

        # Toggleable options with checkmarks
        toggle_sound = self.menu.addAction("Idle indicator sound")
        toggle_sound.setCheckable(True)
        toggle_sound.setChecked(self.config.play_sound_on_idle)
        toggle_sound.triggered.connect(self.toggle_idle_sound)

        toggle_border = self.menu.addAction("Show border when not working")
        toggle_border.setCheckable(True)
        toggle_border.setChecked(self.config.show_border_when_not_working)
        toggle_border.triggered.connect(self.toggle_border_indicator)

        self.menu.addSeparator()

        # Timer history submenu
        history_menu = self.menu.addMenu("Resume a previous time")
        history = self.config.get_time_history()

        if history:
            for i, time_seconds in enumerate(history):
                h, m, s = self.convert_seconds_to_hms(time_seconds)
                time_text = f"{h:02}:{m:02}:{s:02}"
                history_menu.addAction(
                    time_text, lambda t=time_seconds: self.resume_time_from_history(t)
                )
        else:
            # Show disabled item when no history
            no_history_action = history_menu.addAction("No previous sessions")
            no_history_action.setEnabled(False)

        # Time management actions
        self.menu.addAction("Reset time", self.reset_time)
        self.menu.addAction("Change current time", self.change_current_time)

    def toggle_border_indicator(self) -> None:
        """Toggle the display of border indicators.

        Switches the border indicator setting between enabled and disabled,
        saves the setting to configuration, and updates the UI to show
        the new state.
        """
        is_enabled = self.config.toggle_border_setting()

        if is_enabled:
            self.show_message("brdr on")
            # If not tracking time, show border immediately
            if not self.foreground_is_tracked or self.is_idle():
                self.border_windows.show()
        else:
            self.show_message("brdr off")
            # Hide border immediately if it's visible
            if self.border_windows.isVisible():
                self.border_windows.hide()

    def is_idle(self) -> bool:
        """Determine if the system is currently idle based on user input activity.

        This method checks if the system has been inactive for longer than the configured
        idle timeout period. It uses Windows API calls to detect the last input time and
        calculates the duration since that input.

        If the system is determined to be idle:
        - Plays an alert sound if enabled (only once per idle period)

        Returns:
            bool: True if the system is idle, False otherwise
        """

        # http://stackoverflow.com/questions/911856/detecting-idle-time-in-python
        class LASTINPUTINFO(Structure):
            _fields_: list = [
                ("cbSize", c_uint),
                ("dwTime", c_uint),
            ]

        def get_idle_duration() -> float:
            lastInputInfo = LASTINPUTINFO()
            lastInputInfo.cbSize = sizeof(lastInputInfo)
            windll.user32.GetLastInputInfo(byref(lastInputInfo))
            milliseconds: float = (
                windll.kernel32.GetTickCount64() - lastInputInfo.dwTime
            )
            return milliseconds / 1000

        idle_duration = get_idle_duration()
        if idle_duration >= self.config.idle_timeout:
            if self.config.play_sound_on_idle and not self.idle_sound_played:
                try:
                    self.idle_sound_played = True
                    self.sound_effect.play()
                except Exception as e:
                    print(f"Error playing sound: {e}")

            return True
        else:
            self.idle_sound_played = False  # Reset flag when no longer idle
            return False

    def set_idle_timeout(self) -> None:
        """Open a dialog to set the idle timeout duration in seconds.

        This method displays an input dialog allowing the user to set how many seconds
        of inactivity are required before the system is considered idle. Valid values
        range from 1 to 99999 seconds.

        When accepted, the new value is stored in both the application state and the
        configuration file.
        """
        dialog: QInputDialog = QInputDialog(self)

        # Remove question mark from the title bar
        dialog.setWindowFlags(
            dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        dialog.setInputMode(QInputDialog.InputMode.IntInput)
        dialog.setIntRange(1, 99999)
        dialog.setIntValue(self.config.idle_timeout)
        dialog.setLabelText("Enter new idle timeout:")
        dialog.setWindowTitle("Idle Setting")

        if dialog.exec() == QInputDialog.DialogCode.Accepted:
            new_timeout: int = dialog.intValue()
            self.config.set_idle_timeout(new_timeout)

    def convert_seconds_to_hms(self, seconds: float | int) -> tuple[int, int, int]:
        """Convert seconds to hours, minutes, and seconds."""
        seconds = int(round(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return (h, m, s)

    def set_goal_time(self) -> None:
        """Open a dialog to set the goal time using a custom time edit widget."""
        dialog = QDialog()
        dialog.setWindowTitle("Goal Time Setting")
        dialog.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowStaysOnTopHint
        )
        dialog.setWindowIcon(QIcon(ICON_PATH))

        time_edit = CustomTimeEdit()
        goal_h, goal_m, goal_s = self.convert_seconds_to_hms(self.config.goal_time)
        time_edit.set_time(goal_h, goal_m, goal_s)

        # Buttons layout
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(time_edit)
        main_layout.addLayout(button_layout)
        dialog.setLayout(main_layout)

        # Show dialog as modal
        dialog.setModal(True)
        if dialog.exec():
            goal_h, goal_m, goal_s = time_edit.get_time()
            goal_time_seconds = goal_h * 3600 + goal_m * 60 + goal_s
            self.config.set_goal_time(goal_time_seconds)
            self.goal_time_reached = False  # Reset flag when goal changes
        dialog.deleteLater()

    def change_current_time(self) -> None:
        """Open a dialog to change the current time using a custom time edit widget."""
        dialog = QDialog()
        dialog.setWindowTitle("Change Current Time")
        dialog.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowStaysOnTopHint
        )
        dialog.setWindowIcon(QIcon(ICON_PATH))

        time_edit = CustomTimeEdit()
        h, m, s = self.convert_seconds_to_hms(self.elapsed_seconds)
        time_edit.set_time(h, m, s)

        # Buttons layout
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(time_edit)
        main_layout.addLayout(button_layout)
        dialog.setLayout(main_layout)

        # Show dialog as modal
        dialog.setModal(True)
        if dialog.exec():
            # Save current session before changing time
            self.save_current_session()

            h, m, s = time_edit.get_time()
            self.elapsed_seconds = h * 3600 + m * 60 + s
            self.update_time_display()

            # Check if goal has been reached with the new time
            if (
                self.elapsed_seconds >= self.config.goal_time
                and self.config.goal_time > 0
            ):
                self.goal_time_reached = True
            else:
                self.goal_time_reached = False

            self.max_time_reached = False

        dialog.deleteLater()

    def set_add_program_shortcut(self) -> None:
        """Open a dialog to set the add program shortcut."""
        dialog = ShortcutInputDialog(
            self, "Add Program Shortcut", self.config.add_program_hotkey
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_shortcut: str = dialog.get_shortcut().strip()
            if new_shortcut:
                old_shortcut = self.config.add_program_hotkey
                try:
                    # Update hotkey registration - replace just the add program hotkey
                    self.hotkeys.replace_hotkey(
                        old_shortcut, new_shortcut, self.add_program
                    )
                    self.config.set_add_program_hotkey(new_shortcut)
                except RuntimeError as e:
                    # Show error message to user
                    error_dialog = QMessageBox(self)
                    error_dialog.setIcon(QMessageBox.Icon.Warning)
                    error_dialog.setWindowTitle("Hotkey Error")
                    error_dialog.setText(f"Could not set hotkey: {str(e)}")
                    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                    error_dialog.exec()

    def set_remove_program_shortcut(self) -> None:
        """Open a dialog to set the remove program shortcut."""
        dialog = ShortcutInputDialog(
            self, "Remove Program Shortcut", self.config.remove_program_hotkey
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_shortcut: str = dialog.get_shortcut().strip()
            if new_shortcut:
                old_shortcut = self.config.remove_program_hotkey
                try:
                    # Update hotkey registration - replace just the remove program hotkey
                    self.hotkeys.replace_hotkey(
                        old_shortcut, new_shortcut, self.remove_program
                    )
                    self.config.set_remove_program_hotkey(new_shortcut)
                except RuntimeError as e:
                    # Show error message to user
                    error_dialog = QMessageBox(self)
                    error_dialog.setIcon(QMessageBox.Icon.Warning)
                    error_dialog.setWindowTitle("Hotkey Error")
                    error_dialog.setText(f"Could not set hotkey: {str(e)}")
                    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                    error_dialog.exec()

    def is_self_focused(self) -> bool:
        """Determine if any part of this application has input focus."""
        if self.isActiveWindow():
            return True
        else:
            return any(widget.isActiveWindow() for widget in self.findChildren(QWidget))

    def add_program(self) -> None:
        """Add the currently active program to the tracked programs list."""
        exe = self.get_active_exe()
        if not exe or self.is_self_focused():
            return
        if self.config.is_program_tracked(exe):
            self.show_message("already+")
        else:
            self.config.add_tracked_program(exe)
            self.show_message("added")

        self.foreground_is_tracked = True
        self.update_time_display()

    def remove_program(self) -> None:
        """Remove the currently active program from the tracked programs list."""
        exe = self.get_active_exe()
        if not exe or self.is_self_focused():
            return
        if self.config.is_program_tracked(exe):
            self.config.remove_tracked_program(exe)
            self.show_message("removed")
        else:
            self.show_message("already-")

        self.foreground_is_tracked = False
        self.update_time_display()

    def add_program_mouse(self) -> None:
        """Initiate add program operation via mouse click.

        Sets a flag to listen for the next window focus change event
        to add that program to the tracking list.
        Updates the label to indicate the operation is in progress.
        """
        self.wait_to_add_program = True
        # Click then handled by eventFilter ...

        self.show_message("add prog")

    def remove_program_mouse(self) -> None:
        """Initiate remove program operation via mouse click.

        Sets a flag to listen for the next window focus change event
        to remove that program from the tracking list.
        Updates the label to indicate the operation is in progress.
        """
        self.wait_to_remove_program = True
        # Click then handled by eventFilter ...

        self.show_message("rem prog")

    def resume_previous_time(self) -> None:
        """Restore the previously saved elapsed time."""
        # Save current session before changing time
        self.save_current_session()

        self.elapsed_seconds = self.config.previous_time
        self.update_time_display()

    def resume_time_from_history(self, time_seconds: int) -> None:
        """Resume a specific time from the history.

        Args:
            time_seconds: The time in seconds to resume to
        """
        # Save current session before changing time
        self.save_current_session()

        self.elapsed_seconds = time_seconds
        self.update_time_display()

        # Check if goal has been reached with the resumed time
        if self.elapsed_seconds >= self.config.goal_time and self.config.goal_time > 0:
            self.goal_time_reached = True
        else:
            self.goal_time_reached = False

        self.max_time_reached = False

    def reset_time(self) -> None:
        """Saves the previous time, then resets the elapsed time to zero.

        Also clears any goal or maximum time reached flags.
        Only performs reset if current time is not already at 0.
        """
        # Calculate total current time including any active timer
        total = self.elapsed_seconds
        if self.active_timer.isValid():
            total += self.active_timer.nsecsElapsed() / 1e9

        # Only reset if current time is not already at 0
        if total > 0:
            # Save current session to history before resetting
            self.save_current_session()

            self.save_data()
            self.elapsed_seconds = 0
            self.goal_time_reached = False
            self.max_time_reached = False
            self.update_time_display()

    def show_alert(self, message: str, seconds: int | None = None) -> None:
        """Display a temporary alert message box to the user.

        Shows a non-modal warning message box in the center of the screen
        that automatically closes after the specified number of seconds.
        If seconds is None, the alert will remain until manually closed.

        Args:
            message: The text message to display in the alert box
            seconds: Number of seconds before auto-closing, or None for no auto-close
        """
        # Create the QMessageBox
        alert = QMessageBox(self)
        alert.setWindowTitle("Alert")
        alert.setText(message)
        alert.setIcon(QMessageBox.Icon.Warning)
        alert.setModal(False)

        # Calculate the center position
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        screen_center = screen_geometry.center()
        alert.move(screen_center - alert.rect().center())

        # Show the alert
        alert.show()

        # Close it after specified seconds if provided
        if seconds is not None:
            QTimer.singleShot(seconds * 1000, alert.close)

    def toggle_idle_sound(self) -> None:
        """Toggle the sound alert for idle state detection.

        Switches the idle sound alert setting between enabled and disabled,
        saves the setting to configuration, and updates the UI to show
        the new state.
        """
        is_enabled = self.config.toggle_idle_sound()

        if is_enabled:
            self.show_message("snd on")
        else:
            self.show_message("snd off")

    def checkbox_was_toggled(self, checked: bool) -> None:
        """Updates the time visibility setting and refreshes the display."""
        self.hide_time: bool = checked
        self.update_time_display()

    def click_handler(self) -> None:
        """Process deferred click actions for program tracking.

        Called when the window loses focus after a tracking operation
        has been initiated. Calls the appropriate add/remove program
        function and resets the waiting flags.
        """
        if self.wait_to_add_program:
            self.add_program()
        elif self.wait_to_remove_program:
            self.remove_program()

        self.wait_to_add_program = False
        self.wait_to_remove_program = False

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        """Filter and process events for the application.

        This event filter handles:
        1. Escape key presses to cancel add/remove program operations

        Args:
            source: The object that triggered the event
            event: The event that was triggered

        Returns:
            bool: True if the event should be filtered out, False to pass it on
        """
        if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Escape:
            self.wait_to_add_program = False
            self.wait_to_remove_program = False

        return super().eventFilter(source, event)

    def closeEvent(self, event: QEvent) -> None:
        """Handle window close events.

        Performs cleanup operations when the application is closing:
        - Saves current session to history
        - Hides border windows to prevent them from staying visible
        - Cleans up COM event context
        - Unhooks all Windows event hooks
        - Saves current application state to settings
        """
        # Save current session to history before closing
        self.save_current_session()

        # Hide border windows first to prevent them from staying visible
        if self.border_windows.isVisible():
            self.border_windows.hide()

        self.save_data()

        self.hotkeys.unregister_all()


app: QApplication = QApplication([])
window: MainWindow = MainWindow()
sys.excepthook = window.handle_exception
window.show()

app.exec()
