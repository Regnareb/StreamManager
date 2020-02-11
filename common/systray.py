from PySide2 import QtWidgets, QtGui

class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.createTrayIcon()

    def setIcon(self, icon):
        self.setWindowIcon(icon)
        self.trayIcon.setIcon(icon)

    def restore(self):
        self.show()
        self.activateWindow()

    def iconActivated(self, reason):
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick):
            self.restore()

    def createTrayIcon(self):
        self.quitAction = QtWidgets.QAction("&Quit", self, triggered=self.quit)
        self.trayIconMenu = QtWidgets.QMenu(self)
        self.trayIconMenu.addSeparator()
        self.trayIconMenu.addAction(self.quitAction)
        self.trayIcon = QtWidgets.QSystemTrayIcon(self)
        self.trayIcon.setContextMenu(self.trayIconMenu)
        self.trayIcon.messageClicked.connect(self.showNormal)
        self.trayIcon.activated.connect(self.iconActivated)
        self.trayIcon.show()

    def closeEvent(self, event):
        if self.trayIcon.isVisible():
            self.hide()
            event.ignore()

    def quit(self):
        QtGui.qApp.quit()
