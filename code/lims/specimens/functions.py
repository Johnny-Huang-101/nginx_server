import os
import pathlib
from datetime import datetime, timedelta
import string

import pythoncom
from flask import render_template, current_app, jsonify
from flask_migrate import current
from sqlalchemy import or_
from win32com.client import Dispatch
from wtforms.validators import DataRequired

from lims.models import *
from lims import db, current_user
from lims.specimens.forms import Approve, Edit
from lims.view_templates.views import approve_item, edit_item, add_item
from lims.specimen_audit.views import add_specimen_audit
from lims.evidence_comments.functions import sort_comments
from lims.containers.forms import Add as ContainerAdd
from lims.containers.functions import process_form as containers_process
from lims.containers.functions import get_form_choices as get_container_choices
from lims.locations.functions import location_dict
from sqlalchemy.sql import text


def get_form_choices(form, container_id=None, case_id=None, custody_type=None, discipline=None,
                     from_autopsy=False, item=None):
    case = None

    cases = [(item.id, item.case_number) for item in Cases.query.filter(Cases.create_date > datetime(2025, 1, 1)).order_by(Cases.create_date.desc())]
    cases.insert(0, (0, 'Please select a case'))
    form.case_id.choices = cases

    form.parent_specimen.choices = [(0, 'Please select a case')]

    if container_id:
        container = Containers.query.get(container_id)
        case_id = container.case_id
        form.case_id.data = case_id
        case = Cases.query.get(case_id)
        containers = [(container.id, f"{container.accession_number} | {container.type.name}")
                      for container in Containers.query.filter_by(case_id=case_id)]
        containers.insert(0, (0, 'Please select a container'))
        form.container_id.choices = containers
        # form.container_id.data = container_id
        # if container.submitter.agency.name == 'San Francisco Office of the Chief Medical Examiner':
        #     form.no_collected_by.render_kw = {'disabled': False}
        if case.type.code == 'PM':
            form.no_collected_by.render_kw = {'disabled': False}
    elif case_id:
        form.case_id.data = case_id
        containers = [(container.id, f"{container.accession_number} | {container.type.name}")
                      for container in Containers.query.filter_by(case_id=case_id)]
        containers.insert(0, (0, 'Please select a container'))
        form.container_id.choices = containers
        form.parent_specimen.choices = [(specimen.id, specimen.accession_number) for specimen in
                                        Specimens.query.filter_by(case_id=case_id)]
        form.parent_specimen.choices.insert(0, (0, '---'))
    else:
        form.container_id.choices = [(0, 'No case selected')]

    custody_types = [(k, k) for k, v in location_dict.items()]
    custody_types.insert(0, (0, 'Please select a custody type'))
    form.custody_type.choices = custody_types

    if custody_type:
        custody_table = location_dict[custody_type]['table']
        if custody_table:
            alias = location_dict[custody_type]['alias']

            # Sort items by their alias. Many are sorted by equipment ID. Also handles if the alias
            # is a list like with rooms
            if isinstance(alias, list):
                order_by = text(alias[0])
            else:
                order_by = text(alias)

            custody = [
                (f"{getattr(item, alias[0])} - {getattr(item, alias[1])}",
                 f"{getattr(item, alias[0])} - {getattr(item, alias[1])}")
                if isinstance(alias, list) and len(alias) == 2 else (getattr(item, alias), getattr(item, alias))
                for item in custody_table.query.order_by(order_by)
            ]
            form.custody.choices = custody
        else:
            form.custody.choices = [(" ", 'No custody type selected')]
    else:
        form.custody.choices = [(" ", 'No custody type selected')]

    conditions = [(item.name, item.name) for item in
                  SpecimenConditions.query.order_by(SpecimenConditions.name.asc())]
    form.condition.choices = conditions

    collection_containers = [(item.id, item.display_name) for item in
                             SpecimenCollectionContainers.select_field_query().order_by(
                                 SpecimenCollectionContainers.display_name.asc()).all()]

    collection_containers.insert(0, (0, '---'))
    form.collection_container_id.choices = collection_containers

    form.collected_by.choices = [(0, '---')]
    form.collected_by.render_kw = {'disabled': True}

    form.discipline.choices = discipline_choices

    specimen_types = []
    if discipline:
        # form.discipline.data = discipline
        specimen_types = SpecimenTypes.query  # .filter(
        # func.lower(SpecimenTypes.discipline).contains(discipline.lower())
        # ).all()
        print(f'SPECIMEN TYPES: {specimen_types}')
        specimen_types = [(item.id, f"[{item.code}] - {item.name}") for item in specimen_types]
    specimen_types.insert(0, (0, 'Please select a specimen type'))
    form.specimen_type_id.choices = specimen_types

    if case_id:
        case = Cases.query.get(case_id)
        if case.type.code == 'PM':
            form.no_collected_by.render_kw = {'disabled': False}
            form.collected_by.choices = [(item.id, f"{item.last_name}, {item.first_name}") for item in
                                         Personnel.query
                                         .join(Divisions)
                                         .join(Agencies)
                                         .filter(Agencies.id == 1)
                                         .order_by(Personnel.last_name)
                                         ]
            form.collected_by.choices.insert(0, (0, 'Please select a collector'))
            form.collected_by.render_kw = {'disabled': False}

    if form.no_collected_by.data:
        form.collected_by.render_kw = {'disabled': True}

    # Set collected by to user if user not FLD
    if current_user.personnel:
        if current_user.personnel.division_id != Divisions.query.filter_by(abbreviation='FLD').first().id and \
                form.collected_by.data != 0:
            form.collected_by.data = current_user.personnel_id
    #Exclude certain disciplines if user is INV
    if current_user.permissions == 'INV':
        exclude = {'External','Histology', 'Biochemistry', 'Toxicology'}
        form.discipline.choices = [
        choice for choice in discipline_choices if choice[0] not in exclude
        ]
    else:
        form.discipline.choices = discipline_choices
        

    ### For Edit, Approve and Update
    # if the item's collection date was in the future (i.e., after the create_date, set the future_collection_date checkbox.
    # Set the no_collection_date and no_collection_time checkboxes and disable the fields
    if item:
        if item.collection_date and item.collection_time:
            # Convert the collection_time into a time object
            try:
                collection_time = datetime.strptime(item.collection_time, '%H%M').time()
            except ValueError:
                collection_time = datetime.strptime('0000', '%H%M').time()
            # Combine the collection date and collection time and compare to item.create_date.
            # if it after the create date, set the checkbox to checked.
            if datetime.combine(item.collection_date, collection_time) > item.create_date:
                form.future_collection_date.render_kw = {'checked': True}

        # If the specimen doesn't have a collection_date, disable the collection_date field
        # and check the no_collection_date checkbox
        if not item.collection_date:
            form.collection_date.render_kw = {'disabled': True}
            form.no_collection_date.render_kw = {'checked': True}

        # If the specimen doesn't have a collection_time, disable the collection_time field
        # and check the no_collection_time checkbox
        if not item.collection_time:
            form.collection_time.render_kw = {'disabled': True}
            form.no_collection_time.render_kw = {'checked': True}

        # If the specimen doesn't have a collection_time and collection_date disable the future_collection_date field
        if not item.collection_date and not item.collection_time:
            form.future_collection_date.render_kw = {'disabled': True}

        # If the specimen doesn't have a collect_by value and the case type is PM, disable the collected_by field
        # and check the no_collected_by checkbox. For HP cases, these fields are disabled by default
        if not item.collected_by and item.case.type.code == 'PM':
            form.collected_by.render_kw = {'disabled': True}
            form.no_collected_by.render_kw = {'checked': True}

        # If the specimen doesn't have a submitted_sample_amount, disable the submitted_sample_amount field
        # and check the unknown_sample_amount checkbox
        if not item.submitted_sample_amount:
            form.submitted_sample_amount.render_kw = {'disabled': True}
            form.unknown_sample_amount.render_kw = {'checked': True}

        if getattr(item, "collection_container_id", None):
            # Ensure it matches the SelectField's coerce=int
            form.collection_container_id.data = int(item.collection_container_id)
        else:
            # fall back to 0/placeholder if you want "---" selected
            form.collection_container_id.data = 0

        form.parent_specimen.choices = [(specimen.id, specimen.accession_number) for specimen in
                                        Specimens.query.filter_by(case_id=item.case_id)]

        form.parent_specimen.choices.insert(0, (0, '---'))

        if item.parent_specimen:
            form.sub_specimen.data = True
            form.parent_specimen.render_kw = {'disabled': False}
            form.parent_specimen.data = int(item.parent_specimen)

    return form


def process_form(form, event=None, accession_number=None):
    kwargs = {}
    print('Event: ', event)
    specimen_type = SpecimenTypes.query.get(form.specimen_type_id.data)
    discipline = specimen_type.discipline.lower().split(', ')
    # discipline = specimen_type.discipline.lower()
    case = Cases.query.get(form.case_id.data)
    # Handle multiple specimens with multiple discipline options
    for d in discipline:
        if hasattr(case, f"{d}_requested") and getattr(case, f"{d}_requested"):
            if not getattr(case, f"{d}_start_date"):
                setattr(case, f"{d}_start_date", datetime.now())

    if form.submitted_sample_amount.data:
        kwargs['current_sample_amount'] = form.submitted_sample_amount.data
    kwargs['custody'] = form.custody.data

    kwargs['evidence_comments'] = "\n".join(
        [x.rstrip() for x in sort_comments(form.evidence_comments.data).split("\n")])

    print(kwargs['evidence_comments'])
    if event == 'Add':
        # Check if there is an accession number submitted in the request
        if accession_number is not None:
            kwargs['accession_number'] = accession_number
        else:
            kwargs['accession_number'] = generate_accession_number()

        kwargs['accessioned_by'] = current_user.id
        kwargs['accession_date'] = datetime.now()
        container = Containers.query.get(form.container_id.data)  # Query to get spec. cont.
        # Get container and increment number of specimens
        container.n_specimens += 1
        transfer = None

        # if container.submission_route_type == 'By Hand':
        #     destination = container.submitter.first_name + ' ' + container.submitter.last_name
        # elif container.submission_route_type == 'By Location':
        #     table = tables[container.location_type]
        #     name = aliases[container.location_type]
        #     reference = table.query.get(container.submission_route)
        #     # destination = getattr(reference, name)
        #     destination = container.submission_route
        # elif container.submission_route_type == 'By Transfer':
        #     destination = container.submission_route
        #     transfer = container.transfer.initials
        # else:
        #     destination = 'Initial entry placeholder'
        #
        # if container.submission_time:
        #     submission_time = container.submission_time  # Cont. submission time specimen inherits
        # else:
        #     submission_time = datetime.now().strftime('%H:%M')
        #
        # submission_date = container.submission_date.date()
        #
        # # Handle errors if submission time can't be formatted
        # try:
        #     submission_time = datetime.strptime(container.submission_time, '%H%M').time()
        #     submission_datetime = datetime.combine(submission_date, submission_time)
        #     submission_datetime_plus_one = submission_datetime + timedelta(minutes=1)
        # except TypeError:
        #     submission_time = None
        #     submission_datetime = None
        #     submission_datetime_plus_one = None
        #
        # # most_recent_specimen = Specimens.query.order_by(Specimens.id.desc()).first().id
        # # specimen_id = most_recent_specimen + 1
        #
        # # Get the specimen_id for the specimen to be created which will be used to
        # # create specimen audit entries
        # specimen_id = Specimens.get_next_id()
        #
        # # Check if "By Transfer" selected for container submission_route_type
        # if transfer:
        #     # Set specimen audit data
        #     destinations = [container.submitter.full_name, transfer, destination, current_user.initials,
        #                     form.custody.data]
        #     o_times = [submission_datetime, submission_datetime, submission_datetime_plus_one, form.start_time.data,
        #                datetime.now()]
        # elif container.submission_route_type == 'By Location':
        #     destinations = [container.submitter.full_name, destination, current_user.initials, form.custody.data]
        #     o_times = [submission_datetime, submission_datetime, form.start_time.data, datetime.now()]
        #     print(f'DESTINATIONS: {destinations}')
        # else:
        #     # Set specimen audit data
        #     destinations = [container.submitter.full_name, current_user.initials, form.custody.data]
        #     o_times = [submission_datetime, form.start_time.data, datetime.now()]
        # # Make each specimen audit entry
        # for dest, o_time in zip(destinations, o_times):
        #     add_specimen_audit(destination=dest,
        #                        reason=f'{current_user.initials} submitted specimen add form',
        #                        o_time=o_time,
        #                        specimen_id=specimen_id,
        #                        status='Out')

    # kwargs['custody'] = form.assay_storage_id.data

    return kwargs


def generate_accession_number(commit=False):
    alphabet = list(string.ascii_uppercase)
    settings = CurrentSystemDisplay.query.first()

    accession_letter = settings.accession_letter
    accession_counter = settings.accession_counter
    print(accession_counter)

    accession_number = f"{accession_letter}{str(accession_counter).rjust(5, '0')}"

    if accession_counter == 99999:
        letter = alphabet[alphabet.index(accession_letter) + 1]
        accession_counter = 1
        settings.accession_letter = letter
    else:
        accession_counter += 1

    print(accession_counter)
    settings.accession_counter = accession_counter
    # db.session.commit()

    return accession_number


# def get_location_choices(location_type):
#     # Get table
#     table = tables.get(location_type)
#
#     # Initialize choices
#     choices = []
#     if table:
#
#         # Check if table is evidence lockers and get only unoccupied evidence lockers
#         if table == EvidenceLockers:
#             items = table.query.filter(or_(EvidenceLockers.occupied != True, EvidenceLockers.occupied == None))
#         # Get all items in table
#         else:
#             items = table.query
#
#         if items.count() != 0:
#             # Set initial choice
#             choices.append({'id': " ", 'name': f'Please select a {location_type.lower()}'})
#             for item in items:
#                 # Clear choice and name
#                 choice = {}
#                 name = None
#
#                 # Set name based on attribute present
#                 if not hasattr(item, 'status_id'):
#                     if hasattr(item, 'status'):
#                         if item.status == 'Active':
#                             name = getattr(item, aliases[location_type])
#                 elif hasattr(item, 'status_id'):
#                     if getattr(item, 'status_id') == 1:
#                         name = getattr(item, aliases[location_type])
#                 else:
#                     name = getattr(item, aliases[location_type])
#
#                 # If name, choice name and ID and append to choices
#                 if name:
#                     choice['id'] = name
#                     choice['name'] = name
#                     choices.append(choice)
#         else:
#             choices.append({'id': " ", 'name': 'This location type has no items'})
#     else:
#         choices.append({'id': " ", 'name': 'No location type selected'})
#
#     if location_type == 'Cooled Storage':
#         default_choice = CooledStorage.query.filter_by(equipment_id='08R').first().id
#     elif location_type == 'Bench':
#         default_choice = Benches.query.filter_by(equipment_id='BS60').first().id
#     else:
#         default_choice = 0
#
#     print(default_choice)
#     return jsonify({'choices': choices, 'default_choice': default_choice})


def custody_and_audit(item, item_id, reason, user=None):
    # Set the user audit is being transferred to
    if user:
        transfer_to = user
    else:
        transfer_to = current_user
    
    # Add specimen audit with relevant information
    add_specimen_audit(item_id, transfer_to.initials, f'{transfer_to.initials} {reason}', datetime.now(),
                       'Out')
    
    # Update current location to user taking custody
    item.custody = transfer_to.initials

    db.session.commit()


def print_specimen(case, current, printer):
    """ Prints specimen accession labels.

    Args:
        case (ORM): The case that the specimen is part of.
        current (ORM): The current specimen being accessioned.
        printer (str): Printer being used

    Returns:

    """

    # Need label type to filter template
    # Need object being printed to get information
    # Fill label template fields with relevant information

    # Assign label parameters based on specimen
    label_name = case.last_name + ', ' + case.first_name
    label_case = case.case_number
    label_accession = current.accession_number
    label_type = '[' + current.type.code + ']'
    label_barcode = f'Specimens: {current.id}'

    # Get path to label template
    label_path = os.path.join(current_app.root_path, 'static/label_templates', 'specimen.label')

    # Assign name of printer
    my_printer = 'DYMO LabelWriter 450'

    # Initialize COM library
    pythoncom.CoInitialize()

    # Get printer object
    printer_com = Dispatch('Dymo.DymoAddIn')

    # Select relevant printer
    printer_com.SelectPrinter(my_printer)

    # Load label template from label path
    printer_com.Open(label_path)

    # Assign the label object
    printer_label = Dispatch('Dymo.DymoLabels')

    # Set relevant fields of label
    printer_label.SetField('Barcode', label_barcode)
    printer_label.SetField('Text', label_accession)
    printer_label.SetField('Text_1', label_type)
    printer_label.SetField('Text_2', label_name)
    printer_label.SetField('Text_3', label_case)

    # Print one label
    printer_com.StartPrintJob()
    printer_com.Print(1, False)

    # End printing
    printer_com.EndPrintJob()

    # Uninitialize
    pythoncom.CoUninitialize()


def add_specimen_container(container_type, form, submission_route_type, location_type, submission_route, discipline,
                           **kwargs):
    """
    Used to automatically add a new container. This function fills out 'container_form' and 'submits' form to trigger
    add_item.
    Args:
        container_type (int): ID of container type
        form (form object): The form used to trigger this function
        submission_route_type (str): By Hand or By Location
        location_type (str): Name of location type table (e.g., Cooled Storage)
        submission_route (int): ID of the actual item in the location type table
        discipline (str): Discipline associated with this container
        **kwargs:

    Returns:
        Adds new container and returns new container id
    """
    # Create container
    container_form = get_container_choices(ContainerAdd())

    # Assign case id based on choice
    container_form.case_id.data = form.case_id.data

    # Assign container discipline
    container_form.discipline.data = discipline

    # No container default
    container_form.container_type_id.data = container_type

    # The current users division assigned in personnel
    container_form.division_id.data = current_user.personnel.division_id

    # Current user as submitter
    container_form.submitted_by.data = current_user.personnel_id

    # Set to 0 and auto-increment with specimens submitted
    container_form.n_specimens_submitted.data = 0

    # Default to by location
    container_form.submission_route_type.data = submission_route_type

    # Default to Cooled Storage
    container_form.location_type.data = location_type

    # Default to 08R
    container_form.submission_route.data = submission_route

    # Set submission date and time to datetime now
    container_form.submission_date.data = datetime.now()
    container_form.submission_time.data = datetime.now().strftime('%H%M')

    # Remove validators for specific fields to force validation
    container_form.submission_time.validators = [v for v in container_form.submission_time.validators if
                                                 not isinstance(v, DataRequired)]
    container_form.n_specimens_submitted.validators = [v for v in
                                                       container_form.n_specimens_submitted.validators if
                                                       not isinstance(v, DataRequired)]
    # Set submit to True
    container_form.submit.data = True

    if container_form.is_submitted():
        # if a new container is added to the case, set the case to pending.
        kwargs.update(containers_process(container_form, 'Add'))
        add_item(container_form, Containers, 'Container', 'Containers', 'containers', True, 'accession_number',
                 **kwargs)
        return Containers.query.order_by(Containers.id.desc()).first().id


def process_audit(form, from_autopsy=False, histo_sub=False):
    # Initialize transfer
    transfer = None

    # Get specimen container
    container = Containers.query.get(form.container_id.data)

    # Check submission route and handle destination accordingly

    if histo_sub:
        personnel = Personnel.query.get(form.collected_by.data)
        collector = Users.query.filter_by(personnel_id=personnel.id).first().initials
        collection_time = datetime.strptime(form.collection_time.data, '%H%M').time()
        collection_datetime = datetime.combine(form.collection_date.data, collection_time)
        destinations = [collector, current_user.initials, form.custody.data]
        o_times = [collection_datetime, datetime.now(), datetime.now()]
    else:
        if container.submission_route_type == 'By Hand':
            destination = container.submitter.first_name + ' ' + container.submitter.last_name
        elif container.submission_route_type == 'By Location':
            # table = location_dict[container.location_type]['table']
            # name = location_dict[container.location_type]['alias']
            # reference = table.query.get(container.submission_route)
            # destination = getattr(reference, name)
            destination = container.submission_route
        elif container.submission_route_type == 'By Transfer':
            destination = container.submission_route
            transfer = container.transfer.initials
        else:
            destination = 'Initial entry placeholder'

        # Get submission time
        if container.submission_time:
            submission_time = container.submission_time  # Cont. submission time specimen inherits
        else:
            submission_time = datetime.now().strftime('%H:%M')

        submission_date = container.submission_date.date()

        # Handle errors if submission time can't be formatted
        try:
            submission_time = datetime.strptime(container.submission_time, '%H%M').time()
            submission_datetime = datetime.combine(submission_date, submission_time)
            submission_datetime_plus_one = submission_datetime + timedelta(minutes=1)
        except TypeError:
            submission_time = None
            submission_datetime = None
            submission_datetime_plus_one = None

        # most_recent_specimen = Specimens.query.order_by(Specimens.id.desc()).first().id
        # specimen_id = most_recent_specimen + 1

        # Check if "By Transfer" selected for container submission_route_type
        if from_autopsy:
            destinations = [current_user.initials, form.custody.data]
            o_times = [form.start_time.data, datetime.now()]
        elif transfer:
            # Set specimen audit data
            destinations = [container.submitter.full_name, transfer, destination, current_user.initials,
                            form.custody.data]
            o_times = [submission_datetime, submission_datetime, submission_datetime_plus_one, form.start_time.data,
                       datetime.now()]
            print(f'TRANSFER DESTINATIONS: {destinations}')
        elif container.submission_route_type == 'By Location':
            destinations = [container.submitter.full_name, destination, current_user.initials, form.custody.data]
            o_times = [submission_datetime, submission_datetime, form.start_time.data, datetime.now()]
            print(f'DESTINATIONS: {destinations}')
        else:
            # Set specimen audit data
            destinations = [container.submitter.full_name, current_user.initials, form.custody.data]
            o_times = [submission_datetime, form.start_time.data, datetime.now()]

    # Get the specimen_id for the specimen to be created which will be used to
    # create specimen audit entries
    specimen_id = Specimens.query.order_by(Specimens.id.desc()).first().id

    # Make each specimen audit entry
    for dest, o_time in zip(destinations, o_times):
        add_specimen_audit(destination=dest,
                           reason=f'{current_user.initials} submitted specimen add form',
                           o_time=o_time,
                           specimen_id=specimen_id,
                           status='Out',
                           db_status='Active')
