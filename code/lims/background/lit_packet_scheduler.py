import time
from datetime import datetime
from multiprocessing import Process
from multiprocessing.pool import Pool
from flask import current_app
from lims.models import LitigationPacketRequest, db, LitigationPackets
from lims.pdf_redacting.functions import lit_packet_generation_templates
# from app import process_lock
import traceback
from threading import Thread
import sys



CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def process_job(job):
    from app import app  # Import inside the subprocess
    import pythoncom
    import logging
    from logging.handlers import TimedRotatingFileHandler
    import os
    pythoncom.CoInitialize()

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_DIR = os.path.abspath(os.path.join(BASE_DIR, '../../lims_logs'))
    os.makedirs(LOG_DIR, exist_ok=True)

    # 🔑 give litpacket its own log file
    log_file = os.path.join(LOG_DIR, 'lit_packet_worker.log')

    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s', 
        '%m/%d/%Y %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("litpacket")  # use a named logger
    logger.setLevel(logging.INFO)
    logger.handlers = []  # clear any inherited handlers
    logger.addHandler(file_handler)


    # Optional: redirect stdout/stderr (just like in app.py)
    class StreamToLogger:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
        def write(self, message):
            if message:
                for line in message.rstrip().splitlines():
                    self.logger.log(self.level, line.rstrip())
        def flush(self): pass
    
    sys.stdout = StreamToLogger(logging.getLogger("litpacket.STDOUT"), logging.INFO)
    sys.stderr = StreamToLogger(logging.getLogger("litpacket.STDERR"), logging.ERROR)

    with app.app_context():
        try:
            from lims.models import LitigationPacketRequest, db, LitigationPackets
            from lims.pdf_redacting.functions import lit_packet_generation_templates
            from app import process_lock

            def lit_packet_generation_templates_safe(*args, **kwargs):
                with process_lock:
                    return lit_packet_generation_templates(*args, **kwargs)

            path = lit_packet_generation_templates_safe(
                job["item_id"],
                job["template_id"],
                job["redact"],
                job["packet_name"],
                job["remove_pages"],
                True
            )

            packet = LitigationPackets.query.filter_by(id=job["packet_id"]).first()
            if packet:
                packet.packet_status = "Ready for PP"
                db.session.commit()

            job_record = LitigationPacketRequest.query.get(job['id'])
            if job_record:
                job_record.status = 'Success'
                job_record.zip = path
                db.session.commit()

            print(f"{CYAN}[PROCESS] Packet {job['item_id']} generated successfully{RESET}")
        
        except Exception as e:
            error_msg = traceback.format_exc()
            print(f"[PROCESS] Error in job {job['id']}: {error_msg}")
            job_record = LitigationPacketRequest.query.get(job['id'])
            if job_record:
                job_record.status = 'Fail'
                db.session.commit()
        finally:
            db.session.remove()
            pythoncom.CoUninitialize()


def lit_packet_loop():
    from app import app
    with app.app_context():
        while True:
            print(f"{CYAN}[Worker] Checking for scheduled litigation packets...{RESET}")
            now = datetime.now()
            rows = LitigationPacketRequest.query.filter(
                LitigationPacketRequest.status == 'Scheduled',
                LitigationPacketRequest.scheduled_exec <= now
            ).all()

            jobs = []
            for row in rows:
                row.status = 'Processing'
                jobs.append({
                    "id": row.id,
                    "item_id": row.item_id,
                    "template_id": row.template_id,
                    "redact": row.redact,
                    "packet_name": row.packet_name,
                    "remove_pages": row.remove_pages,
                    "packet_id": row.packet_id
                })
            db.session.commit()

            print(f"\033[96m Scheduled {len(jobs)} jobs fetched and marked as processed!\033[0m")
            
            if jobs:
                with Pool(processes=1) as pool:
                    pool.map(process_job, jobs)

            # Sleep in chunks to allow responsiveness to Ctrl+C
            print(f"{CYAN}[Worker] Sleeping for 5 minutes...{RESET}")
            time.sleep(300)



def background_worker():
    thread = Thread(target=lit_packet_loop, daemon=False)
    thread.start()

# # to run, open a new terminal and go to the code folder then python -m lims.background.lit_packet_scheduler
# if __name__ == "__main__":
#     background_worker()
