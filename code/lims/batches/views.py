import re
import threading
import time
from collections import defaultdict
import ast

import pandas as pd
import pythoncom
import requests
import qrcode
from flask import after_this_request

from sqlalchemy import and_, or_
from sqlalchemy.sql import func, cast
from sqlalchemy.orm import joinedload
from win32com import client

from lims.batches.forms import *
from lims.batches.functions import *
from lims.forms import Import, Attach
from lims.locations.functions import get_location_choices

from lims.models import *
from lims.results.forms import UpdateStatus
from lims.specimen_audit.views import add_specimen_audit
from lims.specimens.functions import custody_and_audit
from lims.tests.forms import Cancel, Reinstate
from lims.view_templates.views import *
from lims.labels import fields_dict
import base64

# Set item variables
item_type = 'Batch'
item_name = 'Batches'
table = Batches
table_name = 'batches'
name = 'batch_id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = ['test_id', 'test_id_order']  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'view'
default_kwargs = {'template': template,
                  'redirect': redirect_to,
                  'ignore_fields': ignore_fields}

blueprint = Blueprint(table_name, __name__)

required_checks = {
    'GCET': ['specimen_check', 'sequence_check'],
    'LCQD': ['specimen_check', 'transfer_check', 'load_check', 'sequence_check'],
    'QTON': ['specimen_check', 'transfer_check', 'load_check', 'sequence_check'],
    'REF': ['specimen_check', 'gcet_specimen_check'],
    'LCCI': ['sequence_check'],
    'SAMQ': ['specimen_check', 'transfer_check', 'sequence_check'],
    'LCFS': ['specimen_check', 'transfer_check', 'sequence_check'],
    'PRIM': ['specimen_check'],
    'GCDP': ['specimen_check', 'transfer_check', 'sequence_check'],
    'COHB': ['specimen_check'],
    'GCVO': ['specimen_check', 'sequence_check'],
    'GCNO': ['specimen_check', 'sequence_check']
}

all_checks = ['specimen_check', 'transfer_check', 'load_check', 'sequence_check',
              'gcet_specimen_check']


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    assay_id = request.args.get('assay_id', type=int)
    form = get_form_choices(Add(), function='Add', assay_id=assay_id)

    kwargs['items'] = []
    kwargs['test_count'] = "Test count: 0"
    kwargs['num_tests'] = "/0"
    kwargs['test_id_order'] = ""
    if assay_id is not None:
        assay = Assays.query.get(assay_id)
        kwargs['test_count'] = "0"
        kwargs['num_tests'] = f" of max: {assay.num_tests}"
        kwargs['items'] = Tests.query.filter_by(assay_id=assay_id, test_status='Pending')

    kwargs['days'] = {
        test.id: (
        (datetime.now() - test.case.toxicology_alternate_start_date).days 
        if test.case.toxicology_alternate_start_date
        else (datetime.now() - test.case.toxicology_start_date).days) 
        for test in Tests.query.filter(Tests.batch_id == None)
        }
    
    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            assay = Assays.query.get(form.assay_id.data)
            assay.batch_count += 1
            date = datetime.now().strftime('%Y%m%d%H%M')
            kwargs['batch_id'] = f'{assay.assay_name}_{date}'
            kwargs['batch_template_id'] = assay.batch_template_id
            kwargs['test_count'] = len(form.test_id.data)
            kwargs['batch_status'] = 'Processing'
            kwargs['extracted_by_id'] = current_user.id
            kwargs['extraction_date'] = datetime.now()
            kwargs['locked'] = True
            kwargs['locked_by'] = current_user.initials
            kwargs['lock_date'] = datetime.now()

            # Get the id of the batch which will be created
            batch_id = Batches.get_next_id()
            # Create the batch
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

            if 'REF' in assay.assay_name:
                assay_key = 'REF'
            else:
                assay_key = assay.assay_name.split('-')[0]

            for n, id in enumerate(map(int, form.test_id_order.data.split(','))):
                test = Tests.query.get(id)
                test_name = f"{test.case.case_number} {test.specimen.accession_number} [{test.specimen.type.code}]_{str(n + 1).rjust(2, '0')}"
                test_id = f"{kwargs['batch_id']}_{str(n + 1).rjust(2, '0')}"
                test.test_id = test_id
                test.test_name = test_name
                test.batch_id = batch_id
                test.test_status = 'Processing'
                test.specimen_check = None
                test.checked_by = None
                test.checked_date = None
                test.gcet_specimen_check = None
                test.gcet_checked_by = None
                test.gcet_checked_date = None
                test.transfer_check = None
                test.transfer_check_by = None
                test.transfer_check_date = None
                test.sequence_check = None
                test.sequence_check_by = None
                test.sequence_check_date = None
                test.sequence_check_2 = None
                test.sequence_check_2_by = None
                test.sequence_check_2_date = None
                test.load_check = None
                test.load_check_by = None
                test.load_checked_date = None

                for verif in all_checks:
                    if verif not in required_checks[assay_key]:
                        setattr(test, verif, 'N/A')

                specimen = Specimens.query.get(test.specimen_id)
                specimen.checked_in = False
                # add_specimen_audit(specimen_id=test.specimen_id, destination=current_user.initials,
                #                    reason='Checked out for Batch', o_time=datetime.now(), status='Out',
                #                    db_status='Active')

                case = Cases.query.get(test.case.id)
                setattr(case, f"{assay.discipline.lower()}_status", 'Testing')
                case.case_status = 'In Progress'

            # Create batch record directory
            os.makedirs(os.path.join(app.config['FILE_SYSTEM'], 'batch_records', kwargs['batch_id']))

            return redirect(url_for('batches.view_list'))
            # print('BATCH SUBMITTED')
            # print(form.test_id.data)
            # selections = form.test_id.data
            # specimen_ids = []
            # for x in selections:
            #     y = Tests.query.get(x)
            #     z = Specimens.query.get(y.specimen_id)
            #     z.checked_in = False
            #     add_specimen_audit(origin=z.assay_storage_id, destination=current_user.initials,
            #                        reason='Checked out for Batch', specimen_id=y.specimen_id,o_time=datetime.now(),
            #                        d_time=datetime.now(), status='Out')
            #     specimen_ids.append(y.specimen_id)
            # print(specimen_ids)
            # for x in specimen_ids:
            #     y = Specimens.query.filter_by(id=x).all()
            #     setattr(y[0], 'checked_in', False)
            # # db.session.commit()
            # add_specimen_audit(origin='09R',destination=current_user.initials, reason='Checked out for a batch',
            #                    specimen_id=specimen_ids, o_time=datetime.now(), d_time=datetime.now(), status='6')

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Edit())
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
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
    batch = table.query.get(item_id)
    assay_id = batch.assay.id
    form = get_form_choices(Update(), function='Update', assay_id=assay_id)

    test_id = []
    test_id_order = []
    for test in Tests.query.filter_by(batch_id=batch.id).order_by(Tests.test_name.asc()):
        test_id.append(test.id)
        test_id_order.append(test.id)

    if request.method == 'GET':
        # Disable assay_id so the assay cannot be changed for the batch
        kwargs['disable_fields'] = ['assay_id']
        # kwargs['ignore_fields'] = ['assay_id']
        kwargs['items'] = [item for item in Tests.query.filter_by(assay_id=assay_id).filter(
            Tests.test_status.in_(['Pending', 'Processing'])).order_by(Tests.test_name.asc())]
        kwargs['test_id_order'] = test_id_order
        kwargs['assay_id'] = assay_id
        kwargs['test_id'] = test_id
        kwargs['test_count'] = f"Test count: {len(test_id)}"
        kwargs['num_tests'] = f"/{batch.assay.num_tests}"
        # form.assay_id.data = assay_id
        # form.test_id.data = test_id
        # form.test_id_order.data = ",".join(map(str, test_id_order))

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


##### HARD DELETE #####
@blueprint.route(f'/{table_name}/<int:item_id>/delete_hard', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()
    item = table.query.get(item_id)

    # Remove batch id from Test entry
    tests = Tests.query.filter_by(batch_id=item_id)
    for test in tests:
        test.test_id = None
        test.test_name = None
        test.batch_id = None
        test.test_status = 'Pending'

    assay = Assays.query.get(item.assay_id)
    # assay.batch_count -= 1

    BatchConstituents.query.filter_by(batch_id=item_id).delete()
    # db.session.commit()

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():
    if current_user.permissions not in ['Admin', 'Owner']:
        abort(403)

    for assay in Assays.query:
        assay.batch_count = 0

    tests = Tests.query
    if tests.count() > 0:
        for test in tests:
            test.test_id = ""
            test.test_name = ""
            test.batch_id = ""
            test.test_status = "Pending"

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
    kwargs = {}

    active_status = Statuses.query.filter_by(name='Active').first().id

    # Batches ready for PA used for notification
    kwargs['pa'] = [item for item in Batches.query.filter(and_(Batches.extraction_finish_date != None,
                                                               Batches.extraction_finish_date_2 != None,
                                                               Batches.extraction_finish_date_3 != None),
                                                               or_(Batches.process_finish_date == None,
                                                                   Batches.process_finish_date_2 == None,
                                                                   Batches.process_finish_date_3 == None)
                                                               )]

    # Batches ready for BR used for notification
    kwargs['br'] = [item for item in Batches.query.filter(and_(Batches.extraction_finish_date != None,
                                                               or_(Batches.process_finish_date != None,
                                                                   Batches.process_finish_date_2 != None,
                                                                   Batches.process_finish_date_3 != None),
                                                               or_(Batches.review_finish_date == None,
                                                                   Batches.review_finish_date_2 == None,
                                                                   Batches.review_finish_date_3 == None)))]

    # sequences = [x.split(".")[0] for x in os.listdir(os.path.join(current_app.root_path, 'static/batch_sequences'))]
    # kwargs['sequences'] = sequences

    # Get pending tests to display at the top of the page
    pending_tests = {}
    for assay in Assays.query:
        n_tests = Tests.query.filter_by(assay_id=assay.id, test_status='Pending').count()
        if n_tests:
            pending_tests[assay] = n_tests

    pending_tests = sorted(pending_tests.items(), key=lambda x: x[1], reverse=True)
    kwargs['pending_tests'] = pending_tests

    kwargs['discipline'] = disciplines

    discipline = kwargs['discipline']

    query = request.args.get('query')
    query_type = request.args.get('query_type')
    items = None

    if query_type == 'discipline':
        if query:
            print(f'query here {query}')
            items = table.query.join(Assays).filter(Assays.discipline.contains(query))

    # Get assays to display in the Filter by Assay button
    kwargs['assays'] = [item.assay_name for item in Assays.query.filter_by(status_id=active_status).order_by(Assays.assay_name)]
    # print(kwargs['assays'])
    query_type = request.args.get('query_type')
    if query_type == 'assay':
        assay = request.args.get('query')
        if assay:
            items = table.query.join(Assays, Batches.assay_id == Assays.id).filter(Assays.assay_name == assay)

    # Filter based on status
    if query_type == 'status':
        status = request.args.get('query')
        if status == 'All':
            items = table.query
        elif status:
            items = table.query.filter_by(batch_status=status)

    if query is None and query_type is None:
        items = table.query.filter_by(batch_status='Processing')

    _view_list = view_items(table, item_name, item_type, table_name, items=items, query=query, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    if current_user.permissions in ['MED-Autopsy', 'INV', 'MED', 'ADM']:
        return render_template('/error_pages/403.html'), 403

    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)

    # Initialize in_use kwarg
    kwargs['in_use'] = True

    # Initialize sequence_const kwargs
    kwargs['sequence_const'] = False

    # Initialize packets kwarg
    kwargs['packets'] = []

    # Set iteration kwarg for each process (EA, PA, BR)
    kwargs['iterations'] = {
        'ea': 3 if item.extracted_by_3_id is not None else 2 if item.extracted_by_2_id is not None else 1,
        'pa': 3 if item.processed_by_3_id is not None else 2 if item.processed_by_2_id is not None else 1,
        'br': 3 if item.reviewed_by_3_id is not None else 2 if item.reviewed_by_2_id is not None else 1
    }

    print(f'ITERATION: {kwargs["iterations"]}')

    # Check if all batch constituents are in use and set kwarg accordingly
    for const in BatchConstituents.query.filter_by(batch_id=item_id):
        if const.populated_from == 'Sequence':
            kwargs['sequence_const'] = True
        if const.constituent_id is not None:
            if not const.constituent.in_use:
                kwargs['in_use'] = False
        elif const.reagent_id is not None:
            if not const.reagent.in_use:
                kwargs['in_use'] = False

    # Get sequence if it has been created
    ws_sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                 BatchRecords.file_type == 'Sequence')).first()

    # Get extractor, processor and reviewer
    users = [item.extracted_by_id, item.processed_by_id, item.reviewed_by_id]

    # Extracting analyst form and choices
    ea_form = ExtractingAnalyst()
    # ea_form.extracted_by_id.choices = [(analyst.id, analyst.initials) for analyst in
    #                                    Users.query.filter_by(status='Active').order_by(Users.initials).all()]
    ea_form.extracted_by_id.choices = [(analyst.id, analyst.initials) for analyst in Users.query.filter(and_(
        Users.status == 'Active',
        or_(Users.permissions == 'FLD', Users.permissions == 'Admin', Users.permissions == 'Owner')
    )).order_by(Users.initials)]

    # NT form and choices
    nt_form = SetNT()
    nt_form.qr_id.choices = [(qr.id, qr.text) for qr in QRReference.query.all()]

    fin_form = SetFinalized()

    # Processing analyst form and choices
    pa_form = ProcessingAnalyst()
    pa_form.processed_by_id.choices = [(analyst.id, analyst.initials) for analyst in Users.query.filter(and_(
        Users.status == 'Active', or_(Users.permissions == 'FLD', Users.permissions == 'Admin',
                                      Users.permissions == 'Owner')
    )).order_by(Users.initials)]

    # Batch reviewer form and choices
    br_form = BatchReviewer()
    br_form.reviewed_by_id.choices = [(analyst.id, analyst.initials) for analyst in Users.query.filter(and_(
        Users.status == 'Active', or_(Users.permissions == 'FLD', Users.permissions == 'Admin',
                                      Users.permissions == 'Owner')
    )).order_by(Users.initials)]

    # Cancel test form and choices
    cancel_form = Cancel()
    cancel_form.test_comment.choices = [(item.text, item.text) for item in QRReference.query.all()]

    # Reinstate test form and choices
    reinstate_form = Reinstate()
    reinstate_form.test_comment.choices = [(item.text, item.text) for item in QRReference.query.all()]

    # Manual constituent form and choices
    manual_constituent = ManualConstituents()
    if 'GCDP-ZZ' in item.assay.assay_name and 'GCNO-ZZ' in item.gcdp_assay.assay_name:
        manual_constituent.constituent_type.choices = [(item.sequence_name, item.sequence_name) for item in SequenceConstituents.query.all()]
    else:
        manual_constituent.constituent_type.choices = [(item.constituent_type, item.constituent_type) for item in 
                                                       BatchConstituents.query.filter_by(batch_id=item_id).all()]
    manual_constituent.batch_id.data = item.id

    # Instrument and extraction check forms and choices
    inst_check_form = InstrumentCheck()
    ext_check_form = ExtractionCheck()
    status_choices = [('', '---'), ('Satisfactory', 'Satisfactory'),
                      ('Unsatisfactory - See Comment', 'Unsatisfactory -  See Comment'), ('See Comment', 'See Comment'),
                      ('N/A', 'N/A')]
    inst_check_form.instrument_check.choices = status_choices
    ext_check_form.extraction_check.choices = status_choices

    transcribe_form = TranscribeCheck()

    # Define forms
    pipette_form = PipetteForm()
    delete_pipette_form = DeletePipetteForm()

    # Normalize existing pipettes in item
    existing_pipette_ids = [str(id_.strip()) for id_ in item.pipettes.split(',') if
                            id_.strip()] if item.pipettes else []

    # Fetch calibrated labware choices excluding the ones already stored
    pipette_form.pipettes.choices = [
        (str(labware.id), labware.equipment_id)
        for labware in CalibratedLabware.query
        .join(Statuses)
        .join(CalibratedLabwareTypes)
        .filter(Statuses.name == 'Active')
        .filter(CalibratedLabwareTypes.name.ilike('%Pipette%'))
        .filter(~CalibratedLabware.id.in_(existing_pipette_ids))  # Exclude existing ones
        .all()
    ]

    # Handle pipette addition form submission
    if pipette_form.is_submitted() and pipette_form.validate() and 'pip_submit' in request.form:
        # Get the current pipettes from the database (if any)
        existing_pipettes = item.pipettes.split(',') if item.pipettes else []

        # Add the new selected pipettes from the form
        new_pipettes = [str(pip_id).strip() for pip_id in pipette_form.pipettes.data]

        # Combine the existing and new pipettes, remove duplicates
        combined_pipettes = set(existing_pipettes + new_pipettes)

        # Convert back to a comma-separated string
        updated_pipettes_str = ','.join(sorted(combined_pipettes, key=lambda x: int(x)))

        # Update the pipettes column
        item.pipettes = updated_pipettes_str

        # Commit changes to the database
        db.session.add(item)
        db.session.commit()

        flash('Pipettes have been added successfully.', 'success')
        return redirect(request.url)

    # Set sequence_check_2 (pa_check) columns to relevant data if nt is submitted
    if nt_form.is_submitted() and nt_form.validate() and 'nt_submit' in request.form:
        test = Tests.query.get(nt_form.test_id.data)
        qr_comment = QRReference.query.get(nt_form.qr_id.data)

        test.sequence_check_2 = qr_comment.text
        test.sequence_check_2_by = current_user.id
        test.sequence_check_2_date = datetime.now()

        db.session.commit()

        # If 'NT - See Comment' is selected, redirect to add a comment
        if 'See Comment' in qr_comment.text:
            return redirect(url_for('comment_instances.add', comment_item_id=test.id, comment_item_type='Tests'))

    if fin_form.is_submitted() and fin_form.validate() and 'fin_submit' in request.form:

        test = Tests.query.get(fin_form.test_id.data)
        discipline = item.assay.discipline
        event = 'UPDATED'
        status = 'Approved'
        test_revision = -1

        test_original_value = test.test_status
        test.test_status = 'Finalized'
        test_mod = Modifications.query.filter_by(record_id=test.id, table_name='Tests',
                                                 field_name='test_status').first()
        if test_mod:
            test_revision = int(test_mod.revision)

        test_revision += 1

        modification = Modifications(
            event=event,
            status=status,
            table_name='Tests',
            record_id=test.id,
            revision=test_revision,
            field='Test Status',
            field_name='test_status',
            original_value=test_original_value,
            original_value_text=str(test_original_value),
            new_value='Finalized',
            new_value_text='Finalized',
            submitted_by=current_user.id,
            submitted_date=datetime.now(),
            reviewed_by=current_user.id,
            review_date=datetime.now()
        )

        db.session.add(modification)

        # Get the case for the test
        case = test.case
        # Get the statuses of each test for that discipline in a case
        test_statuses = [x.test_status for x in
                         Tests.query.join(Assays).filter(
                             and_(Tests.case_id == case.id, Tests.test_status != 'Cancelled',
                                  Assays.discipline == discipline))]
        # Check if all statuses are 'Finalized' we also need to check if the list is empty as it also returns True.
        # Set the discipline status to 'Drafting
        if test_statuses and all(x == 'Finalized' for x in test_statuses):
            setattr(case, f"{discipline.lower()}_status", 'Ready for Drafting')

        db.session.commit()

    # Print errors for debugging
    if pipette_form.errors:
        print("Pipette Form errors:", pipette_form.errors)

    # Fetch selected pipettes for display
    pipette_ids_str = item.pipettes or ''  # Default to empty string if no pipettes are saved
    pipette_ids = [int(id.strip()) for id in pipette_ids_str.split(',') if id.strip()]  # Convert to list of ints
    selected_pipettes = CalibratedLabware.query.filter(CalibratedLabware.id.in_(pipette_ids)).all()

    # Handle deletion of pipettes
    if item.pipettes:
        # Normalize stored pipette IDs
        stored_pipette_ids = [str(id_.strip()) for id_ in item.pipettes.split(',') if id_.strip()]
        # Get the pipettes from the database that match the stored IDs
        stored_pipettes = CalibratedLabware.query.filter(CalibratedLabware.id.in_(stored_pipette_ids)).all()
        # Populate the choices for deletion
        delete_pipette_form.pipettes.choices = [(str(pip.id), pip.equipment_id) for pip in stored_pipettes]

    # Handle form submission for deletion
    if delete_pipette_form.is_submitted() and delete_pipette_form.validate() and 'pip_submit' in request.form:
        # Get the list of pipettes to delete
        pipettes_to_delete = [str(pip_id).strip() for pip_id in delete_pipette_form.pipettes.data]

        # Remove selected pipettes from the stored pipettes in the DB column
        stored_pipette_ids = [str(pip_id).strip() for pip_id in item.pipettes.split(',') if pip_id.strip()]
        updated_pipettes = [pip_id for pip_id in stored_pipette_ids if pip_id not in pipettes_to_delete]

        # Update the pipettes column with the new list (comma-separated)
        updated_pipettes_str = ','.join(updated_pipettes)
        item.pipettes = updated_pipettes_str

        db.session.commit()  # Commits the changes to the database
        flash('Selected pipettes have been removed.', 'success')
        return redirect(request.url)

    else:
        print("Delete Pipette Form Errors:", delete_pipette_form.errors)

    # get ids for all GCDP relevant assays

    gcdp_assays = ['LCQD-UR', 'QTON-BL', 'QTON-UR', 'LCFS-BL', 'LCFS-UR', 'GCNO-ZZ', 'GCVO-ZZ']

    gcdp_form = GcdpVar()
    gcdp_form.gcdp_assay_id.choices = [(assay.id, assay.assay_name) for assay in Assays.query.filter(Assays.assay_name.in_(gcdp_assays))]

    # Handle gcdp_form submission
    if gcdp_form.is_submitted() and gcdp_form.validate() and 'submit_gcdp' in request.form:
        item.gcdp_assay_id = gcdp_form.gcdp_assay_id.data
        for test in Tests.query.filter_by(batch_id=item_id, db_status='Active').all():
            for verif in all_checks:
                if verif not in required_checks[item.gcdp_assay.assay_name.split('-')[0]]:
                    setattr(test, verif, 'N/A')
        db.session.commit()

    # if pa_form.is_submitted() and pa_form.validate() and 'submit_pa' in request.form:
    #     item.locked = False
    #     pa_form.process_date.data = date
    #     update_item(pa_form, item_id, table, item_type, item_name, table_name, requires_approval, name,
    #                 locking=False, **kwargs)
    #
    #     # Lock item
    #     item.locked = True
    #     item.locked_by = Users.query.get(pa_form.processed_by_id.data).initials
    #     item.lock_date = date
    #
    #     return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Instrument form and choices
    inst_form = Instrument()
    lcms = InstrumentTypes.query.filter_by(name='LC-MS/MS').first().id
    gcms = InstrumentTypes.query.filter_by(name='HS-GC-FID').first().id
    qtof = InstrumentTypes.query.filter_by(name='LC-QTOF/MS').first().id
    cohb = InstrumentTypes.query.filter_by(name='Oximeter').first().id
    prim = InstrumentTypes.query.filter_by(name='Electrolyte Chemistry Analyzer').first().id
    gc = InstrumentTypes.query.filter_by(name='GC-MS').first().id

    if 'LC' in item.assay.assay_name or 'SAMQ' in item.assay.assay_name:
        inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=lcms)]

    elif 'GCET' in item.assay.assay_name:
        inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=gcms)]

    elif 'QTON' in item.assay.assay_name:
        inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=qtof)]

    elif 'COHB' in item.assay.assay_name:
        inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=cohb)]

    elif 'PRIM' in item.assay.assay_name:
        inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=prim)]

    elif 'GCDP' in item.assay.assay_name:
        if item.gcdp_assay_id is not None:
            if 'LC' in item.gcdp_assay.assay_name:
                inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=lcms)]
            elif 'QTON' in item.gcdp_assay.assay_name:
                inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=qtof)]
            elif 'GC' in item.gcdp_assay.assay_name:
                inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=gc)]
        else:
            inst_form.instrument_id.choices = [(0, 'Please select a GCDP variant')]

    elif item.assay.assay_name in ['GCVO-ZZ', 'GCNO-ZZ']:
        inst_form.instrument_id.choices = [(inst.id, inst.instrument_id) for inst in
                                           Instruments.query.filter_by(instrument_type_id=gc)]

    # Batch template form and choices
    batch_form = BatchTemplate()
    seen = set()  # Set to track the first 7 characters of added names

    if 'QTON' in item.assay.assay_name:
        # Set QTON batch template choices for matrix, don't include all 4 template options
        batch_form.batch_template_id.choices = [(x.id, x.name[:7]) for x in
                                                BatchTemplates.query.filter_by(instrument_id=item.instrument_id)
                                                .filter(BatchTemplates.max_samples >= item.test_count)
                                                if x.name[:7] not in seen and not seen.add(x.name[:7])]
    else:
        # Only include batch templates that can be used for sample amount. Do not include duplicate templates
        batch_form.batch_template_id.choices = [(x.id, x.name) for x in
                                                BatchTemplates.query.filter_by(instrument_id=item.instrument_id)
                                                .filter(BatchTemplates.max_samples >= item.test_count)
                                                if x.name not in seen and not seen.add(x.name)]

    # Add extractor form and add button in html in the EA cell
    # Extract the last two digits from test_name and convert them to integer for sorting
    if 'SAMQ' not in item.assay.assay_name:
        tests = (
            Tests.query
            .filter_by(batch_id=item_id, db_status='Active')
            .order_by(
                cast(
                    func.substring(Tests.test_name, func.length(Tests.test_name) - 1, 2),
                    Integer
                )
            )
        )
    else:
        tests = Tests.query.filter_by(batch_id=item_id, db_status='Active')

    # Get cases for the select field to filter results. This avoids issues with SQL and using the distinct queries.
    cases = list(sorted(set([x.case.case_number for x in tests])))

    case_ids = [x.case_id for x in tests]

    for case in case_ids:
        if LitigationPackets.query.filter_by(case_id=case).count():
            kwargs['packets'].append(Cases.query.get(case).case_number)
        else:
            pass

    test_ids = [x.id for x in Tests.query.filter_by(batch_id=item_id)]

    results = Results.query.filter(Results.test_id.in_(test_ids))

    # Initialize result status update form
    status_form = UpdateStatus()
    status_form.result_status.choices = [('Withdrawn', 'Withdrawn')]
    status_form.result_type.choices = []
    status_form.result_type.render_kw = {'disabled': True}
    status_form.result_type_update_reason.render_kw = {'disabled': True}
    status_form.type_dont_change.render_kw = {'disabled': True}

    if status_form.is_submitted() and status_form.validate() and 'status_submit' in request.form:
        # Initialize status_changed
        status_changed = False

        # Check if result_status for any result in results is different from status_form result_status
        if any(result.result_status != status_form.result_status.data for result in results):
            status_changed = True

        # Will never change result_type at batch level
        type_changed = False

        # Update fields only if values changed and reason is provided
        if status_changed and status_form.result_status_update_reason.data.strip():
            for result in results:
                result.result_status = status_form.result_status.data
                result.result_status_updated = 'Y'
                result.result_status_update_reason = f'{status_form.result_status_update_reason.data} ' \
                                                     f'({current_user.initials} ' \
                                                     f'{datetime.now().strftime("%m/%d/%Y %H:%M")})'

        if type_changed and status_form.result_type_update_reason.data.strip():
            for result in results:
                result.result_type = status_form.result_type.data
                result.result_type_updated = 'Y'
                result.result_type_update_reason = f'{status_form.result_type_update_reason.data} ' \
                                                   f'({current_user.initials} ' \
                                                   f'{datetime.now().strftime("%m/%d/%Y %H:%M")})'

        # Withdraw batch
        item.batch_status = 'Withdrawn'

        for test in tests:
            test.test_status = 'Withdrawn'

        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Create comment dictionaries for tooltips
    test_comment_dict = {}
    result_comment_dict = {}
    item_types = {
        'Tests': (test_comment_dict, tests),
        'Results': (result_comment_dict, results)
    }

    start = time.time()

    for itype, (item_type_dict, items) in item_types.items():
        # Get all IDs from the items
        item_ids = [i.id for i in items]

        # Fetch all comments for these items in one query
        all_comments = CommentInstances.query.filter(
            CommentInstances.comment_item_type == itype,
            CommentInstances.comment_item_id.in_(item_ids),
            CommentInstances.db_status == 'Active'
        ).order_by(CommentInstances.comment_id.desc()).all()

        # Group comments by comment_item_id
        comments_by_item = {}
        for comment in all_comments:
            comments_by_item.setdefault(comment.comment_item_id, []).append(comment)

        # Build HTML for each item if it has comments
        for i in items:
            comments = comments_by_item.get(i.id, [])
            if comments:
                # Use list to accumulate parts of the HTML string
                li_elements = []
                for comment in comments:
                    li_parts = ["<li>"]
                    if getattr(comment, 'comment_id'):
                        if comment.comment.code:
                            li_parts.append(f"{comment.comment.code} - ")
                        li_parts.append(f"{comment.comment.comment}")
                    else:
                        li_parts.append(f"{comment.comment_text}")
                    li_parts.append(f" ({comment.created_by})</li>")
                    li_elements.append("".join(li_parts))
                # Join all list items into a single HTML unordered list
                comment_text = "<ul>" + "".join(li_elements) + "</ul>"
                item_type_dict[i.id] = comment_text

    print(f'COMMENTS TOOK: {time.time() - start}')

    # Create dynamic SAMQ form
    samq_form = dynamic_form(tests)

    # Set choices for dynamic form
    for field in samq_form:
        if field.type == 'SelectMultipleField':
            field.choices = [
                ('SAMQ-1-QLA', 'SAMQ-1-QLA'),
                ('SAMQ-1-QHA', 'SAMQ-1-QHA'),
                ('SAMQ-Z-C1A', 'SAMQ-Z-C1A'),
                ('SAMQ-Z-C2A', 'SAMQ-Z-C2A'),
                ('SAMQ-Z-C3A', 'SAMQ-Z-C3A'),
                ('SAMQ-Z-C4A', 'SAMQ-Z-C4A'),
                ('SAMQ-Z-C5A', 'SAMQ-Z-C5A'),
                ('SAMQ-Z-C6A', 'SAMQ-Z-C6A'),
                ('SAMQ-Z-C7A', 'SAMQ-Z-C7A')
            ]

    # for test in tests:
    #     test.checked_by = None
    #     test.checked_date = None
    #     test.specimen_check = None
    # db.session.commit()

    # Initialize arrays for samples that need to be collected/returned
    need_collect = []
    need_return = []

    if item.extraction_finish_date is None and current_user.id == item.extracted_by_id:
        if 'PRIM' in item.assay.assay_name or 'COHB' in item.assay.assay_name:
            for test in tests:
                # Don't include tests with no specimen assigned
                if test.specimen is None:
                    pass
                # Check if there are any blank checks for test and specimen not in extractor's custody
                elif test.specimen_check is None and \
                        test.specimen.custody != current_user.initials:
                    # Append specimen to collect
                    need_collect.append(test.specimen_id)
                # Check if all checks are completed and specimen in extractor's custody
                elif test.specimen_check is not None and \
                        test.specimen.custody == current_user.initials:
                    # Check if extraction is automated
                    if item.technique == 'Hamilton':
                        # Check if automated check is complete
                        if test.load_check is not None and test.specimen.custody == current_user.initials:
                            # Append specimen to return
                            need_return.append(test.specimen_id)
                    else:
                        # Append specimen to return
                        need_return.append(test.specimen_id)
                # Check if extraction is automated
                elif item.technique == 'Hamilton':
                    # Check if automated check is blank and specimen not in extractor's custody
                    if test.load_check is None and test.specimen.custody != current_user.initials:
                        # Append to collect
                        need_collect.append(test.specimen_id)
        else:
            for test in tests:
                # Don't include tests with no specimen assigned
                if test.specimen is None:
                    pass
                # Check if there are any blank checks for test and specimen not in extractor's custody
                elif test.specimen_check is None or test.sequence_check is None and \
                        test.specimen.custody != current_user.initials:
                    # Append specimen to collect
                    need_collect.append(test.specimen_id)
                # Check if all checks are completed and specimen in extractor's custody
                elif test.specimen_check is not None and test.transfer_check is not None and \
                        test.sequence_check is not None and test.specimen.custody == current_user.initials:
                    # Check if extraction is automated
                    if item.technique == 'Hamilton':
                        # Check if automated check is complete
                        if test.load_check is not None and test.specimen.custody == current_user.initials:
                            # Append specimen to return
                            need_return.append(test.specimen_id)
                    else:
                        # Append specimen to return
                        need_return.append(test.specimen_id)
                # Check if extraction is automated
                elif item.technique == 'Hamilton':
                    # Check if automated check is blank and specimen not in extractor's custody
                    if test.load_check is None and test.specimen.custody != current_user.initials:
                        # Append to collect
                        need_collect.append(test.specimen_id)
                elif 'LC' in item.assay.assay_name or 'QTON' in item.assay.assay_name:
                    if test.transfer_check is None and test.specimen.custody != current_user.initials:
                        need_collect.append(test.specimen_id)

    # Remove duplicates from arrays
    need_collect = set(need_collect)
    need_return = set(need_return)

    # Length arrays
    need_collect_len = len(need_collect)
    need_return_len = len(need_return)

    if 'LCCI' in item.assay.assay_name:
        if item.tandem_id:
            if Batches.query.get(item.tandem_id).extraction_finish_date:
                not_extracted = 0
                need_collect_len = 0
                need_return_len = 0
            else:
                not_extracted = 1
        elif 'PRIM' in item.assay.assay_name or 'COHB' in item.assay.assay_name:
            not_extracted = Tests.query.filter(
                and_(Tests.batch_id == item_id, or_(Tests.specimen_check == None))).count()
        else:
            not_extracted = Tests.query.filter(and_(Tests.batch_id == item_id, or_(Tests.specimen_check == None,
                                                                                   Tests.transfer_check == None,
                                                                                   Tests.sequence_check == None))).count()

    elif 'PRIM' in item.assay.assay_name or 'COHB' in item.assay.assay_name:
        not_extracted = Tests.query.filter(and_(Tests.batch_id == item_id, or_(Tests.specimen_check == None))).count()

    else:
        # Number of tests that have not been extracted
        not_extracted = Tests.query.filter(and_(Tests.batch_id == item_id, or_(Tests.specimen_check == None,
                                                                               Tests.transfer_check == None,
                                                                               Tests.sequence_check == None))).count()
        not_extracted = BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item_id,
                                                            or_(BatchConstituents.specimen_check == None,
                                                                BatchConstituents.transfer_check == None,
                                                                BatchConstituents.sequence_check == None))).count()
    # Add to count for automated checks
    if item.technique == 'Hamilton':
        not_extracted += Tests.query.filter(and_(Tests.batch_id == item_id, and_(Tests.load_check == None,
                                                                                 Tests.specimen_check != None,
                                                                                 Tests.transfer_check != None,
                                                                                 Tests.sequence_check != None))).count()
        not_extracted = BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item_id,
                                                            and_(BatchConstituents.load_check == None,
                                                                 BatchConstituents.specimen_check != None,
                                                                 BatchConstituents.transfer_check != None,
                                                                 BatchConstituents.sequence_check != None,
                                                                 BatchConstituents.include_checks == True))).count()

    constituents = BatchConstituents.query.filter_by(batch_id=item_id)
    batch_records = BatchRecords.query.filter_by(batch_id=item_id)
    batch_comments = CommentInstances.query.filter_by(comment_item_type=item_name, comment_item_id=item.id,
                                                      db_status='Active')
    # Create dictionary of constituent_type key and vial_position value to display vial position for manually added constituents
    kwargs['constituent_vials'] = {const.constituent_type: const.vial_position for const in constituents if const.vial_position is not None}
    date = datetime.now()

    # Sequence form
    seq_form = GenerateSequence()

    # Necessary for batches that do not have a tandem batch
    tandem_batch = None

    if item.tandem_id is not None:
        tandem_batch = [batch for batch in Batches.query.filter(and_(Batches.tandem_id == item.tandem_id,
                                                                     Batches.id != item_id))]

    # Initialize form for adding constituents via barcode
    form = ResourcesBarcode()

    # Handle constituent barcode form if submitted
    if form.is_submitted() and form.validate():

        print(f"SUBMITTED CONSTITUENT BARCODE {form}")

        form.specimen_check_by.data = current_user.id
        form.specimen_check_date.data = datetime.now()
        # If standard_and_solution was scanned in
        if form.constituent_scan.data.split(': ')[0] == 'standards_and_solutions':
            # Get ID from form
            form.constituent_id.data = int(form.constituent_scan.data.split(': ')[1])

            standard = StandardsAndSolutions.query.get(form.constituent_id.data)
            assays = []
            for assay_id in standard.assay.split(', '):
                assays.append(Assays.query.get(int(assay_id)).assay_name)

            print(f'ASSAYS: {assays}')

            # Get assay_constituent ID from standards_and_solutions
            scan = standard.constituent.id
            # Get constituent name
            scan_name = standard.constituent.name

            defaults = ['Mobile Phase A', 'Mobile Phase B', 'Acetonitrile', 'Methanol', 'ISZ1']

            # Follow different path for SAMQ, no matching
            if 'SAMQ' in item.assay.assay_name and scan_name not in defaults:
                # This is used because SAMQ standards aren't assigned to a batch constituent
                # Standards are used in tests. SAMQ just assigns standard to batch
                field_data = {}
                vial_pos_idx = 0
                # Get sample vial positions from sequence
                if scan_name == 'Reconstitution Mix':
                    vial_pos_idx = len(BatchConstituents.query.filter_by(constituent_id=form.constituent_id.data,
                                                                         batch_id=item_id).all())

                    vial_position = [y['VialPos'] for x, y in pd.read_csv(ws_sequence.file_path,
                                                                          encoding='utf-8-sig').iterrows()
                                     if 'Blank (Recon)' in y['% header=SampleName']]
                elif scan_name == 'Blank (Blood)':
                    vial_position = [y['VialPos'] for x, y in pd.read_csv(ws_sequence.file_path,
                                                                          encoding='utf-8-sig').iterrows()
                                     if scan_name in y['% header=SampleName']]
                elif scan_name[:2] in ['QH', 'QL']:
                    vial_position = [y['VialPos'] for x, y in pd.read_csv(ws_sequence.file_path,
                                                                          encoding='utf-8-sig').iterrows()
                                     if scan_name[:2] in y['SampleID']]
                elif scan_name == 'Blank (Urine)':
                    vial_position = [y['VialPos'] for x, y in pd.read_csv(ws_sequence.file_path,
                                                                          encoding='utf-8-sig').iterrows()
                                     if scan_name in y['% header=SampleName']]
                else:
                    vial_position = [y['VialPos'] for x, y in pd.read_csv(ws_sequence.file_path,
                                                                          encoding='utf-8-sig').iterrows()
                                     if scan_name in y['SampleID']]

                # Set relevant data for batch constituents
                # Update to only include all fields for blank matrices, standards do not get all fields
                field_data.update({
                    'db_status': 'Active',
                    'locked': False,
                    'create_date': datetime.now(),
                    'created_by': current_user.initials,
                    'revision': 0,
                    'batch_id': item.id,
                    'constituent_id': form.constituent_id.data,
                    'constituent_type': scan_name,
                    'populated_from': 'Scan',
                    'vial_position': vial_position[vial_pos_idx],
                    'include_checks': True,
                    'specimen_check': 'Completed / Automated',
                    'specimen_check_by': current_user.id,
                    'specimen_check_date': datetime.now()
                })

                # Add relevant batch constituent
                to_add = BatchConstituents(**field_data)
                db.session.add(to_add)
                db.session.commit()
            # Get sequence_constituent entry for matching
            seq_const = SequenceConstituents.query.filter_by(constituent_type=scan).all()
            # Iterate through all constituents to find match
            for seq in seq_const:
                found = False
                for const in constituents:
                    if seq.sequence_name == const.constituent_type and const.constituent_id is None:
                        # Assign constituent_id to batch_constituents entry only if there is no match
                        if seq.sequence_name in ['Blank (Blood)', 'Blank (Urine)']:
                            if item.assay.assay_name not in assays:
                                flash(Markup('Blank matrix lot not approved for use in current assay.'), 'error')
                                return redirect(url_for(f'{table_name}.view', item_id=item.id))
                        const.constituent_id = form.constituent_id.data
                        if 'Mix Check' in seq.sequence_name:
                            const.transfer_check = 'N/A'
                            const.transfer_check_date = None
                            const.transfer_check_by = None
                        if 'Blank (Recon)' in seq.sequence_name and item.technique == 'Non-Hamilton':
                            const.specimen_check = 'Completed / Automated'
                            const.specimen_check_by = current_user.id
                            const.specimen_check_date = datetime.now()
                            const.transfer_check = 'N/A'
                            const.transfer_check_date = None
                            const.transfer_check_by = None
                        # Only set specimen check for standards where extracted = False and assay/technique correct
                        elif seq.extracted and (item.technique == 'Non-Hamilton' or 'GCET' in item.assay.assay_name):
                            form.specimen_check_by.data = None
                            form.specimen_check_date.data = None
                        else:
                            const.specimen_check = 'Completed / Automated'
                            const.specimen_check_by = current_user.id
                            const.specimen_check_date = datetime.now()
                        db.session.commit()
                        found = True
                        break
                if found:
                    break
        # If solvent_and_reagent was scanned in
        elif form.constituent_scan.data.split(': ')[0] == 'solvents_and_reagents':
            # Get ID from form
            form.reagent_id.data = int(form.constituent_scan.data.split(': ')[1])
            # Get assay_constituent ID from standards_and_solutions
            scan = SolventsAndReagents.query.get(form.reagent_id.data).const.id

            # Follow different path for SAMQ, no matching
            if 'SAMQ' in item.assay.assay_name:
                field_data = {}

                # Populate field data for purchased reagent
                # Check to make sure all necessary fields are populated
                field_data.update({
                    'db_status': 'Active',
                    'locked': False,
                    'create_date': datetime.now(),
                    'created_by': current_user.initials,
                    'revision': 0,
                    'batch_id': item.id,
                    'constituent_id': form.constituent_id.data,
                    'constituent_type': SolventsAndReagents.query.get(form.reagent_id.data).const.name,
                    'populated_from': 'Scan'
                })

                # Add batch constituent
                to_add = BatchConstituents(**field_data)
                db.session.add(to_add)
                db.session.commit()

            # Get sequence_constituent entry for matching
            seq_const = SequenceConstituents.query.filter_by(constituent_type=scan).all()
            # Iterate through all constituents to find match
            for seq in seq_const:
                found = False
                for const in constituents:
                    if seq.sequence_name == const.constituent_type and const.reagent_id is None:
                        # Assign constituent_id to batch_constituents entry only if there is no match
                        const.reagent_id = form.reagent_id.data
                        # Only set specimen check for standards where extracted = False and assay/technique correct
                        if seq.extracted and (item.technique == 'Non-Hamilton' or 'GCET' in item.assay.assay_name):
                            form.specimen_check_by.data = None
                            form.specimen_check_date.data = None
                        else:
                            const.specimen_check = 'Completed / Automated'
                            const.specimen_check_by = current_user.id
                            const.specimen_check_date = datetime.now()
                        db.session.commit()
                        found = True
                        break
                if found:
                    break
        # Do not add if above conditions are not met
        else:
            pass

        # Set batch id in form
        form.batch_id.data = item_id

        # add_item(form, BatchConstituents, 'Batch Constituents', 'Batch Constituents', 'batch_constituents', False, 'id',
        #          **kwargs)

        # Replaced with add_item to include modifications
        # # Initialize model data
        # field_data.update({
        #     'db_status': 'Active',
        #     'locked': False,
        #     'create_date': datetime.now(),
        #     'created_by': current_user.initials,
        #     'revision': 0
        # })
        #
        # # Get the int of the scanned constituent
        # constituent_id = int(form.constituent.data.split(': ')[1])
        #
        # # Add batch_id and constituent_id to dict to be added to db
        # field_data.update({
        #     'batch_id': item.id,
        #     'constituent_id': constituent_id
        # })
        #
        # # Add and commit changes to db
        # db.session.add(BatchConstituents(**field_data))
        # db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))
        # return jsonify(redirect=url_for(f'{table_name}.view', item_id=item_id))
    else:
        if form.is_submitted():
            print(f"FORM ERRORS {form.errors}")
        else:
            print(f"FORM NOT SUBMITTED")

    # Handle extracting analyst form if submitted
    if ea_form.is_submitted() and ea_form.validate():

        new_ea = Users.query.get(ea_form.extracted_by_id.data)

        if item.extracted_by_2_id is not None:
            current_ea = item.extractor_2.initials
        elif item.extracted_by_id is not None:
            current_ea = item.extractor.initials

        # Specimen IDs if in batch
        specimens_in_batch = [test.specimen_id for test in Tests.query.filter_by(batch_id=item_id).all()]

        # Specimens in current users custody
        specimens_in_custody = [specimen for specimen in Specimens.query.filter_by(custody=current_ea).all()]

        # Specimens to be transferred on EA change
        specimens_to_transfer = []

        # Assign specimen to be transferred to new EA
        for specimen in specimens_in_custody:
            if specimen.id in specimens_in_batch:
                specimens_to_transfer.append(specimen)


        item.locked = False
        if item.extracted_by_id is not None:
            if item.extracted_by_2_id is not None:
                if item.extracted_by_3_id is not None:
                    pass
                else:
                    item.extraction_finish_date_2 = datetime.now()
                    item.extracted_by_3_id = ea_form.extracted_by_id.data
                    item.extraction_date_3 = datetime.now()

                    for specimen in specimens_to_transfer:
                        custody_and_audit(specimen, specimen.id, 'received for extraction', user=new_ea)
            else:
                item.extraction_finish_date = datetime.now()
                item.extracted_by_2_id = ea_form.extracted_by_id.data
                item.extraction_date_2 = datetime.now()

                for specimen in specimens_to_transfer:
                        custody_and_audit(specimen, specimen.id, 'received for extraction', user=new_ea)
        else:
            item.extracted_by_id = ea_form.extracted_by_id.data
            item.extraction_date = datetime.now()
            
        # ea_form.extraction_date.data = datetime.now()
        # update_item(ea_form, item_id, table, item_type, item_name, table_name, requires_approval, name,
        #             locking=False, **kwargs)

        # Lock item
        item.locked = True
        item.locked_by = Users.query.get(ea_form.extracted_by_id.data).initials
        item.lock_date = datetime.now()
        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Handle processing analyst form if submitted
    if pa_form.is_submitted() and pa_form.validate() and 'submit_pa' in request.form:
        item.locked = False
        if item.processed_by_id is not None:
            if item.processed_by_2_id is not None:
                if item.processed_by_3_id is not None:
                    pass
                else:
                    item.process_finish_date_2 = datetime.now()
                    item.processed_by_3_id = pa_form.processed_by_id.data
                    item.process_date_3 = datetime.now()

            else:
                item.process_finish_date = datetime.now()
                item.processed_by_2_id = pa_form.processed_by_id.data
                item.process_date_2 = datetime.now()

        else:
            item.processed_by_id = pa_form.processed_by_id.data
            item.process_date = datetime.now()


        # pa_form.process_date.data = datetime.now()
        # update_item(pa_form, item_id, table, item_type, item_name, table_name, requires_approval, name,
        #             locking=False, **kwargs)

        # Lock item
        item.locked = True
        item.locked_by = Users.query.get(pa_form.processed_by_id.data).initials
        item.lock_date = datetime.now()

        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Handle batch reviewer form if submitted
    if br_form.is_submitted() and br_form.validate() and 'submit_br' in request.form:
        item.locked = False
        if item.reviewed_by_id is not None:
            if item.reviewed_by_2_id is not None:
                if item.reviewed_by_3_id is not None:
                    pass
                else:
                    item.review_finish_date_2 = datetime.now()
                    item.reviewed_by_3_id = br_form.reviewed_by_id.data
                    item.review_date_3 = datetime.now()

            else:
                item.review_finish_date = datetime.now()
                item.reviewed_by_2_id = br_form.reviewed_by_id.data
                item.review_date_2 = datetime.now()

        else:
            item.reviewed_by_id = br_form.reviewed_by_id.data
            item.review_date = datetime.now()

        # br_form.review_date.data = datetime.now()
        # update_item(br_form, item_id, table, item_type, item_name, table_name, requires_approval, name,
        #             locking=False, **kwargs)

        # Lock item
        item.locked = True
        item.locked_by = Users.query.get(br_form.reviewed_by_id.data).initials
        item.lock_date = datetime.now()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Handle instrument assignment form if submitted
    if 'inst_submit' in request.form:
        if inst_form.is_submitted() and inst_form.validate():
            update_item(inst_form, item_id, table, item_type, item_name, table_name, requires_approval, name,
                        locking=False,
                        **kwargs)

            return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Handle batch template form if submitted
    if batch_form.is_submitted() and batch_form.validate():
        update_item(batch_form, item_id, table, item_type, item_name, table_name, requires_approval, name,
                    locking=False, **kwargs)

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    if seq_form.is_submitted() and seq_form.validate() and 'submit_seq' in request.form:
        # Initialize sequence form dictionary
        seq_dict = {}

        # Assign assay type
        if 'GCDP' in item.assay.assay_name:
            assay = item.gcdp_assay.assay_name
        else:
            assay = item.assay.assay_name

        # Iterate through each form field and add field name and data to dict
        for field in seq_form:
            seq_dict[field.name] = field.data

        # Convert dict to str
        dict_str = json.dumps(seq_dict)
        return redirect(url_for(f'{table_name}.create_sequence', item_id=item_id, seq_dict=dict_str, assay=assay))

    # Set seq variable to determine if batch currently has a sequence generated
    if BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id, BatchRecords.file_type == 'Sequence')).first():
        seq = True
    else:
        seq = False

    # if cancel_form.is_submitted() and cancel_form.validate() and 'submit_cancel' in request.form:
    #     print(request.form)
    #     # Set test_status to cancelled
    #     cancel_form.test_status.data = 'Cancelled'
    #     update_item(cancel_form, cancel_form.test_id.data, Tests, 'Test(s)', 'Tests', 'tests', False, 'id',
    #                 locking=False)
    #     # Record comment in TestComments table
    #     add_item(cancel_form, TestComments, 'Test Comment', 'Test Comments', 'test_comments', False, 'id')
    #
    #     return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # if reinstate_form.is_submitted() and reinstate_form.validate() and 'submit_reinstate' in request.form:
    #     print(request.form)
    #     # Set test_status to cancelled
    #     reinstate_form.test_status.data = 'Processing'
    #     reinstate_form.test_comment.data = 'Reinstated'
    #     update_item(reinstate_form, reinstate_form.test_id.data, Tests, 'Test(s)', 'Tests', 'tests', False, 'id',
    #                 locking=False)
    #     # Record comment in TestComments table
    #     add_item(reinstate_form, TestComments, 'Test Comment', 'Test Comments', 'test_comments', False, 'id')
    #
    #     return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Check if a manual constituent iteration has been added, if so, add_item
    if manual_constituent.is_submitted() and manual_constituent.validate() and 'const_submit' in request.form:
        manual_constituent.populated_from.data = 'Manual'
        kwargs['sequence_check'] = 'N/A'
        kwargs['transfer_check'] = 'N/A'
        add_item(manual_constituent, BatchConstituents, 'Batch Constituents', 'Batch Constituents',
                 'batch_constituents', False, 'id', **kwargs)

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Handle SAMQ form submission - FINISH COMMENTING TLD
    if samq_form.is_submitted() and samq_form.validate() and 'samq_submit' in request.form:
        # Initialize relevant dictionaries
        samq_const = {}
        seq_dict = {}

        for test in tests:
            for field in samq_form:
                if str(test.id) in field.name:
                    samq_const[test.id] = field.data

        for field in seq_form:
            seq_dict[field.name] = field.data

        # Convert dict to str
        dict_str = json.dumps(seq_dict)

        samq_dict = json.dumps(samq_const)

        return redirect(url_for(f'{table_name}.create_sequence', item_id=item.id, seq_dict=dict_str,
                                assay=item.assay.assay_name, samq_const=samq_dict))

    # Check for instrument check submission and update data as needed
    if inst_check_form.is_submitted() and inst_check_form.validate() and 'inst_check_submit' in request.form:
        inst_check_form.instrument_check_by.data = current_user.id
        inst_check_form.instrument_check_date.data = datetime.now()
        update_item(inst_check_form, item_id, table, item_type, item_name, table_name, requires_approval, name)

        return redirect(url_for(f'{table_name}.view', item_id=item.id))

    # Check for extraction check submission and update data as needed
    if ext_check_form.is_submitted() and ext_check_form.validate() and 'ext_check_submit' in request.form:
        ext_check_form.extraction_check_by.data = current_user.id
        ext_check_form.extraction_check_date.data = datetime.now()
        update_item(ext_check_form, item_id, table, item_type, item_name, table_name, requires_approval, name)

        return redirect(url_for(f'{table_name}.view', item_id=item.id))

    # Check for transcribe check submission and update data as needed
    if transcribe_form.is_submitted() and transcribe_form.validate() and 'transcribe_check_submit' in request.form:
        transcribe_form.transfer_check.data = "Complete"
        transcribe_form.checked_by_id.data = current_user.id
        transcribe_form.checked_date.data = datetime.now()
        item.locked = False
        item.locked_by = None
        item.lock_date = None
        update_item(transcribe_form, item_id, table, item_type, item_name, table_name, requires_approval, name)
        item.locked = True
        item.locked_by = Users.query.get(item.extracted_by_id).initials
        item.lock_date = datetime.now()

        for test in tests:
            test.transfer_check = True

        return redirect(url_for(f'{table_name}.view', item_id=item.id))

    # Set batch level checks
    kwargs['batch_specimen_check'] = True
    kwargs['batch_load_check'] = True
    kwargs['batch_transfer_check'] = True
    kwargs['batch_sequence'] = True

    # Default extraction check to N/A for COHB, PRIM, GCET and GCDP
    if 'REF' in item.assay.assay_name or 'COHB' in item.assay.assay_name or 'PRIM' in item.assay.assay_name or 'GCET' in item.assay.assay_name or 'GCDP' \
            in item.assay.assay_name:
        ext_check_form.extraction_check.data = 'N/A'

    for const in constituents:
        if const.specimen_check_by is not None:
            pass
        elif const.specimen_check is None:
            kwargs['batch_specimen_check'] = False

        if const.sequence_check is not None:
            pass
        elif const.sequence_check is None:
            kwargs['batch_sequence'] = False

    if 'LCCI' in item.assay.assay_name and item.tandem_id:
        tandem_tests = Tests.query.filter_by(batch_id=item.tandem_id).all()
        tandem_constituents = BatchConstituents.query.filter_by(batch_id=item.tandem_id).all()

        # Check tests check statuses
        for test in tandem_tests:

            if test.load_check is not None:
                pass
            elif test.load_check is None:
                kwargs['batch_load_check'] = False

            if test.transfer_check is not None:
                pass
            elif test.transfer_check is None:
                kwargs['batch_transfer_check'] = False

        # Check constituents check statuses, same logic as above
        for const in tandem_constituents:
            if const.transfer_check is not None:
                pass
            elif const.transfer_check is None:
                kwargs['batch_transfer_check'] = False

        for test in tests:
            if test.sequence_check is not None:
                pass
            elif test.sequence_check is None:
                kwargs['batch_sequence'] = False

    elif 'REF' in item.assay.assay_name:
        # Check tests check statuses
        for test in tests:

            # If relevant check is completed, keep status boolean, else set status to False
            if test.specimen_check != 'Skipped' and test.specimen_check is not None:
                pass
            elif test.specimen_check is None or test.specimen_check == 'Skipped':
                kwargs['batch_specimen_check'] = False

    else:

        # Check constituents check statuses, same logic as above
        for const in constituents:
            if const.transfer_check is not None:
                pass
            elif const.transfer_check is None:
                kwargs['batch_transfer_check'] = False

        # Check tests check statuses
        for test in tests:

            # If relevant check is completed, keep status boolean, else set status to False
            if test.specimen_check != 'Skipped' and test.specimen_check is not None:
                pass
            elif test.specimen_check is None or test.specimen_check == 'Skipped':
                kwargs['batch_specimen_check'] = False

            if test.load_check is not None:
                pass
            elif test.load_check is None:
                kwargs['batch_load_check'] = False

            if test.transfer_check is not None:
                pass
            elif test.transfer_check is None:
                kwargs['batch_transfer_check'] = False

            if test.sequence_check is not None:
                pass
            elif test.sequence_check is None:
                kwargs['batch_sequence'] = False

        # Check constituents check statuses, same logic as above
        for const in constituents:
            if const.specimen_check is not None:
                pass
            elif const.specimen_check is None:
                kwargs['batch_specimen_check'] = False

            if const.transfer_check is not None:
                pass
            elif const.transfer_check is None:
                kwargs['batch_transfer_check'] = False

            if const.sequence_check is not None:
                pass
            elif const.sequence_check is None:
                kwargs['batch_sequence'] = False

    # Set current_extractor kwarg to determine EA
    kwargs['current_extractor'] = None

    if item.extracted_by_3_id is not None:
        kwargs['current_extractor'] = item.extracted_by_3_id
    elif item.extracted_by_2_id is not None:
        kwargs['current_extractor'] = item.extracted_by_2_id
    elif item.extracted_by_id is not None:
        kwargs['current_extractor'] = item.extracted_by_id

    alias = f"{item.batch_id} | {item.batch_status}"

    _view = view_item(
        item, alias, item_name, table_name,
        default_buttons=False,
        show_attachments=False,
        show_comments=False,
        constituents=constituents,
        tests=tests,
        cases=cases,
        batch_records=batch_records,
        results=results,
        tandem=tandem_batch,
        form=form,
        date=date,
        ea_form=ea_form,
        pa_form=pa_form,
        br_form=br_form,
        inst_form=inst_form,
        batch_form=batch_form,
        seq=seq,
        seq_form=seq_form,
        cancel_form=cancel_form,
        reinstate_form=reinstate_form,
        manual_constituent=manual_constituent,
        test_comment_dict=test_comment_dict,
        result_comment_dict=result_comment_dict,
        batch_comments=batch_comments,
        users=users,
        need_collect_len=need_collect_len,
        need_return_len=need_return_len,
        not_extracted=not_extracted,
        samq_form=samq_form,
        pipette_form=pipette_form,
        delete_pipette_form=delete_pipette_form,
        selected_pipettes=selected_pipettes,
        inst_check_form=inst_check_form,
        ext_check_form=ext_check_form,
        transcribe_form=transcribe_form,
        nt_form=nt_form,
        fin_form=fin_form,
        status_form=status_form,
        gcdp_form=gcdp_form,
        **kwargs
    )

    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/assign_resources', methods=['GET', 'POST'])
@login_required
def assign_resources(item_id):
    kwargs = default_kwargs.copy()
    item = Batches.query.get(item_id)
    assay = item.assay
    form = AssignResources()
    field_data = {}

    constituents = [(item.id, item.lot) for item in
                    StandardsAndSolutions.query.filter(and_(StandardsAndSolutions.assay.contains(str(assay.id)),
                                                            StandardsAndSolutions.in_use == False))]

    form.constituent_id.choices = constituents

    # Get any assigned constituents
    selected_constituents = [item.constituent_id for item in BatchConstituents.query.filter_by(batch_id=item_id)]

    if request.method == 'POST':
        if form.is_submitted() and form.validate():

            field_data.update({
                'db_status': 'Active',
                'locked': False,
                'create_date': datetime.now(),
                'created_by': current_user.initials,
                'revision': 0
            })

            for const in form.constituent_id.data:
                field_data.update({
                    'batch_id': item.id,
                    'constituent_id': const
                })

            to_add = BatchConstituents(**field_data)

            db.session.add(to_add)
            db.session.commit()

            return redirect(url_for(f'{table_name}.view', item_id=item_id))

            # # Create sequence file
            # if item.batch_template_id != form.batch_template_id.data:
            #     batch_template_id = form.batch_template_id.data
            #     batch_template_name = BatchTemplates.query.get(batch_template_id).name
            #     df = pd.read_csv(
            #         os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template_name}.csv"),
            #         encoding="ISO-8859-1")
            #     headers = SequenceHeaderMappings.query.filter_by(batch_template_id=batch_template_id).first()
            #     sample_idx = df[df[headers.sample_name].isna()].index
            #
            #     for n, test in enumerate(Tests.query.filter_by(batch_id=item_id)):
            #         idx = sample_idx[n]
            #         df.loc[idx, headers.sample_name] = test.test_name
            #         df.loc[idx, headers.dilution] = test.dilution
            #         df.loc[idx, headers.comments] = test.specimen.condition
            #
            #     df[headers.data_file] = item.batch_id
            #     df = df.dropna(subset=[headers.sample_name])
            #     df.to_csv(os.path.join(current_app.root_path, 'static/batch_sequences', f"{item.batch_id}.csv"),
            #               index=False)
            #
            # for constituent in form.constituent_id.data:
            #     if constituent not in selected_constituents:
            #         db.session.add(BatchConstituents(**{
            #             'constituent_id': constituent,
            #             'batch_id': item_id,
            #             'template': 'form.html'
            #         }))
            #
            # for constituent in selected_constituents:
            #     if constituent not in form.constituent_id.data:
            #         BatchConstituents.query.filter_by(batch_id=item_id, constituent_id=constituent).delete()

    elif request.method == 'GET':
        kwargs['instrument_id'] = assay.instrument_id
        kwargs['items'] = StandardsAndSolutions.query.filter(and_(StandardsAndSolutions.assay.contains(str(assay.id)),
                                                                  StandardsAndSolutions.in_use == False))
        kwargs['extraction_date'] = datetime.now().date()
        kwargs['extracted_by_id'] = current_user.id
        kwargs['constituent_id'] = selected_constituents
        kwargs['assays'] = dict([(item.id, item.assay_name) for item in Assays.query.all()])
        print(kwargs['constituent_id'])

    # _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    # return _update

    return render_template(
        f'{table_name}/assign_resources.html',
        item=item,
        form=form,
        kwargs=kwargs
    )


@blueprint.route(f'/{table_name}/<int:item_id>/cancel', methods=['GET', 'POST'])
@login_required
def cancel(item_id):
    batch = Batches.query.get(item_id)
    # Set the batch status to cancelled
    batch.batch_status = 'Cancelled'
    # Get only active tests
    tests = Tests.query.filter_by(batch_id=item_id, db_status='Active')
    # This removes these properties from the tests and modifications dictionaries which will be clone
    remove_keys = ['id', '_sa_instance_state']

    for n, test in enumerate(tests):
        if 'SAMQ' in test.test_name:
            test.db_status = 'Removed'
        # Cancel the tests
        test.test_status = 'Cancelled'
        # Get the modifications for the test
        mods = Modifications.query.filter_by(table_name='Tests', record_id=str(test.id))
        for mod in mods:
            # Convert the modifications to a dictionary
            mod_dict = mod.__dict__
            # Remove the 'id' and '_sa_instance_state' keys
            for key in remove_keys:
                del mod_dict[key]
            # Set the new values
            mod_dict['record_id'] = Tests.get_next_id()
            mod_dict['submitted_by'] = current_user.id
            mod_dict['submitted_date'] = datetime.now()
            mod_dict['reviewed_by'] = current_user.id
            mod_dict['review_date'] = datetime.now()
            db.session.add(Modifications(**mod_dict))

        # Clone the test data and set new_values
        test_dict = test.__dict__
        for key in remove_keys:
            del test_dict[key]
        # Remove the _XX from the test name since these tests are assigned to a batch
        test_dict['test_name'] = test_dict['test_name'][:-3]
        test_dict['test_id'] = None
        test_dict['batch_id'] = None
        test_dict['test_status'] = 'Pending'
        test_dict['created_by'] = current_user.initials
        test_dict['create_date'] = datetime.now()
        test_dict['modified_by'] = None
        test_dict['modify_date'] = None
        db.session.add(Tests(**test_dict))

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/reinstate', methods=['GET', 'POST'])
@login_required
def reinstate(item_id):
    if current_user.permissions not in ['Admin', 'Owner']:
        abort(403)

    batch = Batches.query.get(item_id)
    batch.batch_status = 'Processing'
    tests = Tests.query.filter_by(batch_id=item_id)

    for test in tests:
        test.test_status = 'Processing'

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/duplicate_tests', methods=['GET', 'POST'])
@login_required
def duplicate_tests():
    form = Duplicate()
    batch_id = request.args.get('item_id', type=int)
    # Get all batchs for the batch_id field.
    batches = [(item.id, item.batch_id) for item in Batches.query.order_by(Batches.create_date.desc())]
    batches.insert(0, (0, 'Please select a batch'))

    # Set the test choices if batch_id is provided
    if batch_id:
        tests = Tests.query.filter_by(batch_id=batch_id, db_status='Active')
        test_choices = [(item.id, item.id) for item in tests]
    else:
        tests = []
        test_choices = []

    kwargs = {
        'tests': tests,
        'test_choices': test_choices
    }

    form.batch_id.choices = batches
    form.batch_id.data = batch_id
    form.test_id.choices = test_choices

    if request.method == 'POST':
        if form.validate_on_submit():
            # Keys to remove from item dictionary when cloning
            remove_keys = ['id', '_sa_instance_state']
            tests = Tests.query.filter(Tests.id.in_(form.test_id.data))

            # Clone the test details for each test and remove the 'id' and '_sa_instance_state' keys
            # Add the "batch_id" and create new test_id based on the batch_id and set the
            # create_date to now and created_by to the current user. Clear any modify details
            for n, test in enumerate(tests):
                mods = Modifications.query.filter_by(table_name='Tests', record_id=str(test.id))
                for mod in mods:
                    # Convert the modifications to a dictionary
                    mod_dict = mod.__dict__
                    # Remove the 'id' and '_sa_instance_state' keys
                    for key in remove_keys:
                        del mod_dict[key]
                    # Set the new values
                    mod_dict['record_id'] = Tests.get_next_id()
                    mod_dict['submitted_by'] = current_user.id
                    mod_dict['submit_date'] = datetime.now()
                    mod_dict['reviewed_by'] = current_user.id
                    mod_dict['review_date'] = datetime.now()
                    db.session.add(Modifications(**mod_dict))

                # Clone the test data and set new_values
                test_dict = test.__dict__
                for key in remove_keys:
                    del test_dict[key]
                # Remove the _XX from the test name since these tests are assigned to a batch
                test_dict['test_name'] = test_dict['test_name'][:-3]
                test_dict['test_id'] = None
                test_dict['batch_id'] = None
                test_dict['test_status'] = 'Pending'
                test_dict['created_by'] = current_user.initials
                test_dict['create_date'] = datetime.now()
                test_dict['modified_by'] = None
                test_dict['modify_date'] = None
                db.session.add(Tests(**test_dict))

            db.session.commit()
            flash(Markup(f"<b>{tests.count()}</b> test(s) duplicated"), 'success')
            return redirect(url_for(f'{table_name}.view_list'))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                    function='Duplicate Tests', template=f'duplicate.html', **kwargs)

    return _add


@blueprint.route(f'/{table_name}/get_tests/', methods=['GET', 'POST'])
@login_required
def get_tests_json():
    assay_id = request.args.get('assay_id', type=int)
    batch_id = request.args.get('batch_id', type=int)
    response = get_tests(assay_id, batch_id)

    return response


@blueprint.route(f'/{table_name}/get_oldest/', methods=['GET', 'POST'])
@login_required
def get_oldest_json():
    assay_id = request.args.get('assay_id', type=int)
    response = get_oldest(assay_id)

    return response


@blueprint.route(f'/{table_name}/get_newest/', methods=['GET', 'POST'])
@login_required
def get_newest_json():
    assay_id = request.args.get('assay_id', type=int)
    response = get_newest(assay_id)

    return response


@blueprint.route(f'/{table_name}/get_optimum/', methods=['GET', 'POST'])
@login_required
def get_optimum_json():
    assay_id = request.args.get('assay_id', type=int)
    response = get_optimum(assay_id)

    return response


@blueprint.route(f'/{table_name}/<int:item_id>/inject_samples/', methods=['GET', 'POST'])
@login_required
def inject_samples(item_id):
    tests = Tests.query.filter_by(batch_id=item_id)

    for test in tests:
        # test.specimen.checked_in = True

        test.specimen.custody = 'PLACEHOLDER'  # Need to add ability to choose specimen next location

        # Need to update specimen audit to include next location
        add_specimen_audit(test.specimen.id, 'PLACEHOLDER', 'Batch injected', datetime.now(), 'OUT', db_status='Active')

    db.session.commit()

    return redirect(url_for(f'{table_name}.view_list'))


@blueprint.route(f'/{table_name}/<int:item_id>/collect', methods=['GET', 'POST'])
@login_required
def collect(item_id):
    form = CollectSpecimens()

    # tests = Tests.query.filter_by(batch_id=item_id)  # Each test item in the batch
    # specimens = []  # Initialize list for specimens

    item = Batches.query.get(item_id)
    users = [x.initials for x in  # query for all active users with below job classes
             Users.query.filter(and_(or_(Users.job_class == '2403', Users.job_class == '2456',
                                         Users.job_class == '2457', Users.job_class == '2458'),
                                     Users.status == 'Active'))]
    # users.append('TST')

    # Array of specimen ids in batch
    specimen_ids = [test.specimen.id for test in Tests.query.filter_by(batch_id=item_id) if 'B' not 
                    in test.specimen.case.case_number and 'SAMQ' in item.assay.assay_name]
    
    if 'SAMQ' in item.assay.assay_name:
        specimen_ids = [test.specimen.id for test in Tests.query.filter_by(batch_id=item_id) if 'B' not 
                        in test.specimen.case.case_number]
        
    else:
        specimen_ids = [test.specimen.id for test in Tests.query.filter_by(batch_id=item_id)]
    
    specimens = Specimens.query.filter(Specimens.id.in_(specimen_ids))

    specimens_in_users_possession = specimens.filter(Specimens.custody == current_user.initials)
    # Array of specimen model object
    specimens = specimens.filter(Specimens.custody != current_user.initials)

    # Current specimen locations
    locations = [specimen.custody for specimen in Specimens.query.filter(Specimens.id.in_(specimen_ids))]

    # Choices for select_specimens
    form.selected_specimens.choices = [(specimen.id, specimen.accession_number) for specimen in
                                       specimens]

    unique = set(locations)
    unique = list(unique)

    print(f'UNIQUE: {unique}')

    # for test in tests:
    #     specimens.append(test.specimen)  # Add each specimen in batch to list
    #     print(f'SPECIMEN: {test.specimen.accession_number}')
    #     test.specimen.custody = current_user.initials
    #     add_specimen_audit(test.specimen.id, current_user.initials, 'clicked "Collect Specimens" button',
    #                        datetime.now(), 'OUT')
    # db.session.commit()

    if form.is_submitted() and form.validate():
        print(f'DATA: {form.selected_specimens.data}')

        collected_specimens = [specimen for specimen in
                               Specimens.query.filter(Specimens.id.in_(form.selected_specimens.data))]

        for specimen in collected_specimens:
            # specimen.custody = '18R'
            # db.session.commit()
            if 'SAMQ' in item.assay.assay_name and 'B' in specimen.case.case_number:
                pass
            else:
                custody_and_audit(specimen, specimen.id, 'collected for extraction')

    return render_template(
        f'{table_name}/collect.html',
        item=item,
        specimens=specimens,
        specimens_in_users_possession=specimens_in_users_possession,
        users=users,
        unique=unique,
        form=form,
    )


@blueprint.route(f'/{table_name}/<int:item_id>/return', methods=['GET', 'POST'])
@login_required
def return_specimen(item_id):
    form = ReturnSpecimens()

    # tests = Tests.query.filter_by(batch_id=item_id)  # Each test item in the batch
    # specimens = []  # Initialize list for specimens

    item = Batches.query.get(item_id)
    users = [x.initials for x in  # query for all active users with below job classes
             Users.query.filter(and_(or_(Users.job_class == '2403', Users.job_class == '2456',
                                         Users.job_class == '2457', Users.job_class == '2458'),
                                     Users.status == 'Active')).all()]
    # users.append('TST')

    choices = []

    # Array of specimen ids in batch
    specimen_ids = [test.specimen.id for test in Tests.query.filter_by(batch_id=item_id)]

    # Array of specimen model object
    specimens = [specimen for specimen in Specimens.query.filter(Specimens.id.in_(specimen_ids))]

    # Choices for selected_specimens (matches specimens in table to facilitate table selections)
    form.selected_specimens.choices = [(specimen.id, specimen.accession_number) for specimen in specimens]
    
    # Initialize previous_locations dict
    previous_locations = {}

    # Get most recent storage location for each specimen
    for specimen in specimens:
        all_locations = [x.destination for x in 
                         SpecimenAudit.query.filter_by(specimen_id=specimen.id).order_by(SpecimenAudit.id.desc())]
        
        # Get the most recent specimen audit entry that starts with two digits
        first_two_digit = next(
            (loc for loc in all_locations
            if isinstance(loc, str) and re.match(r'^\s*\d{2}', loc)),
            None
        )

        previous_locations[specimen.id] = first_two_digit

    if form.is_submitted() and form.validate():
        print(f'DATA: {form.selected_specimens.data}')

        returned_specimens = [specimen for specimen in
                              Specimens.query.filter(Specimens.id.in_(form.selected_specimens.data))]

        destination = form.custody.data.strip()

        for specimen in returned_specimens:
            specimen.custody = destination
            add_specimen_audit(specimen.id, destination, f'{current_user.initials} returned specimen after extraction',
                               datetime.now(), 'IN', db_status='Active')

    return render_template(
        f'{table_name}/return.html',
        item=item,
        specimens=specimens,
        users=users,
        form=form,
        previous_locations=previous_locations
    )


@blueprint.route(f'/get_batches_choices/')
@login_required
def get_choices():
    location_1 = request.args.get('location_1')

    response = get_location_choices(location_1)

    return response

    # if storage_location == 'person':
    #     people = Users.query.filter(and_(or_(Users.job_class == '2403', Users.job_class == '2456',
    #                                          Users.job_class == '2457', Users.job_class == '2458'),
    #                                      Users.status == 'Active')).all()
    #     print(people[0].initials)
    #
    #     choices = []
    #
    #     if next_location != 0:
    #         if len(people) != 0:
    #             choices.append({'id': 0, 'name': 'Please select staff'})
    #             for person in people:
    #                 choices.append({'id': person.id, 'name': person.initials})
    #         else:
    #             choices.append({'id': 0, 'name': 'Please select staff'})
    #     else:
    #         choices.append({'id': 0, 'name': 'Please select next location'})
    #
    #     return jsonify({'choices': choices})

    # if location_1 == 'fridge_or_freezer':  # Need to add query when fridges and freezers table created
    #     choices = [{'id': item.id, 'name': item.equipment_id} for item in CooledStorage.query.all()]
    #     choice = {'id': 0, 'name': 'Please select a fridge/freezer'}
    #     choices.insert(0, choice)
    #     print(f'CHOICES {choices}')
    #     return jsonify({'choices': choices})
    #
    # elif location_1 == 'bench':  # Need to add query when benches table created
    #     choices = []
    #     choice = {'id': 0, 'name': 'Please select a bench'}
    #     choices.append(choice)
    #     print(f'CHOICES {choices}')
    #     return jsonify({'choices': choices})
    #
    # elif location_1 == 'cabinet':
    #     choices = []
    #     choice = {'id': 0, 'name': 'Please select a cabinet'}
    #     choices.append(choice)
    #     print(f'CHOICES {choices}')
    #     return jsonify({'choices': choices})
    #
    # elif location_1 == 'fume_hood':
    #     choices = []
    #     choice = {'id': 0, 'name': 'Please select a hood'}
    #     choices.append(choice)
    #     print(f'CHOICES {choices}')
    #     return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/<int:item_id>/check', methods=['GET', 'POST'])
@login_required
def check(item_id):
    form = ReturnSpecimens()
    item = Batches.query.get(item_id)

    # Query for all active users with below job classes
    users = [x.initials for x in
             Users.query.filter(and_(or_(Users.job_class == '2403', Users.job_class == '2456',
                                         Users.job_class == '2457', Users.job_class == '2458'),
                                     Users.status == 'Active')).all()]
    # users.append('TST')

    # Determine if looking for specimens in EA custody or current user custody
    if form.is_submitted():
        # Query for tests that are in the batch, have not been checked, and in current user (checker) custody
        tests = Tests.query.join(Specimens, Tests.specimen).options(joinedload(Tests.specimen)) \
            .filter(and_(Tests.batch_id == item.id, Tests.checked_by.is_(None),
                         Specimens.custody == current_user.initials))
    else:
        # Query for tests that are in the batch, have not been checked, and are in custody of the EA
        tests = Tests.query.join(Specimens, Tests.specimen).options(joinedload(Tests.specimen)) \
            .filter(and_(Tests.batch_id == item.id, Tests.checked_by.is_(None),
                         Specimens.custody == item.extractor.initials))

    # The following assignments are necessary for the way the code works

    # Assign a list of all specimen accession numbers
    specimen_accession = [test.specimen.accession_number for test in tests]
    # Assign a list of all specimen case numbers
    specimen_case = [test.specimen.case.case_number for test in tests]
    # Assign a list of all specimen ids
    specimen_id = [test.specimen.id for test in tests]

    # Get tests into the format of form choices
    form.selected_specimens.choices = [(test.specimen.id, test.specimen.accession_number) for test in tests if
                                       test.specimen.custody == item.extractor.initials]

    # Assign specimen custody to current user and add specimen audit
    for test in tests:
        test.specimen.custody = current_user.initials
        add_specimen_audit(test.specimen.id, current_user.initials,
                           f'{current_user.initials} performed specimen check', datetime.now(), 'OUT')

    if form.is_submitted():

        # Get all tests in which the specimen has been approved
        approved_specimens = [test for test in tests if test.specimen.id in form.selected_specimens.data]

        # Get all possible specimen which could have been approved
        submission_choices = [(test.specimen.id, test.specimen.accession_number) for test in tests if
                              test.specimen.custody == current_user.initials]

        # Search for tests in which the specimen has been approved
        for index, accession_number in submission_choices:
            for x in approved_specimens:
                # Set checked_by, checked_date, custody and add an audit for each approved specimen
                if accession_number == x.specimen.accession_number:
                    x.checked_by = current_user.id
                    x.specimen_check = 'Complete / Manual'
                    x.checked_date = datetime.now()
                    x.specimen.custody = item.extractor.initials
                    add_specimen_audit(x.specimen.id, item.extractor.initials, 'returned after specimen check',
                                       datetime.now(), 'OUT')
                    # Remove approved specimens from choices
                    submission_choices.remove((index, accession_number))

        # At this point submission_choices is a list of everything that hasn't been approved

        # Get just the specimen id from submission_choices
        unapproved_ids = [index for index, accession_number in submission_choices]

        # Get all tests in batch that do not have approved specimen
        unapproved_specimens = [test for test in tests if test.specimen.id in unapproved_ids]

        # Assign custody to the EA and add specimen audit for each unapproved specimen
        for x in unapproved_specimens:
            x.specimen.custody = item.extractor.initials
            add_specimen_audit(x.specimen.id, item.extractor.initials,
                               f'{current_user.initials} returned after specimen check', datetime.now(), 'OUT')

        # Commit all changes to db
        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    return render_template(
        f'{table_name}/check.html',
        item=item,
        users=users,
        form=form,
        specimen_accession=specimen_accession,
        specimen_case=specimen_case,
        specimen_id=specimen_id,
    )


@blueprint.route(f'/{table_name}/<int:item_id>/barcode_check', methods=['GET', 'POST'])
@login_required
def barcode_check(item_id):
    form = BarcodeCheck()
    batch = Batches.query.get(item_id)
    constituents = []
    dilution_form = DilutionUpdate()
    directive_form = DirectiveUpdate()
    comment_form = AddComment()
    item = Batches.query.get(item_id)

    # initialize iterative standard
    iterative_standard = False

    const_id_hold = BatchConstituents.query.filter_by(batch_id=item_id).all()
    constituent_ids = {const.constituent_type: const.id for const in const_id_hold if const.vial_position is not None}

    # Initialize for exiting source check modal counting
    check_needed = 0

    comment_form.comment_id.choices = [(comment.id, f"{comment.code} - {comment.comment_type} - {comment.comment}")
                                       for comment in Comments.query.filter_by(comment_type='Tests')]

    for const in BatchConstituents.query.filter_by(batch_id=batch.id):
        # Append relevant constituents and attr to constituents array (reagent and constituent have different attr)
        if const.constituent_id is not None:
            constituents.append((const.constituent_type, const.constituent.constituent.name, const))
        elif const.reagent_id is not None:
            constituents.append((const.constituent_type, const.reagent.const.name, const))
        else:
            pass

    # Create tests array for all tests and extracted constituents in batch
    if 'SAMQ' not in item.assay.assay_name:
        tests = [z for x, y, z in constituents if
                 SequenceConstituents.query.filter_by(sequence_name=x).first().extracted]
    else:
        # Tests array must follow separate creation due to SAMQ nuances
        tests = []
        for x, y, z in constituents:
            if x == 'Internal Standard':
                pass
            else:
                lookup = AssayConstituents.query.filter_by(name=x).first().id
                if SequenceConstituents.query.filter_by(constituent_type=lookup).first().extracted:
                    tests.extend([z])
    tests += [test for test in Tests.query.filter_by(batch_id=item_id)]

    # Used for testing purposes - TLD
    # for test in tests:
    #     if test.__tablename__ == 'tests' and test.specimen_check is None:
    #         print(f'VIAL: {test.vial_position}: SPECIMEN: {test.specimen_id}')

    # # Sort the combined list by the `vial_position` attribute in ascending order
    # tests = sorted(tests, key=lambda test: test.vial_position)
    #
    # for test in tests:
    #     print(f'VIAL POSITION: {test.vial_position}')

    # # If user is EA: query tests that are in the batch, have not been checked, and are in the EA's possession
    # if current_user.initials == item.extractor.initials:
    #     if item.technique == 'Manual':
    #         tests = [z for x, y, z in constituents if SequenceConstituents.filter_by(sequence_name=x).first().extracted]
    #         # for x, y, z in constituents:
    #         #     if SequenceConstituents.query.filter_by(sequence_name=x).first().extracted:
    #         #         tests.append(z)
    #         # tests.append([test for test in ])
    #         # Array of const.constituent_type for const in BatchConstituents
    #         # For const in array, if const in sequence_constituents and extracted, tests.append(const)
    #         # tests.append([const for const in BatchConstituents.query.filter(and_(BatchConstituents.))])
    #
    #     tests += [test for test in Tests.query.join(Specimens,
    #                                                 Tests.specimen).options(joinedload(Tests.specimen)).filter(
    #         and_(Tests.batch_id == item.id, Tests.checked_by.is_(None),
    #              Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)]  # storage_location?
    #
    #     # Append skipped tests to the end of the array
    #     if Tests.query.filter(and_(Tests.batch_id == item.id, Tests.specimen_check == 'Skipped')).first():
    #         tests += [test for test in Tests.query.join(Specimens,
    #                                                     Tests.specimen).options(joinedload(Tests.specimen)).filter(
    #             and_(Tests.batch_id == item.id, Tests.specimen_check.is_('Skipped'),
    #                  Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)]
    # else:
    #     tests = []

    # Testing dilution instructions
    # for test in tests:
    #     if test.id == 78768:
    #         test.directive = '(d1/2)'
    #         # test.directive = '(d1/5)'
    #         # test.directive = 'HV(d1/2)'
    #         # test.directive = '(d1/20)'
    #         db.session.commit()

    # Check for dilution change
    if dilution_form.is_submitted() and dilution_form.validate() and 'dilution_submit' in request.form:
        # Get form data
        id_test = dilution_form.id_test.data
        update_item(dilution_form, id_test, Tests, 'Test(s)', 'Tests', 'tests', False, 'test_name')

    # # Check for directive change
    if directive_form.is_submitted() and directive_form.validate() and 'directive_submit' in request.form:
        # Get form data
        id_test = directive_form.id_test.data
        update_item(directive_form, id_test, Tests, 'Test(s)', 'Tests', 'tests', False, 'test_name')

    # Handle add comment submission
    if comment_form.is_submitted() and comment_form.validate() and 'comment_submit' in request.form:
        comment_form.comment_item_type.data = 'Tests'
        comment_form.comment_type.data = 'Tests'
        comment_form.comment_text.data = Comments.query.get(int(comment_form.comment_id.data)).comment

        add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 'comment_instances',
                 False, 'id')

    # Check form submission
    if form.is_submitted() and form.validate() and 'dilution_submit' not in request.form and \
            'comment_submit' not in request.form and 'directive_submit' not in request.form:
        # Initialize variables
        batch_items = []
        idx = 0

        # Split source data into [table, id]
        source = form.source_specimen.data.split(': ')

        # Get all batch_items (tests/batch_constituents) related to input
        if source[0] == 'specimens' or source[0] == 's':
            batch_items = [item for item in Tests.query.filter(and_(Tests.specimen_id == source[1],
                                                                    Tests.batch_id == batch.id))]
        elif source[0] == 'standards_and_solutions':
            specimen = BatchConstituents.query.filter_by(constituent_id=source[1]).first()
            if specimen.vial_position is not None:
                batch_items = [item for item in BatchConstituents.query.filter(
                    and_(BatchConstituents.constituent_id == source[1], BatchConstituents.batch_id == batch.id))]
            else:
                batch_items = [item for item in BatchConstituents.query.filter_by(id=constituent_ids[specimen.constituent_type])]
                iterative_standard = True
            if 'SAMQ' in Batches.query.get(item_id).assay.assay_name and 'Blank' in \
                    specimen.constituent.constituent.name:
                batch_items.extend(item for item in
                                   Tests.query.filter(and_(Tests.batch_id == item_id, Tests.test_name.like('PSS%'))))

        elif source[0] == 'solvents_and_reagents':
            batch_items = [item for item in BatchConstituents.query.filter(
                and_(BatchConstituents.reagent_id == source[1], BatchConstituents.batch_id == batch.id))]

        # else:
        #     try:
        #         if int(form.source_specimen.data):
        #             batch_items = [item for item in Tests.query.filter(and_(Tests.specimen_id == source[1],
        #                                                                     Tests.batch_id == batch.id))]
        #     except ValueError:
        #         pass

        # Check if skip was selected
        # To get all relevant tests, need to query similar to get_batch_information and check for which tests present
        # for i in range(1, form.num_fields.data + 1):
        #     test_scan_value = request.form.get(f'testScan{idx}')
        #     if int(test_scan_value.split(': ')[1]) in [item.id for item in batch_items]:
        #         print(f'ITEM: {test_scan_value}')

        # Initialize array to check which batch_items were skipped
        skipped_items = list(batch_items)

        # Iterate through all batch items related to input
        for item in batch_items:
            # Increment idx to determine which input element is being handled (input elements dynamically created)
            idx += 1
            # Try
            try:
                if not iterative_standard:
                    # Check if current input element contains current batch_item or if 'qr_reference:' was input
                    if item.id == int(request.form.get(f'testScan{idx}').split(': ')[1]) or 'qr_reference' in \
                            request.form.get(f'testScan{idx}').split(': ')[0]:
                        # Set qr_reference text for relevant batch_item.specimen_check (source check)
                        if 'qr_reference' in request.form.get(f'testScan{idx}').split(': ')[0]:
                            item.specimen_check = QRReference.query.get(int(
                                request.form.get(f'testScan{idx}').split(': ')[1])).text
                        # Set batch_item.specimen_check (source check) to complete
                        else:
                            item.specimen_check = 'Completed / Automated'
                        # Handle if batch_item is test or batch_constituent (different names for specimen_check columns)
                        if hasattr(item, 'checked_by'):
                            item.checked_by = current_user.id
                            item.checked_date = datetime.now()
                        else:
                            item.specimen_check_by = current_user.id
                            item.specimen_check_date = datetime.now()

                        # Remove batch_item from skipped_items (batch_item was not skipped)
                        skipped_items.remove(item)
                else:
                    # Check if current input element contains current batch_item or if 'qr_reference:' was input
                    item = BatchConstituents.query.filter_by(constituent_id=int(request.form.get(f'source_specimen').split(': ')[1]), batch_id=item_id).first()
                    skipped_items = []
                    # Set qr_reference text for relevant batch_item.specimen_check (source check)
                    if 'qr_reference' in request.form.get(f'testScan{idx}').split(': ')[0]:
                        item.specimen_check = QRReference.query.get(int(
                            request.form.get(f'testScan{idx}').split(': ')[1])).text
                    # Set batch_item.specimen_check (source check) to complete
                    else:
                        item.specimen_check = 'Completed / Automated'
                    # Handle if batch_item is test or batch_constituent (different names for specimen_check columns)
                    if hasattr(item, 'checked_by'):
                        item.checked_by = current_user.id
                        item.checked_date = datetime.now()
                    else:
                        item.specimen_check_by = current_user.id
                        item.specimen_check_date = datetime.now()
                    db.session.commit()
            # Handle exception if item was skipped
            except IndexError:
                # Handle requisition barcode assignment for REF batches
                # Will trigger index error because it is assigning new barcode to test
                if 'REF' in batch.assay.assay_name:
                    if request.form.get(f'testScan{idx}') == item.gcet_specimen_check:
                        item.specimen_check = 'Completed / Automated'
                        item.checked_by = current_user.id
                        item.checked_date = datetime.now()
                        skipped_items.remove(item)
                else:
                    print(f'BLANK INPUT')
            # Handle any attribute errors
            except AttributeError:
                print(f'ATTRIBUTE ERROR: {request.form.get(f"testScan{idx}")}')

        # Iterate through skipped items
        for skip in skipped_items:
            # Set all relevant columns for a skipped item
            skip.specimen_check = 'Skipped'
            if hasattr(skip, 'checked_by'):
                skip.checked_by = None
                skip.checked_date = None
            else:
                skip.specimen_check_by = None
                skip.specimen_check_date = None

        # Commit
        db.session.commit()

        # Clear form input
        form.source_specimen.data = ''

        # Find how many tests still need checks
        for test in tests:
            if test.specimen_check is None:
                check_needed += 1

        return render_template(
            f'{table_name}/source_check.html',
            item=batch,
            form=form,
            assay=batch.assay.assay_name,
            tests=tests,
            dilution_form=dilution_form,
            directive_form=directive_form,
            comment_form=comment_form,
            check_needed=check_needed,
        )

    # Find how many tests still need checks
    for test in tests:
        if test.specimen_check is None:
            check_needed += 1

    return render_template(
        f'{table_name}/source_check.html',
        item=batch,
        form=form,
        assay=batch.assay.assay_name,
        tests=tests,
        dilution_form=dilution_form,
        directive_form=directive_form,
        comment_form=comment_form,
        check_needed=check_needed,
    )

    # if not form.source_specimen.data and not form.test_specimen.data and \
    #         (('qr_reference' not in form.source_specimen.data and 'qr_reference' not in form.test_specimen.data)
    #          or ('GCET' in item.assay.assay_name and not form.test_specimen_2.data and
    #              'qr_reference' not in form.test_specimen_2.data and 'qr_reference' not in form.test_specimen.data)):
    #     # if form.source_specimen.data is None or form.test_specimen.data is None:
    #     tests[0].specimen_check = 'Skipped'
    #     tests[0].checked_by = 'Skipped'
    #     tests[0].checked_date = datetime.now()
    #     form.test_specimen.data = ''
    #     form.source_specimen.data = ''
    #     db.session.commit()
    # # Check if a qr code form the qr_reference table was scanned in either test
    # elif 'qr_reference: ' in form.test_specimen.data or 'qr_reference: ' in form.test_specimen_2.data or \
    #         'qr_reference' in form.source_specimen.data:
    #     # Set relevant values for test it was scanned into
    #     if 'qr_reference: ' in form.test_specimen.data:
    #         tests[0].checked_by = current_user.id
    #         tests[0].specimen_check = QRReference.query.get(form.test_specimen.data.split(' ')[1]).text
    #         tests[0].checked_date = datetime.now()
    #         form.test_specimen.data = ''
    #         form.source_specimen.data = ''
    #         form.test_specimen_2.data = ''
    #     elif 'qr_reference' in form.source_specimen.data:
    #         tests[0].checked_by = current_user.id
    #         tests[0].specimen_check = QRReference.query.get(form.source_specimen.data.split(' ')[1]).text
    #         tests[0].checked_date = datetime.now()
    #         form.test_specimen.data = ''
    #         form.source_specimen.data = ''
    #         form.test_specimen_2.data = ''
    #
    #     if 'qr_reference: ' in form.test_specimen_2.data:
    #         tests[0].gcet_checked_by = current_user.id
    #         tests[0].gcet_specimen_check = QRReference.query.get(form.test_specimen_2.data.split(' ')[1]).text
    #         tests[0].gcet_checked_date = datetime.now()
    #         form.test_specimen.data = ''
    #         form.source_specimen.data = ''
    #         form.test_specimen_2.data = ''
    #         # If it was only scanned into test 2, set relevant data for test 1
    #         if 'qr_reference: ' not in form.test_specimen.data:
    #             tests[0].checked_by = current_user.id
    #             tests[0].specimen_check = 'Complete / Automated'
    #             tests[0].checked_date = datetime.now()
    #             form.test_specimen.data = ''
    #             form.source_specimen.data = ''
    #             form.test_specimen_2.data = ''
    #
    #     # Commit
    #     db.session.commit()
    # # qr_reference code not scanned, form not skipped
    # else:
    #     # Set current tests to checked by current user and checked at current datetime
    #     if item.technique == 'Manual' and 'batch_constituents: ' in form.test_specimen.data:
    #         tests[0].specimen_check_by = current_user.id
    #         tests[0].specimen_check = 'Complete / Automated'
    #         tests[0].specimen_check_date = datetime.now()
    #     else:
    #         tests[0].checked_by = current_user.id
    #         tests[0].specimen_check = 'Complete / Automated'
    #         tests[0].checked_date = datetime.now()
    #     form.source_specimen.data = ''
    #     form.test_specimen.data = ''
    #     form.test_specimen_2.data = ''
    #     # Set relevant data for test 2 scan
    #     if 'GCET' in item.assay.assay_name:
    #         tests[0].gcet_checked_by = current_user.id
    #         tests[0].gcet_specimen_check = 'Complete / Automated'
    #         tests[0].gcet_checked_date = datetime.now()
    #         form.test_specimen.data = ''
    #         form.source_specimen.data = ''
    #         form.test_specimen_2.data = ''
    #     # Commit
    #     db.session.commit()

    # Remove the checked test from the list
    #     tests.pop(0)
    #
    #     # If there are still tests in tests, return the next page for checking
    #     # Determine if REF assay
    #     if 'REF' in item.assay.assay_name and tests:
    #         return render_template(
    #             f'{table_name}/ref_barcode_check.html',
    #             item=tests[0],
    #             form=form,
    #             assay=item.assay.assay_name
    #         )
    #     elif tests:
    #         return render_template(
    #             f'{table_name}/barcode_check.html',
    #             item=tests[0],
    #             form=form,
    #             assay=item.assay.assay_name
    #         )
    #     # Redirect to batch view if no more tests remain
    #     else:
    #         return redirect(url_for(f'{table_name}.view', item_id=item_id))
    #
    # # Return correct view based on assay
    # if 'REF' in item.assay.assay_name:
    #     return render_template(
    #         f'{table_name}/ref_barcode_check.html',
    #         item=tests[0],
    #         form=form,
    #         assay=item.assay.assay_name
    #     )
    # else:
    #     return render_template(
    #         f'{table_name}/source_check.html',
    #         item=tests[0],
    #         form=form,
    #         assay=item.assay.assay_name,
    #         tests=tests
    #     )


@blueprint.route(f'/{table_name}/<int:item_id>/tests', methods=['GET', 'POST'])
@login_required
def all_tests(item_id):
    item = Batches.query.get(item_id)
    # Filter for all tests in a batch, sort by last two digits
    tests = (
        Tests.query
        .filter_by(batch_id=item_id)
        .order_by(
            cast(
                func.substring(Tests.test_name, func.length(Tests.test_name) - 1, 2),
                Integer
            )
        )
    )

    # Used to clear all checks for testing purposes - TLD
    # for test in tests:
    #     test.specimen_check = None
    #     test.checked_by = None
    #     test.checked_date = None
    #     test.transfer_check = None
    #     test.transfer_check_by = None
    #     test.transfer_check_date = None
    #     test.sequence_check = None
    #     test.sequence_check_by = None
    #     test.sequence_check_date = None
    #     test.load_check = None
    #     test.load_check_by = None
    #     test.load_checked_date = None
    # db.session.commit()

    return render_template(
        f'{table_name}/tests.html',
        item=item,
        tests=tests
    )


@blueprint.route(f'/{table_name}/<int:item_id>/<ref_table>/<check_name>/single', methods=['GET', 'POST'])
@login_required
def single_check(item_id, ref_table, check_name):
    # Initialize source_checks with column shared by tests and batch_constituents
    source_checks = ['specimen_check']
    if ref_table == 'tests':
        # Get item and add relevant column names to source_checks
        item = Tests.query.get(item_id)
        source_checks.extend(['checked_by', 'checked_date'])
    elif ref_table == 'batch_constituents':
        # Get item and add relevant column names to source_checks
        item = BatchConstituents.query.get(item_id)
        source_checks.extend(['specimen_check_by', 'specimen_check_date'])
        if check_name == 'source':
            # Clear batch_constituent lot information if clearing source check
            source_checks.extend(['constituent_id', 'reagent_id'])
    else:
        item = ''

    # Determine check type
    if check_name == 'source':
        # Clear all source checks
        for x in source_checks:
            setattr(item, x, None)
        db.session.commit()
        # Check if table is batch_constituents
        if ref_table == 'batch_constituents':
            # Redirect to batches.view
            return redirect(url_for(f'{table_name}.view', item_id=item.batch_id))
        else:
            # Redirect to batches.barcode_check
            return redirect(url_for(f'{table_name}.barcode_check', item_id=item.batch_id))
    elif check_name == 'load':
        # Clear load checks
        item.load_check = None
        item.load_check_by = None
        item.load_checked_date = None
        db.session.commit()
        # Redirect to batches.hamilton_samples
        return redirect(url_for(f'{table_name}.hamilton_samples', item_id=item.batch_id))
    elif check_name == 'transfer':
        # Clear transfer checks
        item.transfer_check = None
        item.transfer_check_by = None
        item.transfer_check_date = None
        db.session.commit()
        # Redirect to relevant transfer check view
        if item.batch.technique == 'Non-Hamilton':
            return redirect(url_for(f'{table_name}.manual_transfer_check', item_id=item.batch_id))
        else:
            return redirect(url_for(f'{table_name}.hamilton_check', item_id=item.batch_id))
    elif check_name == 'sequence':
        # Clear sequence checks
        item.sequence_check = None
        item.sequence_check_by = None
        item.sequence_check_date = None
        db.session.commit()
        # Redirect to batches.sequence_check
        return redirect(url_for(f'{table_name}.sequence_check', item_id=item.batch_id, is_first='True'))

    # batch = Batches.query.get(item.batch_id)
    # form = BarcodeCheck()
    # assay = batch.assay.assay_name
    # blank = ''
    #
    # for const in BatchConstituents.query.filter_by(batch_id=batch.id):
    #     if const.constituent_type[0:5] == 'Blank' and const.constituent_type != 'Blank (Recon)':
    #         blank = const
    #
    # # Check form submission, source specimen scan and test 1 scan
    # if form.is_submitted() and form.test_specimen.data and form.source_specimen.data:
    #     if ref_table == 'tests':
    #         # Check if item is test
    #         if 'qr_reference: ' in form.test_specimen.data:
    #             # Set relevant data to item
    #             item.specimen_check = QRReference.query.get(form.test_specimen.data.split(' ')[1]).text
    #             item.checked_by = current_user.id
    #             item.checked_date = datetime.now()
    #         else:
    #             # Set relevant data to item
    #             item.specimen_check = 'Complete / Automated'
    #             item.checked_by = current_user.id
    #             item.checked_date = datetime.now()
    #         # Check if assay is GCET and test 2 specimen scan has data
    #         if 'GCET' in assay and form.test_specimen_2:
    #             if 'qr_reference: ' in form.test_specimen_2.data:
    #                 item.gcet_specimen_check = QRReference.query.get(form.test_specimen_2.data.split(' ')[1]).text
    #                 item.gcet_checked_by = current_user.id
    #                 item.gcet_checked_date = datetime.now()
    #             else:
    #                 # Set relevant data
    #                 item.gcet_checked_by = current_user.id
    #                 item.gcet_specimen_check = 'Complete / Automated'
    #                 item.gcet_checked_date = datetime.now()
    #             db.session.commit()
    #         # Commit for non-GCET assay
    #         elif 'GCET' not in assay:
    #             db.session.commit()
    #         # Statement for skipped check in GCET assay
    #         else:
    #             item.gcet_checked_by = current_user.id
    #             item.gcet_specimen_check = 'Skipped'
    #             item.gcet_checked_date = datetime.now()
    #             item.specimen_check = 'Skipped'
    #             item.checked_by = current_user.id
    #             item.checked_date = datetime.now()
    #     # Check if item is batch constituent
    #     elif ref_table == 'batch_constituents':
    #         if 'qr_reference: ' in form.test_specimen.data:
    #             # Set relevant data to item
    #             item.specimen_check = QRReference.query.get(form.test_specimen.data.split(' ')[1]).text
    #             item.specimen_check_by = current_user.id
    #             item.specimen_check_date = datetime.now()
    #         else:
    #             # Set relevant data to item
    #             item.specimen_check = 'Complete / Automated'
    #             item.specimen_check_by = current_user.id
    #             item.specimen_check_date = datetime.now()
    #
    #     db.session.commit()
    #     return redirect(url_for(f'{table_name}.all_tests', item_id=item.batch_id))
    # elif form.is_submitted():
    #     # Scan data missing from at least one field and assay is not GCET
    #     if 'qr_reference: ' in form.test_specimen.data:
    #         # Set relevant data to item
    #         item.specimen_check = QRReference.query.get(form.test_specimen.data.split(' ')[1]).text
    #     elif 'qr_reference: ' in form.source_specimen.data:
    #         # Set relevant data to item
    #         item.specimen_check = QRReference.query.get(form.source_specimen.data.split(' ')[1]).text
    #     else:
    #         # Set relevant skip data
    #         item.specimen_check = 'Skipped'
    #         item.checked_by = current_user.id
    #         item.checked_date = datetime.now()
    #     item.checked_by = current_user.id
    #     item.checked_date = datetime.now()
    #     # Commit
    #     db.session.commit()
    #
    #     if 'GCET' in assay:
    #         # Set relevant skip data
    #         item.gcet_checked_by = current_user.id
    #         item.gcet_specimen_check = 'Skipped'
    #         item.gcet_checked_date = datetime.now()
    #         item.specimen_check = 'Skipped'
    #         item.checked_by = current_user.id
    #         item.checked_date = datetime.now()
    #         # Commit
    #         db.session.commit()
    #         return redirect(url_for(f'{table_name}.all_tests', item_id=item.batch_id))
    #
    #     return redirect(url_for(f'{table_name}.all_tests', item_id=item.batch_id))
    #
    # return render_template(
    #     f'{table_name}/barcode_check.html',
    #     item=item,
    #     form=form,
    #     assay=assay,
    #     blank=blank
    # )


@blueprint.route(f'/{table_name}/<int:item_id>/generate_worklist/<technique>', methods=['GET', 'POST'])
@login_required
def generate_worklist(item_id, technique):
    start_time = datetime.now()

    kwargs = default_kwargs.copy()

    # Make sure pythoncom not initialized already
    pythoncom.CoUninitialize()

    item = Batches.query.get(item_id)

    tests = sorted(Tests.query.filter_by(batch_id=item_id),
                   key=lambda test: test.test_name[-2:] if len(test.test_name) >= 2 else '')

    constituents = BatchConstituents.query.filter_by(batch_id=item_id)

    # Check if worklist already exists and delete if so
    if BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id, BatchRecords.file_type == 'Worklist')).first():
        original = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                  BatchRecords.file_type == 'Worklist')).first()

        kwargs['request'] = 'POST'

        delete_item(form=Add(), item_id=original.id, table=BatchRecords, table_name='batch_records',
                    item_name='Batch Records', name='file_name', admin_only=False, **kwargs)

    # Check which technique to set file name
    if technique == 'Hamilton':
        technique_name = 'Hamilton'
        for test in tests:
            if test.load_check is None or test.load_check == 'N/A':
                test.load_check = None
        for const in constituents:
            if const.load_check is None or const.load_check == 'N/A':
                const.load_check = None
    else:
        technique_name = 'Non-Hamilton'
        for test in tests:
            if test.load_check is None or test.load_check == 'N/A':
                test.load_check = 'N/A'
        for const in constituents:
            if const.load_check is None or const.load_check == 'N/A':
                const.load_check = 'N/A'

    # Set batch technique
    item.technique = technique

    # Initialize COM library
    pythoncom.CoInitialize()

    # Wait for pythoncom to initialize, possibly remove
    time.sleep(1)

    # Get path to label and batch template
    workbook_path = os.path.join(current_app.root_path, 'static/label_and_batch_template',
                                 'Label and Batch Template.xltm')

    # Create Excel object
    excel = client.Dispatch('Excel.Application')
    excel.Visible = False
    excel.DisplayAlerts = False

    # Open label and batch template
    wb = excel.Workbooks.Open(workbook_path)

    # Assign relevant worksheets to later interact with
    ws = wb.Worksheets('from Results Entry')
    tandem_ws = wb.Worksheets('Labels')

    # Set tandem cell in Excel to true to trigger tandem logic
    if item.tandem_id is not None:
        # Excel cell is M5
        tandem_ws.Cells(8, 13).Value = 'TRUE'

    tests = [test for test in Tests.query.filter_by(batch_id=item_id)]

    tests = sorted(
        [test for test in Tests.query.filter_by(batch_id=item_id)],
        key=lambda test: test.test_name[-2:]
    )

    # Increment row to iterate through rows in Excel template
    row = 9  # First row in 'from Results Entry'

    # Loop counter
    counter = 0

    # Input information for Excel template

    # Same values for all tests in batch
    worksheet_ref = tests[0].batch.batch_id  # batch_id

    # Assign assay name
    if 'GCDP' in item.assay.assay_name:
        # Set to Variant if assay is GCDP
        assay = item.gcdp_assay.assay_name
    else:
        assay = tests[0].assay.assay_name  # assay_id

    # Unique values for each test in batch
    test_names = [test.test_name for test in tests]  # test_name
    specimens = [test.specimen.accession_number for test in tests]  # specimen.accession_number
    sample_types = ['[' + test.specimen.type.code + ']' for test in tests]  # specimen.type.code
    directives = [test.directives if test.directives is not None else '' for test in tests]  # directives
    dilutions = [f'(d1/{test.dilution})' if test.dilution is not None and 'HV' not in test.dilution else
                 'HV' if 'HV' in test.dilution else '' for test in tests]
    descriptors = [test.specimen.condition for test in tests]  # specimen.condition

    # Fill in workbook for each case
    while counter <= len(test_names) - 1:
        ws.Cells(row, 1).Value = worksheet_ref
        ws.Cells(row, 2).Value = assay
        ws.Cells(row, 3).Value = worksheet_ref
        ws.Cells(row, 4).Value = test_names[counter]
        ws.Cells(row, 5).Value = specimens[counter]
        ws.Cells(row, 6).Value = sample_types[counter]
        ws.Cells(row, 7).Value = f'{dilutions[counter]} {directives[counter]}'
        ws.Cells(row, 8).Value = descriptors[counter]
        row += 1
        counter += 1

    # Hamilton worksheet which has all necessary information
    out_ws = wb.Worksheets('Hamilton')

    # Select all data from Hamilton worksheet
    output = out_ws.Range('A1', 'K200').Value

    # Initialize output dictionary
    dict_o = {}

    # Unpack output tuple
    for x in output:
        lc_vial, ham_vial, samplename, labware, filter_vial_labware, sample_type, dilution_factor, standard_pos, \
            filter_vial_pos, final_plate_pos, sample_carrier_pos = x

        # Check if there is a standard position and set it to an integer
        if type(standard_pos) == float:
            standard_pos = int(standard_pos)
        else:
            pass

        # Check for relevant information before adding to output dictionary
        if lc_vial == 'DELETE ROW':
            pass
        elif samplename == '   ':
            pass
        elif type(lc_vial) == str:
            dict_o[lc_vial] = [ham_vial, samplename, labware, filter_vial_labware, sample_type,
                               dilution_factor, standard_pos, filter_vial_pos, final_plate_pos,
                               sample_carrier_pos]
        else:
            try:
                # Dictionary of Hamilton worklist
                if dilution_factor == 0.5:
                    dict_o[int(lc_vial)] = [int(ham_vial), samplename, labware, filter_vial_labware, int(sample_type),
                                            float(dilution_factor), standard_pos, filter_vial_pos, final_plate_pos,
                                            sample_carrier_pos]

                    print(f'DICT O: {dict_o}')
                else:
                    dict_o[int(lc_vial)] = [int(ham_vial), samplename, labware, filter_vial_labware, int(sample_type),
                                            int(dilution_factor), standard_pos, filter_vial_pos, final_plate_pos,
                                            sample_carrier_pos]
            except ValueError:
                if dilution_factor == 0.5:
                    dict_o[int(lc_vial)] = [ham_vial, samplename, labware, filter_vial_labware, int(sample_type),
                                            float(dilution_factor), standard_pos, filter_vial_pos, final_plate_pos,
                                            sample_carrier_pos]
                    print(f'DICT O: {dict_o}')

                else:
                    dict_o[int(lc_vial)] = [ham_vial, samplename, labware, filter_vial_labware, int(sample_type),
                                            int(dilution_factor), standard_pos, filter_vial_pos, final_plate_pos,
                                            sample_carrier_pos]

    # Close workbook
    wb.Close(SaveChanges=False)

    # Assign file name and save path for generated worklist
    fname = item.batch_id + ' ' + technique_name + '.xlsx'
    path = os.path.join(current_app.root_path, 'static', 'batch_records', fname)

    # Create a pandas DataFrame from the output dictionary
    df = pd.DataFrame(dict_o)

    # Transpose DataFrame columns to rows to match traditional Hamilton worklist
    df = df.transpose()

    # Create Excel file from DataFrame
    df.to_excel(excel_writer=path, sheet_name='Hamilton', index=False, header=False)

    # Assign values for BatchRecords table addition
    file_dict = {
        'batch_id': item_id,
        'file_name': fname,
        'file_type': 'Worklist',
        'file_path': path,
        'create_date': datetime.now()
    }

    # Add file to BatchRecords table and commit all db changes
    db.session.add(BatchRecords(**file_dict))
    db.session.commit()

    end_time = datetime.now()

    print(f'RESPONSE TIME: {end_time - start_time}')

    # Uninitialize COM Connection
    pythoncom.CoUninitialize()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/tandem', methods=['GET', 'POST'])
@login_required
def tandem(item_id):
    # May have to update - TLD
    form = Tandem()
    item = Batches.query.get(item_id)
    lcci_id = Assays.query.filter_by(assay_name='LCQD-BL').first().id

    batches = [(batch.id, batch.batch_id) for batch in Batches.query.filter(and_(or_(Batches.batch_status ==
                                                                                     'Processing',
                                                                                     Batches.batch_status == 'Pending'),
                                                                                 Batches.assay_id == lcci_id))]

    batches.append((0, 'None'))
    form.tandem_id.choices = batches[::-1]

    if form.is_submitted():
        # Get parent batch id from form
        tandem_batch = form.tandem_id.data

        # Check if batch has already been assigned a parent batch
        if item.tandem_id != 0 and item.tandem_id is not None:
            # Get previous parent batch
            prev_parent_batch = Batches.query.get(item.tandem_id)

            # Set previous parent batch tandem id back to None
            prev_parent_batch.tandem_id = None

        # Check if there is a new parent batch
        if tandem_batch != 0:
            # Get new parent batch query object
            parent_batch = Batches.query.get(tandem_batch)

            # Set new parent batch tandem id attribute to the parent batch id
            parent_batch.tandem_id = tandem_batch

        # Set parent tandem id attribute to its own id
        item.tandem_id = tandem_batch

        # Add in attributes that child batch will inherit

        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    return render_template(
        f'{table_name}/tandem.html',
        item=item,
        form=form
    )


@blueprint.route(f'/{table_name}/<int:item_id>/clear', methods=['GET', 'POST'])
@login_required
def clear(item_id):
    item = Batches.query.get(item_id)
    to_clear = request.args.get('to_clear')

    # Clear relevant batch date (Admin)
    if to_clear == 'extracting':
        if item.extraction_finish_date_3 is not None:
            item.extraction_finish_date_3 = None
        elif item.extraction_finish_date_2 is not None:
            item.extraction_finish_date_2 = None
        elif item.extraction_finish_date is not None:
            item.extraction_finish_date = None
    elif to_clear == 'processing':
        if item.process_finish_date_3 is not None:
            item.process_finish_date = None
        elif item.process_finish_date_2 is not None:
            item.process_finish_date = None
        elif item.process_finish_date is not None:
            item.process_finish_date = None
    elif to_clear == 'review':
        if item.review_finish_date_3 is not None:
            item.review_finish_date = None
        elif item.review_finish_date_2 is not None:
            item.review_finish_date = None
        elif item.review_finish_date is not None:
            item.review_finish_date = None
        item.batch_status = 'Processing'

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item.id))


@blueprint.route(f'/{table_name}/<int:item_id>/print', methods=['GET', 'POST'])
@login_required
def print_labels(item_id):
    item = Batches.query.get(item_id)
    extraction_type = item.assay.assay_name

    headers = SequenceHeaderMappings.query.filter_by(batch_template_id=item.batch_template_id).first()

    # Set label type based on extraction type
    if 'COHB' in extraction_type or 'PRIM' in extraction_type:
        label_attributes = fields_dict['extraction_cohb']
    else:
        label_attributes = fields_dict['extraction']

    # Default printer for extraction labels
    printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 - Extraction'

    tests = Tests.query.filter_by(batch_id=item_id).all()

    if 'GCET' in extraction_type:
        tests.sort(key=lambda t: t.vial_position)

    constituents = BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item_id,
                                                       BatchConstituents.populated_from != 'Manual'))

    # Set relevant label_attributes based on extraction type and print for each test and constituent (if applicable)
    if 'COHB' in extraction_type or 'PRIM' in extraction_type:
        attributes_list = []
        for test in tests:
            qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'test{test.id}.png')
            qrcode.make(f'tests: {test.id}').save(qr_path)
            label_attributes['CASE_NUM'] = test.case.case_number
            label_attributes['TEST_NAME'] = test.test_name.split(' ')[2]
            label_attributes['ACC_NUM'] = test.specimen.accession_number

            with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

            label_attributes['QR'] = qr_encoded
            label_attributes['CASE_NUM_1'] = test.case.case_number
            label_attributes['TEST_NAME_1'] = test.test_name.split(' ')[2]
            label_attributes['ACC_NUM_1'] = test.specimen.accession_number

            label_attributes['QR_1'] = qr_encoded
            label_attributes['amount'] += 1

            attributes_list.append(label_attributes.copy())

        for const in constituents:
            qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'const{const.id}.png')
            qrcode.make(f'batch_constituents: {const.id}').save(qr_path)
            label_attributes['CASE_NUM'] = const.constituent_type
            label_attributes['TEST_NAME'] = ''
            label_attributes['ACC_NUM'] = ''

            with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

            label_attributes['QR'] = qr_encoded
            label_attributes['CASE_NUM_1'] = const.constituent_type
            label_attributes['TEST_NAME_1'] = ''
            label_attributes['ACC_NUM_1'] = ''
            label_attributes['QR_1'] = qr_encoded
            label_attributes['amount'] += 1

            attributes_list.append(label_attributes.copy())

    elif 'SAMQ' in item.assay.assay_name:

        attributes_list = []

        # Get sequence for batch
        sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                  BatchRecords.file_type == 'Sequence')).first()

        seq_df = pd.read_csv(sequence.file_path)

        sequence_dict = {y[headers.vial_position]: [y[headers.sample_name], y['SampleID']] for x, y in
                         seq_df.iterrows()}

        counter = 0

        for test in tests:
            sample_type = extract_suffix(test.test_name) if extract_suffix(test.test_name) is not None else 'Case'

            qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'tests{test.id}.png')
            qrcode.make(f'tests: {test.id}').save(qr_path)

            with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

            label_attributes['CASE_NUM'] = test.case.case_number
            label_attributes['TEST_NAME'] = sample_type
            label_attributes['ACC_NUM'] = test.specimen.accession_number
            label_attributes['VIAL_POS'] = test.vial_position
            label_attributes['QR'] = qr_encoded
            label_attributes['HAMILTON_SC'] = sample_type
            label_attributes['HAMILTON_FV'] = ''
            label_attributes['CASE_NUM_1'] = test.case.case_number
            label_attributes['TEST_NAME_1'] = sample_type
            label_attributes['ACC_NUM_1'] = test.specimen.accession_number
            label_attributes['VIAL_POS_1'] = test.vial_position
            label_attributes['QR_1'] = qr_encoded
            label_attributes['HAMILTON_SC_1'] = sample_type
            label_attributes['HAMILTON_FV_1'] = ''

            attributes_list.append(label_attributes.copy())

        print(f'ATTRIBUTES LIST LEN: {len(attributes_list)}')

        for k, v in sequence_dict.items():

            if 'Blank' in v[0]:
                if 'Recon' in v[0]:
                    constituent = BatchConstituents.query.filter_by(batch_id=item_id,
                                                                    constituent_type='Reconstitution Mix').first()
                else:
                    constituent = BatchConstituents.query.filter_by(batch_id=item_id, constituent_type=v[0]).first()

                qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                       f'batch_constituents{constituent.id}.png')
                qrcode.make(f'batch_constituents: {constituent.id}').save(qr_path)

                with open(qr_path, "rb") as qr_file:
                    qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                label_attributes['CASE_NUM'] = v[0]
                label_attributes['TEST_NAME'] = ''
                label_attributes['ACC_NUM'] = ''
                label_attributes['VIAL_POS'] = k
                label_attributes['QR'] = qr_encoded
                label_attributes['HAMILTON_SC'] = ''
                label_attributes['HAMILTON_FV'] = ''
                label_attributes['CASE_NUM_1'] = v[0]
                label_attributes['TEST_NAME_1'] = ''
                label_attributes['ACC_NUM_1'] = ''
                label_attributes['VIAL_POS_1'] = k
                label_attributes['QR_1'] = qr_encoded
                label_attributes['HAMILTON_SC_1'] = ''
                label_attributes['HAMILTON_FV_1'] = ''

                attributes_list.append(label_attributes.copy())

                # test = Tests.query.filter_by(batch_id=item_id, vial_position=k).first()
                # print(f'TEST: {test}')
                # qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'tests{test.id}.png')
                # qrcode.make(f'tests: {test.id}').save(qr_path)
                #
                # with open(qr_path, "rb") as qr_file:
                #     qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')
                #
                # label_attributes['CASE_NUM'] = v[0].split(' ')[0]
                # label_attributes['TEST_NAME'] = v[0].split(' ')[2]
                # label_attributes['ACC_NUM'] = v[0].split(' ')[1]
                # label_attributes['VIAL_POS'] = k
                # label_attributes['QR'] = qr_encoded
                # label_attributes['HAMILTON_SC'] = sample_type
                # label_attributes['HAMILTON_FV'] = ''
                # label_attributes['CASE_NUM_1'] = v[0].split(' ')[0]
                # label_attributes['TEST_NAME_1'] = v[0].split(' ')[2]
                # label_attributes['ACC_NUM_1'] = v[0].split(' ')[1]
                # label_attributes['VIAL_POS_1'] = k
                # label_attributes['QR_1'] = qr_encoded
                # label_attributes['HAMILTON_SC_1'] = sample_type
                # label_attributes['HAMILTON_FV_1'] = ''
                #
                # attributes_list.append(label_attributes.copy())

            # else:
            #     qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'samq_const{counter}.png')
            #     qrcode.make(f'placeholder').save(qr_path)
            #
            #     with open(qr_path, "rb") as qr_file:
            #         qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')
            #
            #
            #     label_attributes['CASE_NUM'] = v[0]
            #     label_attributes['TEST_NAME'] = ''
            #     label_attributes['ACC_NUM'] = ''
            #     label_attributes['VIAL_POS'] = k
            #     label_attributes['QR'] = qr_encoded
            #     label_attributes['HAMILTON_SC'] = ''
            #     label_attributes['HAMILTON_FV'] = ''
            #     label_attributes['CASE_NUM_1'] = v[0]
            #     label_attributes['TEST_NAME_1'] = ''
            #     label_attributes['ACC_NUM_1'] = ''
            #     label_attributes['VIAL_POS_1'] = k
            #     label_attributes['QR_1'] = qr_encoded
            #     label_attributes['HAMILTON_SC_1'] = ''
            #     label_attributes['HAMILTON_FV_1'] = ''
            #
            #     attributes_list.append(label_attributes.copy())

    #
    #     qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'tests{test.id}.png')
    #     qrcode.make(f'tests: {test.id}').save(qr_path)
    #     label_attributes['CASE_NUM'] = test.case.case_number
    #     label_attributes['TEST_NAME'] = test.test_name.split(' ')[2]
    #     label_attributes['ACC_NUM'] = test.specimen.accession_number
    #     label_attributes['QR'] = qr_path
    #     label_attributes['CASE_NUM_1'] = test.case.case_number
    #     label_attributes['TEST_NAME_1'] = test.test_name.split(' ')[2]
    #     label_attributes['ACC_NUM_1'] = test.specimen.accession_number
    #     label_attributes['QR_1'] = qr_path

    else:

        attributes_list = []

        # Get worklist for batch
        worklist = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                  BatchRecords.file_type == 'Worklist')).first()

        # Get sequence for batch
        sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                  BatchRecords.file_type == 'Sequence')).first()

        # Create worklist and sequence dataframes
        df = pd.read_excel(worklist.file_path)
        seq_df = pd.read_csv(sequence.file_path)

        # Dictionary of non-standards sample name keys with filter vial and carrier pos values if item is sample
        if 'GCET' in item.assay.assay_name:
            worklist_dict = {y['SampleName'].rstrip(): [f"{y['FilterVialLabware']}-{y['FilterVialPos']}",
                                                        y['SampleCarrierPos']] for x, y in df.iterrows()
                             if y['Type'] == 1
                             }
            # Set GCET constituents for label printing
            consts = ['QC 0.040', 'QC 0.150', 'QC VOL', 'CALIB ETOH 0.010', 'CALIB ETOH 0.080',
                      'CALIB ETOH 0.100', 'CALIB ETOH 0.200', 'CALIB ETOH 0.300', 'CALIB ETOH 0.500',
                      'CALIB VOL 0.010', 'CALIB VOL 0.050', 'CALIB VOL 0.150', 'BLANK (dH2O)', 'BLANK + ISTD']

            # const_dict = {y['Vial']: [y['SampleName'],
            #                           f"{y['FilterVialLabware']}-{y['FilterVialPos']}"
            #                           if pd.notna(y['FilterVialPos']) else '',
            #                           y['SampleCarrierPos'] if pd.notna(y['SampleCarrierPos']) else ''] for x, y in
            #               df.iterrows() if y['SampleName'] in consts}

            const_dict = {const.vial_position: [const.constituent_type, '', ''] for const in constituents}

        else:
            worklist_dict = {y['SampleName'].rstrip(): [f"{y['FilterVialLabware'][-1]}-{y['FilterVialPos']}",
                                                        y['SampleCarrierPos']] for x, y in df.iterrows()
                             if y['Type'] == 1
                             }
            # Dictionary of constituents for non-sample items
            const_dict = {y['Vial']: [y['SampleName'],
                                      f"{y['FilterVialLabware'][-1]}-{y['FilterVialPos']}"
                                      if pd.notna(y['FilterVialPos']) else
                                      f"{y['FilterVialLabware'][-1]}-{y['FinalPlatePos']}",
                                      y['SampleCarrierPos'] if pd.notna(y['SampleCarrierPos']) else ''] for x, y in
                          df.iterrows() if y['Type'] != 1 or 'Blank' in y['SampleName']}

            print(f'CONST DICT 1: {const_dict}')
            updated_dict = {}

            for k, v in list(const_dict.items()):
                updated = False  # Track whether the key was updated

                for _, y in seq_df.iterrows():
                    if v[0] == y[headers.sample_name] and v[0] != 'Blank (Recon)':
                        print(f'V: {v[0]}')
                        print(f'SAMPLE NAME: {y[headers.sample_name]}')
                        print(f'VIAL POS: {y[headers.vial_position]}')

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
            print(f"CONST DICT: {const_dict}")

        # Handle printing for GCET, only need one label per sample
        # Includes logic to still use 2UP labels
        # Even counter numbers go on the bottom label and odd counter numbers go on top label
        if 'GCET' in item.assay.assay_name:
            counter = 1

            # Set label attributes for constituents
            for k, v in const_dict.items():
                # Set relevant label attributes depending on where the counter is 
                if (counter % 2) == 0:
                    label_attributes['CASE_NUM_1'] = v[0]
                    label_attributes['TEST_NAME_1'] = ''
                    label_attributes['ACC_NUM_1'] = ''

                else:
                    label_attributes['CASE_NUM'] = v[0]
                    label_attributes['TEST_NAME'] = ''
                    label_attributes['ACC_NUM'] = ''

                # Get relevant constituent data
                for const in constituents:
                    const.label_made = False
                    if v[0] == const.constituent_type and k == const.vial_position and not const.label_made:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'const{const.id}.png')
                        qrcode.make(f'batch_constituents: {const.id}').save(qr_path)

                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        const.label_made = True
                        db.session.commit()
                        
                        # Set relevant label attributes depending on where the counter is
                        if (counter % 2) == 0:
                            label_attributes['VIAL_POS_1'] = const.vial_position
                            label_attributes['QR_1'] = qr_encoded
                        else:
                            label_attributes['VIAL_POS'] = const.vial_position
                            label_attributes['QR'] = qr_encoded
                        if item.technique == 'Hamilton':
                            if (counter % 2) == 0:
                                label_attributes['HAMILTON_FV_1'] = v[1]
                                label_attributes['HAMILTON_SC_1'] = v[2]
                            else:
                                label_attributes['HAMILTON_FV'] = v[1]
                                label_attributes['HAMILTON_SC'] = v[2]
                        else:
                            if (counter % 2) == 0:
                                label_attributes['HAMILTON_FV_1'] = ''
                                label_attributes['HAMILTON_SC_1'] = ''
                            else:
                                label_attributes['HAMILTON_FV'] = ''
                                label_attributes['HAMILTON_SC'] = ''

                        label_attributes['amount'] += 1

                        # Only add to attributes list if it bottom label
                        # This fixes duplicate labels being added
                        if (counter % 2) == 0:
                            attributes_list.append(label_attributes.copy())
                        # Add if it is the top label and last label
                        elif counter == len(const_dict.items()):
                            attributes_list.append(label_attributes.copy())

                counter += 1

            counter = 1

            for test in tests:
                qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'tests{test.id}.png')
                qrcode.make(f'tests: {test.id}').save(qr_path)

                with open(qr_path, "rb") as qr_file:
                    qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                # Set relevant label attributes depending on where the counter is
                if (counter % 2) == 0:
                    label_attributes['CASE_NUM_1'] = test.case.case_number
                    label_attributes['TEST_NAME_1'] = test.test_name.split(' ')[2]
                    label_attributes['ACC_NUM_1'] = test.specimen.accession_number
                    label_attributes['QR_1'] = qr_encoded
                else:
                    label_attributes['CASE_NUM'] = test.case.case_number
                    label_attributes['TEST_NAME'] = test.test_name.split(' ')[2]
                    label_attributes['ACC_NUM'] = test.specimen.accession_number
                    label_attributes['QR'] = qr_encoded

                # Set relevant extraction data for non COHB/PRIM and for Manual vs Automated batches
                if 'COHB' not in extraction_type and 'PRIM' not in extraction_type:
                    if test.dilution == 'HV':
                        if (counter % 2) == 0:
                            label_attributes['VIAL_POS_1'] = f'{test.vial_position}*'
                        else:
                            label_attributes['VIAL_POS'] = f'{test.vial_position}*'
                    else:
                        if (counter % 2) == 0:
                            label_attributes['VIAL_POS_1'] = test.vial_position
                        else:
                            label_attributes['VIAL_POS'] = test.vial_position

                    if item.technique == 'Hamilton':
                        # Set relevant label attributes depending on where the counter is
                        if (counter % 2) == 0:
                            label_attributes['HAMILTON_FV_1'] = worklist_dict[test.test_name][0]
                            label_attributes['HAMILTON_SC_1'] = worklist_dict[test.test_name][1]
                        else:                    
                            label_attributes['HAMILTON_FV'] = worklist_dict[test.test_name][0]
                            label_attributes['HAMILTON_SC'] = worklist_dict[test.test_name][1]
                    else:
                        if (counter % 2) == 0:
                            label_attributes['HAMILTON_FV_1'] = ''
                            label_attributes['HAMILTON_SC_1'] = ''
                        else:
                            label_attributes['HAMILTON_FV'] = ''
                            label_attributes['HAMILTON_SC'] = ''

                label_attributes['amount'] += 1

                # Only add to attributes list if it bottom label
                # This fixes duplicate labels being added
                if (counter % 2) == 0:
                    attributes_list.append(label_attributes.copy())
                # Add bottom label if last label
                elif counter == len(const_dict.items()):
                    # Clear bottom label attributes before adding
                    label_attributes['CASE_NUM_1'] = ''
                    label_attributes['TEST_NAME_1'] = ''
                    label_attributes['ACC_NUM_1'] = ''
                    label_attributes['QR_1'] = ''
                    label_attributes['VIAL_POS_1'] = ''
                    label_attributes['HAMILTON_FV_1'] = ''
                    label_attributes['HAMILTON_SC_1'] = ''
                    attributes_list.append(label_attributes.copy())

                counter += 1

        else:
            # Set label attributes for constituents
            for k, v in const_dict.items():
                label_attributes['CASE_NUM'] = v[0]
                label_attributes['TEST_NAME'] = ''
                label_attributes['ACC_NUM'] = ''
                label_attributes['CASE_NUM_1'] = v[0]
                label_attributes['TEST_NAME_1'] = ''
                label_attributes['ACC_NUM_1'] = ''

                # Get relevant constituent data
                for const in constituents:
                    const.label_made = False
                    if v[0] == const.constituent_type and k == const.vial_position and not const.label_made:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'const{const.id}.png')
                        qrcode.make(f'batch_constituents: {const.id}').save(qr_path)

                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        const.label_made = True
                        db.session.commit()
                        label_attributes['VIAL_POS'] = const.vial_position
                        label_attributes['QR'] = qr_encoded
                        label_attributes['VIAL_POS_1'] = const.vial_position
                        label_attributes['QR_1'] = qr_encoded
                        if item.technique == 'Hamilton':
                            label_attributes['HAMILTON_FV'] = v[1]
                            label_attributes['HAMILTON_SC'] = v[2]
                            label_attributes['HAMILTON_FV_1'] = v[1]
                            label_attributes['HAMILTON_SC_1'] = v[2]
                        else:
                            label_attributes['HAMILTON_FV'] = ''
                            label_attributes['HAMILTON_SC'] = ''
                            label_attributes['HAMILTON_FV_1'] = ''
                            label_attributes['HAMILTON_SC_1'] = ''

                        label_attributes['amount'] += 1
                        attributes_list.append(label_attributes.copy())

        if 'LCCI' not in item.assay.assay_name and 'GCET' not in item.assay.assay_name:
            for test in tests:
                qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'tests{test.id}.png')
                qrcode.make(f'tests: {test.id}').save(qr_path)

                with open(qr_path, "rb") as qr_file:
                    qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                label_attributes['CASE_NUM'] = test.case.case_number
                label_attributes['TEST_NAME'] = test.test_name.split(' ')[2]
                label_attributes['ACC_NUM'] = test.specimen.accession_number
                label_attributes['QR'] = qr_encoded
                label_attributes['CASE_NUM_1'] = test.case.case_number
                label_attributes['TEST_NAME_1'] = test.test_name.split(' ')[2]
                label_attributes['ACC_NUM_1'] = test.specimen.accession_number
                label_attributes['QR_1'] = qr_encoded

                # Set relevant extraction data for non COHB/PRIM and for Manual vs Automated batches
                if 'COHB' not in extraction_type and 'PRIM' not in extraction_type:
                    if test.dilution == 'HV':
                        label_attributes['VIAL_POS'] = f'{test.vial_position}*'
                        label_attributes['VIAL_POS_1'] = f'{test.vial_position}*'
                    else:
                        label_attributes['VIAL_POS'] = test.vial_position
                        label_attributes['VIAL_POS_1'] = test.vial_position
                    if item.technique == 'Hamilton':
                        label_attributes['HAMILTON_FV'] = worklist_dict[test.test_name][0]
                        label_attributes['HAMILTON_SC'] = worklist_dict[test.test_name][1]
                        label_attributes['HAMILTON_FV_1'] = worklist_dict[test.test_name][0]
                        label_attributes['HAMILTON_SC_1'] = worklist_dict[test.test_name][1]
                    else:
                        label_attributes['HAMILTON_FV'] = ''
                        label_attributes['HAMILTON_SC'] = ''
                        label_attributes['HAMILTON_FV_1'] = ''
                        label_attributes['HAMILTON_SC_1'] = ''

                label_attributes['amount'] += 1
                attributes_list.append(label_attributes.copy())
    # print(f'ATTRIBUTES LIST: {attributes_list}')
    for each in attributes_list:
        print(f'NAME: {each["CASE_NUM"]}')

    # print_label(printer, attributes_list)
    # print(f'ATTRIBUTES_LIST: {json.dumps(attributes_list, indent=2)}')

    # Currently set to print only 1 label
    # for test in tests:
    #     if count < 1:
    #         print_tests(test)
    #         count += 1
    #     else:
    #         break

    # return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # dual_printer = True
    # roll = 0
    # return True
    return jsonify(attributes_list, printer, None, None, url_for(f'{table_name}.view', item_id=item_id, _external=True))


@blueprint.route(f'/{table_name}/<int:item_id>/hamilton', methods=['GET', 'POST'])
@login_required
def hamilton_check(item_id):
    item = Batches.query.get(item_id)

    read_only = request.args.get('read_only')

    # Get batch constituents
    constituents = [(item.constituent.lot, item.id, item.constituent_type) for item in
                    BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item.id,
                                                        BatchConstituents.constituent_id != '',
                                                        BatchConstituents.include_checks == True))]

    # Get worklist for batch
    worklist = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                              BatchRecords.file_type == 'Worklist')).first()

    # Create worklist dataframe
    df = pd.read_excel(worklist.file_path)

    # Assign check form
    form = HamiltonCheck()

    # Initialize relevant arrays and dict
    plate_1 = []
    plate_2 = []
    plate_1_scan = []
    plate_2_scan = []
    p1_qr_scan = []
    p2_qr_scan = []

    worklist_dict = {}

    # Create array of relevant letters for plate layout and initialize alphanumeric array
    alpha = ['A', 'B', 'C', 'D', 'E', 'F']
    alphanumeric = []

    # Create dictionary of possible LCQD constituents
    constituent_pairs = {'QL1 (LCQD) A': 'None Selected', 'QL1 (LCQD) B': 'None Selected',
                         'QH1 (LCQD) A': 'None Selected', 'QL2 (LCQD) A': 'None Selected',
                         'QH2 (LCQD) A': 'None Selected', 'QL2 (LCQD) B': 'None Selected',
                         'QL3 (LCQD) A': 'None Selected', 'QH1 (LCQD) B': 'None Selected',
                         'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                         'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                         'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                         'Calibrator 7': 'None Selected', 'LOD (LCQD) A': 'None Selected',
                         'LOD (LCQD) B': 'None Selected', 'Blank (Blood)': 'None Selected',
                         'Blank (Urine)': 'None Selected', 'Blank (Recon)': 'None Selected'
                         }

    # Search for relevant identifier in constituent lot
    # Assign matching constituents relevant BatchConstituent table ID
    for constituent in constituents:
        constituent_pairs[constituent[2]] = constituent[1]

    # Create array of all alphanumeric plate positions
    for letter in alpha:
        for number in range(1, 9):
            alphanumeric.append(letter + str(number))

    # Create dictionary of samples with associate plate position and Tests table ID
    for x, y in df.iterrows():  # x is the index, y can access column names
        worklist_dict[y['Vial']] = {'samplename': y['SampleName'], 'platepos': y['FinalPlatePos'],
                                    'filterviallw': y['FilterVialLabware'],
                                    'test_id': Tests.query.filter(and_(Tests.batch_id == item_id,
                                                                       Tests.test_name ==
                                                                       y['SampleName'].strip())).value(Tests.id)}

        # Create Plate 1 and Plate 2 arrays with relevant sample name, plate position and Tests table ID
        if y['FilterVialLabware'] == 'Thomson_Filter_Vials_0001':
            plate_1.append([y['SampleName'].strip(), y['FinalPlatePos'],
                            Tests.query.filter(and_(Tests.batch_id == item_id,
                                                    Tests.test_name == y['SampleName'].strip())).value(Tests.id),
                            'test'
                            ])

        elif y['FilterVialLabware'] == 'Thomson_Filter_Vials_0002':
            plate_2.append([y['SampleName'].strip(), y['FinalPlatePos'],
                            Tests.query.filter(and_(Tests.batch_id == item_id,
                                                    Tests.test_name == y['SampleName'].strip())).value(Tests.id),
                            'test'
                            ])

    # Initialize plates with already checked tests/constituents
    p1_checks = []
    p2_checks = []

    blanks = BatchConstituents.query.filter_by(batch_id=item_id, constituent_type='Blank (Recon)').all()

    if item.tandem_id:
        blanks.extend(BatchConstituents.query.filter_by(batch_id=item.tandem_id,
                                                        constituent_type='Blank (Recon)').all())

    # Search constituent pairs dict for constituent name and assign BatchRecords table ID to matching constituents
    for sample in plate_1:
        if sample[0] in constituent_pairs.keys():
            sample[2] = constituent_pairs[sample[0]]
            sample[3] = 'batch_constituent'

    counter = 0

    # Build plate 1 checked tests/constituents with sample ID, sample plate position and check status
    for sample in plate_1:
        # if sample[0] == 'Blank (Recon)':
        #     p1_checks.append([sample[2], sample[1], 'None Selected'])
        if sample[0] == 'Blank (Recon)':
            sample[2] = blanks[counter].id
            sample[3] = 'batch_constituent'
            p1_checks.append([blanks[counter].id, sample[1],
                              BatchConstituents.query.get(blanks[counter].id).transfer_check])
            counter += 1
        elif sample[2] is None or sample[2] == 'None Selected':
            p1_checks.append([sample[2], sample[1], 'None Selected'])
        elif sample[0] in constituent_pairs.keys():
            p1_checks.append([sample[2], sample[1], BatchConstituents.query.get(sample[2]).transfer_check])
        else:
            p1_checks.append([sample[2], sample[1], Tests.query.get(sample[2]).transfer_check])

    # Build plate 2 checked tests/constituents with sample ID, sample plate position and check status
    for sample in plate_2:
        # if sample[0] == 'Blank (Recon)':
        #     p2_checks.append([sample[2], sample[1], 'None Selected'])
        if sample[0] == 'Blank (Recon)':
            try:
                sample[2] = blanks[counter].id
                sample[3] = 'batch_constituent'
                p2_checks.append([blanks[counter].id, sample[1],
                                  BatchConstituents.query.get(blanks[counter].id).transfer_check])
                counter += 1
            except IndexError:
                pass
        elif sample[2] is None or sample[2] == 'None Selected':
            p2_checks.append([sample[2], sample[1], None])
        elif sample[0] in constituent_pairs.keys():
            p2_checks.append([sample[2], sample[1], BatchConstituents.query.get(sample[2]).transfer_check])
        else:
            p2_checks.append([sample[2], sample[1], Tests.query.get(sample[2]).transfer_check])

    # Assign blank positions for plate positions that do not have samples associated
    for an in alphanumeric:
        if any(item[1] == an for item in plate_1):
            pass
        else:
            plate_1.append(['', an, '', ''])

        if any(item[1] == an for item in p1_checks):
            pass
        else:
            p1_checks.append(['', an, None, ''])

        if any(item[1] == an for item in plate_2):
            pass
        else:
            plate_2.append(['', an, '', ''])

        if any(item[1] == an for item in p2_checks):
            pass
        else:
            p2_checks.append(['', an, None, ''])

    if form.is_submitted() and form.validate():
        for field in form:
            # Get test_id from field.data
            if field.name == 'submit' or field.name == 'csrf_token':
                scan_id = None
                scan_table = None
            # Make sure field data is present adn assign scan_id
            elif field.data != '':
                scan_id = field.data.split()[1]
                # Assign relevant table for querying
                if field.data.split()[0][:-1] == 'tests':
                    scan_table = Tests
                elif field.data.split()[0][:-1] == 'batch_constituents':
                    scan_table = BatchConstituents
                elif field.data.split()[0][:-1] == 'qr_reference':
                    scan_table = QRReference
                else:
                    pass
            else:
                scan_id = None
                scan_table = None

            # If field is for plate 1 and field is not date field
            if field.name[:2] == 'p1' and field.name[-4:] != 'date':
                # Build array of arrays for scanned tests in plate 1
                if scan_id is not None and scan_table == Tests:
                    for search in form:
                        # Assign datestamp to scan
                        if search.name[:2] == 'p1' and search.name[2:4] == field.name[-2:] and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    plate_1_scan.append([field.name[-2:], scan_table.query.get(scan_id).test_name, scan_id, field_date,
                                         scan_table])
                elif scan_id is not None and scan_table == BatchConstituents:
                    for search in form:
                        # Assign datestamp to scan
                        if search.name[:2] == 'p1' and search.name[2:4] == field.name[-2:] and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    plate_1_scan.append([field.name[-2:], scan_table.query.get(scan_id).constituent.constituent.name,
                                         scan_id, field_date, scan_table])
                elif scan_id is not None and scan_table == QRReference:
                    plate_position = field.name[-2:].upper()
                    for sample in plate_1:
                        if sample[1] == plate_position:
                            # Assign relevant data to qr_scan array. scan_id and scan_table refer to QRReference
                            if sample[3] == 'test':
                                for search in form:
                                    # Assign datestamp to scan
                                    if search.name[:2] == 'p1' and search.name[2:4] == field.name[-2:] and \
                                            search.name[-4:] == 'date':
                                        field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                                p1_qr_scan.append([field.name[-2:], Tests.query.get(sample[2]), scan_id, field_date,
                                                   scan_table])
                            elif sample[3] == 'batch_constituent':
                                # Assign datestamp to scan
                                if search.name[:2] == 'p1' and search.name[2:4] == field.name[-2:] and \
                                        search.name[-4:] == 'date':
                                    field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                                p1_qr_scan.append([field.name[-2:], BatchConstituents.query.get(sample[2]), scan_id,
                                                   field_date, scan_table])
                else:
                    plate_1_scan.append([field.name[-2:], scan_id, scan_id, scan_id, scan_id])
            # If field is for plate 2
            elif field.name[:2] == 'p2' and field.name[-4:] != 'date':
                # Build array of tuples for scanned tests in plate 2
                if scan_id is not None and scan_table == Tests:
                    for search in form:
                        if search.name[:2] == 'p2' and search.name[2:4] == field.name[-2:] and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    plate_2_scan.append([field.name[-2:], scan_table.query.get(scan_id).test_name, scan_id, field_date,
                                         scan_table])
                elif scan_id is not None and scan_table == BatchConstituents:
                    for search in form:
                        if search.name[:2] == 'p2' and search.name[2:4] == field.name[-2:] and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    plate_2_scan.append([field.name[-2:], scan_table.query.get(scan_id).constituent.constituent.name,
                                         scan_id, field_date, scan_table])
                elif scan_id is not None and scan_table == QRReference:
                    plate_position = field.name[-2:].upper()
                    for sample in plate_2:
                        if sample[1] == plate_position:
                            # Assign relevant data to qr_scan array. scan_id and scan_table refer to QRReference
                            if sample[3] == 'test':
                                for search in form:
                                    if search.name[:2] == 'p2' and search.name[2:4] == field.name[-2:] and \
                                            search.name[-4:] == 'date':
                                        field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                                p2_qr_scan.append([field.name[-2:], Tests.query.get(sample[2]), scan_id, field_date,
                                                   scan_table])
                            elif sample[3] == 'batch_constituent':
                                for search in form:
                                    if search.name[:2] == 'p2' and search.name[2:4] == field.name[-2:] and \
                                            search.name[-4:] == 'date':
                                        field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                                p2_qr_scan.append([field.name[-2:], BatchConstituents.query.get(sample[2]), scan_id,
                                                   field_date, scan_table])

                else:
                    plate_2_scan.append([field.name[-2:], scan_id, scan_id, scan_id, scan_id])

        # Compare scan plate 1 to plate 1 key
        # [v == field.name (e.g., a1), w == test_name, x == scan_id, y == field_date, z == scan_table]
        for v, w, x, y, z in plate_1_scan:
            for a, b, c, d in plate_1:  # [a == SampleName, b == FinalPlatePos, c == test_id, d == test or batch const]
                if x is None:
                    continue
                # Check if plate positions match
                elif v == b.lower():
                    # Check if test ids match
                    if int(x) == c:
                        z.query.get(x).transfer_check_by = current_user.id
                        z.query.get(x).transfer_check_date = y
                        z.query.get(x).transfer_check = 'Completed / Automated'
                        db.session.commit()

        for v, w, x, y, z in plate_2_scan:
            for a, b, c, d in plate_2:  # [a == SampleName, b == FinalPlatePos, c == test_id, d == batch const]
                if x is None:
                    continue
                # Check if plate positions match
                elif v == b.lower():
                    # Check if test ids match
                    if int(x) == c:
                        z.query.get(x).transfer_check_by = current_user.id
                        z.query.get(x).transfer_check_date = y
                        z.query.get(x).transfer_check = 'Completed / Automated'
                        db.session.commit()

        # Set transfer checks for relevant plate
        # [v == field.name (e.g., a1), w == Tests ORM, x == scan_id, y == field_date, z == QRReference table]
        for v, w, x, y, z in p1_qr_scan:
            w.transfer_check_by = current_user.id
            w.transfer_check_date = y
            w.transfer_check = z.query.get(x).text

        for v, w, x, y, z in p2_qr_scan:
            w.transfer_check_by = current_user.id
            w.transfer_check_date = y
            w.transfer_check = z.query.get(x).text

        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    print(f'Plate2 {plate_2}')

    if read_only:
        return render_template(
            f'{table_name}/hamilton_transfer_read.html',
            item=item,
            plate_1=plate_1,
            plate_2=plate_2,
            form=form,
            p1_checks=p1_checks,
            p2_checks=p2_checks,
        )

    return render_template(
        f'{table_name}/hamilton_check.html',
        item=item,
        plate_1=plate_1,
        plate_2=plate_2,
        form=form,
        p1_checks=p1_checks,
        p2_checks=p2_checks,
    )


@blueprint.route(f'/{table_name}/<int:item_id>/scan_resources', methods=['GET', 'POST'])
@login_required
def scan_resources(item_id):
    kwargs = default_kwargs.copy()
    item = Batches.query.get(item_id)
    assay = item.assay
    form = ResourcesBarcode()
    field_data = {}
    print(f"Inside scan_resources")

    constituents = [(item.id, item.lot) for item in
                    StandardsAndSolutions.query.filter(and_(StandardsAndSolutions.assay.contains(str(assay.id)),
                                                            StandardsAndSolutions.in_use == False))]

    # Get any assigned constituents
    selected_constituents = [item.constituent_id for item in BatchConstituents.query.filter_by(batch_id=item_id)]

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            field_data.update({
                'db_status': 'Active',
                'locked': False,
                'create_date': datetime.now(),
                'created_by': current_user.initials,
                'revision': 0
            })

            for const in form.constituent_id.data:
                field_data.update({
                    'batch_id': item.id,
                    'constituent_id': const
                })

            to_add = BatchConstituents(**field_data)

            db.session.add(to_add)
            db.session.commit()

            return redirect(url_for(f'{table_name}.view', item_id=item_id))

            # # Create sequence file
            # if item.batch_template_id != form.batch_template_id.data:
            #     batch_template_id = form.batch_template_id.data
            #     batch_template_name = BatchTemplates.query.get(batch_template_id).name
            #     df = pd.read_csv(
            #         os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template_name}.csv"),
            #         encoding="ISO-8859-1")
            #     headers = SequenceHeaderMappings.query.filter_by(batch_template_id=batch_template_id).first()
            #     sample_idx = df[df[headers.sample_name].isna()].index
            #
            #     for n, test in enumerate(Tests.query.filter_by(batch_id=item_id)):
            #         idx = sample_idx[n]
            #         df.loc[idx, headers.sample_name] = test.test_name
            #         df.loc[idx, headers.dilution] = test.dilution
            #         df.loc[idx, headers.comments] = test.specimen.condition
            #
            #     df[headers.data_file] = item.batch_id
            #     df = df.dropna(subset=[headers.sample_name])
            #     df.to_csv(os.path.join(current_app.root_path, 'static/batch_sequences', f"{item.batch_id}.csv"),
            #               index=False)
            #
            # for constituent in form.constituent_id.data:
            #     if constituent not in selected_constituents:
            #         db.session.add(BatchConstituents(**{
            #             'constituent_id': constituent,
            #             'batch_id': item_id,
            #             'template': 'form.html'
            #         }))
            #
            # for constituent in selected_constituents:
            #     if constituent not in form.constituent_id.data:
            #         BatchConstituents.query.filter_by(batch_id=item_id, constituent_id=constituent).delete()

    elif request.method == 'GET':
        kwargs['instrument_id'] = assay.instrument_id
        kwargs['items'] = StandardsAndSolutions.query.filter(and_(StandardsAndSolutions.assay.contains(str(assay.id)),
                                                                  StandardsAndSolutions.in_use == False))
        kwargs['extraction_date'] = datetime.now().date()
        kwargs['extracted_by_id'] = current_user.id
        kwargs['constituent_id'] = selected_constituents
        kwargs['assays'] = dict([(item.id, item.assay_name) for item in Assays.query.all()])
        print(kwargs['constituent_id'])

    # _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    # return _update

    return render_template(
        f'{table_name}/assign_resources_barcode.html',
        item=item,
        form=form,
        kwargs=kwargs
    )


@blueprint.route(f'/{table_name}/<int:item_id>/sequence', methods=['GET', 'POST'])
@login_required
def sequence_check(item_id):
    # Initialize item
    item = Batches.query.get(item_id)
    read_only = request.args.get('read_only')
    samq_columns = []
    headers = SequenceHeaderMappings.query.filter_by(batch_template_id=item.batch_template_id).first()
    # is_first may only be used for GCET, now that there is only one extraction, may be able to remove - TLD
    # Need to evaluate effects of getting rid of is_first
    is_first_txt = request.args.get('is_first')
    if is_first_txt == 'True':
        is_first = True
    else:
        is_first = False

    # Query for tests in batch
    tests = Tests.query.filter_by(batch_id=item_id)

    # Initialize updates array
    updates = []

    # Find which tests have been updated (dilution or comment added) to display during sequence check
    for test in tests:
        updates.extend([item for item in Modifications.query.filter(and_(Modifications.table_name == 'Tests',
                                                                         Modifications.record_id == str(test.id)))])

        updates.extend([item for item in CommentInstances.query.filter(and_(CommentInstances.comment_item_type ==
                                                                            'Tests',
                                                                            CommentInstances.comment_item_id ==
                                                                            test.id))])

    # Initialize ref_table array
    ref_table = []

    # Get the dilutions and comment additions made
    for entry in updates:
        if entry.__tablename__ == 'modifications':
            test = Tests.query.get(entry.record_id)
            if entry.field_name == 'dilution' and entry.new_value_text != "1":
                ref_table_dil = f'd1/{entry.new_value_text}' if entry.new_value_text != "HV" else "HV"
                ref_table.append([test.vial_position, test.test_name, ref_table_dil])
        elif entry.__tablename__ == 'comment_instances':
            test = Tests.query.get(entry.comment_item_id)
            ref_table_comment = entry.comment_text if entry.comment_text is not None else entry.comment.comment
            ref_table.append([test.vial_position, test.test_name, ref_table_comment])

    # Sort ref_table by vial_position (column 0)
    ref_table.sort(key=lambda x: (x[0] is None, x[0]))

    # Create a set to track seen values for vial_position and test_name
    seen_vial_positions = set()
    seen_test_names_per_vial = defaultdict(set)

    # Iterate and hide duplicates
    for row in ref_table:
        if row[0] in seen_vial_positions:
            row[0] = ""  # Hide duplicate vial_position
        else:
            seen_vial_positions.add(row[0])  # Store unique values

        if row[1] in seen_test_names_per_vial[row[0]]:
            row[1] = ""
        else:
            seen_test_names_per_vial[row[0]].add(row[1])

    # Initialize form
    form = SequenceCheck()

    # Initialize columns
    columns = ['column_1', 'column_2', 'column_3', 'column_4', 'column_5', 'column_6', 'column_7']

    if 'SAMQ' in item.assay.assay_name:
        samq_columns = ['samq_column']

    # Get sequence
    ws_sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                 BatchRecords.file_type == 'Sequence')).first()

    # Initialize index dictionary
    idx_dict = {i: 'PLACEHOLDER' for i in range(1, 100)}

    idx = 0

    seq_search = {y[headers.vial_position]: [y[headers.sample_name], 'PLACEHOLDER'] for x, y in
                  pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

    # Check if assay is GCET
    if 'GCET' in item.assay.assay_name:
        # seq_search = {y['Location']: [y['Sample_Name'], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        # Initialize QC pairs
        constituent_pairs = {'QC 0.040': 'None Selected', 'QC 0.150': 'None Selected', 'QC VOL': 'None Selected',
                             'CALIB ETOH 0.010': 'None Selected', 'CALIB ETOH 0.080': 'None Selected',
                             'CALIB ETOH 0.100': 'None Selected', 'CALIB ETOH 0.200': 'None Selected',
                             'CALIB ETOH 0.300': 'None Selected', 'CALIB ETOH 0.500': 'None Selected',
                             'CALIB VOL 0.010': 'None Selected', 'CALIB VOL 0.050': 'None Selected',
                             'CALIB VOL 0.150': 'None Selected', 'BLANK (dH2O)': 'None Selected',
                             'BLANK + ISTD': 'None Selected'}

    elif 'LCQD' in item.assay.assay_name:
        # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        # Create dictionary of possible LCQD constituents
        constituent_pairs = {'QL1 (LCQD) A': 'None Selected', 'QL1 (LCQD) B': 'None Selected',
                             'QH1 (LCQD) A': 'None Selected', 'QL2 (LCQD) A': 'None Selected',
                             'QH2 (LCQD) A': 'None Selected', 'QL2 (LCQD) B': 'None Selected',
                             'QL3 (LCQD) A': 'None Selected', 'QH1 (LCQD) B': 'None Selected',
                             'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                             'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                             'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                             'Calibrator 7': 'None Selected', 'LOD (LCQD) A': 'None Selected',
                             'LOD (LCQD) B': 'None Selected', 'Mix Check (LCQD)': 'None Selected',
                             'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}
    elif 'QTON' in item.assay.assay_name:
        # seq_search = {y['Vial Position']: [y['Sample Name'], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        # Create dictionary of possible QTON constituents
        constituent_pairs = {'QL1 (QTON) A': 'None Selected', 'QL1 (QTON) B': 'None Selected',
                             'QH1 (QTON) A': 'None Selected', 'QL2 (QTON) A': 'None Selected',
                             'QH2 (QTON) A': 'None Selected', 'QL2 (QTON) B': 'None Selected',
                             'QL3 (QTON) A': 'None Selected', 'QH1 (QTON) B': 'None Selected',
                             'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                             'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                             'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                             'Calibrator 7': 'None Selected',
                             'LOS (QTON) A': 'None Selected', 'LOS (QTON) B': 'None Selected',
                             'Mix Check (QTON) A': 'None Selected', 'Mix Check (QTON) B': 'None Selected',
                             'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

    elif 'LCCI' in item.assay.assay_name:
        # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        # Create dictionary of possible LCQD constituents
        constituent_pairs = {'QL1 (LCCI) A': 'None Selected', 'QL1 (LCCI) B': 'None Selected',
                             'QH1 (LCCI) A': 'None Selected', 'QL2 (LCCI) A': 'None Selected',
                             'QH2 (LCCI) A': 'None Selected', 'QL2 (LCCI) B': 'None Selected',
                             'QL3 (LCCI) A': 'None Selected', 'QH1 (LCCI) B': 'None Selected',
                             'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                             'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                             'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                             'Calibrator 7': 'None Selected', 'LOD (LCCI) A': 'None Selected',
                             'LOD (LCCI) B': 'None Selected', 'Mix Check (LCCI)': 'None Selected',
                             'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

    elif 'LCFS' in item.assay.assay_name:
        # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        # Create dictionary of possible LCQD constituents
        constituent_pairs = {'QL1 (LCFS) A': 'None Selected', 'QL1 (LCFS) B': 'None Selected',
                             'QH1 (LCFS) A': 'None Selected', 'QL2 (LCFS) A': 'None Selected',
                             'QH2 (LCFS) A': 'None Selected', 'QL2 (LCFS) B': 'None Selected',
                             'QL3 (LCFS) A': 'None Selected', 'QH1 (LCFS) B': 'None Selected',
                             'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                             'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                             'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                             'Calibrator 7': 'None Selected', 'LOD (LCCI) A': 'None Selected',
                             'LOD (LCFS) B': 'None Selected', 'Mix Check (LCFS)': 'None Selected',
                             'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

    elif 'SAMQ' in item.assay.assay_name:
        # Add SampleID for SAMQ to distinguish, all SampleNames are the same for each case
        # seq_search = {y['VialPos']: [f"{y['% header=SampleName']}_{y['SampleID']}", 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        # Create dictionary of possible Blank matrices
        constituent_pairs = {'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

    elif 'GCNO' in item.assay.assay_name:
        # seq_search = {y[headers.vial_position]: [y[headers.sample_name], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        constituent_pairs = {'Blank (dH2O)_1': 'None Selected', 'Blank (dH2O)_2': 'None Selected',
                             'Blank (dH2O)_3': 'None Selected', 'Blank + ISTD': 'None Selected',
                             'LOD (GCNO) A': 'None Selected'}

    elif 'GCVO' in item.assay.assay_name:
        # seq_search = {y['Vial']: [y['Name'], 'PLACEHOLDER'] for x, y in
        #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

        constituent_pairs = {'Blank (dH2O)_1': 'None Selected', 'Blank (dH2O)_2': 'None Selected',
                             'Blank (dH2O)_3': 'None Selected', 'Blank + ISTD': 'None Selected',
                             'LOD (GCVO) A': 'None Selected', 'LOD (GCVO) B': 'None Selected'}
    
    # Handle GCDP batches by using gcdp_assay column
    elif 'GCDP' in item.assay.assay_name:
        # Check if assay is GCET
        if 'GCET' in item.gcdp_assay.assay_name:
            # seq_search = {y['Location']: [y['Sample_Name'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Initialize QC pairs
            constituent_pairs = {'QC 0.040': 'None Selected', 'QC 0.150': 'None Selected', 'QC VOL': 'None Selected',
                                'CALIB ETOH 0.010': 'None Selected', 'CALIB ETOH 0.080': 'None Selected',
                                'CALIB ETOH 0.100': 'None Selected', 'CALIB ETOH 0.200': 'None Selected',
                                'CALIB ETOH 0.300': 'None Selected', 'CALIB ETOH 0.500': 'None Selected',
                                'CALIB VOL 0.010': 'None Selected', 'CALIB VOL 0.050': 'None Selected',
                                'CALIB VOL 0.150': 'None Selected', 'BLANK (dH2O)': 'None Selected',
                                'BLANK + ISTD': 'None Selected'}

        elif 'LCQD' in item.gcdp_assay.assay_name:
            # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible LCQD constituents
            constituent_pairs = {'QL1 (LCQD) A': 'None Selected', 'QL1 (LCQD) B': 'None Selected',
                                'QH1 (LCQD) A': 'None Selected', 'QL2 (LCQD) A': 'None Selected',
                                'QH2 (LCQD) A': 'None Selected', 'QL2 (LCQD) B': 'None Selected',
                                'QL3 (LCQD) A': 'None Selected', 'QH1 (LCQD) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected', 'LOD (LCQD) A': 'None Selected',
                                'LOD (LCQD) B': 'None Selected', 'Mix Check (LCQD)': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}
        elif 'QTON' in item.gcdp_assay.assay_name:
            # seq_search = {y['Vial Position']: [y['Sample Name'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible QTON constituents
            constituent_pairs = {'QL1 (QTON) A': 'None Selected', 'QL1 (QTON) B': 'None Selected',
                                'QH1 (QTON) A': 'None Selected', 'QL2 (QTON) A': 'None Selected',
                                'QH2 (QTON) A': 'None Selected', 'QL2 (QTON) B': 'None Selected',
                                'QL3 (QTON) A': 'None Selected', 'QH1 (QTON) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected',
                                'LOS (QTON) A': 'None Selected', 'LOS (QTON) B': 'None Selected',
                                'Mix Check (QTON) A': 'None Selected', 'Mix Check (QTON) B': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'LCCI' in item.gcdp_assay.assay_name:
            # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible LCQD constituents
            constituent_pairs = {'QL1 (LCCI) A': 'None Selected', 'QL1 (LCCI) B': 'None Selected',
                                'QH1 (LCCI) A': 'None Selected', 'QL2 (LCCI) A': 'None Selected',
                                'QH2 (LCCI) A': 'None Selected', 'QL2 (LCCI) B': 'None Selected',
                                'QL3 (LCCI) A': 'None Selected', 'QH1 (LCCI) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected', 'LOD (LCCI) A': 'None Selected',
                                'LOD (LCCI) B': 'None Selected', 'Mix Check (LCCI)': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'LCFS' in item.gcdp_assay.assay_name:
            # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible LCQD constituents
            constituent_pairs = {'QL1 (LCFS) A': 'None Selected', 'QL1 (LCFS) B': 'None Selected',
                                'QH1 (LCFS) A': 'None Selected', 'QL2 (LCFS) A': 'None Selected',
                                'QH2 (LCFS) A': 'None Selected', 'QL2 (LCFS) B': 'None Selected',
                                'QL3 (LCFS) A': 'None Selected', 'QH1 (LCFS) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected', 'LOD (LCCI) A': 'None Selected',
                                'LOD (LCFS) B': 'None Selected', 'Mix Check (LCFS)': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'SAMQ' in item.gcdp_assay.assay_name:
            # Add SampleID for SAMQ to distinguish, all SampleNames are the same for each case
            # seq_search = {y['VialPos']: [f"{y['% header=SampleName']}_{y['SampleID']}", 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible Blank matrices
            constituent_pairs = {'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'GCNO' in item.gcdp_assay.assay_name:
            # seq_search = {y[headers.vial_position]: [y[headers.sample_name], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            constituent_pairs = {'Blank (dH2O)_1': 'None Selected', 'Blank (dH2O)_2': 'None Selected',
                                'Blank (dH2O)_3': 'None Selected', 'Blank + ISTD': 'None Selected',
                                'LOD (GCNO) A': 'None Selected'}

        elif 'GCVO' in item.gcdp_assay.assay_name:
            # seq_search = {y['Vial']: [y['Name'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            constituent_pairs = {'Blank (dH2O)_1': 'None Selected', 'Blank (dH2O)_2': 'None Selected',
                                'Blank (dH2O)_3': 'None Selected', 'Blank + ISTD': 'None Selected',
                                'LOD (GCVO) A': 'None Selected', 'LOD (GCVO) B': 'None Selected'}

    # Handle GCDP batches by using gcdp_assay column
    elif 'GCDP' in item.assay.assay_name:
        # Check if assay is GCET
        if 'GCET' in item.gcdp_assay.assay_name:
            # seq_search = {y['Location']: [y['Sample_Name'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Initialize QC pairs
            constituent_pairs = {'QC 0.040': 'None Selected', 'QC 0.150': 'None Selected', 'QC VOL': 'None Selected',
                                'CALIB ETOH 0.010': 'None Selected', 'CALIB ETOH 0.080': 'None Selected',
                                'CALIB ETOH 0.100': 'None Selected', 'CALIB ETOH 0.200': 'None Selected',
                                'CALIB ETOH 0.300': 'None Selected', 'CALIB ETOH 0.500': 'None Selected',
                                'CALIB VOL 0.010': 'None Selected', 'CALIB VOL 0.050': 'None Selected',
                                'CALIB VOL 0.150': 'None Selected', 'BLANK (dH2O)': 'None Selected',
                                'BLANK + ISTD': 'None Selected'}

        elif 'LCQD' in item.gcdp_assay.assay_name:
            # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible LCQD constituents
            constituent_pairs = {'QL1 (LCQD) A': 'None Selected', 'QL1 (LCQD) B': 'None Selected',
                                'QH1 (LCQD) A': 'None Selected', 'QL2 (LCQD) A': 'None Selected',
                                'QH2 (LCQD) A': 'None Selected', 'QL2 (LCQD) B': 'None Selected',
                                'QL3 (LCQD) A': 'None Selected', 'QH1 (LCQD) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected', 'LOD (LCQD) A': 'None Selected',
                                'LOD (LCQD) B': 'None Selected', 'Mix Check (LCQD)': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}
        elif 'QTON' in item.gcdp_assay.assay_name:
            # seq_search = {y['Vial Position']: [y['Sample Name'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible QTON constituents
            constituent_pairs = {'QL1 (QTON) A': 'None Selected', 'QL1 (QTON) B': 'None Selected',
                                'QH1 (QTON) A': 'None Selected', 'QL2 (QTON) A': 'None Selected',
                                'QH2 (QTON) A': 'None Selected', 'QL2 (QTON) B': 'None Selected',
                                'QL3 (QTON) A': 'None Selected', 'QH1 (QTON) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected',
                                'LOS (QTON) A': 'None Selected', 'LOS (QTON) B': 'None Selected',
                                'Mix Check (QTON) A': 'None Selected', 'Mix Check (QTON) B': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'LCCI' in item.gcdp_assay.assay_name:
            # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible LCQD constituents
            constituent_pairs = {'QL1 (LCCI) A': 'None Selected', 'QL1 (LCCI) B': 'None Selected',
                                'QH1 (LCCI) A': 'None Selected', 'QL2 (LCCI) A': 'None Selected',
                                'QH2 (LCCI) A': 'None Selected', 'QL2 (LCCI) B': 'None Selected',
                                'QL3 (LCCI) A': 'None Selected', 'QH1 (LCCI) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected', 'LOD (LCCI) A': 'None Selected',
                                'LOD (LCCI) B': 'None Selected', 'Mix Check (LCCI)': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'LCFS' in item.gcdp_assay.assay_name:
            # seq_search = {y['VialPos']: [y['% header=SampleName'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible LCQD constituents
            constituent_pairs = {'QL1 (LCFS) A': 'None Selected', 'QL1 (LCFS) B': 'None Selected',
                                'QH1 (LCFS) A': 'None Selected', 'QL2 (LCFS) A': 'None Selected',
                                'QH2 (LCFS) A': 'None Selected', 'QL2 (LCFS) B': 'None Selected',
                                'QL3 (LCFS) A': 'None Selected', 'QH1 (LCFS) B': 'None Selected',
                                'Calibrator 1': 'None Selected', 'Calibrator 2': 'None Selected',
                                'Calibrator 3': 'None Selected', 'Calibrator 4': 'None Selected',
                                'Calibrator 5': 'None Selected', 'Calibrator 6': 'None Selected',
                                'Calibrator 7': 'None Selected', 'LOD (LCCI) A': 'None Selected',
                                'LOD (LCFS) B': 'None Selected', 'Mix Check (LCFS)': 'None Selected',
                                'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'SAMQ' in item.gcdp_assay.assay_name:
            # Add SampleID for SAMQ to distinguish, all SampleNames are the same for each case
            # seq_search = {y['VialPos']: [f"{y['% header=SampleName']}_{y['SampleID']}", 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            # Create dictionary of possible Blank matrices
            constituent_pairs = {'Blank (Blood)': 'None Selected', 'Blank (Urine)': 'None Selected'}

        elif 'GCNO' in item.gcdp_assay.assay_name:
            # seq_search = {y[headers.vial_position]: [y[headers.sample_name], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            constituent_pairs = {'Blank (dH2O)_1': 'None Selected', 'Blank (dH2O)_2': 'None Selected',
                                'Blank (dH2O)_3': 'None Selected', 'Blank + ISTD': 'None Selected',
                                'LOD (GCNO) A': 'None Selected'}

        elif 'GCVO' in item.gcdp_assay.assay_name:
            # seq_search = {y['Vial']: [y['Name'], 'PLACEHOLDER'] for x, y in
            #               pd.read_csv(ws_sequence.file_path, encoding='utf-8-sig').iterrows()}

            constituent_pairs = {'Blank (dH2O)_1': 'None Selected', 'Blank (dH2O)_2': 'None Selected',
                                'Blank (dH2O)_3': 'None Selected', 'Blank + ISTD': 'None Selected',
                                'LOD (GCVO) A': 'None Selected', 'LOD (GCVO) B': 'None Selected'}

    if form.is_submitted() and form.validate():
        for field in form:
            if is_first:
                # Skip submit and csrf field
                scan_table = None
                if field.name == 'submit' or field.name == 'csrf_token':
                    scan_id = None
                    scan_table = None
                # If data in non-date field, record the id and table from the scan
                elif field.data != '' and field.name[-2:] != 'te':
                    scan_id = field.data.split()[1]
                    if field.data.split()[0] == 'tests:':
                        scan_table = Tests
                    elif field.data.split()[0] == 'batch_constituents:':
                        scan_table = BatchConstituents
                    elif field.data.split()[0] == 'qr_reference:':
                        scan_table = QRReference
                    elif field.data.split()[0] == 'standards_and_solutions:':
                        scan_table = StandardsAndSolutions
                    else:
                        pass
                    idx += 1
                else:
                    scan_id = None
                    scan_table = None
                    if field.name[-2:] != 'te':
                        idx += 1
                        # pass
                # If field was scanned into
                if scan_id is not None and scan_table is not None and scan_table != QRReference:
                    # Iterate through form to find match date field
                    for search in form:
                        # Find relevant date field for field that was scanned into
                        try:
                            if (search.name.split('_')[0] == field.name and search.name[-2:] == 'te') or \
                                    ('SAMQ' in item.assay.assay_name and search.name.split('_')[0] == 'samq' and
                                     search.name.split('_')[1] == field.name.split('_')[1] and search.name[
                                                                                               -2:] == 'te'):
                                # Format date
                                print(f'SEARCH DATA: {search.data}')
                                print(f'SEARCH NAME: {search.name}')
                                field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                                # Check if batch_constituent needs checks and fill in relevant columns
                                if scan_table == BatchConstituents and BatchConstituents.query.get(scan_id) \
                                        .include_checks:
                                    scan_table.query.get(scan_id).sequence_check = 'Completed / Automated'
                                    scan_table.query.get(scan_id).sequence_check_by = current_user.id
                                    scan_table.query.get(scan_id).sequence_check_date = field_date
                                elif scan_table == BatchConstituents and not BatchConstituents.query.get(scan_id) \
                                        .include_checks:
                                    pass
                                elif scan_table == StandardsAndSolutions:
                                    standard = StandardsAndSolutions.query.get(scan_id)
                                    batch_const = BatchConstituents.query.filter_by(batch_id=item_id,
                                                                                    constituent_id=standard.id).first()
                                    batch_const.sequence_check = 'Completed / Automated'
                                    batch_const.sequence_check_by = current_user.id
                                    batch_const.sequence_check_date = field_date
                                else:
                                    # Add scan information to db
                                    scan_table.query.get(scan_id).sequence_check = 'Completed / Automated'
                                    scan_table.query.get(scan_id).sequence_check_by = current_user.id
                                    scan_table.query.get(scan_id).sequence_check_date = field_date

                                db.session.commit()
                            else:
                                field_date = None

                        except IndexError:
                            field_date = None

                elif scan_table == QRReference:
                    idx_dict[idx] = scan_table.query.get(scan_id).text
            else:
                # Skip submit and csrf field
                if field.name == 'submit' or field.name == 'csrf_token':
                    scan_id = None
                    scan_table = None
                # If data in non-date field, record the id and table from the scan
                elif field.data != '' and field.name[-2:] != 'te':
                    scan_id = field.data.split()[1]
                    if field.data.split()[0] == 'tests:':
                        scan_table = Tests
                    elif field.data.split()[0] == 'batch_constituents:':
                        scan_table = BatchConstituents
                    elif field.data.split()[0] == 'qr_reference:':
                        scan_table = QRReference
                    else:
                        pass
                    idx += 1
                else:
                    scan_id = None
                    scan_table = None
                    if field.name[-2:] != 'te':
                        idx += 1
                        # pass
                # If field was scanned into
                if scan_id is not None and scan_table is not None and scan_table != QRReference:
                    # Iterate through form to find match date field
                    for search in form:
                        try:
                            if search.name.split('_')[0] == field.name and search.name[-2:] == 'te':
                                # Format date
                                field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")

                                # Add scan information to db
                                scan_table.query.get(scan_id).sequence_check_2 = 'Completed / Automated'
                                scan_table.query.get(scan_id).sequence_check_2_by = current_user.id
                                scan_table.query.get(scan_id).sequence_check_2_date = field_date
                                db.session.commit()
                            else:
                                field_date = None
                        except IndexError:
                            field_date = None

                elif scan_table == QRReference:
                    idx_dict[idx] = scan_table.query.get(scan_id).text

        # set correct values for selected constituents
        for k, v in idx_dict.items():
            if v != 'PLACEHOLDER':
                seq_search[k][1] = idx_dict[k]

        for k, v in seq_search.items():
            if is_first:
                if v[1] != 'PLACEHOLDER':
                    if v[0] in constituent_pairs:
                        pass
                    else:
                        Tests.query.filter(and_(Tests.test_name == v[0], Tests.batch_id == item.id)).first() \
                            .sequence_check = v[1]
                        Tests.query.filter(and_(Tests.test_name == v[0],
                                                Tests.batch_id == item.id)).first().sequence_check_by = current_user.id
                        Tests.query.filter(and_(Tests.test_name == v[0],
                                                Tests.batch_id == item.id)).first().sequence_check_date = datetime.now()
                        db.session.commit()
            else:
                if v[1] != 'PLACEHOLDER':
                    if v[0] in constituent_pairs:
                        pass
                    else:
                        Tests.query.filter(and_(Tests.test_name == v[0], Tests.batch_id == item.id)).first() \
                            .gcet_sequence_check = v[1]
                        Tests.query.filter(and_(Tests.test_name == v[0],
                                                Tests.batch_id ==
                                                item.id)).first().gcet_sequence_check_by = current_user.id
                        Tests.query.filter(and_(Tests.test_name == v[0],
                                                Tests.batch_id ==
                                                item.id)).first().gcet_sequence_check_date = datetime.now()
                        db.session.commit()

        for test in tests:
            if test.sequence_check is not None:
                pass
            else:
                return redirect(url_for(f'{table_name}.sequence_check', item_id=item_id, is_first=True))
        
        for const in BatchConstituents.query.filter_by(batch_id=item_id).all():
            if const.sequence_check is not None:
                pass
            else:
                return redirect(url_for(f'{table_name}.sequence_check', item_id=item_id, is_first=True))

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Initialize headers
    headers = SequenceHeaderMappings.query.filter_by(batch_template_id=item.batch_template_id).first()

    # Set csv encoding dependant on assay
    encoding = 'utf-8-sig'
    # if 'GCET' in item.assay.assay_name:
    #     encoding = 'cp1250'
    # else:
    #     encoding = 'utf-8-sig'

    # Separate sequence building for SAMQ

    # Initialize sequence dict and empty positions array
    sequence_dict = {}
    empty_positions = []

    # Build sequence with tests and batch constituents
    # if 'LCCI' not in item.assay.assay_name:
    sequence = [[x.test_name, x.vial_position, x.id, x.sequence_check, x.checked_by] for x in
                Tests.query.filter_by(batch_id=item_id)]
    # else:
    #     sequence = []
    # This addition not relevant to SAMQ
    if 'SAMQ' not in item.assay.assay_name:
        sequence.extend([[x.constituent_type, x.vial_position, x.id, x.sequence_check, x.specimen_check_by] for x in
                         BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item.id,
                                                             BatchConstituents.constituent_id != '',
                                                             BatchConstituents.include_checks == True
                                                             ))])
    else:
        sequence.extend([[x.constituent_type, x.vial_position, x.id, x.sequence_check, x.specimen_check_by] for x in
                         BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item.id,
                                                             BatchConstituents.constituent_id != '',
                                                             BatchConstituents.include_checks == True,
                                                             BatchConstituents.constituent_type.contains('Blank')
                                                             ))])

    sequence.extend([[x.constituent_type, x.vial_position, x.id, x.sequence_check, x.specimen_check_by] for x in
                     BatchConstituents.query.join(SolventsAndReagents,
                                                  BatchConstituents.reagent_id == SolventsAndReagents.id)
                    .join(AssayConstituents, SolventsAndReagents.constituent == AssayConstituents.id)
                    .filter(and_(BatchConstituents.batch_id == item.id, BatchConstituents.include_checks == True,
                                 SolventsAndReagents.constituent != ''))
                    .options(joinedload(BatchConstituents.reagent).joinedload(SolventsAndReagents.type))
                    .all()
                     ])

    # Add batch constituents with no reagent or constituent assigned to disable in html
    sequence.extend([[x.constituent_type, x.vial_position, 'ID PLACEHOLDER', x.sequence_check, x.specimen_check_by]
                     for x in BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item.id,
                                                                  BatchConstituents.reagent_id == None,
                                                                  BatchConstituents.constituent_id == None,
                                                                  BatchConstituents.include_checks == True))])

    # Build sequence with tests and constituents
    constituents = [[x.constituent.lot, x.vial_position, x.id, x.constituent_type, x.specimen_check_by] for x in
                    BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item.id,
                                                        BatchConstituents.constituent_id != '',
                                                        BatchConstituents.include_checks == True
                                                        ))]

    constituents.extend([[x.reagent.lot, x.vial_position, x.id, x.constituent_type, x.specimen_check_by] for x in
                         BatchConstituents.query
                        .join(SolventsAndReagents, BatchConstituents.reagent_id == SolventsAndReagents.id)
                        .join(AssayConstituents, SolventsAndReagents.constituent == AssayConstituents.id)
                        .filter(and_(BatchConstituents.batch_id == item.id, BatchConstituents.include_checks == True,
                                     SolventsAndReagents.constituent != ''))
                        .options(joinedload(BatchConstituents.reagent).joinedload(SolventsAndReagents.type))
                        .all()
                         ])

    # sequence.extend([[y[headers.sample_name], y[headers.vial_position], 'ID PLACEHOLDER', y[headers.sample_type]]
    #                  for x, y in pd.read_csv(ws_sequence.file_path, encoding=encoding).iterrows() if 'BLANK' in
    #                  y[headers.sample_name]])

    # Set relevant constituent values on a copy to avoid changes during iteration
    for const in sequence[:]:
        for k in constituent_pairs.keys():
            if k in const[0]:
                if 'Mix Check' in k:
                    try:
                        constituent_pairs[k] = BatchConstituents.query.get(const[2]).constituent_id
                        const[2] = constituent_pairs[k]
                        new_const = [const[0], const[1], constituent_pairs[k], const[3], const[4]]
                        sequence.remove(const)
                        sequence.append(new_const)
                    except AttributeError:
                        pass
                else:
                    constituent_pairs[k] = const[2]

    # Initialize unique sequence array to remove duplicated items
    unique_seq = []

    # Initialize seq_check array for sequence check
    seq_check = []

    # Initialize source_check array to determine if a source check has been performed
    source_check = []

    print(f'SEQUENCE: {sequence}')

    # Create sequence array of only unique sample/vial position pairings
    for i in sequence:
        if i not in unique_seq:
            unique_seq.append(i)

    # Set constituent to seq_check if a constituent has been assigned
    for x in unique_seq:
        if x[2] is None:
            seq_check.append(x[1])

        # Check if source check by is none and add to the source check list if so
        if x[4] is None and 'LCCI' not in item.assay.assay_name:
            source_check.append(x[1])

        if x[3] is not None:
            source_check.append(x[1])

    if 'GCET' in item.assay.assay_name or 'GCNO' in item.assay.assay_name or 'GCVO' in item.assay.assay_name:
        # Add relevant columns for GCET
        columns.extend(['column_8', 'column_9'])

        # Create array for each column corresponding to rack
        for column in columns:
            locals()[column] = list(range(12 * int(column.split('_')[1]) + 0, 0 + 12 * int(column.split('_')[1]) - 12,
                                          -1))

            # Find empty positions in rack
            for x in locals()[column]:
                # x is vial position in column (i.e., column 2 position 1, x = 13 (12 positions per column))
                # For each position in column, reset counter and set found to False
                counter = 0
                found = False
                for y in sequence:
                    # y = [sample_name, vial_position, ID, sample_type]
                    if x == y[1]:
                        # If position in column = vial_position
                        found = True
                        counter += 1
                    else:
                        counter += 1

                    # If entire sequence is searched and x != any vial_position, add x to empty_positions array
                    if counter >= len(sequence) and not found:
                        empty_positions.append(x)

        if read_only:
            return render_template(
                f'{table_name}/gcet_sequence_read.html',
                item=item,
                sequence=sequence,
                form=form,
                unique_seq=unique_seq,
                seq_check=seq_check,
                columns=columns,
                locals=locals(),
                empty_positions=empty_positions,
                samq_columns=samq_columns,
                ref_table=ref_table,
                source_check=source_check
            )

        return render_template(
            f'{table_name}/sequence_gcet.html',
            item=item,
            sequence=sequence,
            form=form,
            unique_seq=unique_seq,
            seq_check=seq_check,
            columns=columns,
            locals=locals(),
            empty_positions=empty_positions,
            samq_columns=samq_columns,
            ref_table=ref_table,
            source_check=source_check
        )
    elif 'LCQD' in item.assay.assay_name or 'QTON' in item.assay.assay_name or 'SAMQ' in item.assay.assay_name or \
            'LCCI' in item.assay.assay_name or 'LCFS' in item.assay.assay_name:
        # Create array for each column corresponding to LC autosampler rack
        for column in columns:
            locals()[column] = list(range(15 * int(column.split('_')[1]), 0 + 15 * int(column.split('_')[1]) -
                                          15, -1))

            # Find empty positions in LC autosampler rack
            for x in locals()[column]:
                # x is vial position in column (i.e., column 2 position 1, x = 16 (15 positions per column))
                # For each position in column, reset counter and set found to False
                counter = 0
                found = False
                for y in sequence:
                    # y = [sample_name, vial_position, ID, sample_type]
                    if x == y[1]:
                        # If position in column = vial_position
                        found = True
                        counter += 1
                    else:
                        counter += 1

                    # If entire sequence is searched and x != any vial_position, add x to empty_positions array
                    if counter >= len(sequence) and not found:
                        empty_positions.append(x)
        # Create SAMQ 'Control Rack' column for sequence check
        if 'SAMQ' in item.assay.assay_name:
            for column in samq_columns:
                # Positions in this rack start at 20001
                locals()[column] = list(range(20001, 20011))[::-1]
        print(f'UNIQUE SEQ: {unique_seq}')
        print(f'SEQ CHECK: {seq_check}')

        if read_only:
            return render_template(
                f'{table_name}/sequence_read.html',
                item=item,
                sequence_dict=sequence_dict,
                locals=locals(),
                columns=columns,
                sequence=sequence,
                empty_positions=empty_positions,
                unique_seq=unique_seq,
                form=form,
                seq_check=seq_check,
                ref_table=ref_table,
                source_check=source_check
            )

        return render_template(
            f'{table_name}/sequence_check.html',
            item=item,
            sequence_dict=sequence_dict,
            locals=locals(),
            columns=columns,
            sequence=sequence,
            empty_positions=empty_positions,
            unique_seq=unique_seq,
            form=form,
            seq_check=seq_check,
            ref_table=ref_table,
            source_check=source_check
        )
    
    elif 'GCDP' in item.assay.assay_name:
        if 'GCET' in item.gcdp_assay.assay_name or 'GCNO' in item.gcdp_assay.assay_name or 'GCVO' in item.gcdp_assay.assay_name:
            # Add relevant columns for GCET
            columns.extend(['column_8', 'column_9'])

            # Create array for each column corresponding to rack
            for column in columns:
                locals()[column] = list(range(12 * int(column.split('_')[1]) + 0, 0 + 12 * int(column.split('_')[1]) - 12,
                                            -1))

                # Find empty positions in rack
                for x in locals()[column]:
                    # x is vial position in column (i.e., column 2 position 1, x = 13 (12 positions per column))
                    # For each position in column, reset counter and set found to False
                    counter = 0
                    found = False
                    for y in sequence:
                        # y = [sample_name, vial_position, ID, sample_type]
                        if x == y[1]:
                            # If position in column = vial_position
                            found = True
                            counter += 1
                        else:
                            counter += 1

                        # If entire sequence is searched and x != any vial_position, add x to empty_positions array
                        if counter >= len(sequence) and not found:
                            empty_positions.append(x)

            if read_only:
                return render_template(
                    f'{table_name}/gcet_sequence_read.html',
                    item=item,
                    sequence=sequence,
                    form=form,
                    unique_seq=unique_seq,
                    seq_check=seq_check,
                    columns=columns,
                    locals=locals(),
                    empty_positions=empty_positions,
                    samq_columns=samq_columns,
                    ref_table=ref_table,
                    source_check=source_check
                )

            return render_template(
                f'{table_name}/sequence_gcet.html',
                item=item,
                sequence=sequence,
                form=form,
                unique_seq=unique_seq,
                seq_check=seq_check,
                columns=columns,
                locals=locals(),
                empty_positions=empty_positions,
                samq_columns=samq_columns,
                ref_table=ref_table,
                source_check=source_check
            )
        elif 'LCQD' in item.gcdp_assay.assay_name or 'QTON' in item.gcdp_assay.assay_name or 'SAMQ' in item.gcdp_assay.assay_name or \
                'LCCI' in item.gcdp_assay.assay_name or 'LCFS' in item.gcdp_assay.assay_name:
            # Create array for each column corresponding to LC autosampler rack
            for column in columns:
                locals()[column] = list(range(15 * int(column.split('_')[1]), 0 + 15 * int(column.split('_')[1]) -
                                            15, -1))

                # Find empty positions in LC autosampler rack
                for x in locals()[column]:
                    # x is vial position in column (i.e., column 2 position 1, x = 16 (15 positions per column))
                    # For each position in column, reset counter and set found to False
                    counter = 0
                    found = False
                    for y in sequence:
                        # y = [sample_name, vial_position, ID, sample_type]
                        if x == y[1]:
                            # If position in column = vial_position
                            found = True
                            counter += 1
                        else:
                            counter += 1

                        # If entire sequence is searched and x != any vial_position, add x to empty_positions array
                        if counter >= len(sequence) and not found:
                            empty_positions.append(x)
            # Create SAMQ 'Control Rack' column for sequence check
            if 'SAMQ' in item.assay.assay_name:
                for column in samq_columns:
                    # Positions in this rack start at 20001
                    locals()[column] = list(range(20000, 20010))
            print(f'UNIQUE SEQ: {unique_seq}')
            print(f'SEQ CHECK: {seq_check}')

            if read_only:
                return render_template(
                    f'{table_name}/sequence_read.html',
                    item=item,
                    sequence_dict=sequence_dict,
                    locals=locals(),
                    columns=columns,
                    sequence=sequence,
                    empty_positions=empty_positions,
                    unique_seq=unique_seq,
                    form=form,
                    seq_check=seq_check,
                    ref_table=ref_table,
                    source_check=source_check
                )

            return render_template(
                f'{table_name}/sequence_check.html',
                item=item,
                sequence_dict=sequence_dict,
                locals=locals(),
                columns=columns,
                sequence=sequence,
                empty_positions=empty_positions,
                unique_seq=unique_seq,
                form=form,
                seq_check=seq_check,
                ref_table=ref_table,
                source_check=source_check
            )


@blueprint.route(f'/{table_name}/<int:item_id>/<seq_dict>/<assay>/create_sequence', methods=['GET', 'POST'])
@login_required
def create_sequence(item_id, seq_dict, assay):
    kwargs = default_kwargs.copy()
    # Get item
    item = table.query.get(item_id)
    # Initialize form
    form = GenerateSequence()
    # Get batch_constituents
    constituents = BatchConstituents.query.filter_by(batch_id=item_id)
    # Initialize relevant variables
    del_needed = False
    file_dict = {}
    attribute = None
    qc_pairs = {}
    tandem_tests = {}

    # Get seq_dict from frontend
    new_dict = json.loads(seq_dict)

    #  If sequence already exists, delete existing sequence
    if BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id, BatchRecords.file_type == 'Sequence')).first():
        original = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                  BatchRecords.file_type == 'Sequence')).first()
        print('BEFORE DELETE')
        # Change batch constituent db_status to "Deleted" and add modification see 1521 in view_templates
        kwargs['request'] = 'POST'
        delete_item(form=Add(), item_id=original.id, table=BatchRecords, table_name='batch_records',
                    item_name='Batch Records', name='file_name', admin_only=False, **kwargs)

        print('AFTER DELETE')

        del_needed = True

    # Create sequence file
    batch_template_name = BatchTemplates.query.get(item.batch_template_id).name
    headers = SequenceHeaderMappings.query.filter_by(batch_template_id=item.batch_template_id).first()

    if item.tandem_id and 'LCCI' in assay:
        tandem_sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item.tandem_id,
                                                         BatchRecords.file_type == 'Sequence')).first()

        df = pd.read_csv(tandem_sequence.file_path)

        for x, y in df.iterrows():
            tandem_tests[y[headers.sample_name]] = [y[headers.vial_position], y[headers.dilution]]

    # Consider making more standardized once all standards have same lot naming scheme
    # Can iterate dynamically build qc_pairs dict for all none GCET assays. More efficient
    # Potentially build with reference table in the future
    # Reference table includes assay, lot identifier (e.g., QLA1 for QL1 (LCQD) A), name in sequence

    if 'LCQD' in assay:
        # Set QC variables
        qc_pairs = {'QL1 (LCQD) A': 'None Selected', 'QL1 (LCQD) B': 'None Selected', 'QH1 (LCQD) A': 'None Selected',
                    'QL2 (LCQD) A': 'None Selected', 'QH2 (LCQD) A': 'None Selected', 'QL2 (LCQD) B': 'None Selected',
                    'QL3 (LCQD) A': 'None Selected', 'QH1 (LCQD) B': 'None Selected'}

        attribute = 'constituent'
        search = 'LCQD'

    elif 'GCET' in assay:
        # Set QC variables
        qc_pairs = {'QC 0.040': 'None Selected', 'QC 0.150': 'None Selected', 'QC VOL': 'None Selected'}

        attribute = 'reagent'
        search = 'GCET'

    elif 'LCCI' in assay:
        # Set QC variables
        qc_pairs = {'QL1 (LCCI) A': 'None Selected', 'QL1 (LCCI) B': 'None Selected', 'QH1 (LCCI) A': 'None Selected',
                    'QL2 (LCCI) A': 'None Selected', 'QH2 (LCCI) A': 'None Selected', 'QL2 (LCCI) B': 'None Selected',
                    'QL3 (LCCI) A': 'None Selected', 'QH1 (LCCI) B': 'None Selected'}

        attribute = 'constituent'
        search = 'LCCI'

    elif 'LCFS' in assay:
        # Set QC variables
        qc_pairs = {'QL1 (LCFS) A': 'None Selected', 'QL1 (LCFS) B': 'None Selected', 'QH1 (LCFS) A': 'None Selected',
                    'QL2 (LCFS) A': 'None Selected', 'QH2 (LCFS) A': 'None Selected', 'QL2 (LCFS) B': 'None Selected',
                    'QL3 (LCFS) A': 'None Selected', 'QH1 (LCFS) B': 'None Selected', 'QH1 (LCFS) X': 'None Selected',
                    'QL1 (LCFS) X': 'None Selected'}

        attribute = 'constituent'
        search = 'LCFS'

    elif 'QTON' in assay:
        # Set QC variables
        qc_pairs = {'QL1 (QTON) A': 'None Selected', 'QL1 (QTON) B': 'None Selected', 'QH1 (QTON) A': 'None Selected',
                    'QL2 (QTON) A': 'None Selected', 'QH2 (QTON) A': 'None Selected', 'QL2 (QTON) B': 'None Selected',
                    'QL3 (QTON) A': 'None Selected', 'QH1 (QTON) B': 'None Selected'}

        attribute = 'constituent'
        search = 'QTON'

    elif 'SAMQ' in assay:
        # dict: 'test_id': ['const1', 'const2', etc]
        samq = json.loads(request.args.get('samq_const'))

        # Iterate through dictionaries converting test_id to test object
        tests = Tests.query.filter_by(batch_id=item.id).all()

        # SAMQ standards are also tests, get each test and set in qc_pairs
        for test in tests:
            qc_pairs[test] = {'SAMQ-1-QLA': 'None Selected', 'SAMQ-Z-C1A': 'None Selected',
                              'SAMQ-Z-C2A': 'None Selected', 'SAMQ-Z-C3A': 'None Selected',
                              'SAMQ-Z-C4A': 'None Selected', 'SAMQ-Z-C5A': 'None Selected',
                              'SAMQ-Z-C6A': 'None Selected', 'SAMQ-Z-C7A': 'None Selected',
                              'SAMQ-1-QHA': 'None Selected', 'Case Sample': test.test_name,
                              'SAMQ-Z-QH1': 'None Selected', 'SAMQ-Z-QH2': 'None Selected',
                              'SAMQ-Z-QH3': 'None Selected', 'SAMQ-Z-QH4': 'None Selected'}

        for key, value in samq.items():
            test = Tests.query.get(int(key))
            for x in value:
                qc_pairs[test][x] = test.test_name

        attribute = 'constituent'

    df = pd.read_csv(
        os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template_name}.csv"),
        encoding="utf-8-sig")

    sample_idx = df[df[headers.sample_name].isna()].index

    if 'SAMQ' not in assay:
        # Build constituent lot array based on sequence sample name
        for const in constituents:
            if attribute == 'constituent':
                if const.constituent is not None:
                    if 'QLA1' in const.constituent.lot:
                        qc_pairs[f'QL1 ({search}) A'] = const.constituent.lot
                        qc_pairs[f'QL2 ({search}) A'] = const.constituent.lot
                        qc_pairs[f'QL3 ({search}) A'] = const.constituent.lot
                    elif 'QLB1' in const.constituent.lot:
                        qc_pairs[f'QL1 ({search}) B'] = const.constituent.lot
                        qc_pairs[f'QL2 ({search}) B'] = const.constituent.lot
                    elif 'QHA1' in const.constituent.lot:
                        qc_pairs[f'QH1 ({search}) A'] = const.constituent.lot
                        qc_pairs[f'QH2 ({search}) A'] = const.constituent.lot
                    elif 'QHB1' in const.constituent.lot:
                        qc_pairs[f'QH1 ({search}) B'] = const.constituent.lot
            elif attribute == 'reagent':
                if const.reagent is not None:
                    if 'QC 0.040' in const.reagent.name:
                        qc_pairs['QC 0.040'] = const.reagent.lot
                    elif 'QC 0.150' in const.reagent.name:
                        qc_pairs['QC 0.150'] = const.reagent.lot
                elif const.constituent is not None:
                    print(f'LOT: {const.constituent.lot}')
                    if 'QCVOL' in const.constituent.lot:
                        qc_pairs['QC VOL'] = const.constituent.lot

            try:
                qc_idx = df[df[headers.comments].notna()].index
                # Assign constituent lot in df
                for idx in qc_idx:
                    df.loc[idx, headers.comments] = qc_pairs[df.loc[idx, headers.sample_name]]
            except:
                pass

        tests = [test for test in Tests.query.filter_by(batch_id=item_id)]

        if item.tandem_id and 'LCCI' in assay:
            for k, v in tandem_tests.items():
                for test in tests:
                    if test.test_name[:-3] == k[:-3] and str(test.dilution) == str(v[1]):
                        idx = df.index[df[headers.vial_position] == int(v[0])].tolist()

                        if idx:
                            df.loc[idx, headers.sample_name] = test.test_name
                            df.loc[idx, headers.dilution] = test.dilution
                            df.loc[idx, headers.comments] = test.specimen.condition

        else:
            # Set sample name, dilution factor and comments for each test in df
            for n, test in enumerate(sorted(Tests.query.filter_by(batch_id=item_id),
                                            key=lambda test: test.test_name[-2:] if len(test.test_name) >= 2 else '')):
                idx = sample_idx[n]
                df.loc[idx, headers.sample_name] = test.test_name
                df.loc[idx, headers.dilution] = test.dilution
                df.loc[idx, headers.comments] = test.specimen.condition

    else:
        # Iterate over the dictionary
        for key, value in qc_pairs.items():
            for k, v in value.items():
                # Only consider cases where 'v' is not 'None Selected'
                # if v != 'None Selected':
                # Create a mask for rows where 'SampleID' matches 'k' and '% header=SampleName' is None
                mask = (df['SampleID'] == k) & (df['% header=SampleName'].isnull())

                # Find the index of the first row that satisfies the condition
                matching_indices = df.index[mask].tolist()

                if matching_indices:
                    # Update only the first matching row
                    df.at[matching_indices[0], '% header=SampleName'] = v

    if item.assay.assay_name in ['GCVO-ZZ', 'GCNO-ZZ']:
        for x, y in df.iterrows():
            df.loc[x, headers.data_file] = y[headers.sample_name]
            data_path = y['Data Path'].split('\\')
            data_path.pop()
            data_path.append(item.batch_id)
            df.loc[x, 'Data Path'] = '\\'.join(data_path)
    else:
        # Set data file column in df
        df[headers.data_file] = item.batch_id if 'QTON' not in assay else item.batch_id + " (P)"

    # Drop empty cells
    df = df.dropna(subset=[headers.sample_name])

    # Set file name and save
    fname = f"{item.batch_id}.csv"
    path = os.path.join(current_app.root_path, 'static/batch_sequences', fname)
    df.to_csv(path, index=False)

    # Get finished csv
    df_finished = pd.read_csv(path)

    # Set vial positions for each test
    for x, y in df_finished.iterrows():
        for test in Tests.query.filter_by(batch_id=item_id).all():
            if 'SAMQ' in item.assay.assay_name:
                if test.test_name == y[headers.sample_name] and y['SampleID'] == 'Case Sample':
                    test.vial_position = y[headers.vial_position]
            else:
                if test.test_name == y[headers.sample_name]:
                    test.vial_position = y[headers.vial_position]

    db.session.commit()

    if del_needed:

        # Set form information for BatchRecords entry and modifications tracking
        form.batch_id.data = item_id
        form.file_name.data = fname
        form.file_type.data = 'Sequence'
        form.file_path.data = path

        # Carry over submit = True and the csrf_token
        for field in form:
            if field.name in ['submit_seq', 'csrf_token']:
                form[field.name].data = new_dict[field.name]

        # Set request to POST to carry over
        kwargs['request'] = 'POST'

        add_item(form, BatchRecords, 'Batch Records', 'Batch Records', 'batch_records', False,
                 'file_name', **kwargs)

    else:

        # Assign values for BatchRecords table addition
        file_dict = {
            'batch_id': item_id,
            'file_name': fname,
            'file_type': 'Sequence',
            'file_path': path,
            'create_date': datetime.now()
        }

    # Add file to BatchRecords table and commit all db changes
    db.session.add(BatchRecords(**file_dict))
    db.session.commit()

    if 'QTON' in assay:

        form = GenerateSequence()

        del_needed = False

        batch_matrix = batch_template_name[5:7]
        if '(N)' in batch_template_name:
            batch_template_2 = f'QTON-{batch_matrix} (P)'
            batch_datafile_suffix = " (P)"
        else:
            batch_template_2 = f'QTON-{batch_matrix} (N)'
            batch_datafile_suffix = " (N)"

        fname = f"{item.batch_id} {batch_template_2[8::]}.csv"

        #  If sequence already exists, delete existing sequence
        if BatchRecords.query.filter(
                and_(BatchRecords.batch_id == item_id, BatchRecords.file_type == 'Sequence',
                     BatchRecords.file_name == fname)).first():
            original_new = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                          BatchRecords.file_type == 'Sequence',
                                                          BatchRecords.file_name == fname)).first()

            # Change batch constituent db_status to "Deleted" and add modification see 1521 in view_templates
            delete_item(form=Add(), item_id=original_new.id, table=BatchRecords, table_name='batch_records',
                        item_name='Batch Records', name='file_name', admin_only=False)

            del_needed = True

        df = pd.read_csv(
            os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template_2}.csv"),
            encoding="utf-8-sig")

        # COMMENTING DONE HERE
        sample_idx = df[df[headers.sample_name].isna()].index

        try:
            qc_idx = df[df[headers.comments].notna()].index
            # Assign constituent lot in df
            for idx in qc_idx:
                df.loc[idx, headers.comments] = qc_pairs[df.loc[idx, headers.sample_name]]
        except:
            pass

        # Set sample name, dilution factor and comments for each test in df
        for n, test in enumerate(sorted(Tests.query.filter_by(batch_id=item_id),
                                        key=lambda test: test.test_name[-2:] if len(test.test_name) >= 2 else '')):
            idx = sample_idx[n]
            df.loc[idx, headers.sample_name] = test.test_name
            df.loc[idx, headers.dilution] = test.dilution
            df.loc[idx, headers.comments] = test.specimen.condition

        # Set data file column in df
        df[headers.data_file] = item.batch_id + batch_datafile_suffix

        # Drop empty cells
        df = df.dropna(subset=[headers.sample_name])

        # Set path and save
        path = os.path.join(current_app.root_path, 'static/batch_sequences', fname)
        df.to_csv(path, index=False)

        db.session.commit()

        if del_needed:

            # Set form information for BatchRecords entry and modifications tracking
            form.batch_id.data = item_id
            form.file_name.data = fname
            form.file_type.data = 'Sequence'
            form.file_path.data = path

            # Carry over submit = True and the csrf_token
            for field in form:
                if field.name in ['submit_seq', 'csrf_token']:
                    form[field.name].data = new_dict[field.name]

            # Set request to POST to carry over
            kwargs['request'] = 'POST'

            add_item(form, BatchRecords, 'Batch Records', 'Batch Records', 'batch_records', False,
                     'file_name', **kwargs)

        else:

            # Assign values for BatchRecords table addition
            file_dict = {
                'batch_id': item_id,
                'file_name': fname,
                'file_type': 'Sequence',
                'file_path': path,
                'create_date': datetime.now()
            }

        # Add file to BatchRecords table and commit all db changes
        db.session.add(BatchRecords(**file_dict))
        db.session.commit()

    #     df = pd.read_csv(
    #         os.path.join(current_app.root_path, 'static/batch_templates', f"{batch_template_name}.csv"),
    #         encoding="cp1250")
    #
    #     sample_idx = df[df[headers.sample_name].isna()].index
    #
    #     # Set QC variables
    #     qc_idx = df[df[headers.comments].notna()].index
    #     # constituents = [[item.constituent.lot, item.constituent.constituent.name] for item in
    #     #                 BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item.id,
    #     #                                                     BatchConstituents.constituent_id != ''))]
    #
    #     # constituents.extend([[item.reagent.lot, item.reagent.type.name] for item in BatchConstituents.query.filter(
    #     #     and_(BatchConstituents.batch_id == item.id, BatchConstituents.reagent.constituent != '')
    #     # )])
    #
    #     # constituents.extend([
    #     #     [item.reagent.lot, item.reagent.const.name]
    #     #     for item in BatchConstituents.query
    #     #     .join(SolventsAndReagents, BatchConstituents.reagent_id == SolventsAndReagents.id)
    #     #     .join(AssayConstituents, SolventsAndReagents.constituent == AssayConstituents.id)
    #     #     .filter(and_(
    #     #         BatchConstituents.batch_id == item.id,
    #     #         SolventsAndReagents.constituent != ''
    #     #     ))
    #     #     .options(joinedload(BatchConstituents.reagent).joinedload(SolventsAndReagents.type))
    #     #     .all()
    #     # ])
    #
    #     qc_pairs = {'QC 0.040': 'None Selected', 'QC 0.150': 'None Selected', 'QC VOL': 'None Selected'}
    #
    #     # Build constituent lot array based on sequence sample name
    #     for const in constituents:
    #         if const.reagent is not None:
    #             if 'QC VOL' in const:
    #                 qc_pairs['QC VOL'] = const.reagent.lot
    #             elif 'QC 0.040' in const:
    #                 qc_pairs['QC 0.040'] = const.reagent.lot
    #             elif 'QC 0.150' in const:
    #                 qc_pairs['QC 0.150'] = const.reagent.lot
    #     print(f'QC PAIRS: {qc_pairs}')
    #
    #     # Assign constituent lot in df
    #     for idx in qc_idx:
    #         df.loc[idx, headers.comments] = qc_pairs[df.loc[idx, headers.sample_name]]
    #
    #     # Set sample name, dilution factor and comments for each test in df
    #     for n, test in enumerate(Tests.query.filter_by(batch_id=item_id)):
    #         idx = sample_idx[n]
    #         df.loc[idx, headers.sample_name] = test.test_name
    #         df.loc[idx, headers.dilution] = test.dilution
    #         df.loc[idx, headers.comments] = test.specimen.condition
    #
    #     # Set data file column in df
    #     df[headers.data_file] = item.batch_id
    #
    #     # Drop empty cells
    #     df = df.dropna(subset=[headers.sample_name])
    #
    #     # Set file name and save
    #     fname = f"{item.batch_id}.csv"
    #     path = os.path.join(current_app.root_path, 'static/batch_sequences', fname)
    #     df.to_csv(path, index=False, encoding='cp1250')
    #
    #     # Get finished csv
    #     df_finished = pd.read_csv(path, encoding='cp1250')
    #
    #     # Set test vial positions
    #     for x, y in df_finished.iterrows():
    #         for test in Tests.query.filter_by(batch_id=item_id).all():
    #             if test.test_name == y[headers.sample_name]:
    #                 test.vial_position = y[headers.vial_position]
    #
    #     db.session.commit()
    #
    #     if del_needed:
    #
    #         # Set form information for BatchRecords entry and modifications tracking
    #         form.batch_id.data = item_id
    #         form.file_name.data = fname
    #         form.file_type.data = 'Sequence'
    #         form.file_path.data = path
    #
    #         # Carry over submit = True and the csrf_token
    #         for field in form:
    #             if field.name in ['submit', 'csrf_token']:
    #                 form[field.name].data = new_dict[field.name]
    #
    #         # Set request to POST to carry over
    #         kwargs['request'] = 'POST'
    #
    #         add_item(form, BatchRecords, 'Batch Records', 'Batch Records', 'batch_records', False,
    #                  'file_name', **kwargs)
    #
    #     else:
    #
    #         # Assign values for BatchRecords table addition
    #         file_dict = {
    #             'batch_id': item_id,
    #             'file_name': fname,
    #             'file_type': 'Sequence',
    #             'file_path': path,
    #             'create_date': datetime.now()
    #         }
    #
    # # Add file to BatchRecords table and commit all db changes
    # db.session.add(BatchRecords(**file_dict))
    # db.session.commit()

    # print(f'NEW DICT 2: {new_dict}')
    # print(f'FORM 2: {form.data}')

    # # Check if a batch record exists and update or add a new batch record
    # if BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id, BatchRecords.file_type == 'Sequence')).first():
    #     original = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
    #                                               BatchRecords.file_type == 'Sequence')).first()
    #
    #     update_item(form, original.id, BatchRecords, 'Batch Records', 'Batch Records', 'batch_records',
    #                 False, 'file_name', locking=False, **kwargs)
    #
    # else:
    #     print('IN ELSE STATEMENT')
    #     add_item(form, BatchRecords, 'Batch Records', 'Batch Records', 'batch_records', False,
    #              'file_name', **kwargs)

    # record = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
    #                                         BatchRecords.file_type == 'Sequence')).first()
    #
    # record.file_name = record.file_name.split('_')[0] + '_' + record.file_name.split('_')[1] + '.csv'
    # db.session.commit()
    # kwargs['batch_id'] = item_id
    # kwargs['file_name'] = fname
    # kwargs['file_type'] = 'Sequence'
    # kwargs['file_path'] = path
    # kwargs['create_date'] = datetime.now()

    # Replaced by add_item
    # # Assign values for BatchRecords table addition
    # file_dict = {
    #     'batch_id': item_id,
    #     'file_name': fname,
    #     'file_type': 'Sequence',
    #     'file_path': path,
    #     'create_date': datetime.now()
    # }
    #
    # # Add file to BatchRecords table and commit all db changes
    # db.session.add(BatchRecords(**file_dict))
    # db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/hamilton_samples', methods=['GET', 'POST'])
@login_required
def hamilton_samples(item_id):
    item = Batches.query.get(item_id)

    read_only = request.args.get('read_only')

    print(f'READ ONLY: {read_only}')

    # Initialize form
    form = HamiltonSampleCheck()

    # Get batch_constituents
    constituents = [item for item in BatchConstituents.query.filter_by(batch_id=item_id).all()]

    # Get worklist for batch
    worklist = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                              BatchRecords.file_type == 'Worklist')).first()

    work_df = pd.read_excel(worklist.file_path)

    non_blank_pos = [
        y['SampleCarrierPos'].split('-')[1].strip() if type(y['SampleCarrierPos']) != float
                                                       and y['SampleCarrierPos'][0] == '1' else None
        for x, y in work_df.iterrows()
    ]

    non_blank_pos = [int(pos) for pos in non_blank_pos if pos is not None]

    print(f'non_blank_pos: {non_blank_pos}')

    # Create worklist dataframe
    df = pd.read_excel(worklist.file_path)

    # Initialize relevant arrays and dict
    rack_1 = []
    rack_2 = []
    rack_3 = []
    rack_4 = []
    rack_1_scan = []
    rack_2_scan = []
    rack_3_scan = []
    rack_4_scan = []
    rack_1_checks = []
    rack_2_checks = []
    rack_3_checks = []
    rack_4_checks = []
    worklist_dict = {}

    # Create array of relevant letters for plate layout and initialize alphanumeric array
    alpha = ['A', 'B', 'C', 'D', 'E', 'F']
    alphanumeric = []

    # Create array of all alphanumeric plate positions
    for letter in alpha:
        for number in range(1, 9):
            alphanumeric.append(letter + str(number))

    # Create dictionary of samples with associate plate position and Tests table ID
    for x, y in df.iterrows():  # x is the index, y can access column names
        worklist_dict[y['Vial']] = {'samplename': y['SampleName'], 'platepos': y['FinalPlatePos'],
                                    'filterviallw': y['FilterVialLabware'],
                                    'test_id': Tests.query.filter(and_(Tests.batch_id == item_id,
                                                                       Tests.test_name ==
                                                                       y['SampleName'].strip())).value(Tests.id)}
        # If sample is in Hamilton Sample Carrier, Build racks 1 through 4
        if type(y['SampleCarrierPos']) != float:
            # Find sample carrier test/batch_constituent is in
            if y['SampleCarrierPos'][:1] == '1':
                # If sample is test, add to relevant sample carrier
                if Tests.query.filter(and_(Tests.batch_id == item_id, Tests.test_name == y['SampleName'].strip())) \
                        .value(Tests.id) is not None:
                    rack_1.append([y['SampleCarrierPos'], y['SampleName'].strip(),
                                   Tests.query.filter(and_(Tests.batch_id == item_id,
                                                           Tests.test_name ==
                                                           y['SampleName'].strip())).value(Tests.id)])
                # Add batch_constituent to relevant sample carrier (batch_constituents only in carrier 1)
                else:
                    for const in constituents:
                        try:
                            if const.constituent.constituent.name == y['SampleName'].strip():
                                # Ensure SampleCarrierPos has no spaces around the dash
                                sample_carrier_pos = y['SampleCarrierPos'].replace(' ', '') if ' ' in y[
                                    'SampleCarrierPos'] else y['SampleCarrierPos']

                                # Optionally validate that it matches the correct format
                                if not re.match(r'^\d+-\d+$', sample_carrier_pos):
                                    raise ValueError(f"Invalid format for SampleCarrierPos: {sample_carrier_pos}")

                                rack_1.append([sample_carrier_pos, y['SampleName'].strip(), const])
                        except AttributeError:
                            pass
            # Find sample carrier sample is in
            elif y['SampleCarrierPos'][:1] == '2':
                # If sample is test, add to relevant sample carrier
                if Tests.query.filter(and_(Tests.batch_id == item_id, Tests.test_name == y['SampleName'].strip())) \
                        .value(Tests.id) is not None:
                    rack_2.append([y['SampleCarrierPos'], y['SampleName'].strip(),
                                   Tests.query.filter(and_(Tests.batch_id == item_id,
                                                           Tests.test_name ==
                                                           y['SampleName'].strip())).value(Tests.id)])
                # Add batch_constituent to relevant sample carrier (batch_constituents only in carrier 1)
                else:
                    for const in constituents:
                        try:
                            if const.constituent.constituent.name == y['SampleName'].strip():
                                rack_2.append([y['SampleCarrierPos'], y['SampleName'].strip(), const])
                        except AttributeError:
                            pass

            elif y['SampleCarrierPos'][:1] == '3':
                rack_3.append([y['SampleCarrierPos'], y['SampleName'].strip(),
                               Tests.query.filter(and_(Tests.batch_id == item_id,
                                                       Tests.test_name ==
                                                       y['SampleName'].strip())).value(Tests.id)])

            elif y['SampleCarrierPos'][:1] == '4':
                rack_4.append([y['SampleCarrierPos'], y['SampleName'].strip(),
                               Tests.query.filter(and_(Tests.batch_id == item_id,
                                                       Tests.test_name ==
                                                       y['SampleName'].strip())).value(Tests.id)])

    # Create checked racks
    for sample in rack_1:
        # If sample has not been checked, add 'None' to check
        if sample[2] is None or sample[2] == 'None Selected':
            rack_1_checks.append([sample[2], sample[0], None])
        # Else find if sample is test or batch_constituent and add check status
        elif type(sample[2]) == BatchConstituents:
            rack_1_checks.append([sample[2], sample[0], sample[2].load_check])
            sample[2] = sample[2].id
        else:
            rack_1_checks.append([sample[2], sample[0], Tests.query.get(sample[2]).load_check])

    for sample in rack_2:
        if sample[2] is None or sample[2] == 'None Selected':
            rack_2_checks.append([sample[2], sample[0], None])
        elif type(sample[2]) == BatchConstituents:
            rack_2_checks.append([sample[2], sample[0], sample[2].load_check])
            sample[2] = sample[2].id
        else:
            rack_2_checks.append([sample[2], sample[0], Tests.query.get(sample[2]).load_check])

    for sample in rack_3:
        if sample[2] is None or sample[2] == 'None Selected':
            rack_3_checks.append([sample[2], sample[0], None])
        else:
            rack_3_checks.append([sample[2], sample[0], Tests.query.get(sample[2]).load_check])

    for sample in rack_4:
        if sample[2] is None or sample[2] == 'None Selected':
            rack_4_checks.append([sample[2], sample[0], None])
        else:
            rack_4_checks.append([sample[2], sample[0], Tests.query.get(sample[2]).load_check])

    if form.is_submitted() and form.validate():
        for field in form:
            # Get test_id from field.data
            if field.name == 'submit' or field.name == 'csrf_token':
                scan_id = None
                scan_table = None
            # Make sure field data is present adn assign scan_id
            elif field.data != '':
                scan_id = field.data.split()[1]
                # Assign relevant table for querying
                if field.data.split()[0] == 'tests:':
                    scanned_name = Tests.query.get(scan_id).test_name
                    scan_table = Tests
                elif field.data.split()[0] == 'qr_reference:':
                    scanned_name = QRReference.query.get(scan_id).text
                    scan_table = QRReference
                elif field.data.split()[0] == 'batch_constituents:':
                    scanned_name = BatchConstituents.query.get(scan_id).constituent.constituent.name
                    scan_table = BatchConstituents
                else:
                    pass
            else:
                scan_id = None
                scan_table = None
            # Check current field is not date field
            if field.name[0] == '1' and field.name[-4:] != 'date':
                # Check if field had scan entered
                if scan_id is not None:
                    for search in form:
                        # Find matching date field
                        if search.name[0] == '1' and search.name.split("_")[0] == field.name and \
                                search.name[-4:] == 'date':
                            # Set check datetime
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    rack_1_scan.append([field.name, scanned_name, scan_id, field_date, scan_table])

            elif field.name[0] == '2' and field.name[-4:] != 'date':
                if scan_id is not None:
                    for search in form:
                        if search.name[0] == '2' and search.name.split("_")[0] == field.name and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    rack_2_scan.append([field.name, scanned_name, scan_id, field_date, scan_table])
                    print(f'RACK 2 SCAN: {rack_2_scan}')

            elif field.name[0] == '3' and field.name[-4:] != 'date':
                if scan_id is not None:
                    for search in form:
                        if search.name[0] == '3' and search.name.split("_")[0] == field.name and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    rack_3_scan.append([field.name, scanned_name, scan_id, field_date, scan_table])
                    print(f'RACK 3 SCAN: {rack_3_scan}')

            elif field.name[0] == '4' and field.name[-4:] != 'date':
                if scan_id is not None:
                    for search in form:
                        if search.name[0] == '4' and search.name.split("_")[0] == field.name and \
                                search.name[-4:] == 'date':
                            field_date = datetime.strptime(search.data, "%Y-%m-%d %H:%M:%S")
                    rack_4_scan.append([field.name, scanned_name, scan_id, field_date, scan_table])
                    print(f'RACK 4 SCAN: {rack_4_scan}')

        # Compare scan rack 1 to rack 1 key
        # [v == field.name (e.g., 1-1), w == test_name, x == scan_id, y == field_date, z == scan_table]
        for v, w, x, y, z in rack_1_scan:
            for a, b, c in rack_1:  # [a == SampleCarrierPos (e.g., 1-1), b == SampleName, c == test_id]
                if x is None:
                    continue
                # Check if plate positions match
                elif v == a:
                    if z == QRReference:
                        # Check if scan table is QRReference
                        for sample in rack_1:
                            if sample[0] == v:
                                Tests.query.get(sample[2]).load_check_by = current_user.id
                                Tests.query.get(sample[2]).load_checked_date = y
                                Tests.query.get(sample[2]).load_check = w
                                db.session.commit()
                    else:
                        # Check if test ids match
                        if int(x) == c:
                            z.query.get(x).load_check_by = current_user.id
                            z.query.get(x).load_checked_date = y
                            z.query.get(x).load_check = 'Completed / Automated'
                            db.session.commit()

        for v, w, x, y, z in rack_2_scan:
            for a, b, c in rack_2:  # [a == SampleCarrierPos (e.g., 1-1), b == SampleName, c == test_id]
                if x is None:
                    continue
                # Check if plate positions match
                elif v == a:
                    if z == QRReference:
                        # Check if scan table is QRReference
                        for sample in rack_2:
                            if sample[0] == v:
                                Tests.query.get(sample[2]).load_check_by = current_user.id
                                Tests.query.get(sample[2]).load_checked_date = y
                                Tests.query.get(sample[2]).load_check = w
                                db.session.commit()
                    # Check if test ids match
                    if int(x) == c:
                        z.query.get(x).load_check_by = current_user.id
                        z.query.get(x).load_checked_date = y
                        z.query.get(x).load_check = 'Completed / Automated'
                        db.session.commit()

        for v, w, x, y, z in rack_3_scan:
            for a, b, c in rack_3:  # [a == SampleCarrierPos (e.g., 1-1), b == SampleName, c == test_id]
                if x is None:
                    continue
                # Check if plate positions match
                elif v == a:
                    if z == QRReference:
                        # Check if scan table is QRReference
                        for sample in rack_3:
                            if sample[0] == v:
                                Tests.query.get(sample[2]).load_check_by = current_user.id
                                Tests.query.get(sample[2]).load_checked_date = y
                                Tests.query.get(sample[2]).load_check = w
                                db.session.commit()
                    # Check if test ids match
                    if int(x) == c:
                        z.query.get(x).load_check_by = current_user.id
                        z.query.get(x).load_checked_date = y
                        z.query.get(x).load_check = 'Completed / Automated'
                        db.session.commit()

        for v, w, x, y, z in rack_4_scan:
            for a, b, c in rack_4:  # [a == SampleCarrierPos (e.g., 1-1), b == SampleName, c == test_id]
                if x is None:
                    continue
                # Check if plate positions match
                elif v == a:
                    if z == QRReference:
                        # Check if scan table is QRReference
                        for sample in rack_4:
                            if sample[0] == v:
                                Tests.query.get(sample[2]).load_check_by = current_user.id
                                Tests.query.get(sample[2]).load_checked_date = y
                                Tests.query.get(sample[2]).load_check = w
                                db.session.commit()
                    # Check if test ids match
                    if int(x) == c:
                        z.query.get(x).load_check_by = current_user.id
                        z.query.get(x).load_checked_date = y
                        z.query.get(x).load_check = 'Completed / Automated'
                        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    if read_only:
        return render_template(
            f'{table_name}/hamilton_load_read.html',
            item=item,
            form=form,
            rack_1=rack_1,
            rack_2=rack_2,
            rack_3=rack_3,
            rack_4=rack_4,
            rack_1_checks=rack_1_checks,
            rack_2_checks=rack_2_checks,
            rack_3_checks=rack_3_checks,
            rack_4_checks=rack_4_checks,
            non_blank_pos=non_blank_pos
        )
    else:
        return render_template(
            f'{table_name}/hamilton_samples.html',
            item=item,
            form=form,
            rack_1=rack_1,
            rack_2=rack_2,
            rack_3=rack_3,
            rack_4=rack_4,
            rack_1_checks=rack_1_checks,
            rack_2_checks=rack_2_checks,
            rack_3_checks=rack_3_checks,
            rack_4_checks=rack_4_checks,
            non_blank_pos=non_blank_pos
        )


@blueprint.route(f'/{table_name}/<int:item_id>/requisition_check', methods=['GET', 'POST'])
@login_required
def requisition_check(item_id):
    # only for REF assay
    form = BarcodeCheck()
    item = Batches.query.get(item_id)
    fix_this = request.args.get('fix_this', None)

    # If user is EA: query tests that are in the batch, have not been checked, and are in the EA's possession
    if current_user.initials == item.extractor.initials:
        if fix_this is not None:
            tests = [test for test in Tests.query.join(Specimens,
                                                       Tests.specimen).options(joinedload(Tests.specimen)).filter(
                and_(Tests.batch_id == item.id, Tests.id == fix_this,
                     Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)]
        else:
            tests = [test for test in Tests.query.join(Specimens,
                                                       Tests.specimen).options(joinedload(Tests.specimen)).filter(
                and_(Tests.batch_id == item.id, Tests.gcet_checked_by.is_(None),
                     Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)]  # storage_location?
        # Append skipped tests to the end of the array
        first_skipped_test = Tests.query.filter(
            and_(Tests.batch_id == item.id, Tests.gcet_specimen_check == 'Skipped')).first()
        if first_skipped_test and first_skipped_test not in tests:
            tests.extend([test for test in Tests.query.join(Specimens,
                                                            Tests.specimen).options(joinedload(Tests.specimen)).filter(
                and_(Tests.batch_id == item.id, Tests.gcet_specimen_check == 'Skipped',
                     Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)])
    else:
        tests = []
    # Check form submission
    if form.is_submitted():
        # Check if skip was selected
        if not form.source_specimen.data:
            # if form.source_specimen.data:
            tests[0].gcet_specimen_check = 'Skipped'
            tests[0].gcet_checked_by = None
            tests[0].gcet_checked_date = datetime.now()
            form.test_specimen.data = ''
            form.source_specimen.data = ''
            db.session.commit()
        # Check if a qr code from the qr_reference table was scanned in source
        elif 'qr_reference' in form.source_specimen.data.split(': ')[0]:
            tests[0].gcet_checked_by = current_user.id
            tests[0].gcet_specimen_check = QRReference.query.get(form.source_specimen.data.split(': ')[1]).text
            tests[0].gcet_checked_date = datetime.now()
            form.source_specimen.data = ''
        # no qr_reference scan, set relevant check data
        elif 'qr_reference: ' not in form.source_specimen.data.split(': ')[0]:
            tests[0].gcet_checked_by = current_user.id
            tests[0].gcet_specimen_check = form.source_specimen.data
            tests[0].gcet_checked_date = datetime.now()
            form.source_specimen.data = ''

        # Commit
        db.session.commit()

        # Remove the checked test from the list
        tests.pop(0)

        # If there are still tests in tests, return the next page for checking
        if tests:
            return render_template(
                f'{table_name}/requisition_check.html',
                item=tests[0],
                form=form,
                assay=item.assay.assay_name
            )
        # Redirect to batch view if no more tests remain
        else:
            return redirect(url_for(f'{table_name}.view', item_id=item_id))

    if tests:
        return render_template(
            f'{table_name}/requisition_check.html',
            item=tests[0],
            form=form,
            assay=item.assay.assay_name
        )
    # Redirect to batch view if no more tests remain
    else:
        return redirect(url_for(f'{table_name}.all_tests', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/<method>/populate_constituents', methods=['GET', 'POST'])
@login_required
def populate_constituents(item_id, method):
    # kwargs = default_kwargs.copy()
    kwargs = {}
    item = table.query.get(item_id)
    form = PopulateConstituents()

    if 'REF' in item.assay.assay_name:
        assay_key = 'REF'
    elif 'GCDP' in item.assay.assay_name:
        assay_key = item.gcdp_assay.assay_name.split('-')[0]
    else:
        assay_key = item.assay.assay_name.split('-')[0]

    # Initialize variables
    populated_from = ''
    include_checks = False
    specimen_check = None
    transfer_check = None
    load_check = 'N/A'
    gcet_specimen_check = 'N/A'
    sequence_check = None

    encoding = 'utf-8-sig'

    headers = SequenceHeaderMappings.query.filter_by(batch_template_id=item.batch_template_id).first()

    # Check out constituent is being populated and set variables
    if method == 'automated':
        populated_from = 'Sequence'
        include_checks = True
    elif method == 'Manual':
        populated_from = 'Manual'
        include_checks = False
        transfer_check = 'N/A'
        sequence_check = 'N/A'
        load_check = 'N/A'
    elif method == 'default':
        populated_from = 'Default'
        include_checks = True

    if 'specimen_check' not in required_checks[assay_key]:
        specimen_check = 'N/A'
    if transfer_check is None and 'transfer_check' not in required_checks[assay_key]:
        transfer_check = 'N/A'
    if sequence_check is None and 'sequence_check' not in required_checks[assay_key]:
        sequence_check = None

    # Check if constituents already in BatchConstituents and delete if so
    if len(BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item_id,
                                               BatchConstituents.populated_from == populated_from)).all()) > 0:
        for const in BatchConstituents.query.filter(and_(BatchConstituents.batch_id == item_id,
                                                         BatchConstituents.populated_from == populated_from)):
            kwargs['request'] = 'POST'
            delete_item(form, const.id, BatchConstituents, 'batch_constituents', 'Batch Constituents', 'id',
                        admin_only=False, **kwargs)

    # Batch sequence, make sure default not selected because ws not required for default
    if populated_from != 'Default':
        # if 'QTON' in item.assay.assay_name:
        #     sequences = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
        #                                                BatchRecords.file_type == 'Sequence')).all()
        ws_sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                     BatchRecords.file_type == 'Sequence')).first().file_path

    # Set csv encoding and sample type names for standards in relevant assay
    if 'LCQD' in item.assay.assay_name or 'LCCI' in item.assay.assay_name or 'LCFS' in item.assay.assay_name:
        controls = ['Standard', 'QC', 'Solvent']
    elif 'GCET' in item.assay.assay_name:
        controls = ['Calibration', 'Control Sample']
    elif 'QTON' in item.assay.assay_name:
        controls = ['Standard', 'QualityControl', 'Solvent']
    elif item.assay.assay_name in ['GCVO-ZZ', 'GCNO-ZZ']:
        controls = ['DoubleBlank', 'Cal', 'MatrixBlank']
    elif 'GCDP' in item.assay.assay_name:
        if 'LCQD' in item.gcdp_assay.assay_name or 'LCCI' in item.gcdp_assay.assay_name or 'LCFS' in item.gcdp_assay.assay_name:
            controls = ['Standard', 'QC', 'Solvent']
        elif 'GCET' in item.gcdp_assay.assay_name:
            controls = ['Calibration', 'Control Sample']
        elif 'QTON' in item.gcdp_assay.assay_name:
            controls = ['Standard', 'QualityControl', 'Solvent']
        elif item.gcdp_assay.assay_name in ['GCVO-ZZ', 'GCNO-ZZ']:
            controls = ['DoubleBlank', 'Cal', 'MatrixBlank']
    else:
        controls = []

    # Check populated_from
    if populated_from == 'Sequence':
        # Build dictionary of constituents from sequence
        # constituents = {y[headers.vial_position]: [y[headers.comments], y[headers.sample_name]] for x, y in
        #                 pd.read_csv(ws_sequence, encoding=encoding).iterrows() if
        #                 y[headers.sample_type] in controls or 'Blank' in y[headers.sample_name] or
        #                 'BLANK' in y[headers.sample_name]}

        # Initialize an empty dictionary
        constituents = {}

        # Iterate over the rows of the CSV file
        for x, y in pd.read_csv(ws_sequence, encoding=encoding).iterrows():
            # Check if the sample type or name matches the conditions
            if y[headers.sample_type] in controls or 'Blank' in y[headers.sample_name] or 'BLANK' in \
                    y[headers.sample_name]:
                # Check if the key already exists in the dictionary
                if y[headers.vial_position] not in constituents:
                    # Add the entry if the key does not exist
                    constituents[y[headers.vial_position]] = [y[headers.comments], y[headers.sample_name]]

        # Iterate through dictionary
        for k, v in constituents.items():
            # Initialize / reset field_data
            if 'Blank' in v[1] and 'Recon' not in v[1] and method == 'automated':
                load_check_input = None
            else:
                load_check_input = load_check

            if 'LCCI' in item.assay.assay_name and v[1] in ['LOD (LCCI) A', 'QL1 (LCCI) A', 'QH1 (LCCI) A']:
                transfer_check_input = None
            else:
                transfer_check_input = transfer_check

            field_data = {}
            # Update field_data with relevant data
            field_data.update({
                'db_status': 'Active',
                'locked': False,
                'create_date': datetime.now(),
                'created_by': current_user.initials,
                'revision': 0,
                'pending_submitter': None,
                'batch_id': item_id,
                'constituent_type': v[1],
                'populated_from': populated_from,
                'include_checks': include_checks,
                'transfer_check': transfer_check_input,
                'sequence_check': sequence_check,
                'vial_position': k,
                'specimen_check': specimen_check,
                'load_check': load_check_input,
                'gcet_specimen_check': gcet_specimen_check
            })

            # Because a new entry is being added, get the latest table id and add 1
            if BatchConstituents.query.count():
                record_id = BatchConstituents.query.order_by(BatchConstituents.id.desc()).first().id + 1
            else:
                record_id = BatchConstituents.query.count() + 1

            # Modification for creating the batch_id entry
            modification = Modifications(
                event='CREATED',
                status='Approved',
                table_name='Batch Constituents',
                record_id=record_id,
                revision=0,
                field='Batch ID',
                field_name='batch_id',
                new_value=item_id,
                new_value_text=item_id,
                submitted_by=current_user.id,
                submitted_date=datetime.now(),
                reviewed_by=current_user.id,
                review_date=datetime.now()
            )
            # Add modification item
            db.session.add(modification)

            # Modification for creating the constituent_type entry
            modification = Modifications(
                event='CREATED',
                status='Approved',
                table_name='Batch Constituents',
                record_id=record_id,
                revision=0,
                field='Constituent Type',
                field_name='constituent_type',
                new_value=v[1],
                new_value_text=v[1],
                submitted_by=current_user.id,
                submitted_date=datetime.now(),
                reviewed_by=current_user.id,
                review_date=datetime.now()
            )
            # Add modification item
            db.session.add(modification)

            # Add entry to Batch Constituents
            db.session.add(BatchConstituents(**field_data))

    elif populated_from == 'Default':
        # Build constituent list from default_constituents table
        if 'GCDP' in item.assay.assay_name:
            default_constituents = DefaultAssayConstituents.query.filter_by(assay_id=item.gcdp_assay_id) \
                .first().constituent_id
        else:
            default_constituents = DefaultAssayConstituents.query.filter_by(assay_id=item.assay_id) \
                .first().constituent_id
        # Get IDs of default constituents
        const_id = [int(const) for const in default_constituents.split(', ')]
        # Find each sequence_constituent for each default_constituent
        matches = [SequenceConstituents.query.filter_by(constituent_type=curr_const).first() for
                   curr_const in const_id]
        # Create dictionary of sequence name and ID
        constituents = {seq.sequence_name: seq.id for seq in matches}

        # Iterate through dictionary
        for k, v in constituents.items():
            # Initialize / reset field_data dict
            field_data = {}
            # Update field_data with relevant data
            field_data.update({'db_status': 'Active',
                               'locked': False,
                               'create_date': datetime.now(),
                               'created_by': current_user.initials,
                               'revision': 0,
                               'pending_submitter': None,
                               'batch_id': item_id,
                               'constituent_type': k,
                               'populated_from': populated_from,
                               'include_checks': include_checks,
                               'transfer_check': transfer_check,
                               'sequence_check': sequence_check
                               })

            # Because a new entry is being added, get the latest table id and add 1
            if BatchConstituents.query.count():
                record_id = BatchConstituents.query.order_by(BatchConstituents.id.desc()).first().id + 1
            else:
                record_id = BatchConstituents.query.count() + 1

            # Modification for creating the batch_id entry
            modification = Modifications(
                event='CREATED',
                status='Approved',
                table_name='Batch Constituents',
                record_id=record_id,
                revision=0,
                field='Batch ID',
                field_name='batch_id',
                new_value=item_id,
                new_value_text=item_id,
                submitted_by=current_user.id,
                submitted_date=datetime.now(),
                reviewed_by=current_user.id,
                review_date=datetime.now()
            )
            # Add modification item
            db.session.add(modification)

            # Modification for creating the constituent_type entry
            modification = Modifications(
                event='CREATED',
                status='Approved',
                table_name='Batch Constituents',
                record_id=record_id,
                revision=0,
                field='Constituent Type',
                field_name='constituent_type',
                new_value=k,
                new_value_text=k,
                submitted_by=current_user.id,
                submitted_date=datetime.now(),
                reviewed_by=current_user.id,
                review_date=datetime.now()
            )
            # Add modification item
            db.session.add(modification)

            # Add entry to Batch Constituents
            db.session.add(BatchConstituents(**field_data))

    else:  # May not be needed, consider effects if deleted - TLD
        constituents = {}
        field_data = {}

    # # Iterate through dictionary
    # for k, v in constituents.items():
    #     # Initialize / reset field_data dict
    #     field_data = {}
    #     # Update field_data with relevant data
    #     field_data.update({'db_status': 'Active',
    #                        'locked': False,
    #                        'create_date': datetime.now(),
    #                        'created_by': current_user.initials,
    #                        'revision': 0,
    #                        'pending_submitter': None,
    #                        'batch_id': item_id,
    #                        'constituent_type': k,
    #                        'populated_from': populated_from,
    #                        'include_checks': include_checks,
    #                        'transfer_check': transfer_check,
    #                        'sequence_check': sequence_check
    #                        })

    # # Because a new entry is being added, get the latest table id and add 1
    # if BatchConstituents.query.count():
    #     record_id = BatchConstituents.query.order_by(BatchConstituents.id.desc()).first().id + 1
    # else:
    #     record_id = BatchConstituents.query.count() + 1
    #
    # # Modification for creating the batch_id entry
    # modification = Modifications(
    #     event='CREATED',
    #     status='Approved',
    #     table_name='Batch Constituents',
    #     record_id=record_id,
    #     revision=0,
    #     field='Batch ID',
    #     field_name='batch_id',
    #     new_value=item_id,
    #     new_value_text=item_id,
    #     submitted_by=current_user.id,
    #     submitted_date=datetime.now(),
    #     reviewed_by=current_user.id,
    #     review_date=datetime.now()
    # )
    # # Add modification item
    # db.session.add(modification)
    #
    # # Modification for creating the constituent_type entry
    # modification = Modifications(
    #     event='CREATED',
    #     status='Approved',
    #     table_name='Batch Constituents',
    #     record_id=record_id,
    #     revision=0,
    #     field='Constituent Type',
    #     field_name='constituent_type',
    #     new_value=k,
    #     new_value_text=k,
    #     submitted_by=current_user.id,
    #     submitted_date=datetime.now(),
    #     reviewed_by=current_user.id,
    #     review_date=datetime.now()
    # )
    # # Add modification item
    # db.session.add(modification)
    #
    # # Add entry to Batch Constituents
    # db.session.add(BatchConstituents(**field_data))

    # Commit all additions
    db.session.commit()

    # May not be needed, consider effects if deleted - TLD
    batch_const = BatchConstituents.query.filter_by(batch_id=item_id)

    # if method == 'automated':
    #
    #     if ws_sequence is not None:
    #         df = pd.read_csv(ws_sequence, encoding='cp1250')
    #         print(f'DF: {df}')
    #
    #     # y = column, i.e., y['Type'] will iterate through each row and get the type
    #     for x, y in df.iterrows():
    #         for const in batch_const:
    #             if const.constituent_type == y[headers.sample_name]:
    #                 const.vial_position = y[headers.vial_position]
    #
    #     db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/clear_constituent', methods=['GET', 'POST'])
@login_required
def clear_constituent(item_id):
    item = BatchConstituents.query.get(item_id)
    # Set of columns inherited from BaseTemplate
    base_columns = set(attr for attr in dir(BaseTemplate) if isinstance(getattr(BaseTemplate, attr), db.Column))

    # Iterate through columns and set to None for relevant columns
    for column in item.__table__.columns:
        if column.name not in ['batch_id', 'populated_from', 'constituent_type', 'include_checks', 'vial_position'] \
                and column.name not in base_columns:
            setattr(item, column.name, None)

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item.batch_id))


@blueprint.route(f'/{table_name}/<int:item_id>/checkbox_change', methods=['GET', 'POST'])
@login_required
def checkbox_change(item_id):
    item = BatchConstituents.query.get(item_id)
    batch_id = item.batch_id

    # Create arrays of check types
    checks = ['transfer_check', 'sequence_check']
    date_checks = ['transfer_check_date', 'sequence_check_date']
    checks_by = ['transfer_check_by', 'sequence_check_by']
    gcet_checks = ['gcet_sequence_check', 'gcet_sequence_check_by']

    if table.query.get(batch_id).technique == 'Hamilton':
        checks.append('load_check')

    # Switch include_checks to opposite
    item.include_checks = not item.include_checks

    # Check for GCET to clear all checks and GCET specific checks
    # Can be updated with new GCET process, consider effects first - TLD
    if 'GCET' in item.batch.assay.assay_name:
        if item.include_checks:
            for x in checks:
                setattr(item, x, None)
            for x in date_checks:
                setattr(item, x, None)
            for x in checks_by:
                setattr(item, x, None)
            for x in gcet_checks:
                setattr(item, x, None)
        else:
            for x in checks:
                setattr(item, x, 'N/A')
            for x in date_checks:
                setattr(item, x, None)
            for x in checks_by:
                setattr(item, x, None)
            for x in gcet_checks:
                setattr(item, x, None)
    else:
        # Clear checks for all other assays
        if item.include_checks:
            for x in checks:
                setattr(item, x, None)
            for x in date_checks:
                setattr(item, x, None)
            for x in checks_by:
                setattr(item, x, None)
        else:
            for x in checks:
                setattr(item, x, 'N/A')
            for x in date_checks:
                setattr(item, x, None)
            for x in checks_by:
                setattr(item, x, None)

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=batch_id))


@blueprint.route(f'/{table_name}/<int:item_id>/manual_transfer', methods=['GET', 'POST'])
@login_required
def manual_transfer_check(item_id):
    # Initialize form
    form = BarcodeCheck()
    # Get batch
    batch = table.query.get(item_id)
    # Initialize constituents array
    constituents = []

    # for const in BatchConstituents.query.filter_by(batch_id=item.id):
    #     if const.constituent_id is not None and const.transfer_check_by is None:
    #         constituents.append((const.constituent_type, const.constituent.constituent.name, const))
    #     elif const.reagent_id is not None and const.transfer_check_by is None:
    #         constituents.append((const.constituent_type, const.reagent.const.name, const))
    #     else:
    #         pass

    for const in BatchConstituents.query.filter_by(batch_id=batch.id):
        # Get relevant columns for constituents (constituent vs. reagent columns)
        if const.constituent_id is not None:
            constituents.append((const.constituent_type, const.constituent.constituent.name, const))
        elif const.reagent_id is not None:
            constituents.append((const.constituent_type, const.reagent.const.name, const))
        else:
            pass
    # Set tests array to all batch_constituents and tests, ensure batch_constituents are extracted
    tests = [z for x, y, z in constituents
             if getattr(SequenceConstituents.query.filter_by(sequence_name=x).first(), 'extracted', False)]

    tests += [test for test in Tests.query.filter_by(batch_id=item_id)]

    # # If user is EA: query tests that are in the batch, have not been checked, and are in the EA's possession
    # if current_user.initials == item.extractor.initials:
    #     if item.technique == 'Manual':
    #         for x, y, z in constituents:
    #             if SequenceConstituents.query.filter_by(sequence_name=x).first().extracted:
    #                 tests.append(z)
    #
    #     tests += [test for test in Tests.query.join(Specimens,
    #                                                 Tests.specimen).options(joinedload(Tests.specimen)).filter(
    #         and_(Tests.batch_id == item.id, Tests.transfer_check_by.is_(None),
    #              Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)]  # storage_location?
    #
    #     # Append skipped tests to the end of the array
    #     if Tests.query.filter(and_(Tests.batch_id == item.id, Tests.transfer_check == 'Skipped')).first():
    #         tests += [test for test in Tests.query.join(Specimens,
    #                                                     Tests.specimen).options(joinedload(Tests.specimen)).filter(
    #             and_(Tests.batch_id == item.id, Tests.transfer_check.is_('Skipped'),
    #                  Specimens.custody == item.extractor.initials)).order_by(Tests.test_id)]
    # else:
    #     tests = []

    # Testing dilution instructions
    # for test in tests:
    #     if test.id == 78768:
    #         test.directive = '(d1/2)'
    #         # test.directive = '(d1/5)'
    #         # test.directive = 'HV(d1/2)'
    #         # test.directive = '(d1/20)'
    #         db.session.commit()

    # Check form submission
    if form.is_submitted():
        # Initialize batch_item (only one at a time)
        batch_item = []
        # Get source [table, id]
        source = form.source_specimen.data.split(': ')

        # Get item from relevant table
        if source[0] == 'tests':
            batch_item = Tests.query.get(source[1])
        elif source[0] == 'batch_constituents':
            batch_item = BatchConstituents.query.get(source[1])

        # Initialize skipped_item
        skipped_item = batch_item

        try:
            # Make sure batch_item is the same as the item scanned in
            if batch_item.id == int(request.form.get(f'testScan1').split(': ')[1]) or 'qr_reference' in \
                    request.form.get(f'testScan1').split(': ')[0]:
                # Check if qr_reference scanned in for batch item and set transfer check
                if 'qr_reference' in request.form.get(f'testScan1').split(': ')[0]:
                    batch_item.transfer_check = QRReference.query.get(
                        int(request.form.get(f'testScan1').split(': ')[1])).text
                # Batch item successfully scanned
                else:
                    batch_item.transfer_check = 'Completed / Automated'

                # Set relevant columns and remove batch_item from skipped
                batch_item.transfer_check_by = current_user.id
                batch_item.transfer_check_date = datetime.now()
                skipped_item = None
        # Batch item was skipped
        except IndexError:
            print('BLANK INPUT')
        # Handle potential attribute errors
        except AttributeError:
            print(f'ATTRIBUTE ERROR: {request.form.get("testScan1")}')

        # Set skipped data if batch item was skipped
        if skipped_item is not None:
            skipped_item.transfer_check = 'Skipped'
            skipped_item.transfer_check_date = None
            skipped_item.transfer_check_by = None

        db.session.commit()

        # Clear form field
        form.source_specimen.data = ''

        return render_template(
            f'{table_name}/manual_transfer.html',
            batch=batch,
            form=form,
            assay=batch.assay.assay_name,
            tests=tests
        )

    return render_template(
        f'{table_name}/manual_transfer.html',
        batch=batch,
        form=form,
        assay=batch.assay.assay_name,
        tests=tests
    )

    #     # Check if skip was selected
    #     if not form.source_specimen.data and not form.test_specimen.data and \
    #             (('qr_reference' not in form.source_specimen.data and 'qr_reference' not in form.test_specimen.data)
    #              or ('GCET' in batch.assay.assay_name and not form.test_specimen_2.data and
    #                  'qr_reference' not in form.test_specimen_2.data and 'qr_reference' not in form.test_specimen.data)):
    #         # if form.source_specimen.data is None or form.test_specimen.data is None:
    #         tests[0].transfer_check = 'Skipped'
    #         tests[0].transfer_check_by = 'Skipped'
    #         tests[0].transfer_check_date = datetime.now()
    #         form.test_specimen.data = ''
    #         form.source_specimen.data = ''
    #         db.session.commit()
    #     # Check if a qr code form the qr_reference table was scanned in either test
    #     elif 'qr_reference: ' in form.test_specimen.data or 'qr_reference: ' in form.test_specimen_2.data \
    #             or 'qr_reference: ' in form.source_specimen.data:
    #         # Set relevant values for test it was scanned into
    #         tests[0].transfer_check_by = current_user.id
    #         try:
    #             tests[0].transfer_check = QRReference.query.get(form.test_specimen.data.split(' ')[1]).text
    #         except IndexError:
    #             tests[0].transfer_check = QRReference.query.get(form.source_specimen.data.split(' ')[1]).text
    #         tests[0].transfer_check_date = datetime.now()
    #         form.test_specimen.data = ''
    #         form.source_specimen.data = ''
    #         form.test_specimen_2.data = ''
    #         # Commit
    #         db.session.commit()
    #     # qr_reference code not scanned, form not skipped
    #     else:
    #         # Set current tests to checked by current user and checked at current datetime
    #         tests[0].transfer_check_by = current_user.id
    #         tests[0].transfer_check = 'Complete / Automated'
    #         tests[0].transfer_check_date = datetime.now()
    #         form.source_specimen.data = ''
    #         form.test_specimen.data = ''
    #         form.test_specimen_2.data = ''
    #         # Commit
    #         db.session.commit()
    #
    #     # Remove the checked test from the list
    #     tests.pop(0)
    #
    #     # If there are still tests in tests, return the next page for checking
    #     # Determine if REF assay
    #     if 'REF' in batch.assay.assay_name and tests:
    #         return render_template(
    #             f'{table_name}/ref_barcode_check.html',
    #             batch=batch,
    #             form=form,
    #             assay=batch.assay.assay_name,
    #             tests=tests
    #         )
    #     elif tests:
    #         return render_template(
    #             f'{table_name}/manual_transfer.html',
    #             batch=batch,
    #             form=form,
    #             assay=batch.assay.assay_name,
    #             tests=tests
    #         )
    #     # Redirect to batch view if no more tests remain
    #     else:
    #         return redirect(url_for(f'{table_name}.view', item_id=item_id))
    #
    # # Return correct view based on assay
    # if 'REF' in batch.assay.assay_name:
    #     return render_template(
    #         f'{table_name}/ref_barcode_check.html',
    #         batch=batch,
    #         form=form,
    #         assay=batch.assay.assay_name,
    #         tests=tests
    #     )
    # else:
    #     return render_template(
    #         f'{table_name}/manual_transfer.html',
    #         batch=batch,
    #         form=form,
    #         assay=batch.assay.assay_name,
    #         tests=tests
    #     )


@blueprint.route(f'/{table_name}/get_batch_information/', methods=['GET', 'POST'])
@login_required
def get_batch_information():
    start = time.time()
    # Get source and batch_id
    source = request.args.get('input').split(':')
    batch_id = request.args.get('item_id')
    batch_func = request.args.get('batch_func')

    # Initialize relevant variables
    tests = ''
    source_out = ''
    idx = 0
    values = []
    value = []
    out_table = ''

    if batch_func == 'transfer':
        # Set relevant data for reference batch
        if 'REF' in Batches.query.get(batch_id).assay.assay_name:
            specimen = Specimens.query.get(source[1])
            source_out = {'specimen': specimen.case.case_number, 'data-value': specimen.id}
            values = [[item.vial_position, item.test_name, item.gcet_specimen_check, str(item.gcet_specimen_check),
                       item.transfer_check, item.dilution] for item in
                      Tests.query.filter(and_(Tests.specimen_id == source[1], Tests.batch_id == batch_id))]
        # Set relevant data to variables dependant on input
        elif source[0] == 'specimens' or source[0] == 's':
            specimen = Specimens.query.get(source[1])
            source_out = {'specimen': f'{specimen.case.case_number} {specimen.accession_number} [{specimen.type.code}]',
                          'data-value': specimen.id}
            values = [
                [item.vial_position, item.test_name, item.test_id, str(item.id), item.transfer_check, item.dilution]
                for item in Tests.query.filter(and_(Tests.specimen_id == source[1], Tests.batch_id == batch_id))]
            out_table = 'tests'
        elif source[0] == 'standards_and_solutions':
            specimen = BatchConstituents.query.filter_by(constituent_id=source[1]).first()
            source_out = {'specimen': specimen.constituent.lot, 'data-value': specimen.constituent.id}
            values = [[item.vial_position, item.constituent.lot, item.constituent.id, str(item.id), item.transfer_check,
                       '', ''] for item in
                      BatchConstituents.query.filter(and_(BatchConstituents.constituent_id == source[1],
                                                          BatchConstituents.batch_id == batch_id))]
            out_table = 'batch_constituents'
        elif source[0] == 'solvents_and_reagents':
            specimen = BatchConstituents.query.filter_by(reagent_id=source[1]).first()
            source_out = {'specimen': specimen.reagent.name, 'data-value': specimen.reagent.id}
            values = [
                [item.vial_position, item.reagent.name, item.reagent.id, str(item.id), item.transfer_check, '', '']
                for item in BatchConstituents.query.filter(and_(BatchConstituents.reagent_id == source[1],
                                                                BatchConstituents.batch_id == batch_id))]
            out_table = 'batch_constituents'
        elif source[0] == 'tests':
            specimen = Tests.query.get(source[1])
            if int(specimen.batch_id) == int(batch_id):
                value = [specimen.vial_position, specimen.test_name, specimen.test_id, str(specimen.id),
                         specimen.transfer_check, specimen.dilution, specimen.directives]
                source_out = {'specimen': f'{specimen.test_name}',
                              'data-value': specimen.id}
                out_table = 'tests'
            else:
                value = []
                source_out = {}
                out_table = ''
        elif source[0] == 'batch_constituents':
            specimen = BatchConstituents.query.get(source[1])
            if specimen.constituent_id is not None:
                value = [specimen.vial_position, specimen.constituent.lot, specimen.constituent.id, str(specimen.id),
                         specimen.transfer_check, '', '']
                source_out = {'specimen': specimen.constituent.lot, 'data-value': specimen.constituent.id}
            else:
                value = [specimen.vial_position, specimen.reagent.name, specimen.reagent.id, str(specimen.id),
                         specimen.transfer_check, '', '']
                source_out = {'specimen': specimen.reagent.name, 'data-value': specimen.reagent.id}

            out_table = 'batch_constituents'
    else:
        constituents = BatchConstituents.query.filter_by(batch_id=batch_id).all()
        constituent_ids = {const.constituent_type: const.id for const in constituents if const.vial_position is not None}

        # Set relevant data for reference batch
        if 'REF' in Batches.query.get(batch_id).assay.assay_name:
            specimen = Specimens.query.get(source[1])
            source_out = {'specimen': specimen.case.case_number, 'data-value': specimen.id}
            values = [[item.vial_position, item.test_name, item.gcet_specimen_check, str(item.gcet_specimen_check),
                       item.specimen_check, item.dilution, item.directives] for item in
                      Tests.query.filter(and_(Tests.specimen_id == source[1], Tests.batch_id == batch_id))]
        # Set relevant data to variables dependant on input
        elif source[0] == 'specimens' or source[0] == 's':
            specimen = Specimens.query.get(source[1])
            source_out = {'specimen': f'{specimen.case.case_number} {specimen.accession_number} [{specimen.type.code}]',
                          'data-value': specimen.id}
            if specimen.custody != current_user.initials:
                values = [
                    [item.vial_position, item.test_name, item.test_id, 'NOT IN CUSTODY', 'N/A', item.dilution,
                    item.directives]
                    for item in Tests.query.filter(and_(Tests.specimen_id == source[1], Tests.batch_id == batch_id))
                ]
            else:
                    values = [
                    [item.vial_position, item.test_name, item.test_id, str(item.id), item.specimen_check, item.dilution,
                    item.directives]
                    for item in Tests.query.filter(and_(Tests.specimen_id == source[1], Tests.batch_id == batch_id))
                ]
            out_table = 'tests'
        elif source[0] == 'standards_and_solutions':
            specimen = BatchConstituents.query.filter_by(constituent_id=source[1]).first()
            source_out = {'specimen': specimen.constituent.lot, 'data-value': specimen.constituent.id}
            if specimen.vial_position is not None:
                values = [[item.vial_position, item.constituent.lot, item.constituent.id, str(item.id), item.specimen_check,
                        '', ''] for item in
                        BatchConstituents.query.filter(and_(BatchConstituents.constituent_id == source[1],
                                                            BatchConstituents.batch_id == batch_id))]
            else:
                batch_const = BatchConstituents.query.filter_by(constituent_id=source[1], batch_id=batch_id).first()
                values = [[item.vial_position, item.constituent.lot, item.constituent.id, str(item.id), batch_const.specimen_check, 
                           '', ''] for item in 
                           BatchConstituents.query.filter_by(id=constituent_ids[batch_const.constituent_type])]
            out_table = 'batch_constituents'

            if 'SAMQ' in Batches.query.get(batch_id).assay.assay_name and 'Blank' in \
                    specimen.constituent.constituent.name:
                values.extend([item.vial_position, item.test_name, item.test_id, str(item.id),
                               item.specimen_check, '', ''] for item in
                              Tests.query.filter(and_(Tests.batch_id == batch_id, Tests.test_name.like('PSS%'))))
        elif source[0] == 'solvents_and_reagents':
            specimen = BatchConstituents.query.filter_by(reagent_id=source[1]).first()
            source_out = {'specimen': specimen.reagent.name, 'data-value': specimen.reagent.id}
            values = [
                [item.vial_position, item.reagent.name, item.reagent.id, str(item.id), item.specimen_check, '', '']
                for item in BatchConstituents.query.filter(and_(BatchConstituents.reagent_id == source[1],
                                                                BatchConstituents.batch_id == batch_id))]
            out_table = 'batch_constituents'
        elif source[0] == 'tests':
            specimen = Tests.query.get(source[1])
            if int(specimen.batch_id) == int(batch_id):
                value = [specimen.vial_position, specimen.test_name, specimen.test_id, str(specimen.id),
                         specimen.transfer_check, specimen.dilution, specimen.directives]
                source_out = {'specimen': f'{specimen.test_name}',
                              'data-value': specimen.id}
                out_table = 'tests'
            else:
                value = []
                source_out = {}
                out_table = ''
        elif source[0] == 'batch_constituents':
            specimen = BatchConstituents.query.get(source[1])
            if specimen.constituent_id is not None:
                value = [specimen.vial_position, specimen.constituent.lot, specimen.constituent.id, str(specimen.id),
                         specimen.specimen_check, '', '']
                source_out = {'specimen': specimen.constituent.lot, 'data-value': specimen.constituent.id}
            else:
                value = [specimen.vial_position, specimen.reagent.name, specimen.reagent.id, str(specimen.id),
                         specimen.specimen_check, '', '']
                source_out = {'specimen': specimen.reagent.name, 'data-value': specimen.reagent.id}

            out_table = 'batch_constituents'

    # If values populated
    if len(values) != 0:
        for value in values:
            # Dynamically set tests (html) with all necessary table rows
            idx += 1
            dilution = f'<td></td>'
            # Check for dilution and set background-color appropriately
            if value[5] != '' and value[5] is not None:
                if value[5] == '1':
                    dilution = f'<td>{value[5]}</td>'
                elif value[5] in ['2', 'HV']:
                    if value[5] == 'HV':
                        dilution = f'<td style="background-color: #fdfd96">{value[5]}</td>'
                    else:
                        dilution = f'<td style="background-color: #ff66ff">d1/{value[5]}</td>'
                elif value[5] == '5':
                    dilution = f'<td style="background-color: #0099ff">d1/{value[5]}</td>'
                else:
                    dilution = f'<td style="background-color: #f9ad40">d1/{value[5]}</td>'
            else:
                # Check if skipped and set background-color to yellow
                if value[4] is not None and value[4] != 'Skipped':
                    dilution = f'<td style="background-color: #d4edda"></td>'
            # If Skipped or not yet Checked
            if value[4] is None or value[4] == 'Skipped':
                tests += f'<tr class="dynamic-row"><td id="{value[2]}" name="{value[2]}">{value[0]}</td>{dilution}' \
                         f'<td id="sourceDirective{str(idx)}" name="sourceDirective{str(idx)}" data-value="{value[3]}">' \
                         f'{value[6]}</td>' \
                         f'<td id="sourceName{str(idx)}" name="sourceName{str(idx)}" data-value="{value[3]}">' \
                         f'{value[1]}</td><td id="testTest{str(idx)}" name="testTest{str(idx)}">' \
                         f'<input type="text" id="testScan{str(idx)}" name="testScan{str(idx)}"></td></tr>'
            else:
                tests += f'<tr class="dynamic-row"><td style="background-color: #d4edda" id="{value[2]}" ' \
                         f'name="{value[2]}">{value[0]}</td>{dilution}' \
                         f'<td style="background-color: #d4edda" id="sourceDirective{str(idx)}" name="sourceDirective{str(idx)}" data-value="{value[3]}">' \
                         f'{value[6]}</td>' \
                         f'<td style="background-color: #d4edda" id="sourceName{str(idx)}" name="sourceName{str(idx)}" ' \
                         f'data-value="{value[3]}">{value[1]}</td><td id="testTest{str(idx)}" name="testTest{str(idx)}">' \
                         f'<input readonly type="text" id="testScan{str(idx)}" name="testScan{str(idx)}"' \
                         f'value="{out_table}: {value[3]}" style="background-color: #d4edda"></td></tr>'
    else:
        # Values array not populated, value variable set
        dilution = f'<td></td>'
        # Check for dilution and set background-color appropriately
        if value[5] != '' and value[5] is not None:
            if value[5] == '1':
                dilution = f'<td>{value[5]}</td>'
            elif value[5] in ['2', 'HV']:
                if value[5] == 'HV':
                    dilution = f'<td style="background-color: #fdfd96">{value[5]}</td>'
                else:
                    dilution = f'<td style="background-color: #ff66ff">d1/{value[5]}</td>'
            elif value[5] == '5':
                dilution = f'<td style="background-color: #0099ff">d1/{value[5]}</td>'
            else:
                dilution = f'<td style="background-color: #f9ad40">d1/{value[5]}</td>'
        else:
            # Check if item skipped and set background color to yellow
            if value[4] is not None and value[4] != 'Skipped':
                dilution = f'<td style="background-color: #d4edda"></td>'
        if value[4] is None or value[4] == 'Skipped':
            tests += f'<tr class="dynamic-row"><td id="{value[2]}" name="{value[2]}">{value[0]}</td>{dilution}' \
                     f'<td id="sourceName1" name="sourceDirective1" data-value="{value[3]}">' \
                     f'{value[6]}</td>' \
                     f'<td id="sourceName1" name="sourceName1" data-value="{value[3]}">' \
                     f'{value[1]}</td><td id="testTest1" name="testTest1">' \
                     f'<input type="text" id="testScan1" name="testScan1"></td></tr>'
        else:
            tests += f'<tr class="dynamic-row"><td style="background-color: #d4edda" id="{value[2]}" ' \
                     f'name="{value[2]}">{value[0]}</td>{dilution}' \
                     f'<td style="background-color: #d4edda" id="sourceDirective1" name="sourceName1" data-value="{value[3]}">' \
                     f'{value[6]}</td>' \
                     f'<td style="background-color: #d4edda" id="sourceName1" name="sourceName1" ' \
                     f'data-value="{value[3]}">{value[1]}</td><td id="testTest1" name="testTest1">' \
                     f'<input readonly type="text" id="testScan1" name="testScan1"' \
                     f'value="{out_table}: {value[3]}" style="background-color: #d4edda"></td></tr>'

    print(f'GET BATCH INFORMATION TOOK: {time.time() - start}')

    return jsonify({'tests': tests, 'source_out': source_out})


@blueprint.route(f'/{table_name}/<int:item_id>/set_datetime/', methods=['GET', 'POST'])
@login_required
def set_datetime(item_id):

    # When complete is selected for EA, PA, BR
    to_set = request.args.get('to_set')
    item = table.query.get(item_id)
    event = 'UPDATED'
    iteration = request.args.get('iteration', type=int)
    admin_complete = request.args.get('admin', type=bool)

    if admin_complete:
        fulfilled = False
        missing = []

        # Load all batch records
        records = BatchRecords.query.filter_by(batch_id=item_id).all()

        # Determine test type
        batch = Batches.query.get(item_id)
        test_type = batch.batch_id[:4] if batch else None

        # Only handle LCQD test type for now
        if test_type == "LCQD":
            filenames = [r.file_name for r in records]  # assuming records have .file_name

            for req in required_exact:
                if not any(req in f for f in filenames):
                    missing.append(req)

            found_lastwords = set()

            for f in filenames:
                lw = get_last_word(f)
                if lw in required_lastword:
                    found_lastwords.add(lw)

            for req in required_lastword:
                if req not in found_lastwords:
                    missing.append(req)

            if not missing:
                fulfilled = True

            print("The PDF requirements are fulfiled? ", fulfilled)
            if not fulfilled:
                flash(f"Missing required files: {', '.join(missing)}", "danger")
                return redirect(request.referrer or url_for(f'{table_name}.view', item_id=item.id))

    complete_datetime(item_id, item_name, event, to_set, iteration)

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/read_only/', methods=['GET', 'POST'])
@login_required
def read_only(item_id):
    # Handles read_only paths for batches (For non-EA)
    item = table.query.get(item_id)
    # Get the process
    process = request.args.get('process')
    # Get tests related to batch and order
    tests = (
        Tests.query
        .filter_by(batch_id=item_id)
        .order_by(
            cast(
                func.substring(Tests.test_name, func.length(Tests.test_name) - 1, 2),
                Integer
            )
        )
    )

    # Based on process, redirect as necessary
    if process == 'hamilton_load':
        return redirect(url_for(f'{table_name}.hamilton_samples', item_id=item.id, read_only=True))
    elif process == 'hamilton_transfer':
        return redirect(url_for(f'{table_name}.hamilton_check', item_id=item.id, read_only=True))
    elif process == 'sequence':
        return redirect(url_for(f'{table_name}.sequence_check', item_id=item.id, read_only=True))
    elif process == 'gcet_sequence':
        return redirect(url_for(f'{table_name}.sequence_check', item_id=item.id, read_only=True))

    # Return read_only template for processes not listed above
    return render_template(
        f'{table_name}/{process}_read.html',
        item=item,
        tests=tests,
    )

required_files_map = {
    "LCQD": [
        "LCQD-BLURZZ-QLA1",
        "LCQD-BLURZZ-QHA1",
        "Metric Plot",
        "Calibration",
        "Report",
        "Sequence",
    ],

    "LCCI": [
        "Calibration",
        "Metric Plot",
        "Report",
        "Sequence",
    ],

    "LCFS": [
        "Calibration",
        "Metric Plot",
        "Report",
        "Sequence",
    ],

    "SAMQ": [
        "Case Component Conc",
        "Data Summary",
        "Metric Plot",
        "PSS Summary",
        "Sequence",
        "Workbook",
    ],

    "GCET": [
        # "Batch ID.zip",
        "Workbook",
        "Data",
        "Report",
        "Sequence",
    ],

    "QTON": [
        "(P) Calibration",
        "(P) Metric Plot",
        "(P) MS Tune Check",
        "(P) Report",
        "(P) Sequence",
        "(N) Calibration",
        "(N) Metric Plot",
        "(N) MS Tune Check",
        "(N) Report",
        "(N) Sequence",
    ],
}

required_exact = [
        "LCQD-BLURZZ-QLA1",
        "LCQD-BLURZZ-QHA1",
    ]

required_lastword = [
    "Metric Plot",
    "Calibration",
    "Report",
    "Sequence",
]

def get_last_word(filename: str):
    """
    e.g.
    'Something Something Metric Plot.pdf' -> 'Metric Plot'
    'LCQD-123 Calibration.docx' -> 'Calibration'
    """
    # Remove extension
    name_without_ext = filename.rsplit('.', 1)[0]

    # Last word = text after last space
    # but since "Metric Plot" is 2 words, we need to match the *whole ending*
    for w in required_lastword:
        if name_without_ext.endswith(w):
            return w

    # If nothing matches, return full last segment for debugging
    return name_without_ext.rsplit(" ", 1)[-1]

@blueprint.route(f'/{table_name}/<int:item_id>/admin_complete/', methods=['GET', 'POST'])
@login_required
def admin_complete(item_id):

    fulfilled = False
    missing = []

    # Load all batch records
    records = BatchRecords.query.filter_by(batch_id=item_id).all()

    # Determine test type
    batch = Batches.query.get(item_id)
    test_type = batch.batch_id[:4] if batch else None

    # Only handle LCQD test type for now
    if test_type == "LCQD":
        filenames = [r.file_name for r in records]  # assuming records have .file_name

        for req in required_exact:
            if not any(req in f for f in filenames):
                missing.append(req)

        found_lastwords = set()

        for f in filenames:
            lw = get_last_word(f)
            if lw in required_lastword:
                found_lastwords.add(lw)

        for req in required_lastword:
            if req not in found_lastwords:
                missing.append(req)

        if not missing:
            fulfilled = True

        print("The PDF requirements are fulfiled? ", fulfilled)
        if not fulfilled:
            flash(f"Missing required files: {', '.join(missing)}", "danger")
            return redirect(request.referrer or url_for(f'{table_name}.view', item_id=item.id))

        
    item = table.query.get(item_id)
    process = request.args.get('process')


    if process == 'review':
        fulfilled = False
        missing = []

        # Load batch records
        records = BatchRecords.query.filter_by(batch_id=item_id).all()
        filenames = [r.file_name for r in records]

        # Determine test type prefix (first 4 chars)

        print(item_id)
        batch = Batches.query.get(item_id)
        test_type = batch.batch_id[:4] if batch else None

        required_list = required_files_map.get(test_type, [])

        if required_list:

            if test_type == "GCET":
                required_list.append(f"{batch.batch_id}.zip")
            for req in required_list:
                if not any(req in f for f in filenames):
                    missing.append(req)

            if not missing:
                fulfilled = True

            print("PDF requirements fulfilled? ", fulfilled)

            if not fulfilled:
                return jsonify({"missing": missing}), 400
        
    item = table.query.get(item_id)
    event = 'UPDATED'

    new_value = datetime.now()
    status = 'Approved'
    test_revision = -1

    # Get the discipline of the assay
    discipline = item.assay.discipline

    # Set relevant completion time (Admin override)
    if process == 'extract':
        original_value = item.extraction_finish_date
        field = 'Extraction Finish Date'
        field_name = 'extraction_finish_date'
        item.extraction_finish_date = new_value
    if process == 'processing':
        original_value = item.process_finish_date
        field = 'Processing Finish Date'
        field_name = 'process_finish_date'
        item.process_finish_date = new_value
    if process == 'review':
        original_value = item.review_finish_date
        field = 'Review Finish Date'
        field_name = 'review_finish_date'
        item.review_finish_date = datetime.now()
        item.batch_status = 'Finalized'

        # Mark each test as finalized when batch is finalized
        for test in Tests.query.filter_by(batch_id=item_id).all():
            test_original_value = test.test_status
            test.test_status = 'Finalized'
            test_mod = Modifications.query.filter_by(record_id=test.id, table_name='Tests',
                                                     field_name='test_status').first()
            if test_mod:
                test_revision = int(test_mod.revision)

            test_revision += 1

            modification = Modifications(
                event=event,
                status=status,
                table_name='Tests',
                record_id=test.id,
                revision=test_revision,
                field='Test Status',
                field_name='test_status',
                original_value=test_original_value,
                original_value_text=str(test_original_value),
                new_value='Finalized',
                new_value_text='Finalized',
                submitted_by=current_user.id,
                submitted_date=datetime.now(),
                reviewed_by=current_user.id,
                review_date=datetime.now()
            )

            db.session.add(modification)

            # Get the case for the test
            case = test.case
            # Get the statuses of each test for that discipline in a case
            test_statuses = [x.test_status for x in
                             Tests.query.join(Assays).filter(
                                 and_(Tests.case_id == case.id, Tests.test_status != 'Cancelled',
                                      Assays.discipline == discipline))]
            # Check if all statuses are 'Finalized' we also need to check if the list is empty as it also returns True.
            # Set the discipline status to 'Drafting
            if test_statuses and all(x == 'Finalized' for x in test_statuses):
                setattr(case, f"{discipline.lower()}_status", 'Ready for Drafting')

            db.session.commit()

    # Unlock batch
    item.locked = False
    item.locked_by = None
    item.lock_date = None

    mod = Modifications.query.filter_by(record_id=str(item_id), table_name=item_name, field_name=field_name).first()

    # Initialize revision number to set to 0 if no revisions exist
    revision = -1

    if mod:
        revision = int(mod.revision)
    else:
        event = 'CREATED'

    revision += 1

    try:
        original_value = original_value.strftime("%m/%d/%Y")

    except AttributeError:
        original_value = str(original_value)

    try:
        new_value = new_value.strftime("%m/%d/%Y")
    except AttributeError:
        new_value = str(new_value)

    modification = Modifications(
        event=event,
        status=status,
        table_name=item_name,
        record_id=str(item.id),
        revision=revision,
        field=field,
        field_name=field_name,
        original_value=original_value,
        original_value_text=str(original_value),
        new_value=new_value,
        new_value_text=new_value,
        submitted_by=current_user.id,
        submitted_date=datetime.now(),
        reviewed_by=current_user.id,
        review_date=datetime.now()
    )

    db.session.add(modification)

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item.id))


@blueprint.route(f'/{table_name}/<int:item_id>/delete_results/', methods=['GET', 'POST'])
@login_required
def delete_results(item_id):
    batch = Batches.query.get(item_id)

    # Get the test IDs in the batch to filter the results
    test_ids = [item.id for item in Tests.query.filter_by(batch_id=item_id)]
    # Get the results using the test IDs
    results = Results.query.filter(Results.test_id.in_(test_ids))
    result_ids = [str(item.id) for item in results]

    # Delete the modifications
    Modifications.query.filter_by(table_name='Results').filter(Modifications.record_id.in_(result_ids)).delete()

    # Delete results comments
    CommentInstances.query.filter(sa.and_(
        CommentInstances.comment_item_type == 'Results',
        CommentInstances.comment_item_id.in_(result_ids)
    )
    ).delete()
    # Delete test comments
    # CommentInstances.query.filter(sa.and_(
    #     CommentInstances.comment_item_type=='Tests',
    #     CommentInstances.comment_item_id.in_(test_ids)
    #     )
    # ).delete()

    # Delete the results
    results.delete()

    db.session.commit()

    flash(Markup(f'Results for <b>{batch.batch_id}</b> have been deleted.'), 'error')

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/create_samq_tests/', methods=['GET', 'POST'])
@login_required
def create_samq_tests(item_id):
    # Set reference for all SAMQ standards possible
    samq_standards = ['SAMQ-1-QLA', 'SAMQ-Z-C1A', 'SAMQ-Z-C2A', 'SAMQ-Z-C3A', 'SAMQ-Z-C4A',
                      'SAMQ-Z-C5A', 'SAMQ-Z-C6A', 'SAMQ-Z-C7A', 'SAMQ-1-QHA',
                      'SAMQ-Z-QH1', 'SAMQ-Z-QH2', 'SAMQ-Z-QH3', 'SAMQ-Z-QH4']

    # Get assay
    assay = Batches.query.get(item_id).assay_id

    # Get sequence
    sequence = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                              BatchRecords.file_type == 'Sequence')).first()

    # May be irrelevant
    try:
        constituents_dict = dict([(item.constituent_type, [item.constituent_id, item.constituent.lot]) for item in
                                  BatchConstituents.query.filter_by(batch_id=item_id)])
    except AttributeError:
        constituents_dict = dict([(item.constituent_type, [item.constituent_id, None]) for item in
                                  BatchConstituents.query.filter_by(batch_id=item_id)])

    if request.method == 'GET':
        # Create dataframe from sequence
        if sequence is not None:
            df = pd.read_csv(sequence.file_path)
            # Iterate through sequence and create tests for SAMQ standards
            for x, y in df.iterrows():
                # Get relevant samples
                if y['SampleID'] in samq_standards and 'PSS QCH' not in y['% header=SampleName'] and \
                        'None Selected' not in y['% header=SampleName']:
                    # Get test that shares case number to set repeat data
                    test = Tests.query.filter(and_(Tests.batch_id == item_id,
                                                   Tests.test_name == y["% header=SampleName"])).first()
                    # Set all test data
                    field_dict = {
                        'test_name': f'{y["% header=SampleName"]}_{y["SampleID"]}',
                        'case_id': test.case_id,
                        'specimen_id': test.specimen_id,
                        'assay_id': test.assay_id,
                        'batch_id': item_id,
                        'vial_position': y['VialPos'],
                        'test_status': 'Processing',
                        'dilution': '',
                        'db_status': 'Active'
                    }

                    # Add test
                    item = Tests(**field_dict)
                    db.session.add(item)
                    db.session.commit()

                # Assign blank specimen to PSS
                elif 'PSS QCH' in y['% header=SampleName']:
                    # Get blank matrix constituent_id from batch_constituents
                    constituent = BatchConstituents.query.filter(and_(
                        BatchConstituents.constituent_type == f"Blank {y['% header=SampleName'].split(' ')[2]}",
                        BatchConstituents.batch_id == item_id)).first().constituent_id
                    # Get blank matrix lot from standards_and_solutions using above variable
                    standard = StandardsAndSolutions.query.get(constituent).lot
                    # Get corresponding blank matrix case id from cases using above variable
                    case = Cases.query.filter_by(case_number=standard).first().id
                    # Get blank matrix specimen id from specimens using above variable
                    specimen = Specimens.query.filter_by(case_id=case).first().id
                    # Set field dictionary to add test
                    field_dict = {
                        'test_name': f'{y["% header=SampleName"]}_{y["SampleID"]}',
                        'case_id': case,
                        'specimen_id': specimen,
                        'assay_id': assay,
                        'batch_id': item_id,
                        'vial_position': y['VialPos'],
                        'test_status': 'Processing',
                        'dilution': '',
                        'db_status': 'Active'
                    }
                    item = Tests(**field_dict)
                    db.session.add(item)

                    db.session.commit()

            return redirect(url_for(f'{table_name}.view', item_id=item_id))

        else:
            return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/batches_pdf/', methods=['GET', 'POST'])
@login_required
def batches_pdf(item_id):
    batch = Batches.query.get(item_id)

    batches_printable_page(item_id)

    return redirect(f'/static/batch_pdf_reference/{batch.batch_id}.pdf')


@blueprint.route(f'/{table_name}/clear_pa/', methods=['GET', 'POST'])
@login_required
def clear_pa():
    # Get test
    test = Tests.query.get(int(request.args.get('test_id')))

    # If test, set all sequence_check_2 (pa_check) columns to None
    if test:
        test.sequence_check_2 = None
        test.sequence_check_2_by = None
        test.sequence_check_2_date = None
    else:
        pass

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=test.batch_id))


@blueprint.route(f'/{table_name}/<int:item_id>/change_all/', methods=['GET', 'POST'])
@login_required
def change_all(item_id):
    value = request.args.get('value')

    print(f'VALUE: {value}')

    if value.lower() == 't':
        value = True
    else:
        value = False

    batch_constituents = BatchConstituents.query.filter_by(batch_id=item_id)

    for const in batch_constituents:
        const.include_checks = value
        if value:
            const.transfer_check = None
            const.transfer_check_by = None
            const.transfer_check_date = None
            const.sequence_check = None
            const.sequence_check_by = None
            const.sequence_check_date = None
        else:
            const.transfer_check = 'N/A'
            const.sequence_check = 'N/A'
            const.transfer_check_by = None
            const.transfer_check_date = None
            const.sequence_check_by = None
            const.sequence_check_date = None

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/manual_check/', methods=['GET', 'POST'])
@login_required
def manual_check(item_id):
    # Get test and check from request
    test = request.args.get('test')
    check_type = request.args.get('check')

    # Initialize checks array
    checks = []

    # Set relevant check based on if sample is test or batch_constituent and check_type
    if test == 'true':
        test = True
        if check_type == 'source':
            checks.extend(['specimen_check', 'checked_by', 'checked_date'])
    else:
        test = False
        if check_type == 'source':
            checks.extend(['specimen_check', 'specimen_check_by', 'specimen_check_date'])

    # Set relevant checks based only on check_type
    if check_type == 'transfer':
        checks.extend(['transfer_check', 'transfer_check_by', 'transfer_check_date'])
    elif check_type == 'load':
        checks.extend(['load_check', 'load_check_by', 'load_checked_date'])
    elif check_type == 'sequence':
        checks.extend(['sequence_check', 'sequence_check_by', 'sequence_check_date'])

    # Get item
    if test:
        item = Tests.query.get(item_id)
    else:
        item = BatchConstituents.query.get(item_id)

    # Set relevant check information
    setattr(item, checks[0], 'Completed / Manual')
    setattr(item, checks[1], current_user.id)
    setattr(item, checks[2], datetime.now())

    # Return to batch view
    batch_id = Batches.query.get(item.batch_id).id
    return redirect(url_for(f'{table_name}.view', item_id=batch_id))


@blueprint.route(f'/{table_name}/<int:item_id>/import_sequence/', methods=['GET', 'POST'])
@login_required
def import_sequence(item_id):
    item = table.query.get(item_id)
    batch_template_id = item.batch_template_id
    errors = []
    exit_route = url_for(f'{table_name}.view', item_id=item_id)
    temp_file_path = os.path.join(current_app.root_path, 'static', 'filesystem', 'temp')

    headers = SequenceHeaderMappings.query.filter_by(batch_template_id=batch_template_id).first()

    form = Import()

    # This will probably go under form submitted and approved
    # Compare original seq to imported seq and record changed, make changes in backend
    # Track changes in dict? key = vial, value = dict (key = field name, value = dict (key = new/orig, value = value))

    if form.is_submitted() and form.validate():
        vial_positions = []
        temp_file = os.path.join(temp_file_path, f'{item.batch_id}_temp.csv')
        form.file.data.save(temp_file)
        new_seq_df = pd.read_csv(temp_file)
        # Check if duplicates exist outside of Recon blank
        for x, y in new_seq_df.iterrows():
            if y[headers.vial_position] not in vial_positions:
                vial_positions.append(y[headers.vial_position])
            elif 'Blank' in y[headers.sample_name] or 'BLANK' in y[headers.sample_name]:
                pass
            elif 'QC' in y[headers.sample_name] or 'QL' in y[headers.sample_name] or 'QH' in y[headers.sample_name] or \
                    'QM' in y[headers.sample_name]:
                pass
            else:
                # raise ValueError(f'There are duplicate vial positions assigned to different samples. '
                #                  f'Vial position: {y[headers.vial_position]}')
                flash(Markup(f'There are duplicate vial positions assigned to different samples. Vial position: '
                             f'{y[headers.vial_position]}'), 'error')
                return render_template(
                    f'{table_name}/import_seq.html',
                    form=form,
                    function='Import',
                    item_name=item_name,
                    errors=json.dumps(errors),
                    pending_fields=json.dumps([]),
                    exit_route=exit_route,
                    item=item
                )

        # Get the current sequence
        if 'QTON' in item.assay.assay_name:
            if '(P)' in form.file.data.filename:
                original_seq = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                              BatchRecords.file_type == 'Sequence',
                                                              ~BatchRecords.file_name.contains('(N)'))).first()
            elif '(N)' in form.file.data.filename:
                original_seq = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                              BatchRecords.file_type == 'Sequence',
                                                              BatchRecords.file_name.contains('(N)'))).first()
        else:
            original_seq = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                          BatchRecords.file_type == 'Sequence')).first()

        # Create dicts from current seq and new seq with vial pos as key and dict with column header: value as value
        original_dict = {
            y[headers.vial_position]: {
                **{k: v for k, v in y.items() if k != headers.vial_position},
                'changed': False
            }
            for x, y in
            pd.read_csv(original_seq.file_path).iterrows()
        }

        new_dict = {
            y[headers.vial_position]: {
                **{k: v for k, v in y.items() if k != headers.vial_position},
                'changed': False
            }
            for x, y
            in new_seq_df.iterrows()
        }

        changes_dict = {}
        missing_keys = []
        send_dict = {}

        for k, v in original_dict.items():
            if k in new_dict.keys() and v == new_dict[k]:
                print(f'SKIPPED KEY: {k}')
            elif k in new_dict.keys():
                changes_dict[k] = new_dict[k]
            else:
                missing_keys.append(k)

        for k, v in new_dict.items():
            if k not in original_dict.keys():
                changes_dict[k] = new_dict[k]

        final_missing_keys = missing_keys.copy()

        # print(f'FINAL MISSING KEYS 2: {final_missing_keys}')
        original_dict = replace_nan(original_dict)
        changes_dict = replace_nan(changes_dict)

        for idx, key in enumerate(missing_keys):
            if original_dict[key] in changes_dict.values():
                if re.search(r'_\d{2}$', original_dict[key][headers.sample_name][-3:]) or 'SAMQ' in item.assay.assay_name:
                    sample_type = 'test'
                else:
                    sample_type = 'batch_constituent'
                changed_vial = next((k for k, v in changes_dict.items() if v == original_dict[key]))
                changes_dict[changed_vial]['changed'] = True
                send_dict[idx] = {'prev': key, 'new': changed_vial, 'type': sample_type}
                if key in final_missing_keys:
                    final_missing_keys.remove(key)

        # Check missing keys for NTs, return error if key is missing and no NTs exist and vial position exists in batch
        # Add confirmation for changes
        # Distinguish between test and batch_constituents by using "_##" ending in test_id

        for key in final_missing_keys:
            if re.search(r'_\d{2}$', original_dict[key][headers.sample_name][-3:]):
                current = Tests.query.filter_by(vial_position=int(key), batch_id=item_id).first()
                sample_type = 'test'
            else:
                current = BatchConstituents.query.filter_by(vial_position=int(key), batch_id=item_id).first()
                sample_type = 'batch_constituent'

            fields = (
                current.specimen_check,
                current.transfer_check,
                current.sequence_check,
                current.load_check,
            )

            if all((f or '')[:2] != 'NT' for f in fields):
                # raise ValueError(f'You have removed a row from the sequence that does not have any "NTs". If this'
                #                  f' is intentional, please NT the {sample_type} first and proceed.')
                flash(Markup(f'You have removed a row from the sequence that does not have any "NTs".'
                             f'If this is intentional, please NT the {sample_type} first and proceed'), 'error')
                return render_template(
                    f'{table_name}/import_seq.html',
                    form=form,
                    function='Import',
                    item_name=item_name,
                    errors=json.dumps(errors),
                    pending_fields=json.dumps([]),
                    exit_route=exit_route,
                    item=item
                )
            else:
                send_dict[len(send_dict.keys()) + 1] = {'prev': key, 'new': 'None', 'type': sample_type}

        return redirect(url_for(f'{table_name}.seq_changes', item_id=item_id, changes=json.dumps(send_dict),
                                new_seq=temp_file))

    return render_template(
        f'{table_name}/import_seq.html',
        form=form,
        function='Import',
        item_name=item_name,
        errors=json.dumps(errors),
        pending_fields=json.dumps([]),
        exit_route=exit_route,
        item=item
    )


@blueprint.route(f'/{table_name}/<int:item_id>/seq_changes/', methods=['GET', 'POST'])
@login_required
def seq_changes(item_id):
    item = table.query.get(item_id)
    errors = []
    exit_route = url_for(f'{table_name}.view', item_id=item_id)
    changes = json.loads(request.args.get('changes'))
    new_seq = request.args.get('new_seq')
    original_seq = BatchRecords.query.filter(and_(BatchRecords.batch_id == item_id,
                                                  BatchRecords.file_type == 'Sequence')).first()
    nt_reason = None

    form = SeqChanges()

    test_checks = ['specimen_check', 'checked_by', 'checked_date']
    const_checks = ['specimen_check', 'specimen_check_by', 'specimen_check_date']
    if 'GCDP' in item.assay.assay_name:
        necessary_checks = required_checks[item.gcdp_assay.assay_name[:4]]
    else:
        necessary_checks = required_checks[item.assay.assay_name[:4]]

    if item.technique == 'Non-Hamilton' and 'load_check' in necessary_checks:
        necessary_checks.remove('load_check')
    else:
        if 'load_check' not in necessary_checks:
            necessary_checks.append('load_check')
        necessary_checks.extend(['load_check_by', 'load_checked_date'])

    if 'transfer_check' in necessary_checks:
        necessary_checks.extend(['transfer_check_by', 'transfer_check_date'])

    if 'sequence_check' in necessary_checks:
        necessary_checks.extend(['sequence_check_by', 'sequence_check_date'])

    if form.is_submitted():
        changes_dict = ast.literal_eval(form.changes_dict.data)
        curr_necessary_checks = necessary_checks.copy()

        for k, v in changes_dict.items():
            if v['type'] == 'test':
                current = Tests.query.filter_by(batch_id=item_id, vial_position=int(v['prev'])).first()
                curr_necessary_checks.extend(test_checks)
            else:
                current = BatchConstituents.query.filter_by(batch_id=item_id, vial_position=int(v['prev'])).first()
                curr_necessary_checks.extend(const_checks)

            if v['new'] != 'None':
                current.vial_position = int(v['new'])
            else:
                current.vial_position = None
                for curr_check in curr_necessary_checks:
                    if getattr(current, curr_check) is not None and 'by' not in curr_check and 'date' not in \
                            curr_check and 'NT' in getattr(current, curr_check):
                        nt_reason = getattr(current, curr_check)
                    if 'by' in curr_check and getattr(current, curr_check) is None:
                        setattr(current, curr_check, current_user.id)
                    elif 'date' in curr_check and getattr(current, curr_check) is None:
                        setattr(current, curr_check, datetime.now())
                    elif getattr(current, curr_check) is None and nt_reason is not None:
                        setattr(current, curr_check, nt_reason)

        db.session.commit()
        shutil.move(new_seq, original_seq.file_path)

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    form.changes_dict.data = changes

    return render_template(
        f'{table_name}/confirm_changes.html',
        form=form,
        changes=changes,
        item_name=item_name,
        function='Confirm',
        errors=json.dumps(errors),
        pending_fields=json.dumps([]),
        exit_route=exit_route,
    )


@blueprint.route(f'/{table_name}/<int:item_id>/mark_na/', methods=['GET', 'POST'])
@login_required
def mark_na(item_id):
    item = Tests.query.get(item_id)
    check = request.args.get('check_name')

    if check == 'source':
        item.specimen_check = 'Completed / Not Applicable'
        item.checked_by = current_user.id
        item.checked_date = datetime.now()
    elif check == 'transfer':
        item.transfer_check = 'Completed / Not Applicable'
        item.transfer_check_by = current_user.id
        item.transfer_check_date = datetime.now()
    elif check == 'load':
        item.load_check = 'Completed / Not Applicable'
        item.load_check_by = current_user.id
        item.load_checked_date = datetime.now()
    elif check == 'sequence':
        item.sequence_check = 'Completed / Not Applicable'
        item.sequence_check_by = current_user.id
        item.sequence_check_date = datetime.now()
        
    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item.batch_id))
