import redis
import pythoncom
import sys
import os

# Import SimpleWorker to force Single-Process execution (Crucial for COM/Word)
from rq import Queue, Connection
from rq_win import WindowsWorker
from app import app  # Import your Flask app for DB context

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