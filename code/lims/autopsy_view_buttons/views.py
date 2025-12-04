from lims.models import AutopsyViewButtons, SpecimenTypes
from lims.autopsy_view_buttons.forms import Add, Edit, Approve, Update
from lims.autopsy_view_buttons.functions import get_form_choices
from lims.forms import Attach, Import
from lims.view_templates.views import *

# Set item global variables
item_type = 'Autopsy View Button'
item_name = 'Autopsy View Buttons'
table = AutopsyViewButtons
table_name = 'autopsy_view_buttons'
name = 'button'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'view'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

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
    form = get_form_choices(Update())

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

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    kwargs = default_kwargs.copy()
    items = table.query
    kwargs['specimen_table'] = SpecimenTypes

    _view_list = view_items(table, item_name, item_type, table_name, items=items, add_item_button=False, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    kwargs = {}
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"
    kwargs['specimen_table'] = SpecimenTypes

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/get_specimen_types', methods=['GET'])
@login_required
def get_specimen_types():

    # Initialize choices array
    choices = []
    # Get all specimen types
    items = SpecimenTypes.query.all()

    # Initialize discipline
    discipline = None
    # Get button clicked from request
    button = request.args.get('button')

    # Determine button clicked and set discipline
    if button == 'Toxicology (N)':
        discipline = 'Toxicology'
    elif button in ('Physical (N)', 'Physical (SA)', 'Physical (Bundle)'):
        discipline = 'Physical'
    elif button in ('Histology (T)', 'Histology (S)'):
        discipline = 'Histology'

    # Refine items for only specimen types in with specified discipline in discipline column
    if discipline is not None:
        items = [item for item in items if item.discipline is not None and discipline in item.discipline]
        # items = SpecimenTypes.query.filter(discipline=discipline).all()

    # Set choices array with choice dictionaries
    if len(items) != 0:
        for item in items:
            choice = {}
            choice['id'] = int(item.id)
            choice['name'] = item.name
            choices.append(choice)
    else:
        choices.append({'id': "", 'name': 'This discipline has no specimen types'})

    return jsonify({'choices': choices, 'discipline': discipline})


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments
