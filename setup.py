import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
buildOptions = dict(includes=['PySide2', 'concurrent.futures', 'keyboard', 'cherrypy', 'psutil', 'requests_oauthlib', 'oauthlib.oauth2.rfc6749.errors'],
                    include_files=['common', 'services', ('lib/pssuspend.exe', 'lib/pssuspend.exe'), ('lib/pssuspend64.exe', 'lib/pssuspend64.exe'), ('icon.png', 'icon.png'), ('lib/bottle.py', 'lib/bottle.py'), ('data/theme', 'data/theme')],
                    silent=True)

base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable(script='main.py', base=base, targetName='StreamManager.exe', icon='icon.ico')
]

setup(name='Stream Manager',
      version = '1.0',
      description = '',
      options = dict(build_exe = buildOptions),
      executables = executables)
