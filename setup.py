from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
buildOptions = dict(includes=['PySide2', 'concurrent.futures', 'keyboard', 'cherrypy', 'psutil', 'requests_oauthlib', 'oauthlib.oauth2.rfc6749.errors'],
                    include_files=['common', 'services', ('icon.png', 'icon.png'), ('lib/bottle.py', 'lib/bottle.py'), 'data/theme', ('lib/pssuspend.exe', 'lib/pssuspend.exe')],
                    silent =True)

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('main.py', base=base, targetName='StreamManager.exe', icon='icon.png')
]

setup(name='Stream Manager',
      version = '1.0',
      description = '',
      optimize = 2,
      options = dict(build_exe = buildOptions),
      executables = executables)
