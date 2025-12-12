import qrcode
from sqlalchemy import func, and_
from string import ascii_uppercase

from lims.models import *
from lims.evidence_comments.forms import Base as Form
from lims.evidence_comments.functions import add_comments, delete_comments
from lims.evidence_comments.functions import get_form_choices as get_evidence_comment_choices

from lims.specimen_audit.views import add_specimen_audit

from lims.specimens.forms import *
from lims.specimens.functions import get_form_choices, print_specimen, process_form, add_specimen_container, \
    process_audit
from lims.locations.functions import get_location_choices
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.locations.functions import location_dict
from lims.labels import fields_dict, print_label
from lims.comment_instances.forms import Add as CommentAdd
from lims.comment_instances.functions import get_form_choices as get_comment_form
from datetime import datetime, date, time
from flask import jsonify, request
from typing import Optional
import base64

# Set item variables
item_type = 'Specimen'
item_name = 'Specimens'
table = Specimens
table_name = 'specimens'
name = 'accession_number'
requires_approval = True  # controls whether the approval process is required
ignore_fields = ['custody_type', 'custody', 'start_time']  # fields not added to the modification table
disable_fields = []
template = 'form.html'
redirect_to = 'view'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'ignore_fields': ignore_fields.copy(),
}

blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    # Get request args to prefill form
    kwargs = default_kwargs.copy()

    # Get data to prefill form
    case_id = request.args.get('case_id', type=int)
    container_id = request.args.get('container_id', type=int)
    specimen_n = request.args.get('specimen_n', type=int)
    collection_date = request.args.get('collection_date')
    collection_time = request.args.get('collection_time')
    custody_type = request.args.get('custody_type')
    custody = request.args.get('custody')
    from_autopsy = request.args.get('from_autopsy')
    discipline = request.args.get('discipline')
    accession_number = request.args.get('accession_number')
    histology = request.args.get('histology')

    print(f"from_autopsy = {from_autopsy}")
    submitted = True

    kwargs['from_autopsy'] = from_autopsy

    # Sets the name of the units in submitted_sample_amount field
    kwargs['units'] = 'No Units'

    # If the user exits the form and case_id has been passed in as a URL arg, return the user to the case.
    exit_route = None
    if case_id:
        exit_route = url_for('cases.view', item_id=case_id, view_only=True)
    # Try to get specimen type if present in request
    try:
        specimen_type = int(request.args.get('specimen_type'))
    except TypeError:
        specimen_type = None

    # Instantiate specimen add form and evidence_comments_form
    form = get_form_choices(Add(), container_id, case_id, custody_type, discipline, from_autopsy)
    evidence_comment_form = get_evidence_comment_choices(Form())
    kwargs['evidence_comment_form'] = evidence_comment_form

    # If the container is submitted by location, disable the custody fields
    # and set their values
    if custody and current_user.permissions == 'INV':
        kwargs['disable_fields'] = ['custody_type', 'custody']
        form.custody_type.data = custody_type
        form.custody.data = custody
        # kwargs['custody'] = custody
        # kwargs['custody_type'] = custody

    # If specimen is being submitted from autopsy view, populate relevant fields
    if from_autopsy:
        try:
            form.collection_container_id.data = SpecimenTypes.query.get(specimen_type).collection_container.id
            if 'Physical' in SpecimenTypes.query.get(specimen_type).discipline:
                custody_type = 'Benches'
                form.custody.choices = [(item.equipment_id, item.equipment_id) for item in Benches.query.all()]
                # custody = Benches.query.filter_by(equipment_id='BS60').first().
                custody = 'BS60'
            else:
                custody_type = 'Cooled Storage'
                form.custody.choices = [(item.equipment_id, item.equipment_id) for item in CooledStorage.query.all()]
                # custody = CooledStorage.query.filter_by(equipment_id='08R').first().id
                custody = '08R'
        except AttributeError:
            if custody is not None:
                form.custody_type.data = custody_type
                custody = str(custody)
                form.custody.choices = [(item.equipment_id, item.equipment_id) for item in
                                        location_dict[custody_type]['table'].query.all()]

        # Set printer to autopsy printer
        printer = r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo'

        # Store from_autopsy value in kwargs
        kwargs['from_autopsy'] = from_autopsy
    # Set printer based on investigator

    # Accessioning area printer
    elif request.remote_addr == '10.63.21.58':
        printer = r'\\OCMEG9M020.medex.sfgov.org\BS01 - Accessioning'
    elif request.remote_addr == '10.63.21.64':
        printer = r'\\OCMEG9M022.medex.sfgov.org\BS11 - Accessioning'
    elif request.remote_addr == '10.63.20.115':
        printer = r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo'
    elif current_user.permissions == 'INV':
        # printer = current_user.default_printer
        printer = r'\\OCMEG9M042.medex.sfgov.org\DYMO LabelWriter 450 Turbo INV'
    else:
        # Default printer in accessioning area
        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'

    print(f"PRINTER USED IS: {printer}")

    # If the container is being submitted through the add case or add container workflow
    if container_id:
        container = Containers.query.get(container_id)
        kwargs['container_accession_number'] = container.accession_number
        kwargs['container_type'] = container.type.name
        # lock_case_items(container.case_id)
        exit_route = url_for('cases.view', item_id=container.case_id)

    kwargs['cont_id'] = container_id
    kwargs['specimen_n'] = specimen_n
    kwargs['checked_in'] = True

    if specimen_type:
        form.specimen_type_id.data = specimen_type

    if request.method == 'POST':
        selected_specimen_type = SpecimenTypes.query.get(form.specimen_type_id.data)

        if selected_specimen_type and 'other' not in selected_specimen_type.name.lower():
            # Remove the validator and clear the value
            form.other_specimen.validators = []
            form.other_specimen.raw_data = ['']  # ensures validation doesn’t run on stale data
            response_data = []
            
        if form.validate_on_submit():

            print(f"FORM SUBMITTED IS {request.form}")
            attributes_list = []
            histo_sub = False
            case = Cases.query.get(form.case_id.data)
            if not discipline:
                discipline = form.discipline.data
                if isinstance(discipline, list) and discipline:
                    discipline = discipline[0]
            label_attributes = fields_dict['specimen']
            submitted = True
            if form.sub_specimen.data:
                parent_specimen = Specimens.query.get(form.parent_specimen.data)
            else:
                parent_specimen = None

            # if not form.sub_specimen.data:
            #     form.parent_specimen.data = None
            # else:
            #     # ADD CONTAINER
            #     container_type = ContainerTypes.query.filter_by(name='No Container').first().id
            #     container_id = add_specimen_container(container_type, form, 'By Location', 'Person', current_user.id,
            #                                           'Histology')
            #     form.container_id.data = container_id

            # if a new specimen is added to the case, set the case to pending.
            case = Cases.query.get(form.case_id.data)
            case.pending_submitter = current_user.initials
            case.db_status = 'Pending'

            form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                    form.discipline.data)

            if discipline == 'Histology':
                # Initialize alphabet arrays for histology accession number generating
                block_alphabet = list(ascii_uppercase[:ascii_uppercase.index('R') + 1])
                slide_alphabet = list(ascii_uppercase[ascii_uppercase.index('S'):])

                # accession_number is present when request comes from autopsy_view
                if accession_number:
                    kwargs.update(process_form(form, event='Add', accession_number=accession_number))
                else:
                    # Get all histology blocks for case
                    block_specimens = [item for item in Specimens.query.filter(and_(Specimens.case_id == case_id,
                                                                                    Specimens.discipline ==
                                                                                    'Histology')).order_by(
                        Specimens.accession_number.desc()) if item.accession_number[-2] in block_alphabet]

                    # If parent specimen in form, get all slides with same parent specimen
                    if parent_specimen is not None:
                        slide_specimens = [item for item in Specimens.query.filter_by(case_id=case_id,
                                                                                      discipline='Histology',
                                                                                      parent_specimen=parent_specimen.id)
                        .order_by(Specimens.accession_number.desc()) if item.accession_number[-2] in slide_alphabet]

                    # Get all histology slides for case
                    else:
                        slide_specimens = [item for item in Specimens.query.filter(and_(Specimens.case_id == case_id,
                                                                                        Specimens.discipline ==
                                                                                        'Histology')).order_by(
                            Specimens.accession_number.desc()) if item.accession_number[-2] in slide_alphabet]

                    if block_specimens or slide_specimens:
                        # Try to get current block accession number and current slide accession number
                        try:
                            current_block = block_specimens[0].accession_number
                        except IndexError:
                            current_block = None
                        try:
                            current_slide = slide_specimens[0].accession_number
                        except IndexError:
                            current_slide = None

                        # Check if sub_specimen (slide) is being created
                        if form.sub_specimen.data:
                            histo_sub = True
                            # Check if any slides already exist
                            if current_slide:
                                # Check if number is at max yet
                                if int(current_slide[-1]) < 9:
                                    # Can increment by 1
                                    accession_number = (f'{parent_specimen.accession_number}'
                                                        f'^{current_slide[-2]}{int(current_slide[-1]) + 1}')
                                    # accession_number = f'{current_slide[:-6]}{int(current_slide[-6]) + 1}' \
                                    #                    f'^{parent_specimen.accession_number[-2:]}'
                                else:
                                    # Need to go to next letter
                                    counter = 0
                                    # Set counter to next letter
                                    for letter in slide_alphabet:
                                        if current_slide[-2] == letter:
                                            counter += 1
                                            break
                                        else:
                                            counter += 1

                                    # Create accession number
                                    accession_number = f'{parent_specimen.accession_number}^{slide_alphabet[counter]}1'
                                    # accession_number = f'{case.case_number}_{slide_alphabet[counter]}1' \
                                    #                    f'^{parent_specimen.accession_number[-2:]}'

                            else:
                                # Create first slide (always S1)
                                accession_number = f'{parent_specimen.accession_number}^S1'

                        # Specimen is not a slide
                        else:
                            # Set submitted specimen to current accession number
                            if current_block:
                                # Check if number is at max yet
                                if int(current_block[-1]) < 9:
                                    # Can increment by 1
                                    accession_number = f'{current_block[:-1]}{int(current_block[-1]) + 1}'
                                else:
                                    # Need to go to next letter
                                    counter = 0
                                    # Set counter to next letter
                                    for letter in block_alphabet:
                                        if current_block[-2] == letter:
                                            counter += 1
                                            break
                                        else:
                                            counter += 1

                                    # Create accession number
                                    accession_number = f'{case.case_number}_{block_alphabet[counter]}1'

                    # No histo specimens exist for case, set to A1
                    else:
                        accession_number = f'{case.case_number}_A1'

                    kwargs.update(process_form(form, event='Add', accession_number=accession_number))
            else:
                kwargs.update(process_form(form, event='Add'))

            if form.evidence_comments.data:
                add_comments(form, kwargs['accession_number'], 'Specimen')

            # If container ID not present in request, set to form data
            if container_id is None:
                container_id = form.container_id.data

            # If n_specimens_submitted is left blank, default to 1
            if Containers.query.get(container_id).n_specimens_submitted is None:
                Containers.query.get(container_id).n_specimens_submitted = 1

            # If n_specimens_submitted equals number of specimens accessioned, increment to include specimen addition
            elif Containers.query.get(container_id).n_specimens_submitted + 1 == \
                    Containers.query.get(container_id).n_specimens:
                Containers.query.get(container_id).n_specimens_submitted += 1

            # If submitting a new blank case, create entry in standards_and_solutions
            if form.case_id.data:
                case = Cases.query.get(form.case_id.data)
                if case.type.code == 'B':
                    StandardsAndSolutions.query.filter_by(lot=case.case_number).first().location_type = \
                        form.custody_type.data
                    StandardsAndSolutions.query.filter_by(lot=case.case_number).first().location = form.custody.data
                    db.session.commit()

            if specimen_n:
                specimen_n += 1
                # Get prefill data for the add specimen form loop
                collection_date = form.collection_date.data  # .date()
                collection_time = form.collection_time.data
                custody_type = form.custody_type.data
                custody = form.custody.data

                kwargs['ignore_fields'] = kwargs['ignore_fields'].copy() + ['collection_date', 'collection_time',
                                                                            'notes']
                # update_item(form, form.case_id.data, Cases, 'Case', 'Cases', 'cases', False, 'case_number',
                #             display_flash_message=False,
                #             **kwargs)

                # Reset ignore fields
                del kwargs['ignore_fields']
                kwargs['ignore_fields'] = ignore_fields.copy()
                add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                process_audit(form, from_autopsy, histo_sub)

                # Get current specimen and set histology accession_number
                specimen = Specimens.query.order_by(Specimens.id.desc()).first()
                # if parent_specimen:
                #     if discipline == 'Histology':
                #         specimen.accession_number += f' ^{parent_specimen.accession_number[-2:]}^'
                #     else:
                #         specimen.accession_number += f' ^{parent_specimen.accession_number}^'
                #     db.session.commit()

                if form.comments.data is not None:
                    comment_form = get_comment_form(CommentAdd(), comment_item_id=specimen.id, comment_item_type='Specimens')
                    comment_form.comment_text.data = form.comments.data
                    comment_form.submit.data = True
                    comment_kwargs = {'comment_type': 'Manual'}
                    add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 
                             'comment_instances', False, ['comment_type', 'comment_text'], **comment_kwargs)

                if form.sub_specimen.data and discipline == 'Histology':
                    # Set to histology slide label printer
                    printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'
                    # Get label_attributes
                    label_attributes = fields_dict['histo_slides']
                    # Remove "Tissue, " from specimen type name and split type name into multiple lines if needed
                    if 'Tissue, ' in specimen.type.name:
                        spec_name = specimen.type.name.split('Tissue, ')[1]
                    else:
                        spec_name = specimen.type.name
                    name_list = list(spec_name)
                    counter = 0
                    for i in name_list:
                        counter += 1
                        if counter == 10:
                            name_list.insert(counter, '-\n')
                        if counter == 20:
                            name_list.insert(counter, '-\n')

                    specimen_name = ''.join(name_list)
                    # Set relevant label fields
                    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{specimen.id}.png')
                    qrcode.make(f's: {specimen.id}').save(qr_path)

                    with open(qr_path, "rb") as qr_file:
                        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                    label_attributes['TYPE'] = f'[{specimen.type.code}]\n{specimen_name}'
                    label_attributes['ACC_NUM'] = specimen.accession_number
                    label_attributes['QR'] = qr_encoded
                    label_attributes['TYPE_1'] = f'[{specimen.type.code}]\n{specimen_name}'
                    label_attributes['ACC_NUM_1'] = specimen.accession_number
                    label_attributes['QR_1'] = qr_encoded
                    label_attributes['amount'] += 1
                # Check if case is HP and set relevant label fields for non-sub_specimen
                elif case.type.code not in ['PM', 'B']:
                    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{specimen.id}.png')
                    qrcode.make(f's: {specimen.id}').save(qr_path)

                    with open(qr_path, "rb") as qr_file:
                        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                    label_attributes = fields_dict['hp_specimen']
                    label_attributes['CASE_NUM'] = case.case_number
                    label_attributes['CASE_NUM_1'] = case.case_number
                    label_attributes['ACC_NUM'] = specimen.accession_number
                    label_attributes['ACC_NUM_1'] = specimen.accession_number
                    label_attributes['CODE'] = f'[{specimen.type.code}]'
                    label_attributes['CODE_1'] = f'[{specimen.type.code}]'
                    label_attributes['QR'] = qr_encoded
                    label_attributes['QR_1'] = qr_encoded
                    label_attributes['amount'] += 1
                else:
                    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{specimen.id}.png')
                    qrcode.make(f's: {specimen.id}').save(qr_path)

                    with open(qr_path, "rb") as qr_file:
                        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                    label_attributes['LAST_FIRST'] = f'{case.last_name}, {case.first_name}'
                    label_attributes['CASE_NUM'] = case.case_number
                    label_attributes['ACC_NUM'] = specimen.accession_number
                    label_attributes['CODE'] = f'[{specimen.type.code}]'
                    label_attributes['TYPE'] = specimen.type.name
                    label_attributes['QR'] = qr_encoded
                    label_attributes['amount'] += 1

                # Print two labels if necessary otherwise print one label
                if specimen.case.case_type == CaseTypes.query.filter_by(code='M').first().id or \
                        specimen.case.case_type == CaseTypes.query.filter_by(code='D').first().id or \
                        specimen.case.case_type == CaseTypes.query.filter_by(code='X').first().id or \
                        specimen.case.case_type == CaseTypes.query.filter_by(code='N').first().id or \
                        specimen.case.case_type == CaseTypes.query.filter_by(code='P').first().id:

                    for i in range(0, 2):
                        attributes_list.append(label_attributes.copy())

                else:
                    attributes_list.append(label_attributes.copy())

                print(f"START PRINTING")
                if printer == r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo':

                    # submit and next specimen
                    if not request.form.get('submit_exit') and not request.form.get('submit_attach'):

                        return jsonify([(attributes_list, printer, True, 1, url_for('specimens.add',
                                                                                    # case_id=kwargs['case_id'],
                                                                                    container_id=container_id,
                                                                                    specimen_n=specimen_n,
                                                                                    collection_date=collection_date,
                                                                                    collection_time=collection_time,
                                                                                    custody_type=custody_type,
                                                                                    custody=custody,
                                                                                    discipline=discipline,
                                                                                    histology=histology,
                                                                                    
                                                                                    ))])
                    # subit and attach
                    elif request.form.get('submit_attach'):

                        return jsonify(
                            [(attributes_list, printer, True, 1, url_for('containers.attach', item_id=container_id,
                                                                         redirect_url=url_for('cases.view',
                                                                                              item_id=form.case_id.data),
                                                                         ))])
                    # submit exit
                    else:
                        if from_autopsy:
                            return jsonify(
                                [(attributes_list, printer, True, 1, url_for('cases.autopsy_view', ))])
                        else:
                            return jsonify([(attributes_list, printer, True, 1,
                                             url_for('cases.view', item_id=form.case_id.data, view_only=True,
                                                     ))])
                else:

                    if not request.form.get('submit_exit') and not request.form.get('submit_attach'):

                        return jsonify([(attributes_list, printer, None, None, url_for('specimens.add',
                                                                                       # case_id=kwargs['case_id'],
                                                                                       container_id=container_id,
                                                                                       specimen_n=specimen_n,
                                                                                       collection_date=collection_date,
                                                                                       collection_time=collection_time,
                                                                                       custody_type=custody_type,
                                                                                       custody=custody,
                                                                                       discipline=discipline,
                                                                                       histology=histology,
                                                                                       
                                                                                       ))])
                    elif request.form.get('submit_attach'):

                        return jsonify(
                            [(attributes_list, printer, None, None, url_for('containers.attach', item_id=container_id,
                                                                            redirect_url=url_for('cases.view',
                                                                                                 item_id=form.case_id.data),
                                                                            ))])

                    else:
                        if from_autopsy:

                            return jsonify(
                                [(attributes_list, printer, None, None, url_for('cases.autopsy_view', ))])

                        else:

                            return jsonify([(attributes_list, printer, None, None,
                                             url_for('cases.view', item_id=form.case_id.data, view_only=True,
                                                     ))])
            else:
                print(f"IN ELSE")
                # TODO NOT RETURNED
                kwargs['ignore_fields'] = kwargs['ignore_fields'].copy() + ['collection_date', 'collection_time',
                                                                            'notes']
                # print(f'IGNORE: {kwargs["ignore_fields"]}')
                # update_item(form, form.case_id.data, Cases, 'Case', 'Cases', 'cases', False, 'case_number',
                #             display_flash_message=False, **kwargs)

                # Reset ignore fields
                del kwargs['ignore_fields']
                kwargs['ignore_fields'] = ignore_fields.copy()

                # Check if submit and exit clicked and route accordingly
                if request.form.get('submit_exit') is not None:
                    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                    process_audit(form, from_autopsy, histo_sub)
                    specimen = Specimens.query.order_by(Specimens.id.desc()).first()

                    if form.comments.data is not None:
                        comment_form = get_comment_form(CommentAdd(), comment_item_id=specimen.id, comment_item_type='Specimens')
                        comment_form.comment_text.data = form.comments.data
                        comment_form.submit.data = True
                        comment_kwargs = {'comment_type': 'Manual'}
                        add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 
                                'comment_instances', False, ['comment_type', 'comment_text'], **comment_kwargs)

                    # if parent_specimen:
                    #     if discipline == 'Histology':
                    #         specimen.accession_number += f' ^{parent_specimen.accession_number[-2:]}^'
                    #     else:
                    #         specimen.accession_number += f' ^{parent_specimen.accession_number}^'
                    #     db.session.commit()
                    # See above comments
                    if form.sub_specimen.data and discipline == 'Histology':
                        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'
                        label_attributes = fields_dict['histo_slides']
                        if 'Tissue, ' in specimen.type.name:
                            spec_name = specimen.type.name.split('Tissue, ')[1]
                        else:
                            spec_name = specimen.type.name
                        name_list = list(spec_name)
                        counter = 0
                        for i in name_list:
                            counter += 1
                            if counter == 10:
                                name_list.insert(counter, '-\n')
                            if counter == 20:
                                name_list.insert(counter, '-\n')

                        specimen_name = ''.join(name_list)

                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)

                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes['TYPE'] = f'[{specimen.type.code}]\n{specimen_name}'
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['QR'] = qr_encoded
                        label_attributes['TYPE_1'] = f'[{specimen.type.code}]\n{specimen_name}'
                        label_attributes['ACC_NUM_1'] = specimen.accession_number
                        label_attributes['QR_1'] = qr_encoded

                    # Check if case is HP and set relevant label fields for non-sub_specimen
                    elif case.type.code not in ['PM', 'B']:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)

                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes = fields_dict['hp_specimen']
                        label_attributes['CASE_NUM'] = case.case_number
                        label_attributes['CASE_NUM_1'] = case.case_number
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['ACC_NUM_1'] = specimen.accession_number
                        label_attributes['CODE'] = f'[{specimen.type.code}]'
                        label_attributes['CODE_1'] = f'[{specimen.type.code}]'
                        label_attributes['QR'] = qr_encoded
                        label_attributes['QR_1'] = qr_encoded
                    else:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)
                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes['LAST_FIRST'] = f'{case.last_name}, {case.first_name}'
                        label_attributes['CASE_NUM'] = case.case_number
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['CODE'] = f'[{specimen.type.code}]'
                        label_attributes['TYPE'] = specimen.type.name
                        label_attributes['QR'] = qr_encoded

                    # Print two labels if necessary otherwise print one label
                    if specimen.case.case_type == CaseTypes.query.filter_by(code='M').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='D').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='X').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='N').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='P').first().id:

                        for i in range(0, 2):
                            attributes_list.append(label_attributes.copy())
                    else:
                        attributes_list.append(label_attributes.copy())

                    print(f'DONE PRINT LABEL HERE 2')
                    print(f'LABEL ATTRIBUTES: {label_attributes}')

                    unlock_item(case.id, Cases, 'case_number')

                    if printer == r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo':

                        if current_user.permissions == 'MED-Autopsy':

                            return jsonify(
                                [(attributes_list, printer, True, 1, url_for('cases.autopsy_view', ))])
                            # return redirect(url_for('cases.autopsy_view'))
                        else:

                            return jsonify(
                                [(attributes_list, printer, True, 1, url_for('cases.view_list', ))])
                            # return redirect(url_for('cases.view_list'))

                        # print_label(printer, attributes_list, True, 1)
                    else:

                        if current_user.permissions == 'MED-Autopsy':

                            return jsonify(
                                [(attributes_list, printer, None, None, url_for('cases.autopsy_view', ))])
                            # return redirect(url_for('cases.autopsy_view'))
                        else:
                            return jsonify(
                                [(attributes_list, printer, None, None, url_for('cases.view_list', ))])
                            # return redirect(url_for('cases.view_list'))

                        # print_label(printer, attributes_list)

                    # unlock_item(case.id, Cases, 'case_number')
                    # if current_user.permissions == 'MED-Autopsy':
                    #     return redirect(url_for('cases.autopsy_view'))
                    # else:
                    #     return redirect(url_for('cases.view_list'))
                # Check if submit and close container clicked and act accordingly
                elif request.form.get('submit_close') is not None:
                    Containers.query.get(container_id).submission_time = datetime.now().strftime('%H%M')
                    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                    process_audit(form, from_autopsy, histo_sub)
                    specimen = Specimens.query.order_by(Specimens.id.desc()).first()

                    if form.comments.data is not None:
                        comment_form = get_comment_form(CommentAdd(), comment_item_id=specimen.id, comment_item_type='Specimens')
                        comment_form.comment_text.data = form.comments.data
                        comment_form.submit.data = True
                        comment_kwargs = {'comment_type': 'Manual'}
                        add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 
                                'comment_instances', False, ['comment_type', 'comment_text'], **comment_kwargs)

                    # if parent_specimen:
                    #     if discipline == 'Histology':
                    #         specimen.accession_number += f' ^{parent_specimen.accession_number[-2:]}^'
                    #     else:
                    #         specimen.accession_number += f' ^{parent_specimen.accession_number}^'
                    #     db.session.commit()

                    # See above comments
                    if form.sub_specimen.data and discipline == 'Histology':
                        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'
                        label_attributes = fields_dict['histo_slides']
                        if 'Tissue, ' in specimen.type.name:
                            spec_name = specimen.type.name.split('Tissue, ')[1]
                        else:
                            spec_name = specimen.type.name
                        name_list = list(spec_name)
                        counter = 0
                        for i in name_list:
                            counter += 1
                            if counter == 10:
                                name_list.insert(counter, '-\n')
                            if counter == 20:
                                name_list.insert(counter, '-\n')

                        specimen_name = ''.join(name_list)

                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)

                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes['TYPE'] = f'[{specimen.type.code}]\n{specimen_name}'
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['QR'] = qr_encoded
                        label_attributes['TYPE_1'] = f'[{specimen.type.code}]\n{specimen_name}'
                        label_attributes['ACC_NUM_1'] = specimen.accession_number
                        label_attributes['QR_1'] = qr_encoded

                    # Check if case is HP and set relevant label fields for non-sub_specimen
                    elif case.type.code not in ['PM', 'B']:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)
                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes = fields_dict['hp_specimen']
                        label_attributes['CASE_NUM'] = case.case_number
                        label_attributes['CASE_NUM_1'] = case.case_number
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['ACC_NUM_1'] = specimen.accession_number
                        label_attributes['CODE'] = f'[{specimen.type.code}]'
                        label_attributes['CODE_1'] = f'[{specimen.type.code}]'
                        label_attributes['QR'] = qr_encoded
                        label_attributes['QR_1'] = qr_encoded
                    else:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)
                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes['LAST_FIRST'] = f'{case.last_name}, {case.first_name}'
                        label_attributes['CASE_NUM'] = case.case_number
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['CODE'] = f'[{specimen.type.code}]'
                        label_attributes['TYPE'] = specimen.type.name
                        label_attributes['QR'] = qr_encoded

                    # Print two labels if necessary otherwise print one label
                    if specimen.case.case_type == CaseTypes.query.filter_by(code='M').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='D').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='X').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='N').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='P').first().id:

                        for i in range(0, 2):
                            attributes_list.append(label_attributes.copy())
                    else:
                        attributes_list.append(label_attributes.copy())

                    print(f'DONE PRINT LABEL HERE 3')
                    # print(f'LABEL ATTRIBUTES: {label_attributes}')

                    if printer == r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo':

                        if from_autopsy:
                            print(f"FROM AUTOPSY IN POST REQUEST")
                            return jsonify(
                                [(attributes_list, printer, True, 1, url_for('cases.autopsy_view', ))])
                            # return redirect(url_for('cases.autopsy_view'))
                        else:
                            return jsonify(
                                [(attributes_list, printer, True, 1, url_for('cases.view_list', ))])
                            # return redirect(url_for('cases.view_list'))

                        # print_label(printer, attributes_list, True, 1)
                    else:

                        if from_autopsy:
                            return jsonify(
                                [(attributes_list, printer, None, None, url_for('cases.autopsy_view', ))])
                            # return redirect(url_for('cases.autopsy_view'))
                        else:
                            return jsonify(
                                [(attributes_list, printer, None, None, url_for('cases.view_list', ))])
                            # return redirect(url_for('cases.view_list'))
                        # print_label(printer, attributes_list)

                ########################################################### Submit route & submit and add specimen route
                elif request.form.get('submit_exit') is None and request.form.get('submit_close') is None:
                    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                    process_audit(form, from_autopsy, histo_sub)
                    specimen = Specimens.query.order_by(Specimens.id.desc()).first()

                    if form.comments.data is not None:
                        comment_form = get_comment_form(CommentAdd(), comment_item_id=specimen.id, comment_item_type='Specimens')
                        comment_form.comment_text.data = form.comments.data
                        comment_form.submit.data = True
                        comment_kwargs = {'comment_type': 'Manual'}
                        add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 
                                'comment_instances', False, ['comment_type', 'comment_text'], **comment_kwargs)

                    # if parent_specimen:
                    #     if discipline == 'Histology':
                    #         specimen.accession_number += f' ^{parent_specimen.accession_number[-2:]}^'
                    #     else:
                    #         specimen.accession_number += f' ^{parent_specimen.accession_number}^'
                    #     db.session.commit()

                    # See above comments
                    if form.sub_specimen.data and discipline == 'Histology':
                        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'
                        label_attributes = fields_dict['histo_slides']
                        if 'Tissue, ' in specimen.type.name:
                            spec_name = specimen.type.name.split('Tissue, ')[1]
                        else:
                            spec_name = specimen.type.name
                        name_list = list(spec_name)
                        counter = 0
                        for i in name_list:
                            counter += 1
                            if counter == 10:
                                name_list.insert(counter, '-\n')
                            if counter == 20:
                                name_list.insert(counter, '-\n')

                        specimen_name = ''.join(name_list)
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)
                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes['TYPE'] = f'[{specimen.type.code}]\n{specimen_name}'
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['QR'] = qr_encoded
                        label_attributes['TYPE_1'] = f'[{specimen.type.code}]\n{specimen_name}'
                        label_attributes['ACC_NUM_1'] = specimen.accession_number
                        label_attributes['QR_1'] = qr_encoded

                    # Check if case is HP and set relevant label fields for non-sub_specimen
                    elif case.type.code not in ['PM', 'B']:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)
                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes = fields_dict['hp_specimen']
                        label_attributes['CASE_NUM'] = case.case_number
                        label_attributes['CASE_NUM_1'] = case.case_number
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['ACC_NUM_1'] = specimen.accession_number
                        label_attributes['CODE'] = f'[{specimen.type.code}]'
                        label_attributes['CODE_1'] = f'[{specimen.type.code}]'
                        label_attributes['QR'] = qr_encoded
                        label_attributes['QR_1'] = qr_encoded
                    else:
                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                               f'specimen{specimen.id}.png')
                        qrcode.make(f's: {specimen.id}').save(qr_path)

                        with open(qr_path, "rb") as qr_file:
                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                        label_attributes['LAST_FIRST'] = f'{case.last_name}, {case.first_name}'
                        label_attributes['CASE_NUM'] = case.case_number
                        label_attributes['ACC_NUM'] = specimen.accession_number
                        label_attributes['CODE'] = f'[{specimen.type.code}]'
                        label_attributes['TYPE'] = specimen.type.name
                        label_attributes['QR'] = qr_encoded

                    # Print two labels if necessary otherwise print one label
                    if specimen.case.case_type == CaseTypes.query.filter_by(code='M').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='D').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='X').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='N').first().id or \
                            specimen.case.case_type == CaseTypes.query.filter_by(code='P').first().id:

                        for i in range(0, 2):
                            attributes_list.append(label_attributes.copy())
                    else:
                        attributes_list.append(label_attributes.copy())

                    print(f'DONE PRINT LABEL HERE 4')
                    print(f'LABEL ATTRIBUTES: {label_attributes}')

                    if printer == r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo':

                        if from_autopsy:
                            return jsonify([(attributes_list, printer, True, 1, url_for('specimens.add',
                                                                                        case_id=case_id,
                                                                                        container_id=container_id,
                                                                                        specimen_n=specimen_n,
                                                                                        collection_date=collection_date,
                                                                                        collection_time=collection_time,
                                                                                        custody_type=form.custody_type.data,
                                                                                        custody=form.custody.data,
                                                                                        from_autopsy=from_autopsy,
                                                                                        discipline=discipline,
                                                                                        histology=histology,
                                                                                        
                                                                                        ))])
                        elif request.form.get('submit_attach') is not None:

                            return jsonify(
                                [(attributes_list, printer, True, 1, url_for('containers.attach', item_id=container_id,
                                                                             redirect_url=url_for('cases.view',
                                                                                                  item_id=form.case_id.data),
                                                                             ))])

                        else:

                            return jsonify([(attributes_list, printer, True, 1, url_for('specimens.add',
                                                                                        case_id=case_id,
                                                                                        container_id=container_id,
                                                                                        specimen_n=specimen_n,
                                                                                        collection_date=collection_date,
                                                                                        collection_time=collection_time,
                                                                                        custody_type=custody_type,
                                                                                        custody=custody,
                                                                                        discipline=discipline,
                                                                                        histology=histology,
                                                                                        
                                                                                        ))])

                        # print_label(printer, attributes_list, True, 1)
                    else:

                        if from_autopsy:

                            return jsonify([(attributes_list, printer, None, None, url_for('specimens.add',
                                                                                           case_id=case_id,
                                                                                           container_id=container_id,
                                                                                           specimen_n=specimen_n,
                                                                                           collection_date=collection_date,
                                                                                           collection_time=collection_time,
                                                                                           custody_type=form.custody_type.data,
                                                                                           custody=form.custody.data,
                                                                                           from_autopsy=from_autopsy,
                                                                                           discipline=discipline,
                                                                                           histology=histology,
                                                                                           
                                                                                           ))])

                        elif request.form.get('submit_attach') is not None:

                            return jsonify([(attributes_list, printer, None, None,
                                             url_for('containers.attach', item_id=container_id,
                                                     redirect_url=url_for('cases.view', item_id=form.case_id.data),
                                                     ))])

                        else:

                            return jsonify([(attributes_list, printer, None, None, url_for('specimens.add',
                                                                                           case_id=case_id,
                                                                                           container_id=container_id,
                                                                                           specimen_n=specimen_n,
                                                                                           collection_date=collection_date,
                                                                                           collection_time=collection_time,
                                                                                           custody_type=custody_type,
                                                                                           custody=custody,
                                                                                           discipline=discipline,
                                                                                           histology=histology,
                                                                                           
                                                                                           ))])

                        # print_label(printer, attributes_list)

            if from_autopsy:
                return jsonify([(None, None, None, None, url_for('cases.autopsy_view', ))])
                # return redirect(url_for('cases.autopsy_view'))

            # if a new container is added to the case, set the case to pending.
            case = Cases.query.get(form.case_id.data)
            case.pending_submitter = current_user.initials
            case.db_status = 'Pending'
        else:
            print(f"LINE 939 FORM ERROR SUBMITTED IS {request.form}")
            print(form.errors)
            form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                    form.discipline.data)
            return jsonify({'success': False, 'errors': form.errors}), 400
    elif request.method == 'GET':

        form.discipline.data = discipline
        form.container_id.data = container_id
        submitted = False
        form.start_time.data = datetime.now()

        print(collection_date)
        if collection_date:
            form.collection_date.data = datetime.strptime(collection_date, '%Y-%m-%d')
        else:
            form.collection_date.data = datetime.now().date()

        if collection_time:
            form.collection_time.data = collection_time
        form.custody_type.data = custody_type
        form.custody.data = str(custody)

    if from_autopsy:
        if submitted:
            print(f"GOING TO PRINT WHEN NAVIGATING TO SPECIMEN")
            attributes_list = []
            # Set relevant label fields and print
            # print('DONE PRINT LABEL HERE FROM AUTOPSY')
            specimen = ''
            qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{specimen.id}.png')
            qrcode.make(f's: {specimen.id}').save(qr_path)

            with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

            label_attributes = fields_dict['specimen']
            label_attributes['LAST_FIRST'] = f'{case.last_name}, {case.first_name}'
            label_attributes['CASE_NUM'] = case.case_number
            label_attributes['ACC_NUM'] = specimen.accession_number
            label_attributes['CODE'] = f'[{specimen.type.code}]'
            label_attributes['TYPE'] = specimen.type.name
            label_attributes['QR'] = qr_encoded

            attributes_list.append(label_attributes)

            if printer == r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo':

                return jsonify([(attributes_list, printer, True, 1)])
                # print_label(printer, attributes_list, True, 1)
            else:
                return jsonify([(attributes_list, printer)])
                # print_label(printer, attributes_list)

            print('REACHED FROM AUTOPSY -> SUBMITTED')
    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, exit_route=exit_route,
                    **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    kwargs['locking'] = False
    item = table.query.get_or_404(item_id)
    case_id = item.case_id
    container_id = item.container_id

    if item.custody == current_user.initials:
        kwargs['give_custody'] = True

    print(case_id)
    print(container_id)

    form = Edit()
    evidence_comment_form = get_evidence_comment_choices(Form())
    kwargs['evidence_comment_form'] = evidence_comment_form
    # Sets the name of the units in submitted_sample_amount field
    kwargs['units'] = 'No Units'
    if item.type.unit:
        kwargs['units'] = item.type.unit.name

    kwargs['comments'] = [comment for comment in CommentInstances.query.filter_by(comment_item_type='Specimens', 
                                                                                  comment_item_id=item.id,
                                                                                  db_status='Active')]

    if request.method == 'POST':
        form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                form.discipline.data)
        selected_specimen_type = SpecimenTypes.query.get(form.specimen_type_id.data)

        if selected_specimen_type and 'other' not in selected_specimen_type.name.lower():
            # Remove the validator and clear the value
            form.other_specimen.validators = []
            form.other_specimen.raw_data = ['']
        if form.validate() and form.is_submitted():
            if form.evidence_comments.data:
                add_comments(form, item.accession_number, 'Specimen')

            add_specimen_audit(destination=form.custody.data,
                               reason=f'{current_user.initials} submitted specimen edit form',
                               o_time=datetime.now(),
                               specimen_id=item.id,
                               status='Out')

            kwargs.update(process_form(form))

            edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

            if request.form.get('submit_attach'):
                return redirect(url_for('containers.attach', item_id=item.container_id,
                                        redirect_url=url_for('cases.view', item_id=item.case_id)))
            else:
                return redirect(url_for('cases.view', item_id=item.case_id))
        else:
            form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                    form.discipline.data)

    elif request.method == 'GET':
        form = get_form_choices(Edit(), container_id=item.container.id, case_id=item.case.id,
                                discipline=item.discipline, item=item)

        kwargs['discipline'] = item.discipline
        kwargs['custody_type'] = 0
        if item.evidence_comments:
            kwargs['evidence_comments'] = "\n".join(item.evidence_comments.split("; "))
        if item.custody != current_user.initials:
            item.custody = current_user.initials
            item.custody_type = 'Person'
            add_specimen_audit(destination=current_user.initials,
                               reason=f'{current_user.initials} opened specimen edit form',
                               o_time=datetime.now(),
                               specimen_id=item.id,
                               status='Out')

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    print(kwargs)
    kwargs['locking'] = False
    item = table.query.get_or_404(item_id)
    form = Approve()
    custody_arg = request.args.get('custody')

    if custody_arg == 'True':
        give_custody = True
    else:
        give_custody = False
        form.custody_type.validators = []
        form.custody_type.validate_choice = False
        form.custody.data = item.custody

    kwargs['give_custody'] = give_custody

    evidence_comment_form = get_evidence_comment_choices(Form())
    kwargs['evidence_comment_form'] = evidence_comment_form
    # Sets the name of the units in submitted_sample_amount field
    kwargs['units'] = 'No Units'
    if item.type.unit:
        kwargs['units'] = item.type.unit.name

    kwargs['comments'] = [comment for comment in CommentInstances.query.filter_by(comment_item_type='Specimens', 
                                                                                  comment_item_id=item.id,
                                                                                  db_status='Active')]

    if request.method == 'POST':
        form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                form.discipline.data)
        selected_specimen_type = SpecimenTypes.query.get(form.specimen_type_id.data)

        if selected_specimen_type and 'other' not in selected_specimen_type.name.lower():
            # Remove the validator and clear the value
            form.other_specimen.validators = []
            form.other_specimen.raw_data = ['']

        if form.validate() and form.is_submitted():
            if form.evidence_comments.data:
                add_comments(form, item.accession_number, 'Specimen')
            if give_custody:
                add_specimen_audit(destination=form.custody.data,
                                reason=f'{current_user.initials} submitted specimen review form',
                                o_time=datetime.now(),
                                specimen_id=item.id,
                                status='Out')

            kwargs.update(process_form(form))

            approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)
        
            #sets conditions and volumes as preapproved fields by updating modifications to approved
            preapproved_mods = (
                Modifications.query.filter(
                    Modifications.table_name == 'Specimens',
                    Modifications.record_id == str(item.id),
                    Modifications.status == 'Pending',
                    Modifications.field_name.in_(['submitted_sample_amount', 'condition']) #update this to add more preapproved fields
                ).update({
                    Modifications.status: 'Approved',
                    Modifications.reviewed_by: current_user.id,
                    Modifications.review_date: datetime.now(),}, synchronize_session=False))
            db.session.flush()
            
            pending_mods  = (
                Modifications.query.filter(
                    Modifications.table_name == 'Specimens',
                    Modifications.record_id == str(item.id),
                    Modifications.status == 'Pending').count())
            
            #if changes are made to preapproved fields and there no pending modifications
            if preapproved_mods > 0 and pending_mods == 0:
                #set specimen status to active
                Specimens.query.filter_by(id=item.id).update({Specimens.pending_submitter: None, Specimens.db_status: 'Active'},synchronize_session=False)
                #override the flash
                session.pop('_flashes', None)
                flash(Markup(f"<b>{item.accession_number}</b> now approved for use."), "success")

            case = Cases.query.get(item.case.id)
            case_id = case.id

            case_pending = Modifications.query.filter_by(table_name='Cases', record_id=case_id,
                                                         status='Pending').count()
            pending_containers = Containers.query.filter(sa.and_(Containers.case_id == case_id,
                                                                 Containers.pending_submitter != None)).count()
            pending_specimens = Specimens.query.filter(sa.and_(Specimens.case_id == case_id,
                                                               Specimens.pending_submitter != None)).count()

            # If the container was not fully approved, set the pending_submitter of the case to the current user only if
            # the case details have been approved
            if item.pending_submitter:
                if not case_pending:
                    case.pending_submitter = item.pending_submitter

            # If the case and all it's content is approved.
            if not case_pending and not pending_containers and not pending_specimens:

                # Set evidence_locker occupied to false on approval
                # Get the equipment IDs for all security lockers
                evidence_lockers = [item.equipment_id for item in EvidenceLockers.query]
                for container in Containers.query.filter_by(case_id=case_id):
                    if container.submission_route in evidence_lockers:
                        evidence_locker = EvidenceLockers.query.filter_by(
                            equipment_id=container.submission_route).first()
                        evidence_locker.occupied = False

                # if any discipline requested set status to "Need Test Addition" Only if there is specimens, no case_status and
                # no existing tests this should preserve the case status if updates are made to the case later on after testing
                # has been added
                if (case.testing_requested and not case.case_status and Specimens.query.filter_by(
                        case_id=case_id).count()
                        and not Tests.query.filter_by(case_id=case_id).count()):
                    case.case_status = 'Need Test Addition'

                unlock_item(case_id, Cases, 'case_number', request.referrer)
                locked_containers = Containers.query.filter_by(case_id=case_id, locked_by=current_user.initials)
                for container in locked_containers:
                    unlock_item(container.id, Containers, 'accession_number', request.referrer)

                locked_specimens = Specimens.query.filter_by(case_id=case_id, locked_by=current_user.initials)
                for specimen in locked_specimens:
                    unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)

                case.db_status = 'Active'
                case.pending_submitter = None
                case.review_discipline = None

                # Set evidence_locker occupied to false on approval
                # Get the equipment IDs for all security lockers
                for container in Containers.query.filter_by(case_id=case.id, location_type='Evidence Lockers'):
                    evidence_locker = EvidenceLockers.query.filter_by(
                        equipment_id=container.submission_route).first()
                    evidence_locker.occupied = False

            db.session.commit()

            if request.form.get('submit_attach'):
                return redirect(url_for('containers.attach', item_id=item.container_id,
                                        redirect_url=url_for('cases.view', item_id=item.case_id)))
            else:
                return redirect(url_for('cases.view', item_id=item.case_id))
        else:
            form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                    form.discipline.data)

    elif request.method == 'GET':

        form = get_form_choices(Approve(), container_id=item.container.id, case_id=item.case.id,
                                discipline=item.discipline, item=item)

        kwargs['custody_type'] = 0
        if item.evidence_comments:
            kwargs['evidence_comments'] = "\n".join(item.evidence_comments.split("; "))
        if give_custody:
            if item.custody != current_user.initials:
                item.custody = current_user.initials
                item.custody_type = 'Person'
                add_specimen_audit(destination=current_user.initials,
                                reason=f'{current_user.initials} opened specimen review form',
                                o_time=datetime.now(),
                                specimen_id=item.id,
                                status='Out')

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)
    form = Update()
    custody = request.args.get('custody', type=int)

    if custody == 1:
        custody = True
    else:
        custody = False
        form.custody_type.validators = []
        form.custody_type.validate_choice = False
        form.custody.data = item.custody

    kwargs['custody_input'] = custody
    kwargs['give_custody'] = custody


    # Set the evidence comment form
    kwargs['evidence_comment_form'] = get_evidence_comment_choices(Form())
    # Sets the name of the units in submitted_sample_amount field
    kwargs['units'] = 'No Units'
    if item.type.unit:
        kwargs['units'] = item.type.unit.name

    kwargs['comments'] = [comment for comment in CommentInstances.query.filter_by(comment_item_type='Specimens', 
                                                                                  comment_item_id=item.id,
                                                                                  db_status='Active')]

    if request.method == 'POST':
        form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                form.discipline.data)
        selected_specimen_type = SpecimenTypes.query.get(form.specimen_type_id.data)

        if selected_specimen_type and 'other' not in selected_specimen_type.name.lower():
            # Remove the validator and clear the value
            form.other_specimen.validators = []
            form.other_specimen.raw_data = ['']
        if form.validate() and form.is_submitted():
            if form.evidence_comments.data:
                add_comments(form, item.accession_number, 'Specimen')
            
            if custody:
                add_specimen_audit(destination=form.custody.data, 
                                   reason=f'{current_user.initials} submitted specimen update form', 
                                   o_time=datetime.now(), 
                                   specimen_id=item.id, 
                                   status='Out')

            kwargs.update(process_form(form), event='Update')

            update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
              
            #sets conditions and volumes as preapproved fields by updating modifications to approved
            preapproved_mods = (
                Modifications.query.filter(
                    Modifications.table_name == 'Specimens',
                    Modifications.record_id == str(item.id),
                    Modifications.status == 'Pending',
                    Modifications.field_name.in_(['submitted_sample_amount', 'condition']) #update this to add more preapproved fields
                ).update({
                    Modifications.status: 'Approved',
                    Modifications.reviewed_by: current_user.id,
                    Modifications.review_date: datetime.now(),}, synchronize_session=False))
            db.session.flush()
            
            pending_mods  = (
                Modifications.query.filter(
                    Modifications.table_name == 'Specimens',
                    Modifications.record_id == str(item.id),
                    Modifications.status == 'Pending').count())
            
            #if changes are made to preapproved fields and there no pending modifications
            if preapproved_mods > 0 and pending_mods == 0:
                #set specimen status to active
                Specimens.query.filter_by(id=item.id).update({Specimens.pending_submitter: None, Specimens.db_status: 'Active'},synchronize_session=False)
                #override the flash
                session.pop('_flashes', None)
                flash(Markup(f"<b>{item.accession_number}</b> now approved for use."), "success")


            # If the specimen is pending after updating. Set the case's db_status to 'Pending'
            # and make the current user the pending submitter of the case to trigger the approval process.
            if item.pending_submitter:
                item.case.pending_submitter = current_user.initials
                item.case.db_status = 'Pending'
                db.session.commit()

            if request.form.get('submit_attach'):
                return redirect(url_for('containers.attach', item_id=item.container_id,
                                        redirect_url=url_for('cases.view', item_id=item.case_id)))
            else:
                return redirect(url_for('cases.view', item_id=item.case_id))

        else:
            form = get_form_choices(form, form.container_id.data, form.case_id.data, form.custody_type.data,
                                    form.discipline.data)

    elif request.method == 'GET':
        # Sets the name of the units in submitted_sample_amount field
        form = get_form_choices(form, container_id=item.container.id, case_id=item.case.id,
                                discipline=item.discipline, item=item)

        kwargs['units'] = item.type.unit.name
        kwargs['custody_type'] = 0
        if item.evidence_comments:
            kwargs['evidence_comments'] = "\n".join(item.evidence_comments.split("; "))
        
        if custody:
            if item.custody != current_user.initials:
                item.custody = current_user.initials
                item.custody_type = 'Person'
                add_specimen_audit(destination=current_user.initials, 
                                   reason=f'{current_user.initials} opened specimen update form', 
                                   o_time=datetime.now(), 
                                   specimen_id=item.id, 
                                   status='Out')

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
    # Since admin removals don't go through the approve_remove function, we also need to
    # have the decrement code here
    if current_user.permissions in ['Admin', 'Owner']:
        container = table.query.get(item_id).container
        container.n_specimens -= 1
        container.n_specimens_submitted -= 1

    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove


@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    container = table.query.get(item_id).container
    container.n_specimens -= 1
    container.n_specimens_submitted -= 1

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
    # If the specimen is restores, increment n_specimens and n_specimens_submitted.
    container = table.query.get(item_id).container
    container.n_specimens += 1
    container.n_specimens_submitted += 1

    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    SpecimenAudit.query.filter_by(specimen_id=item_id).delete()
    specimen = Specimens.query.get(item_id)
    if specimen.container:
        container = Containers.query.get(specimen.container.id)
        container.n_specimens -= 1
        container.n_specimens_submitted -= 1

    delete_comments(item_id, item_type)

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

    _import = import_items(form, table, table_name, item_name, dtype={'collection_time': str})

    return _import


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():
    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    alias = request.args.get('alias')

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
    kwargs = default_kwargs.copy()
    kwargs['discipline'] = disciplines
    discipline = kwargs['discipline']

    spec_id = Specimens.query.order_by(Specimens.id.desc()).first()

    print(f'most recent ID {spec_id}')

    query = request.args.get('query')
    query_type = request.args.get('query_type')
    items = None

    if query_type == 'discipline':
        if query:
            items = Specimens.query.join(SpecimenTypes).filter(SpecimenTypes.discipline.contains(query))

    _view_list = view_items(table, item_name, item_type, table_name, items=items, query=query, **kwargs)

    return _view_list


# @blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
# @login_required
# def view(item_id):
#     item = table.query.get_or_404(item_id)
#
#     alias = f"{getattr(item, name)}"
#
#     view_only = request.args.get('view_only')
#     view_only = False
#     if item.locked and item.locked_by != current_user.initials:
#         view_only = True
#     if item.pending_submitter:  # and item.pending_submitter != current_user.initials:
#         view_only = True
#
#     container = Containers.query.get(item.container_id)
#     tests = db.session.query(Tests).filter(Tests.specimen_id == item.id).all()
#     test_ids = [test.id for test in tests]
#     results = db.session.query(Results).filter(Results.test_id.in_(test_ids))
#     attachments = db.session.query(Attachments).filter_by(table_name=item_name, record_id=item_id)
#     specimen_audit = db.session.query(SpecimenAudit).filter_by(specimen_id=item_id).order_by(
#         SpecimenAudit.o_time.desc())
#
#     test_ids = [item.test_id for item in results]
#
#     _view = view_item(item, alias, item_name, table_name,
#                       view_only=view_only,
#                       container=container,
#                       tests=tests,
#                       test_ids=test_ids,
#                       results=results,
#                       attachments=attachments,
#                       specimen_audit=specimen_audit)
#     return _view

@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    kwargs = default_kwargs.copy()
    print(item_id)
    item = table.query.get_or_404(item_id)
    print(f'condition - {item.condition}')
    alias = getattr(item, 'accession_number')
    view_only = request.args.get('view_only')
    if not view_only:
        view_only = False
        if item.locked and item.locked_by != current_user.initials:
            view_only = True
        elif item.pending_submitter:  # and item.pending_submitter != current_user.initials:
            view_only = True

    tests = db.session.query(Tests).filter(Tests.specimen_id == item.id).all()
    test_ids = [test.id for test in tests]
    results = db.session.query(Results).filter(Results.test_id.in_(test_ids))
    result_test_ids = [result.test_id for result in results]
    specimen_audit = SpecimenAudit.query.filter(and_(SpecimenAudit.specimen_id == item_id,
                                                     SpecimenAudit.db_status != 'Removed')).order_by(
        SpecimenAudit.id.desc())

    pending_audits = [audit for audit in specimen_audit if audit.db_status == 'Pending']

    test_ids = [item.test_id for item in results]

    delete_mod = []
    pending_mods = []
    delete_mod = Modifications.query.filter_by(record_id=str(item_id), event='DELETE',
                                               status='Approved', table_name=item_name).first()

    mods = Modifications.query.filter_by(record_id=str(item_id), table_name=item_name). \
        order_by(Modifications.submitted_date.desc())

    custody_form = AdminCustody()
    admin_custody_form = AdminOnlyCustody()

    custody_form.custody_type.choices = [(k, k) for k, v in location_dict.items()]

    admin_custody_form.custody_type.choices = [(k, k) for k, v in location_dict.items()]
    admin_custody_form.custody_type.choices.insert(0, ('', 'Please select a custody type'))
    admin_custody_form.custody.choices = [(" ", 'No custody type selected')]

    selected_custody_type = custody_form.custody_type.data
    if selected_custody_type in [v['table'] for v in location_dict.values()]:
        custody_table = location_dict[selected_custody_type]['table']
        if custody_table:
            alias = location_dict[selected_custody_type]['alias']
            # Populate the custody field based on the selected custody type
            custody_form.custody.choices = [
                (getattr(item, alias), getattr(item, alias)) for item in custody_table.query
            ]
        else:
            custody_form.custody.choices = [(" ", 'No custody type selected')]
    else:
        custody_form.custody.choices = [(" ", 'No custody type selected')]

    if custody_form.validate_on_submit() and 'admin_custody_submit' not in request.form:
        # put custody of specimen change here
        # put specimen audit change here
        # custody = chosen custody
        # reason = Initials Admin custody change (LNR Admin Custody Change)
        print(f'custody_type {custody_form.custody_type.data}')
        print(f'custody {custody_form.custody.data}')
        item.custody = custody_form.custody.data
        item.custody_type = custody_form.custody_type.data
        db.session.commit()

        created_by = current_user.initials

        if current_user.permissions in ['Admin', 'Owner']:
            modified_by = current_user.initials
            db_status = 'Active'
            user_string = '[Admin Change]'
        else:
            modified_by = None
            db_status = 'Pending'
            user_string = '[User Change]'

        add_specimen_audit(destination=custody_form.custody.data,
                           reason=f'{current_user.initials} {user_string} {custody_form.reason.data}',
                           o_time=datetime.now(),
                           specimen_id=item.id,
                           status='',
                           created_by=created_by,
                           modified_by=modified_by,
                           db_status=db_status)
        
    if admin_custody_form.validate_on_submit() and 'admin_custody_submit' in request.form:
        item.custody = admin_custody_form.custody.data
        db.session.commit()

    # Generate modification tooltips (hover behaviour) for item fields
    tooltips = {}
    # for mod in mods:
    #     if mod.field != "Reason":
    #         if mod.original_value == "":
    #             original_value = "[None]"
    #         else:
    #             original_value = mod.original_value
    #         if mod.new_value == "":
    #             new_value = "[None]"
    #         else:
    #             new_value = mod.new_value
    #
    #         tooltips[mod.field] = f"{original_value} > {new_value}<br>" \
    #                                    f"({mod.submitter.initials} > {mod.reviewer.initials})"
    #
    # print(tooltips)
    pending_submitters = {}
    # Get pending modifications for alerts
    pending_mods = Modifications.query.filter_by(record_id=str(item_id),
                                                 status='Pending',
                                                 table_name=item_name).all()
    # # This will show which fields are pending changes
    # pending_mods = [mod for mod in pending_mods]
    # This says how many fields are pending changes
    n_pending = len(pending_mods)
    # n_pending = 0
    for mod in pending_mods:
        pending_submitters[mod.field] = mod.submitter.initials

    kwargs['custody_form'] = custody_form

    today = datetime.now()

    disc_form = EditDiscipline()

    if disc_form.is_submitted() and disc_form.validate() and 'disc_submit' in request.form:
        print('disc_form submitted')

        now_discipline = item.discipline
        new_discipline = disc_form.add_discipline.data
        item.discipline = f"{now_discipline}, {new_discipline}" if now_discipline else new_discipline

        event = 'UPDATED'
        status = 'Approved'
        spec_revision = -1

        disc_original_value = now_discipline
        item.discipline = f"{now_discipline}, {new_discipline}" if now_discipline else new_discipline

        spec_mod = Modifications.query.filter_by(record_id=item.id, table_name='Specimens',
                                                 field_name='discipline').first()
        if spec_mod:
            spec_revision = int(spec_mod.revision)

        spec_revision += 1

        modification = Modifications(
            event=event,
            status=status,
            table_name='Specimens',
            record_id=item.id,
            revision=spec_revision,
            field='Discipline',
            field_name='discipline',
            original_value=now_discipline,
            original_value_text=str(now_discipline),
            new_value=item.discipline,
            new_value_text=str(item.discipline),
            submitted_by=current_user.id,
            submitted_date=datetime.now(),
            reviewed_by=current_user.id,
            review_date=datetime.now(),
        )

        db.session.add(modification)
        db.session.commit()

        # mods? db.session.add(modification)

    # alias = getattr(item, name)

    _view = view_item(item, alias, item_name, table_name,
                      view_only=view_only,
                      tests=tests,
                      test_ids=test_ids,
                      results=results,
                      result_test_ids=result_test_ids,
                      specimen_audit=specimen_audit,
                      default_header=False,
                      default_buttons=False,
                      custody_form=custody_form,
                      today=today,
                      disc_form=disc_form,
                      pending_audits=pending_audits,
                      admin_custody_form=admin_custody_form
                      )

    return _view


@blueprint.route(f'/{table_name}/get_containers/', methods=['GET', 'POST'])
@login_required
def get_containers():
    case_id = request.args.get('case_id', type=int)
    specimen_id = request.args.get('parent_specimen', type=int)
    containers = Containers.query.filter_by(case_id=case_id).all()
    containers_lst = []
    collectors = []
    collected_by = False

    print(f'SPECIMEN ID: {specimen_id}')

    if specimen_id:
        specimen = Specimens.query.get(specimen_id)
        container_id = specimen.container_id
        discipline = specimen.discipline
        specimen_type = specimen.specimen_type_id
        collection_vessel = specimen.type.collection_container_id
        print(f'SPECIMEN TYPE: {specimen_type}')
        return jsonify({'container_id': container_id, 'discipline': discipline, 'type_id': specimen_type,
                        'collection_vessel': collection_vessel})
    elif case_id:
        case = Cases.query.get(case_id)
        if case.type.id == 7:
            collected_by = True
            collectors = [{'id': item.id, 'name': f"{item.last_name}, {item.first_name}"} for item in
                          Personnel.query
                          .join(Divisions)
                          .join(Agencies)
                          .filter(Agencies.id == 1, Personnel.status_id == 1)
                          .order_by(Personnel.last_name)
                          ]
            collectors.insert(0, {'id': 0, 'name': 'Please select a collector'})

        if len(containers) != 0:
            containers_lst.append({'id': 0, 'name': 'Please select a container'})
            for item in containers:
                dict = {}
                dict['id'] = item.id
                dict['name'] = f"{item.accession_number} - {item.type.name}"
                containers_lst.append(dict)
        else:
            containers_lst.append({'id': 0, 'name': 'This case has no containers'})

    else:
        containers_lst.append({'id': 0, 'name': 'No case selected'})

    print(collectors)
    return jsonify(containers=containers_lst, 
                   collected_by=collected_by, collectors=collectors)


@blueprint.route(f'/{table_name}/get_collectors/', methods=['GET', 'POST'])
@login_required
def get_collectors():
    container_id = request.args.get('container_id', type=int)
    container = Containers.query.filter_by(id=container_id).first()
    if container.submitter:
        container_submitting_agency = container.submitter.agency.name
    else:
        container_submitting_agency = None

    collected_by = False
    if container_submitting_agency == 'San Francisco Office of the Chief Medical Examiner':
        collected_by = True
        collectors = [{'id': item.id, 'name': f"{item.last_name}, {item.first_name}"} for item in
                      Personnel.query
                      .join(Divisions)
                      .join(Agencies)
                      .filter(Agencies.id == 1,Personnel.status_id == 1)
                      .order_by(Personnel.last_name)
                      ]
        collectors.insert(0, {'id': 0, 'name': 'Please select a collector'})
    else:
        collectors = [{'id': 0, 'name': '---'}]

    return jsonify(collected_by=collected_by, collectors=collectors)


@blueprint.route(f'/{table_name}/get_specimen_types/', methods=['GET'])
@login_required
def get_specimen_types():
    discipline = request.args.getlist('discipline[]')

    specimen_types = []

    for disc in discipline:
        specimen_types.extend(SpecimenTypes.query.filter(
            func.lower(SpecimenTypes.discipline).contains(disc.lower())
        ))

    # specimen_types = [SpecimenTypes.query.filter(
    #     func.lower(SpecimenTypes.discipline).contains(disc.lower())
    # ).all() for disc in discipline]

    choices = []

    if discipline:
        if len(specimen_types) > 0:
            choices.append({'id': 0, 'name': 'Please select a specimen type'})
            for specimen_type in specimen_types:
                choice = {}
                choice['id'] = specimen_type.id
                choice['name'] = f"[{specimen_type.code}] - {specimen_type.name}"
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This discipline has no specimen types'})
    else:
        choices.append({'id': 0, 'name': 'No discipline selected'})

    return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/get_specimen_type_defaults/', methods=['GET', 'POST'])
@login_required
def get_specimen_type_defaults():
    specimen_type_id = request.args.get('specimen_type_id', type=int)

    specimen_type = SpecimenTypes.query.get(specimen_type_id)

    default_site = specimen_type.specimen_site_id
    default_collection_container = specimen_type.collection_container_id
    default_units = specimen_type.unit.name
    specimen_discipline = specimen_type.discipline.split(', ')

    location_return = ''

    if 'Toxicology' in specimen_type.discipline:
        location_type = 'Cooled Storage'
    elif 'Histology' in specimen_type.discipline:
        if current_user.job_class in ['2456', '2403', '2458', '2457']:
            location_type = 'Hoods'
        else:
            location_type = 'Cooled Storage'
    elif 'Physical' in specimen_type.discipline:
        if current_user.job_class in ['2456', '2403', '2458', '2457']:
            location_type = 'Evidence Storage'
        else:
            location_type = 'Benches'
    elif 'Drug' in specimen_type.discipline:
        if current_user.job_class in ['2456', '2403', '2458', '2457']:
            location_type = 'Evidence Storage'
        else:
            location_type = 'Evidence Lockers'

    choices, default_location = get_location_choices(location_type=location_type, return_var=True, store_as='name')    

    default_location_table = ''
    default_choice = ''

    if 'Other' in specimen_type.name:
        other = True
    else:
        other = False

    return jsonify(default_site=default_site,
                   default_collection_container=default_collection_container,
                   default_units=default_units,
                   other=other,
                   choices=choices,
                   default_location=default_location,
                   location_type=location_type)


@blueprint.route(f'/{table_name}/get_custody_locations/', methods=['GET', 'POST'])
@login_required
def get_custody_locations():
    custody_type = request.args.get('custody_type')
    response = get_location_choices(custody_type, store_as='name')

    return response


@blueprint.route(f'/{table_name}/get_default_id/', methods=['GET', 'POST'])
@login_required
def get_default_id():
    # Get custody type from request
    custody_type = request.args.get('custody_type')

    # Set default ID for specimen custody based on custody type
    if custody_type == 'Cooled Storage':
        default_id = CooledStorage.query.filter_by(equipment_id='08R').first().id
    else:
        default_id = Benches.query.filter_by(equipment_id='BS60').first().id

    return jsonify({'default_id': default_id})


@blueprint.route(f'/{table_name}/<int:item_id>/print')
@login_required
def print_specimen_label(item_id):
    # Get current specimen
    item = Specimens.query.get(item_id)
    case = Cases.query.get(item.case.id)

    attributes_list = []

    label_attributes = fields_dict['specimen']

    # Accessioning area printer
    if item.parent_specimen is not None and item.discipline == 'Histology':
        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'
        label_attributes = fields_dict['histo_slides']
    elif request.remote_addr == '10.63.21.58':
        printer = r'\\OCMEG9M020.medex.sfgov.org\BS01 - Accessioning'
    elif request.remote_addr == '10.63.21.64':
        printer = r'\\OCMEG9M022.medex.sfgov.org\BS11 - Accessioning'
    elif request.remote_addr == '10.63.20.115':
        printer = r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo'
    elif current_user.permissions == 'INV':
        # printer = current_user.default_printer
        printer = r'\\OCMEG9M042.medex.sfgov.org\DYMO LabelWriter 450 Turbo INV';
    else:
        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'

    # Check if case is HP and set attributes accordingly
    if item.parent_specimen is not None and item.discipline == 'Histology':
        if 'Tissue, ' in item.type.name:
            spec_name = item.type.name.split('Tissue, ')[1]
        else:
            spec_name = item.type.name
        name_list = list(spec_name)
        counter = 0
        for i in name_list:
            counter += 1
            if counter == 10:
                name_list.insert(counter, '-\n')
            if counter == 20:
                name_list.insert(counter, '-\n')

        specimen_name = ''.join(name_list)
        # Set relevant label fields
        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{item.id}.png')
        qrcode.make(f's: {item.id}').save(qr_path)

        with open(qr_path, "rb") as qr_file:
            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

        label_attributes['TYPE'] = f'[{item.type.code}]\n{specimen_name}'
        label_attributes['ACC_NUM'] = item.accession_number
        label_attributes['QR'] = qr_encoded
        label_attributes['TYPE_1'] = f'[{item.type.code}]\n{specimen_name}'
        label_attributes['ACC_NUM_1'] = item.accession_number
        label_attributes['QR_1'] = qr_encoded
        label_attributes['amount'] += 1
    elif case.type.code not in ['PM', 'B']:
        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{item.id}.png')
        qrcode.make(f's: {item.id}').save(qr_path)

        with open(qr_path, "rb") as qr_file:
            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

        label_attributes = fields_dict['hp_specimen']
        label_attributes['CASE_NUM'] = case.case_number
        label_attributes['CASE_NUM_1'] = case.case_number
        label_attributes['ACC_NUM'] = item.accession_number
        label_attributes['ACC_NUM_1'] = item.accession_number
        label_attributes['CODE'] = f'[{item.type.code}]'
        label_attributes['CODE_1'] = f'[{item.type.code}]'
        label_attributes['QR'] = qr_encoded
        label_attributes['QR_1'] = qr_encoded

    else:
        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'specimen{item.id}.png')
        qrcode.make(f's: {item.id}').save(qr_path)

        with open(qr_path, "rb") as qr_file:
            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

        label_attributes['LAST_FIRST'] = f'{case.last_name}, {case.first_name}'
        label_attributes['CASE_NUM'] = case.case_number
        label_attributes['ACC_NUM'] = item.accession_number
        label_attributes['CODE'] = f'[{item.type.code}]'
        label_attributes['TYPE'] = item.type.name
        label_attributes['QR'] = qr_encoded

    if item.case.case_type == CaseTypes.query.filter_by(code='M').first().id or \
            item.case.case_type == CaseTypes.query.filter_by(code='D').first().id or \
            item.case.case_type == CaseTypes.query.filter_by(code='X').first().id or \
            item.case.case_type == CaseTypes.query.filter_by(code='N').first().id or \
            item.case.case_type == CaseTypes.query.filter_by(code='P').first().id:

        for i in range(0, 2):
            attributes_list.append(label_attributes.copy())

    else:
        attributes_list.append(label_attributes.copy())

    if printer == r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo':
        # print_label(printer, attributes_list, True, 1)
        return jsonify(attributes_list, printer, True, 1,
                       url_for(f'{table_name}.view', item_id=item_id, ))
    else:
        # print_label(printer, attributes_list)
        return jsonify(attributes_list, printer, None, None,
                       url_for(f'{table_name}.view', item_id=item_id, ))

    # print_specimen(current.case, current)

    # return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/get_custody_options_modal/', methods=['GET'])
@login_required
def get_custody_options_modal():
    custody_type = request.args.get('custody_type')
    response = get_location_choices(custody_type)  # Assume this fetches the choices based on type
    return response


@blueprint.route(f'/{table_name}/<int:item_id>/review_custody/', methods=['GET'])
@login_required
def review_custody(item_id):
    item = table.query.get(item_id)
    func = request.args.get('func')

    if func == 'approve':
        db_status = 'Active'
    else:
        db_status = 'Removed'

    for audit in SpecimenAudit.query.filter_by(specimen_id=item_id, db_status='Pending'):
        audit.db_status = db_status
        if db_status == 'Active':
            audit.reason = f'{audit.reason} Approved By: {current_user.initials}'

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


def _parse_hhmm(hhmm: str) -> Optional[time]:
    """Accepts 'HHMM' (e.g., '0240', '1122'). Returns time or None."""
    if not hhmm:
        return None
    s = hhmm.strip()
    if len(s) != 4 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%H%M").time()
    except ValueError:
        return None

def _parse_date_any(s: str) -> Optional[date]:
    """Try multiple common date formats; return date or None."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

@blueprint.route(f'/{table_name}/validate-collection', methods=['GET'])
@login_required
def validate_collection():
    """
    Read-only validator: compares specimen collection (date+HHMM)
    with container submission (date+HHMM). Returns JSON only.
    """
    container_id = request.args.get('container_id', type=int)
    coll_date    = request.args.get('collection_date', type=str)
    coll_time    = request.args.get('collection_time', type=str, default='')

    # If we don't have enough info yet, don't block the user.
    if not container_id or not coll_date or not coll_time:
        return jsonify({"ok": True, "skip": True})

    container = Containers.query.get(container_id)
    if not container or not container.submission_date or not container.submission_time:
        return jsonify({"ok": True, "skip": True})

    # Parse inputs
    spec_date = _parse_date_any(coll_date)
    spec_time = _parse_hhmm(coll_time)
    cont_date = container.submission_date.date()  # model stores DateTime; date portion is meaningful
    cont_time = _parse_hhmm(container.submission_time)

    # If any part can't be parsed yet, let UI continue without blocking
    if not spec_date or not spec_time or not cont_time:
        return jsonify({"ok": True, "skip": True})

    spec_dt = datetime.combine(spec_date, spec_time)
    cont_dt = datetime.combine(cont_date, cont_time)

    if spec_dt > cont_dt:
        return jsonify({
            "ok": False,
            "message": "Warning: Specimen collection date/time is after container submission date/time."
        })

    return jsonify({"ok": True})