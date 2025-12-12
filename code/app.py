from lims import app, db
import threading
import pythoncom
import logging
import sys
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
# from multiprocessing import Lock

# --- GLOBAL LOCKS ---
# WARNING: These locks only work within ONE process. 
# Worker 1 cannot see Worker 2's locks. 
# This is usually fine for COM objects since processes are isolated.
# com_lock = threading.Lock()
# process_lock = Lock()

# --- LOGGING SETUP (Global Scope) ---
# We run this immediately so Waitress picks it up.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'lims_logs')
os.makedirs(LOG_DIR, exist_ok=True)

# CRITICAL FIX: Append Process ID (pid) to filename
# This ensures Worker 1 writes to log_1234.log and Worker 2 writes to log_5678.log
# preventing Windows file locking crashes.
pid = os.getpid()
log_file = os.path.join(LOG_DIR, f'WORKER_lims_server_{pid}_{datetime.now().date()}.log')

file_handler = TimedRotatingFileHandler(
    filename=log_file,
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [PID:%(process)d] [%(levelname)s] %(message)s', '%m/%d/%Y %H:%M:%S')
file_handler.setFormatter(formatter)

# Console handler
console = logging.StreamHandler(stream=sys.__stdout__) 
console.setFormatter(formatter)

# Root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console)  # Now safe to add this back!

# Redirect stdout/stderr to logger
class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
    def write(self, message):
        if message and message.strip(): 
            self.logger.log(self.level, message.rstrip())
    def flush(self): pass

# NOW ENABLE THESE LINES (They capture 'print' statements)
sys.stdout = StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
sys.stderr = StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)

logging.captureWarnings(True)

# --- WEB APP ENTRY POINT ---
if __name__ == '__main__':
    # This block is ONLY for debugging locally with "python app.py"
    # It is ignored by Waitress.
    app.run(host='0.0.0.0', debug=True)