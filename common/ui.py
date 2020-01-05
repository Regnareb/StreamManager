import os
import sys
import logging
import functools
logger = logging.getLogger(__name__)
from PySide2 import QtCore, QtWidgets, QtGui, QtWebEngineWidgets

import common.manager
import common.remote

class MovableWindow():
    def mousePressEvent(self, QMouseEvent):
        self.windowPos = QMouseEvent.pos()
        self.setCursor(QtGui.QCursor(QtCore.Qt.SizeAllCursor))

    def mouseReleaseEvent(self, QMouseEvent):
        self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

    def mouseMoveEvent(self, QMouseEvent):
        pos = QtCore.QPoint(QMouseEvent.globalPos())
        self.window().move(pos - self.windowPos + QtCore.QPoint(self.pos().x() - self.geometry().x(), self.pos().y() - self.geometry().y()))


class StreamManager_UI(MovableWindow, QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setStyleSheet("QTableWidget {margin: 10px;} QPlainTexxtEdit, QxLineEdit {margin: 3px;} QHeaderView::section { background-color: #3697FE;border:1px solid #ccc;font-weight: bold} QHeaderView::section:checked { background-color: #fff;border:1px solid #ccc;} QPlainTextEdit {background:white}")
        self.setWindowTitle('Stream Manager')
        self.setCentralWidget(None)
        self.manager = ManagerStreamThread()
        self.manager.updated.connect(self.updated)
        self.webremote = WebRemote()
        self.webremote.check.connect(self.check)
        self.webremote.updated.connect(self.updated)
        self.webremote.start()
        self.create_menu()
        self.create_gamelayout()
        self.create_statuslayout()
        self.load_appdata()
        self.load_generalsettings()
        self.gameslayout['dock'].setTitleBarWidget(QtWidgets.QWidget())
        self.panel_status['dock'].setTitleBarWidget(QtWidgets.QWidget())
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas, QtWidgets.QTabWidget.North)
        self.setDockOptions(QtWidgets.QMainWindow.AllowNestedDocks | QtWidgets.QMainWindow.AllowTabbedDocks)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.panel_status['dock'])
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.gameslayout['dock'])
        self.tabifyDockWidget(self.panel_status['dock'], self.gameslayout['dock'])
        self.panel_status['dock'].raise_()

    def check(self):
        self.manager.start()

    def updated(self, infos):
        pass

    def closeEvent(self, event):
        self.manager.quit()
        self.webremote.quit()
        self.webremote.terminate()
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if self.menuBar().isVisible():
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
            self.centralwidget.tabBar().hide()
        else:
            self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint & ~QtCore.Qt.FramelessWindowHint)
            self.centralwidget.tabBar().show()
        self.show()
        self.menuBar().setVisible(not self.menuBar().isVisible())

    def create_gamelayout(self):
        self.gameslayout = {}
        self.gameslayout['llayout'] = QtWidgets.QVBoxLayout()
        self.gameslayout['table'] = QtWidgets.QTableWidget()
        self.gameslayout['table'].currentCellChanged.connect(self.load_appsettings)
        self.gameslayout['table'].setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.gameslayout['table'].setColumnCount(1)
        self.gameslayout['table'].setWordWrap(False)
        self.gameslayout['table'].verticalHeader().setVisible(False)
        self.gameslayout['table'].setMinimumWidth(200)
        header = self.gameslayout['table'].horizontalHeader()
        header.setMinimumHeight(40)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.sectionClicked.connect(self.load_generalsettings)
        self.gameslayout['table'].setHorizontalHeaderLabels(['GENERAL'])

        self.gameslayout['add_game'] = QtWidgets.QPushButton('+')
        self.gameslayout['add_game'].setFlat(True)
        self.gameslayout['add_game'].setFixedSize(30, 27)
        self.gameslayout['add_game'].clicked.connect(self.add_game)
        self.gameslayout['remove_game'] = QtWidgets.QPushButton('-')
        self.gameslayout['remove_game'].setFlat(True)
        self.gameslayout['remove_game'].setFixedSize(30, 27)
        self.gameslayout['remove_game'].clicked.connect(self.remove_game)
        self.gameslayout['addremove_layout'] = QtWidgets.QHBoxLayout()
        self.gameslayout['addremove_layout'].addWidget(self.gameslayout['add_game'])
        self.gameslayout['addremove_layout'].addWidget(self.gameslayout['remove_game'])
        self.gameslayout['addremove_layout'].addStretch()
        self.gameslayout['llayout'].addWidget(self.gameslayout['table'])
        self.gameslayout['llayout'].addLayout(self.gameslayout['addremove_layout'])

        self.gameslayout['rlayout'] = QtWidgets.QVBoxLayout()
        self.gameslayout['stacked'] = QtWidgets.QStackedWidget()
        self.gameslayout['stacked'].setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed))
        self.gameslayout['stacked_process'] = QtWidgets.QLineEdit()
        self.gameslayout['stacked_process'].setMinimumHeight(30)
        self.gameslayout['stacked_process'].setEnabled(False)
        self.gameslayout['stacked_label'] = QtWidgets.QLabel()
        self.gameslayout['stacked_label'].setText('Applied by default for all games if there is no data\nLocks will force this setting no matter what')
        self.gameslayout['stacked_label'].setAlignment(QtCore.Qt.AlignCenter)
        self.gameslayout['stacked'].addWidget(self.gameslayout['stacked_process'])
        self.gameslayout['stacked'].addWidget(self.gameslayout['stacked_label'])

        self.gameslayout['rlayout'].addWidget(self.gameslayout['stacked'])
        self.gameslayout['stacked'].setCurrentWidget(self.gameslayout['stacked_label'])

        elements = ['category', 'title', 'description', 'tags']
        folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'theme', 'images'))
        icons = {True: QtGui.QIcon(folder + "/lock.png"), False: QtGui.QIcon(folder + "/unlock.png")}
        for key in elements:
            if key == 'description':
                self.gameslayout[key] = PlainTextEdit(icons)
                self.gameslayout[key].setMinimumHeight(150)
            else:
                self.gameslayout[key] = LineEdit(icons)
                self.gameslayout[key].setMinimumHeight(30)
            self.gameslayout[key].editingFinished.connect(self.save_appdata)
            s = self.gameslayout[key].sizePolicy()
            s.setRetainSizeWhenHidden(True)
            self.gameslayout[key].setSizePolicy(s)
            self.gameslayout[key].setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed))
            self.gameslayout['rlayout'].addWidget(self.gameslayout[key])
        self.gameslayout['description'].setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding))
        self.gameslayout['rlayout'].addStretch()

        self.gameslayout['container_llayout'] = QtWidgets.QWidget()
        self.gameslayout['container_llayout'].setLayout(self.gameslayout['llayout'])
        self.gameslayout['container_rlayout'] = QtWidgets.QWidget()
        self.gameslayout['container_rlayout'].setLayout(self.gameslayout['rlayout'])
        self.gameslayout['dock'] = QtWidgets.QDockWidget('Games')
        self.gameslayout['dock_layout'] = QtWidgets.QHBoxLayout()
        self.gameslayout['main'] = QtWidgets.QSplitter()
        self.gameslayout['main'].addWidget(self.gameslayout['container_llayout'])
        self.gameslayout['main'].addWidget(self.gameslayout['container_rlayout'])
        self.gameslayout['main'].setStretchFactor(0, 0)
        self.gameslayout['main'].setStretchFactor(1, 1)
        self.gameslayout['main'].setCollapsible(0, 0)
        self.gameslayout['main'].setCollapsible(1, 0)
        self.gameslayout['main'].addWidget(self.gameslayout['container_rlayout'])
        self.gameslayout['dock'].setWidget(self.gameslayout['main'])

    def create_filedialog(self):
        self.filedialog = QtWidgets.QFileDialog()
        result = self.filedialog.exec_()
        if result:
            return self.filedialog.selectedFiles()[0]

    def add_game(self):
        path = self.create_filedialog()
        if path:
            process = os.path.basename(path)
            if self.manager.config['appdata'].get(process):
                logger.warning('The same process is already registered: {}'.format(self.manager.config['appdata'].get(process)))
            else:
                self.manager.config['appdata'][process] = {}
                self.create_gamerow(process)
                self.gameslayout['table'].sortByColumn(0, QtCore.Qt.AscendingOrder)

    def remove_game(self):
        current = self.gameslayout['table'].currentItem()
        if current:
            self.manager.config['appdata'].pop(current._process)
            self.gameslayout['table'].removeRow(self.gameslayout['table'].currentRow())

    def save_appdata(self):
        current = self.gameslayout['table'].currentItem()
        cat = self.gameslayout['category'].text()
        title = self.gameslayout['title'].text()
        desc = self.gameslayout['description'].toPlainText()
        tags = self.gameslayout['tags'].text().split(',')
        tags = [i.strip() for i in tags if i]
        data = {'category': cat, 'title': title, 'description': desc, 'tags': tags}
        if current:
            self.manager.config['appdata'][current._process].update(data)
            self.update_gamerow(current)
        else:
            for key in data.copy():
                data['forced_' + key] = self.gameslayout[key].button.state
                self.manager.config['base'].update(data)
        self.manager.process = ''  # Reset current process to be able to apply new settings
        logger.debug(data)

    def update_gamerow(self, row):
        row.setText('{} ({})'.format(self.manager.config['appdata'][row._process].get('category', ''), row._process))

    def create_gamerow(self, process):
        row = QtWidgets.QTableWidgetItem()
        row._process = process
        self.update_gamerow(row)
        row.setFlags(row.flags() & ~QtCore.Qt.ItemIsEditable)
        rowcount = self.gameslayout['table'].rowCount()
        self.gameslayout['table'].insertRow(rowcount)
        self.gameslayout['table'].setItem(rowcount, 0, row)
        return row

    def load_appdata(self):
        for process in self.manager.config['appdata']:
            self.create_gamerow(process)
        self.gameslayout['table'].sortByColumn(0, QtCore.Qt.AscendingOrder)

    def load_appsettings(self, *args):
        self.block_signals(True)
        current = self.gameslayout['table'].currentItem()
        if current:
            elements = ['category', 'title', 'tags']
            for key in elements:
                for action in self.gameslayout[key].actions():
                    self.gameslayout[key].removeAction(action)
            self.gameslayout['stacked'].setCurrentWidget(self.gameslayout['stacked_process'])
            val = self.manager.config['appdata'][current._process]
            finalvals = self.manager.get_informations(current._process)
            self.gameslayout['stacked_process'].setText(current._process)
            self.gameslayout['category'].setText(val.get('category'))
            self.gameslayout['title'].setText(val.get('title'))
            self.gameslayout['description'].setPlainText(val.get('description'))
            self.gameslayout['tags'].setText(', '.join(val.get('tags', [])))
            self.gameslayout['title'].setPlaceholderText(finalvals.get('title'))
            self.gameslayout['category'].setPlaceholderText(finalvals.get('category'))
            self.gameslayout['description'].setPlaceholderText(finalvals.get('description'))
            self.gameslayout['tags'].setPlaceholderText(', '.join(finalvals.get('tags', [])))
            self.gameslayout['title'].setButtonVisibility(False)
            self.gameslayout['category'].setButtonVisibility(False)
            self.gameslayout['description'].setButtonVisibility(False)
            self.gameslayout['tags'].setButtonVisibility(False)
            self.gameslayout['remove_game'].setEnabled(True)
        self.block_signals(False)

    def load_generalsettings(self, *args):
        self.block_signals(True)
        self.gameslayout['table'].clearSelection()
        self.gameslayout['table'].setCurrentCell(-1, -1)
        self.gameslayout['stacked'].setCurrentWidget(self.gameslayout['stacked_label'])
        val = self.manager.config['base']
        elements = ['category', 'title', 'tags']
        for key in elements:
            self.gameslayout[key].setPlaceholderText(key)
        self.gameslayout['category'].setText(val.get('category'))
        self.gameslayout['title'].setText(val.get('title'))
        self.gameslayout['description'].setPlainText(val.get('description'))
        self.gameslayout['tags'].setText(','.join(val.get('tags', [])))
        self.gameslayout['title'].setButtonVisibility(True)
        self.gameslayout['category'].setButtonVisibility(True)
        self.gameslayout['description'].setButtonVisibility(True)
        self.gameslayout['tags'].setButtonVisibility(True)
        self.gameslayout['title'].changeButtonState(val.get('forced_title', ''))
        self.gameslayout['category'].changeButtonState(val.get('forced_category', ''))
        self.gameslayout['description'].changeButtonState(val.get('forced_description', ''))
        self.gameslayout['tags'].changeButtonState(val.get('forced_tags', []))
        self.gameslayout['remove_game'].setEnabled(False)
        self.block_signals(False)

    def create_statuslayout(self):
        self.panel_status = {}
        self.panel_status['dock'] = QtWidgets.QDockWidget('Status')
        self.panel_status['webpage'] = QtWebEngineWidgets.QWebEngineView()
        self.panel_status['webpage'].load(QtCore.QUrl("http://localhost:8080/"))
        self.panel_status['dock'].setWidget(self.panel_status['webpage'])

    def block_signals(self, block):
        for i in self.gameslayout:
            self.gameslayout[i].blockSignals(block)

def set_disabledrowstyle(item, val):
    if val:
        item.setForeground(QtGui.QColor(0,0,0))
    else:
        item.setForeground(QtGui.QColor(150,150,150))

        self.panel_services = {}
        self.panel_services['main'] = QtWidgets.QWidget()
        self.panel_services['main_container'] = QtWidgets.QGridLayout()
        self.panel_services['list'] = QtWidgets.QTableWidget()
        self.panel_services['list'].setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.panel_services['list'].setColumnCount(1)
        self.panel_services['list'].setWordWrap(False)
        self.panel_services['list'].verticalHeader().setVisible(False)
        self.panel_services['list'].horizontalHeader().setVisible(False)
        self.panel_services['list'].horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.panel_services['list'].currentCellChanged.connect(self.service_changed)

        for i, elem in enumerate(['enabled', 'channel', 'channel_id', 'client_id', 'client_secret', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url']):
            namelabel = 'label_' + elem
            nameline = 'line_' + elem
            self.panel_services[namelabel] = QtWidgets.QLabel()
            self.panel_services[namelabel].setText(elem.capitalize() + ':')
            self.panel_services['main_container'].addWidget(self.panel_services[namelabel], i, 1)
            if elem == 'enabled':
                self.panel_services[nameline] = QtWidgets.QCheckBox()
                self.panel_services[nameline].stateChanged.connect(self.save_servicedata)
            else:
                self.panel_services[nameline] = QtWidgets.QLineEdit()
                self.panel_services[nameline].editingFinished.connect(self.save_servicedata)
                # self.panel_services[nameline].setEnabled(False)
            self.panel_services[nameline].setMinimumHeight(30)
            self.panel_services['main_container'].addWidget(self.panel_services[nameline], i, 2)
        self.panel_services['main_container'].setRowStretch(self.panel_services['main_container'].rowCount(), 10)
        self.panel_services['list'].setFixedWidth(150)
        self.panel_services['main'].setLayout(self.panel_services['main_container'])
        self.panel_services['main_container'].addWidget(self.panel_services['list'], 0, 0, -1, 1)
        self.create_services()
        self.panel_services['list'].itemSelectionChanged.connect(self.service_changed)
        self.panel_services['list'].setCurrentCell(0, 0)

    def service_changed(self):
        self.block_signals(True)
        item = self.panel_services['list'].currentItem()
        service = item.text()
        config = self.manager.config['streamservices'][service]
        for elem in ['enabled', 'channel', 'channel_id', 'client_id', 'client_secret', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url']:
            if elem == 'enabled':
                val = config.get(elem, False)
                self.panel_services['line_' + elem].setChecked(val)
                set_disabledrowstyle(item, val)
            else:
                self.panel_services['line_' + elem].setText(str(config.get(elem, '')))
        self.block_signals(False)

    def save_servicedata(self):
        item = self.panel_services['list'].currentItem()
        service = item.text()
        for elem in ['enabled', 'channel', 'channel_id', 'client_id', 'client_secret', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url']:
            if elem == 'enabled':
                result = self.panel_services['line_' + elem].isChecked()
                set_disabledrowstyle(item, result)
            else:
                result = self.panel_services['line_' + elem].text()
            self.manager.config['streamservices'][service][elem] = result

    def create_statuslayout(self):
        self.panel_status = {}
        self.panel_status['main'] = QtWidgets.QWidget()
        self.panel_status['main_container'] = QtWidgets.QHBoxLayout()
        self.panel_status['webpage'] = QtWebEngineWidgets.QWebEngineView()
        self.panel_status['webpage'].load(QtCore.QUrl("http://localhost:8080/"))
        self.panel_status['main_container'].addWidget(self.panel_status['webpage'])
        self.panel_status['main'].setLayout(self.panel_status['main_container'])

    def block_signals(self, block):
        for i in self.gameslayout:
            self.gameslayout[i].blockSignals(block)
        for i in self.panel_services:
            self.panel_services[i].blockSignals(block)


def set_disabledrowstyle(item, val):
    if val:
        item.setForeground(QtGui.QColor(0,0,0))
    else:
class WebRemote(common.remote.WebRemote, QtCore.QThread):
    check = QtCore.Signal()
    updated = QtCore.Signal(dict)

    def check_process(self):
        self.check.emit()

    def run(self):
        self.server()
        self.exec_()


class ManagerStreamThread(common.manager.ManageStream, QtCore.QThread):
    updated = QtCore.Signal(dict)

    def run(self):
        self.create_services()
        timer = QtCore.QTimer()
        timer.timeout.connect(self.main)
        timer.start(1000)
        self.exec_()

    def main(self):
        result = self.check_application()
        if result:
            self.updated.emit(result)
            logger.info(result)

class StateButtons():
    buttonClicked = QtCore.Signal(bool)

    def __init__(self, icons, parent=None):
        super().__init__(parent)
        self.button = QtWidgets.QToolButton(self)
        self.button.state = None
        self.button.icons = icons
        self.button.setStyleSheet('border: none; padding: 0px;')
        self.button.setCursor(QtCore.Qt.PointingHandCursor)
        self.button.clicked.connect(functools.partial(self.changeButtonState))
        self.setButtonVisibility(True)

    def setButtonVisibility(self, state):
        frameWidth = self.style().pixelMetric(QtWidgets.QStyle.PM_DefaultFrameWidth)
        buttonSize = self.button.sizeHint()
        if state:
            self.button.show()
            self.setStyleSheet('padding-right: %dpx;' % (buttonSize.width() + frameWidth + 1))
            self.setMinimumSize(max(self.minimumSizeHint().width(), buttonSize.width() + frameWidth*2 + 2),
                                max(self.minimumSizeHint().height(), buttonSize.height() + frameWidth*2 + 2))
        else:
            self.button.hide()
            self.setStyleSheet('padding-right: 0px;')

    def changeButtonState(self, state=None):
        if state == None:
            try:
                keys = list(self.button.icons.keys())
                i = keys.index(self.button.state)
                self.button.state = keys[i+1]
            except (ValueError, IndexError):
                self.button.state = keys[0]
        else:
            self.button.state = state
        self.button.setIcon(self.button.icons[self.button.state])
        self.buttonClicked.emit(self.button.state)
        self.editingFinished.emit()

    def resizeEvent(self, event):
        buttonSize = self.button.sizeHint()
        frameWidth = self.style().pixelMetric(QtWidgets.QStyle.PM_DefaultFrameWidth)
        self.button.move(self.rect().right() - frameWidth - buttonSize.width(),
                        (self.rect().bottom() - buttonSize.height() + 1)/2)
        super().resizeEvent(event)

class PlainTextEdit(StateButtons, QtWidgets.QPlainTextEdit):
    editingFinished = QtCore.Signal()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editingFinished.emit()

class LineEdit(StateButtons, QtWidgets.QLineEdit):
    pass

