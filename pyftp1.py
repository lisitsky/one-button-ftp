#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, time, os, hashlib, atexit
import ftplib
import traceback
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QVBoxLayout, \
                            QScrollArea, QLineEdit, QCheckBox, QMessageBox, QMenu
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon, QPalette, QLinearGradient, QColor, QBrush, QCursor
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot, QEvent, QSettings

album_uploaders = {}

class MainWindow(QWidget):
    _album_buttons = {}

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        def _start():
            try:
                self.start_work(name.text(), passwd.text(), remember.checkState())
            except ftplib.error_perm as e:
                QMessageBox.critical(self, 'Error', 'Неверный пароль!', QMessageBox.Ok)
            except Exception as e:
                s = traceback.format_exc()
                QMessageBox.critical(self, 'Ошибка', 'Пожалуйста, отправьте данную информацию разработчикам:\n\n %s' % s, 
                                        QMessageBox.Ok)

        self.resize(600, 400)
        self.setWindowTitle('Загрузка по FTP в Фотобанк')
        self.setWindowIcon(QIcon('resources/favicon.ico'))
        # set layouts
        name = QLineEdit(settings.login)
        name.returnPressed.connect(_start)
        name.setPlaceholderText('Логин в фотобанк')
        passwd = QLineEdit(settings.passwd)
        passwd.returnPressed.connect(_start)
        passwd.setPlaceholderText('Пароль для фотобанка')
        passwd.setEchoMode(QLineEdit.Password)
        remember = QCheckBox('Запомнить?', checked=settings.remember)
        login = QPushButton('Вход')
        auth_panel = QHBoxLayout()
        auth_panel.addWidget(name)
        auth_panel.addWidget(passwd)
        auth_panel.addWidget(remember)
        auth_panel.addWidget(login)
        login.clicked.connect(_start)
        # login.clicked.connect(lambda: self.start_work(name.text(), passwd.text(), remember.checkState()))

        btn_area = QScrollArea()
        btn_area_widget = QWidget()
        btn_area.setWidget(btn_area_widget)
        self.__btn_area_layout = btn_area_layout = QVBoxLayout(btn_area_widget)

        btn_area.setWidgetResizable(True)
        central_box = QHBoxLayout()
        central_box.addWidget(btn_area)

        vbox = QVBoxLayout()
        # vbox.addStretch()
        vbox.addLayout(auth_panel)
        vbox.addLayout(central_box)

        self.setLayout(vbox)

        self.show()


    def set_ftp_credentials(self, login, passwd, remember):
        # set ftp credentials
        #print (login, passwd, remember)
        self.__ftp_login = login
        self.__ftp_passwd = passwd
        self.__ftp_remember = remember
    

    def add_album_buttons(self, albums):
        # adds album buttons
        layout = self.__btn_area_layout 
        for name in albums:
            if name not in self._album_buttons:
                button = AlbumButton(name, self.__ftp_login, self.__ftp_passwd)
                layout.addWidget(button)
                self._album_buttons[name] = button

    def start_work(self, login, passwd, remember):
        # start work:
        #  - remember credentials
        #  - establish connection
        #  - get albums
        self.set_ftp_credentials(login, passwd, remember)
        if remember:
            save_settings(login=login, passwd=passwd, remember=remember)
        self.__ftp = start_ftp(login, passwd)
        albums = sort_albums(get_albums(self.__ftp))
        self.add_album_buttons(albums)

    def enqueueFiles_XXX(self, album_name, fileslist):
        # enqueue files to specific folder uploader
        worker = album_uploaders.get(album_name)
        if worker is None:
            # start new uploader
            worker = AlbumUploader()
            worker.setName(album_name)
            thread = QThread(self)
            worker.moveToThread(thread)
            thread.started.connect(worker.process)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            # worker.message.connect(self.text)
            thread.start()
            album_uploaders[album_name] = worker

    def closeEvent(self, event):
        # check and exit
        workers = len(album_uploaders)
        if workers > 0:
            reply = QMessageBox.question(self, 'Закрыть программу?', 
                                        'Вы уверены, что хотите выйти? \nСейчас загружается %s альбом(а,ов)' % workers,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


class AlbumUploader(QObject):
    name = ''
    finished = pyqtSignal()
    message = pyqtSignal(int)
    progress_message = pyqtSignal(str, float, bool)
    fileslist = None
    ftp = None  # connection to server
    i = 0
    active = False
    progress = 0.0

    def setName(self, name, ftp_login, ftp_passwd):
        self.name = name
        self.ftp_login = ftp_login
        self.ftp_passwd = ftp_passwd

    def __str__(self):
        return 'AlbumUploader @%s ftp=%s name="%s" i=%s len=%s fileslist=%s' % \
            (id(self), self.ftp, self.name, self.i, len(self.fileslist), self.fileslist)

    def prepareFtp(self):
        self.ftp = start_ftp(self.ftp_login, self.ftp_passwd)
        #print('FTP conn: %s', self.ftp)
        cwd = '/' + self.name
        self.ftp.cwd(cwd)
        self.ftp.set_pasv(True)
        self.ftp.sendcmd('TYPE I')
        self.ftp.set_debuglevel(2)

    def uploadFile(self, f):
        # upload file to server
        #print('Uploading file "%s"' % f)
        fil = open(f, 'rb')
        size_local = os.path.getsize(f)
        basename = os.path.basename(f)
        self.ftp.storbinary('STOR '+basename, fil)
        size_remote = self.ftp.size(basename)
        md5 = hashlib.md5(fil.read()).hexdigest()
        #print('Uploaded file %s md5=%s size_local=%s size_remote=%s'  % (f, md5, size_local, size_remote))
        fil.close()
        if size_remote != size_local:
            raise Exception("Sizes don't match!")

    def getProgress(self):
        # return current progress percent
        if self.startlen == 0:
            return 0.0
        return float(self.startlen-len(self.fileslist))/self.startlen

    def updateButton(self):
        # update album button style:
        #   progressbar
        #   show activity
        # percent = float(self.startlen-len(self.fileslist))/self.startlen
        self.progress_message.emit(self.name, self.getProgress(), self.active)

    @pyqtSlot()
    def process(self):
        #print('START %s', self)
        #print('fileslist: %s' % self.fileslist)
        self.prepareFtp()
        self.i = 0
        self.startlen = len(self.fileslist)
        self.active = True
        self.updateButton() 
        while True:
            # get first file name
            #print("New load cycle by %s" % self)
            try:
                f = self.fileslist.pop(0)
                self.uploadFile(f)
                #print('sleep', self.i, len(self.fileslist), f)
                self.message.emit(self.i)
                self.updateButton() 
                # time.sleep(2.0)
                # 1/(1-1)
            except IndexError as err:
                #print('upload fileslist is empty. \nGot error: %s\n' % err)
                break
            except Exception as err:
                #print('Fatal!!!! \nWhile uploading file "%s" got error: \n%s' % (f, err))
                traceback.print_exc(file=sys.stdout)
                self.fileslist.append(f)
                time.sleep(2.0)
                self.prepareFtp()
        #print('FINISHED')
        #print('These file(s) were not uploaded: %s' % self.fileslist)
        self.active=False
        self.updateButton()
        self.finished.emit()
        self.fileslist = []
        self.startlen = len(self.fileslist)

    def enqueueFiles(self, fileslist):
        if self.fileslist is None:
            self.fileslist = []
            self.startlen = 0
        for f in fileslist:
            if os.path.isdir(f):
                subdirfiles = [os.path.join(f, i) for i in os.listdir(f)]
                self.enqueueFiles(subdirfiles)
            else:
                self.fileslist.append(f)
                self.startlen += 1
        # self.fileslist.extend(fileslist)
        # self.startlen += len(fileslist)        


class AlbumButton(QPushButton):
    """docstring for AlbumButton"""
    drop_ready = pyqtSignal(bool)

    def __init__(self, name, ftp_login, ftp_passwd):
        # super(AlbumButton, self).__init__()
        QPushButton.__init__(self, name)
        self.name = name
        self.ftp_login = ftp_login
        self.ftp_passwd = ftp_passwd
        # self.active = False
        self.setStyleSheet(self.formatStyle())
        self.setAcceptDrops(True)
        self.drop_ready.connect(self.setDropReady)
        # self.setToolTip('Левая кнопка - загрузить файлы\nПравая - дополнительные действия')

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('Добавить файлы к альбому', self.selectFiles)
        menu.show()
        menu.exec_(QCursor.pos())

    def mousePressEvent(self, event):
        if event.type() in (QEvent.MouseButtonPress,) and event.button() == Qt.LeftButton:
            self.selectFiles()
        else:
            super().mousePressEvent(event)

    def setDropReady(self, ready):
        # print (self.name, ready)
        self.setProperty('dropReady', ready)
        self.style().unpolish(self)
        self.style().polish(self)
        # self.update()
        self.repaint()

    def dragLeaveEvent(self, event):
        self.drop_ready.emit(False)
        super().dragLeaveEvent(event)
        event.accept()

    def dragEnterEvent(self, event):
        self.drop_ready.emit(True)
        super().dragEnterEvent(event)
        event.accept()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        print (urls)
        self.drop_ready.emit(False)
        self.enqueueFilesToUpload([u.toLocalFile() for u in urls])
        event.accept()

    def selectFiles(self):
        # show dialog, get list of files/dir, start uploader
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.AnyFile)
        qfileslist = dialog.getOpenFileNames(self, u'Загрузка в альбом "%s"' % self.name)[0]
        fileslist = [str(x) for x in qfileslist]
        if fileslist:
            self.enqueueFilesToUpload(fileslist)

    def enqueueFilesToUpload(self, fileslist):
        # add fileslist (str[]) to 
        # enqueue files to specific folder uploader
        album_name = self.name
        uploader = album_uploaders.get(album_name)
        if uploader is None:
            # start new uploader
            uploader = AlbumUploader()
            uploader.setName(album_name, self.ftp_login, self.ftp_passwd)
            thread = QThread(self)
            uploader.moveToThread(thread)
            thread.started.connect(uploader.process)
            uploader.finished.connect(thread.quit)
            # uploader.finished.connect(lambda: print('==FINISHED'))
            uploader.finished.connect(uploader.deleteLater)
            thread.finished.connect(thread.deleteLater)
            uploader.finished.connect(lambda: self.cleanAlbumUploaders(album_name))
            uploader.progress_message.connect(self.updateProgressBar)
            # uploader.message.connect(self.text)
            thread.start()
            album_uploaders[album_name] = uploader
        uploader.enqueueFiles(fileslist)  ### ???
        #print('AlbumUploaders after enqueue: ', album_uploaders)

    def cleanAlbumUploaders(self, album_name):
        del album_uploaders[album_name]
        #print('AlbumUploaders after clean: ', album_uploaders)

    def formatStyle(self, percent=0.0, active=False):
        # format style depending on progress level
        low = percent-0.001
        if low < 0.0 : low = 0
        high = percent+0.001
        if high >= 1.0 : high = 0.9999
        color = "#d8d8d8"
        if active:
            color = "#ffffd8"
        #     self.setText(self.name + '  (Загружено ' + ('%0.f' % (percent*100)) + '%)' ) # + ' %02.f' % 100*percent)
        style = """QPushButton {font-size: 16pt; /* background-color: #d8d8d8; */ padding: 0.5em; margin: 0.3em;
                        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, 
                                        stop: 0 green, stop: %(low)s green, stop: %(high)s %(color)s, stop: 1.0 %(color)s)} 
                   QPushButton[dropReady="true"]:hover { background-color: #d8f0d8; font-weight: bold; }
                   QPushButton:hover {background-color: #d8f0d8; /* border: solid 1px green */}
                   """ % dict(low=low, high=high, color=color)
        return style

    def updateProgressBar(self, name, percent, active=False):
        #print ('Updating updateProgressBar to', percent)
        style = self.formatStyle(percent, active)
        self.setStyleSheet(style)
        if active:
            # color = "#ffffd8"
            self.setText(self.name + '  (Загружено ' + ('%0.f' % (percent*100)) + '%)' ) # + ' %02.f' % 100*percent)
        # print (style)
              

def start_ftp(login, passwd):
    # starts ftp connection 
    ftp = ftplib.FTP(settings.host, login, passwd, None, 180)
    ftp.encoding = 'utf-8'
    ftp.set_debuglevel(level=0)
    ftp.set_pasv(True)
    return ftp

def get_qsettings():
    '''returns QSettings with set Company and Product names'''
    return QSettings(settings.company, settings.product)

def save_settings(login, passwd, remember):
    qset = get_qsettings()
    qset.setValue('login', login)
    qset.setValue('passwd', passwd)
    qset.setValue('remember', remember)

def restore_settings(settings):
    qset = get_qsettings()
    settings.login = qset.value('login', type=str)
    settings.passwd = qset.value('passwd', type=str)
    settings.remember = qset.value('remember', type=bool)

def get_albums(ftp):
    #retrives albums for specified connection
    def get_albums_cb(rows):
        # callback for function get_albums - receives rows from LIST command
        # print(rows, type(rows), repr(rows))
        for row in rows.split("\n"):
            name = str.split(row, maxsplit=8)[-1]
            albums.append(name)
    albums = []
    ftp.retrlines('LIST', get_albums_cb)
    return albums

def sort_albums(albums):
    # sorts albums by their ids
    def sorter(name):
        try:
            return int(name.split("-")[0])
        except:
            return -1
    return sorted(albums, key=sorter, reverse=True)



if __name__ == '__main__':
    try:
        import settings
    except Exception:
        import types
        settings = types.ModuleType('settings', '''Default empty login and password''')
        settings.login = ''
        settings.passwd = ''
        settings.host = ''
        remember = False
        settings.command = 'MyCompany'
        settings.product = 'MyFtpProduct'
    restore_settings(settings)
    app = QApplication(sys.argv)
    wnd = MainWindow()
    sys.exit(app.exec())