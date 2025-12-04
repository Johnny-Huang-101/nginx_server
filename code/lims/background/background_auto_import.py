from threading import Lock, Thread
import time
from datetime import datetime, timedelta
import os
from flask import current_app
from lims.cases.functions import auto_import_fa_cases, get_form_choices
from lims.cases.forms import Add
from pathlib import Path
import traceback

d_root = Path(current_app.config["D_FILE_SYSTEM"])
control_dir = d_root / "Exports" / "JSON"
log_path = d_root / "Exports" / "export-log.csv"
EXPORT_FREQUENCIES = [
    "1d_15m", "7d_1h", "30d_13h", "365d_24h_a", "365d_24h_b"
]

import_lock = Lock()

def background_import_watcher(app, interval=60):
    # if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    #     # This is the reloader parent process; don't start threads here
    #     return

    print('background_import_watcher called')

    def loop():
        while True:
            try:
                with (app.app_context()):
                    log_path = os.path.join(
                        app.config['D_FILE_SYSTEM'], "Exports", "export-log.csv"
                        )
                    fa_col_map = os.path.join(app.config['FILE_SYSTEM'], "fa_column_mapping.csv")
                    impl_date = app.config['IMPLEMENTATION_DATE']
                    add_form = Add(meta={'csrf':False})
                    add_form = get_form_choices(add_form, agency_id=1)

                    if os.path.exists(log_path):
                        with import_lock:
                            print(f"Launching import thread")
                            try:
                                print("AUTO-IMPORT TRIGGERED")
                                auto_import_fa_cases(log_path, fa_col_map, impl_date, add_form)
                            except Exception as e:
                                raise e
                    else:
                        print("[watcher] export-log.csv not found")
                print(f"Sleeping {interval} seconds...")
                time.sleep(interval)
            except Exception as e:
                print(f"Background import watcher error: {e}")
                traceback.print_exc()
                time.sleep(interval)
                raise e

    thread = Thread(target=loop, daemon=True)
    thread.start()

