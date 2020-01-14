import sys
from PySide2 import QtWidgets
import common.ui
import common.tools


try:
    # Windows dont have stdout in GUI mode, override it to prevent crashes
    sys.stdout.write("\n")
    sys.stdout.flush()
except (IOError, AttributeError):
    class dummyStream:
        def __init__(self): pass
        def write(self,data): pass
        def read(self,data): pass
        def flush(self): pass
        def close(self): pass
    # redirect all default streams to this dummyStream:
    sys.stdout = dummyStream()
    sys.stderr = dummyStream()
    sys.stdin = dummyStream()
    sys.__stdout__ = dummyStream()
    sys.__stderr__ = dummyStream()
    sys.__stdin__ = dummyStream()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    win = common.ui.StreamManager_UI()
    win.show()
    sys.exit(app.exec_())
