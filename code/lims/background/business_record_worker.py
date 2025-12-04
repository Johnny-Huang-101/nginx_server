# lims/background/r1_daily_scheduler.py
import os, time, traceback
from threading import Thread
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

from lims.business_record.business_record_builder import build_reports_maintenance

TZ_NAME = "America/Los_Angeles"

def _seconds_until_next_3am():
    if ZoneInfo:
        tz = ZoneInfo(TZ_NAME)
        now = datetime.now(tz)
    else:
        now = datetime.now()  # assume server clock PT if zoneinfo missing
    # set to 5:25AM
    target = now.replace(hour=5, minute=25, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return max(5, int((target - now).total_seconds()))

def start_r1_daily_scheduler(app):
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return

    def loop():
        with app.app_context():
            while True:
                try:
                    sleep_s = _seconds_until_next_3am()
                    print(f"[R1 Scheduler] Sleeping {sleep_s}s until next 5:25 AM")
                    time.sleep(sleep_s)

                    counts = build_reports_maintenance()
                    print(f"[R1 Scheduler] R1 created: {counts['r1_created']}; "
                          f"R2 created/updated: {counts['r2_created_or_updated']}")

                    time.sleep(90)
                except Exception:
                    traceback.print_exc()
                    time.sleep(60)

    Thread(target=loop, daemon=True).start()
