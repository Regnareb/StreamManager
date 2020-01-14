import os
import sys
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
    if sys.platform=='win32':
        for service in services:
            subprocess.Popen('net stop "{}"'.format(service), creationflags=subprocess.CREATE_NO_WINDOW)
        yield
        for service in services:
            subprocess.Popen('net start "{}"'.format(service), creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        yield

@contextmanager
def pause_processes(processes):
    if sys.platform=='win32':
        for process in processes:
            subprocess.Popen('pssuspend.exe "{}"'.format(process), creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        yield
        for process in processes:
            subprocess.Popen('pssuspend.exe -r "{}"'.format(process), creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    else:
        for process in processes:
           subprocess.Popen('pkill -STOP -c "{}$"'.format(process), creationflags=subprocess.CREATE_NO_WINDOW)
        yield
        for process in processes:
            subprocess.Popen('pkill -CONT -c "{}$"'.format(process), creationflags=subprocess.CREATE_NO_WINDOW)

def threaded(func):
    @functools.wraps(func)
    def async_func(*args, **kwargs):
        func_hl = threading.Thread(target=func, args=args, kwargs=kwargs)
        func_hl.start()
        return func_hl
    return async_func

def loadmodules(path, subfolder):
    modules = glob.glob(os.path.join(path, subfolder, '*.py'))
    modules = ['.'.join([subfolder, os.path.basename(i)[:-3]]) for i in modules]
    data = {}
    for module in modules:
        data[module] = importlib.import_module(module)
    return data

def getForegroundProcess():
    if sys.platform == 'win32':
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        h_wnd = user32.GetForegroundWindow()
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))
        process = psutil.Process(pid.value).name()
    elif sys.platform=='darwin':
        # import AppKit
        process = ''
    else:
        process = ''
    return process

def listservices(namefilter='', status=''):
    if sys.platform != 'win32':
        return {}
    services = {}
    for i in psutil.win_service_iter():
        if namefilter and namefilter.lower() not in i.name().lower() or status and i.status() != status:
            continue
        services[i.binpath()] = i.as_dict()
    return services

def listprocesses():
    result = {}
    ignorelist = ['System Idle Process', 'System', 'svchost.exe', 'csrss.exe', 'services.exe', 'conhost.exe', 'wininit.exe', 'lsass.exe', 'lsm.exe', 'winlogon.exe', 'rundll32.exe', 'taskkill.exe']
    for proc in psutil.process_iter():
        try:
            name = proc.name()
            exe = proc.exe()
            if name in ignorelist:
                continue
            if exe in result:
                result[exe]['memory_percent'] += proc.memory_percent()
            else:
                result[exe] = proc.as_dict(attrs=['name', 'exe', 'memory_percent', 'nice', 'num_threads'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return result

def parse_strings(infos):
    for key in infos:
        try:
            infos[key] = infos[key].replace('%SERVICE%', infos.get('name', '%SERVICE%'))
            infos[key] = infos[key].replace('%CATEGORY%', infos.get('category', '%CATEGORY%'))
            infos[key] = infos[key].replace('%CUSTOMTEXT%', infos.get('customtext', '%CUSTOMTEXT%'))
        except AttributeError:
            pass
    return infos


class Borg:
    __shared_state = {}
    def __init__(self):
        super().__init__()
        self.__dict__ = self.__shared_state
