
from lims.models import *
from lims.disseminations.forms import Add, Edit, Approve, Update
from lims.forms import Import, Attach
from lims.view_templates.views import *

# Set item global variables
item_type = 'Dissemination'
item_name = 'Disseminations'
table = Disseminations
table_name = 'disseminations'
name = 'id'  # This selects what property is displayed in the flash messages
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

    form = Add()
    kwargs = default_kwargs.copy()

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


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

    kwargs = {}
    pdfs = []
    print(current_app.root_path)
    report_path = os.path.join(current_app.root_path, 'static/filesystem', 'reports')
    if os.path.exists(report_path):
        pdfs = [x.split(".")[0] for x in os.listdir(report_path)]
        kwargs['pdfs'] = pdfs

    _view_list = view_items(table, item_name, item_type, table_name, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name)
    return _view
