import psutil
import win32gui
import win32process
import configparser
from ctypes import Structure, windll, c_uint, sizeof, byref
from PyQt5.QtCore import QSize, Qt, QEvent, QTimer
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QPushButton, QLabel, QCheckBox, QHBoxLayout, QMenu, QInputDialog
from PyQt5.QtGui import QFont, QFontDatabase

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # delimeters set to only "=" becuase ":" is used in the path
        self.config = configparser.ConfigParser(delimiters=('=',))
        self.config.read('settings.ini')
        if 'OPTIONS' not in self.config.sections():
            self.config['OPTIONS'] = {}
            self.config['OPTIONS']['idle_timeout'] = '30'
        if 'PROGRAMS' not in self.config.sections():
            self.config['PROGRAMS'] = {}
        self.idle_timeout = self.config['OPTIONS']['idle_timeout']
        self.tracked_programs = self.config['PROGRAMS']

        self.wait_to_add_program = False
        self.wait_to_remove_program = False

        self.setWindowTitle("WORK WORK")
        self.setFixedSize(QSize(205, 39))
        self.setObjectName("MainWindow")
        self.change_background_color("#F07070")
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.timer = 0
        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)

        self.current_time = '00:00:00'
        self.label = QLabel(self.current_time, self)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        digital_font_id = QFontDatabase.addApplicationFont("digital-7-mono.ttf")
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
        try:
            active_window_handle = win32gui.GetForegroundWindow()
            _, process_id = win32process.GetWindowThreadProcessId(active_window_handle)
            program = psutil.Process(process_id)
            return program
        except:
            return None

    def update_time(self):
        active_program_path = self.get_active_program().exe()

        if active_program_path in self.tracked_programs and self.is_idle() == False:
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

        if self.label.text() == '404':
            # changes display back the next timer tick for readability
            self.label.setText(' 404')
        elif not self.wait_to_add_program and not self.wait_to_remove_program:
            self.update_display()

    def update_display(self):
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

        idle_timeout_item = self.menu.addAction(f'Timeout: {self.idle_timeout}')
        idle_timeout_item.triggered.connect(self.set_idle_timeout)
        self.menu.addSeparator()

        add_program_item = self.menu.addAction('Add program')
        add_program_item.triggered.connect(self.add_program)
        remove_program_item = self.menu.addAction('Remove program')
        remove_program_item.triggered.connect(self.remove_program)
        self.menu.addSeparator()

        resume_previous_time_item = self.menu.addAction("Resume previous time")
        resume_previous_time_item.triggered.connect(self.resume_previous_time)

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
        # -----------------------------------------------------------------------

        if get_idle_duration() >= int(self.idle_timeout):
            return True
        else:
            return False

    def set_idle_timeout(self):
        dialog_box = QInputDialog(self)
        # remove question mark from the title bar
        dialog_box.setWindowFlags(dialog_box.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowCloseButtonHint)
        dialog_box.setInputMode(QInputDialog.IntInput)
        dialog_box.setIntRange(1, 99999)
        dialog_box.setIntValue(int(self.idle_timeout))
        dialog_box.setLabelText('Ender new idle timeout:')
        dialog_box.setWindowTitle('Idle Setting')

        if dialog_box.exec() == QInputDialog.Accepted:
            new_timeout = dialog_box.intValue()
            self.idle_timeout = new_timeout

    def add_program(self):
        self.wait_to_add_program = True
        # click then handled by eventFilter
        self.label.setText('add prog')

    def remove_program(self):
        self.wait_to_remove_program = True
        # click then handled by eventFilter
        self.label.setText('rem prog')

    def resume_previous_time(self):
        pass

    def checkbox_was_toggled(self, checked):
        self.hide_time = checked
        self.update_display()

    def eventFilter(self, source, event):
        if event.type() == QEvent.WindowDeactivate:
            last_clicked = self.get_active_program()

            if last_clicked == None:
                pass
            elif self.wait_to_add_program == True:
                self.tracked_programs[last_clicked.exe()] = last_clicked.name()
                self.update_display()
                self.wait_to_add_program = False
            elif self.wait_to_remove_program == True:
                if last_clicked.exe() in self.tracked_programs:
                    self.config.remove_option('PROGRAMS',
                                              last_clicked.exe())
                    self.update_display()
                else:
                    self.label.setText('404')
                self.wait_to_remove_program = False

        return super().eventFilter(source, event)

    def closeEvent(self, event):
        with open('settings.ini', 'w') as configfile:
            self.config.write(configfile)

app = QApplication([])
window = MainWindow()
window.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
window.show()

app.exec()
