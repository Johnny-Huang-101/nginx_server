from lims.models import *
from lims.forms import Attach, Import
from lims.view_templates.views import *

from lims.bookings.forms import Add, Edit, Approve, Update
from lims.bookings.functions import get_form_choices, process_form, calculate_time


# Set item global variables
item_type = 'Booking'
item_name = 'Bookings'
table = Bookings
table_name = 'bookings'
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
# Filesystem path
path = None

@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    case_id = request.args.get('case_id', type=int)
    form = get_form_choices(Add(), case_id)
    alias = None

    if request.method == 'GET':
        form.user_id.data = current_user.id

    elif request.method == 'POST':

        # Set the alias manually for alerts
        case = Cases.query.get(form.case_id.data)
        purpose = BookingPurposes.query.get(form.purpose_id.data)
        alias = f"Booking - {case.case_number}"
        if purpose:
            alias += f" ({purpose.name})"

        # Calculates total_testifying_time and total_work_time
        kwargs.update(process_form(form))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                    alias=alias, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    case_id = request.args.get('item_id')
    form = get_form_choices(Edit(), case_id)
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    case_id = request.args.get('item_id')
    form = get_form_choices(Approve(), case_id)
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    kwargs['users'] = Users.query
    item = table.query.get(item_id)
    case_id = item.case.id

    form = get_form_choices(Update(), case_id=case_id)

    alias = f"Booking - {item.case.case_number}"
    if item.purpose:
        alias += f" ({item.purpose.name})"
    # Only allow booking creator and admin/owner to edit booking entry
    if current_user.initials != item.created_by and current_user.permissions not in ['Admin', 'Owner']:
        return abort(403)

    if request.method == 'POST':

        # Calculates total_testifying_time and total_work_time
        kwargs.update(process_form(form))

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name,
                          alias=alias, **kwargs)

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
    item = table.query.get(item_id)
    if current_user.initials != item.created_by and current_user.permissions not in ['Admin', 'Owner']:
        return abort(403)
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
    item = table.query.get(item_id)
    alias = f"{item.case.case_number} | {item.purpose.name}"
    _attach = attach_items(form, item_id, table, item_name, table_name, name, alias=alias)

    return _attach

@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    # Query all Personnel with their associated Users
    personnel_records = Personnel.query.options(db.joinedload(Personnel.personnel_users)).all()

    # Create a dictionary mapping Personnel.id to the first associated Users.initials
    personnel_initials = {
        record.id: record.personnel_users[0].initials for record in personnel_records if record.personnel_users
    }

    kwargs = {'booking_info_provider': BookingInformationProvider,
              'booking_info_provided': BookingInformationProvided,
              'others_present': Personnel,
              'personnel_initials': personnel_initials,
              }

    _view_list = view_items(table, item_name, item_type, table_name, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    # Pass in information provider and information provided models in kwargs
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)
    kwargs['provided_by'] = BookingInformationProvider
    kwargs['information_provided'] = BookingInformationProvided
    kwargs['others_present'] = Personnel

    alias = f"{item.case.case_number}"
    if item.purpose:
        alias += f" ({item.purpose.name})"

    _view = view_item(item, alias, item_name, table_name, view_only=False, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/get_personnel/')
@login_required
def get_personnel_json():

    agency_id = request.args.get('agency_id', type=int)
    print('agency_id: ',agency_id)
    choices = []
    if agency_id:
        items = Personnel.query.filter_by(agency_id=agency_id)
        if items.count():
            choices.append({'id': 0, 'name': 'Please select a person'})
            for item in items:
                choice = {}
                choice['id'] = item.id
                div_name = item.division.name if item.division else 'No Division'
                choice['name'] = f"{div_name} - {item.full_name}"
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This agency has no personnel'})
    else:
        choices.append({'id': 0, 'name': 'No agency selected'})

    return jsonify({'choices': choices})

@blueprint.route(f'/{table_name}/calculate_times/')
@login_required
def calculate_times():
    
    start_dt  = (request.args.get('date')
                or request.args.get('start_datetime'))
    finish_dt = request.args.get('finish_datetime')
    drive_duration = request.args.get('drive_time', default="00:00")
    excluded_duration = request.args.get('excluded_time', default="00:00")
    waiting_duration  = request.args.get('waiting_time', default="00:00")

    total_work_time_str, total_testifying_time_str = calculate_time(
        start_dt, finish_dt, drive_duration, excluded_duration, waiting_duration
    )

    return jsonify(
        total_work_time=total_work_time_str,
        total_testifying_time=total_testifying_time_str
    )

