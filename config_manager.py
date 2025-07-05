import os
import json
from PyQt6.QtCore import QSettings, QByteArray


class ConfigManager:
    """Manages configuration settings for the work timer application.

    This class encapsulates all functionality related to reading, writing,
    and managing application configuration settings, including:

    - Window position and geometry
    - Idle detection timeout
    - Goal time tracking
    - Previous time tracking
    - Sound and visual indicator preferences
    - Keyboard shortcut configuration
    - Tracked programs list
    """

    def __init__(self, settings_file: str = "qsettings.ini"):
        """Initialize the configuration manager.

        Args:
            settings_file: The filename for the settings INI file
        """
        self.settings = QSettings(settings_file, QSettings.Format.IniFormat)
        self._load_settings()

    def _load_settings(self) -> None:
        """Load all settings from the configuration file."""
        # Options group
        self.settings.beginGroup("Options")

        # Load idle timeout with error handling
        try:
            self.idle_timeout: int = self.settings.value("idle_timeout", 30, type=int)
        except Exception:
            self.idle_timeout = 30
            self.settings.setValue("idle_timeout", 30)
            print("Invalid idle timeout in qsettings.ini, using default value")

        # Load goal time with error handling
        try:
            self.goal_time: int = self.settings.value("goal_time", 0, type=int)
        except Exception:
            self.goal_time = 0
            self.settings.setValue("goal_time", 0)
            print("Invalid goal time in qsettings.ini, using default value")

        # Load previous time with error handling
        try:
            self.previous_time: int = self.settings.value("previous_time", 0, type=int)
        except Exception:
            self.previous_time = 0
            self.settings.setValue("previous_time", 0)
            print("Invalid previous time in qsettings.ini, using default value")

        # Load boolean options
        self.play_sound_on_idle: bool = self.settings.value(
            "play_sound_on_idle", True, type=bool
        )
        self.show_border_when_not_working: bool = self.settings.value(
            "show_border_when_not_working", True, type=bool
        )

        # Load hotkeys
        self.add_program_hotkey: str = self.settings.value(
            "add_program_hotkey", "win+shift+="
        )
        self.remove_program_hotkey: str = self.settings.value(
            "remove_program_hotkey", "win+shift+-"
        )

        self.settings.endGroup()

        # Load tracked programs
        self.tracked_programs: dict[str, str] = self._load_tracked_programs()
        
        # Load time history
        self.time_history: list[int] = self._load_time_history()

    def _load_tracked_programs(self) -> dict[str, str]:
        """Load the tracked programs list from settings.

        Returns:
            A dictionary mapping executable paths to program names
        """
        self.settings.beginGroup("Programs")
        programs = {key: self.settings.value(key) for key in self.settings.childKeys()}
        self.settings.endGroup()
        
        # Add explorer.exe as default tracked program for new users
        if not programs:
            explorer_path = "C:\\Windows\\explorer.exe"
            programs[explorer_path] = "explorer.exe"
            self.settings.setValue("Programs/" + explorer_path, "explorer.exe")
        
        return programs

    def save_window_geometry(self, geometry: QByteArray) -> None:
        """Save the window geometry to settings.

        Args:
            geometry: The window geometry to save
        """
        self.settings.setValue("geometry", geometry)

    def load_window_geometry(self) -> QByteArray | None:
        """Load the window geometry from settings.

        Returns:
            The stored window geometry or None if not set
        """
        if self.settings.contains("geometry"):
            return self.settings.value("geometry")
        return None

    def save_previous_time(self, seconds: int) -> None:
        """Save the previous time value to settings.

        Args:
            seconds: The time in seconds to save
        """
        self.previous_time = seconds
        self.settings.setValue("Options/previous_time", seconds)

    def set_idle_timeout(self, seconds: int) -> None:
        """Set the idle timeout value.

        Args:
            seconds: The idle timeout in seconds
        """
        self.idle_timeout = seconds
        self.settings.setValue("Options/idle_timeout", seconds)

    def set_goal_time(self, seconds: int) -> None:
        """Set the goal time value.

        Args:
            seconds: The goal time in seconds
        """
        self.goal_time = seconds
        self.settings.setValue("Options/goal_time", seconds)

    def toggle_idle_sound(self) -> bool:
        """Toggle the idle sound setting.

        Returns:
            The new state of the setting
        """
        self.play_sound_on_idle = not self.play_sound_on_idle
        self.settings.setValue("Options/play_sound_on_idle", self.play_sound_on_idle)
        return self.play_sound_on_idle

    def toggle_border_setting(self) -> bool:
        """Toggle the border indicator setting.

        Returns:
            The new state of the setting
        """
        self.show_border_when_not_working = not self.show_border_when_not_working
        self.settings.setValue(
            "Options/show_border_when_not_working", self.show_border_when_not_working
        )
        return self.show_border_when_not_working

    def add_tracked_program(self, exe_path: str) -> None:
        """Add a program to the tracked programs list.

        Args:
            exe_path: The full path to the executable
        """
        program_name = os.path.basename(exe_path)
        self.tracked_programs[exe_path] = program_name
        self.settings.setValue("Programs/" + exe_path, program_name)

    def remove_tracked_program(self, exe_path: str) -> None:
        """Remove a program from the tracked programs list.

        Args:
            exe_path: The full path to the executable
        """
        if exe_path in self.tracked_programs:
            self.settings.remove("Programs/" + exe_path)
            del self.tracked_programs[exe_path]

    def is_program_tracked(self, exe_path: str) -> bool:
        """Check if a program is in the tracked programs list.

        Args:
            exe_path: The full path to the executable

        Returns:
            True if the program is tracked, False otherwise
        """
        return exe_path in self.tracked_programs

    def set_add_program_hotkey(self, hotkey: str) -> None:
        """Set the add program hotkey.
        
        Args:
            hotkey: The new hotkey string
        """
        self.add_program_hotkey = hotkey
        self.settings.setValue("Options/add_program_hotkey", hotkey)
        
    def set_remove_program_hotkey(self, hotkey: str) -> None:
        """Set the remove program hotkey.
        
        Args:
            hotkey: The new hotkey string
        """
        self.remove_program_hotkey = hotkey
        self.settings.setValue("Options/remove_program_hotkey", hotkey)
    
    def _load_time_history(self) -> list[int]:
        """Load the time history from settings.
        
        Returns:
            A list of previous times in seconds (max 5 entries)
        """
        try:
            history_str = self.settings.value("Options/time_history", "[]")
            history = json.loads(history_str)
            # Ensure it's a list of integers and limit to 5 entries
            if isinstance(history, list):
                return [int(t) for t in history if isinstance(t, (int, float)) and t > 0][-5:]
            return []
        except (json.JSONDecodeError, ValueError, TypeError):
            return []
    
    def add_time_to_history(self, seconds: int) -> None:
        """Add a time to the history, maintaining max 5 entries.
        
        Args:
            seconds: The time in seconds to add to history
        """
        if seconds <= 0:
            return  # Don't save 0 or negative times
        
        # Remove duplicate if it exists
        if seconds in self.time_history:
            self.time_history.remove(seconds)
        
        # Add new time at the end
        self.time_history.append(seconds)
        
        # Keep only the last 5 entries
        if len(self.time_history) > 5:
            self.time_history = self.time_history[-5:]
        
        # Save to settings
        self.settings.setValue("Options/time_history", json.dumps(self.time_history))
    
    def get_time_history(self) -> list[int]:
        """Get the current time history.
        
        Returns:
            A list of previous times in seconds (newest first)
        """
        return list(reversed(self.time_history))
