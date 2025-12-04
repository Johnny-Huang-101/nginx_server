from lims.forms import Attach, Import
from lims.models import *
from lims.view_templates.views import *

# Set item Global Variables
item_type = 'FA Personal Effect'
item_name = 'FA Personal Effects'
table = FAPersonalEffects
table_name = 'fa_personal_effects'
name = "type"
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to,
                  'disable_fields': disable_fields}

# Filesystem path
path = None
# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())
    if request.method == 'POST':
        kwargs.update(process_form(form))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Edit())
    if request.method == 'POST':
        kwargs.update(process_form(form))
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Approve())
    if request.method == 'POST':
        kwargs.update(process_form(form))
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Update())
    if request.method == 'POST':
        kwargs.update(process_form(form))
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


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():

    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items


@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    _import = import_items(form, table, table_name, item_name, dtype={'street_number': str, 'zipcode': str})

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

@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    _view_list = view_items(table, item_name, item_type, table_name)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"


    _view = view_item(item, alias, item_name, table_name)
    return _view

from flask import jsonify, current_app
from sqlalchemy import and_, or_
from sqlalchemy.orm import load_only
import os, glob
from collections import defaultdict
from lims.cases.functions import generate_decedent_report
# from lims import db
# from lims.models import Cases, Records, FAPersonalEffects, Reports

def _pe_key(pe):
    return (
        pe.case_id, pe.type, pe.description, pe.disposition,
        pe.received_by, pe.received_date, pe.released_to, pe.released_date
    )

def _fmt_dt(dt):
    return dt.isoformat(sep=' ', timespec='seconds') if dt else None

def _delete_fs_artifacts_by_stem(base_dir, stem):
    deleted, missing = [], []
    patterns = [f"{stem}.pdf", f"{stem}.docx", f"{stem}.doc", f"{stem}.rtf", f"{stem}.txt", f"{stem}.*"]
    for patt in patterns:
        full_pattern = os.path.join(base_dir, patt)
        matches = glob.glob(full_pattern)
        if not matches and patt != f"{stem}.*":
            missing.append(full_pattern)
        for fp in matches:
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
                    deleted.append(fp)
            except Exception as ex:
                current_app.logger.exception(f"Failed deleting artifact '{fp}': {ex}")
    return deleted, missing

def _delete_existing_O1_for_case(case_id, case_number):
    base_dir = os.path.join(current_app.root_path, 'static', 'filesystem', 'records', str(case_number or ''))
    removed_record_ids, removed_files, missing_files = [], [], []

    o1_recs = (Records.query
               .filter(and_(Records.case_id == case_id,
                            or_(Records.record_name.like('%\\_O1', escape='\\'),
                                Records.record_name.like('%\\_O1.%', escape='\\'))))
               .all())

    for r in o1_recs:
        if r.record_name:
            fp = os.path.join(base_dir, r.record_name)
            try:
                if os.path.exists(fp):
                    os.remove(fp)
                    removed_files.append(fp)
                else:
                    missing_files.append(fp)
            except Exception as ex:
                current_app.logger.exception(f"Failed to delete O1 file '{fp}': {ex}")

        try:
            if hasattr(r, 'records_reports') and r.records_reports:
                for rep in list(r.records_reports):
                    db.session.delete(rep)
        except Exception as ex:
            current_app.logger.exception(f"Failed to delete linked Reports for record id={r.id}: {ex}")

        try:
            db.session.delete(r)
            removed_record_ids.append(r.id)
        except Exception as ex:
            current_app.logger.exception(f"Failed to delete O1 record id={r.id}: {ex}")

    # Also remove canonical <case>_O1.*
    stem_deleted, stem_missing = _delete_fs_artifacts_by_stem(base_dir, f"{case_number}_O1")
    removed_files.extend(stem_deleted); missing_files.extend(stem_missing)

    if removed_record_ids:
        db.session.commit()

    msg = (f"[O1 RESET] Case {case_number} (id={case_id}) — "
           f"removed O1 records {removed_record_ids}; "
           f"files deleted: {len(removed_files)}, files missing: {len(missing_files)}")
    print(msg); current_app.logger.info(msg)

    return {
        "o1_records_deleted": removed_record_ids,
        "o1_files_deleted": removed_files,
        "o1_files_missing": missing_files,
    }

@blueprint.route(f'/{table_name}/correct_duplicates', methods=['GET', 'POST'])
@login_required
def correct_duplicates():
    # --------- ALWAYS-DEFINED ACCUMULATORS (prevents NameError) ----------
    dup_ids_to_delete = []
    cases_touched = set()
    printable_dups_by_case = defaultdict(list)
    records_deleted, files_deleted, files_missing = [], [], []
    o1_resets = {}
    generated_for, gen_errors = [], []

    # ---- Load PEs & group for duplicates ----
    effects = (FAPersonalEffects.query
               .options(load_only(
                   FAPersonalEffects.id, FAPersonalEffects.case_id, FAPersonalEffects.type,
                   FAPersonalEffects.description, FAPersonalEffects.disposition,
                   FAPersonalEffects.received_by, FAPersonalEffects.received_date,
                   FAPersonalEffects.released_to, FAPersonalEffects.released_date,
               ))
               .order_by(FAPersonalEffects.case_id.asc(), FAPersonalEffects.id.asc())
               .all())

    groups = defaultdict(list)
    for pe in effects:
        groups[_pe_key(pe)].append(pe)

    for key, rows in groups.items():
        if len(rows) > 1:
            keep_id = rows[0].id
            extras = rows[1:]
            dup_ids_to_delete.extend([r.id for r in extras])
            cases_touched.add(rows[0].case_id)

            case_id, t, desc, disp, recv_by, recv_dt, rel_to, rel_dt = key
            printable_dups_by_case[case_id].append({
                "count": len(rows),
                "kept_id": keep_id,
                "duplicate_ids": [r.id for r in extras],
                "type": t,
                "description": desc,
                "disposition": disp,
                "received_by": recv_by,
                "received_date": _fmt_dt(recv_dt),
                "released_to": rel_to,
                "released_date": _fmt_dt(rel_dt),
            })

    # ---- Print summary BEFORE deletion (only if any duplicates) ----
    if printable_dups_by_case:
        case_map = {
            c.id: c.case_number
            for c in (Cases.query
                      .options(load_only(Cases.id, Cases.case_number))
                      .filter(Cases.id.in_(printable_dups_by_case.keys())).all())
        }
        print("\n=== FAPersonalEffects Duplicate Summary (exact-match) ===")
        current_app.logger.info("=== FAPersonalEffects Duplicate Summary (exact-match) ===")
        total_dup_groups = sum(len(v) for v in printable_dups_by_case.values())
        line = f"Cases with duplicates: {len(printable_dups_by_case)} | Duplicate groups: {total_dup_groups}"
        print(line); current_app.logger.info(line)
        for case_id, groups_for_case in sorted(printable_dups_by_case.items()):
            case_line = f"\nCase {case_map.get(case_id, 'UNKNOWN')} (id={case_id}) — {len(groups_for_case)} duplicate group(s)"
            print(case_line); current_app.logger.info(case_line)
            for idx, g in enumerate(groups_for_case, start=1):
                l1 = f"  [{idx}] count={g['count']} | keep id={g['kept_id']} | delete ids={g['duplicate_ids']}"
                l2 = (f"       type='{g['type']}' | desc='{g['description']}' | disp='{g['disposition']}' | "
                      f"received_by={g['received_by']} | received_date={g['received_date']} | "
                      f"released_to='{g['released_to']}' | released_date={g['released_date']}")
                print(l1); print(l2); current_app.logger.info(l1); current_app.logger.info(l2)
        print("=== End Duplicate Summary ===\n")
        current_app.logger.info("=== End Duplicate Summary ===")

    # ---- Delete duplicate PEs (no-op if none) ----
    if dup_ids_to_delete:
        (FAPersonalEffects.query
         .filter(FAPersonalEffects.id.in_(dup_ids_to_delete))
         .delete(synchronize_session=False))

    # ---- Remove records 13/14 + files (only if we actually touched cases) ----
    if cases_touched:
        case_map = {
            c.id: c.case_number
            for c in (Cases.query
                      .options(load_only(Cases.id, Cases.case_number))
                      .filter(Cases.id.in_(cases_touched)).all())
        }

        for case_id in cases_touched:
            case_number = str(case_map.get(case_id, '') or '')
            base_dir = os.path.join(current_app.root_path, 'static', 'filesystem', 'records', case_number)

            recs = (Records.query
                    .filter(and_(Records.case_id == case_id,
                                 Records.record_type.in_([13, 14])))
                    .all())

            # delete by recorded filename
            for r in recs:
                if r.record_name:
                    fp = os.path.join(base_dir, r.record_name)
                    try:
                        if os.path.exists(fp):
                            os.remove(fp)
                            files_deleted.append(fp)
                        else:
                            files_missing.append(fp)
                    except Exception as ex:
                        current_app.logger.exception(f"Failed to delete file '{fp}': {ex}")

                try:
                    db.session.delete(r)
                    records_deleted.append(r.id)
                except Exception as ex:
                    current_app.logger.exception(f"Failed to delete record id={r.id}: {ex}")

            # ALSO delete canonical stems
            r1_deleted, r1_missing = _delete_fs_artifacts_by_stem(base_dir, f"{case_number}_R1")
            o1_deleted, o1_missing = _delete_fs_artifacts_by_stem(base_dir, f"{case_number}_O1")
            files_deleted.extend(r1_deleted + o1_deleted)
            files_missing.extend(r1_missing + o1_missing)

        db.session.commit()  # commit 13/14 & PE deletions

        # ---- Ensure O1 is gone before generating fresh O1 ----
        for case_id in cases_touched:
            cn = case_map.get(case_id)
            o1_resets[case_id] = _delete_existing_O1_for_case(case_id, cn)

        # ---- Generate decedent report (fresh O1) ----
        for case_id in cases_touched:
            try:
                generate_decedent_report(case_id)
                generated_for.append(case_id)
            except Exception as ex:
                gen_errors.append({"case_id": case_id, "error": str(ex)})
                current_app.logger.exception(f"generate_decedent_report failed for case_id={case_id}: {ex}")

    # Summary always returns (even if nothing was touched)
    return jsonify({
        "personal_effects": {
            "duplicate_groups_found": sum(len(v) for v in printable_dups_by_case.values()),
            "duplicates_deleted": len(dup_ids_to_delete),
            "cases_touched": sorted(list(cases_touched)),
        },
        "records_cleanup": {
            "count_deleted_13_14": len(records_deleted),
            "files_deleted": len(files_deleted),
            "files_missing": len(files_missing),
        },
        "o1_resets": o1_resets,
        "decedent_reports": {
            "generated_for_case_ids": sorted(generated_for),
            "errors": gen_errors,
        }
    })