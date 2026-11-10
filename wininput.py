"""Win32 input helpers: a low-level mouse hook that blocks the mouse inside a screen
rectangle, and forcing a window to the foreground.

Coordinates are physical pixels, the same space as GetCursorPos / SetCursorPos.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_MOUSE_LL = 14
HC_ACTION = 0

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


WM_MOUSEMOVE = 0x0200

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL


class MouseBlocker:
    """Keeps mouse events inside `rect` from reaching any application.

    The low-level hook sees every mouse event before windows and other hooks do.
    Inside the rectangle:
    - movement is swallowed, and the cursor is repositioned with SetCursorPos instead,
      so the pointer still moves normally but no hook or window receives the event;
    - buttons and wheel are swallowed outright.
    Outside the rectangle everything passes through untouched.

    Must be used from a thread that runs a Windows message loop (the Qt GUI thread).
    """

    def __init__(self) -> None:
        self._hook: Optional[int] = None
        self._rect: Optional[tuple[int, int, int, int]] = None  # left, top, right, bottom
        self._proc = HOOKPROC(self._callback)  # keep a reference; ctypes must not free it

    @property
    def active(self) -> bool:
        return self._hook is not None

    def block(self, left: int, top: int, right: int, bottom: int) -> None:
        self._rect = (left, top, right, bottom)
        if self._hook is None:
            hmod = kernel32.GetModuleHandleW(None)
            self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, hmod, 0)
            if not self._hook:
                self._hook = None
                raise ctypes.WinError(ctypes.get_last_error())

    def release(self) -> None:
        self._rect = None
        if self._hook is not None:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def _callback(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code == HC_ACTION and self._rect is not None:
            info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            left, top, right, bottom = self._rect
            if left <= info.pt.x < right and top <= info.pt.y < bottom:
                if w_param == WM_MOUSEMOVE:
                    # SetCursorPos does not go through low-level hooks, so this moves the
                    # pointer without the event ever being seen by anyone else.
                    user32.SetCursorPos(info.pt.x, info.pt.y)
                return 1  # swallow
        return user32.CallNextHookEx(None, n_code, w_param, l_param)


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL

_pid_names: dict[int, str] = {}


def process_name_of_window(hwnd: int) -> str:
    """Lower-case executable name (e.g. 'sharex.exe') owning `hwnd`, or '' if unknown."""
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    cached = _pid_names.get(pid.value)
    if cached is not None:
        return cached
    name = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = buf.value.rsplit("\\", 1)[-1].lower()
        finally:
            kernel32.CloseHandle(handle)
    if len(_pid_names) > 256:
        _pid_names.clear()
    _pid_names[pid.value] = name
    return name


def foreground_process_name() -> str:
    return process_name_of_window(user32.GetForegroundWindow())


GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x8


def foreground_window_info() -> tuple[str, bool, tuple[int, int, int, int]]:
    """(process exe name, is topmost, window rect) of the foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", False, (0, 0, 0, 0)
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return process_name_of_window(hwnd), bool(ex & WS_EX_TOPMOST), (r.left, r.top, r.right, r.bottom)


def set_topmost(hwnd: int, topmost: bool) -> None:
    user32.SetWindowPos(
        hwnd, HWND_TOPMOST if topmost else HWND_NOTOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


def force_foreground(hwnd: int) -> None:
    """Bring `hwnd` to the foreground even when another process owns the foreground.

    Windows refuses SetForegroundWindow from a background process; attaching to the
    foreground thread's input queue for the call is the standard workaround.
    """
    fg = user32.GetForegroundWindow()
    cur_thread = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = False
    if fg_thread and fg_thread != cur_thread:
        attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
