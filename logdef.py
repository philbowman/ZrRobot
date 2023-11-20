import logging
import sys
from logging.handlers import TimedRotatingFileHandler
import os
FILE_FORMATTER = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
CONSOLE_FORMATTER = logging.Formatter("[%(levelname)-5.5s]  %(message)s")
LOG_FOLDER = "logs"
LOG_FILE = f"{LOG_FOLDER}/debug.log"
if not os.path.exists(LOG_FOLDER):
   os.mkdir(LOG_FOLDER)

def get_console_handler():
   console_handler = logging.StreamHandler(sys.stdout)
   console_handler.setFormatter(CONSOLE_FORMATTER)
   console_handler.setLevel(logging.INFO)
   return console_handler
def get_file_handler():
   file_handler = TimedRotatingFileHandler(LOG_FILE, when='midnight', backupCount=20)
   file_handler.setLevel(logging.DEBUG)
   file_handler.setFormatter(FILE_FORMATTER)
   return file_handler
def get_logger(logger_name):
   logger = logging.getLogger(logger_name)
   logger.setLevel(logging.DEBUG)
   logger.addHandler(get_console_handler())
   logger.addHandler(get_file_handler())
   # with this pattern, it's rarely necessary to propagate the error up to parent
   logger.propagate = False
   return logger

logger = get_logger("mr_robot")