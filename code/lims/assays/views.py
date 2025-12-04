
from lims.models import *
from lims.forms import Attach, Import
from lims.view_templates.views import *

from lims.assays.forms import Add, Edit, Approve, Update
from lims.assays.functions import get_form_choices, get_order, update_counts

# Set item global variables
item_type = 'Assay'
item_name = 'Assays'
table = Assays
table_name = 'assays'
name = 'assay_name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Filesystem path
path = None
# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

    kwargs['orders'] = get_order()

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Edit())
    kwargs['orders'] = get_order()

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Approve())
    kwargs['orders'] = get_order()

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Update())
    kwargs['orders'] = get_order()

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

    # Update the compound_counts, component_counts, test_counts and batch_counts
    for assay in table.query:
        update_counts(assay.id)

    _view_list = view_items(table, item_name, item_type, table_name, order_by=['status_id', 'assay_order'])

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{item.assay_name} | {item.status.name}"

    # Update the compound_counts, component_counts, test_counts and batch_counts
    update_counts(item_id)
    # Assay constituents
    constituent_ids = []
    default_constituents = DefaultAssayConstituents.query.filter_by(assay_id=item_id).first()
    if default_constituents:
        constituent_ids = default_constituents.constituent_id.split(", ")
    print(constituent_ids)
    constituents = AssayConstituents.query.filter(AssayConstituents.id.in_(constituent_ids))
    # Get assay scope
    scope = Scope.query.join(Components).filter(Scope.assay_id == item_id).order_by(Components.name)
    # Get batches for display
    batches = Batches.query.filter_by(assay_id=item_id).order_by(Batches.extraction_date.desc())
    # Get the current year to determine tests and batches to date
    year = datetime.now().year
    tests_to_date = Tests.query.join(Batches)\
        .filter_by(assay_id=item_id)\
        .filter(Batches.extraction_date >= datetime(year, 1, 1))\
        .count()
    batches_to_date = Batches.query.filter_by(assay_id=item_id).filter(Batches.extraction_date >= datetime(year, 1, 1)).count()

    return view_item(item, alias, item_name, table_name,
                     constituents=constituents,scope=scope, batches=batches, year=year,
                     batches_to_date=batches_to_date, tests_to_date=tests_to_date)


@blueprint.route(f'/{table_name}/get_batch_templates/', methods=['GET', 'POST'])
@login_required
def get_batch_templates():
    """

    Returns
    -------

    A list of batch templates that are assigned to the selected instrument

    """

    instrument_id = request.args.get('instrument_id', type=int)
    items = BatchTemplates.query.filter_by(instrument_id=instrument_id).all()
    print(items)
    lst = []

    if len(items) != 0:
        lst.append({'id': 0, 'name': '---'})
        for item in items:
            dict = {}
            dict['id'] = item.id
            dict['name'] = item.name
            lst.append(dict)

    else:
        lst.append({'id': 0, 'name': "---"})

    print(lst)
    return jsonify({'batch_templates': lst})


# @blueprint.route(f'/{table_name}/<int:item_id>/in_use', methods=['GET', 'POST'])
# def in_use(item_id):
#     # Used to 'retire' assays
#     item = Assays.query.get(item_id)
#
#     item.in_use = not item.in_use
#     db.session.commit()
#
#     return redirect(url_for(f'{table_name}.view_list'))
