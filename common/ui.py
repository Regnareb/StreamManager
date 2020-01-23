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


STYLESHEET = """
#table_games QHeaderView::section { background-color: #3697FE;border:1px solid #ccc;font-weight: bold}
#table_games QHeaderView::section:checked { background-color: #fff;border:1px solid #ccc;}
"""


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
        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle('Stream Manager')
        self.setCentralWidget(None)
        self.manager = ManagerStreamThread()
        self.manager.create_services()
        self.webremote = WebRemote()
        self.webremote.start()
        self.preferences = Preferences(self.manager, self)
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
        self.manager.createdservices.connect(self.updated)
        self.webremote.startedcheck.connect(self.start_check)
        self.webremote.stoppedcheck.connect(self.stop_check)
        self.webremote.updated.connect(self.updated)
        self.manager.validate.connect(self.update_invalidcategory)
        self.manager.updated.connect(self.updated)

    def start_check(self):
        self.manager.start()

    def stop_check(self):
        self.manager.quit()

    def updated(self, infos=None):
        self.panel_status['webpage'].reload()

    def closeEvent(self, event):
        self.manager.quit()
        self.webremote.quit()
        self.webremote.terminate()
        super().closeEvent(event)

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.manager.load_credentials(url.toLocalFile())

    def dragEnterEvent(self, event):
        event.acceptProposedAction()
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
        action = QtWidgets.QAction('Preferences', self, triggered=self.preferences.open)
        self.menuBar().addAction(action)

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
        if category:
            self.preferences.open()
            self.preferences.tabs.setCurrentIndex(1)
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

    def create_statuslayout(self):
        self.panel_status = {}
        self.panel_status['dock'] = QtWidgets.QDockWidget('Status')
        self.panel_status['webpage'] = QtWebEngineWidgets.QWebEngineView()
        self.panel_status['webpage'].page().profile().clearHttpCache()
        self.panel_status['webpage'].load(QtCore.QUrl("http://localhost:8080/"))
        self.panel_status['dock'].setWidget(self.panel_status['webpage'])


def block_signals(iterable, block):
    for i in iterable:
        i.blockSignals(block)

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
        self.tab_assignations = Preferences_Assignations(manager)
        self.tab_pauseprocesses = Preferences_Pauseprocesses(manager)
        self.tab_pauseservices = Preferences_Pauseservices(manager)
        self.tabs.addTab(self.tab_streams, "Streams")
        self.tabs.addTab(self.tab_assignations, "Game Assignations")
        self.tabs.addTab(self.tab_pauseprocesses, "Processes")
        self.tabs.addTab(self.tab_pauseservices, "Services (Windows)")

        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.addWidget(self.tabs)
        self.mainLayout.addWidget(self.buttons)
        self.setLayout(self.mainLayout)
        self.setWindowTitle('Preferences')


    def reset(self):
        self.tab_streams.reset()
        self.tab_pauseservices.reset()
        self.tab_pauseprocesses.reset()
        self.tab_assignations.reset()

    def accept(self):
        self.tab_streams.accept()
        self.tab_pauseservices.accept()
        self.tab_pauseprocesses.accept()
        self.tab_assignations.accept()
        super().accept()


    def open(self):
        self.reset()
        super().open()


class Preferences_Assignations(QtWidgets.QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.interface = {}
        self.interface['layout'] = QtWidgets.QVBoxLayout()
        self.interface['hlayout'] = QtWidgets.QHBoxLayout()
        self.interface['processes'] = QtWidgets.QComboBox()
        self.interface['validate'] = QtWidgets.QPushButton('Check All')
        self.interface['validate'].clicked.connect(self.validate)
        self.interface['table'] = QtWidgets.QTableWidget()
        self.interface['table'].horizontalHeader().setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.interface['table'].verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.interface['table'].horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.interface['table'].setWordWrap(True)
        self.interface['hlayout'].addWidget(self.interface['processes'])
        self.interface['hlayout'].addWidget(self.interface['validate'])
        self.interface['layout'].addLayout(self.interface['hlayout'])
        self.interface['layout'].addWidget(self.interface['table'])
        self.servicesorder = sorted([i.Main.name for i in common.manager.SERVICES.values()])
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
            widget.setStyleSheet('border: none; padding: 0px;')
            self.interface['table'].setCellWidget(rowcount, 0, widget)
            if not common.manager.SERVICES['services.'+service].Main.features['category']:
                widget.setDisabled(True)
            self.interface['line_' + service] = widget

        self.interface['table'].setVerticalHeaderLabels(self.servicesorder)
        self.interface['table'].horizontalHeader().setVisible(False)

    def edited(self, widget, service, text):
        # Add a QTimer to prevent lag
        autocompletion = self.manager.services[service].query_category(text)
        self.interface['completer'] = QtWidgets.QCompleter(list(autocompletion.keys()))
        self.interface['completer'].setCompletionMode(QtWidgets.QCompleter.UnfilteredPopupCompletion)
        self.interface['completer'].activated.connect(functools.partial(self.set_validautocomplete, service))
        widget.setCompleter(self.interface['completer'])  # If activated() then validated automatically

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
            disabled = not common.manager.SERVICES['services.' + service].Main.features['category']
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
        if category:
            row = self.servicesorder.index(service)
            widget = self.interface['line_' + service]
            text = widget.text()
            self.temporary_settings.setdefault(category, {}).setdefault(service, {})
            self.temporary_settings[category][service] = {'name': text, 'valid': ''}
            self.validate(category)

    def set_layouthorizontal(self):
        self.interface['processes'].hide()
        for i in self.servicesorder:
            self.interface['table'].insertColumn(0)
        self.interface['table'].setHorizontalHeaderLabels(self.servicesorder)
        for process, values in self.temporary_settings.items():
            rowcount = self.interface['table'].rowCount()
            self.interface['table'].insertRow(rowcount)
            row = QtWidgets.QTableWidgetItem()
            row.setText(process)
            self.interface['table'].setVerticalHeaderItem(rowcount, row)
            for i, service in enumerate(self.servicesorder):
                row = QtWidgets.QLineEdit()
                row.setText(values.get(service, {}).get('name', '') or '')
                row.setStyleSheet('border: none; padding: 0px;')
                self.interface['table'].setCellWidget(rowcount, i, row)

        rowcount = self.interface['table'].rowCount()
        for column, service in enumerate(self.servicesorder):
            s = self.manager.services.get(service)
            if s:
                completer = QtWidgets.QCompleter(['test', 'caca', 'toto'])
                completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                for row in range(rowcount):
                    widget = self.interface['table'].cellWidget(row, column+1)
                    widget.setCompleter(completer)  # If activated() then validated automatically

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

        self.panel_services['list'] = QtWidgets.QTableWidget()
        self.panel_services['list'].setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.panel_services['list'].setColumnCount(1)
        self.panel_services['list'].setWordWrap(False)
        self.panel_services['list'].verticalHeader().setVisible(False)
        self.panel_services['list'].horizontalHeader().setVisible(False)
        self.panel_services['list'].horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.panel_services['list'].currentCellChanged.connect(self.service_changed)
        self.elements = ['enabled', 'channel_id', 'client_id', 'client_secret', 'scope', 'redirect_uri', 'authorization_base_url', 'token_url']
        for i, elem in enumerate(self.elements):
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
                self.panel_services[nameline].editingFinished.connect(self.save_servicedata)
            self.panel_services[nameline].setMinimumHeight(30)
            self.panel_services['container'].addWidget(self.panel_services[nameline], i, 2)
        self.panel_services['container'].setRowStretch(self.panel_services['container'].rowCount(), 10)
        self.panel_services['list'].setFixedWidth(150)
        self.setLayout(self.panel_services['container'])
        self.panel_services['container'].addWidget(self.panel_services['list'], 0, 0, -1, 1)
        self.panel_services['list'].itemSelectionChanged.connect(self.service_changed)

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
        block_signals(self.panel_services.values(), True)
        item = self.panel_services['list'].currentItem()
        service = item.text()
        config = self.temporary_settings[service]
        for elem in self.elements:
            if elem == 'enabled':
                val = config.get(elem, False)
                self.panel_services['line_' + elem].blockSignals(True)
                self.panel_services['line_' + elem].setChecked(val)
                self.panel_services['line_' + elem].blockSignals(False)
                set_disabledrowstyle(item, val)
            else:
                self.panel_services['line_' + elem].setText(str(config.get(elem, '')))
        block_signals(self.panel_services.values(), False)

    def save_servicedata(self):
        item = self.panel_services['list'].currentItem()
        service = item.text()
        for elem in self.elements:
            if elem == 'enabled':
                result = self.panel_services['line_' + elem].isChecked()
                set_disabledrowstyle(item, result)
            else:
                result = self.panel_services['line_' + elem].text()
            self.temporary_settings[service][elem] = result

    def accept(self):
        for service in self.temporary_settings:
            self.manager.config['streamservices'][service] = self.temporary_settings[service]

    def reset(self):
        self.temporary_settings = copy.deepcopy(self.manager.config['streamservices'])
        self.create_services()
        self.panel_services['list'].setCurrentCell(0, 0)


class Preferences_Pause(QtWidgets.QWidget):
    def __init__(self, manager, name, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.config = self.manager.config['base'][name]
        self.panel_pause = {}
        self.panel_pause['container'] = QtWidgets.QGridLayout()
        self.panel_pause['label'] = QtWidgets.QLabel('When the check is runned any entry on the right side will be paused until the check is stopped.\nUsefull for automatically pausing applications that use bandwith or CPU.\n')
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
        return []

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
        if sys.platform != 'win32':
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
    updated = QtCore.Signal(dict)

    def start_check(self):
        self.startedcheck.emit()

    def stop_check(self):
        self.stoppedcheck.emit()

    def run(self):
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
                timer = QtCore.QTimer()
                timer.timeout.connect(self.main)
                timer.start(1000)
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
        try:
            super().load_credentials(path)
        except AttributeError:
            raise  # Show a notification telling the user the json file is not right

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

