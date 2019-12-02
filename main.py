import sys

if __name__ == '__main__':
    from PySide2 import QtCore, QtWidgets, QtGui
    import common.ui

    app = QtWidgets.QApplication([])
    win = common.ui.StreamManager_UI()
    win.show()
    sys.exit(app.exec_())
