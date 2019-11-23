import os.path
import glob
import ctypes
import logging
import importlib
import functools
import threading
import subprocess

import psutil
from contextlib import contextmanager
logger = logging.getLogger(__name__)

@contextmanager
def pause_services(services):
    # Use pssuspend and kill -STOP on mac
    for service in services:
        subprocess.Popen('net stop "{}"'.format(service))
    yield
    for service in services:
        subprocess.Popen('net start "{}"'.format(service))

def threaded(func):
    @functools.wraps(func)
    def async_func(*args, **kwargs):
        func_hl = threading.Thread(target=func, args=args, kwargs=kwargs)
        func_hl.start()
        return func_hl
    return async_func

def loadmodules(path, subfolders):
    modules = glob.glob(os.path.join(path, subfolders, '*.py'))
    modules = ['.'.join([subfolders, os.path.basename(i)[:-3]]) for i in modules]
    data = {}
    for module in modules:
        data[module] = importlib.import_module(module)
    return data

def getForegroundProcess():
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    h_wnd = user32.GetForegroundWindow()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))
    process = psutil.Process(pid.value)
    return process

def parse_strings(infos):
    for key, val in infos.items():
        try:
            infos[key] = val.replace('%SERVICE%', infos.get('name', '%SERVICE%'))
            infos[key] = val.replace('%CATEGORY%', infos.get('category', '%CATEGORY%'))
            infos[key] = val.replace('%CUSTOMTEXT%', infos.get('customtext', '%CUSTOMTEXT%'))
        except AttributeError:
            pass
    return infos
