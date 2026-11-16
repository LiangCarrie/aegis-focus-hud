"""A premultiplied-alpha Windows surface, backed by one reusable DIB.

Unlike Tk's color key, this preserves translucent glass and antialiased light.
The window never activates and Windows routes mouse events to the app beneath it.
"""
import ctypes as C
from ctypes import wintypes as W

u32 = C.WinDLL('user32', use_last_error=True)
g32 = C.WinDLL('gdi32', use_last_error=True)

class Point(C.Structure):
    _fields_ = [('x', W.LONG), ('y', W.LONG)]

class Size(C.Structure):
    _fields_ = [('cx', W.LONG), ('cy', W.LONG)]

class Blend(C.Structure):
    _fields_ = [('op', W.BYTE), ('flags', W.BYTE), ('alpha', W.BYTE), ('format', W.BYTE)]

class BitmapHeader(C.Structure):
    _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG),
                ('planes', W.WORD), ('bits', W.WORD), ('compression', W.DWORD),
                ('image_size', W.DWORD), ('xppm', W.LONG), ('yppm', W.LONG),
                ('used', W.DWORD), ('important', W.DWORD)]

u32.GetDC.argtypes = [W.HWND]; u32.GetDC.restype = W.HDC
u32.ReleaseDC.argtypes = [W.HWND, W.HDC]
g32.CreateCompatibleDC.argtypes = [W.HDC]; g32.CreateCompatibleDC.restype = W.HDC
g32.CreateDIBSection.argtypes = [W.HDC, C.POINTER(BitmapHeader), W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD]
g32.CreateDIBSection.restype = W.HBITMAP
g32.SelectObject.argtypes = [W.HDC, W.HANDLE]; g32.SelectObject.restype = W.HANDLE
g32.DeleteObject.argtypes = [W.HANDLE]
g32.DeleteDC.argtypes = [W.HDC]
u32.UpdateLayeredWindow.argtypes = [W.HWND, W.HDC, C.POINTER(Point), C.POINTER(Size), W.HDC,
                                   C.POINTER(Point), W.DWORD, C.POINTER(Blend), W.DWORD]
u32.UpdateLayeredWindow.restype = W.BOOL
u32.GetWindowLongPtrW.argtypes = [W.HWND, C.c_int]; u32.GetWindowLongPtrW.restype = C.c_ssize_t
u32.SetWindowLongPtrW.argtypes = [W.HWND, C.c_int, C.c_ssize_t]; u32.SetWindowLongPtrW.restype = C.c_ssize_t

class LayeredSurface:
    def __init__(self, hwnd, width, height):
        self.hwnd, self.width, self.height = hwnd, width, height
        self.dc = self.bitmap = self.old_bitmap = None
        style = u32.GetWindowLongPtrW(hwnd, -20)
        # Reset WS_EX_LAYERED to remove any previous SetLayeredWindowAttributes state.
        u32.SetWindowLongPtrW(hwnd, -20, style & ~0x80000)
        u32.SetWindowLongPtrW(hwnd, -20, style | 0x80000 | 0x20 | 0x08000000 | 0x80)
        screen = u32.GetDC(None)
        try:
            self.dc = g32.CreateCompatibleDC(screen)
            header = BitmapHeader(C.sizeof(BitmapHeader), width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
            self.bits = C.c_void_p()
            self.bitmap = g32.CreateDIBSection(screen, C.byref(header), 0, C.byref(self.bits), None, 0)
            if not self.dc or not self.bitmap:
                self.close()
                raise C.WinError(C.get_last_error())
            self.old_bitmap = g32.SelectObject(self.dc, self.bitmap)
        finally:
            u32.ReleaseDC(None, screen)

    def present(self, frame, opacity=255):
        if frame.size != (self.width, self.height): raise ValueError('Surface size mismatch')
        # Pillow RGBa is premultiplied RGBA; Windows expects premultiplied BGRA.
        pixels = frame.convert('RGBa').tobytes('raw', 'BGRa')
        C.memmove(self.bits, pixels, len(pixels))
        blend = Blend(0, 0, max(0, min(255, int(opacity))), 1)
        target, source, size = Point(0, 0), Point(0, 0), Size(self.width, self.height)
        if not u32.UpdateLayeredWindow(self.hwnd, None, C.byref(target), C.byref(size), self.dc,
                                       C.byref(source), 0, C.byref(blend), 2):
            raise C.WinError(C.get_last_error())

    def close(self):
        if self.dc and self.old_bitmap: g32.SelectObject(self.dc, self.old_bitmap)
        if self.bitmap: g32.DeleteObject(self.bitmap)
        if self.dc: g32.DeleteDC(self.dc)
        self.dc = self.bitmap = self.old_bitmap = None
