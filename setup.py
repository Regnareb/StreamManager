from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
buildOptions = dict(packages=['PySide2', 'concurrent.futures', 'keyboard', 'cherrypy', 'psutil', 'requests_oauthlib', 'oauthlib.oauth2.rfc6749.errors'],
                    include_files=['common', 'services', ('lib/bottle.py', 'lib/bottle.py'), 'data', ('lib/pssuspend.exe', 'lib/pssuspend.exe')])

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('main.py', base=base, targetName='StreamManager.exe')
]

setup(name='Stream Manager',
      version = '1.0',
      description = '',
      options = dict(build_exe = buildOptions),
      executables = executables)
