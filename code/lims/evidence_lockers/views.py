import qrcode

from lims.evidence_lockers.functions import get_form_choices
from lims.labels import fields_dict, print_label
from lims.locations.functions import set_location, models_iter, location_dict, get_location_display
from lims.models import EvidenceLockers, Locations, Specimens, Cases, Containers, SpecimenTypes
from lims.evidence_lockers.forms import Add, Edit, Approve, Update
from lims.forms import Attach, Import
from lims.view_templates.views import *


import csv
from flask import jsonify
from pathlib import Path
from flask import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from io import BytesIO
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.styles import Font, PatternFill, Color
import os
from sqlalchemy import and_, func

from datetime import datetime

todaysdate = datetime.today().strftime("%Y%m%d")

# Set item global variables
item_type = 'Evidence Locker'
item_name = 'Evidence Lockers'
table = EvidenceLockers
table_name = "evidence_lockers"
name = 'equipment_id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

    if form.is_submitted() and form.validate():
        set_location(table_name, None, form.location_table.data, form.location_id.data)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
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
    form = get_form_choices(Update())

    if form.is_submitted() and form.validate():
        set_location(table_name, item_id, form.location_table.data, form.location_id.data)

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs,
                          locking=False)

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

    file_path = request.args.get('file_path')

    pdf_path = request.args.get('pdf_path')

    _attach = attach_items(form, item_id, table, item_name, table_name, name, file_path=file_path, pdf_path = pdf_path)

    

    return _attach


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = {'locations': Locations.query.all(), 'models': models_iter, 'location_dict': location_dict}

    _view_list = view_items(table, item_name, item_type, table_name, **kwargs)

    # for item in table.query:
    #     item.occupied = False
    # db.session.commit()

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)
    kwargs = {'location_display': get_location_display(table_name, item.id)}

    alias = f"{getattr(item, name)}"

    custody_id = table.query.get_or_404(item_id).equipment_id
    safe_custody_id = custody_id.replace("->", "__").replace(" ", "")
    file_path = Path(current_app.static_folder) / 'resource_manifests' / f"{safe_custody_id}_{todaysdate}_InitialSealAudit.csv"
    manifest_exists = file_path.exists()

    kwargs['manifest_exists'] = manifest_exists
    
    manifest_attached = Attachments.query.filter(
        and_(
            Attachments.table_name == item_name,
            Attachments.record_id == item_id,
            func.lower(Attachments.name).like('%manifest%')
        )
    ).first() is not None

    print(manifest_attached)
    kwargs['manifest_attached'] = manifest_attached

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/print_label', methods=['GET', 'POST'])
@login_required
def print_labels(item_id):
    # Get current item
    item = table.query.get(item_id)

    # Set printer to reagent printer
    printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 – Reagent Prep'
    # Get label_attributes dict
    label_attributes = fields_dict['equipment']
    attributes_list = []

    # Set relevant label_attributes
    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'{table_name}{item.id}.png')
    qrcode.make(f'{table_name}: {item.id}').save(qr_path)
    label_attributes['EQUIP_ID'] = item.equipment_id
    label_attributes['TYPE'] = item.type.name
    label_attributes['QR'] = qr_path

    attributes_list.append(label_attributes)

    # Print label
    print_label(printer, attributes_list)

    print(f'DONE PRINT LABEL HERE')

    return redirect(url_for(f'{table_name}.view', item_id=item.id))


@blueprint.route(f'/{table_name}/<int:item_id>/empty', methods=['GET', 'POST'])
@login_required
def empty(item_id):
    item = table.query.get(item_id)

    item.occupied = False

    return redirect(url_for(f'{table_name}.view_list'))




#change ths hwhokle function
@blueprint.route(f'/{table_name}/<int:item_id>/generate_manifest_raw', methods=['POST'])
@login_required
def generate_manifest_raw(item_id):
    custody_id = table.query.get_or_404(item_id).equipment_id

    # Query all specimens with that custody ID
    specimens = Specimens.query.filter_by(custody=custody_id).all()

    # Ensure the target folder exists
    folder_path = Path(current_app.static_folder) / 'resource_manifests'
    folder_path.mkdir(parents=True, exist_ok=True)

    # Build filename and path
    safe_custody_id = custody_id.replace("->", "__").replace(" ", "")
    file_path = folder_path / f"{safe_custody_id}_{todaysdate}_InitialSealAudit.csv"

    # Define headers
    headers = [
        'Case Number', 'Accession Number', 'Description', 'Code',
        'Parent Container', 'Parent Container Discipline', 'Personnel A', 'Personnel B', 'Notes'
    ]

    # Write CSV
    with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for s in specimens:
            case_number = None
            if s.case_id:
                case = Cases.query.get(s.case_id)
                case_number = getattr(case, 'case_number', None)

            parent_container = None
            if s.container_id:
                container = Containers.query.get(s.container_id)
                parent_container = getattr(container, 'accession_number', None)
                parent_container_discipline = getattr(container, 'discipline', None)

            code = description = None
            if s.specimen_type_id:
                stype = SpecimenTypes.query.get(s.specimen_type_id)
                code = getattr(stype, 'code', None)
                description = getattr(stype, 'name', None)

            writer.writerow([
                case_number or '',
                getattr(s, 'accession_number', ''),
                description or '',
                code or '',
                parent_container or '',
                parent_container_discipline or '',
                '', '', ''
            ])

    flash(f'Manifest Template created!', 'success')

    return redirect(url_for('.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/edit_manifest', methods=['GET'])
@login_required
def edit_manifest(item_id):
    item = table.query.get_or_404(item_id)
    custody_id = item.equipment_id
    safe_custody_id = custody_id.replace("->", "__").replace(" ", "")
    file_path = Path(current_app.static_folder) / 'resource_manifests' / f"{safe_custody_id}_{todaysdate}_InitialSealAudit.csv"

    if not file_path.exists():
        flash("Manifest not found. Please generate it first.", "danger")
        return redirect(url_for('.view', item_id=item_id))

    # Read CSV into rows
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)

    headers = rows[0]
    data_rows = rows[1:]

    initials = current_user.initials if current_user.is_active else "NULL"
    folder, full_filename = str(file_path).rsplit("\\", 1)
    filename = Path(full_filename).stem  # removes .csv

    return render_template(f'edit_manifest.html', item=item, item_id=item_id, headers=headers, data_rows=data_rows, custody_id=custody_id, table_name=table_name, filename = filename, folder = folder, initials = initials)



@blueprint.route(f'/{table_name}/<int:item_id>/view_manifestonly', methods=['GET'])
@login_required
def view_manifestonly(item_id):
    item = table.query.get_or_404(item_id)
    custody_id = item.equipment_id
    safe_custody_id = custody_id.replace("->", "__").replace(" ", "")
    file_path = Path(current_app.static_folder) / 'resource_manifests' / f"{safe_custody_id}_{todaysdate}_InitialSealAudit.csv"

    if not file_path.exists():
        flash("Manifest not found. Please generate it first.", "danger")
        return redirect(url_for('.view', item_id=item_id))

    # Read CSV into rows
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)

    headers = rows[0]
    data_rows = rows[1:]

    initials = current_user.initials if current_user.is_active else "NULL"
    folder, full_filename = str(file_path).rsplit("\\", 1)
    filename = Path(full_filename).stem  # removes .csv

    return render_template(f'edit_manifest.html', 
                           item=item, 
                           item_id=item_id, 
                           headers=headers, 
                           data_rows=data_rows, 
                           custody_id=custody_id, 
                           table_name=table_name, 
                           filename=filename, 
                           folder=folder, 
                           initials=initials,
                           read_only = True)


@blueprint.route(f'/{table_name}/<int:item_id>/save_manifest', methods=['POST'])
@login_required
def save_manifest(item_id):
    custody_id = table.query.get_or_404(item_id).equipment_id
    safe_custody_id = custody_id.replace("->", "__").replace(" ", "")

    file_path = Path(current_app.static_folder) / 'resource_manifests' / f"{safe_custody_id}_{todaysdate}_InitialSealAudit.csv"
    num_rows = int(request.form.get("num_rows", 0))
    num_cols = int(request.form.get("num_cols", 0))

    # Read headers from the CSV (you could also send headers from the form if preferred)
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)

    rows = [headers]
    for i in range(num_rows):
        row = []
        for j in range(num_cols):
            val = request.form.get(f'row-{i}-col-{j}', '')
            row.append(val)
        rows.append(row)

    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    flash("Manifest saved successfully.", "success")
    # return redirect(url_for('.view', item_id=item_id))
    return redirect(url_for('.edit_manifest', item_id=item_id))

@blueprint.route(f'/{table_name}/<string:case_num>/save_manifest', methods= ['GET'])
@login_required
def redirect_by_case_num(case_num):
    case = Cases.query.filter_by(case_number=case_num).first()
    if case:
        return redirect(url_for('cases.view', item_id=case.id, view_only = True))
    else:
        abort(404, description=f"Case number {case_num} not found")
        
# @blueprint.route(f'/{table_name}/<int:item_id>/download_manifest', methods=['GET'])
# @login_required
# def download_manifest(item_id):
#     custody_id = table.query.get_or_404(item_id).equipment_id
#     file_path = Path(current_app.static_folder) / 'resource_manifests' / f"resource_manifest_{custody_id}.csv"

#     if not file_path.exists():
#         flash("Manifest not found in the backend. Please generate it first.", "danger")
#         return redirect(url_for('.view', item_id=item_id))

#     return send_file(
#         file_path,
#         mimetype='text/csv',
#         as_attachment=True,
#         download_name=f"resource_manifest_{custody_id}.csv"
#     )


@blueprint.route(f'/{table_name}/<int:item_id>/update_manifest', methods=['POST'])
@login_required
def update_manifest(item_id):
    custody_id = table.query.get_or_404(item_id).equipment_id
    safe_custody_id = custody_id.replace("->", "__").replace(" ", "")
    file_path = Path(current_app.static_folder) / 'resource_manifests' / f"{safe_custody_id}_{todaysdate}_InitialSealAudit.csv"

    if not file_path.exists():
        flash("Manifest not found. Generating a new one right now.", "success")
        return redirect(url_for(f'{table_name}.generate_manifest_raw', item_id=item_id))

    # Load existing manifest
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)

    # Index existing by accession number for join
    existing_map = {row['Accession Number']: row for row in existing_rows}

    # Fetch fresh data
    specimens = Specimens.query.filter_by(custody=custody_id).all()

    headers = [
        'Accession Number', 'Code', 'Description', 'Discipline',
        'Case Number', 'Parent Container', 'Parent Container Accession Number', 'Notes', 'Personnel A', 'Personnel B'
    ]

    merged_rows = []

    for s in specimens:
        accession_number = getattr(s, 'accession_number', '')
        case_number = ''
        parent_container = ''
        parent_container_discipline = ''

        if s.case_id:
            case = Cases.query.get(s.case_id)
            case_number = getattr(case, 'case_number', '')

        if s.container_id:
            container = Containers.query.get(s.container_id)
            parent_container = getattr(container, 'accession_number', '')
            parent_container_discipline = getattr(container, 'discipline', '')

        code = description = ''
        if s.specimen_type_id:
            stype = SpecimenTypes.query.get(s.specimen_type_id)
            code = getattr(stype, 'code', '')
            description = getattr(stype, 'name', '')

        # Use updated data for fields 0-6, and keep user edits for columns 7-9
        old = existing_map.get(accession_number, {})
        merged_row = [
            accession_number,
            code,
            description,
            getattr(s, 'discipline', ''),
            case_number,
            parent_container,
            parent_container_discipline,
            old.get('Notes', ''),
            old.get('Personnel A', ''),
            old.get('Personnel B', ''),
        ]
        merged_rows.append(merged_row)

    # Save the new merged manifest
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(merged_rows)

    flash("Manifest updated and merged with latest specimen data.", "success")
    return redirect(url_for('.view', item_id=item_id))

