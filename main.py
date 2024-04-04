import os
import sys
import time
from configparser import ConfigParser, SectionProxy
from ctypes import Structure, byref, c_uint, sizeof, windll
from types import TracebackType
from typing import Type

import keyboard
import psutil
import simpleaudio
import win32gui
import win32process
from PyQt5.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QRect,
    QSettings,
    QSize,
    Qt,
    QTimer,
)
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QIcon, QKeyEvent, QPainter, QPen
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QDesktopWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QWidget,
)


def resource_path(relative_path) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path: str = getattr(
        sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(base_path, relative_path)


alert_path: str = resource_path("alert.wav")
font_path: str = resource_path("digital-7-mono.ttf")
icon_path: str = resource_path("timericon.ico")


class BorderWindow(QWidget):
    def __init__(self, geometry: QRect) -> None:
        super().__init__()
        self.setGeometry(geometry)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.show()

    def paintEvent(self, a0: QEvent) -> None:
        event = a0
        painter: QPainter = QPainter()
        painter.begin(self)
        self.drawBorder(painter)
        painter.end()

    def drawBorder(self, painter: QPainter) -> None:
        color: QColor = QColor(240, 112, 112)
        painter.setPen(QPen(color, 8))  # Set pen color and width
        painter.drawRect(0, 0, self.width(), self.height())  # Draw border rectangle


class BorderWindows:
    def __init__(self) -> None:
        self.border_windows: list = []
        self.create_border_windows()
        self.is_visible: bool = False

    def create_border_windows(self) -> None:
        desktop: QDesktopWidget = QApplication.desktop()
        if desktop is not None:
            for i in range(desktop.screenCount()):
                geometry: QRect = desktop.screenGeometry(i)
                border_window: BorderWindow = BorderWindow(geometry)
                self.border_windows.append(border_window)
        else:
            print("Error: Desktop object not available")

    def hide(self) -> None:
        for border_window in self.border_windows:
            border_window.hide()
        self.is_visible = False

    def show(self) -> None:
        for border_window in self.border_windows:
            border_window.show()
        self.is_visible = True

    def isVisible(self) -> bool:
        return self.is_visible


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings: QSettings = QSettings("qsettings.ini", QSettings.IniFormat)

        self.window_size: QSize = QSize(205, 39)
        self.setFixedSize(self.window_size)

        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        else:
            available_width: int = QApplication.desktop().availableGeometry().width()
            available_height: int = QApplication.desktop().availableGeometry().height()

            x: int = available_width - self.window_size.width()
            y: int = available_height - self.window_size.height()
            w: int = self.window_size.width()
            h: int = self.window_size.height()

            self.setGeometry(QRect(x, y, w, h))

        # Delimeters set to only "=" becuase
        # ":" is used for saving the path of tracked programs
        self.config: ConfigParser = ConfigParser(delimiters=("=",))
        self.config.read("settings.ini")
        if "OPTIONS" not in self.config:
            self.config["OPTIONS"] = {}
        if "PROGRAMS" not in self.config:
            self.config["PROGRAMS"] = {}

        options: SectionProxy = self.config["OPTIONS"]
        self.tracked_programs: SectionProxy = self.config["PROGRAMS"]

        self.idle_timeout: int = options.getint("idle_timeout", 30)
        self.previous_time: str = options.get("previous_time", "00:00:00")
        self.play_sound_on_idle: bool = options.getboolean("play_sound_on_idle", False)
        self.show_border_on_idle: bool = options.getboolean(
            "show_border_on_idle", False
        )
        self.hide_time: bool = options.getboolean("hide_time", False)

        add_program_hotkey: str = options.get("add_program_hotkey", "ctrl+win+alt+a")
        remove_program_hotkey: str = options.get(
            "remove_program_hotkey", "ctrl+win+alt+r"
        )
        keyboard.add_hotkey(add_program_hotkey, self.add_program)
        keyboard.add_hotkey(remove_program_hotkey, self.remove_program)

        self.seconds_since_idle_timeout: int = 0
        self.border_windows: BorderWindows = BorderWindows()
        self.border_windows.hide()
        self.wait_to_add_program: bool = False
        self.wait_to_remove_program: bool = False

        self.setWindowTitle("WORK WORK")
        self.setWindowIcon(QIcon(icon_path))
        self.setObjectName("MainWindow")
        self.change_background_color("#F07070")
        self.hours: int = 0
        self.minutes: int = 0
        self.seconds: int = 0
        timer: QTimer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)
        self.time_reached = False

        self.current_time: str = "--:--:--" if self.hide_time else "00:00:00"
        self.label: QLabel = QLabel(self.current_time, self)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        digital_font_id: int = QFontDatabase.addApplicationFont(font_path)
        font_families: list[str] = QFontDatabase.applicationFontFamilies(
            digital_font_id
        )
        self.label.setFont(QFont(font_families[0], 24))

        self.menu: QMenu = QMenu()
        self.menu.aboutToShow.connect(self.update_menu)
        menu_button: QPushButton = QPushButton("MENU")
        menu_button.setStyleSheet(
            f"""QPushButton {{
                background-color: white;
                padding: 3px 6px;
                border: 1px solid black;
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

        layout: QHBoxLayout = QHBoxLayout()
        layout.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label)
        layout.addWidget(menu_button)
        layout.addWidget(checkbox)

        self.container: QWidget = QWidget()
        self.container.installEventFilter(self)
        self.container.setLayout(layout)

        self.setCentralWidget(self.container)

        self.show()

    def save_data(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        with open("settings.ini", "w") as configfile:
            self.config["OPTIONS"]["previous_time"] = self.current_time
            self.config.write(configfile)

    def handle_exception(
        self,
        type: Type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        self.save_data()
        print(type, value, traceback)
        sys.exit(0)

    def change_background_color(self, color: str) -> None:
        self.setStyleSheet(f"MainWindow {{ background-color: {color}; }}")

    def get_active_program(self) -> psutil.Process | None:
        max_retries: int = 3
        for attempt in range(max_retries):
            try:
                active_window_handle: int = win32gui.GetForegroundWindow()
                _, process_id = win32process.GetWindowThreadProcessId(
                    active_window_handle
                )
                if process_id > 0:
                    program: psutil.Process = psutil.Process(process_id)
                    return program
                else:
                    print(f"Invalid PID (attempt {attempt+1}): {process_id}")
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                OSError,
                ValueError,
            ) as e:
                print(f"Error getting active program (attempt {attempt+1}): {e}")

            time.sleep(0.2)

        return None

    def update_time(self) -> None:
        active_program: psutil.Process | None = self.get_active_program()
        active_program_path: str | None = (
            active_program.exe() if active_program else None
        )

        if ":" not in self.label.text():
            # Show the label message for .5 seconds before going back to the time
            time.sleep(0.5)

        if (
            active_program_path is not None
            and active_program_path in self.tracked_programs
            and self.is_idle() is False
        ):
            if self.border_windows.isVisible():
                self.border_windows.hide()
            self.change_background_color("#B0FFFF")
            self.setWindowTitle("KEEP WORKING")

            if self.seconds < 59:
                self.seconds += 1
            elif self.minutes < 59:
                self.minutes += 1
                self.seconds = 0
            elif self.hours < 99:
                self.hours += 1
                self.minutes = 0
                self.seconds = 0

            # Temporarily hardcoded alert for workday end
            if (
                self.hours == 8
                and self.minutes == 0
                and self.seconds <= 2
                and self.time_reached == False
            ):
                self.show_alert("Workday complete!")
                self.time_reached = True

        elif self.windowTitle() != "WORK WORK":
            self.change_background_color("#F07070")
            self.setWindowTitle("BACK TO WORK")

        if not self.wait_to_add_program and not self.wait_to_remove_program:
            self.update_label()

    def update_label(self) -> None:
        hh: str = str(self.hours) if self.hours > 9 else "0" + str(self.hours)
        mm: str = str(self.minutes) if self.minutes > 9 else "0" + str(self.minutes)
        ss: str = str(self.seconds) if self.seconds > 9 else "0" + str(self.seconds)
        self.current_time: str = f"{hh}:{mm}:{ss}"

        if self.hide_time:
            self.label.setText("--:--:--")
        else:
            self.label.setText(self.current_time)

    def update_menu(self) -> None:
        self.menu.clear()

        add_program_item: QAction = self.menu.addAction("Add program")
        add_program_item.triggered.connect(self.add_program_mouse)
        remove_program_item: QAction = self.menu.addAction("Remove program")
        remove_program_item.triggered.connect(self.remove_program_mouse)
        self.menu.addSeparator()

        idle_timeout_item: QAction = self.menu.addAction(
            f"Timeout: {self.idle_timeout}"
        )
        sound_state: str = "on" if self.play_sound_on_idle else "off"
        toggle_idle_sound_item: QAction = self.menu.addAction(
            f"Idle indicator sound: {sound_state}"
        )
        idle_timeout_item.triggered.connect(self.set_idle_timeout)

        toggle_idle_sound_item.triggered.connect(self.toggle_idle_sound)
        border_state: str = "on" if self.show_border_on_idle else "off"
        toggle_idle_border_item: QAction = self.menu.addAction(
            f"Idle indicator border: {border_state}"
        )
        toggle_idle_border_item.triggered.connect(self.toggle_idle_border)

        self.menu.addSeparator()

        resume_previous_time_item: QAction = self.menu.addAction("Resume previous time")
        resume_previous_time_item.triggered.connect(self.resume_previous_time)
        reset_time_item: QAction = self.menu.addAction("Reset time")
        reset_time_item.triggered.connect(self.reset_time)

    def toggle_idle_border(self) -> None:
        self.show_border_on_idle: bool = not self.show_border_on_idle
        self.config["OPTIONS"]["show_border_on_idle"] = str(self.show_border_on_idle)

        if self.show_border_on_idle:
            self.label.setText("brdr on")
        else:
            self.label.setText("brdr off")

    def is_idle(self) -> bool:
        # http://stackoverflow.com/questions/911856/detecting-idle-time-in-python
        class LASTINPUTINFO(Structure):
            _fields_: list = [
                ("cbSize", c_uint),
                ("dwTime", c_uint),
            ]

        def get_idle_duration() -> float:
            lastInputInfo: LASTINPUTINFO = LASTINPUTINFO()
            lastInputInfo.cbSize = sizeof(lastInputInfo)
            windll.user32.GetLastInputInfo(byref(lastInputInfo))
            millis: float = windll.kernel32.GetTickCount() - lastInputInfo.dwTime
            return millis / 1000

        # ----------------------------------------------------------------------

        if get_idle_duration() >= self.idle_timeout:
            if self.show_border_on_idle:
                self.border_windows.show()

            if self.play_sound_on_idle and self.seconds_since_idle_timeout == 0:
                wave_obj: simpleaudio.WaveObject = (
                    simpleaudio.WaveObject.from_wave_file(alert_path)
                )
                wave_obj.play()
                self.seconds_since_idle_timeout += 1

            return True
        else:
            self.seconds_since_idle_timeout = 0
            return False

    def set_idle_timeout(self) -> None:
        dialog_box: QInputDialog = QInputDialog(self)

        # Remove question mark from the title bar
        dialog_box.setWindowFlags(
            dialog_box.windowFlags() & ~Qt.WindowContextHelpButtonHint
            | Qt.WindowCloseButtonHint
        )

        dialog_box.setInputMode(QInputDialog.IntInput)
        dialog_box.setIntRange(1, 99999)
        dialog_box.setIntValue(self.idle_timeout)
        dialog_box.setLabelText("Ender new idle timeout:")
        dialog_box.setWindowTitle("Idle Setting")

        if dialog_box.exec() == QInputDialog.Accepted:
            new_timeout: int = dialog_box.intValue()
            self.idle_timeout: int = new_timeout
            self.config["OPTIONS"]["idle_timeout"] = str(new_timeout)

    def is_self_focused(self) -> bool:
        if self.isActiveWindow():
            return True
        else:
            return any(widget.isActiveWindow() for widget in self.findChildren(QWidget))

    def add_program(self) -> None:
        current_program: psutil.Process | None = self.get_active_program()
        if current_program is None or self.is_self_focused():
            return
        current_program_exe: str = current_program.exe()

        if current_program_exe in self.tracked_programs:
            self.label.setText("already+")
        else:
            self.tracked_programs[current_program_exe] = current_program.name()
            self.label.setText("added")

    def remove_program(self) -> None:
        current_program: psutil.Process | None = self.get_active_program()
        if current_program is None or self.is_self_focused():
            return
        current_program_exe: str = current_program.exe()

        if current_program_exe in self.tracked_programs:
            self.config.remove_option("PROGRAMS", current_program_exe)
            self.label.setText("removed")
        else:
            self.label.setText("already-")

    def add_program_mouse(self) -> None:
        self.wait_to_add_program = True
        # Click then handled by eventFilter ...

        self.label.setText("add prog")

    def remove_program_mouse(self) -> None:
        self.wait_to_remove_program = True
        # Click then handled by eventFilter ...

        self.label.setText("rem prog")

    def resume_previous_time(self) -> None:
        previous_time: list[str] = self.config["OPTIONS"]["previous_time"].split(":")
        self.hours: int = int(previous_time[0])
        self.minutes: int = int(previous_time[1])
        self.seconds: int = int(previous_time[2])
        self.update_label()

    def reset_time(self) -> None:
        self.save_data()
        self.hours: int = 0
        self.minutes: int = 0
        self.seconds: int = 0
        self.update_label()

    def show_alert(self, message):
        # Create the QMessageBox
        alert = QMessageBox(self)
        alert.setWindowTitle("Alert")
        alert.setText(message)
        alert.setIcon(QMessageBox.Warning)

        # Calculate the center position
        screen_geometry = QCoreApplication.instance().primaryScreen().geometry()
        screen_center = screen_geometry.center()
        alert.move(screen_center - alert.rect().center())

        # Display the QMessageBox
        alert.exec_()

    def toggle_idle_sound(self) -> None:
        self.play_sound_on_idle: bool = not self.play_sound_on_idle
        self.config["OPTIONS"]["play_sound_on_idle"] = str(self.play_sound_on_idle)

        if self.play_sound_on_idle:
            self.label.setText("snd on")
        else:
            self.label.setText("snd off")

    def checkbox_was_toggled(self, checked: bool) -> None:
        self.hide_time: bool = checked
        self.config["OPTIONS"]["hide_time"] = str(self.hide_time)
        self.update_label()

    def click_handler(self) -> None:
        if self.wait_to_add_program is True:
            self.add_program()
        elif self.wait_to_remove_program is True:
            self.remove_program()

        self.wait_to_add_program = False
        self.wait_to_remove_program = False

    def eventFilter(self, a0: QObject, a1: QEvent) -> bool:
        source = a0
        event = a1

        if event.type() == QEvent.WindowDeactivate:
            self.click_handler()

        if isinstance(event, QKeyEvent) and event.key() == Qt.Key_Escape:
            self.wait_to_add_program = False
            self.wait_to_remove_program = False

        return super().eventFilter(source, event)

    def closeEvent(self, a0: QEvent):
        event = a0
        self.save_data()


app: QApplication = QApplication([])
window: MainWindow = MainWindow()
sys.excepthook = window.handle_exception
window.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
window.show()

app.exec()

