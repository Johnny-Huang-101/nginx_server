from fileinput import filename
from lims.models import *
from lims.forms import Attach, Import
from lims.view_templates.views import *
import os, re
from lims.batch_records.forms import Add, Edit, Approve, Update
from lims.batch_records.functions import get_form_choices
import os, re
from flask import current_app
import requests  # assuming external API is HTTP based

# Set item global variables
item_type = 'Batch Records'
item_name = 'Batch Records'
table = BatchRecords
table_name = 'batch_records'
name = 'file_name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Filesystem path
path = os.path.join(current_app.config['FILE_SYSTEM'], 'batch_records')
os.makedirs(path, exist_ok=True)

# Create blueprint
blueprint = Blueprint(table_name, __name__)




@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

    # If the add batch record form is accessed through the batches/view route
    # set the batch_id form field to the batch_id
    batch_id = request.args.get('item_id', type=int)
    kwargs['redirect'] = request.args.get('redirect_url')
    if batch_id:
        kwargs['batch_id'] = batch_id

    if request.method == 'POST':
        # Get list of files from the form.
        files = request.files.to_dict(flat=False)
        # Get the batch from the form data.
        batch_id = form.batch_id.data
        batch = Batches.query.get(batch_id)
        # Get the folders in the batch_records folders
        batch_records = [Path(folder).name for folder in glob.glob(f"{path}\*")]
        # Generate path by concatenating the batch record path with the batch_id
        record_path = os.path.join(path, batch.batch_id)
        # if a folder does exist for
        if batch_id not in batch_records:
            os.makedirs(record_path, exist_ok=True)

        # iterate through each file from the form
        for file in files['file_name']:
            # Get the file's filename
            file_name = file.filename
            # Get the file's extension
            ext = file_name.split(".", maxsplit=1)[1]
            # Get the files title (without .ext) and remove the batch_id
            title = file_name.split(".", maxsplit=1)[0].replace(batch.batch_id, "").strip()

            # if the file name is only the batch_id i.e., LCQD-BL_202401011234.ext
            # then set the title to the extension
            if not title:
                title = ext[0:]

            kwargs['title'] = title
            kwargs['file_name'] = file_name
            kwargs['file_path'] = os.path.join(record_path, file.filename)
            kwargs['file_type'] = ext.upper()
            # kwargs['file_path'] = os.path.join(
            #     current_app.root_path,
            #     'static/filesystem/batch_records',
            #     f"{filename}_{datetime.now().strftime('%Y%m%d%H%M')}.{ext}")
            file.save(kwargs['file_path'])
            if files['file_name'][-1] != file:
                add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, exit_route=url_for('batches.view',item_id=batch_id), **kwargs)

    return _add
 
 



@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Edit())
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Approve())
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Update())
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
    item = table.query.get_or_404(item_id)
    redirect_url = url_for('batches.view', item_id=item.batch_id)

    # --- Soft delete the file on disk (rename only) ---
    if item.file_name and item.batch_id is not None:
        base_dir = os.path.join(
            current_app.static_folder, "filesystem", "batch_records", str(item.batch.batch_id)
        )
        original_path = os.path.join(base_dir, item.file_name)

        # Split out name and extension
        name_root, ext = os.path.splitext(item.file_name or "")
        # Remove any existing " [Removed]" or " [Removed](n)" suffix
        cleaned_root = re.sub(r' \[removed\](\(\d+\))?$', '', name_root, flags=re.IGNORECASE)

        # Propose new name
        new_root = f"{cleaned_root} [Removed]"
        candidate = f"{new_root}{ext}"
        new_path = os.path.join(base_dir, candidate)

        # Ensure uniqueness if already exists
        i = 1
        while os.path.exists(new_path):
            candidate = f"{new_root}({i}){ext}"
            new_path = os.path.join(base_dir, candidate)
            i += 1

        # Rename if the file exists
        if os.path.isfile(original_path):
            os.replace(original_path, new_path)

    # --- Always delete the DB row ---
    return delete_item(
        form, item_id, table, table_name, item_name, name,
        admin_only=False, redirect_url=redirect_url
    )



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

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


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

@blueprint.route(f'/{table_name}/<int:item_id>/export_records', methods=['GET'])
def export_records(item_id):
    """

    Export any batch records as a .zip folder which will be sent to the browser's
    downloads.

    A <batch_id> folder will be created in the temp folder of the filesystem. Any
    batch records will be added to this folder which will then be zipped and sent
    to the browser. The original folder will be deleted but the .zip file will remain.

    To prevent build-up of .zip files. When this function is run, it will delete any
    .zip files in the temp folder.

    Parameters
    ----------
    item_id

    Returns
    -------

    .zip file sent to browser


    """

    # Remove any zipped folders in the temp folder of the file system.
    # When exporting the .zip folder.
    temp_path = os.path.join(current_app.config['FILE_SYSTEM'], 'temp')
    tmp_zip_folders = glob.glob(f"{temp_path}\*.zip")
    for folder in tmp_zip_folders:
        os.remove(folder)
    # tmp_folders = glob.glob(f"{temp_path}\*")
    # print(tmp_folders)
    # for folder in tmp_folders:
    #     shutil.rmtree(folder)

    # Get the batch_id and create a folder in the temp path, getting the folder's path
    item = Batches.query.get(item_id)
    batch_id = item.batch_id
    output_path = os.path.join(temp_path, batch_id)
    # Get the batch records folder, iterating through the files and copying them to the
    # batch_id folder in the temp folder.
    batch_records = os.path.join(current_app.config['FILE_SYSTEM'], 'batch_records', batch_id)
    files = glob.glob(f"{batch_records}\*")
    if files:
        # os.makedirs(output_path, exist_ok=True)
        shutil.copytree(batch_records, output_path)

    # Zip file
    shutil.make_archive(output_path, 'zip', output_path)
    # Delete the
    shutil.rmtree(output_path)
    # Send .zip file to the downloads folder for the browser
    return send_file(f"{output_path}.zip",
             as_attachment=True,
             download_name=f'{batch_id}.zip')


