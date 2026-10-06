"""Native Windows title-bar styling; safe no-op on unsupported systems."""
import sys


def style_title_bar(window):
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        window.update_idletasks()
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        dwm = ctypes.WinDLL('dwmapi', use_last_error=True)
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = user32.GetAncestor(window.winfo_id(), 2)
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        dark = wintypes.BOOL(1)
        if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark)) != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
        # COLORREF is 0x00BBGGRR: caption #28143f; text #f5efff.
        caption = wintypes.DWORD(0x003f1428)
        text = wintypes.DWORD(0x00ffeff5)
        border = wintypes.DWORD(0x00532f39)
        result = dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), ctypes.sizeof(border))
        return result == 0
    except (OSError, AttributeError, ValueError):
        return False
