import time
import os
import sys
import logging
import traceback
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from flask import current_app

# Import the NEW queue submitter
from lims.queue import submit
from lims.models import LitigationPacketRequest, db, LitigationPackets
# We import the actual generator function here so we can call it in process_job
from lims.pdf_redacting.functions import lit_packet_generation_templates

CYAN = "\033[96m"
RESET = "\033[0m"

# ------------------------------------------------------------------
# PART 1: THE WORKER LOGIC
# This function is called by run_worker.py when it picks up a ticket
# ------------------------------------------------------------------
def process_job(job_data):
    """
    Generates the Lit Packet PDF.
    This runs inside the 'run_worker.py' process.
    """
    import pythoncom
    
    # 1. Setup Logging (Specific to this job type)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_DIR = os.path.abspath(os.path.join(BASE_DIR, '../../lims_logs'))
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'lit_packet_worker.log')

    # (Simple logger setup for brevity, your existing setup is fine too)
    logging.basicConfig(filename=log_file, level=logging.INFO, 
                        format='[%(asctime)s] %(message)s')
    
    print(f"{CYAN}[WORKER] Starting Lit Packet {job_data['item_id']}...{RESET}")

    # 2. Run the Logic
    # Note: run_worker.py already initialized COM and App Context, 
    # but nested context/init is safe.
    try:
        # Call your existing PDF generation function
        path = lit_packet_generation_templates(
            job_data["item_id"],
            job_data["template_id"],
            job_data["redact"],
            job_data["packet_name"],
            job_data["remove_pages"],
            True # Flatten/Finalize
        )

        # 3. Update DB (Success)
        # We need to re-fetch the objects because we are in a new transaction
        packet = LitigationPackets.query.filter_by(id=job_data["packet_id"]).first()
        if packet:
            packet.packet_status = "Ready for PP"
        
        job_record = LitigationPacketRequest.query.get(job_data['id'])
        if job_record:
            job_record.status = 'Success'
            job_record.zip = path
            
        db.session.commit()
        print(f"{CYAN}[WORKER] Packet {job_data['item_id']} SUCCESS{RESET}")
        return path

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"[WORKER] ERROR: {error_msg}")
        logging.error(f"Job {job_data['id']} Failed: {error_msg}")
        
        # Update DB (Fail)
        db.session.rollback() # clear previous failed transaction
        job_record = LitigationPacketRequest.query.get(job_data['id'])
        if job_record:
            job_record.status = 'Fail'
            db.session.commit()
        raise e # Re-raise so Redis marks job as failed

# ------------------------------------------------------------------
# PART 2: THE SCHEDULER LOGIC
# This runs in your 'services.py' or a separate background thread
# ------------------------------------------------------------------
def lit_packet_loop():
    """
    Checks DB for scheduled packets and PUSHES them to Redis.
    Does NOT generate them itself.
    """
    from app import app
    
    print(f"{CYAN}[Scheduler] Lit Packet Scheduler Active{RESET}")
    
    with app.app_context():
        while True:
            try:
                now = datetime.now()
                # Find jobs that need to run
                rows = LitigationPacketRequest.query.filter(
                    LitigationPacketRequest.status == 'Scheduled',
                    LitigationPacketRequest.scheduled_exec <= now
                ).all()

                for row in rows:
                    print(f"{CYAN}[Scheduler] Enqueuing Packet {row.id}{RESET}")
                    
                    # 1. Mark as Processing so we don't pick it up again
                    row.status = 'Processing'
                    db.session.commit() # Commit status change immediately

                    # 2. Prepare Data (Must be JSON serializable)
                    job_payload = {
                        "id": row.id,
                        "item_id": row.item_id,
                        "template_id": row.template_id,
                        "redact": row.redact,
                        "packet_name": row.packet_name,
                        "remove_pages": row.remove_pages,
                        "packet_id": row.packet_id
                    }

                    # 3. Submit to Redis (Priority 10 = Low/Default) 
                    #TODO IDK if we need to change the priority of lit packets
                    # We pass the STRING path to the function above
                    submit(
                        "lims.background.lit_packet_scheduler:process_job", 
                        priority=9, 
                        job_data=job_payload # passed as kwarg to process_job
                    )

                if len(rows) > 0:
                    print(f"{CYAN}[Scheduler] Pushed {len(rows)} jobs to Redis.{RESET}")

            except Exception as e:
                print(f"[Scheduler] Error: {e}")
                db.session.rollback()

            # Sleep 5 minutes
            time.sleep(300)