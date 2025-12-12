import redis
import pythoncom
import sys
import os
# import logging
# from datetime import datetime
# from logging.handlers import TimedRotatingFileHandler

# Import SimpleWorker to force Single-Process execution (Crucial for COM/Word)
from rq import Queue, Connection
from rq_win import WindowsWorker
from app import app  # Import your Flask app for DB context

# # --- LOGGING SETUP ---
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# LOG_DIR = os.path.join(BASE_DIR, 'lims_logs')
# os.makedirs(LOG_DIR, exist_ok=True)

# # Append Process ID (pid) to filename
# pid = os.getpid()
# log_file = os.path.join(LOG_DIR, f'PDF_lims_worker_{pid}_{datetime.now().date()}.log')

# file_handler = TimedRotatingFileHandler(
#     filename=log_file,
#     when='midnight',
#     interval=1,
#     backupCount=7,
#     encoding='utf-8'
# )
# file_handler.setLevel(logging.INFO)

# formatter = logging.Formatter('[%(asctime)s] [PID:%(process)d] [%(levelname)s] %(message)s', '%m/%d/%Y %H:%M:%S')
# file_handler.setFormatter(formatter)

# # Console handler
# console = logging.StreamHandler()
# console.setFormatter(formatter)

# # Root logger
# logger = logging.getLogger()
# logger.setLevel(logging.INFO)
# logger.addHandler(file_handler)
# logger.addHandler(console)

# # Redirect stdout/stderr to logger
# class StreamToLogger:
#     def __init__(self, logger, level):
#         self.logger = logger
#         self.level = level
#     def write(self, message):
#         if message and message.strip(): # Skip empty lines
#             self.logger.log(self.level, message.rstrip())
#     def flush(self): pass

# # sys.stdout = StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
# # sys.stderr = StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)
# logging.captureWarnings(True)


# Priority Order: Worker looks at 'high' first. If empty, looks at 'low'.
listen = ['high', 'low']

def start_worker():
    # Hardcoded fallback or env var, ensuring we can connect
    redis_url = 'redis://localhost:6379'
    conn = redis.from_url(redis_url)

    # 1. Initialize Windows COM (Word/Excel/Dymo)
    # Since we use SimpleWorker, this stays valid for the life of the script.
    # No other threads will corrupt this state.
    pythoncom.CoInitialize()

    print(f"==================================================")
    print(f"[*] WORKER STARTED (PID: {os.getpid()})")
    print(f"[*] Listening on queues: {listen}")
    print(f"[*] COM Initialized. Ready for Word/PDF jobs.")
    print(f"==================================================")

    with Connection(conn):
        # 2. Load Flask App Context (so we can use db.session inside jobs)
        with app.app_context():
            
            # 3. Create the Worker
            # SimpleWorker means: No forking. No multiprocessing. 
            # One job finishes completely before the next begins.
            worker = WindowsWorker(map(Queue, listen))
            
            # 4. Run Loop
            worker.work()

if __name__ == '__main__':
    try:
        start_worker()
    finally:
        # Clean up COM handles on exit
        pythoncom.CoUninitialize()