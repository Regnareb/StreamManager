import os
import sys
import copy
import socket
import logging
import threading
import functools
logger = logging.getLogger(__name__)
import keyboard
from PySide2 import QtCore, QtWidgets, QtGui, QtWebEngineWidgets

import common.manager
import common.remote
import common.tools


class QLoggerHandler(common.tools.HtmlStreamHandler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        message = self.format(record)
        self.signal.emit(QtCore.SIGNAL("logMsg(QString)"), message)


class LogPanel(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle('Logs')
        self.setObjectName('docklogs')
        self.levels = ['Debug', 'Info', 'Warning', 'Error', 'Critical']
        self.interface = {}
        self.interface['main'] = QtWidgets.QWidget()
        self.interface['layoutv'] = QtWidgets.QVBoxLayout()
        self.interface['layouth'] = QtWidgets.QHBoxLayout()
        self.interface['label'] = QtWidgets.QLabel('Logs Level:')
        self.interface['levels'] = QtWidgets.QComboBox()
        self.interface['levels'].insertItems(0, self.levels)
        self.interface['levels'].currentIndexChanged.connect(self.set_level)
        self.interface['textedit'] = QtWidgets.QTextBrowser()
        self.interface['textedit'].setOpenLinks(False)
        self.interface['layouth'].addStretch()
        self.interface['layouth'].addWidget(self.interface['label'])
        self.interface['layouth'].addWidget(self.interface['levels'])
        self.interface['layouth'].addStretch()
        self.interface['layoutv'].addLayout(self.interface['layouth'])
        self.interface['layoutv'].addWidget(self.interface['textedit'])
        self.interface['main'].setLayout(self.interface['layoutv'])
        self.setWidget(self.interface['main'])
        # Use old syntax signals as you can't have multiple inheritance with QObject
        self.emitter = QtCore.QObject()
        self.connect(self.emitter, QtCore.SIGNAL("logMsg(QString)"), self.interface['textedit'].append)
        self.handler = QLoggerHandler(self.emitter)
        formatter = logging.Formatter('<span title="line %(lineno)d">%(levelname)s %(name)s.%(funcName)s() - %(message)s</span>')
        self.handler.setFormatter(formatter)
        logging.getLogger().addHandler(self.handler)

    def set_level(self, level=''):
        if level not in self.levels:
            level = self.interface['levels'].currentText()
        attr = getattr(logging, level.upper())
        logging.getLogger().setLevel(attr)


class StreamManager_UI(common.systray.Window):
    def __init__(self):
        super().__init__()
        self.log_panel = LogPanel()
        self.setWindowTitle('Stream Manager')
        self.setIcon(QtGui.QIcon('icon.png'))
        self.load_stylesheet()
        self.setCentralWidget(None)
        self.manager = ManagerStreamThread()
        self.manager.create_services()
        self.manager.createdservices.connect(self.updated)
        self.manager.validate.connect(self.update_invalidcategory)
        self.manager.updated.connect(self.updated)
        self.webremote = WebRemote(self.manager.config['base']['autostart'])
        self.webremote.startedcheck.connect(self.start_check)
        self.webremote.stoppedcheck.connect(self.stop_check)
        self.webremote.start()
        self.preferences = Preferences(self.manager, self)
        self.preferences.updated.connect(self.preferences_updated)
        self.create_gamelayout()
        self.create_statuslayout()
        self.load_appdata()
        self.load_generalsettings()
        self.create_menu()
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas, QtWidgets.QTabWidget.North)
        self.setDockOptions(QtWidgets.QMainWindow.AllowNestedDocks | QtWidgets.QMainWindow.AllowTabbedDocks)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.log_panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.panel_status['dock'])
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.gameslayout['dock'])
        self.tabifyDockWidget(self.panel_status['dock'], self.gameslayout['dock'])
        self.tabifyDockWidget(self.gameslayout['dock'], self.log_panel)
        self.panel_status['dock'].raise_()
        self.setAcceptDrops(True)
        self.preferences_updated()
        self.set_shortcuts()
        self.read_qsettings()

    def set_dockable(self, state):
        self.dockable = state
        for i in [self.log_panel, self.gameslayout['dock'], self.panel_status['dock']]:
            dummy = None if state else QtWidgets.QWidget()
            i.setTitleBarWidget(dummy)

    def read_qsettings(self):
        self.settings = QtCore.QSettings('regnareb', 'Stream Manager')
        if self.settings.value('initialised_once'):
            self.restoreGeometry(self.settings.value('geometry'))
            self.restoreState(self.settings.value('windowState'))
            self.log_panel.interface['levels'].setCurrentIndex(self.log_panel.interface['levels'].findText(self.settings.value('logslevel')))
            logger.info('Loaded settings from last session.')
            self.set_dockable(self.settings.value('dockable'))
        else:
            self.first_launch()

    def first_launch(self):
        logger.info('First launch.')
        self.log_panel.set_level('Info')
        self.preferences.open()
        self.preferences.tabs.tabBar().hide()
        self.set_dockable(False)
        self.settings.setValue('initialised_once', 1)

    def closeEvent(self, event):
        if self.trayIcon.isVisible():
            if not self.settings.value('showed_quitmessage'):
                QtWidgets.QMessageBox.information(self, "Minimise to System Tray", "The program will keep running in the system tray. To terminate the program, choose <b>Quit</b> in the context menu of the system tray icon.")
            self.settings.setValue("showed_quitmessage", True)
            super().closeEvent(event)
        else:
            self.quit()

    def quit(self):
        self.manager.quit()
        self.webremote.quit()
        self.webremote.terminate()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("dockable", True if self.dockable else '')
        self.settings.setValue("logslevel", self.log_panel.interface['levels'].currentText())
        if not self.manager.save_config():
            msgBox = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Can't Save Preferences", "Couldn't save the preferences, you can copy its content in the \"Show Detail\" to try and salvage them, or send it to the developer for debug purposes.")
            msgBox.setDetailedText(str(self.manager.config))
            msgBox.setStandardButtons(QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
            msgBox.setDefaultButton(QtWidgets.QMessageBox.Close)
            ret = msgBox.exec_()
            if ret==QtWidgets.QMessageBox.Cancel:
                return
        super().quit()

    def preferences_updated(self):
        self.manager.process = ''
        try:
            self.reloadtimer.stop()
        except AttributeError:
            self.reloadtimer = QtCore.QTimer()
        if int(self.manager.config['base']['reload']):
            self.reloadtimer.timeout.connect(self.reload)
            self.reloadtimer.start(int(self.manager.config['base']['reload']) * 60000)

    def load_stylesheet(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'theme', 'qtstylesheet.css')
        with open(path) as f:
            stylesheet = f.read()
        self.setStyleSheet(stylesheet)

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.manager.load_credentials(url.toLocalFile())

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def start_check(self):
        self.manager.start()

    def stop_check(self):
        self.manager.quit()

    def updated(self, infos=None):
        self.reload()

    def reload(self):
        self.panel_status['webpage'].reload()

    def mouseDoubleClickEvent(self, *args):
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
        actionview = self.menuBar().addMenu('View')
        preferences = QtWidgets.QAction('&Preferences', self, triggered=self.preferences.open)
        preferences.setMenuRole(QtWidgets.QAction.PreferencesRole)
        actionview.addAction(preferences)
        actionview.addSeparator()
        actionview.addAction(self.panel_status['dock'].toggleViewAction())
        actionview.addAction(self.gameslayout['dock'].toggleViewAction())
        actionview.addAction(self.log_panel.toggleViewAction())

    def create_gamelayout(self):
        self.gameslayout = {}
        self.gameslayout['llayout'] = QtWidgets.QVBoxLayout()
        self.gameslayout['table'] = QtWidgets.QTableWidget()
        self.gameslayout['table'].setObjectName('table_games')
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

        elements = ['title', 'description', 'tags']
        folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'theme', 'images'))
        icons = {False: QtGui.QIcon(folder + "/unlock.png"), True: QtGui.QIcon(folder + "/lock.png")}
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

        self.gameslayout['category_layout'] = QtWidgets.QHBoxLayout()
        self.gameslayout['category_layout'].setSpacing(0)
        self.gameslayout['category_conflicts'] = QtWidgets.QPushButton('...')
        self.gameslayout['category_conflicts'].setStyleSheet('border: 1px solid rgba(0, 0, 0, 50); padding:4px')
        self.gameslayout['category_conflicts'].setFixedWidth(self.gameslayout['category_conflicts'].sizeHint().height())
        self.gameslayout['category_conflicts'].clicked.connect(self.show_assignations)
        self.gameslayout['category'] = LineEdit(icons)
        self.gameslayout['category'].editingFinished.connect(functools.partial(self.save_appdata, validate=True))
        self.gameslayout['category_layout'].addWidget(self.gameslayout['category_conflicts'])
        self.gameslayout['category_layout'].addWidget(self.gameslayout['category'])
        self.gameslayout['rlayout'].insertLayout(2, self.gameslayout['category_layout'])

        self.gameslayout['description'].setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding))
        self.gameslayout['rlayout'].addStretch()

        self.gameslayout['container_llayout'] = QtWidgets.QWidget()
        self.gameslayout['container_llayout'].setLayout(self.gameslayout['llayout'])
        self.gameslayout['container_rlayout'] = QtWidgets.QWidget()
        self.gameslayout['container_rlayout'].setLayout(self.gameslayout['rlayout'])
        self.gameslayout['dock'] = QtWidgets.QDockWidget('Games')
        self.gameslayout['dock'].setObjectName('dockgames')
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

    def save_appdata(self, validate=False):
        current = self.gameslayout['table'].currentItem()
        cat = self.gameslayout['category'].text()
        title = self.gameslayout['title'].text()
        desc = self.gameslayout['description'].toPlainText()
        tags = self.gameslayout['tags'].text().split(',')
        tags = [i.strip() for i in tags if i]
        data = {'category': cat, 'title': title, 'description': desc, 'tags': tags}
        if validate:
            self.manager.config['assignations'] = self.manager.validate_assignations(self.manager.config['assignations'], cat)
        if current:
            self.manager.config['appdata'][current._process].update(data)
            self.update_gamerow(current)
        else:
            for key in data.copy():
                data['forced_' + key] = self.gameslayout[key].button.state
                self.manager.config['base'].update(data)
        self.manager.process = ''  # Reset current process to be able to apply new settings
        logger.debug(data)

    def show_assignations(self):
        category = self.gameslayout['category'].text()
        self.preferences.open()
        self.preferences.tabs.setCurrentIndex(1)
        self.preferences.tabs.tabBar().hide()
        if category:
            index = self.preferences.tab_assignations.interface['processes'].findText(category)
            self.preferences.tab_assignations.interface['processes'].setCurrentIndex(index)

    def update_invalidcategory(self, category):
        isvalid = [i['valid'] for i in self.manager.config['assignations'].get(category, {}).values()]
        if all(isvalid):
            self.gameslayout['category_conflicts'].setStyleSheet('background: rgba(0, 0, 0, 15)')
        elif category == self.gameslayout['category'].text():
            self.gameslayout['category_conflicts'].setStyleSheet('background: rgba(255, 0, 0, 255)')
        current = self.gameslayout['table'].currentItem()
        if current:
            self.update_gamerow(current)

    def update_gamerow(self, row):
        category = self.manager.config['appdata'][row._process].get('category', '')
        row.setText('{} ({})'.format(category, row._process))
        isvalid = [i['valid'] for i in self.manager.config['assignations'].get(category, {}).values()]
        if all(isvalid):
            row.setBackground(QtGui.QBrush())
        else:
            row.setBackground(QtGui.QColor(255,0,0))

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
        block_signals(self.gameslayout.values(), True)
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
            self.update_invalidcategory(val.get('category'))
        block_signals(self.gameslayout.values(), False)

    def load_generalsettings(self, *args):
        block_signals(self.gameslayout.values(), True)
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
        self.update_invalidcategory(val.get('category'))
        block_signals(self.gameslayout.values(), False)

    def set_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("F11"), self, self.mouseDoubleClickEvent)
        QtWidgets.QShortcut(QtGui.QKeySequence("F5"), self, self.reload)
        keyboard.add_hotkey(self.manager.config['shortcuts']['createclip'], self.manager.create_clip)

    def create_statuslayout(self):
        self.panel_status = {}
        self.panel_status['dock'] = QtWidgets.QDockWidget('Status')
        self.panel_status['dock'].setObjectName('dockstatus')
        self.panel_status['webpage'] = QtWebEngineWidgets.QWebEngineView()
        self.panel_status['webpage'].setAcceptDrops(False)
        self.panel_status['webpage'].page().profile().clearHttpCache()
        self.panel_status['webpage'].load(QtCore.QUrl("http://localhost:8080/"))
        self.panel_status['dock'].setWidget(self.panel_status['webpage'])


def block_signals(iterable, block):
    for i in iterable:
        i.blockSignals(block)


class Preferences(QtWidgets.QDialog):
    updated = QtCore.Signal()

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.tabs = QtWidgets.QTabWidget()
        self.tab_general = Preferences_General(manager)
        self.tab_streams = Preferences_Streams(manager)
        self.tab_assignations = Preferences_Assignations(manager)
        self.tab_pauseprocesses = Preferences_Pauseprocesses(manager)
        self.tab_pauseservices = Preferences_Pauseservices(manager)
        self.tabs.addTab(self.tab_general, "General")
        self.tabs.addTab(self.tab_streams, "Streams")
        self.tabs.addTab(self.tab_assignations, "Game Assignations")
        self.tabs.addTab(self.tab_pauseprocesses, "Pause Processes")
        if sys.platform == 'win32':
            self.tabs.addTab(self.tab_pauseservices, "Pause Windows Services")

        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.addWidget(self.tabs)
        self.mainLayout.addWidget(self.buttons)
        self.setLayout(self.mainLayout)
        self.setWindowTitle('Preferences')

    def reset(self):
        self.tabs.tabBar().show()
        self.tab_general.reset()
        self.tab_streams.reset()
        self.tab_pauseservices.reset()
        self.tab_pauseprocesses.reset()
        self.tab_assignations.reset()

    def accept(self):
        self.tab_general.accept()
        self.tab_streams.accept()
        self.tab_pauseservices.accept()
        self.tab_pauseprocesses.accept()
        self.tab_assignations.accept()
        self.updated.emit()
        super().accept()

    def open(self):
        self.reset()
        super().open()


class Preferences_General(QtWidgets.QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.interface = {}
        self.interface['layout'] = QtWidgets.QFormLayout()
        self.interface['autostart'] = QtWidgets.QCheckBox()
        self.interface['checktimer'] = QtWidgets.QLineEdit()
        self.interface['reload'] = QtWidgets.QLineEdit()
        self.interface['timeout'] = QtWidgets.QLineEdit()
        self.interface['label_autostart'] = QtWidgets.QLabel('Automatically start the check on launch')
        self.interface['label_checktimer'] = QtWidgets.QLabel('Check the foreground process every (x) seconds')
        self.interface['label_reload'] = QtWidgets.QLabel('Reload the status webpage every (x) minutes')
        self.interface['label_timeout'] = QtWidgets.QLabel('Number of seconds before the token creation timeouts')
        self.interface['label_autostart'].setMinimumHeight(30)
        self.interface['label_checktimer'].setMinimumHeight(30)
        self.interface['label_reload'].setMinimumHeight(30)
        self.interface['label_timeout'].setMinimumHeight(30)
        self.interface['autostart'].setMinimumHeight(30)
        self.interface['checktimer'].setMinimumHeight(30)
        self.interface['reload'].setMinimumHeight(30)
        self.interface['timeout'].setMinimumHeight(30)

        self.interface['line'] = QtWidgets.QFrame()
        self.interface['line'].setObjectName('stream_line')
        self.interface['line'].setFrameShape(QtWidgets.QFrame.HLine)

        self.interface['label_createclip'] = QtWidgets.QLabel('Create Clip')
        self.interface['shortcut_createclip'] = KeySequenceRecorder('')
        self.interface['label_createclip'].setMinimumHeight(30)
        self.interface['shortcut_createclip'].setMinimumHeight(30)

        self.interface['layout'].addRow(self.interface['label_autostart'], self.interface['autostart'])
        self.interface['layout'].addRow(self.interface['label_checktimer'], self.interface['checktimer'])
        self.interface['layout'].addRow(self.interface['label_reload'], self.interface['reload'])
        self.interface['layout'].addRow(self.interface['label_timeout'], self.interface['timeout'])
        self.interface['layout'].addRow(self.interface['line'])
        self.interface['layout'].addRow(self.interface['label_createclip'], self.interface['shortcut_createclip'])
        self.setLayout(self.interface['layout'])

    def accept(self):
        self.manager.config['base']['checktimer'] = self.interface['checktimer'].text()
        self.manager.config['base']['autostart'] = self.interface['autostart'].isChecked()
        self.manager.config['base']['reload'] = self.interface['reload'].text()
        self.manager.config['base']['timeout'] = self.interface['timeout'].text()
        self.manager.config['shortcuts']['createclip'] = self.interface['shortcut_createclip'].text()
        socket.setdefaulttimeout(int(self.manager.config['base']['timeout']))

    def reset(self):
        self.interface['checktimer'].setText(self.manager.config['base']['checktimer'])
        self.interface['autostart'].setChecked(self.manager.config['base']['autostart'])
        self.interface['reload'].setText(self.manager.config['base']['reload'])
        self.interface['timeout'].setText(self.manager.config['base']['timeout'])
        self.interface['shortcut_createclip'].setText(self.manager.config['shortcuts']['createclip'])


class Preferences_Assignations(QtWidgets.QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.interface = {}
        self.interface['layout'] = QtWidgets.QVBoxLayout()
        self.interface['label'] = QtWidgets.QLabel('Some stream services do not use the same name for the same activity. You can match the category for each services.\nFor example Youtube has only "Gaming" and no specific game in its database.')
        self.interface['label'].setAlignment(QtCore.Qt.AlignCenter)
        self.interface['hlayout'] = QtWidgets.QHBoxLayout()
        self.interface['processes'] = QtWidgets.QComboBox()
        self.interface['validate'] = QtWidgets.QPushButton('Check All')
        self.interface['processes'].setFixedHeight(27)
        self.interface['validate'].setFixedHeight(27)
        self.interface['validate'].clicked.connect(self.validate)
        self.interface['table'] = QtWidgets.QTableWidget()
        self.interface['table'].horizontalHeader().setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.interface['table'].verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.interface['table'].horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.interface['table'].setWordWrap(True)
        self.interface['hlayout'].addWidget(self.interface['processes'])
        self.interface['hlayout'].addWidget(self.interface['validate'])
        self.interface['layout'].addWidget(self.interface['label'])
        self.interface['layout'].addLayout(self.interface['hlayout'])
        self.interface['layout'].addWidget(self.interface['table'])
        self.servicesorder = sorted(common.manager.SERVICES)
        self.setLayout(self.interface['layout'])
        self.set_layoutvertical()

    def set_layoutvertical(self):
        self.interface['processes'].show()
        self.interface['processes'].currentIndexChanged.connect(self.populate)
        self.interface['table'].insertColumn(0)
        for service in self.servicesorder:
            rowcount = self.interface['table'].rowCount()
            self.interface['table'].insertRow(rowcount)
            widget = QtWidgets.QLineEdit()
            widget.editingFinished.connect(functools.partial(self.save_assignation, service))
            widget.textEdited.connect(functools.partial(self.edited, widget, service))
            self.interface['table'].setCellWidget(rowcount, 0, widget)
            if not common.manager.SERVICES[service].Main.features['category']:
                widget.setDisabled(True)
            self.interface['line_' + service] = widget

        self.interface['table'].setVerticalHeaderLabels(self.servicesorder)
        self.interface['table'].horizontalHeader().setVisible(False)

    def edited(self, widget, service, text):
        # Add a QTimer to prevent lag
        service = self.manager.services.get(service)
        if service:
            autocompletion = service.query_category(text)
            self.interface['completer'] = QtWidgets.QCompleter(list(autocompletion.keys()))
            self.interface['completer'].setCompletionMode(QtWidgets.QCompleter.UnfilteredPopupCompletion)
            self.interface['completer'].activated.connect(functools.partial(self.set_validautocomplete, service.name))  # If activated() then validated automatically
            widget.setCompleter(self.interface['completer'])

    def set_validautocomplete(self, service, text):
        """Force validation of the current category and service."""
        current = self.interface['processes'].currentText()
        self.temporary_settings.setdefault(current, {}).setdefault(service, {})
        self.temporary_settings[current][service] = {'name': text, 'valid': True}
        self.populate()

    def validate(self, category=None):
        if category:
            category = self.interface['processes'].currentText()
        self.temporary_settings = self.manager.validate_assignations(self.temporary_settings, category)
        self.populate()

    def populate(self):
        block_signals(self.interface.values(), True)
        current = self.interface['processes'].currentText()
        for index, service in enumerate(self.servicesorder):
            text = self.temporary_settings.get(current, {}).get(service, {}).get('name', '')
            valid = self.temporary_settings.get(current, {}).get(service, {}).get('valid', '')
            disabled = not common.manager.SERVICES[service].Main.features['category']
            widget = self.interface['line_' + service]
            widget.setText(text or '')
            if disabled:
                widget.setStyleSheet('background-color:#efefef;border: transparent')
            elif not valid:
                widget.setStyleSheet('background-color:#faa;border: transparent')
            else:
                widget.setStyleSheet('background-color:transparent')
        block_signals(self.interface.values(), False)

    def save_assignation(self, service):
        category = self.interface['processes'].currentText()
        widget = self.interface['line_' + service]
        current = widget.text()
        old = self.temporary_settings.get(category, {}).get(service, {}).get('name', '')
        if category and current != old:
            self.temporary_settings.setdefault(category, {}).setdefault(service, {})
            self.temporary_settings[category][service] = {'name': current, 'valid': ''}
            self.validate(category)

    def accept(self):
        assignations = self.manager.validate_assignations(self.temporary_settings)
        self.manager.config['assignations'] = assignations

    def reset(self):
        block_signals(self.interface.values(), True)
        self.temporary_settings = copy.deepcopy(self.manager.config['assignations'])
        self.interface['processes'].clear()
        categories = [i['category'] for i in self.manager.config['appdata'].values()]
        self.interface['processes'].insertItems(0, categories)
        self.populate()
        block_signals(self.interface.values(), False)


class Preferences_Streams(QtWidgets.QWidget):
    def __init__(self, manager, parent=None):
        # add get token button
        super().__init__(parent)
        self.manager = manager
        self.panel_services = {}
        self.panel_services['container'] = QtWidgets.QGridLayout()

        self.panel_services['llayout'] = QtWidgets.QVBoxLayout()
        self.panel_services['list'] = QtWidgets.QTableWidget()
        self.panel_services['list'].setObjectName('table_services')
        self.panel_services['list'].setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.panel_services['list'].setColumnCount(1)
        self.panel_services['list'].setWordWrap(False)
        self.panel_services['list'].verticalHeader().setVisible(False)
        self.panel_services['list'].verticalHeader().setDefaultSectionSize(40)
        self.panel_services['list'].horizontalHeader().setVisible(False)
        self.panel_services['list'].horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.panel_services['list'].currentCellChanged.connect(self.service_changed)
        self.panel_services['list'].setFixedWidth(150)
        self.panel_services['llayout'].addWidget(self.panel_services['list'])
        self.elements = ['enabled', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url', 'client_id', 'client_secret']
        self.panel_services['formlayout'] = QtWidgets.QFormLayout()
        for elem in self.elements[1:]:
            namelabel = 'label_' + elem
            nameline = 'line_' + elem
            self.panel_services[namelabel] = QtWidgets.QLabel(elem.replace('_', ' ').capitalize())
            if elem in ['client_id', 'client_secret']:
                self.panel_services[nameline] = LineditSpoiler()
                self.panel_services[nameline].setProperty('mandatory', True)
            else:
                self.panel_services[nameline] = QtWidgets.QLineEdit()

            self.panel_services[namelabel].setFixedHeight(30)
            self.panel_services[nameline].setFixedHeight(30)
            self.panel_services[nameline].editingFinished.connect(functools.partial(self.save_servicedata, elem))
            self.panel_services['formlayout'].addRow(self.panel_services[namelabel], self.panel_services[nameline])
            self.panel_services[namelabel].setObjectName(namelabel)

        self.panel_services['label_enabled'] = QtWidgets.QLabel('Enabled')
        self.panel_services['line_enabled'] = QtWidgets.QPushButton()
        self.panel_services['line_enabled'].setCheckable(True)
        self.panel_services['line_enabled'].setFixedWidth(71)
        self.panel_services['line_enabled'].setObjectName('enable_service')
        self.panel_services['line_enabled'].clicked.connect(functools.partial(self.save_servicedata, 'enabled'))
        self.panel_services['label_enabled'].setMinimumHeight(30)
        self.panel_services['line_enabled'].setMinimumHeight(30)

        self.panel_services['reset_token'] = QtWidgets.QPushButton('Reset Auth')
        self.panel_services['reset_token'].clicked.connect(self.reset_token)
        self.panel_services['reset_token'].setMinimumHeight(30)
        self.panel_services['hlayout'] = QtWidgets.QHBoxLayout()
        self.panel_services['hlayout'].addWidget(self.panel_services['label_enabled'])
        self.panel_services['hlayout'].addWidget(self.panel_services['line_enabled'])
        self.panel_services['hlayout'].addStretch()
        self.panel_services['hlayout'].addWidget(self.panel_services['reset_token'])

        self.panel_services['line'] = QtWidgets.QFrame()
        # self.panel_services['line'].setMinimumHeight(30)
        self.panel_services['line'].setObjectName('stream_line')
        self.panel_services['line'].setFrameShape(QtWidgets.QFrame.HLine)

        self.panel_services['features_layout'] = QtWidgets.QVBoxLayout()
        self.panel_services['features_layout'].setSpacing(0)
        self.panel_services['label_features'] = QtWidgets.QLabel('Features')
        self.panel_services['label_features'].setDisabled(True)
        features = list(common.manager.SERVICES['Facebook'].Main.features.keys())
        for feat in features:
            name = 'feature_' + feat
            self.panel_services[name] = QtWidgets.QLabel(feat)
            self.panel_services[name].setAlignment(QtCore.Qt.AlignCenter)
            self.panel_services[name].setObjectName('features')
            self.panel_services['features_layout'].addWidget(self.panel_services['feature_' + feat])
            if feat == features[0]:
                updateStyle(self.panel_services[name], 'firstv', True)
            elif feat == features[-1]:
                updateStyle(self.panel_services[name], 'lastv', True)

        self.panel_services['container'].addLayout(self.panel_services['llayout'], 0, 0, -1, 1)
        self.panel_services['container'].addLayout(self.panel_services['hlayout'], 0, 1, 1, -1)
        self.panel_services['container'].addWidget(self.panel_services['line'], 1, 1, 1, -1)
        self.panel_services['container'].addLayout(self.panel_services['features_layout'], 3, 1)
        self.panel_services['container'].addLayout(self.panel_services['formlayout'], 3, 3, -1, 1)
        self.panel_services['container'].setRowStretch(self.panel_services['container'].rowCount(), 1)
        self.setLayout(self.panel_services['container'])
        self.panel_services['list'].itemSelectionChanged.connect(self.service_changed)

    def paintEvent(self, paintEvent):
        item = self.panel_services['list'].currentItem()
        service = item.text()
        imgpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'theme', 'images', service + '.png'))
        if os.path.isfile(imgpath):
            pixmap = QtGui.QPixmap()
            pixmap.load(imgpath)
            widWidth = self.width()
            widHeight = self.height()
            pixmap = pixmap.scaled(10, widHeight, QtCore.Qt.KeepAspectRatioByExpanding)
            paint = QtGui.QPainter(self)
            paint.setOpacity(0.3)
            paint.drawPixmap(widWidth-pixmap.width()*0.8, -pixmap.height()*0.2, pixmap)

    def create_services(self):
        self.panel_services['list'].blockSignals(True)
        while self.panel_services['list'].rowCount():
            self.panel_services['list'].removeRow(0)
        for service in common.manager.SERVICES:
            row = StreamTableWidgetItem(service)
            rowcount = self.panel_services['list'].rowCount()
            self.panel_services['list'].insertRow(rowcount)
            self.panel_services['list'].setItem(rowcount, 0, row)
            row.set_disabledrowstyle(self.temporary_settings[service].get('enabled', False))
        self.panel_services['list'].sortItems(QtCore.Qt.AscendingOrder)
        self.panel_services['list'].blockSignals(False)

    def service_changed(self):
        block_signals(self.panel_services.values(), True)
        item = self.panel_services['list'].currentItem()
        service = item.text()
        config = self.temporary_settings[service]
        for elem in self.elements:
            if elem == 'enabled':
                val = config.get(elem, False)
                self.panel_services['line_' + elem].setChecked(val)
                item.set_disabledrowstyle(val)
            else:
                self.panel_services['line_' + elem].setText(str(config.get(elem, '')))
        features = common.manager.SERVICES[service].Main.features
        for feat, state in features.items():
            updateStyle(self.panel_services['feature_' + feat], 'available', state)
        self.repaint()
        block_signals(self.panel_services.values(), False)

    def check_service(self):
        item = self.panel_services['list'].currentItem()
        service = item.text()
        state = self.panel_services['line_enabled'].isChecked()
        if state:
            service = self.manager.create_service(service, self.temporary_settings[service], force=True)
            if service:
                self.temporary_settings[service.name] = service.config  # Save access token
                return True
            if not service:
                self.panel_services['line_enabled'].setChecked(False)
                self.save_servicedata('enabled')
                QtWidgets.QToolTip().showText(self.panel_services['line_enabled'].mapToGlobal(QtCore.QPoint(0, 20)), "<nobr>Couldn't create the service.</nobr><br><nobr>Check your <b style='color:red'>client id</b> and <b style='color:red'>client secret</b> below.</nobr>")
                return False
        else:
            self.manager.deactivate_service(service)
            return False

    def save_servicedata(self, element):
        item = self.panel_services['list'].currentItem()
        service = item.text()
        if element == 'enabled':
            result = self.panel_services['line_enabled'].isChecked()
        else:
            result = self.panel_services['line_' + element].text()
        if self.temporary_settings[service][element] != result:
            self.temporary_settings[service][element] = result
            if element != 'enabled':
                self.reset_token()
            self.check_service()
            item.set_disabledrowstyle(self.temporary_settings[service]['enabled'])

    def reset_token(self):
        service = self.panel_services['list'].currentItem().text()
        self.temporary_settings[service]['authorization'] = {}
        self.check_service()

    def accept(self):
        for service in self.temporary_settings:
            self.manager.config['streamservices'][service] = self.temporary_settings[service]
        self.manager.services = {}
        self.manager.create_services()

    def reset(self):
        self.temporary_settings = copy.deepcopy(self.manager.config['streamservices'])
        self.create_services()
        self.panel_services['list'].setCurrentCell(0, 0)


class StreamTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __init__(self, service):
        super().__init__()
        self.service = service
        imgpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'theme', 'images', self.service + '.png'))
        self.setIcon(QtGui.QPixmap(imgpath))
        self.setText(self.service)
        self.setFlags(self.flags() & ~QtCore.Qt.ItemIsEditable)

    def set_disabledrowstyle(self, val):
        if val:
            color = QtGui.QColor.fromRgbF(0.282, 0.855, 0.255, 1)
            self.setForeground(QtGui.QColor(0, 0, 0))
        else:
            color = QtGui.QColor.fromRgbF(1, 0, 0, 1)
            self.setForeground(QtGui.QColor(150, 150, 150))
        gradient = QtGui.QRadialGradient(130, 20, 5, 120, 20)
        gradient.setColorAt(0, color)
        gradient.setColorAt(0.8, color)
        gradient.setColorAt(1, QtGui.QColor.fromRgbF(0, 0, 0, 0))
        self.setBackground(QtGui.QBrush(gradient))


class Preferences_Pause(QtWidgets.QWidget):
    def __init__(self, manager, name, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.config = self.manager.config['base'][name]
        self.panel_pause = {}
        self.panel_pause['container'] = QtWidgets.QGridLayout()
        self.panel_pause['label'] = QtWidgets.QLabel('When you start the "automatic check" any entry on the right side will be paused until the "automatic check" is stopped.<br>Usefull for automatically pausing applications that use bandwith or CPU.')
        self.panel_pause['label'].setAlignment(QtCore.Qt.AlignCenter)

        for elem in ['list', 'list_pause']:
            self.panel_pause[elem] = QtWidgets.QTableWidget()
            self.panel_pause[elem].setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.panel_pause[elem].setColumnCount(1)
            self.panel_pause[elem].setWordWrap(False)
            self.panel_pause[elem].verticalHeader().setVisible(False)
            self.panel_pause[elem].horizontalHeader().setVisible(False)
            self.panel_pause[elem].horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        self.panel_pause['refresh'] = QtWidgets.QPushButton('🔃')
        self.panel_pause['add'] = QtWidgets.QPushButton('→')
        self.panel_pause['remove'] = QtWidgets.QPushButton('←')
        self.panel_pause['refresh'].setFlat(True)
        self.panel_pause['add'].setFlat(True)
        self.panel_pause['remove'].setFlat(True)

        self.panel_pause['refresh'].clicked.connect(self.populate_pauseprocess)
        self.panel_pause['add'].clicked.connect(functools.partial(self.transfer_pauseprocess, 'add'))
        self.panel_pause['remove'].clicked.connect(functools.partial(self.transfer_pauseprocess, 'remove'))

        self.panel_pause['addremove_widget'] = QtWidgets.QWidget()
        self.panel_pause['addremove_layout'] = QtWidgets.QVBoxLayout()

        self.panel_pause['addremove_layout'].addWidget(self.panel_pause['refresh'])
        self.panel_pause['addremove_layout'].addStretch()
        self.panel_pause['addremove_layout'].addWidget(self.panel_pause['add'])
        self.panel_pause['addremove_layout'].addWidget(self.panel_pause['remove'])
        self.panel_pause['addremove_layout'].addStretch()
        self.panel_pause['addremove_widget'].setLayout(self.panel_pause['addremove_layout'])

        self.setLayout(self.panel_pause['container'])
        self.panel_pause['container'].addWidget(self.panel_pause['label'], 0, 0, 1, -1)
        self.panel_pause['container'].addWidget(self.panel_pause['list'], 1, 0, -1, 1)
        self.panel_pause['container'].addWidget(self.panel_pause['addremove_widget'], 1, 1, -1, 1)
        self.panel_pause['container'].addWidget(self.panel_pause['list_pause'], 1, 2, -1, 1)

    def populate_pauseprocess(self):
        while self.panel_pause['list'].rowCount():
            self.panel_pause['list'].removeRow(0)
        while self.panel_pause['list_pause'].rowCount():
            self.panel_pause['list_pause'].removeRow(0)
        self.currentprocesses = self.list_processes()

        def insertrow(name, destination):
            row = QtWidgets.QTableWidgetItem()
            row.setText(name)
            rowcount = destination.rowCount()
            destination.insertRow(rowcount)
            destination.setItem(rowcount, 0, row)

        done = []
        for service in self.currentprocesses.values():
            if service['name'] in self.currentconfig:
                insertrow(service['name'], self.panel_pause['list_pause'])
            else:
                insertrow(service['name'], self.panel_pause['list'])
            done.append(service['name'])

        for process in self.currentconfig:
            if process not in done:
                insertrow(process, self.panel_pause['list_pause'])

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
            self.panel_pause['list'].sortByColumn(0, QtCore.Qt.AscendingOrder)
            self.panel_pause['list_pause'].sortByColumn(0, QtCore.Qt.AscendingOrder)
            if operation == 'add':
                self.currentconfig.append(item)
            else:
                self.currentconfig.remove(item)

    def list_processes(self):
        return {}

    def accept(self):
        rowdata = []
        for row in range(self.panel_pause['list_pause'].rowCount()):
            item = self.panel_pause['list_pause'].item(row, 0)
            rowdata.append(item.text())
        self.config.clear()
        [self.config.append(i) for i in rowdata]

    def reset(self):
        self.currentconfig = self.config.copy()
        self.populate_pauseprocess()


class Preferences_Pauseservices(Preferences_Pause):
    def __init__(self, manager, parent=None):
        super().__init__(manager, 'services', parent)
        sizepolicy = self.panel_pause['refresh'].sizePolicy()
        sizepolicy.setRetainSizeWhenHidden(True)
        self.panel_pause['refresh'].setSizePolicy(sizepolicy)
        self.panel_pause['refresh'].hide()
        if sys.platform == 'win32':
            admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if not admin:
                self.panel_pause['label'].setText(self.panel_pause['label'].text() + '<br><b style="color:red">Requires Admin Rights!</b>')
                self.disable_all()

    def disable_all(self):
        for i in self.panel_pause.values():
            try:
                i.setDisabled(True)
            except AttributeError:
                pass

    def list_processes(self):
        return common.tools.listservices()

    def populate_pauseprocess(self):
        super().populate_pauseprocess()
        for service in self.currentprocesses.values():
            try:
                item = self.panel_pause['list'].findItems(service['name'], QtCore.Qt.MatchExactly)[0]
            except IndexError:
                item = self.panel_pause['list_pause'].findItems(service['name'], QtCore.Qt.MatchExactly)[0]
            tooltip = '{} ({})\n\n{}'.format(service['display_name'], service['status'].upper(), service['description'].replace('. ', '.\n'))
            item.setToolTip(tooltip.strip())


class Preferences_Pauseprocesses(Preferences_Pause):
    def __init__(self, manager, parent=None):
        super().__init__(manager, 'processes', parent)

    def list_processes(self):
        return common.tools.listprocesses()

    def populate_pauseprocess(self):
        super().populate_pauseprocess()
        for process in self.currentprocesses.values():
            try:
                name = process['name']
                item = self.panel_pause['list'].findItems(name, QtCore.Qt.MatchExactly)[0]
            except IndexError:
                item = self.panel_pause['list_pause'].findItems(name, QtCore.Qt.MatchExactly)[0]
            tooltip = '{0} ({1:.2f}% RAM)\n{2}'.format(name, process['memory_percent'], process['exe'])
            item.setToolTip(tooltip.strip())


class WebRemote(common.remote.WebRemote, QtCore.QThread):
    startedcheck = QtCore.Signal()
    stoppedcheck = QtCore.Signal()

    def __init__(self, autostart=True):
        super().__init__()
        self.running = autostart

    def start_check(self):
        self.startedcheck.emit()

    def stop_check(self):
        self.stoppedcheck.emit()

    def run(self):
        if self.running:
            self.start_check()
        self.server()
        self.exec_()


class ManagerStreamThread(common.manager.ManageStream, QtCore.QThread):
    validate = QtCore.Signal(str)
    updated = QtCore.Signal(dict)
    createdservices = QtCore.Signal()

    def run(self):
        with common.tools.pause_processes(self.config['base']['processes']):
            with common.tools.pause_services(self.config['base']['services']):
                self.create_services()
                self.checktimer = QtCore.QTimer()
                self.checktimer.timeout.connect(self.main)
                self.checktimer.start(int(self.config['base']['checktimer']) * 1000)
                self.exec_()

    def main(self):
        result = self.check_application()
        if result:
            self.updated.emit(result)
            logger.info(result)

    def create_services(self):
        super().create_services()
        self.createdservices.emit()

    # @common.tools.threaded
    def validate_assignations(self, config, category=None):
        result = super().validate_assignations(config, category)
        if category:
            self.validate.emit(category)
        return result

    def load_credentials(self, path=''):
        if super().load_credentials(path) == False:
            QtWidgets.QMessageBox.warning(None, "Can't Load Credentials File", "The JSON file must be wrong, check your file with text editor or the person who sent it to you.", QtWidgets.QMessageBox.StandardButton.Ok)

    def load_config(self):
        if super().load_config() == False:
            msgBox = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Can't Load Preference File", "The JSON file must be wrong, the preferences has been reset. The old preferences are still available at this path:\n{}".format(self.config_filepath+'_error'))
            msgBox.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            msgBox.exec_()


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


class LineditSpoiler(QtWidgets.QLineEdit):
    def __init__(self, blurAmount=10, parent=None):
        super().__init__(parent=parent)
        self.blurAmount = blurAmount
        self.effect = QtWidgets.QGraphicsBlurEffect(self)
        self.effect.setBlurRadius(blurAmount)
        self.setGraphicsEffect(self.effect)

    def enterEvent(self, event):
        self.effect.setBlurRadius(0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.effect.setBlurRadius(self.blurAmount)
        super().leaveEvent(event)


class KeySequenceRecorder(QtWidgets.QLineEdit):
    def __init__(self, keySequence, parent=None):
        super().__init__(parent)
        self.setKeySequence(keySequence)

    def setKeySequence(self, keySequence):
        try:
            self.keySequence = keySequence.toString(QtGui.QKeySequence.NativeText)
        except AttributeError:
            self.keySequence = keySequence
        self.setText(self.keySequence)

    def keyPressEvent(self, e):
        if e.type() == QtCore.QEvent.KeyPress:
            key = e.key()
            if key == QtCore.Qt.Key_unknown:
                logger.warning('Unknown key for shortcut')
                return
            if(key == QtCore.Qt.Key_Control or
            key == QtCore.Qt.Key_Shift or
            key == QtCore.Qt.Key_Alt or
            key == QtCore.Qt.Key_Meta):
                return
            modifiers = e.modifiers()
            if modifiers & QtCore.Qt.ShiftModifier:
                key += QtCore.Qt.SHIFT
            if modifiers & QtCore.Qt.ControlModifier:
                key += QtCore.Qt.CTRL
            if modifiers & QtCore.Qt.AltModifier:
                key += QtCore.Qt.ALT
            if modifiers & QtCore.Qt.MetaModifier:
                key += QtCore.Qt.META
            self.setKeySequence(QtGui.QKeySequence(key))


def updateStyle(obj, name, value):
    obj.setProperty(name, value)
    obj.setStyle(obj.style())




