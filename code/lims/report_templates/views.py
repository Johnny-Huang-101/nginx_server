
from lims.models import ReportTemplates
from lims.forms import Attach, Import
from lims.report_templates.forms import Add, Edit, Approve, Update
from lims.view_templates.views import *
from lims.report_templates.functions import process_form
import os
import docx2pdf
import pythoncom
import glob
from datetime import datetime
import pandas as pd
import numpy as np
import re

# Set item variables
item_type = 'Report Template'
item_name = 'Report Templates'
table = ReportTemplates
table_name = 'report_templates'
name = 'name'
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
kwargs = {'template': template,
          'redirect': redirect_to}

path = os.path.join(app.config['FILE_SYSTEM'], table_name)

blueprint = Blueprint('report_templates', __name__)


##### ADD #####

@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    form = Add()

    if request.method == 'POST':
        process_form(path, form)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


##### EDIT #####
@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    form = Edit()
    if request.method == 'POST':
        process_form(path, form, item_id)
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


##### APPROVE #####
@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    form = Approve()
    if request.method == 'POST':
        process_form(path, form, item_id)
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


##### UPDATE #####
@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    form = Update()
    if request.method == 'POST':
        process_form(path, form, item_id)
    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _update

##### UNLOCK #####
@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):

    _unlock = unlock_item(item_id, table, name)

    return _unlock

@blueprint.route(f'/{table_name}/<int:item_id>/unlock', methods=['GET', 'POST'])
@login_required
def unlock(item_id):

    _unlock = unlock_item(item_id, table, name)

    return _unlock

##### REVERT CHANGES #####
@blueprint.route(f'/{table_name}/revert_changes/')
@login_required
def revert_changes():

    item_id = request.args.get('item_id', 0, type=int)
    field = request.args.get('field_name', type=str)
    field_value = request.args.get('field_value', type=str)
    field_type = request.args.get('field_type', type=str)
    multiple = request.args.get('multiple', type=str)

    print(field)
    print(field_value)
    print(field_type)
    print(multiple)

    _revert_changes = revert_item_changes(item_id, field, field_value, item_name, field_type, multiple)

    return _revert_changes


@blueprint.route(f'/{table_name}/<int:item_id>/remove', methods=['GET', 'POST'])
@login_required
def remove(item_id):
    item = table.query.get(item_id)

    if item and item.name:
        template_dir = Path("static/filesystem/report_templates")
        file_path = template_dir / item.name  # assumes item.name includes extension

        if file_path.exists():
            base, ext = os.path.splitext(file_path)
            directory = os.path.dirname(base)
            filename = os.path.basename(base)

            # Remove existing [removed] or [removed](n)
            cleaned_filename = re.sub(r' \[removed\](\(\d+\))?$', '', filename)

            # Start with base removed name
            new_filename = f"{cleaned_filename} [removed]{ext}"
            new_path = os.path.join(directory, new_filename)

            # Only increment if that exact name already exists
            count = 1
            while os.path.exists(new_path):
                new_filename = f"{cleaned_filename} [removed]({count}){ext}"
                new_path = os.path.join(directory, new_filename)
                count += 1

            os.rename(file_path, new_path)

    # Run your existing remove logic
    return remove_item(item_id, table, table_name, item_name, name)

EXTS = [".docx", ".pdf"]
INACTIVE_RE = re.compile(r' \[Inactive\]$', re.IGNORECASE)

def _base_dir() -> Path:
    # ABSOLUTE path: <app_root>/static/filesystem/report_templates
    return Path(current_app.root_path) / "static" / "filesystem" / "report_templates"

def _to_stem(name: str) -> str:
    # Treat item.name as a stem; if it accidentally has an extension, strip it
    for ext in EXTS:
        if name.lower().endswith(ext):
            return name[:-len(ext)]
    return name

def _apply_inactive(stem: str, make_inactive: bool) -> str:
    clean = INACTIVE_RE.sub('', stem)     # remove existing [Inactive] if present
    return f"{clean} [Inactive]" if make_inactive else clean

def _rename_both(abs_dir: Path, old_stem: str, new_stem: str):
    found_any = False
    for ext in EXTS:
        src = abs_dir / f"{old_stem}{ext}"
        if src.exists():
            dst = abs_dir / f"{new_stem}{ext}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)  # overwrite if exists
            found_any = True
    if not found_any:
        # Fail loudly so you see the EXACT absolute paths we tried
        tried = ", ".join(str(abs_dir / f"{old_stem}{ext}") for ext in EXTS)
        abort(400, description=f"No artifacts found to rename. Looked for: {tried}")

@blueprint.route(f'/{table_name}/<int:item_id>/set_inactive')
@login_required
def set_inactive(item_id):
    item = table.query.get_or_404(item_id)
    item.status_id = 2  # Inactive
    db.session.commit()

    if item and item.name:
        abs_dir = _base_dir()
        current_stem = _to_stem(item.name)
        target_stem  = _apply_inactive(current_stem, make_inactive=True)
        _rename_both(abs_dir, current_stem, target_stem)
        item.name = target_stem        # keep DB stem in sync
        db.session.commit()

    return redirect(url_for('report_templates.view', item_id=item_id))

@blueprint.route(f'/{table_name}/<int:item_id>/set_active')
@login_required
def set_active(item_id):
    item = table.query.get_or_404(item_id)
    item.status_id = 1  # Active
    db.session.commit()

    if item and item.name:
        abs_dir = _base_dir()
        current_stem = _to_stem(item.name)
        target_stem  = _apply_inactive(current_stem, make_inactive=False)
        _rename_both(abs_dir, current_stem, target_stem)
        item.name = target_stem
        db.session.commit()

    return redirect(url_for('report_templates.view', item_id=item_id))

##### APPROVE REMOVE #####
@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):

    _approve_remove = approve_remove_item(item_id, table, table_name, item_name, name)

    return _approve_remove


##### REJECT REMOVE #####
@blueprint.route(f'/{table_name}/<int:item_id>/reject_remove', methods=['GET', 'POST'])
@login_required
def reject_remove(item_id):

    _reject_remove = reject_remove_item(item_id, table, table_name, item_name, name)

    return _reject_remove

##### RESTORE #####
@blueprint.route(f'/{table_name}/<int:item_id>/restore', methods=['GET', 'POST'])
@login_required
def restore(item_id):

    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


##### DELETE #####
@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    item = table.query.get(item_id)
    files = glob.glob(f"{path}\{item.name}*")

    for file in files:
        os.remove(file)

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


#### DELETE ALL #####
@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():

    files = glob.glob(f"{path}\*")
    for file in files:
        os.remove(file)
    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items

@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    _import = import_items(form, table, table_name, item_name)

    return _import


##### VIEW ALL #####

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


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():

    _export = export_items(table)

    return _export

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    query = request.args.get('query')
    _view_list = view_items(table, item_name, item_type, table_name, query=query)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name)
    return _view
