from lims import app
import time
import os
import sys
import threading

# Import your background workers
from lims.background.background_auto_import import background_import_watcher
from lims.background.autopsy_reports_worker import autopsy_worker
from lims.background.business_record_worker import start_r1_daily_scheduler
from lims.background.lit_packet_scheduler import lit_packet_loop

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