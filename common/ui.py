import os
import sys
import copy
import logging
import threading
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
        self.webremote.startedcheck.connect(self.start_check)
        self.webremote.stoppedcheck.connect(self.stop_check)
        self.webremote.updated.connect(self.updated)
        self.webremote.start()
        self.preferences = Preferences(self.manager)
        self.create_gamelayout()
        self.create_statuslayout()
        self.load_appdata()
        self.load_generalsettings()
        self.create_menu()
        self.gameslayout['dock'].setTitleBarWidget(QtWidgets.QWidget())
        self.panel_status['dock'].setTitleBarWidget(QtWidgets.QWidget())
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas, QtWidgets.QTabWidget.North)
        self.setDockOptions(QtWidgets.QMainWindow.AllowNestedDocks | QtWidgets.QMainWindow.AllowTabbedDocks)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.panel_status['dock'])
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.gameslayout['dock'])
        self.tabifyDockWidget(self.panel_status['dock'], self.gameslayout['dock'])
        self.panel_status['dock'].raise_()

    def start_check(self):
        self.manager.start()

    def stop_check(self):
        self.manager.quit()

    def updated(self, infos):
        pass

    def closeEvent(self, event):
        self.manager.quit()
        self.webremote.quit()
        self.webremote.terminate()
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        pos = self.pos()
        geo = self.geometry()
        if self.menuBar().isVisible():
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint & ~QtCore.Qt.FramelessWindowHint)
        self.show()
        self.move(pos)
        self.setGeometry(geo)
        self.menuBar().setVisible(not self.menuBar().isVisible())

    def create_menu(self):
        action = QtWidgets.QAction('Preferences', self, triggered=self.preferences.exec_)
        self.menuBar().addAction(action)

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


class Preferences(QtWidgets.QDialog):
    # Make a dirty attribute to prevent closing the window without saving
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.tabs = QtWidgets.QTabWidget()
        self.tab_streams = Preferences_Streams(manager)
        self.tab_pauseservices = Preferences_Pauseservices(manager)
        self.tabs.addTab(self.tab_streams, "Streams")
        self.tabs.addTab(self.tab_pauseservices, "Services (Windows)")

        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.addWidget(self.tabs)
        self.mainLayout.addWidget(self.buttons)
        self.setLayout(self.mainLayout)
        self.setWindowTitle('Preferences')

    def accept(self):
        self.tab_streams.accept()
        self.tab_pauseservices.accept()
        super().accept()

    def exec_(self):
        self.tab_streams.reset()
        self.tab_pauseservices.reset()
        super().exec_()

class Preferences_Streams(QtWidgets.QWidget):
    def __init__(self, manager, parent=None):
        # add get token button
        super().__init__(parent)
        self.manager = manager
        self.panel_services = {}
        self.panel_services['container'] = QtWidgets.QGridLayout()

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
            self.panel_services['container'].addWidget(self.panel_services[namelabel], i, 1)
            if elem == 'enabled':
                self.panel_services[nameline] = QtWidgets.QCheckBox()
                self.panel_services[nameline].stateChanged.connect(self.save_servicedata)
            else:
                self.panel_services[nameline] = QtWidgets.QLineEdit()
                # self.panel_services[nameline].editingFinished.connect(self.save_servicedata)
                self.panel_services[nameline].setEnabled(False)
            self.panel_services[nameline].setMinimumHeight(30)
            self.panel_services['container'].addWidget(self.panel_services[nameline], i, 2)
        self.panel_services['container'].setRowStretch(self.panel_services['container'].rowCount(), 10)
        self.panel_services['list'].setFixedWidth(150)
        self.setLayout(self.panel_services['container'])
        self.panel_services['container'].addWidget(self.panel_services['list'], 0, 0, -1, 1)
        self.panel_services['list'].itemSelectionChanged.connect(self.service_changed)
        self.reset()

    def create_services(self):
        self.panel_services['list'].blockSignals(True)
        while self.panel_services['list'].rowCount():
            self.panel_services['list'].removeRow(0)
        for service in common.manager.SERVICES.values():
            servicename = service.Main.name
            row = QtWidgets.QTableWidgetItem()
            row.setText(servicename)
            row.setFlags(row.flags() & ~QtCore.Qt.ItemIsEditable)
            rowcount = self.panel_services['list'].rowCount()
            self.panel_services['list'].insertRow(rowcount)
            self.panel_services['list'].setItem(rowcount, 0, row)
            set_disabledrowstyle(row, self.temporary_settings[service.Main.name].get('enabled', False))
        self.panel_services['list'].sortItems(QtCore.Qt.AscendingOrder)
        self.panel_services['list'].blockSignals(False)

    def service_changed(self):
        # self.block_signals(True)
        item = self.panel_services['list'].currentItem()
        service = item.text()
        config = self.temporary_settings[service]
        for elem in ['enabled', 'channel', 'channel_id', 'client_id', 'client_secret', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url']:
            if elem == 'enabled':
                val = config.get(elem, False)
                self.panel_services['line_' + elem].blockSignals(True)
                self.panel_services['line_' + elem].setChecked(val)
                self.panel_services['line_' + elem].blockSignals(False)
                set_disabledrowstyle(item, val)
            else:
                self.panel_services['line_' + elem].setText(str(config.get(elem, '')))
        # self.block_signals(False)

    def save_servicedata(self):
        item = self.panel_services['list'].currentItem()
        service = item.text()
        for elem in ['enabled', 'channel', 'channel_id', 'client_id', 'client_secret', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url']:
            if elem == 'enabled':
                result = self.panel_services['line_' + elem].isChecked()
                set_disabledrowstyle(item, result)
            else:
                result = self.panel_services['line_' + elem].text()
            self.temporary_settings[service][elem] = result

    def accept(self):
        for service in self.temporary_settings:
            self.manager.config['streamservices'][service]['enabled'] = self.temporary_settings[service]['enabled']

    def reset(self):
        self.temporary_settings = copy.deepcopy(self.manager.config['streamservices'])
        self.create_services()
        self.panel_services['list'].setCurrentCell(0, 0)


class Preferences_Pauseservices(QtWidgets.QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.panel_pause = {}
        self.panel_pause['container'] = QtWidgets.QGridLayout()
        self.panel_pause['label'] = QtWidgets.QLabel('Test')

        for elem in ['list', 'list_pause']:
            self.panel_pause[elem] = QtWidgets.QTableWidget()
            self.panel_pause[elem].setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.panel_pause[elem].setColumnCount(1)
            self.panel_pause[elem].setWordWrap(False)
            self.panel_pause[elem].verticalHeader().setVisible(False)
            self.panel_pause[elem].horizontalHeader().setVisible(False)
            self.panel_pause[elem].horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        # self.panel_pause['refresh'] = QtWidgets.QPushButton('🔃')
        self.panel_pause['add'] = QtWidgets.QPushButton('→')
        self.panel_pause['remove'] = QtWidgets.QPushButton('←')
        # self.panel_pause['refresh'].setFlat(True)
        self.panel_pause['add'].setFlat(True)
        self.panel_pause['remove'].setFlat(True)

        # self.panel_pause['refresh'].clicked.connect(self.populate_pauseprocess)
        self.panel_pause['add'].clicked.connect(functools.partial(self.transfer_pauseprocess, 'add'))
        self.panel_pause['remove'].clicked.connect(functools.partial(self.transfer_pauseprocess, 'remove'))

        self.panel_pause['addremove_widget'] = QtWidgets.QWidget()
        self.panel_pause['addremove_layout'] = QtWidgets.QVBoxLayout()

        # self.panel_pause['addremove_layout'].addWidget(self.panel_pause['refresh'])
        self.panel_pause['addremove_layout'].addStretch()
        self.panel_pause['addremove_layout'].addWidget(self.panel_pause['add'])
        self.panel_pause['addremove_layout'].addWidget(self.panel_pause['remove'])
        self.panel_pause['addremove_layout'].addStretch()
        self.panel_pause['addremove_widget'].setLayout(self.panel_pause['addremove_layout'])

        # self.panel_pause['container'].setRowStretch(self.panel_pause['container'].rowCount(), 10)
        self.setLayout(self.panel_pause['container'])
        self.panel_pause['container'].addWidget(self.panel_pause['list'], 0, 0, 1, -1)
        self.panel_pause['container'].addWidget(self.panel_pause['list'], 1, 0, -1, 1)
        self.panel_pause['container'].addWidget(self.panel_pause['addremove_widget'], 1, 1, -1, 1)
        self.panel_pause['container'].addWidget(self.panel_pause['list_pause'], 1, 2, -1, 1)
        # self.reset()

    def populate_pauseprocess(self):
        while self.panel_pause['list'].rowCount():
            self.panel_pause['list'].removeRow(0)
        while self.panel_pause['list_pause'].rowCount():
            self.panel_pause['list_pause'].removeRow(0)

        currentconfig = self.manager.config['base']['services'].copy()
        currentprocesses = common.tools.listservices()
        for service in currentprocesses.values():
            row = QtWidgets.QTableWidgetItem()
            row.setText((service['name']))
            tooltip = '{} ({})\n\n{}'.format(service['display_name'], service['status'].upper(), service['description'].replace('. ', '.\n'))
            row.setToolTip(tooltip.strip())
            if service['name'] in currentconfig:
                destination = self.panel_pause['list_pause']
                currentconfig.remove(service['name'])
            else:
                destination = self.panel_pause['list']
            rowcount = destination.rowCount()
            destination.insertRow(rowcount)
            destination.setItem(rowcount, 0, row)

        for service in currentconfig:
            rowcount = self.panel_pause['list_pause'].rowCount()
            row = QtWidgets.QTableWidgetItem()
            row.setText(service)
            self.panel_pause['list_pause'].insertRow(rowcount)
            self.panel_pause['list_pause'].setItem(rowcount, 0, row)
        self.panel_pause['list'].sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.panel_pause['list_pause'].sortByColumn(0, QtCore.Qt.AscendingOrder)

    def transfer_pauseprocess(self, operation):
        if operation == 'add':
            source = self.panel_pause['list']
            destination = self.panel_pause['list_pause']
        else:
            source = self.panel_pause['list_pause']
            destination = self.panel_pause['list']
        item = source.currentItem()
        if item:
            item = item.text()
            row = QtWidgets.QTableWidgetItem()
            row.setText(item)
            rowcount = destination.rowCount()
            source.removeRow(source.currentRow())
            destination.insertRow(rowcount)
            destination.setItem(rowcount, 0, row)
            # if operation == 'add':
            #     self.manager.config['base']['services'].append(item)
            # else:
            #     self.manager.config['base']['services'].remove(item)
        self.panel_pause['list'].sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.panel_pause['list_pause'].sortByColumn(0, QtCore.Qt.AscendingOrder)

    def accept(self):
        rowdata = []
        for row in range(self.panel_pause['list_pause'].rowCount()):
            item = self.panel_pause['list_pause'].item(row, 0)
            rowdata.append(item.text())
        self.manager.config['base']['services'] = rowdata

    def reset(self):
        self.populate_pauseprocess()


class WebRemote(common.remote.WebRemote, QtCore.QThread):
    startedcheck = QtCore.Signal()
    stoppedcheck = QtCore.Signal()
    updated = QtCore.Signal(dict)

    def start_check(self):
        self.startedcheck.emit()

    def stop_check(self):
        self.stoppedcheck.emit()

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

