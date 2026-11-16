import runpy
from pathlib import Path
import traceback
import ctypes
try:
    runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
except Exception:
    path = Path(__file__).with_name('error.log')
    path.write_text(traceback.format_exc(), encoding='utf-8')
    ctypes.windll.user32.MessageBoxW(None, f'Startup failed. Details saved to {path}', 'FOCUS FIELD', 16)
