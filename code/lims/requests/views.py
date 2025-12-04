from lims.models import Requests
from lims.personnel.forms import AddFromRequest
from lims.personnel.functions import process_form
from lims.requests.forms import *
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.requests.functions import *
from lims.specimen_audit.views import add_specimen_audit
from lims.requests.forms import LegacySpecimenAdd

# Set item global variables
item_type = 'Request'
item_name = 'Requests'
table = Requests
table_name = 'requests'
name = 'name'  # This selects what property is displayed in the flash messages
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

    personnel_add_form = AddFromRequest()

    items_requested = ['Blood', 'Blood Spot', 'ME Bundle', 'Histology Slides', 'Other']

    form.requested_items_multi.choices = [(item, item) for item in items_requested]

    personnel_add_form.agency_id.choices = [(agency.id, agency.name) for agency in Agencies.query.all()]
    personnel_add_form.division_id.choices = [(division.id, division.name) for division in Divisions.query.all()]

    if form.is_submitted() and form.validate():

        selected_items = form.requested_items_multi.data
        other_value = form.requested_items_other.data.strip()

        # Replace "Other" with the value from requested_items_other
        if "Other" in selected_items and other_value:
            selected_items = [item if item != "Other" else other_value for item in selected_items]

        form.requested_items.data = ', '.join(selected_items)

        selected_case_ids = form.case_id.data
        cases = Cases.query.filter(Cases.id.in_(selected_case_ids)).all()
        specimen_ids = []

        for case in cases:
            specimens = Specimens.query.filter_by(case_id=case.id).all()
            specimen_ids.extend([specimen.id for specimen in specimens])

        unique_specimen_ids = ','.join(map(str, set(specimen_ids)))

        last_request = Requests.query.order_by(Requests.id.desc()).first()
        print(f'last-request - {last_request}')

        # Determine the next ID by incrementing the last ID or setting it to 1 if no requests exist
        if last_request:
            next_id = last_request.id + 1
            print(f'next id = {next_id}')
        else:
            next_id = 1

        # Format the ID as a 4-digit number with leading zeros
        formatted_id = f"{next_id:04d}"

        print(f'formatted id - {formatted_id}')

        # Set the name field to include the formatted ID
        form.name.data = f"Request_{formatted_id}"

        form.intake_user.data = current_user.id

        form.intake_date.data = datetime.now()

        form.status.data = 'Incomplete Request'

        form.next_of_kin_confirmation.data = 'No'

        form.payment_confirmation.data = 'No'

        form.email_confirmation.data = 'No'

        form.me_confirmation.data = 'No'

        form.prepare_status.data = 'None'

        form.check_status.data = 'None'

        form.release_status.data = 'None'

        if form.legacy_case_number.data:
            form.legacy_case.data = form.legacy_case_number.data


        if form.notes.data:
            form.notes.data = f"{form.notes.data} ({current_user.initials} {datetime.now().strftime('%m/%d/%Y %H:%M')})"

    kwargs = {'personnel_add_form': personnel_add_form,
              }


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

    item = table.query.get_or_404(item_id)

    form = get_form_choices(Update(), agency_id=item.requesting_agency, division_id=item.requesting_division,
                            dest_agency_id=item.destination_agency)

    personnel_add_form = AddFromRequest()

    kwargs['personnel_add_form'] = personnel_add_form
    kwargs['template'] = 'update_form.html'

    if form.is_submitted() and form.validate():
        if form.legacy_case_number.data:
            form.legacy_case.data = form.legacy_case_number.data

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


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
    kwargs = default_kwargs.copy()

    items = Requests.query.all()  # Replace with your query for the list

    case_ids = set()

    print(len(current_user.permissions))

    # Collect all case IDs from items
    for item in items:
        if item.case_id:
            case_ids.update(map(int, item.case_id.split(',')))  # Convert to integers
            # case_ids.update(int(float(x)) for x in item.case_id.split(','))  # use this for sqlite

    # Fetch the corresponding cases from the database
    cases = Cases.query.filter(Cases.id.in_(case_ids)).all()
    kwargs['case_number_map'] = {case.id: case.case_number for case in cases}

    _view_list = view_items(table, item_name, item_type, table_name, order_by=['ID DESC'], **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)

    alias = getattr(item, name)

    specimen_add_form = SpecimenAdd()
    specimen_review_form = SpecimenReview()
    collected_specimen_form = CollectSpecimen()
    note_add_form = AddNote()
    communication_add_form = AddCommunication()
    prepared_specimen_form = PrepareSpecimen()
    return_prepared_specimen_form = ReturnPreparedSpecimen()
    collect_checked_specimen_form = CheckSpecimen()
    collect_released_specimen_form = ReleaseSpecimen()
    return_checked_specimen_form = ReturnCheckedSpecimen()
    return_released_specimen_form = ReturnReleaseSpecimen()
    no_evidence_form = NoEvidenceFound()
    legacy_specimen_add_form = LegacySpecimenAdd()
    withdraw_request_form = WithdrawRequest()
    cancel_request_form = CancelRequest()
    update_received_date_form = UpdateReceivedDate()

    specimens = Specimens.query.filter(
        Specimens.case_id == item.case_id,
        Specimens.db_status != 'Removed',
        Specimens.released is not True
    ).all()

    existing_specimen_ids = item.specimens.split(',') if item.specimens else [
]
    if item.case_id:
        case_ids = [int(case_id.strip()) for case_id in item.case_id.split(',')]

        specimens = Specimens.query.filter(
            Specimens.case_id.in_(case_ids),
            ~Specimens.id.in_(existing_specimen_ids),  # Exclude existing specimens
            Specimens.db_status != 'Removed',
            Specimens.released is not True
        ).all()


        if specimens:
            specimen_add_form.specimens.choices = [
                (
                    str(specimen.id),
                    f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]"
                ) for specimen in specimens
            ]
        else:
            # Add a placeholder option if no specimens are available
            specimen_add_form.specimens.choices = [("", "No specimens found")]
            specimen_add_form.specimens.data = "No specimens found"
    else:
        specimen_add_form.specimens.choices = []

    # Handle form submission for adding specimens
    if specimen_add_form.is_submitted() and specimen_add_form.validate() and 'specimens_submit' in request.form:
        # Get current specimens as list
        existing_specimens = item.specimens.split(',') if item.specimens else []

        # Add new specimens from the form
        new_specimens = specimen_add_form.specimens.data

        # Combine and deduplicate specimens, then convert to comma-separated string
        combined_specimens = set(existing_specimens + new_specimens)
        updated_specimens_str = ','.join(sorted(combined_specimens))

        # Update the item with the new specimen list
        item.specimens = updated_specimens_str

        db.session.commit()

        flash('Specimens added successfully!', 'success')
        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Set up for displaying selected specimens (existing entries)
    specimen_ids = [int(id) for id in item.specimens.split(',')] if item.specimens else []
    selected_specimens = Specimens.query.filter(Specimens.id.in_(specimen_ids)).all()

    specimens_str = ', '.join(f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]" for specimen in selected_specimens)

    # If there are stored specimens, populate choices for deletion
    if item.specimens:
        stored_specimen_ids = item.specimens.split(',')
        stored_specimens = Specimens.query.filter(Specimens.id.in_(stored_specimen_ids)).all()

    specimen_review_form.approved_specimens.choices = [
        (str(specimen.id), f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]")
        for specimen in Specimens.query
        .filter(Specimens.id.in_(existing_specimen_ids))  # Include only existing specimens
        .all()
    ]

    collected_specimen_form.collected_specimen.choices = [
        (str(specimen.id), f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]")
        for specimen in Specimens.query
        .filter(Specimens.id.in_(existing_specimen_ids))
        .all()
    ]

    if specimen_review_form.is_submitted() and specimen_review_form.validate() and 'approved_submit' in request.form:
        selected_specimen_ids = specimen_review_form.approved_specimens.data

        # Convert selected specimens to a comma-separated string
        approved_specimens_str = ','.join(selected_specimen_ids)

        item.approved_specimens = approved_specimens_str

        item.approver_id = current_user.id

        item.approve_date = datetime.now()

        item.status = 'Ready for Preparation'


        db.session.commit()

        flash('Approved specimens successfully!', 'success')
        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    if collected_specimen_form.is_submitted() and collected_specimen_form.validate() and 'collected_submit' in request.form:
        # Assuming collected_specimen_form.collected_specimen.data is a list of IDs
        specimen_ids = collected_specimen_form.collected_specimen.data


        # add_specimen_audit(destination=current_user.initials,
        #                    reason=f'{current_user.initials} collected for preparation',
        #                    o_time=datetime.now(),
        #                    specimen_id=collected_specimen_form.collected_specimen.id,
        #                    status='Out')
        #
        # print(f' collected specimen -- {collected_specimen_form.collected_specimen.data}')

    approved_specimen_ids = [int(id) for id in item.approved_specimens.split(',')] if item.approved_specimens else []
    approved_specimens = Specimens.query.filter(Specimens.id.in_(approved_specimen_ids)).all()

    approved_specimens_str = ', '.join(f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]" for specimen in approved_specimens)


    if item.case_id:
        case_ids = [int(i.strip()) for i in item.case_id.split(',')]
        cases = Cases.query.filter(Cases.id.in_(case_ids)).all()
        case_number_str = ', '.join(f"{case.case_number} ({case.division.abbreviation})" if case.case_type == 7 and case.division else f"{case.case_number}" for case in cases)  # Create a single string of case numbers
    elif item.legacy_case:
        case_number_str = f'{item.legacy_case} (Legacy)'
    else:
        case_number_str = "N/A"

    # -- changes status depending on attachment / payment verification --
    if item.next_of_kin_confirmation != 'No' and item.payment_confirmation != 'No' and item.status == 'Incomplete Request':
        item.status = 'Pending Request'

    # -=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |
    # PREPARED SPECIMEN CUSTODY FORM                         |
    # -=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |

    prepared_specimen_form.prepared_specimen.choices = [(str(specimen.id),
                                                         f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]")
                                                        for specimen in Specimens.query
                                                        .filter(
            Specimens.id.in_(approved_specimen_ids))  # Include only existing specimens
                                                        .all()]

    collected_specimen_ids = None

    if prepared_specimen_form.is_submitted() and prepared_specimen_form.validate() and 'prepared_submit' in request.form:
        item.prepare_status = 'Return'
        collected_specimen_ids = prepared_specimen_form.prepared_specimen.data

        print(f'collected_specimen_ids {collected_specimen_ids}')

        # assigns chain of custody to current user
        for i in collected_specimen_ids:
            add_specimen_audit(i, current_user.initials, f'{current_user.initials} collected for preparation',
                               datetime.now(), 'OUT')

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = f'{current_user.initials}'
            specimen_location.custody_type = 'Person'
            db.session.commit()


        # Convert selected specimens to a comma-separated string
        collected_specimens_str = ','.join(collected_specimen_ids)

        item.in_custody_specimens = collected_specimens_str

        db.session.commit()

    # item.prepare_status = 'None'
    # db.session.commit()

    tables = {
        'Benches': Benches,
        'Cabinets': Cabinets,
        'Storage': Compactors,
        'Evidence Lockers': EvidenceLockers,
        'Hoods': FumeHoods,
        'Person': Users,
        'Cooled Storage': CooledStorage
    }

    aliases = {
        'Bench': 'equipment_id',
        'Cabinet': 'equipment_id',
        'Storage': 'equipment_id',
        'Evidence Lockers': 'equipment_id',
        'Hood': 'equipment_id',
        'Person': 'initials',
        'Cooled Storage': 'equipment_id'
    }
    return_prepared_specimen_form.custody_type.choices = [('', '---')] + [(key, key) for key in tables.keys()]
    return_prepared_specimen_form.custody.choices = [('', '---')]

    print(f'in custody specimens {item.in_custody_specimens}')

    if return_prepared_specimen_form.is_submitted() and 'return_prepared_submit' in request.form:

        custody_specimen_ids = ([int(s) for s in (item.in_custody_specimens or "").split(",") if s.strip().isdigit()])

        for i in custody_specimen_ids:
            add_specimen_audit(i, return_prepared_specimen_form.custody.data,
                               f'{current_user.initials} returned specimen after preparation',
                               datetime.now(), 'IN')

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = f'{return_prepared_specimen_form.custody.data}'
            specimen_location.custody_type = f'{return_prepared_specimen_form.custody_type.data}'
            db.session.commit()

        print()

        item.prepare_status = 'Complete'
        item.preparer = current_user.id
        item.prepare_date = datetime.now()
        item.status = 'Ready for Check'
        item.in_custody_specimens = None
        collected_specimen_ids = None
        db.session.commit()

    # -=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |
    # CHECKER SPECIMEN CUSTODY FORM                          |
    # -=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |

    collect_checked_specimen_form.checked_specimen.choices = [(str(specimen.id),
                                                               f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]")
                                                              for specimen in Specimens.query
                                                              .filter(
            Specimens.id.in_(approved_specimen_ids))  # Include only existing specimens
                                                              .all()]

    if collect_checked_specimen_form.is_submitted() and collect_checked_specimen_form.validate() and 'checked_specimen_submit' in request.form:
        item.check_status = 'Return'
        checked_specimen_ids = collect_checked_specimen_form.checked_specimen.data

        for i in checked_specimen_ids:
            add_specimen_audit(i, current_user.initials, f'{current_user.initials} collected for check',
                               datetime.now(), 'OUT')

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = f'{current_user.initials}'
            specimen_location.custody_type = 'Person'
            db.session.commit()

        print(f'checked specimen data == {collect_checked_specimen_form.checked_specimen.data}')

        # Convert selected specimens to a comma-separated string
        checked_specimen_str = ','.join(checked_specimen_ids)

        item.in_custody_specimens = checked_specimen_str

        db.session.commit()


    print(f'prepare status {item.prepare_status}')

    # item.check_status = 'None'
    # db.session.commit()

    return_checked_specimen_form.custody_type_checked.choices = [(key, key) for key in tables.keys()]
    return_checked_specimen_form.custody_checked.choices = []

    if return_checked_specimen_form.is_submitted() and 'return_checked_submit' in request.form:

        custody_specimen_ids = ([int(s) for s in (item.in_custody_specimens or "").split(",") if s.strip().isdigit()])

        for i in custody_specimen_ids:
            add_specimen_audit(i, return_checked_specimen_form.custody_checked.data,
                               f'{current_user.initials} returned specimen after preparation',
                               datetime.now(), 'IN')

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = f'{return_checked_specimen_form.custody_checked.data}'
            specimen_location.custody_type = f'{return_checked_specimen_form.custody_type_checked.data}'
            db.session.commit()


        item.check_status = 'Complete'
        item.checker = current_user.id
        item.check_date = datetime.now()
        item.status = 'Ready for Finalization'
        item.in_custody_specimens = None
        collected_specimen_ids = None
        db.session.commit()


    # -=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |
    # RELEASER SPECIMEN CUSTODY FORM                         |
    # -=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |

    collect_released_specimen_form.released_specimen.choices = [(str(specimen.id),
                                                               f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]")
                                                              for specimen in Specimens.query
                                                              .filter(
            Specimens.id.in_(approved_specimen_ids))  # Include only existing specimens
                                                              .all()]

    if collect_released_specimen_form.is_submitted() and collect_released_specimen_form.validate() and 'released_specimen_submit' in request.form:



        item.release_status = 'Return'
        collected_specimen_ids = collect_released_specimen_form.released_specimen.data

        # Convert selected specimens to a comma-separated string
        collected_specimens_str = ','.join(collected_specimen_ids)

        for i in collected_specimen_ids:
            add_specimen_audit(i, current_user.initials, f'{current_user.initials} collected for release',
                               datetime.now(), 'OUT')

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = f'{current_user.initials}'
            specimen_location.custody_type = 'Person'
            db.session.commit()

        item.in_custody_specimens = collected_specimens_str

        db.session.commit()
        # -=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |
        # ASSIGN CHAIN OF CUSTODY TO ALL APPROVED SPECIMEN HERE  |
        # -=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- |
    # Populate receiving agency choices
    return_released_specimen_form.receiving_agency.choices = [(agency.id, agency.name) for agency in
                                                              Agencies.query.all()]
    return_released_specimen_form.receiving_agency.choices.insert(0, (0, 'Select Receiving Agency'))

    # Populate receiving division choices based on the selected agency
    if item.agency_rec:  # Use the current receiving agency if set
        divisions = Divisions.query.filter_by(agency_id=item.agency_rec.id).all()
        return_released_specimen_form.receiving_division.choices = [(division.id, division.name) for division in
                                                                    divisions]
        return_released_specimen_form.receiving_division.choices.insert(0, (0, 'Select Receiving Division'))
    else:
        return_released_specimen_form.receiving_division.choices = [(0, 'No Divisions Available')]

    # Populate receiving personnel choices based on the selected division
    if item.division_rec:  # Use the current receiving division if set
        personnel = Personnel.query.filter_by(division_id=item.division_rec.id).all()
        return_released_specimen_form.receiving_personnel.choices = [
            (person.id, f"{person.first_name} {person.last_name}") for person in personnel
        ]
        return_released_specimen_form.receiving_personnel.choices.insert(0, (0, 'Select Receiving Personnel'))
    else:
        return_released_specimen_form.receiving_personnel.choices = [(0, 'No Personnel Available')]
    rooms = Rooms.query.all()
    cooled_storage = [(item.equipment_id, item.equipment_id) for item in CooledStorage.query.filter_by(equipment_id='09R')]

    # Populate the choices dynamically with room names or room numberscheck
    return_released_specimen_form.drop_off_location.choices = [(room.id, f"{room.name} - {room.room_number}") for room in rooms]
    return_released_specimen_form.drop_off_location.choices.extend(cooled_storage)

    if return_released_specimen_form.is_submitted() and 'return_released_submit' in request.form:
        custody_specimen_ids = []
        if item.approved_specimens is not None:
            custody_specimen_ids = ([int(s) for s in (item.in_custody_specimens or "").split(",") if s.strip().isdigit()])

        received_agency = Agencies.query.filter_by(id=return_released_specimen_form.receiving_agency.data).first()
        drop_off_name = None

        #If request was released as direct hand-off
        if return_released_specimen_form.in_person.data is True:
            item.release_date = datetime.now()
            item.received_date = datetime.now()
            item.status = 'Finalized'
            item.release_status = 'Complete'
            item.communications = None
            item.in_custody_specimens = None
            db.session.commit()
            
            for i in custody_specimen_ids:
                add_specimen_audit(i, received_agency.name,
                                   f'Request received',
                                   item.received_date, 'OUT')
                specimen_location = Specimens.query.filter_by(id=i).first()
                specimen_location.custody = f'{received_agency.name}'
                specimen_location.custody_type = f''
                db.session.commit()
        #If request was released through courier
        else:
            item.release_date = datetime.now()
            item.received_date = None
            item.status = 'Ready for Finalization'
            item.release_status = 'Complete'

            for i in custody_specimen_ids:
                # Handle data if 09R selected
                # Required because all other options are rooms and workflow queries "Rooms"
                if return_released_specimen_form.drop_off_location.data == '09R':
                    drop_off = CooledStorage.query.filter_by(equipment_id='09R').first()
                    drop_off_name = drop_off.equipment_id
                    reason = 'finalized release'
                # Handle for any other selection
                else:
                    drop_off = Rooms.query.filter_by(id=return_released_specimen_form.drop_off_location.data).first()
                    drop_off_name = drop_off.name
                    reason = 'dropped off for shipment'
                add_specimen_audit(i, drop_off_name, f'{current_user.initials} {reason}', item.release_date, 'OUT')
                if item.request_type.name != 'Hold':
                    add_specimen_audit(i, received_agency.name,
                                    f'Request picked up',
                                    item.release_date, 'OUT')
        
        item.custody = drop_off_name
        item.releaser = current_user.id
        collected_specimen_ids = None
        item.receiving_agency = return_released_specimen_form.receiving_agency.data
        item.receiving_division = return_released_specimen_form.receiving_division.data
        item.receiving_personnel = return_released_specimen_form.receiving_personnel.data
        db.session.commit()

    #Handling update date received form for when the request is received by destination agency
    if update_received_date_form.is_submitted() and update_received_date_form.validate() and 'update_received_date_submit' in request.form:
        custody_specimen_ids = []
        if item.approved_specimens is not None:
            custody_specimen_ids = ([int(s) for s in (item.in_custody_specimens or "").split(",") if s.strip().isdigit()])

        item.received_date = update_received_date_form.received_date.data 
        item.status = 'Finalized'
        item.release_status = 'Complete'
        item.communications = None
        if item.request_type.name != 'Hold':
                for i in custody_specimen_ids:
                    add_specimen_audit(i, item.dest_agency.name,
                                    f'Request received',
                                    item.received_date, 'OUT')
                    specimen_location = Specimens.query.filter_by(id=i).first()
                    specimen_location.custody = f'{item.dest_agency.name}'
                    specimen_location.custody_type = f''
    db.session.commit()

    prepared_specimen_ids = [int(id) for id in item.in_custody_specimens.split(',')] if item.in_custody_specimens else []
    prepared_specimens = Specimens.query.filter(Specimens.id.in_(prepared_specimen_ids)).all()

    if no_evidence_form.is_submitted() and 'evidence_confirm' in request.form:
        print("Form was submitted")
        item.status = 'Finalized'
        # 'N/A' = Not Applicable — meaning these fields are no longer relevant due to no evidence found
        item.me_confirmation = 'N/A'
        item.prepare_status = 'N/A'
        item.check_status = 'N/A'
        item.release_status = 'No Available Evidence'
        item.communications = None
        db.session.commit()

    print(f'{item.prepare_status}, {item.check_status}, {item.release_status}')

    kwargs = {'specimen_add_form': specimen_add_form,
              'selected_specimens': selected_specimens,
              'specimens_str': specimens_str,
              'specimen_review_form': specimen_review_form,
              'approved_specimens_str': approved_specimens_str,
              'collected_specimen_form': collected_specimen_form,
              'case_number_str': case_number_str,
              'approved_specimens': approved_specimens,
              'note_add_form': note_add_form,
              'communication_add_form': communication_add_form,
              'prepared_specimen_form': prepared_specimen_form,
              'return_prepared_specimen_form': return_prepared_specimen_form,
              'prepared_specimens': prepared_specimens,
              'collect_checked_specimen_form': collect_checked_specimen_form,
              'collect_released_specimen_form': collect_released_specimen_form,
              'return_checked_specimen_form': return_checked_specimen_form,
              'return_released_specimen_form': return_released_specimen_form,
              'no_evidence_form': no_evidence_form,
              'legacy_specimen_add_form': legacy_specimen_add_form,
              'withdraw_request_form': withdraw_request_form,
              'cancel_request_form': cancel_request_form,
              'update_received_date_form': update_received_date_form
              }

    if item.case_id:
        if len(item.case_id.split(', ')) == 1:
            case = Cases.query.get(int(item.case_id.split(', ')[0]))
            kwargs['subject_name'] = f'{case.last_name}, {case.first_name} {case.middle_name}'
        elif len(item.case_id.split(', ')) > 1:
            kwargs['subject_name'] = 'Multiple'
    else:
        kwargs['subject_name'] = 'N/A'

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


@blueprint.route('/get_all_personnel/')
@login_required
def get_personnel():
    division = request.args.get('division', type=int)
    agency = request.args.get('agency', type=int)

    # Filter personnel based on both agency and division
    personnel = Personnel.query.filter_by(division_id=division, agency_id=agency, status_id='1').all()
    choices = []

    if division != 0:
        if len(personnel) != 0:
            choices.append({'id': 0, 'name': '---'})
            for person in personnel:
                choice = {
                    'id': person.id,
                    'name': f"{person.first_name} {person.last_name}"
                }
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This division has no personnel'})
    else:
        choices.append({'id': 0, 'name': 'No division selected'})

    return jsonify({'personnel': choices})


@blueprint.route('/requests/get_divisions/')
@login_required
def get_divisions():
    agency_id = request.args.get('agency', type=int)

    # Query divisions based on the provided agency ID
    divisions = Divisions.query.filter_by(agency_id=agency_id).all()
    choices = []

    # Build the choices list based on available divisions
    if agency_id != 0:
        if divisions:
            choices.append({'id': 0, 'name': 'Please select a division'})
            for division in divisions:
                choice = {
                    'id': division.id,
                    'name': division.name
                }
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'No divisions available for this agency'})
    else:
        choices.append({'id': 0, 'name': 'No agency selected'})

    return jsonify({'divisions': choices})


@blueprint.route(f'/{table_name}/<int:item_id>/approval_request')
@login_required
def approval_request(item_id):

    item = table.query.get_or_404(item_id)
    item.status = 'Ready for Authorization'
    db.session.commit()

    flash('Approval Requested', 'success')

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route('/requests/add_personnel', methods=['POST'])
@login_required
def add_personnel():
    item_type = 'Personnel'
    item_name = 'Personnel'
    table = Personnel
    table_name = 'personnel'
    name = "full_name"  # This selects what property is displayed in the flash messages
    requires_approval = False  # controls whether the approval process is required. Can be set on a view level
    ignore_fields = []  # fields not added to the modification table
    disable_fields = []  # fields to disable
    template = 'form.html'
    redirect_to = 'view'
    default_kwargs = {'template': template,
                      'redirect': redirect_to}
    kwargs = default_kwargs.copy()

    personnel_add_form = AddFromRequest()
    personnel_add_form.agency_id.choices = [(agency.id, agency.name) for agency in Agencies.query.all()]
    personnel_add_form.division_id.choices = [(division.id, division.name) for division in Divisions.query.all()]

    print("Submitted form data:", request.form)  # Debugging form data

    if personnel_add_form.is_submitted() and personnel_add_form.validate() and 'personnel_submit' in request.form:
        kwargs.update(process_form(personnel_add_form))

        _add = add_item(personnel_add_form, table, item_type, item_name, table_name,
                        requires_approval, name, **kwargs)

    # Redirect back to the main add form
    return redirect(url_for('requests.add'))


@blueprint.route(f'/{table_name}/<int:item_id>/update_nok_status')
@login_required
def update_nok_status(item_id):
    # Fetch the item from the database
    item = table.query.get_or_404(item_id)

    # Get the status argument
    status = request.args.get('status')

    # Update the status
    if status == 'verify':
        item.next_of_kin_confirmation = current_user.initials
        item.next_of_kin_date = datetime.now()
    elif status == 'na':
        item.next_of_kin_confirmation = 'N/A'


    # Save changes to the database
    db.session.commit()

    # Redirect back to the same page
    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/update_payment_status')
@login_required
def update_payment_status(item_id):
    item = table.query.get_or_404(item_id)
    status = request.args.get('status')

    if status == 'verify':
        item.payment_confirmation = current_user.initials
        item.payment_confirmation_date = datetime.now()
    elif status == 'na':
        item.payment_confirmation = 'N/A'


    db.session.commit()
    flash('Payment confirmation status updated successfully!', 'success')

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/update_submission_status')
@login_required
def update_submission_status(item_id):
    item = table.query.get_or_404(item_id)
    status = request.args.get('status')

    if item.status != 'Ready for Authorization':
        item.status = 'Ready for Authorization'

    if status == 'verify':
        item.me_confirmation = current_user.initials
        item.me_confirmation_date = datetime.now()
    elif status == 'na':
        item.me_confirmation = 'N/A'


    db.session.commit()
    flash('Submission agency authorization status updated successfully!', 'success')

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/approver_legacy')
@login_required
def approver_legacy(item_id):
    item = table.query.get_or_404(item_id)
    submit_status = request.args.get('submit_status')

    if submit_status == 'approver':
        item.status = 'Ready for Preparation'
        item.approver_id = current_user.id
        item.approve_date = datetime.now()
    elif submit_status == 'preparer':
        item.status = 'Ready for Check'
        item.preparer = current_user.id
        item.prepare_date = datetime.now()
    elif submit_status == 'checker':
        item.status = 'Ready for Finalization'
        item.checker = current_user.id
        item.check_date = datetime.now()
    elif submit_status == 'approve_no_evidence':
        item.status = 'Finalized'
        item.communications = None
        item.approver_id = current_user.id
        item.approve_date = datetime.now()


    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))

@blueprint.route(f'/{table_name}/<int:item_id>/remove_specimen', methods=['POST'])
@login_required
def remove_specimen(item_id):
    item = table.query.get_or_404(item_id)
    specimen_id = request.form.get('specimen_id')

    if specimen_id and item.specimens:
        specimen_list = item.specimens.split(',')
        specimen_list = [s for s in specimen_list if s.strip() != specimen_id]
        item.specimens = ','.join(specimen_list)
        db.session.commit()
        flash('Specimen removed successfully!', 'success')
    
    return redirect(url_for(f'{table_name}.view', item_id=item_id))

# Remove a legacy specimen entry from requests based on the given index.
# Parses comma-separated legacy field strings, removes the indexed row, and updates the database.
@blueprint.route(f'/{table_name}/<int:item_id>/remove_legacy_specimen', methods=['POST'])
@login_required
def remove_legacy_specimen(item_id):
    item = table.query.get_or_404(item_id)  # or however your logic gets the request item
    index = request.form.get('legacy_index', type=int)

    def remove_indexed_value(csv_string):
        parts = [p.strip() for p in (csv_string or '').split(',')]
        if 0 <= index < len(parts):
            parts.pop(index)
        return ','.join(parts)

    item.legacy_code = remove_indexed_value(item.legacy_code)
    item.legacy_accession_number = remove_indexed_value(item.legacy_accession_number)
    item.legacy_date_created = remove_indexed_value(item.legacy_date_created)
    item.legacy_created_by = remove_indexed_value(item.legacy_created_by)
    item.legacy_checked_by = remove_indexed_value(item.legacy_checked_by)

    db.session.commit()
    flash('Legacy specimen removed from request.', 'success')
    return redirect(url_for('requests.view', item_id=item.id))

@blueprint.post(f'/{table_name}/<int:item_id>/withdraw')
@login_required
def withdraw_request(item_id):
    item = table.query.get_or_404(item_id)

    # If you want CSRF validation with WTForms, bind the form here:
    form = WithdrawRequest()
    if not form.validate_on_submit():
        flash('Invalid submission.', 'danger')
        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    item.status = 'Finalized'
    item.me_confirmation ='N/A'
    item.prepare_status = 'N/A'
    item.check_status = 'N/A'
    item.release_status = 'Withdrawn'
    item.communications = None
    db.session.commit()
    flash('Request successfully withdrawn!', 'success')
    return redirect(url_for(f'{table_name}.view', item_id=item_id))

@blueprint.post(f'/{table_name}/<int:item_id>/cancel')
@login_required
def cancel_request(item_id):
    item = table.query.get_or_404(item_id)
    form = CancelRequest()

    if not form.validate_on_submit():
        flash('Invalid submission.', 'danger')
        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    item.status = 'Finalized'
    item.me_confirmation ='N/A'
    item.prepare_status = 'N/A'
    item.check_status = 'N/A'
    item.release_status = 'Canceled'
    item.communications = None
    db.session.commit()
    flash('Request successfully canceled!', 'success')
    return redirect(url_for(f'{table_name}.view', item_id=item_id))

@blueprint.route(f'/{table_name}/<int:item_id>/legacy-specimen', methods=['POST'])
@login_required
def add_legacy_specimen(item_id):
    item = table.query.get_or_404(item_id)   # same 'table' you use elsewhere
    form = LegacySpecimenAdd()

    if not form.validate_on_submit():
        flash("Invalid legacy specimen submission.", "danger")
        return redirect(url_for(f"{table_name}.view", item_id=item_id))

    def append(existing, new):
        new = (new or "").strip()
        if not new:
            return existing
        return f"{existing}, {new}" if existing else new

    # Append submitted values
    item.legacy_code = append(item.legacy_code, form.legacy_code.data)
    item.legacy_accession_number = append(item.legacy_accession_number, form.legacy_accession_number.data)
    item.legacy_date_created = append(item.legacy_date_created, form.legacy_date_created.data)
    item.legacy_created_by = append(item.legacy_created_by, form.legacy_created_by.data)
    item.legacy_checked_by = append(item.legacy_checked_by, form.legacy_checked_by.data)

    db.session.commit()
    flash("Legacy specimen details updated successfully!", "success")
    return redirect(url_for(f"{table_name}.view", item_id=item_id))

@blueprint.route(f'/{table_name}/<int:item_id>/add-communication', methods=['POST'])
@login_required
def add_communication(item_id):
    item = table.query.get_or_404(item_id)
    form = AddCommunication()
    if form.validate_on_submit():
        existing_communications = item.communications or ""
        new_communications = form.communications.data.strip()
        if new_communications:
            updated_communications= f"{existing_communications}\n{new_communications} ({current_user.initials} {datetime.now().strftime('%m/%d/%Y %H:%M')})"
            item.communications = updated_communications.strip()
            db.session.commit()
    return redirect(url_for(f"{table_name}.view", item_id=item_id))

@blueprint.route(f'/{table_name}/<int:item_id>/no-evidence', methods=['POST'], endpoint='mark_no_evidence')
@login_required
def mark_no_evidence(item_id):
    item = table.query.get_or_404(item_id)
    form = NoEvidenceFound()

    if form.validate_on_submit() and form.evidence_confirm.data:
        item.status = 'Finalized'
        # N/A = fields not applicable because there is no evidence available
        item.me_confirmation = 'N/A'
        item.prepare_status = 'N/A'
        item.check_status = 'N/A'
        item.release_status = 'No Available Evidence'
        item.communications = None

        db.session.commit()
    return redirect(url_for(f'{table_name}.view', item_id=item_id))