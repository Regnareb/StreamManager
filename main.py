import sys
from PySide2 import QtWidgets
import common.ui
import common.tools




if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = common.ui.StreamManager_UI()
    win.show()
    sys.exit(app.exec_())
