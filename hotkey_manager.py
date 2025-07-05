"""
Global-hotkey helper for PyQt6 on Windows
========================================

Register system-wide shortcuts via the Win32 RegisterHotKey API and forward the
events into the Qt event loop.

- Supports every key found on a standard US keyboard (main row, function row,
  navigation cluster, num-pad, punctuation, etc.).
- No 3rd-party packages required beyond PyQt6 and pywin32.
"""

import logging
from ctypes import WinError, get_last_error, windll, wintypes
from typing import Callable

import win32con
from PyQt6.QtCore import (
    QAbstractEventDispatcher,
    QAbstractNativeEventFilter,
    QTimer,
    Qt,
)
from PyQt6.QtGui import QKeySequence


# Virtual-key constants – fall back to literal values if win32con lacks them
def _vk(name: str, fallback: int) -> int:
    """Return win32con.VK_* if present, else the literal fallback."""
    return getattr(win32con, name, fallback)

# Punctuation & OEM keys
VK_OEM_1        = _vk("VK_OEM_1",        0xBA)  # ; :
VK_OEM_PLUS     = _vk("VK_OEM_PLUS",     0xBB)  # = +
VK_OEM_COMMA    = _vk("VK_OEM_COMMA",    0xBC)  # , <
VK_OEM_MINUS    = _vk("VK_OEM_MINUS",    0xBD)  # - _
VK_OEM_PERIOD   = _vk("VK_OEM_PERIOD",   0xBE)  # . >
VK_OEM_2        = _vk("VK_OEM_2",        0xBF)  # / ?
VK_OEM_3        = _vk("VK_OEM_3",        0xC0)  # ` ~
VK_OEM_4        = _vk("VK_OEM_4",        0xDB)  # [ {
VK_OEM_5        = _vk("VK_OEM_5",        0xDC)  # \ |
VK_OEM_6        = _vk("VK_OEM_6",        0xDD)  # ] }
VK_OEM_7        = _vk("VK_OEM_7",        0xDE)  # ' "

# Numeric keypad
VK_NUMPAD0      = _vk("VK_NUMPAD0",      0x60)
VK_NUMPAD1      = _vk("VK_NUMPAD1",      0x61)
VK_NUMPAD2      = _vk("VK_NUMPAD2",      0x62)
VK_NUMPAD3      = _vk("VK_NUMPAD3",      0x63)
VK_NUMPAD4      = _vk("VK_NUMPAD4",      0x64)
VK_NUMPAD5      = _vk("VK_NUMPAD5",      0x65)
VK_NUMPAD6      = _vk("VK_NUMPAD6",      0x66)
VK_NUMPAD7      = _vk("VK_NUMPAD7",      0x67)
VK_NUMPAD8      = _vk("VK_NUMPAD8",      0x68)
VK_NUMPAD9      = _vk("VK_NUMPAD9",      0x69)
VK_MULTIPLY     = _vk("VK_MULTIPLY",     0x6A)
VK_ADD          = _vk("VK_ADD",          0x6B)
VK_SEPARATOR    = _vk("VK_SEPARATOR",    0x6C)
VK_SUBTRACT     = _vk("VK_SUBTRACT",     0x6D)
VK_DECIMAL      = _vk("VK_DECIMAL",      0x6E)
VK_DIVIDE       = _vk("VK_DIVIDE",       0x6F)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hotkey")


class HotkeyManager(QAbstractNativeEventFilter):
    """
    Global-hotkey registrar for PyQt 6 applications (Windows only).

    Example
    -------
    >>> hk = HotkeyManager()
    >>> hk.register("ctrl+alt+f9", lambda: print("Boom!"))
    """

    _MODS: dict[str, int] = {
        "ctrl":  win32con.MOD_CONTROL,
        "alt":   win32con.MOD_ALT,
        "shift": win32con.MOD_SHIFT,
        "win":   win32con.MOD_WIN,
    }

    # Life-cycle ---------------------------------------------------------------
    def __init__(self) -> None:
        """Initialize the hotkey manager and install the native event filter."""
        super().__init__()
        self._id_to_cb: dict[int, Callable[[], None]] = {}
        QAbstractEventDispatcher.instance().installNativeEventFilter(self)

    def unregister_all(self) -> None:
        """Release every hot-key that was registered by this instance."""
        for _id in list(self._id_to_cb):
            windll.user32.UnregisterHotKey(None, _id)
        self._id_to_cb.clear()
        QAbstractEventDispatcher.instance().removeNativeEventFilter(self)

    def replace_hotkey(self, old_sequence: str, new_sequence: str, callback: Callable[[], None]) -> None:
        """
        Replace an existing hotkey with a new one without removing the event filter.
        
        Args:
            old_sequence: The current hotkey sequence to replace
            new_sequence: The new hotkey sequence
            callback: Function to execute when the new hotkey is pressed
            
        Raises:
            RuntimeError: If the new hotkey registration fails or input is invalid
        """
        # Parse and validate the new sequence first
        try:
            new_mods, new_vk = self._parse(new_sequence.lower())
        except ValueError as e:
            raise RuntimeError(f"Invalid hotkey format '{new_sequence}': {str(e)}")
        
        # Find and unregister the old hotkey
        try:
            old_mods, old_vk = self._parse(old_sequence.lower())
        except ValueError:
            # If we can't parse the old sequence, just continue without unregistering
            old_mods, old_vk = 0, 0
        
        old_id = None
        for hotkey_id, cb in self._id_to_cb.items():
            if cb == callback:
                old_id = hotkey_id
                break
        
        if old_id is not None:
            windll.user32.UnregisterHotKey(None, old_id)
            del self._id_to_cb[old_id]
        
        # Register the new hotkey - find an unused ID
        new_id = 1
        while new_id in self._id_to_cb:
            new_id += 1
        
        if not windll.user32.RegisterHotKey(None, new_id, new_mods, new_vk):
            err = get_last_error()
            error_msg = WinError(err).strerror
            log.error("RegisterHotKey %s FAILED  (mods=%#x vk=%#x)  → %s",
                      new_sequence, new_mods, new_vk, error_msg)
            
            # If registration failed, try to re-register the old hotkey
            if old_id is not None and old_mods != 0 and old_vk != 0:
                try:
                    windll.user32.RegisterHotKey(None, old_id, old_mods, old_vk)
                    self._id_to_cb[old_id] = callback
                except:
                    pass  # If we can't restore the old hotkey, just continue
            
            # Provide user-friendly error messages
            if "already registered" in error_msg.lower():
                raise RuntimeError(f"Hotkey '{new_sequence}' is already registered by another application or hotkey")
            else:
                raise RuntimeError(f"Failed to register hotkey '{new_sequence}': {error_msg}")
        
        self._id_to_cb[new_id] = callback
        log.debug("Replaced hot-key %s with %s (mods=%#x vk=%#x id=%d)",
                  old_sequence, new_sequence, new_mods, new_vk, new_id)

    # Public API ---------------------------------------------------------------
    def register(self, sequence: str, callback: Callable[[], None]) -> None:
        """
        Register a key sequence as a global shortcut.
        
        Args:
            sequence: Human-readable key string - e.g. `ctrl+alt+numpad5` or `win+shift+f12`
            callback: Function executed on the Qt main thread when the hot-key is pressed.
            
        Raises:
            RuntimeError: If registration fails
        """
        mods, vk = self._parse(sequence.lower())
        # Find an unused ID
        hotkey_id = 1
        while hotkey_id in self._id_to_cb:
            hotkey_id += 1
        if not windll.user32.RegisterHotKey(None, hotkey_id, mods, vk):
            err = get_last_error()
            log.error("RegisterHotKey %s FAILED  (mods=%#x vk=%#x)  → %s",
                      sequence, mods, vk, WinError(err).strerror)
            raise RuntimeError(f"RegisterHotKey failed for {sequence!r}: {err}")
        self._id_to_cb[hotkey_id] = callback
        log.debug("Registered hot-key %s (mods=%#x vk=%#x id=%d)",
                  sequence, mods, vk, hotkey_id)

    # Native event -------------------------------------------------------------
    def nativeEventFilter(
        self, event_type: bytes | str, message: int
    ) -> tuple[bool, int]:
        """
        Intercept WM_HOTKEY and forward it to the registered callback.
        
        Args:
            event_type: Type of the native event
            message: Native message pointer
            
        Returns:
            tuple: (event_handled, result)
        """
        if event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
            return False, 0

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == win32con.WM_HOTKEY:
            cb = self._id_to_cb.get(msg.wParam)
            if cb:
                # Callback on Qt's main thread, non-blocking
                QTimer.singleShot(0, cb)
            return True, 1  # Event handled
        return False, 0  # Let Qt continue processing

    # Helpers ------------------------------------------------------------------
    # Full mapping for US-keyboard punctuation & control keys
    _QT_TO_VK: dict[Qt.Key, int] = {
        # Punctuation
        Qt.Key.Key_Equal:          VK_OEM_PLUS,
        Qt.Key.Key_Plus:           VK_OEM_PLUS,
        Qt.Key.Key_Minus:          VK_OEM_MINUS,
        Qt.Key.Key_Underscore:     VK_OEM_MINUS,
        Qt.Key.Key_Comma:          VK_OEM_COMMA,
        Qt.Key.Key_Period:         VK_OEM_PERIOD,
        Qt.Key.Key_Slash:          VK_OEM_2,
        Qt.Key.Key_Backslash:      VK_OEM_5,
        Qt.Key.Key_Semicolon:      VK_OEM_1,
        Qt.Key.Key_Apostrophe:     VK_OEM_7,
        Qt.Key.Key_QuoteLeft:      VK_OEM_3,
        Qt.Key.Key_BracketLeft:    VK_OEM_4,
        Qt.Key.Key_BracketRight:   VK_OEM_6,

        # Whitespace & control
        Qt.Key.Key_Space:          win32con.VK_SPACE,
        Qt.Key.Key_Return:         win32con.VK_RETURN,
        Qt.Key.Key_Enter:          win32con.VK_RETURN,
        Qt.Key.Key_Tab:            win32con.VK_TAB,
        Qt.Key.Key_Backspace:      win32con.VK_BACK,
        Qt.Key.Key_Escape:         win32con.VK_ESCAPE,
        Qt.Key.Key_Delete:         win32con.VK_DELETE,
        Qt.Key.Key_Insert:         win32con.VK_INSERT,

        # Navigation
        Qt.Key.Key_Home:           win32con.VK_HOME,
        Qt.Key.Key_End:            win32con.VK_END,
        Qt.Key.Key_PageUp:         win32con.VK_PRIOR,
        Qt.Key.Key_PageDown:       win32con.VK_NEXT,
        Qt.Key.Key_Left:           win32con.VK_LEFT,
        Qt.Key.Key_Up:             win32con.VK_UP,
        Qt.Key.Key_Right:          win32con.VK_RIGHT,
        Qt.Key.Key_Down:           win32con.VK_DOWN,

        # Locks
        Qt.Key.Key_CapsLock:       win32con.VK_CAPITAL,
        Qt.Key.Key_NumLock:        win32con.VK_NUMLOCK,
        Qt.Key.Key_ScrollLock:     win32con.VK_SCROLL,
    }

    # Named keys that are *not* directly representable by a printable character
    # or by Qt's key codes
    _NAMED_KEYS: dict[str, int] = {
        # Navigation / editing
        "insert":           win32con.VK_INSERT,
        "delete":           win32con.VK_DELETE,
        "home":             win32con.VK_HOME,
        "end":              win32con.VK_END,
        "pageup":           win32con.VK_PRIOR,
        "pgup":             win32con.VK_PRIOR,
        "pagedown":         win32con.VK_NEXT,
        "pgdn":             win32con.VK_NEXT,
        "left":             win32con.VK_LEFT,
        "right":            win32con.VK_RIGHT,
        "up":               win32con.VK_UP,
        "down":             win32con.VK_DOWN,

        # Punctuation (word alternatives)
        "comma":            VK_OEM_COMMA,
        "period":           VK_OEM_PERIOD,
        "dot":              VK_OEM_PERIOD,
        "slash":            VK_OEM_2,
        "backslash":        VK_OEM_5,
        "semicolon":        VK_OEM_1,
        "apostrophe":       VK_OEM_7,
        "quote":            VK_OEM_7,
        "tilde":            VK_OEM_3,
        "grave":            VK_OEM_3,
        "lbracket":         VK_OEM_4,
        "rbracket":         VK_OEM_6,
        "minus":            VK_OEM_MINUS,
        "equals":           VK_OEM_PLUS,

        # System
        "esc":              win32con.VK_ESCAPE,
        "escape":           win32con.VK_ESCAPE,
        "space":            win32con.VK_SPACE,
        "backspace":        win32con.VK_BACK,
        "tab":              win32con.VK_TAB,
        "enter":            win32con.VK_RETURN,
        "return":           win32con.VK_RETURN,

        # Num-pad (aliases numpad0-9, *, /, +, -, ., enter)
        "numpad0":          VK_NUMPAD0,
        "numpad1":          VK_NUMPAD1,
        "numpad2":          VK_NUMPAD2,
        "numpad3":          VK_NUMPAD3,
        "numpad4":          VK_NUMPAD4,
        "numpad5":          VK_NUMPAD5,
        "numpad6":          VK_NUMPAD6,
        "numpad7":          VK_NUMPAD7,
        "numpad8":          VK_NUMPAD8,
        "numpad9":          VK_NUMPAD9,
        "numpadmultiply":   VK_MULTIPLY,
        "numpaddivide":     VK_DIVIDE,
        "numpadplus":       VK_ADD,
        "numpadminus":      VK_SUBTRACT,
        "numpaddecimal":    VK_DECIMAL,
        "numpadenter":      win32con.VK_RETURN,
    }

    def _qt_to_vk(self, qt_enum: Qt.Key) -> int:
        """
        Convert a Qt.Key value to the corresponding Windows virtual-key code.
        
        Args:
            qt_enum: The Qt key enum value
            
        Returns:
            int: The Windows virtual-key code, or 0 if no direct match is available
        """
        val = int(qt_enum)  # Raw integer behind the enum

        # 0-9 and A-Z are numerically identical between Qt and Windows
        if int(Qt.Key.Key_0) <= val <= int(Qt.Key.Key_9) or \
           int(Qt.Key.Key_A) <= val <= int(Qt.Key.Key_Z):
            return val

        # Function keys
        if int(Qt.Key.Key_F1) <= val <= int(Qt.Key.Key_F24):
            return win32con.VK_F1 + (val - int(Qt.Key.Key_F1))

        return self._QT_TO_VK.get(qt_enum, 0)   # 0 ⇒ unknown

    def _parse(self, seq: str) -> tuple[int, int]:
        """
        Translate a key sequence into Win32 (modifier, vkCode) for RegisterHotKey().
        
        Args:
            seq: A key sequence like `ctrl+alt+f9` or `shift+comma`
            
        Returns:
            tuple: (modifiers, vkCode) suitable for RegisterHotKey()
            
        Raises:
            ValueError: If key name cannot be interpreted
        """
        parts = seq.lower().split("+")
        key_name = parts[-1]
        mods = 0
        for part in parts[:-1]:
            mods |= self._MODS.get(part, 0)

        # Named-key dictionary
        vk = self._NAMED_KEYS.get(key_name, 0)

        # Qt translation (letters, digits, function keys, punctuation, etc.)
        if vk == 0:
            qseq = QKeySequence(key_name)
            if qseq.count():
                vk = self._qt_to_vk(qseq[0].key())
                log.debug("Qt-key %-10s → qt=0x%X → vk=0x%X",
                          key_name, int(qseq[0].key()), vk)

        # VkKeyScanW for any printable single character still unresolved
        if vk == 0 and len(key_name) == 1:
            vk = windll.user32.VkKeyScanW(ord(key_name)) & 0xFF
            log.debug("VkKeyScanW(%s) → vk=0x%X", key_name, vk)

        if vk == 0:
            raise ValueError(f"Unable to interpret key name {key_name!r}")

        return mods, vk
