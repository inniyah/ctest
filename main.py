#!/usr/bin/env python3

import os
import sys

import logging
import argparse
import traceback
import faulthandler

faulthandler.enable()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(process)s/%(threadName)s:%(thread)d] [%(pathname)s:%(lineno)d] [%(asctime)s]: '%(message)s'")

import json
import signal
import threading
import time

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

MY_PATH = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(MY_PATH, 'libs'))
os.chdir(MY_PATH)

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

FULLSCREEN = False
MAXIMIZED = False

LOG_FILE_FORMAT = "[%(levelname)s] [%(pathname)s:%(lineno)d] [%(asctime)s] [%(name)s]: '%(message)s'"
LOG_CONSOLE_FORMAT = "[%(pathname)s:%(lineno)d] [%(asctime)s]: '%(message)s'"
LOG_GUI_FORMAT = "[%(levelname)s] %(message)s"

LOGS_DIR       = os.path.abspath(os.path.join(MY_PATH, 'logs'))
LOGS_MAX_SIZE  = 5000000
LOGS_MAX_COUNT = 9

DEFAULT_LOG_LEVEL = 'INFO'

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

from PyQt5.uic import loadUiType
from PyQt5 import Qt, QtGui, QtWidgets, QtCore

UiMainWindow, QMainWindow = loadUiType(os.path.join(MY_PATH, 'mainwin.ui'))

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

from spinner import WaitingSpinner
from json_viewer import JsonView

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

# https://stackoverflow.com/questions/57584560/how-to-clear-the-text-of-qtextedit-and-immediately-insert-new-text
class Stream(QtCore.QObject):
    newText = QtCore.pyqtSignal(str)
    def write(self, text):
        if self.newText is not None:
            self.newText.emit(str(text))
    def flush(self):
        pass
    def destroy(self):
        self.newText = None

class MainWindow(UiMainWindow, QMainWindow):
    def __init__(self, args):
        self.exit_now = False
        self.show_log = True
        self.threads = { }

        try:
            super(MainWindow, self).__init__()
            self.setupUi(self)
            self.setWindowTitle("Main Window")

            # Setup logging in GUI (if enabled)
            if self.show_log:
                # Redirect logging output to a custom logging stream that updates a UI element
                self.logging_stream = Stream(newText=self.onUpdateLogText)
                self.logging_handler = logging.StreamHandler(self.logging_stream)
                self.logging_handler.setLevel(logging.INFO)
                self.logging_handler.setFormatter(logging.Formatter(LOG_GUI_FORMAT))

                # Attach logging handler to the root logger
                rootLogger = logging.getLogger()
                rootLogger.addHandler(self.logging_handler)

                # Clear the log widget and configure its appearance
                self.log.clear()
                # See: https://stackoverflow.com/questions/45048555/pyqt5-textedit-delete-lines-as-they-move-past-specified-line
                self.log.setMaximumBlockCount(100)  # Limit log history to 100 entries
                self.monospace_font = QtGui.QFont("Monospace", 9)
                self.log.setFont(self.monospace_font)
                self.log.show()  # Display the log widget

                self.log_splitter.setSizes([1, 0])

            else:
                # Hide the log widget if logging is disabled
                self.log.clear()
                self.log.hide()

            # Configure a loading spinner to indicate ongoing background tasks (if enabled)
            self.spinner = WaitingSpinner(self, True, True, QtCore.Qt.ApplicationModal)

            # Set up a periodic timer, that will call self.tick every 100 ms.
            self.tick_counter = -1
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.tick)
            self.timer.start(100)

            logging.info('System started!')

        except Exception as e:
            logging.error(f"{type(e).__name__}: {e}")
            logging.error(traceback.format_exc())

        self.load_initial_data()

    def load_initial_data(self):
        def _run(self, thread_id):
            try:
                time.sleep(2)
                self.json.addTopLevelItem('something', {i: str(i) for i in range(10)})
                logging.info('Initial Data Loaded')

            except Exception as e:
                logging.error(f"{type(e).__name__}: {e} [{sys._getframe().f_code.co_name}]")
                logging.error(traceback.format_exc())
                #~ logging.error(sys.exc_info()[2])

            finally:
                self.threads.pop(thread_id, None)

        try:
            thread_id = sys._getframe().f_code.co_name # Get function name ( https://www.oreilly.com/library/view/python-cookbook/0596001673/ch14s08.html )
            logging.info(f"Creating thread: '{thread_id}'")
            thread = threading.Thread(target=_run, args=(self, thread_id))
            self.threads[thread_id] = thread
            thread.start()

        except Exception as e:
            logging.error(f"{type(e).__name__}: {e} [{sys._getframe().f_code.co_name}]")
            logging.error(traceback.format_exc())
            #~ logging.error(sys.exc_info()[2])

    def tick(self):
        self.tick_counter += 1

        dead_threads = [ id for id, thread in self.threads.items() if not thread.is_alive() ]
        for thread_id in dead_threads:
            self.threads.pop(thread_id, None)

        if not self.threads:
           if self.spinner.isSpinning:
                self.spinner.stop()
        else:
            if not self.spinner.isSpinning:
                self.spinner.start()

        if self.exit_now:
            self.close()
            return

    def onUpdateLogText(self, text):
        if self.show_log:
            self.log.moveCursor(QtGui.QTextCursor.End)
            self.log.insertPlainText(text)

    def closeEvent(self, event):
        self.exit_now = True

        if self.timer is not None:
            self.timer.stop()

        logging.debug("Bye, World!")
        #~ event.ignore()

    def kill(self):
        self.exit_now = True

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

class ColorStderr(logging.StreamHandler):
    def __init__(self, fmt=None):
        class AddColor(logging.Formatter):
            def __init__(self):
                super().__init__(fmt)
            def format(self, record: logging.LogRecord):
                msg = super().format(record)
                # Green/Cyan/Yellow/Red/Redder based on log level:
                color = '\033[1;' + ('32m', '36m', '33m', '31m', '41m')[min(4,int(4 * record.levelno / logging.FATAL))]
                return color + record.levelname + '\033[1;0m: ' + msg
        super().__init__(sys.stderr)
        self.setFormatter(AddColor())

class GracefulKiller:
    def __init__(self, objects):
        self.objects = objects
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
    def exit_gracefully(self, *args):
        logging.warning(" /!\\ Program Killed! /!\\")
        for obj in self.objects:
            try:
                obj.kill()
            except Exception as e:
                logging.error(f"{type(e).__name__}: {e}")
                logging.error(traceback.format_exc())
        sys.exit(-1)

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def main_qt():
    import argparse
    parser = argparse.ArgumentParser()
    default_log_level=logging.getLevelName(DEFAULT_LOG_LEVEL)
    parser.add_argument('-q', '--quiet', help='set logging to ERROR',
                        action='store_const', dest='loglevel',
                        const=logging.ERROR, default=default_log_level)
    parser.add_argument('-w', '--warning', help='set logging to WARNING',
                        action='store_const', dest='loglevel',
                        const=logging.WARNING, default=default_log_level)
    parser.add_argument('-v', '--verbose', help='set logging to INFO',
                        action='store_const', dest='loglevel',
                        const=logging.INFO, default=default_log_level)
    parser.add_argument('-d', '--debug', help='set logging to DEBUG',
                        action='store_const', dest='loglevel',
                        const=logging.DEBUG, default=default_log_level)
    parser.add_argument('--log', action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    log_console_handler = ColorStderr(LOG_CONSOLE_FORMAT)
    log_console_handler.setLevel(args.loglevel)
    logger.addHandler(log_console_handler)

    if args.log:
        now = datetime.now()
        logs_dir = LOGS_DIR
        os.makedirs(logs_dir, exist_ok=True)
        log_filename = "main.log"
        log_file_handler = RotatingFileHandler(os.path.join(logs_dir, log_filename), maxBytes=LOGS_MAX_SIZE, backupCount=LOGS_MAX_COUNT)
        log_formatter = logging.Formatter(LOG_FILE_FORMAT)
        log_file_handler.setFormatter(log_formatter)
        log_file_handler.setLevel(logging.DEBUG)
        logger.addHandler(log_file_handler)
        logging.info(f"Storing log into '{logs_dir}/{log_filename}'")

    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow(args)
    if FULLSCREEN:
        main_window.showFullScreen()
    elif MAXIMIZED:
        main_window.showMaximized()
    else:
        main_window.showNormal()
    killer = GracefulKiller([main_window])
    res = app.exec_()

    return res

if __name__ == "__main__":
    sys.exit(main_qt())
