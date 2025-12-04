import qrcode
from sqlalchemy import and_

from lims.labels import fields_dict
from lims.models import BatchConstituents, Batches, CurrentAssayConstituents, BatchRecords, SequenceHeaderMappings
from lims.batch_constituents.forms import Add, Edit, Approve, Update
from lims.view_templates.views import *
from lims.batch_constituents.functions import get_form_choices
from lims.forms import Attach, Import
import base64

# Set item global variables
item_type = 'Batch Constituents'
item_name = 'Batch Constituents'
table = BatchConstituents
table_name = 'batch_constituents'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = ['instrument_id', 'batch_id']  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
kwargs = {'template': template}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


##### ADD #####
@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():

    batch_id = request.args.get('item_id', type=int)
    form = get_form_choices(Add(), batch_id)

    kwargs['items'] = []
    if batch_id is not None:
        batch = Batches.query.get_or_404(batch_id)
        kwargs['items'] = CurrentAssayConstituents.query.filter_by(assay_id=batch.assay_id, constituent_status=True)
        # CurrentAssayConstituents NOT USED but references/imports left in this file for now

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            batch = Batches.query.get(form.batch_id.data)
            batch.instrument_id = form.instrument_id.data
            batch.template_id = form.batch_template_id.data
            for constituent in form.constituent_id.data:
                kwargs['constituent_id'] = constituent
                if constituent != form.constituent_id.data[-1]:
                    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/edit', methods=['GET', 'POST'])
@login_required
def edit():

    batch_id = request.args.get('item_id', type=int)
    form = get_form_choices(Edit(), batch_id)

    kwargs['items'] = []
    if batch_id is not None:
        batch = Batches.query.get_or_404(batch_id)
        kwargs['items'] = CurrentAssayConstituents.query.filter_by(assay_id=batch.assay_id, constituent_status=True)

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            batch = Batches.query.get(form.batch_id.data)
            batch.instrument_id = form.instrument_id.data
            batch.template_id = form.batch_template_id.data
            for constituent in form.constituent_id.data:
                kwargs['constituent_id'] = constituent
                if constituent != form.constituent_id.data[-1]:
                    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _edit = edit_item(form, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/approve', methods=['GET', 'POST'])
@login_required
def approve():

    batch_id = request.args.get('item_id', type=int)
    form = get_form_choices(Approve(), batch_id)

    kwargs['items'] = []
    if batch_id is not None:
        batch = Batches.query.get_or_404(batch_id)
        kwargs['items'] = CurrentAssayConstituents.query.filter_by(assay_id=batch.assay_id, constituent_status=True)

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            batch = Batches.query.get(form.batch_id.data)
            batch.instrument_id = form.instrument_id.data
            batch.template_id = form.batch_template_id.data
            for constituent in form.constituent_id.data:
                kwargs['constituent_id'] = constituent
                if constituent != form.constituent_id.data[-1]:
                    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _approve = approve_item(form, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/update', methods=['GET', 'POST'])
@login_required
def update():

    batch_id = request.args.get('item_id', type=int)
    form = get_form_choices(Update(), batch_id)

    kwargs['items'] = []
    if batch_id is not None:
        batch = Batches.query.get_or_404(batch_id)
        kwargs['items'] = CurrentAssayConstituents.query.filter_by(assay_id=batch.assay_id, constituent_status=True)

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            batch = Batches.query.get(form.batch_id.data)
            batch.instrument_id = form.instrument_id.data
            batch.template_id = form.batch_template_id.data
            for constituent in form.constituent_id.data:
                kwargs['constituent_id'] = constituent
                if constituent != form.constituent_id.data[-1]:
                    update_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _update = update_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

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

    batch_id = BatchConstituents.query.get(item_id).batch_id

    kwargs['request'] = 'POST'

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name, admin_only=False, **kwargs)

    return redirect(url_for('batches.view', item_id=batch_id))

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}/<int:item_id>/print_ex_label', methods=['GET', 'POST'])
@login_required
def print_ex_label(item_id):
    item = table.query.get(item_id)
    batch = Batches.query.get(item.batch_id)
    attributes_list = []
    label_attributes = []

    if 'COHB' in batch.assay.assay_name or 'PRIM' in batch.assay.assay_name:
        label_attributes = fields_dict['extraction_cohb']
    else:
        label_attributes = fields_dict['extraction']

        # Get worklist for batch
        worklist = BatchRecords.query.filter(and_(BatchRecords.batch_id == item.batch.id,
                                                  BatchRecords.file_type == 'Worklist')).first()

        sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item.batch.id,
                                                  BatchRecords.file_type == 'Sequence')).first()

        df = pd.read_excel(worklist.file_path)

        headers = SequenceHeaderMappings.query.filter_by(batch_template_id=item.batch.batch_template_id).first()

        seq_df = pd.read_csv(sequence.file_path)

        const_dict = {y['Vial']: [y['SampleName'],
                                  f"{y['FilterVialLabware'][-1]}-{y['FilterVialPos']}"
                                  if pd.notna(y['FilterVialPos']) else
                                  f"{y['FilterVialLabware'][-1]}-{y['FinalPlatePos']}",
                                  y['SampleCarrierPos'] if pd.notna(y['SampleCarrierPos']) else ''] for x, y in
                      df.iterrows() if y['Type'] != 1 or 'Blank' in y['SampleName']}

        print(f"{const_dict}")

        updated_dict = {}

        for k, v in list(const_dict.items()):
            updated = False  # Track whether the key was updated

            for _, y in seq_df.iterrows():
                if v[0] == y[headers.sample_name] and v[0] != 'Blank (Recon)':
                    new_key = y[headers.vial_position]

                    # Update the dictionary with the new key and remove the old key
                    if new_key not in updated_dict:
                        updated_dict[new_key] = v
                        updated = True  # Mark that the key was updated
                        print(f"Updated {k} to {new_key}")
                    else:
                        print(f"Collision detected for {new_key}. Skipping update.")

                    break  # Stop further processing for this key

            # If the key was not updated, retain the original key-value pair
            if not updated:
                if k in updated_dict.keys():
                    pass
                else:
                    updated_dict[k] = v

        const_dict = updated_dict
        print(f"{const_dict}")
        
        print(item.batch.technique)
        for k, v in const_dict.items():
            if item.batch.technique == 'Hamilton':
                if k == item.vial_position:
                    label_attributes['HAMILTON_FV'] = v[1]
                    label_attributes['HAMILTON_SC'] = v[2]
                    label_attributes['HAMILTON_FV_1'] = v[1]
                    label_attributes['HAMILTON_SC_1'] = v[2]
            else:
                label_attributes['HAMILTON_FV'] = ''
                label_attributes['HAMILTON_SC'] = ''
                label_attributes['HAMILTON_FV_1'] = ''
                label_attributes['HAMILTON_SC_1'] = ''

    print(f"{label_attributes}")

    # Default printer for extraction labels
    printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 - Extraction'

    # FOR CONST IN CONSTITUENTS:
    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'const{item.id}.png')
    qrcode.make(f'batch_constituents: {item.id}').save(qr_path)

    with open(qr_path, "rb") as qr_file:
        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

    label_attributes['CASE_NUM'] = item.constituent_type
    label_attributes['TEST_NAME'] = ''
    label_attributes['ACC_NUM'] = ''
    label_attributes['VIAL_POS'] = item.vial_position
    label_attributes['QR'] = qr_encoded
    label_attributes['CASE_NUM_1'] = item.constituent_type
    label_attributes['TEST_NAME_1'] = ''
    label_attributes['ACC_NUM_1'] = ''
    label_attributes['QR_1'] = qr_encoded
    label_attributes['VIAL_POS_1'] = item.vial_position

    attributes_list.append(label_attributes.copy())


    return jsonify(attributes_list, printer, None, None, url_for(f'batches.view', item_id=batch.id, _external =True))
    # print_label(printer, attributes_list)

    # return redirect(url_for(f'batches.view', item_id=batch.id))
