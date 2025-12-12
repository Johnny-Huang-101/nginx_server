# General Imports
import qrcode
from sqlalchemy import and_
# Flask Imports
from flask import request, Blueprint, render_template, jsonify, session, redirect, url_for, abort, current_app
from flask_login import login_required, current_user
# Application Imports
from lims import db
from lims.labels import fields_dict, print_label
from lims.locations.functions import set_location, models_iter, location_dict, get_location_display
from lims.models import BatchConstituents, Batches, SolventsAndReagents, Users, Locations, SolutionTypes, AssayConstituents
from lims.view_templates.views import *
from lims.solvents_and_reagents.forms import Add, Update, PrintLabel
from lims.models import SolventsAndReagents
from lims.solvents_and_reagents.forms import Add, Edit, Approve, Update
from lims.solvents_and_reagents.functions import get_form_choices
from lims.forms import Attach, Import
from lims.view_templates.views import *
import base64

# Set item global variables
item_type = 'Solvent or Reagent'
item_name = 'Purchased Reagents'  # ie display name in navbar, Modifications and Attachments tables
table = SolventsAndReagents
table_name = 'solvents_and_reagents'
name = 'name'  # This selects what property is displayed in the flash messages
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

        # Initialize show_modal
        show_modal = False

        set_location(table_name, None, form.location_table.data, form.location_id.data)
        form.name.data = AssayConstituents.query.get(form.constituent.data).name

        # Add new item
        add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

        # Get most recently added item
        item_id = table.query.order_by(table.id.desc()).first().id
        new_item = table.query.get(item_id)

        # Check if DI water was added
        if new_item.const.name == 'Deionized Water':
            show_modal = True

        # Redirect to most recently added item
        return redirect(url_for(f'{table_name}.view', item_id=item_id, show_modal=show_modal))

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
    form = get_form_choices(Update())

    if form.is_submitted() and form.validate():
        set_location(table_name, item_id, form.location_table.data, form.location_id.data)
        form.name.data = AssayConstituents.query.get(form.constituent.data).name

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = {'locations': Locations.query.all(), 'models': models_iter, 'location_dict': location_dict}

    thirty_days = datetime.today() + timedelta(days=30)

    thirty_day_query = table.query.filter(
        table.in_use == 1,
        table.exp_date <= thirty_days,
        table.exp_date > datetime.now()
        ).count()
    
    one_day_query = table.query.filter(
        table.in_use == 1,
        table.exp_date <= datetime.today()
        ).count()


    warning_alerts = [
        (url_for(f'{table_name}.view_list', query='thirty_day_query'), thirty_day_query,
         Markup('in use with <b>retest dates within 30 days</b>')),
    ]

    danger_alerts = [
        (url_for(f'{table_name}.view_list', query='one_day_query'), one_day_query,
         Markup('in use <b>retest dates that have passed or are within 1 day</b>')),
    ]

    _view_list = view_items(table, item_name, item_type, table_name, 
                            warning_alerts=warning_alerts, danger_alerts=danger_alerts, **kwargs)
    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)
    kwargs = {}

    # Get all batches using prepared standard/reagent
    batch_ids = [const.batch_id for const in BatchConstituents.query.filter_by(reagent_id=item_id).all()]

    if batch_ids:
        kwargs['batches'] = Batches.query.filter(Batches.id.in_(batch_ids)).all()
    else:
        kwargs['batches'] = []

    # Check for show_modal arg
    show_modal = request.args.get('show_modal')

    form = PrintLabel()
    
    kwargs['location_display'] = get_location_display(table_name, item.id)

    # Assign show_modal kwarg based on arg, controls if DI water modal shown
    if show_modal:
        kwargs['show_modal'] = True
    else:
        kwargs['show_modal'] = False
    
    if form.is_submitted() and form.validate():
        return jsonify([(None, None, None, None, url_for(f'{table_name}.print_labels', item_id=item_id, amount=form.amount.data, _external = True))])
        # return redirect(url_for(f'{table_name}.print_labels', item_id=item_id, amount=form.amount.data))

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name, form=form, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/print_label', methods=['GET', 'POST'])
@login_required
def print_labels(item_id):
    # Get current item
    item = SolventsAndReagents.query.get(item_id)

    amount = int(request.args.get('amount'))

    # Set printer to reagent printer
    printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 – Reagent Prep'

    # Get label_attributes dict
    label_attributes = fields_dict['reagent_lg']

    print(f"PRINTING LABELS {label_attributes}")


    attributes_list = []

    # Set relevant label_attributes
    label_attributes['REAGENT'] = item.const.name
    if item.description is not None:
        label_attributes['DESCRIPTION'] = item.description
    else:
        label_attributes['DESCRIPTION'] = ''
    label_attributes['LOT_NUM'] = item.lot
    if item.recd_date is not None:
        label_attributes['PREP_DATE'] = item.recd_date.strftime('%m/%d/%Y')
    else:
        label_attributes['PREP_DATE'] = ''
    if item.exp_date is not None:
        label_attributes['EXP_DATE'] = item.exp_date.strftime('%m/%d/%Y')
    else:
        label_attributes['EXP_DATE'] = ''
    if item.recd_by is not None:
        label_attributes['PREP_BY'] = item.solv_receiver.initials
    else:
        label_attributes['PREP_BY'] = ''

    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'{table_name}{item.id}.png')
    qrcode.make(f'solvents_and_reagents: {item.id}').save(qr_path)

    with open(qr_path, "rb") as qr_file:
            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

    label_attributes['QR'] = qr_encoded
    label_attributes['DATE_TEXT'] = "Rec'd Date:"
    label_attributes['BY_TEXT'] = "Rec'd By:"

    for i in range(0, amount):
        attributes_list.append(label_attributes.copy())

    # Print label
    # print_label(printer, attributes_list)

    # print(f'DONE PRINT LABEL HERE')

    # return redirect(url_for(f'{table_name}.view', item_id=item.id))
    print(f"PRINTING LABELS {attributes_list}")

    return jsonify([(attributes_list, printer, None, None, url_for(f'{table_name}.view', item_id=item.id, True))])


@blueprint.route(f'/{table_name}/<int:item_id>/update_in_use', methods=['GET', 'POST'])
@login_required
def update_in_use(item_id):
    item = table.query.get(item_id)

    if item.in_use:
        item.in_use = False
    else:
        item.in_use = True

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))
