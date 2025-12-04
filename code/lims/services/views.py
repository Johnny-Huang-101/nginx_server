
from lims.models import module_definitions, Services, Divisions, Personnel
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.services.forms import Add, Edit, Approve, Update
from lims.services.functions import get_form_choices

# Set item global variables
item_type = 'Service'  # singular
item_name = 'Services'
table = Services
table_name = 'services'
name = 'id'  # This selects what property is displayed in the flash messages
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
    requires_approval = False
    
    # form = get_form_choices(Add(), item_id=item_id, equipment_type=equipment_type)
    # if request.method == 'POST':
    #     form = get_form_choices(Add(), equipment_type=form.equipment_type.data)

    # If the addition was successful, redirect to the update form for this item
    if form.is_submitted():
        route = module_definitions[form.equipment_type.data][1]

        if "Preventative Maintenance" in form.service_types.data:

            # Flash a message to remind user to update service dates
            flash("Please update the 'Last Service Date' and 'Due Service Date' accordingly.","error")
            kwargs['redirect'] = url_for(f"{route}.update", item_id=form.equipment_id.data)

        if current_user.permissions not in ['Admin','Owner']:
            requires_approval = True

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)
    form = Edit()
    get_form_choices(
        form,
        item_id=item_id,
        equipment_type=item.equipment_type,
        division_id=item.vendor.division_id if item.vendor else None
    )

    if request.method == 'GET':
        form.equipment_type.data = item.equipment_type
        form.equipment_id.data = item.equipment_id
        form.service_types.data = item.service_types
        form.service_date.data = item.service_date
        form.vendor_division.data = item.vendor.division_id 
        form.vendor_id.data = item.vendor_id
        form.issue.data = item.issue
        form.resolution.data = item.resolution
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)

    # Create the form, bind POST data if present
    form = Approve(request.form if request.method == 'POST' else None)

    # Use item values to fill choice-dependent fields
    get_form_choices(
        form,
        item_id=item_id,
        equipment_type=item.equipment_type,
        division_id=item.vendor.division_id if item.vendor else None
    )

    # Pre-fill form with item's existing values (optional but useful)
    if request.method == 'GET':
        form.equipment_type.data = item.equipment_type
        form.equipment_id.data = item.equipment_id
        form.service_types.data = item.service_types
        form.service_date.data = item.service_date
        form.vendor_division.data = item.vendor.division_id 
        form.vendor_id.data = item.vendor_id
        form.issue.data = item.issue
        form.resolution.data = item.resolution
     

    # If form is submitted and valid, run the approval logic
    if form.validate_on_submit():
        return approve_item(
            form, item_id, table, item_type, item_name, table_name, name, **kwargs
        )

    # Default rendering or invalid submission
    return approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)


#   = SelectField('Vendor Division', coerce=int, validate_choice=False, validators=[Optional()])
#      = SelectField('Vendor Personnel', coerce=int, validate_choice=False, validators=[DataRequired()])
#     s = DateField('Service Date', validators=[DataRequired()], render_kw={'type': 'date'})
#      = TextAreaField('Reason')
#      = TextAreaField('Action(s) Taken')
#      = FileField('Attachments', render_kw={'multiple': True})

@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get(item_id)
    form = get_form_choices(Update(), item_id, item.equipment_type, item.vendor.division_id)

    # form = get_form_choices(Update(), item_id, item.equipment_type, item.vendor.agency_id, item.vendor.division_id)

    # If the update was successful, redirect to the update form for this item
    if form.is_submitted() and form.validate():

        if "Preventative Maintenance" in form.service_types.data or item.service_date.date() != form.service_date.data:
            route = module_definitions[form.equipment_type.data][1]

            if "Preventative Maintenance" in form.service_types.data:

                # Flash a message to remind user to update service dates
                flash("Please update the 'Last Service Date' and 'Due Service Date' accordingly.","error")
                kwargs['redirect'] = url_for(f"{route}.update", item_id=form.equipment_id.data)

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
    item = table.query.get_or_404(item_id)

    equipment_type = module_definitions[item.equipment_type]
    # Get the table for the equipment_table using the module_definitions dictionary i.e. the
    # zero index of the list
    equipment_table = equipment_type[0]
    # Get the alias for the equipment type, the 2-index position of the list
    name = equipment_type[2]

    equipment_id = equipment_table.query.get(item.equipment_id)

    alias = f"{getattr(equipment_id, name)} | {item.service_types} | {item.service_date.strftime('%m/%d/%Y')}"
    _attach = attach_items(form, item_id, table, item_name, table_name, name, alias)

    return _attach


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    _view_list = view_items(table, item_name, item_type, table_name, modules=module_definitions)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    equipment_type = module_definitions[item.equipment_type]
    # Get the table for the equipment_table using the module_definitions dictionary i.e. the
    # zero index of the list
    equipment_table = equipment_type[0]
    # Get the alias for the equipment type, the 2-index position of the list
    name = equipment_type[2]

    equipment_id = equipment_table.query.get(item.equipment_id)

    alias = f"{getattr(equipment_id, name)} | {item.service_types} | {item.service_date.strftime('%m/%d/%Y')}"

    _view = view_item(item, alias, item_name, table_name)
    return _view

@blueprint.route(f'/{table_name}/get_equipment_ids/')
@login_required
def get_equipment_ids():

    equipment_type = request.args.get('equipment_type')
    choices = []
    if equipment_type:
        equipment_table = module_definitions[equipment_type][0]
        equipment_name = module_definitions[equipment_type][2]
        items = equipment_table.query
        if items.count():
            choices.append({'id': 0, 'name': 'Please select an equipment ID'})
            for item in items:
                choice = {}
                choice['id'] = item.id
                choice['name'] = getattr(item, equipment_name)
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This equipment type has no equipment'})
    else:
        choices.append({'id': 0, 'name': 'No equipment type selected selected'})

    return jsonify({'choices': choices})

@blueprint.route(f'/{table_name}/get_divisions/')
@login_required
def get_divisions():

    agency_id = request.args.get('agency_id', type=int)

    choices = []
    if agency_id:
        items = Divisions.query.filter_by(agency_id=agency_id, service_provider='Yes')
        if items.count():
            choices.append({'id': 0, 'name': 'Please select a division'})
            for item in items:
                choice = {}
                choice['id'] = item.id
                choice['name'] = item.name
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This agency has no division'})
    else:
        choices.append({'id': 0, 'name': 'No agency selected'})

    return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/get_personnel/')
@login_required
def get_personnel():

    division_id = request.args.get('division_id', type=int)
    print(division_id)

    choices = []
    if division_id:
        items = Personnel.query.filter_by(division_id=division_id, status_id='1')
        if items.count():
            choices.append({'id': 0, 'name': 'Please select a person'})
            for item in items:
                choice = {}
                choice['id'] = item.id
                choice['name'] = item.full_name
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This division has no personnel'})
    else:
        choices.append({'id': 0, 'name': 'No division selected'})

    return jsonify({'choices': choices})