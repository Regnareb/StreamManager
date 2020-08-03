import re
import os
import sys
import glob
import json
import socket
import shutil
import ctypes
import logging
import tempfile
import importlib
import traceback
import functools
import threading
import subprocess
from io import BytesIO
from zipfile import ZipFile

import psutil
import requests
from contextlib import contextmanager
logger = logging.getLogger(__name__)


class NoInternet(Exception):
    pass

def internet(host="8.8.8.8", port=53, timeout=3):
  """
  Host: 8.8.8.8 (google-public-dns-a.google.com)
  OpenPort: 53/tcp
  Service: domain (DNS/TCP)
  """
  try:
    socket.setdefaulttimeout(timeout)
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
    return True
  except socket.error as ex:
    logger.exception(ex)
    return False

@contextmanager
def pause_services(services):
    if sys.platform=='win32':
        admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if admin:
            for service in services:
                subprocess.Popen('net stop "{}"'.format(service), creationflags=subprocess.CREATE_NO_WINDOW)
        elif services:
            logger.warning("No administrator rights, can't pause Windows Services")
        yield
        if admin:
            for service in services:
                subprocess.Popen('net start "{}"'.format(service), creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        yield

@contextmanager
def pause_processes(processes):
    if sys.platform in ['Windows', 'win32', 'cygwin']:
        for process in processes:
            subprocess.Popen('lib/pssuspend.exe "{}"'.format(process), creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        yield
        for process in processes:
            subprocess.Popen('lib/pssuspend.exe -r "{}"'.format(process), creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    else:
        for process in processes:
           subprocess.Popen('pkill -TSTP "{}$"'.format(process), shell=True)
        yield
        for process in processes:
            subprocess.Popen('pkill -CONT "{}$"'.format(process), shell=True)

def download_pssuspend(path):
    url = 'https://download.sysinternals.com/files/PSTools.zip'
    response = requests.get(url)
    zipfile = ZipFile(BytesIO(response.content))
    pssuspend = zipfile.extract('pssuspend.exe', path)
    pssuspend = zipfile.extract('pssuspend64.exe', path)
    return pssuspend

def catch_exception(exception=Exception, logger=logging.getLogger(__name__)):
    def deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception as err:
                logger.critical(traceback.print_exc())
                logger.exception(err)
                # raise
        return wrapper
    return deco

def decorate_all_methods(decorator, exclude=None):
    if exclude is None:
        exclude = []
    def decorate(cls):
        for attr in cls.__dict__:
            if callable(getattr(cls, attr)) and attr not in exclude:
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate

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
        data[module.split('.')[-1]] = importlib.import_module(module)
    return data

def getForegroundProcess():
    if sys.platform in ['Windows', 'win32', 'cygwin']:
        try:
            user32 = ctypes.windll.user32
            h_wnd = user32.GetForegroundWindow()
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))
            return psutil.Process(pid.value).exe().replace('\\', '/')
        except psutil.AccessDenied:
            return ''
    elif sys.platform in ['Mac', 'darwin', 'os2', 'os2emx']:
        import AppKit
        return str(AppKit.NSWorkspace.sharedWorkspace().activeApplication()['NSApplicationPath'])
    elif sys.platform in ['linux', 'linux2']:
        root = subprocess.Popen(['xprop', '-root', '_NET_ACTIVE_WINDOW'], stdout=subprocess.PIPE)
        stdout, _ = root.communicate()
        m = re.search(b'^_NET_ACTIVE_WINDOW.* ([\w]+)$', stdout)
        if m != None:
            window_id = m.group(1)
            window = subprocess.Popen(['xprop', '-id', window_id, 'WM_NAME'], stdout=subprocess.PIPE)
            stdout, _ = window.communicate()
        else:
            return ''
        match = re.match(b"WM_NAME\(\w+\) = (?P<name>.+)$", stdout)
        if match != None:
            return match.group("name").strip(b'"')
    return ''

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
            memory = proc.memory_percent()  # Fix an OSX bug returning None
            if name in ignorelist:
                continue
            if exe in result:
                result[exe]['memory_percent'] += memory
            else:
                result[exe] = proc.as_dict(attrs=['name', 'exe', 'nice', 'num_threads'])
                result[exe]['memory_percent'] = memory
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except FileNotFoundError:
            logger.error('Strange process: {} - {}'.format(proc.name(), proc.pid))
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

def merge_dict(d1, d2):
    for k in d2:
        if k in d1 and isinstance(d1[k], dict) and isinstance(d2[k], dict):
            merge_dict(d1[k], d2[k])
        else:
            d1[k] = d2[k]

def load_json(path, backup=True):
    content = {}
    try:
        with open(path) as json_file:
            content = json.load(json_file)
    except FileNotFoundError:
        return None
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        if backup:
            shutil.copy(path, path + '_error')
        logger.error('There was an error in the json file, you can view it at this path: {}'.format(path+'_error'))
        return False
    return content

def save_json(data, path):
    if not path.endswith('.json'):
        path = path + ('.json')
    with tempfile.NamedTemporaryFile('w', delete=False) as tmp:
        json.dump(data, tmp, indent=4)
    shutil.move(tmp.name, path)
    return True

class Borg:
    __shared_state = {}
    def __init__(self):
        super().__init__()
        self.__dict__ = self.__shared_state


class HtmlStreamHandler(logging.StreamHandler):
    CRITICAL = {'color': 'brown', 'size': '120%', 'special': 'font-weight:bold', 'after': '' }
    ERROR    = {'color': 'red', 'size': '100%', 'special': '', 'after': ''}
    WARNING  = {'color': 'darkorange', 'size': '100%', 'special': '', 'after': ''}
    INFO     = {'size': '100%', 'special': '', 'after': ''}
    DEFAULT  = {'size': '100%', 'special': '', 'after': ''}
    DEBUG    = {'color': 'grey', 'size': '100%', 'special': '', 'after': ''}
    SUCCESS  = {'color': 'green', 'size': '100%', 'special': '', 'after': ''}

    def __init__(self, stream=None):
        super().__init__(stream=stream)

    @classmethod
    def _get_params(cls, level):
        if level == 777:               return cls.SUCCESS  # logger.log(777, 'Message')
        elif level >= logging.CRITICAL:return cls.CRITICAL
        elif level >= logging.ERROR:   return cls.ERROR
        elif level >= logging.WARNING: return cls.WARNING
        elif level >= logging.INFO:    return cls.INFO
        elif level >= logging.DEBUG:   return cls.DEBUG
        else:                          return cls.DEFAULT

    def format(self, record):
        regex = r"((?:\w):(?:\\|/)[^\s/$.?#].[^\s]*)"
        regex = re.compile(regex, re.MULTILINE)
        text = logging.StreamHandler.format(self, record)
        text = re.sub(regex, r'<a href="file:///\g<1>">\g<1></a>', text)
        params = self._get_params(record.levelno)
        style = 'style="font-size:{size};{special}"'.format(**params)
        if params.get('color'):
            style = style.replace('style="', 'style="color:{color};').format(**params)
        result = '<span class="{0}" {1}>{2}</span>{after}'.format(record.levelname.lower(), style, text, **params)
        return result