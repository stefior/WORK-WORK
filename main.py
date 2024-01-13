import os
import sys
import psutil
import win32gui
import win32process
import configparser
import keyboard
import simpleaudio
from time import sleep
from ctypes import Structure, windll, c_uint, sizeof, byref
from PyQt5.QtCore import QSize, Qt, QEvent, QTimer
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget, QPushButton,
                             QLabel, QCheckBox, QHBoxLayout, QMenu,
                             QInputDialog)
from PyQt5.QtGui import QFont, QFontDatabase, QPainter, QColor, QPen, QIcon


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(
        os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


alert_path = resource_path('alert.wav')
font_path = resource_path('digital-7-mono.ttf')
icon_path = resource_path('timericon.ico')


class BorderWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Get combined screen geometry
        desktop = QApplication.desktop()
        rect = desktop.screenGeometry(0)  # Start with the geometry of the first screen
        for i in range(1, desktop.screenCount()):
            rect = rect.united(desktop.screenGeometry(
                i))  # Union the geometries of all screens

        # if all monitors aren't aligned it doesn't cover all perimeters
        # but it's good enough to fulfill it's purpose
        self.setGeometry(rect)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.show()

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        self.drawBorder(qp)
        qp.end()

    def drawBorder(self, qp):
        qp.setPen(QPen(QColor(240, 112, 112), 8))  # Set pen color and width
        qp.drawRect(0, 0, self.width(), self.height())  # Draw border rectangle


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # delimeters set to only "="
        # becuase ":" is used for saving the path of tracked programs
        self.config = configparser.ConfigParser(delimiters=('=', ))
        self.config.read('settings.ini')
        if 'OPTIONS' not in self.config.sections():
            self.config['OPTIONS'] = {}
            self.config['OPTIONS']['idle_timeout'] = '30'
            self.config['OPTIONS']['previous_time'] = '00:00:00'
            self.config['OPTIONS']['add_program_hotkey'] = "ctrl+win+alt+a"
            self.config['OPTIONS']['remove_program_hotkey'] = "ctrl+win+alt+r"
            self.config['OPTIONS']['play_sound_on_idle'] = "FALSE"
            self.config['OPTIONS']['show_border_on_idle'] = "FALSE"
        if 'PROGRAMS' not in self.config.sections():
            self.config['PROGRAMS'] = {}

        self.idle_timeout = self.config.getint('OPTIONS', 'idle_timeout')
        self.play_sound_on_idle = self.config['OPTIONS'][
            'play_sound_on_idle'].upper()
        self.show_border_on_idle = self.config['OPTIONS'][
            'show_border_on_idle'].upper()
        self.tracked_programs = self.config['PROGRAMS']

        keyboard.add_hotkey(self.config['OPTIONS']['add_program_hotkey'],
                            self.add_program_keyboard)
        keyboard.add_hotkey(self.config['OPTIONS']['remove_program_hotkey'],
                            self.remove_program_keyboard)

        self.seconds_since_idle_timeout = 0
        self.border_window = BorderWindow()
        self.border_window.hide()
        self.wait_to_add_program = False
        self.wait_to_remove_program = False

        self.setWindowTitle("WORK WORK")
        self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(QSize(205, 39))
        self.setObjectName("MainWindow")
        self.change_background_color("#F07070")
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)

        self.current_time = '00:00:00'
        self.label = QLabel(self.current_time, self)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        digital_font_id = QFontDatabase.addApplicationFont(font_path)
        font_families = QFontDatabase.applicationFontFamilies(digital_font_id)
        self.label.setFont(QFont(font_families[0], 24))

        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.update_menu)
        menu_button = QPushButton('MENU')
        menu_button.setMenu(self.menu)

        checkbox = QCheckBox("")
        checkbox.setCheckable(True)
        checkbox.clicked.connect(self.checkbox_was_toggled)
        self.hide_time = False

        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label)
        layout.addWidget(menu_button)
        layout.addWidget(checkbox)

        self.container = QWidget()
        self.container.installEventFilter(self)
        self.container.setLayout(layout)

        self.setCentralWidget(self.container)

    def change_background_color(self, color):
        self.setStyleSheet(f"""
            #MainWindow {{
                background-color: {color};
            }}

            QPushButton {{
                background-color: white;
                padding: 3px 6px;
                border: 1px solid black;
            }}

            QPushButton::menu-indicator {{
                width: 0;
            }}
            """)

    def get_active_program(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                active_window_handle = win32gui.GetForegroundWindow()
                _, process_id = win32process.GetWindowThreadProcessId(active_window_handle)
                if process_id > 0:  # Extra check for positive PID
                    program = psutil.Process(process_id)
                    return program
                else:
                    print(f"Invalid PID (attempt {attempt+1}): {process_id}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError) as e:
                print(f"Error getting active program (attempt {attempt+1}): {e}")
            sleep(0.2)  # Short delay before retry

        return None  # Return None if all attempts fail

    def update_time(self):
        active_program = self.get_active_program()
        active_program_path = active_program.exe() if active_program else None

        if ':' not in self.label.text():
            sleep(.5)

        if (active_program_path is not None and
                active_program_path in self.tracked_programs and
                self.is_idle() is False):

            if self.border_window.isVisible():
                self.border_window.hide()
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
        elif self.windowTitle() != "WORK WORK":
            self.change_background_color("#F07070")
            self.setWindowTitle("BACK TO WORK")

        if not self.wait_to_add_program and not self.wait_to_remove_program:
            self.update_label()

    def update_label(self):
        hh = self.hours if self.hours > 9 else '0' + str(self.hours)
        mm = self.minutes if self.minutes > 9 else '0' + str(self.minutes)
        ss = self.seconds if self.seconds > 9 else '0' + str(self.seconds)
        self.current_time = f'{hh}:{mm}:{ss}'

        if self.hide_time:
            self.label.setText("--:--:--")
        else:
            self.label.setText(self.current_time)

    def update_menu(self):
        self.menu.clear()

        add_program_item = self.menu.addAction('Add program')
        add_program_item.triggered.connect(self.add_program_mouse)
        remove_program_item = self.menu.addAction('Remove program')
        remove_program_item.triggered.connect(self.remove_program_mouse)
        self.menu.addSeparator()

        idle_timeout_item = self.menu.addAction(
            f'Timeout: {self.idle_timeout}')
        sound_state = "on" if self.play_sound_on_idle == "TRUE" else "off"
        toggle_idle_sound_item = self.menu.addAction(
            f'Idle indicator sound: {sound_state}'
        )
        idle_timeout_item.triggered.connect(self.set_idle_timeout)

        toggle_idle_sound_item.triggered.connect(self.toggle_idle_sound)
        border_state = "on" if self.show_border_on_idle == "TRUE" else "off"
        toggle_idle_border_item = self.menu.addAction(
            f'Idle indicator border: {border_state}'
        )
        toggle_idle_border_item.triggered.connect(self.toggle_idle_border)

        self.menu.addSeparator()

        resume_previous_time_item = self.menu.addAction("Resume previous time")
        resume_previous_time_item.triggered.connect(self.resume_previous_time)
        reset_time_item = self.menu.addAction("Reset time")
        reset_time_item.triggered.connect(self.reset_time)

    def toggle_idle_border(self):
        if self.show_border_on_idle == 'TRUE':
            self.config['OPTIONS']['show_border_on_idle'] = 'FALSE'
            self.show_border_on_idle = "FALSE"
            self.label.setText('brdr off')
        else:
            self.config['OPTIONS']['show_border_on_idle'] = 'TRUE'
            self.show_border_on_idle = "TRUE"
            self.label.setText('brdr on')

    def is_idle(self):
        # http://stackoverflow.com/questions/911856/detecting-idle-time-in-python
        class LASTINPUTINFO(Structure):
            _fields_ = [
                ('cbSize', c_uint),
                ('dwTime', c_uint),
            ]

        def get_idle_duration():
            lastInputInfo = LASTINPUTINFO()
            lastInputInfo.cbSize = sizeof(lastInputInfo)
            windll.user32.GetLastInputInfo(byref(lastInputInfo))
            millis = windll.kernel32.GetTickCount() - lastInputInfo.dwTime
            return millis / 1000

        # ----------------------------------------------------------------------

        if get_idle_duration() >= self.idle_timeout:
            if self.show_border_on_idle == "TRUE":
                self.border_window.show()

            if (self.play_sound_on_idle == "TRUE" and
                    self.seconds_since_idle_timeout == 0):
                wave_obj = simpleaudio.WaveObject.from_wave_file(alert_path)
                wave_obj.play()
                self.seconds_since_idle_timeout += 1

            return True
        else:
            self.seconds_since_idle_timeout = 0
            return False

    def set_idle_timeout(self):
        dialog_box = QInputDialog(self)
        # remove question mark from the title bar
        dialog_box.setWindowFlags(dialog_box.windowFlags()
                                  & ~Qt.WindowContextHelpButtonHint
                                  | Qt.WindowCloseButtonHint)
        dialog_box.setInputMode(QInputDialog.IntInput)
        dialog_box.setIntRange(1, 99999)
        dialog_box.setIntValue(self.idle_timeout)
        dialog_box.setLabelText('Ender new idle timeout:')
        dialog_box.setWindowTitle('Idle Setting')

        if dialog_box.exec() == QInputDialog.Accepted:
            new_timeout = dialog_box.intValue()
            self.idle_timeout = new_timeout
            self.config['OPTIONS']['idle_timeout'] = str(new_timeout)

    def is_self_focused(self):
        if self.isActiveWindow():
            return True
        else:
            return any(
                widget.isActiveWindow() for
                widget in self.findChildren(QWidget)
            )

    def add_program_keyboard(self):
        current_program = self.get_active_program()
        current_program_exe = current_program.exe()
        if current_program is None or self.is_self_focused():
            return

        if current_program_exe in self.tracked_programs:
            self.label.setText('already+')
        else:
            self.tracked_programs[current_program_exe] = current_program.name()
            self.label.setText('added')

    def remove_program_keyboard(self):
        current_program = self.get_active_program()
        current_program_exe = current_program.exe()
        if current_program is None or self.is_self_focused():
            return

        if current_program_exe in self.tracked_programs:
            self.config.remove_option('PROGRAMS', current_program_exe)
            self.label.setText('removed')
        else:
            self.label.setText('already-')

    def add_program_mouse(self):
        self.wait_to_add_program = True
        # click then handled by eventFilter
        self.label.setText('add prog')

    def remove_program_mouse(self):
        self.wait_to_remove_program = True
        # click then handled by eventFilter
        self.label.setText('rem prog')

    def resume_previous_time(self):
        previous_time = self.config['OPTIONS']['previous_time'].split(':')
        self.hours = int(previous_time[0])
        self.minutes = int(previous_time[1])
        self.seconds = int(previous_time[2])
        self.update_label()

    def reset_time(self):
        with open('settings.ini', 'w') as configfile:
            self.config['OPTIONS']['previous_time'] = self.current_time
            self.config.write(configfile)
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.update_label()

    def toggle_idle_sound(self):
        if self.play_sound_on_idle == 'TRUE':
            self.config['OPTIONS']['play_sound_on_idle'] = "FALSE"
            self.play_sound_on_idle = "FALSE"
            self.label.setText('snd off')
        else:
            self.config['OPTIONS']['play_sound_on_idle'] = "TRUE"
            self.play_sound_on_idle = "TRUE"
            self.label.setText('snd on')

    def checkbox_was_toggled(self, checked):
        self.hide_time = checked
        self.update_label()

    def click_handler(self):
        last_clicked = self.get_active_program()
        if last_clicked is None:
            return
        last_clicked_exe = last_clicked.exe()

        if self.wait_to_add_program is True:
            if last_clicked_exe in self.tracked_programs:
                self.label.setText('already+')
            else:
                self.tracked_programs[last_clicked_exe] = last_clicked.name()
                self.label.setText('added')
            self.wait_to_add_program = False
        elif self.wait_to_remove_program is True:
            if last_clicked_exe in self.tracked_programs:
                self.config.remove_option('PROGRAMS', last_clicked_exe)
                self.label.setText('removed')
            else:
                self.label.setText('already-')
            self.wait_to_remove_program = False

    def eventFilter(self, source, event):
        if event.type() == QEvent.WindowDeactivate:
            self.click_handler()

        return super().eventFilter(source, event)

    def closeEvent(self, event):
        with open('settings.ini', 'w') as configfile:
            self.config['OPTIONS']['previous_time'] = self.current_time
            self.config.write(configfile)


app = QApplication([])
window = MainWindow()
window.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
window.show()

app.exec()
