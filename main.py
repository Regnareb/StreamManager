import sys
from PySide2 import QtWidgets
import common.ui
import common.tools




if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.setQuitOnLastWindowClosed(False)
    win = common.ui.StreamManager_UI()
    sys.exit(app.exec_())
