import os
import sys
import logging
import functools
logger = logging.getLogger(__name__)
from PySide2 import QtCore, QtWidgets, QtGui

import common.manager

class StreamManager_UI(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setStyleSheet("QTableWidget {margin: 10px;} QPlainTexxtEdit, QxLineEdit {margin: 3px;} QHeaderView::section { background-color: #3697FE;border:1px solid #ccc;font-weight: bold} QHeaderView::section:checked { background-color: #fff;border:1px solid #ccc;} QPlainTextEdit {background:white}")
        self.setWindowTitle('Stream Manager')
        self.manager = common.manager.ManageStream()
        self.centralwidget = QtWidgets.QTabWidget(self)
        self.centralwidget.setDocumentMode(True)
        self.setCentralWidget(self.centralwidget)

        self.create_gamelayout()
        # self.create_serviceslayout()
        # self.centralwidget.addTab(self.services, 'Streams')
        self.centralwidget.addTab(self.gameslayout['main'], 'Games')
        self.centralwidget.tabBar().hide()
        self.centralwidget.setCurrentWidget(self.gameslayout['main'])
        self.load_appdata()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.menuBar().setVisible(not self.menuBar().isVisible())
        if self.menuBar().isVisible():
            self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint & ~QtCore.Qt.FramelessWindowHint)
        else:
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.show()
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
        self.gameslayout['main'] = QtWidgets.QSplitter()
        self.gameslayout['main'].addWidget(self.gameslayout['container_llayout'])
        self.gameslayout['main'].addWidget(self.gameslayout['container_rlayout'])
        self.gameslayout['main'].setStretchFactor(0, 0)
        self.gameslayout['main'].setStretchFactor(1, 1)
        self.load_generalsettings()

    def create_filedialog(self):
        self.filedialog = QtWidgets.QFileDialog()
        result = self.filedialog.exec_()
        if result:
            return self.filedialog.selectedFiles()[0]

    def add_game(self):
        path = self.create_filedialog()
        if path:
            process = os.path.basename(path)
            print(process)
            self.manager.config['appdata'][process] = {}
            self.create_row(process)
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
        else:
            for key in data.copy():
                data['forced_' + key] = self.gameslayout[key].button.state
                self.manager.config['base'].update(data)
        logger.debug(data)

    def create_row(self, process):
        row = QtWidgets.QTableWidgetItem()
        row.setText('{} ({})'.format(self.manager.config['appdata'][process].get('category', ''), process))
        row._process = process
        row.setFlags(row.flags() & ~QtCore.Qt.ItemIsEditable)
        rowcount = self.gameslayout['table'].rowCount()
        self.gameslayout['table'].insertRow(rowcount)
        self.gameslayout['table'].setItem(rowcount, 0, row)
        return row

    def load_appdata(self):
        for process in self.manager.config['appdata']:
            self.create_row(process)
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

    def create_serviceslayout(self):
        self.services = QtWidgets.QWidget()
        self.serviceslayout = QtWidgets.QGridLayout(self.services)

    def block_signals(self, block):
        for i in self.gameslayout:
            self.gameslayout[i].blockSignals(block)



class StateButtons():
    buttonClicked = QtCore.Signal(bool)

    def __init__(self, icons, parent=None):
        super().__init__(parent)
        self.button = QtWidgets.QToolButton(self)
        self.button.state = False
        self.button.icons = {True: icons[True], False: icons[False]}
        self.button.setIcon(self.button.icons[self.button.state])
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
            self.button.state = not self.button.state
        else:
            self.button.state = bool(state)
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

