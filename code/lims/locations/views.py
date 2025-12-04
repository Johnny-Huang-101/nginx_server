import lims
from lims.locations.functions import get_location_choices
from lims.models import *
from lims.agencies.forms import Add, Edit, Approve, Update
from lims.forms import Attach, Import
from lims.view_templates.views import *

# Set item global variables
item_type = 'Location'
item_name = 'Locations'
table = Locations
table_name = 'locations'
name = 'id'  # This selects what property is displayed in the flash messages
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
    form = Add()
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
    form = Update()
    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _update


# SWEEP #
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


# END SWEEP #
@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    _view_list = view_items(table, item_name, item_type, table_name)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)
    alias = f"{getattr(item, name)} ({item.abbreviation})"

    mods = Modifications.query.filter_by(record_id=str(item.id), table_name=item_name). \
        order_by(Modifications.submitted_date.desc())

    return render_template(
        f'{table_name}/view.html',
        item=item,
        item_name=item_name,
        item_type=item_type,
        table_name=table_name,
        alias=alias,
        mods=mods,
    )


@blueprint.route(f'/{table_name}/get_location_ids/', methods=['GET', 'POST'])
@login_required
def get_location_ids():
    location_table = request.args.get('location_table')
    print(f'LOCATION TABLE: {location_table}')
    response = get_location_choices(location_table, store_as='id')

    return response


@blueprint.route(f'/{table_name}/initialize_locations/', methods=['GET', 'POST'])
@login_required
def initialize_locations():
    # Find item (resource)
    # Find location
    # Assign location_table and location strings to item (resource)

    # KEEP FOR JS POPULATING OF FORM

    assigned_location_table = None
    assigned_item_table = None

    locations = [item for item in table.query]

    for item in locations:
        for cls in db.Model.__subclasses__():
            # cls is the table object
            if cls.__tablename__ == item.location_table:
                assigned_location_table = cls
            if cls.__tablename__ == item.item_table:
                assigned_item_table = cls
        if assigned_location_table is not None and assigned_item_table is not None:
            print(f'ITEM ID: {item.id}')
            print(f'RESOURCE ITEM: {assigned_item_table.query.get(item.item_id)}')
            print(f'LOCATION TYPE: {item.location_table}')
            print(f'LOCATION ID: {item.location_id}')
            resource_item = assigned_item_table.query.get(item.item_id)
            resource_item.location_type = item.location_table
            resource_item.location = item.location_id

    db.session.commit()

    return redirect(url_for(f'{table_name}.view_list'))


@blueprint.route(f'/{table_name}/get_location_data/', methods=['GET', 'POST'])
@login_required
def get_location_data():
    # Used to retain location information in resource update function

    # Initialize relevant variables
    item = None
    location_type = None
    location_id = None

    # Get relevant variables
    item_table = request.args.get('table')
    item_id_args = request.args.get('id')
    item_id = item_id_args if item_id_args != 'add' else None

    # Get item
    if item_id:
        for cls in db.Model.__subclasses__():
            if cls.__tablename__ == item_table:
                item = cls.query.get(item_id)
                print('item: ',item)

    # Set relevant variables if item exists
    if item is not None:
        print('initial location_type: ',item.location_type)
        # if item.location_type:
        #     location_type = item.location_type.title()
        # else:
        lookup_location = Locations.query.filter(
            Locations.item_table == item_table,
            Locations.item_id == item_id
        ).first()
        print('lookup_location: ', lookup_location)
        if lookup_location:
            location_type = lookup_location.location_table
            location_id = lookup_location.location_id

        if location_type[0].islower():
            location_type = location_type.replace('_',' ').title()

    return jsonify({'location_type': location_type, 'location_id': location_id})
