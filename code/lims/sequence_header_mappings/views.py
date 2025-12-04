from lims.models import SequenceHeaderMappings, BatchTemplates
from lims.sequence_header_mappings.forms import Add, Edit, Approve, Update
from lims.sequence_header_mappings.functions import get_form_choices
from lims.forms import Attach, Import
from lims.view_templates.views import *

# Set item variables
item_type = 'Sequence Header Mapping'
item_name = 'Sequence Header Mappings'
table = SequenceHeaderMappings
table_name = 'sequence_header_mappings'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}
# 'ignore_fields': ignore_fields}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    batch_template_id = request.args.get('batch_template_id', type=int)

    form = get_form_choices(Add(), batch_template_id)

    batch_template = BatchTemplates.query.get(batch_template_id)
    df = pd.read_csv(os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template.name}.csv"),
                     encoding="utf-8-sig")

    for field in form:
        if field.name not in ['batch_template_id', 'submit', 'csrf_token']:
            field.choices = [(column, column) for column in df.columns]
            field.choices.insert(0, ("", "---"))

    if request.method == 'POST':
        kwargs['header_list'] = "; ".join(df.columns)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

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
    item = table.query.get(item_id)
    batch_template = BatchTemplates.query.get(item.batch_template_id)
    form = get_form_choices(Update(), batch_template.id)

    # Read csv with correct encoding
    if 'LCQ' in item.batch_template.name:
        df = pd.read_csv(os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template.name}.csv"),
                         encoding='utf-8-sig')
    elif 'GCET' in item.batch_template.name:
        df = pd.read_csv(os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template.name}.csv"),
                         encoding='utf-8-sig')
    else:
        df = pd.read_csv(os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template.name}.csv"),
                         encoding='utf-8-sig')

    for field in form:
        if field.name not in ['batch_template_id', 'submit', 'csrf_token']:
            field.choices = [(column, column) for column in df.columns]
            field.choices.insert(0, ("", "---"))

    if request.method == 'POST':
        kwargs['header_list'] = "; ".join(df.columns)

    elif request.method == 'GET':
        for field in form:
            if field.name not in ['batch_template_id', 'submit', 'csrf_token']:
                field.data = getattr(item, field.name)

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name,
                          locking=False, **kwargs)

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
