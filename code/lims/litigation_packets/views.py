import threading
from flask import send_from_directory
from lims.litigation_packets.forms import Add, Edit, Approve, LitPacketUpdate, UploadedCompletedPacket, Communications
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.litigation_packets.functions import *
from flask import session
from os.path import relpath
from datetime import datetime


# Set item variables
item_type = 'Litigation Packet'
item_name = 'Packets'
table = LitigationPackets
table_name = 'litigation_packets'
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

#
# @blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
# @login_required
# def add():
#     kwargs = default_kwargs.copy()
#     form = Add()
#     all_cases = Cases.query.all()
#     form.case_id.choices = [(case.id, f"{case.case_number}") for case in all_cases]
#     case_number = Cases.query.filter_by(id=form.case_id.data).first()
#     all_agencies = Agencies.query.all()
#     form.agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in all_agencies]
#     form.del_agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in
#                                                                      all_agencies]
#
#     # Populate divisions based on selected agency
#     if form.agency_id.data and form.agency_id.data != 0:
#         divisions = Divisions.query.filter_by(agency_id=form.agency_id.data).all()
#         form.division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in
#                                                                         divisions]
#     else:
#         form.division_id.choices = [(0, 'Please select a Division')]
#
#     # Populate personnel based on selected division
#     if form.division_id.data and form.division_id.data != 0:
#         personnel = Personnel.query.filter_by(division_id=form.division_id.data).all()
#         form.personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in
#                                                                         personnel]
#     else:
#         form.personnel_id.choices = [(0, 'Please select Personnel')]
#
#     if form.del_agency_id.data and form.del_agency_id.data != 0:
#         divisions = Divisions.query.filter_by(agency_id=form.del_agency_id.data).all()
#         form.del_division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in
#                                                                             divisions]
#     else:
#         form.del_division_id.choices = [(0, 'Please select a Division')]
#
#     if form.del_division_id.data and form.del_division_id.data != 0:
#         personnel = Personnel.query.filter_by(division_id=form.del_division_id.data).all()
#         form.del_personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in
#                                                                             personnel]
#     else:
#         form.del_personnel_id.choices = [(0, 'Please select Personnel')]
#
#     print(form.case_id.data)
#     # Add logic to handle form submission and validation
#     if form.is_submitted() and form.validate():
#         folder_name = f"{case_number.case_number}_L1"
#         folder_path = os.path.join(current_app.root_path, 'static/subpoena', folder_name)
#         if not os.path.exists(folder_path):
#             os.makedirs(folder_path)
#         # path = os.path.join(folder_path, f"{case_number.case_number} subpoena.pdf")
#         existing_packets = LitigationPackets.query.filter(
#             LitigationPackets.packet_name.like(f"{case_number.case_number}_L%")
#         ).all()
#
#         # Determine the next number in the sequence
#         if existing_packets:
#             max_number = max(
#                 int(packet.packet_name.split('_L')[-1]) for packet in existing_packets
#             )
#             next_number = max_number + 1
#         else:
#             next_number = 1
#
#
#         # existing_packets = LitigationPackets.query.filter(
#         #     LitigationPackets.packet_name.like(f'{case_number.case_number}_L%')
#         # ).all()
#         #
#         # if existing_packets:
#         #     max_number = max(
#         #         int(packet.packet_name.split('_L')[-1]) for packet in existing_packets
#         #     )
#         #     next_number = max_number + 1
#         # else:
#         #     next_number = 1
#         #
#         # if next_number > 1:
#         #     previous_packet_name = f"{case_number.case_number}_L{next_number - 1}"
#         #     previous_packet = LitigationPackets.query.filter_by(packet_name=previous_packet_name).first()
#         #
#         #     if previous_packet and previous_packet.packet_status not in ['Finalized', 'Canceled']
#
#         # Create the new packet name
#         new_packet_name = f'{case_number.case_number}_L{next_number}'
#         form.packet_name.data = new_packet_name
#         form.packet_status.data = 'Created'
#         _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
#         return redirect(url_for('litigation_packets.view_list'))
#
#     _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
#
#     return _add


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = Add()
    all_cases = Cases.query.filter(Cases.create_date > datetime(2025, 1, 1)).all()
    form.case_id.choices = [(case.id, f"{case.case_number}") for case in all_cases]
    case_number = Cases.query.filter_by(id=form.case_id.data).first()
    all_agencies = Agencies.query.all()
    form.agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in all_agencies]
    form.del_agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in all_agencies]

    # Populate divisions based on selected agency
    if form.agency_id.data and form.agency_id.data != 0:
        divisions = Divisions.query.filter_by(agency_id=form.agency_id.data).all()
        form.division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in divisions]
    else:
        form.division_id.choices = [(0, 'Please select a Division')]

    # Populate personnel based on selected division
    if form.division_id.data and form.division_id.data != 0:
        personnel = Personnel.query.filter_by(division_id=form.division_id.data).all()
        form.personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in personnel]
    else:
        form.personnel_id.choices = [(0, 'Please select Personnel')]

    if form.del_agency_id.data and form.del_agency_id.data != 0:
        divisions = Divisions.query.filter_by(agency_id=form.del_agency_id.data).all()
        form.del_division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in divisions]
    else:
        form.del_division_id.choices = [(0, 'Please select a Division')]

    if form.del_division_id.data and form.del_division_id.data != 0:
        personnel = Personnel.query.filter_by(division_id=form.del_division_id.data).all()
        form.del_personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in personnel]
    else:
        form.del_personnel_id.choices = [(0, 'Please select Personnel')]

    # Check if the form is submitted and validated
    if form.is_submitted() and form.validate():
        # Fetch existing packets for the case number
        existing_packets = LitigationPackets.query.filter(
            LitigationPackets.packet_name.like(f"{case_number.case_number}_L%")
        ).all()

        if existing_packets:
            # Step 1: Check for packets that are not finalized and find the highest finalized L number
            not_finalized_packet = None
            max_finalized_number = 0

            for packet in existing_packets:
                l_number = int(packet.packet_name.split('_L')[-1])
                if packet.packet_status == 'Finalized':
                    # Track the highest finalized packet number
                    max_finalized_number = max(max_finalized_number, l_number)
                elif packet.packet_status != 'Canceled':
                    # Track the first non-finalized, non-canceled packet we find
                    not_finalized_packet = packet

            if not_finalized_packet:
                # There is a packet that is not finalized, prompt the user for confirmation
                session['form_data'] = request.form.to_dict(flat=False)
                return redirect(url_for('litigation_packets.confirm_packet_creation', item_id=not_finalized_packet.id))

            # Step 2: If no non-finalized packets exist, create the next packet incrementally based on finalized packets
            next_number = max_finalized_number + 1 if max_finalized_number > 0 else 1
            new_packet_name = f'{case_number.case_number}_L{next_number}'
            form.packet_name.data = new_packet_name
            form.packet_status.data = 'Created'

        else:
            # Step 3: No packets exist for this case number, create the first packet (L1)
            new_packet_name = f'{case_number.case_number}_L1'
            form.packet_name.data = new_packet_name
            form.packet_status.data = 'Created'

        # Add the new packet
        _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
        return redirect(url_for('litigation_packets.view_list'))

    # Render the form again if not submitted or validation failed
    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/confirm_packet_creation/<int:item_id>', methods=['GET', 'POST'])
@login_required
def confirm_packet_creation(item_id):
    packet = LitigationPackets.query.get_or_404(item_id)

    print("Reached confirm_packet_creation route")

    if request.method == 'POST':
        print("Form submitted with POST method")
        if 'continue' in request.form:
            print("Continue button clicked")
            try:
                # Cancel the existing packet
                packet.packet_status = 'Canceled'
                print(f"Packet {packet.packet_name} status set to Canceled")

                # Commit the status change separately to avoid transaction conflict
                db.session.commit()
                print("Canceled status committed")

                # Retrieve form data from the session
                form_data = session.get('form_data', None)
                print(f"Retrieved form data from session: {form_data}")

                if not form_data:
                    flash("Session expired or form data not found. Please try again.", "danger")
                    return redirect(url_for('litigation_packets.view_list'))

                # Convert form data into a format suitable for FlaskForm population
                form = Add(data={key: value[0] for key, value in form_data.items()})
                print(f"Form populated with session data: {form.data}")

                case_number = Cases.query.filter_by(id=form.case_id.data).first()

                # Use the same L number as the canceled packet
                current_l_number = packet.packet_name.split('_L')[-1]
                new_packet_name = f'{case_number.case_number}_L{current_l_number}'

                # Update form data for the new packet
                form.packet_name.data = new_packet_name
                form.packet_status.data = 'Created'

                requested_date = datetime.strptime(form.requested_date.data,
                                                   "%Y-%m-%d") if form.requested_date.data else None
                due_date = datetime.strptime(form.due_date.data, "%Y-%m-%d") if form.due_date.data else None
                current_date = datetime.now().strftime("%m/%d/%Y")
                current_time = datetime.now().strftime("%H:%M")
                print(f"New packet name set to: {new_packet_name}")
                print(f'FORM _+_+__+_+_ = {form.agency_id.data}')

                # Create the new packet in the database
                new_packet = LitigationPackets(
                    case_id=form.case_id.data,
                    packet_name=form.packet_name.data,
                    packet_status='Created',
                    agency_id=form.agency_id.data,
                    division_id=form.division_id.data,
                    personnel_id=form.personnel_id.data,
                    requested_date=requested_date,
                    due_date=due_date,
                    created_by=current_user.initials,
                    create_date=datetime.now()
                    # Add any other fields from the form that need to be populated
                )
                db.session.add(new_packet)
                print(f"New packet added to the session: {new_packet}")

                # Commit the new packet creation
                db.session.commit()
                print("All changes committed to the database")

                # Clear session data after successfully creating the packet
                session.pop('form_data', None)
                print("Session data cleared after packet creation")

                flash(f"New packet {new_packet_name} has been created.", "success")
                return redirect(url_for('litigation_packets.view_list'))

            except Exception as e:
                # Rollback in case of error
                db.session.rollback()
                print(f"Error occurred: {str(e)}")
                flash(f"An error occurred: {str(e)}", "danger")
                return redirect(url_for('litigation_packets.confirm_packet_creation', item_id=item_id))

        else:
            # User chose not to continue
            session.pop('form_data', None)
            print("User chose not to continue; session data cleared")  # Debugging statement
            return redirect(url_for('litigation_packets.view_list'))

    # Render confirmation page on GET request
    print("Rendering confirmation page on GET request")  # Debugging statement
    return render_template('litigation_packets/confirm_packet_creation.html', packet=packet)


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
    kwargs['template'] = 'lit_form_update.html'
    form = LitPacketUpdate()
    all_cases = Cases.query.all()
    form.case_id.choices = [(case.id, f"{case.case_number}") for case in all_cases]
    lit = LitigationPackets.query.filter_by(id=item_id).first()
    case_number = Cases.query.filter_by(id=lit.case_id).first()
    print(f'case num {case_number.case_number}')
    # Set the initial value for the form fields
    form.agency_id.data = lit.agency_id
    form.division_id.data = lit.division_id
    # form.agency_id = lit.agency.name
    print("Agency ID:", form.agency_id.data)
    print("Division ID:", form.division_id.data)
    all_agencies = Agencies.query.all()
    form.agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in all_agencies]
    form.del_agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in
                                                                     all_agencies]

    if form.agency_id.data and form.agency_id.data != 0:
        divisions = Divisions.query.filter_by(agency_id=form.agency_id.data).all()
        form.division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in
                                                                        divisions]
    else:
        form.division_id.choices = [(0, 'Please select a Division')]

    if form.division_id.data and form.division_id.data != 0:
        personnel = Personnel.query.filter_by(division_id=form.division_id.data).all()
        form.personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in
                                                                        personnel]
    else:
        form.personnel_id.choices = [(0, 'Please select Personnel')]

    if form.del_agency_id.data and form.del_agency_id.data != 0:
        divisions = Divisions.query.filter_by(agency_id=form.del_agency_id.data).all()
        form.del_division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in
                                                                            divisions]
    else:
        form.del_division_id.choices = [(0, 'Please select a Division')]

    if form.del_division_id.data and form.del_division_id.data != 0:
        personnel = Personnel.query.filter_by(division_id=form.del_division_id.data).all()
        form.del_personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in
                                                                            personnel]
    else:
        form.del_personnel_id.choices = [(0, 'Please select Personnel')]

    print(form.case_id.data)
    if form.is_submitted() and form.validate():
        form.packet_name.data = f'{case_number.case_number}_L1'
        _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
        return redirect(url_for('litigation_packets.view', item_id=item_id))
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
    # doc_delete = LitigationPacketTemplates.query.get(item_id).path
    # try:
    #     os.remove(doc_delete)
    # except OSError as error:
    #     print(error)
    #     print('File path can not be removed')
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

    alias = f"{request.args.get('alias')}"
    _attach = attach_items(form, item_id, table, item_name, table_name, name, alias=alias)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = default_kwargs.copy()

    folder_path = os.path.join(current_app.static_folder, 'filesystem/litigation_packets')
    files = os.listdir(folder_path) if os.path.exists(folder_path) else []

    ready_for_lp_nums = LitigationPackets.query.filter_by(packet_status='Ready for PP').count()
    ready_for_lr_nums = LitigationPackets.query.filter_by(packet_status='Ready for PR').count()

    # kwargs = {'files': files}

    packet_info_map = {}

    all_packets = LitigationPackets.query.all()
    for packet in all_packets:
        packet_name = packet.packet_name
        folder_path = os.path.join(current_app.static_folder, 'filesystem/litigation_packets', packet_name)
        upload_path = os.path.join(current_app.static_folder, 'packet upload', f"{packet_name}_Uploads")
        case = Cases.query.get(packet.case_id)

        zip_files = []
        uploaded_files = []

        if os.path.exists(folder_path):
            zip_files = [f for f in os.listdir(folder_path) if f.endswith('.zip')]
        if os.path.exists(upload_path):
            uploaded_files = [f for f in os.listdir(upload_path) if f.endswith('.pdf')]

        if zip_files and len(zip_files) > 0:
            packet_info_map[packet.id] = {
                'packet_name': packet_name,
                'zip_files': zip_files,
                'uploaded_files': uploaded_files,
                'folder_path': folder_path,
                'upload_path': upload_path
            }
        # Builds a dictionary of all discipline status
        if case:
            status_dict = {
                    'toxicology': case.toxicology_status,
                    'biochemistry': case.biochemistry_status,
                    'histology': case.histology_status,
                    'external': case.external_status,
                    'physical': case.physical_status,
                    'drug': case.drug_status
                }
            discipline_statuses = "\n".join( #discipline status stored in a string for frontend display
                f"{label.capitalize()} status: {value}"
                for label, value in status_dict.items()
                if value is not None # discipline status will not display is None
            )
        else:
            discipline_statuses = "" 

        packet.discipline_statuses = discipline_statuses
        packet_info_map.setdefault(packet.id, {})["discipline_statuses"] = discipline_statuses

    kwargs['packet_info_map'] = packet_info_map
    kwargs['files'] = files
    kwargs['lp_nums'] = ready_for_lp_nums
    kwargs['lr_nums'] = ready_for_lr_nums
    kwargs['scheduled_lit_docs_exist'] = False

    # print(packet_info_map)
    _view_list = view_items(table, item_name, item_type, table_name, **kwargs)
    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)
    alias = f"{getattr(item, name)}"

    litigation_packet = LitigationPackets.query.filter_by(id=item_id).first()
    kwargs['packet_name'] = litigation_packet.packet_name

    if litigation_packet:
        packet_name = litigation_packet.packet_name
        folder_path = os.path.join(current_app.static_folder, 'filesystem/litigation_packets', packet_name)
        upload_path = os.path.join(current_app.static_folder, 'packet upload', f"{packet_name}_Uploads")

        zip_files = []
        uploaded_files = []

        # Check for ZIP files in the Litigation Packets folder
        if os.path.exists(folder_path):
            zip_files = [f for f in os.listdir(folder_path) if f.endswith('.zip')]

        # Check for PDF files in the packet upload folder
        if os.path.exists(upload_path):
            uploaded_files = []

            for f in os.listdir(upload_path):
                if f.endswith('.pdf'):
                    full_path = os.path.join(upload_path, f)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(full_path))
                    file_size = os.path.getsize(full_path)

                    uploaded_files.append({
                        'filename': f,  
                        'modified_time': modified_time, #when the file finished generating
                        'file_size': file_size,
                        })


        # Store the list of ZIP files and the list of uploaded files in kwargs to pass to the template
        kwargs['zip_files'] = zip_files
        kwargs['uploaded_files'] = uploaded_files
        kwargs['folder_name'] = packet_name
        kwargs['folder_path'] = folder_path
        kwargs['upload_path'] = upload_path
    else:
        # Handle the case where the litigation_packet does not exist
        kwargs['zip_files'] = []
        kwargs['uploaded_files'] = []
        kwargs['folder_name'] = ''
        kwargs['folder_path'] = ''
        kwargs['upload_path'] = ''

    record = LitigationPacketRequest.query\
                                     .filter(LitigationPacketRequest.db_status == 'Active', LitigationPacketRequest.item_id == item_id)\
                                     .first()
    kwargs['record'] = record.id if record else None
    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


def delayed_delete(file_path):
    time.sleep(5)  # Delay for 5 seconds
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File deleted: {file_path}")
        else:
            print(f"File not found: {file_path}")
    except Exception as e:
        print(f'Failed to delete {file_path}. Reason: {e}')

def just_delete(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File deleted: {file_path}")
        else:
            print(f"File not found: {file_path}")
    except Exception as e:
        print(f'Failed to delete {file_path}. Reason: {e}')

@app.route('/download_and_delete/<packet_name>/<file_name>')
def download_and_delete(packet_name, file_name):
    # Adjust the folder path to match the new structure
    folder_path = os.path.join(current_app.static_folder, 'filesystem/litigation_packets', packet_name)
    file_path = os.path.join(folder_path, file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        flash(f"The file {file_name} does not exist.", "danger")
        return redirect(request.referrer)

    # Proceed with the download and deletion
    threading.Thread(target=delayed_delete, args=(file_path,)).start()
    return send_file(file_path, as_attachment=True)

@app.route('/download_packet/<packet_name>/<file_name>')
def download_packet(packet_name, file_name):
    # Adjust the folder path to match the new structure
    folder_path = os.path.join(current_app.static_folder, 'filesystem/litigation_packets', packet_name)
    file_path = os.path.join(folder_path, file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        flash(f"The file {file_name} does not exist.", "danger")
        return redirect(request.referrer)

    return send_file(file_path, as_attachment=True)


@blueprint.route('/get_divisions/<int:agency_id>')
@login_required
def get_divisions(agency_id):
    divisions = Divisions.query.filter_by(agency_id=agency_id).all()
    division_list = [(division.id, division.name) for division in divisions]
    return jsonify(division_list)


@blueprint.route('/get_personnel/<int:division_id>')
@login_required
def get_personnel(division_id):
    personnel = Personnel.query.filter_by(division_id=division_id, status_id='1').all()
    personnel_list = [(person.id, person.full_name) for person in personnel]
    return jsonify(personnel_list)


@blueprint.route('/download/<path:folder_path>/<string:file_name>')
@login_required
def download_file(folder_path, file_name):
    try:
        # Ensure the file exists and is in the correct folder
        file_path = os.path.join(folder_path, file_name)
        if os.path.exists(file_path):
            return send_from_directory(directory=folder_path, path=file_name, as_attachment=True)
        else:
            flash("File not found.", "danger")
            return redirect(url_for('litigation_packets.view_list'))
    except Exception as e:
        flash(f"Error downloading file: {str(e)}", "danger")
        return redirect(url_for('litigation_packets.view_list'))


@blueprint.route(f'/{table_name}/<int:item_id>/completed_packet', methods=['GET', 'POST'])
@login_required
def completed_packet(item_id):
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'upload_l1.html'
    item = table.query.get_or_404(item_id)
    form = UploadedCompletedPacket()

    lit_packet = LitigationPackets.query.filter_by(id=item_id).first()

    if form.is_submitted() and form.validate():
        lit_packet.litigation_preparer = current_user.id
        lit_packet.litigation_prepare_date = datetime.now()
        lit_packet.packet_status = 'Ready for PR'
        file = form.file.data
        filename = secure_filename(file.filename)

        # Ensure the uploaded file is a PDF
        if not filename.lower().endswith('.pdf'):
            flash("Only PDF files are allowed.", "danger")
            return redirect(request.url)

        # Create a folder named after lit_packet.file_name + "Uploads"
        folder_name = f"{lit_packet.packet_name}_Uploads"
        folder_path = os.path.join(current_app.root_path, 'static/packet upload', folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Save the file in the created folder
        file_path = os.path.join(folder_path, filename)
        file.save(file_path)

        # Update the database record
        lit_packet.file_name = filename
        lit_packet.completed_packet_path = file_path
        db.session.commit()

        # Redirect to the specific view page for the litigation packet
        return redirect(url_for('litigation_packets.view', item_id=item.id))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/ready_for_lp', methods=['GET', 'POST'])
@login_required
def ready_for_lp(item_id):

    # item = table.query.get(item_id)
    packet = LitigationPackets.query.filter_by(id=item_id).first()
    packet.packet_status = 'Ready for PP'
    print(packet.packet_status)
    db.session.commit()

    return redirect(url_for('litigation_packets.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/lp', methods=['GET', 'POST'])
@login_required
def lp(item_id):
    # litigation_preparer = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = prep_user
    # litigation_prepare_date = db.Column(db.DateTime)
    packet = LitigationPackets.query.filter_by(id=item_id).first()
    packet.packet_status = 'Ready for PR'
    packet.litigation_preparer = current_user.id
    packet.litigation_prepare_date = datetime.now()
    db.session.commit()

    return redirect(request.referrer)

@blueprint.route(f'/{table_name}/<int:item_id>/lr/<packet_name>/', defaults={'file_name': None, 'record': None}, methods=['GET', 'POST'])
@blueprint.route(f'/{table_name}/<int:item_id>/lr/<packet_name>/<file_name>/', defaults={'record': None}, methods=['GET', 'POST'])
@blueprint.route(f'/{table_name}/<int:item_id>/lr/<packet_name>/<file_name>/<record>', methods=['GET', 'POST'])
@login_required
def lr(item_id, packet_name, file_name, record):

    packet = LitigationPackets.query.filter_by(id=item_id).first()
    packet.packet_status = 'Finalized'
    packet.litigation_reviewer = current_user.id
    packet.litigation_review_date = datetime.now()
    packet.communications = None
    new_record = Records(
        case_id=packet.case_id,
        record_name=packet.packet_name,
        created_by=current_user.initials,
        create_date=datetime.now(),
        record_type=7
        # Add other fields as necessary
    )
    db.session.add(new_record)
    db.session.flush()  # This will assign an ID to the new record without committing yet
    # Assign the new record's ID to the litigation packet
    packet.record_id = new_record.id

    if record is not None:
        record_obj = LitigationPacketRequest.query.get_or_404(record)
        record_obj.db_status = 'Inactive'
    db.session.commit()
    if file_name is not None:
        folder_path = os.path.join(current_app.static_folder, 'filesystem/litigation_packets', packet_name)
        file_path = os.path.join(folder_path, file_name)

        just_delete(file_path)  # Delete the file immediately

    return redirect(request.referrer)


@blueprint.route(f'/{table_name}/<int:item_id>/revised_packet', methods=['GET', 'POST'])
@login_required
def revised_packet(item_id):
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'upload_l1.html'
    item = table.query.get_or_404(item_id)
    form = UploadedCompletedPacket()

    lit_packet = LitigationPackets.query.filter_by(id=item_id).first()

    if form.is_submitted() and form.validate():
        file = form.file.data
        filename = secure_filename(file.filename)

        # Ensure the uploaded file is a PDF
        if not filename.lower().endswith('.pdf'):
            flash("Only PDF files are allowed.", "danger")
            return redirect(request.url)

        # Create a folder named after lit_packet.packet_name + "Uploads"
        folder_name = f"{lit_packet.packet_name}_Uploads"
        folder_path = os.path.join(current_app.root_path, 'static/packet upload', folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Identify and rename existing files to include "Draft X" suffix, but only existing files
        # existing_files = os.listdir(folder_path)
        # draft_files = [f for f in existing_files if "Draft" in f]
        # non_draft_files = [f for f in existing_files if "Draft" not in f]
        #
        # # Rename non-draft files to "Draft X"
        # for existing_file in non_draft_files:
        #     existing_file_path = os.path.join(folder_path, existing_file)
        #     if os.path.isfile(existing_file_path):
        #         base, ext = os.path.splitext(existing_file)
        #         new_base = f"{base} Draft 1"
        #         counter = 1
        #
        #         # Increment draft number for existing drafts
        #         while any(f.startswith(new_base) for f in draft_files):
        #             counter += 1
        #             new_base = f"{base} Draft {counter}"
        #
        #         new_name = f"{new_base}{ext}"
        #         os.rename(existing_file_path, os.path.join(folder_path, new_name))
        #         draft_files.append(new_name)  # Update draft files list

        # Save the new file in the created folder
        file_path = os.path.join(folder_path, filename)

        # If a file with the same name already exists, append a unique identifier
        # if os.path.exists(file_path):
        #     base, ext = os.path.splitext(filename)
        #     counter = 1
        #     while os.path.exists(os.path.join(folder_path, f"{base} ({counter}){ext}")):
        #         counter += 1
        #     filename = f"{base} ({counter}){ext}"
        #     file_path = os.path.join(folder_path, filename)

        file.save(file_path)

        # Update the database record
        lit_packet.file_name = filename
        lit_packet.completed_packet_path = file_path
        lit_packet.packet_status = 'Ready for PR'
        lit_packet.litigation_preparer = current_user.id
        lit_packet.litigation_prepare_date = datetime.now()
        db.session.commit()

        # Redirect to the specific view page for the litigation packet
        return redirect(url_for('litigation_packets.view', item_id=item.id))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/revised_packet_lr', methods=['GET', 'POST'])
@login_required
def revised_packet_lr(item_id):
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'upload_l1.html'
    item = table.query.get_or_404(item_id)
    form = UploadedCompletedPacket()

    lit_packet = LitigationPackets.query.filter_by(id=item_id).first()

    if form.is_submitted() and form.validate():
        file = form.file.data
        filename = secure_filename(file.filename)

        # Ensure the uploaded file is a PDF
        if not filename.lower().endswith('.pdf'):
            flash("Only PDF files are allowed.", "danger")
            return redirect(request.url)

        # Create a folder named after lit_packet.packet_name + "Uploads"
        folder_name = f"{lit_packet.packet_name}_Uploads"
        folder_path = os.path.join(current_app.root_path, 'static/packet upload', folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Identify and rename existing files to include "Draft X" suffix, but only existing files
        existing_files = os.listdir(folder_path)
        draft_files = [f for f in existing_files if "Draft" in f]
        non_draft_files = [f for f in existing_files if "Draft" not in f]

        # Rename non-draft files to "Draft X"
        for existing_file in non_draft_files:
            existing_file_path = os.path.join(folder_path, existing_file)
            if os.path.isfile(existing_file_path):
                base, ext = os.path.splitext(existing_file)
                new_base = f"{base} Draft 1"
                counter = 1

                # Increment draft number for existing drafts
                while any(f.startswith(new_base) for f in draft_files):
                    counter += 1
                    new_base = f"{base} Draft {counter}"

                new_name = f"{new_base}{ext}"
                os.rename(existing_file_path, os.path.join(folder_path, new_name))
                draft_files.append(new_name)  # Update draft files list

        # Save the new file in the created folder
        file_path = os.path.join(folder_path, filename)

        # If a file with the same name already exists, append a unique identifier
        if os.path.exists(file_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(folder_path, f"{base} ({counter}){ext}")):
                counter += 1
            filename = f"{base} ({counter}){ext}"
            file_path = os.path.join(folder_path, filename)

        file.save(file_path)

        # Update the database record
        lit_packet.file_name = filename
        lit_packet.completed_packet_path = file_path
        lit_packet.packet_status = 'Ready for PR'
        lit_packet.litigation_preparer = current_user.id
        lit_packet.litigation_prepare_date = datetime.now()
        db.session.commit()

        # Redirect to the specific view page for the litigation packet
        return redirect(url_for('litigation_packets.view', item_id=item.id))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/reset', methods=['GET', 'POST'])
@login_required
def reset(item_id):
    packet = LitigationPackets.query.filter_by(id=item_id).first()
    packet.packet_status = 'Created'

    packet.litigation_preparer = None
    packet.litigation_prepare_date = None
    packet.litigation_reviewer = None
    packet.litigation_review_date = None

    db.session.commit()


    return redirect(url_for('litigation_packets.view_list'))


@blueprint.route(f'/{table_name}/<int:item_id>/cancel', methods=['GET', 'POST'])
@login_required
def cancel(item_id):

    packet = LitigationPackets.query.filter_by(id=item_id).first()
    packet.packet_status = 'Canceled'
    db.session.commit()

    return redirect(request.referrer)



@blueprint.route('/schedule', methods=['GET'])
@login_required
def view_schedule():
    records = LitigationPacketRequest.query\
                                     .filter(LitigationPacketRequest.db_status == 'Active')\
                                     .order_by(LitigationPacketRequest.scheduled_exec.desc()).all()
    
    return render_template('litigation_packets/schedule.html', records=records)



@blueprint.route('/download_lit/<int:id>/<int:item_id>')
@login_required
def download_lit(id, item_id):
    record = LitigationPacketRequest.query.get_or_404(id)
    case = Cases.query.get_or_404(item_id)
    case_name = case.case_number

    # # Mark record as inactive
    # record.db_status = 'Inactive'
    db.session.commit()

    zip_path = record.zip
    if not zip_path or not os.path.isfile(zip_path):
        flash("The file was deleted or you have downloaded this already!", "danger")
        # return redirect(request.referrer or url_for('litigation_packets.view_list'))

    # Start background thread to delete file after some delay
    # threading.Thread(target=delayed_delete, args=(zip_path,)).start()

    # Send file to user with desired filename
    return send_file(zip_path, as_attachment=True, download_name=f"{case_name}_L1 (Draft).zip")



@blueprint.route('/clear_failed_packets', methods=['GET'])
@login_required
def clear_failed_packets():
    records = LitigationPacketRequest.query.filter_by(status='Fail').all()
    for record in records:
        record.db_status = 'Inactive'
    db.session.commit()

    flash("Failed packets cleared successfully.", "success")
    return redirect(url_for('litigation_packets.view_schedule'))


@blueprint.route('/cancel_packet_schedule/<int:packet_id>', methods=['POST'])
@login_required
def cancel_packet_schedule(packet_id):
    record = LitigationPacketRequest.query.filter_by(id=packet_id, status='Scheduled').first()

    if not record:
        flash("Scheduled packet not found or already processed.", "danger")
        return redirect(url_for('litigation_packets.view_schedule'))

    record.db_status = 'Inactive'
    db.session.commit()
    flash(f"Scheduled packet {packet_id} cancelled successfully.", "success")
    return redirect(url_for('litigation_packets.view_schedule'))


@blueprint.route(f'/{table_name}/<int:item_id>/declaration', methods=['POST', 'GET'])
@login_required
def ready_for_declaration(item_id):
    item = table.query.get(item_id)

    item.packet_status = 'Waiting for Declaration'

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/declaration_sent', methods=['POST', 'GET'])
@login_required
def declaration_sent(item_id):
    item = table.query.get(item_id)

    print('route has been hit')

    item.declaration_sent_by = current_user.id
    item.declaration_sent_datetime = datetime.now()

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/revert', methods=['POST', 'GET'])
@login_required
def revert(item_id):
    item = table.query.get(item_id)

    item.packet_status = 'Ready for PP'
    item.litigation_preparer  = None
    item.litigation_prepare_date = None
    db.session.commit()

    return redirect(url_for(f"{table_name}.view", item_id=item.id))


@blueprint.route(f'/{table_name}/<int:item_id>/communications', methods=['GET', 'POST'])
@login_required
def communications(item_id):

    kwargs = default_kwargs.copy()

    item = table.query.get_or_404(item_id)

    form = Communications()

    kwargs['template'] = 'communications.html'

    errors = {}

    if form.validate_on_submit():
        new_comment = form.communications.data.strip()  # Get the new comment
        if new_comment:
            timestamp = datetime.now().strftime("%m/%d/%y %H:%M")  # Format timestamp
            user_initials = current_user.initials  # Get user initials

            # Append new comment while keeping history
            if item.communications:
                item.communications += f"\n{new_comment} ({user_initials}) {timestamp}"
            else:
                item.communications = f"{new_comment} ({user_initials}) {timestamp}"

            db.session.commit()  # Save changes


        return redirect(url_for('litigation_packets.view', item_id=item_id))  # Redirect to item view page

    # On GET request, keep the field empty for new entry
    form.communications.data = ''

    return render_template('litigation_packets/communications.html', form=form, item=item, errors=errors, **kwargs)

    return _update

