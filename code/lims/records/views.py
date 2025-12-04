
from lims.models import *
from lims.records.forms import Add, Edit, Approve, Update, AddMulti
from lims.records.functions import *
from lims.forms import Import, Attach
from lims.view_templates.views import *
from datetime import datetime, date, time

from sqlalchemy import and_

from flask import Response
import io, csv

# Set item global variables
item_type = 'Record'
item_name = 'Records'
table = Records
table_name = 'records'
name = 'record_name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'
redirect_to = 'view'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'ignore_fields': ignore_fields,
    'disable_fields': disable_fields
}

path = os.path.join(app.config['FILE_SYSTEM'], table_name)

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    case_id = request.args.get('item_id', type=int)
    exit_route = None
    if case_id:
        case = Cases.query.get(case_id)
        if case:
            kwargs['case_number'] = case.case_number
            exit_route = url_for('cases.view', item_id=case_id, view_only=True)    

    form = get_form_choices(Add(), case_id=case_id)
    
    if form.is_submitted() and form.validate():
        kwargs.update(process_form(form))
        return add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
        # return redirect(url_for('cases.view',
        #                        item_id=case_id))
    elif request.method == 'GET':
        form.case_id.data = case_id

    return add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)



@blueprint.route(f'/{table_name}/add-multi', methods=['GET', 'POST'])
@login_required
def add_multi():
    kwargs = default_kwargs.copy()

    form = get_form_choices(AddMulti())

    if form.is_submitted() and form.validate():
        success, failures = [], []
        seen_keys = set()   # (case_id, record_name) seen in this upload
        parsed_list = getattr(form, "_parsed_files", [])
        for meta in parsed_list:
            try:
                key = (meta["case_id"], meta["stem"])

                # duplicate within the same upload batch
                if key in seen_keys:
                    failures.append({"filename": meta["filename"], "error": "Duplicate in this upload (same record_name)."})
                    continue
                seen_keys.add(key)

                # duplicate already in DB
                if Records.query.filter_by(case_id=meta["case_id"], record_name=meta["stem"]).first():
                    failures.append({"filename": meta["filename"], "error": "Duplicate in database (record_name already exists for this case)."})
                    continue

                # set per-file fields only after passing duplicate checks
                form.case_id.data = meta["case_id"]
                form.record_type.data = str(meta["record_type"] or "")
                form.record_name.data = meta["stem"]
                form.record_number.data = str(meta["record_number"])
                form.file.data = meta["fs"]

                kwargs = process_form(form)  # writes file to disk
                add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                success.append(meta["filename"])

            except IntegrityError as ie:  # belt-and-suspenders if DB constraint fires
                db.session.rollback()
                failures.append({"filename": meta["filename"], "error": "DB unique constraint: record_name already exists for this case."})
            except Exception as e:
                db.session.rollback()
                failures.append({"filename": meta["filename"], "error": str(e)})

        if failures:
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(["filename", "error"])
            for row in failures:
                w.writerow([row["filename"], row["error"]])
            return Response(
                out.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=upload_errors.csv"}
            )
        return redirect(url_for('records.view_list'))

    _add_multi = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add_multi


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()

    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = Approve()
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = Update()
    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _update


@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):
    _lock = lock_item(item_id, table, name)

    return _lock


@blueprint.route(f'/{table_name}/<int:item_id>/unlock', methods=['GET', 'POST'])
@login_required
def unlock(item_id):
    _unlock = unlock_item(item_id, table, name)

    return _unlock


@blueprint.route(f'/{table_name}/revert_changes/')
@login_required
def revert_changes():
    item_id = request.args.get('item_id', 0, type=int)
    field = request.args.get('field_name', type=str)
    field_value = request.args.get('field_value', type=str)
    field_type = request.args.get('field_type', type=str)
    multiple = request.args.get('multiple', type=str)

    _revert_changes = revert_item_changes(item_id, field, field_value, item_name, field_type, multiple)

    return _revert_changes


@blueprint.route(f'/{table_name}/<int:item_id>/remove', methods=['GET', 'POST'])
@login_required
def remove(item_id):
    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove


@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    _approve_remove = approve_remove_item(item_id, table, table_name, item_name, name)

    return _approve_remove


@blueprint.route(f'/{table_name}/<int:item_id>/reject_remove', methods=['GET', 'POST'])
@login_required
def reject_remove(item_id):
    _reject_remove = reject_remove_item(item_id, table, table_name, item_name, name)

    return _reject_remove


@blueprint.route(f'/{table_name}/<int:item_id>/restore', methods=['GET', 'POST'])
@login_required
def restore(item_id):
    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete_hard', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()
    item = table.query.get(item_id)
    record_path = os.path.join(path, item.case.case_number, f"{item.record_name}")
    record_files = glob.glob(f"{record_path}*")
    for file in record_files:
        os.remove(file)

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():
    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items


# @blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
# @login_required
# def delete_items():
#
#     if current_user.permissions not in ['Owner']:
#         abort(403)
#
#     table.query.delete()
#
#     Modifications.query.filter_by(table_name=item_name).delete()
#
#     # for mod in mods:
#     #     db.session.delete(mod)
#     #     #mod.event = 'DELETE'
#     #     #mod.status = 'Deleted'
#     #     #mod.record_id = item.name
#
#     db.session.commit()
#
#     return redirect(url_for(f'{table_name}.view_list'))

@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    _import = import_items(form, table, table_name, item_name)

    return _import


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():
    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    kwargs = default_kwargs.copy()
    query = request.args.get('query')

    # For prefilling the form and max attr
    today_date = date.today().isoformat()
    kwargs['today_date'] = today_date

    # ---------- Record Type options ----------
    record_types = RecordTypes.query.order_by(RecordTypes.name.asc()).all()
    kwargs['record_type_options'] = [f'{rt.name}' for rt in record_types]

    selected_record_types = request.args.getlist('record_types')  # names
    kwargs['selected_record_types'] = selected_record_types

    # Map selected names -> IDs
    ids = []
    if selected_record_types:
        ids = [
            rt.id
            for rt in RecordTypes.query
                .filter(RecordTypes.name.in_(selected_record_types))
                .all()
        ]

    # ---------- Date Range (inclusive) ----------
    date_from_str = request.args.get('date_from')  # 'YYYY-MM-DD'
    date_to_str   = request.args.get('date_to')    # 'YYYY-MM-DD'

    # Prefill UI: keep To showing today by default; this does NOT force filtering
    kwargs['date_from'] = date_from_str or ''
    kwargs['date_to']   = (date_to_str or today_date)

    # ---------- Base query ----------
    r = Records.query

    # Record type filter
    if ids:
        r = r.filter(Records.record_type.in_(ids))

    # Date filter applies ONLY if date_from is provided
    date_field = Records.create_date  # change if you prefer a different column
    # Pull out the type object once
    sa_type = getattr(date_field, "type", None)

    # Robust datetime check: SQLAlchemy type OR python_type fallback
    is_datetime_col = isinstance(sa_type, DateTime) or getattr(sa_type, "python_type", None) is datetime

    if date_from_str:
        # Parse inputs
        date_from = None
        date_to = None
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
        except Exception:
            date_from = None  # bad input -> treat as blank (no date filter)

        if date_from:
            # If user gave date_to, use it; else open-ended (>= from)
            if date_to_str:
                try:
                    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                except Exception:
                    date_to = None

            # Swap if inverted
            if date_to and date_from > date_to:
                date_from, date_to = date_to, date_from
                kwargs['date_from'], kwargs['date_to'] = kwargs['date_to'], kwargs['date_from']

            # If your column is DateTime, use full-day bounds
            if is_datetime_col:  # safe guard if it’s DateTime
                start_dt = datetime.combine(date_from, datetime.min.time())
                if date_to:
                    end_dt = datetime.combine(date_to, datetime.max.time())
                    r = r.filter(date_field.between(start_dt, end_dt))
                else:
                    r = r.filter(date_field >= start_dt)
            else:
                # Column is a Date (or comparable)
                if date_to:
                    r = r.filter(date_field.between(date_from, date_to))
                else:
                    r = r.filter(date_field >= date_from)
    # else: no date_from provided -> no date filter at all

    items = r

    # ---------- Quick canned filters via ?query= ----------
    if query == 'removal-pending':
        items = r.filter(Records.db_status == 'Removal Pending')
    elif query == 'pending':
        items = r.filter(Records.db_status == 'Pending')
    elif query == 'locked':
        items = r.filter(Records.locked == True)

    # ---------- Finalized reports with no record linkage ----------
    null_record_reports = (
        Reports.query
        .filter(
            Reports.db_status != 'Removed',
            Reports.report_status == 'Finalized',
            Reports.record_id.is_(None)
        )
        .order_by(Reports.id.desc())
        .all()
    )
    kwargs['null_record_reports'] = null_record_reports
    kwargs['null_record_reports_count'] = len(null_record_reports)

    _view_list = view_items(
        table, item_name, item_type, table_name,
        items=items,
        pending_submitter_column=False,
        **kwargs
    )
    return _view_list




@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"
    kwargs = {}
    
    file_path = os.path.join(
        app.static_folder,
        'filesystem', 'records',
        item.case.case_number,
        f"{item.record_name}.pdf"
    )
    print(file_path)
    kwargs['file_exists'] = os.path.isfile(file_path) 
    

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments
import os, re, shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from flask import current_app, flash, redirect, url_for
from sqlalchemy import exists

import threading, time
from datetime import datetime, timedelta, time as dtime
# ... keep your existing imports above this route ...

RUN_AT_LOCAL = "18:05"  # <- set the daily time you want it to run (e.g., 21:00 for 9 PM)

SRC_DIR = r"D:\Copied 2024 Records"   # <- your source folder (read-only)
OVERWRITE_DEST = False                 # unchanged

@blueprint.route(f'/{table_name}/add_legacy_records', methods=['GET', 'POST'])
@login_required
def add_legacy_records():
    # capture the real app for background context
    app_obj = current_app._get_current_object()

    def _seconds_until_run():
        hh, mm = [int(x) for x in RUN_AT_LOCAL.split(":")]
        now = datetime.now()
        target = datetime.combine(now.date(), dtime(hour=hh, minute=mm))
        if target <= now:
            target = target + timedelta(days=1)
        return int((target - now).total_seconds())

    def _worker():
        delay = _seconds_until_run()
        print(f"[LegacyImport] Scheduled at {datetime.now():%Y-%m-%d %H:%M:%S}; sleeping {delay} sec until {RUN_AT_LOCAL} local...")
        time.sleep(delay)  # <-- waiting here does NOT hold any request/DB/app locks

        with app_obj.app_context():
            # ===== BEGIN: your original logic (unchanged) =====
            start_ts = datetime.now()
            print(f"[LegacyImport] START at {start_ts:%Y-%m-%d %H:%M:%S} from {SRC_DIR}")

            src = Path(SRC_DIR)
            if not src.exists() or not src.is_dir():
                err = f"Source directory not found: {SRC_DIR}"
                print(f"[LegacyImport] {err}")
                app_obj.logger.error(err)  # (can't flash from background thread)
                return

            app_root = Path(app_obj.root_path)
            records_root = app_root / "static" / "filesystem" / "records"
            records_root.mkdir(parents=True, exist_ok=True)

            FNAME_RE = re.compile(
                r"""^(?P<case_number>[^_]+)_
                     (?P<code>[A-Za-z]+?)
                     (?P<num>\d+)
                     (?:[^\\/]*)?
                     \.pdf$""",
                re.IGNORECASE | re.VERBOSE
            )

            def parse_filename(pdf_name: str):
                m = FNAME_RE.match(pdf_name)
                if not m:
                    return None
                case_number = m.group("case_number")
                code_letter = m.group("code")[0].upper()
                record_number = int(m.group("num"))
                record_name = pdf_name[:-4]
                return case_number, code_letter, record_number, record_name

            def record_type_for(code_letter: str) -> Optional[int]:
                return {"T": 10, "B": 2, "X": 11}.get(code_letter)

            def ensure_case_folder(case_number: str) -> Path:
                dest = records_root / case_number
                dest.mkdir(parents=True, exist_ok=True)
                return dest

            copied = created = skipped_dupe = skipped_nomatch = skipped_unknown = skipped_exists = errors = 0
            pdf_files = sorted([p for p in src.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])

            for pdf in pdf_files:
                try:
                    parsed = parse_filename(pdf.name)
                    if not parsed:
                        skipped_nomatch += 1
                        msg = f"[LegacyImport] SKIP (name pattern not recognized): {pdf.name}"
                        print(msg); app_obj.logger.warning(msg)
                        continue

                    case_number, code_letter, record_number, record_name = parsed
                    rtype = record_type_for(code_letter)
                    if rtype is None:
                        skipped_unknown += 1
                        msg = f"[LegacyImport] SKIP (unknown code '{code_letter}') for {pdf.name}"
                        print(msg); app_obj.logger.warning(msg)
                        continue

                    dest_folder = ensure_case_folder(case_number)
                    dest_path = dest_folder / pdf.name

                    if dest_path.exists() and not OVERWRITE_DEST:
                        skipped_exists += 1
                        print(f"[LegacyImport] SKIP COPY (already exists): {str(dest_path)}")
                    else:
                        if dest_path.exists() and OVERWRITE_DEST:
                            dest_path.unlink()  # replace dest only; source untouched
                        shutil.copy2(str(pdf), str(dest_path))  # COPY (not move)
                        copied += 1
                        print(f"[LegacyImport] COPIED -> {str(dest_path)}")

                    # Find case for DB insert
                    case = Cases.query.filter(Cases.case_number == case_number).first()
                    if not case:
                        msg = f"[LegacyImport] WARN: No Case found for {case_number}; file copied but no DB row."
                        print(msg); app_obj.logger.warning(msg)
                        continue

                    # MSSQL-safe dupe check
                    dupe = db.session.query(Records.id).filter(Records.record_name == record_name).first()
                    if dupe is not None:
                        skipped_dupe += 1
                        msg = f"[LegacyImport] SKIP DUPLICATE record_name: {record_name}"
                        print(msg); app_obj.logger.info(msg)
                        continue

                    rec = Records(
                        case_id=case.id,
                        record_name=record_name,
                        record_number=record_number,
                        record_type=rtype,
                        created_by='ZZZ',
                        create_date=datetime.now()
                    )
                    db.session.add(rec)
                    db.session.commit()
                    created += 1
                    print(f"[LegacyImport] CREATED record -> case_id={case.id} "
                          f"name='{record_name}' type={rtype} number={record_number}")

                except Exception as e:
                    db.session.rollback()
                    errors += 1
                    msg = f"[LegacyImport] ERROR on {pdf.name}: {e}"
                    print(msg); app_obj.logger.exception(msg)

            msg = (f"Legacy import: copied {copied}, created {created}, "
                   f"skipped exists {skipped_exists}, skipped duplicates {skipped_dupe}, "
                   f"skipped non-matching {skipped_nomatch}, skipped unknown {skipped_unknown}, "
                   f"errors {errors}.")
            print(f"[LegacyImport] SUMMARY: {msg}")
            app_obj.logger.info("[LegacyImport] " + msg)

            end_ts = datetime.now()
            print(f"[LegacyImport] END at {end_ts:%Y-%m-%d %H:%M:%S} (elapsed {(end_ts - start_ts).total_seconds():.1f}s)")
            # ===== END: your original logic (unchanged) =====

    # Start background thread; the request returns immediately
    t = threading.Thread(target=_worker, name=f"legacy_import_at_{RUN_AT_LOCAL.replace(':','')}", daemon=True)
    t.start()

    # Immediate response; nothing is locked while waiting
    flash(f"Legacy import scheduled for {RUN_AT_LOCAL} (local time). The app remains fully usable.", "message")
    return redirect(url_for('records.view_list'))

# import csv
# import os
# import shutil
# from datetime import datetime

# from flask import render_template_string
# from flask_login import login_required

# from lims import db
# from lims.models import Attachments, AttachmentTypes, Instruments  # adjust if needed


# def _process_new_attachments_csv(csv_path: str):
#     """
#     Internal helper used by the route.

#     CSV layout:
#       A (0): source folder path
#       B (1): filename
#       E (4): record_id
#       G (6): attachment type id
#       H (7): table_name
#       I (8): destination folder path
#     """

#     # Get the current max id so we can increment manually
#     current_max_id = db.session.query(db.func.max(Attachments.id)).scalar()
#     if current_max_id is None:
#         current_max_id = 0
#     next_id = current_max_id + 1

#     file_errors = []        # problems with file paths / copying
#     attachment_errors = []  # problems creating the Attachments row
#     processed_count = 0

#     with open(csv_path, newline="", encoding="utf-8-sig") as f:
#         reader = csv.reader(f)
#         header = next(reader, None)  # skip header row

#         for line_num, row in enumerate(reader, start=2):
#             try:
#                 # Basic length check
#                 if len(row) < 9:
#                     file_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": f"Row has only {len(row)} columns, expected at least 9.",
#                             "row": row,
#                         }
#                     )
#                     continue

#                 source_dir = row[0].strip()      # col A
#                 filename = row[1].strip()        # col B
#                 record_id_raw = row[4].strip()   # col E
#                 type_id_raw = row[6].strip()     # col G
#                 table_name = row[7].strip()      # col H
#                 dest_dir = row[8].strip()        # col I

#                 # Skip rows with missing critical info
#                 if (
#                     not filename
#                     or not dest_dir
#                     or not table_name
#                     or not record_id_raw
#                     or not type_id_raw
#                 ):
#                     file_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": "Missing required values (filename, dest_dir, table_name, record_id, or type_id).",
#                             "row": row,
#                         }
#                     )
#                     continue

#                 # Convert ids
#                 try:
#                     record_id = int(record_id_raw)
#                 except ValueError:
#                     file_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": f"record_id not an integer: {record_id_raw}",
#                             "row": row,
#                         }
#                     )
#                     continue

#                 try:
#                     type_id = int(type_id_raw)
#                 except ValueError:
#                     file_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": f"type_id not an integer: {type_id_raw}",
#                             "row": row,
#                         }
#                     )
#                     continue

#                 # Build paths
#                 source_path = os.path.join(source_dir, filename)
#                 dest_path_folder = dest_dir
#                 dest_path = os.path.join(dest_path_folder, filename)

#                 # Make sure destination folder exists
#                 os.makedirs(dest_path_folder, exist_ok=True)

#                 # ---- COPY the file (do NOT move, do NOT delete) ----
#                 source_exists = os.path.exists(source_path)
#                 dest_exists = os.path.exists(dest_path)

#                 if source_exists and not dest_exists:
#                     # Normal case: copy from source to dest, keep source
#                     try:
#                         shutil.copy2(source_path, dest_path)
#                     except Exception as e:
#                         file_errors.append(
#                             {
#                                 "line": line_num,
#                                 "reason": f"Error copying file: {e}",
#                                 "row": row,
#                                 "source_path": source_path,
#                                 "dest_path": dest_path,
#                             }
#                         )
#                         continue
#                 elif source_exists and dest_exists:
#                     # Already copied previously; keep both, no error
#                     pass
#                 elif not source_exists and dest_exists:
#                     # Source missing but file already in destination -> assume already copied earlier
#                     pass
#                 else:
#                     # Source missing and not in destination -> real failure
#                     file_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": "Source file not found and not present at destination.",
#                             "row": row,
#                             "source_path": source_path,
#                             "dest_path": dest_path,
#                         }
#                     )
#                     continue
#                 # ---- end copy block ----

#                 # Get attachment type name
#                 attachment_type = AttachmentTypes.query.get(type_id)
#                 if not attachment_type:
#                     attachment_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": f"No AttachmentTypes row for id {type_id}",
#                             "row": row,
#                             "save_name": None,
#                             "record_id": record_id,
#                             "type_id": type_id,
#                             "attachment_path": dest_path,
#                         }
#                     )
#                     continue
#                 attachment_type_name = attachment_type.name

#                 # Try to get instrument code if table_name is Instruments
#                 instrument_code = ""
#                 if table_name.lower() == "instruments":
#                     instrument = Instruments.query.get(record_id)
#                     if instrument is not None:
#                         # Adjust attribute names to match your Instruments model
#                         instrument_code = getattr(instrument, "instrument_id", "") or getattr(
#                             instrument, "name", ""
#                         )

#                 # Build save_name per your example:
#                 # Attachment-Instruments-Service Report (Legacy)  - RAND1_RE Randox Follow Up 2018.msg
#                 if instrument_code:
#                     save_name = f"Attachment-{table_name}-{attachment_type_name}  - {instrument_code} {filename}"
#                 else:
#                     save_name = f"Attachment-{table_name}-{attachment_type_name}  - {filename}"

#                 # Path stored in DB: column I + "\" + filename
#                 attachment_path = os.path.join(dest_dir, filename)

#                 # Create Attachment row with its own error handling bucket
#                 try:
#                     attachment = Attachments(
#                         id=next_id,
#                         table_name=table_name,
#                         record_id=record_id,
#                         type_id=type_id,
#                         name=filename,
#                         save_name=save_name,
#                         path=attachment_path,
#                         db_status="Active",
#                         create_date=datetime.now(),
#                         created_by="ZZZ",
#                     )

#                     db.session.add(attachment)
#                     next_id += 1
#                     processed_count += 1

#                 except Exception as e:
#                     attachment_errors.append(
#                         {
#                             "line": line_num,
#                             "reason": f"Attachment creation failed: {e}",
#                             "row": row,
#                             "save_name": save_name,
#                             "record_id": record_id,
#                             "type_id": type_id,
#                             "attachment_path": attachment_path,
#                         }
#                     )
#                     continue

#             except Exception as e:
#                 # Catch-all row-level error – treat as a file-level issue
#                 file_errors.append(
#                     {
#                         "line": line_num,
#                         "reason": f"Unexpected error: {e}",
#                         "row": row,
#                     }
#                 )
#                 continue

#     db.session.commit()

#     return {
#         "processed_count": processed_count,
#         "file_errors": file_errors,
#         "attachment_errors": attachment_errors,
#     }


# # KEEP THIS FORMAT
# @blueprint.route(f'/{table_name}/copy_new_csv_files_and_attach_equipment', methods=['GET', 'POST'])
# @login_required
# def copy_new_csv_files_and_attach_equipment():
#     """
#     Route to:
#       - Copy files using column A (source path), B (filename), I (destination path)
#       - Create Attachments rows using:
#             table_name = col H
#             record_id  = col E
#             type_id    = col G
#             name       = col B
#             save_name  = Attachment-table_name-attachment type name-table_name.record_id.instrument_id_original file name
#             path       = col I + "\\" + filename
#     """

#     # 🔴 UPDATE THIS PATH FOR YOUR CSV 🔴
#     CSV_PATH = r"D:\F - Equipment and Manuals\equipment_migration.csv"

#     result = _process_new_attachments_csv(CSV_PATH)
#     file_errors = result["file_errors"]
#     attachment_errors = result["attachment_errors"]
#     processed_count = result["processed_count"]

#     # HTML summary so you can see what happened in the browser
#     html = """
#     <h2>Copy CSV Files & Create Attachments</h2>
#     <p>Processed rows (attachments successfully created): {{ processed_count }}</p>

#     <hr>

#     <h3 style="color:#c00;">File Copy Errors ({{ file_errors|length }})</h3>
#     {% if file_errors %}
#       <ul>
#       {% for f in file_errors %}
#         <li>
#           <b>Row {{ f.line }}</b>: {{ f.reason }}<br>
#           {% if f.source_path %}<i>Source:</i> {{ f.source_path }}<br>{% endif %}
#           {% if f.dest_path %}<i>Dest:</i> {{ f.dest_path }}<br>{% endif %}
#         </li><br>
#       {% endfor %}
#       </ul>
#     {% else %}
#       <p style="color:green;">No file copy errors.</p>
#     {% endif %}

#     <hr>

#     <h3 style="color:#c00;">Attachment Creation Errors ({{ attachment_errors|length }})</h3>
#     {% if attachment_errors %}
#       <ul>
#       {% for f in attachment_errors %}
#         <li>
#           <b>Row {{ f.line }}</b>: {{ f.reason }}<br>
#           <i>save_name:</i> {{ f.save_name }}<br>
#           <i>record_id:</i> {{ f.record_id }}<br>
#           <i>type_id:</i> {{ f.type_id }}<br>
#           <i>path:</i> {{ f.attachment_path }}<br>
#         </li><br>
#       {% endfor %}
#       </ul>
#     {% else %}
#       <p style="color:green;">No attachment creation errors.</p>
#     {% endif %}
#     """

#     return render_template_string(
#         html,
#         processed_count=processed_count,
#         file_errors=file_errors,
#         attachment_errors=attachment_errors,
#     )
# @blueprint.route(f'/{table_name}/copy_new_csv_files_and_attach_route_instruments', methods=['GET', 'POST'])
# @login_required
# def copy_new_csv_files_and_attach_route_instruments():
#     """
#     Route to:
#       - Copy files using column A (source path), B (filename), I (destination path)
#       - Create Attachments rows using:
#             table_name = col H
#             record_id  = col E
#             type_id    = col G
#             name       = col B
#             save_name  = Attachment-table_name-attachment type name-table_name.record_id.instrument_id_original file name
#             path       = col I + "\\" + filename
#     """

#     # 🔴 UPDATE THIS PATH FOR YOUR CSV 🔴
#     CSV_PATH = r"D:\J - Instruments\instruments_migration.csv"

#     result = _process_new_attachments_csv(CSV_PATH)
#     file_errors = result["file_errors"]
#     attachment_errors = result["attachment_errors"]
#     processed_count = result["processed_count"]

#     # HTML summary so you can see what happened in the browser
#     html = """
#     <h2>Copy CSV Files & Create Attachments</h2>
#     <p>Processed rows (attachments successfully created): {{ processed_count }}</p>

#     <hr>

#     <h3 style="color:#c00;">File Copy Errors ({{ file_errors|length }})</h3>
#     {% if file_errors %}
#       <ul>
#       {% for f in file_errors %}
#         <li>
#           <b>Row {{ f.line }}</b>: {{ f.reason }}<br>
#           {% if f.source_path %}<i>Source:</i> {{ f.source_path }}<br>{% endif %}
#           {% if f.dest_path %}<i>Dest:</i> {{ f.dest_path }}<br>{% endif %}
#         </li><br>
#       {% endfor %}
#       </ul>
#     {% else %}
#       <p style="color:green;">No file copy errors.</p>
#     {% endif %}

#     <hr>

#     <h3 style="color:#c00;">Attachment Creation Errors ({{ attachment_errors|length }})</h3>
#     {% if attachment_errors %}
#       <ul>
#       {% for f in attachment_errors %}
#         <li>
#           <b>Row {{ f.line }}</b>: {{ f.reason }}<br>
#           <i>save_name:</i> {{ f.save_name }}<br>
#           <i>record_id:</i> {{ f.record_id }}<br>
#           <i>type_id:</i> {{ f.type_id }}<br>
#           <i>path:</i> {{ f.attachment_path }}<br>
#         </li><br>
#       {% endfor %}
#       </ul>
#     {% else %}
#       <p style="color:green;">No attachment creation errors.</p>
#     {% endif %}
#     """

#     return render_template_string(
#         html,
#         processed_count=processed_count,
#         file_errors=file_errors,
#         attachment_errors=attachment_errors,
#     )
import csv
import os
import shutil

from flask import render_template_string
from flask_login import login_required


def _process_new_attachments_csv(csv_path: str):
    """
    Internal helper used by the route.

    CSV layout (still using the same columns, but only A, B, and I are needed):
      A (0): source folder path
      B (1): filename
      E (4): record_id            [ignored]
      G (6): attachment type id   [ignored]
      H (7): table_name           [ignored]
      I (8): destination folder path

    Functionality:
      - Copy files from source (A + B) to destination (I + B)
      - Do NOT create or modify any database rows
    """

    file_errors = []        # problems with file paths / copying
    processed_count = 0     # number of rows where copy step was "ok" (copied or already present)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header row

        for line_num, row in enumerate(reader, start=2):
            try:
                # Need at least up to col I (index 8)
                if len(row) < 9:
                    file_errors.append(
                        {
                            "line": line_num,
                            "reason": f"Row has only {len(row)} columns, expected at least 9 (needs A,B,I).",
                            "row": row,
                        }
                    )
                    continue

                source_dir = (row[0] or "").strip()   # col A
                filename = (row[1] or "").strip()     # col B
                dest_dir = (row[8] or "").strip()     # col I

                # Skip rows with missing critical info
                if not filename or not dest_dir or not source_dir:
                    file_errors.append(
                        {
                            "line": line_num,
                            "reason": "Missing required values (source_dir, filename, or dest_dir).",
                            "row": row,
                        }
                    )
                    continue

                # Build paths
                source_path = os.path.join(source_dir, filename)
                dest_path_folder = dest_dir
                dest_path = os.path.join(dest_path_folder, filename)

                # Make sure destination folder exists
                os.makedirs(dest_path_folder, exist_ok=True)

                # ---- COPY the file (do NOT move, do NOT delete) ----
                source_exists = os.path.exists(source_path)
                dest_exists = os.path.exists(dest_path)

                if source_exists and not dest_exists:
                    # Normal case: copy from source to dest, keep source
                    try:
                        shutil.copy2(source_path, dest_path)
                        processed_count += 1
                    except Exception as e:
                        file_errors.append(
                            {
                                "line": line_num,
                                "reason": f"Error copying file: {e}",
                                "row": row,
                                "source_path": source_path,
                                "dest_path": dest_path,
                            }
                        )
                        continue
                elif source_exists and dest_exists:
                    # Already copied previously; count as processed but not an error
                    processed_count += 1
                elif not source_exists and dest_exists:
                    # Source missing but file already in destination -> assume already copied earlier
                    processed_count += 1
                else:
                    # Source missing and not in destination -> real failure
                    file_errors.append(
                        {
                            "line": line_num,
                            "reason": "Source file not found and not present at destination.",
                            "row": row,
                            "source_path": source_path,
                            "dest_path": dest_path,
                        }
                    )
                    continue
                # ---- end copy block ----

            except Exception as e:
                # Catch-all row-level error – treat as a file-level issue
                file_errors.append(
                    {
                        "line": line_num,
                        "reason": f"Unexpected error: {e}",
                        "row": row,
                    }
                )
                continue

    return {
        "processed_count": processed_count,
        "file_errors": file_errors,
    }



@blueprint.route(f'/{table_name}/copy_new_csv_files_and_attach_instruments', methods=['GET', 'POST'])
@login_required
def copy_new_csv_files_and_attach_route_instruments():
    """
    Route to:
      - Copy files using:
            source path      = col A
            filename         = col B
            destination path = col I

    No database changes are made by this route.
    """

    # 🔴 UPDATE THIS PATH FOR YOUR CSV 🔴
    CSV_PATH = r"D:\J - Instruments\instruments_migration.csv"

    result = _process_new_attachments_csv(CSV_PATH)
    file_errors = result["file_errors"]
    processed_count = result["processed_count"]

    # HTML summary so you can see what happened in the browser
    html = """
    <h2>Copy CSV Files</h2>
    <p>Processed rows (files copied or already present): {{ processed_count }}</p>

    <hr>

    <h3 style="color:#c00;">File Copy Errors ({{ file_errors|length }})</h3>
    {% if file_errors %}
      <ul>
      {% for f in file_errors %}
        <li>
          <b>Row {{ f.line }}</b>: {{ f.reason }}<br>
          {% if f.source_path %}<i>Source:</i> {{ f.source_path }}<br>{% endif %}
          {% if f.dest_path %}<i>Dest:</i> {{ f.dest_path }}<br>{% endif %}
        </li><br>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:green;">No file copy errors.</p>
    {% endif %}
    """

    return render_template_string(
        html,
        processed_count=processed_count,
        file_errors=file_errors,
    )

@blueprint.route(f'/{table_name}/copy_new_csv_files_and_attach_equipment', methods=['GET', 'POST'])
@login_required
def copy_new_csv_files_and_attach_route_equipment():
    """
    Route to:
      - Copy files using:
            source path      = col A
            filename         = col B
            destination path = col I

    No database changes are made by this route.
    """

    # 🔴 UPDATE THIS PATH FOR YOUR CSV 🔴
    CSV_PATH = r"D:\F - Equipment and Manuals\equipment_migration.csv"

    result = _process_new_attachments_csv(CSV_PATH)
    file_errors = result["file_errors"]
    processed_count = result["processed_count"]

    # HTML summary so you can see what happened in the browser
    html = """
    <h2>Copy CSV Files</h2>
    <p>Processed rows (files copied or already present): {{ processed_count }}</p>

    <hr>

    <h3 style="color:#c00;">File Copy Errors ({{ file_errors|length }})</h3>
    {% if file_errors %}
      <ul>
      {% for f in file_errors %}
        <li>
          <b>Row {{ f.line }}</b>: {{ f.reason }}<br>
          {% if f.source_path %}<i>Source:</i> {{ f.source_path }}<br>{% endif %}
          {% if f.dest_path %}<i>Dest:</i> {{ f.dest_path }}<br>{% endif %}
        </li><br>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:green;">No file copy errors.</p>
    {% endif %}
    """

    return render_template_string(
        html,
        processed_count=processed_count,
        file_errors=file_errors,
    )

