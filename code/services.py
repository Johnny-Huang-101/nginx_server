from lims import app
import time
import os
import sys
import threading
# import logging
# from datetime import datetime
# from logging.handlers import TimedRotatingFileHandler

# Import your background workers
from lims.background.background_auto_import import background_import_watcher
from lims.background.autopsy_reports_worker import autopsy_worker
from lims.background.business_record_worker import start_r1_daily_scheduler
from lims.background.lit_packet_scheduler import lit_packet_loop

# # --- LOGGING SETUP ---
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# LOG_DIR = os.path.join(BASE_DIR, 'lims_logs')
# os.makedirs(LOG_DIR, exist_ok=True)

# # Append Process ID (pid) to filename
# pid = os.getpid()
# log_file = os.path.join(LOG_DIR, f'SERVICE_lims_services_{pid}_{datetime.now().date()}.log')

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

# sys.stdout = StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
# # sys.stderr = StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)
# logging.captureWarnings(True)

# # --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    print("--- STARTING BACKGROUND SERVICES (Scheduler/Watcher) ---")
    
    # We can use the app context if your tasks need DB access
    with app.app_context():
        # 1. Start Scheduler
        print("Initializing Daily Scheduler...")
        try:
            start_r1_daily_scheduler(app)
        except Exception as e:
            print(f"Error starting scheduler: {e}")

        # 2. Start Watcher
        print("Initializing Import Watcher...")
        try:
            background_import_watcher(app)
        except Exception as e:
            print(f"Error starting watcher: {e}")
        
        print("Initializing litpacket generator...")
        scheduler_thread = threading.Thread(
            target=lit_packet_loop, 
            name="LitPacketScheduler", 
            daemon=True
        )
        scheduler_thread.start()

        # 3. WILL WRITE TO PROD
        # autopsy_worker()

    print("Background services are running. Press Ctrl+C to stop.")
    
    # Keep this script running forever so the background threads stay alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping services...")