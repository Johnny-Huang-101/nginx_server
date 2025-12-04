import string
from flask import jsonify
from sqlalchemy import or_
from lims.models import *
from lims.locations.functions import location_dict
from lims.evidence_comments.functions import sort_comments
from wtforms.validators import DataRequired, Optional

def get_form_choices(form, case_id=None, division_id=None, submission_route_type=None,
                     location_type=None, item=None, submission_route=None):
    if case_id:
        case = Cases.query.get(case_id)
        form.case_id.choices = [(case.id, case.case_number)]

        if current_user.permissions in ['Admin', 'Owner']:
            divisions = [(item.id, f"{item.agency.name} - {item.name}") for item in
                         Divisions.query.join(Agencies).order_by(Agencies.name, Divisions.name)]
        else:
            divisions = [(item.id, item.name) for item in
                         Divisions.query.filter_by(agency_id=case.agency.id).order_by(Divisions.name.asc())]
            # TODO consider replacing agency_id filter with client="Yes"

        divisions.insert(0, (0, 'Please select a submitting division'))
        form.division_id.choices = divisions

        if division_id:
            personnel = [(item.id, f"{item.last_name}, {item.first_name}") for item in
                         Personnel.query.filter_by(division_id=division_id, status_id = '1')]
        else:
            personnel = [(0, "No division selected")]
        form.submitted_by.choices = personnel

    else:
        cases = [(item.id, item.case_number) for item in Cases.query.order_by(Cases.create_date.desc())]
        cases.insert(0, (0, 'Please select a case'))
        form.case_id.choices = cases

        # divisions = [(item.id, item.name) for item in Divisions.query.all()]
        # divisions.insert(0, (0, 'Please select a submitting agency division'))
        # form.division_id.choices = divisions

        form.division_id.choices = [(0, 'No case selected')]
        personnel = [(0, "No case selected")]
        form.submitted_by.choices = personnel

    # observers = Personnel.query.filter(Personnel.agency_id == 1, Personnel.division_id == 1, Personnel.status_id == '1').all()
    observers = [(item.id, f"{item.last_name}, {item.first_name}") for item in
                         Personnel.query.filter_by(agency_id = 1, division_id = 1, status_id = '1')]
    # observed_by_choices = [('', 'Please select observer')] + [(o.id, f"{o.last_name}, {o.first_name}") for o in observers]
    observers.insert(0, (0, "No observer selected"))
    observers.remove((23, "Karwowski, Evan"))
    observers.remove((33, "Devincenzi, Tyler"))
    form.observed_by.choices = observers

    location_types = [(k, k) for k, v in location_dict.items()]  # if key != 'Person']
    location_types.insert(0, ("", '---'))
    form.location_type.choices = location_types

    if submission_route_type == 'By Location':
        form.location_type.render_kw = {'disabled': False}
        form.submission_route.render_kw = {'disabled': False}
    print(location_type)

    # TODO replace this block with inclusion of locations.js in containers/form.html
    if location_type:
        table = location_dict[location_type]['table']
        alias = location_dict[location_type]['alias']
        locations = [
            (f"{getattr(item, alias[0])} - {getattr(item, alias[1])}",
             f"{getattr(item, alias[0])} - {getattr(item, alias[1])}")
            if isinstance(alias, list) and len(alias) == 2 else (getattr(item, alias), getattr(item, alias))
            for item in table.query
        ]
        locations.insert(0, ("", 'Please select a location'))
    else:
        locations = [("", "No location type selected")]

    form.submission_route.choices = locations

    container_types = [(item.id, item.name) for item in ContainerTypes.query.all()]
    container_types.insert(0, (0, 'Please select a container type'))
    form.container_type_id.choices = container_types

    form.discipline.choices = discipline_choices

    # try:
    #     form.discipline.choices.remove(('Histology', 'Histology'))
    # except ValueError:
    #     print('Histology not in choices')

    # If current user is not FLD and not Medical Division, autofill form fields
    if 'INV' in current_user.permissions:
        exclude = {'External','Histology', 'Biochemistry'} #Exclude certain disciplines if user is INV
        form.discipline.choices = [
        choice for choice in discipline_choices if choice[0] not in exclude
        ]
        if current_user.personnel.division_id != Divisions.query.filter_by(abbreviation='FLD').first().id and \
                current_user.personnel.division_id != Divisions.query.filter_by(name='Medical Division').first().id:
            form.division_id.data = current_user.personnel.division_id
            form.submitted_by.choices = [(item.id, f"{item.last_name}, {item.first_name}") for
                                         item in Personnel.query.filter_by(division_id=form.division_id.data)]
            form.submitted_by.data = current_user.personnel_id
            form.submission_date.data = datetime.now()
            form.submission_time.data = datetime.now().strftime('%H%M')
            form.location_type.render_kw = {'disable': False}
            form.submission_route.render_kw = {'disable': False}
            form.submission_route_type.choices = [choice for choice in form.submission_route_type.choices if
                                                  choice != ('By Transfer', 'By Transfer')]
            # form.submission_route_type.data = 'By Location'
            # form.location_type.data = 'Evidence Lockers'
            # form.submission_route.choices = [(item.equipment_id, item.equipment_id) for item in
            #                                  EvidenceLockers.query.filter(or_(EvidenceLockers.occupied != True,
            #                                                                   EvidenceLockers.occupied == None))]

    form.transfer_by.choices = [(user.id, user.initials) for user in Users.query.filter(or_(Users.job_class == '2403',
                                                                                            Users.job_class == '2456',
                                                                                            ))]
    form.transfer_by.choices.insert(0, (0, '--'))


    # if the item's submission date was in the future (i.e., after the create_date, set the future_submission_date
    # checkbox. This is only for HP cases. For PM cases, the submission time can be after the container created time.
    # so the future_submission_date would always be checked.
    if item:
        if item.case.type.code != 'PM' and item.submission_time:
            # Convert the submission_time into a time object
            submission_time = datetime.strptime(item.submission_time, '%H%M').time()
            # Combine the submission date and submission time and compare to item.create_date.
            # if it after the create_date, set the checkbox to checked.
            if datetime.combine(item.submission_date, submission_time) > item.create_date:
                form.future_submission_date.render_kw = {'checked': True}

    if submission_route:
        form.submission_route.data = submission_route
        #
        # table = tables.get(location_type)
        # try:
        #     form.submission_route.data = table.query.get(int(submission_route)).equipment_id
        # except ValueError:
        #     form.submission_route.data = submission_route
        
    #For all receipt of  Drug containers, an observer must be present with the reviewer
    is_fld = (current_user.permissions == 'FLD')


    if is_fld and form.discipline.data =='Drug':
            form.observed_by.validators = [
                DataRequired(message="Please make a selection for the 'Observed By' field.")
            ]
    else:
        form.observed_by.validators = [Optional()]

    print(f'ROUTE DATA: {form.submission_route.data}')
    print(f'CHOICES: {form.submission_route.choices}')

    return form


def process_form(form, event=None, accession_number=None):
    kwargs = {}
    case = Cases.query.get(form.case_id.data)
    kwargs['case_number'] = case.case_number
    if event == 'Add':
        if not case.n_containers:
            case.n_containers = 1
        else:
            case.n_containers += 1

        # Get the id of the container which will be created
        # This will be to pass into the specimen.add function to pre-populate the add form
        kwargs['container_id'] = Containers.get_next_id()

        if not accession_number:
            print(f"GENERATE ACCESSION NUMBER")
            kwargs['accession_number'] = generate_accession_number()
        else:
            print(f"ACCESSION NUMBER ALREADY EXISTS")
            kwargs['accession_number'] = accession_number
        kwargs['n_specimens'] = 0
        if not form.n_specimens_submitted.data:
            kwargs['n_specimens_submitted'] = 0
        # db.session.commit()

    # kwargs['submission_time'] = form.submission_time.data
    # kwargs['submission_date'] = form.submission_date.data

    if form.submission_route.data == 0:
        kwargs['submission_route'] = None

    kwargs['evidence_comments'] = "\n".join([x.rstrip() for x in sort_comments(form.evidence_comments.data).split("\n")])

    return kwargs


def generate_accession_number():

    alphabet = list(string.ascii_uppercase)
    settings = CurrentSystemDisplay.query.first()

    accession_letter = settings.accession_letter
    accession_counter = settings.accession_counter

    accession_number = f"{accession_letter}{str(accession_counter).rjust(5, '0')}"

    if accession_counter == 99999:
        letter = alphabet[alphabet.index(accession_letter) + 1]
        accession_counter = 1
        settings.accession_letter = letter
    else:
        accession_counter += 1

    settings.accession_counter = accession_counter

    db.session.commit()

    return accession_number


def get_division_choices(case_id):
    choices = []

    if case_id:
        case = Cases.query.get_or_404(case_id)
        agency = case.agency.id
        if current_user.permissions in ['Admin', 'Owner']:
            divisions = Divisions.query.join(Agencies).order_by(Agencies.name, Divisions.name)
        else:
            divisions = Divisions.query.filter_by(agency_id=agency).order_by(Divisions.name)
        if divisions.count():
            choices.append({'id': 0, 'name': 'Please select a division'})
            for item in divisions:
                choice = {}
                choice['id'] = item.id
                if current_user.permissions in ['Admin', 'Owner']:
                    choice['name'] = f"{item.agency.name} - {item.name}"
                else:
                    choice['name'] = item.name
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This agency has no divisions'})
    else:
        choices.append({'id': 0, 'name': 'No case selected'})

    print(choices)
    return jsonify({'choices': choices})


def get_personnel_choices(division_id):
    personnel = Personnel.query.filter_by(division_id=division_id, status_id = '1').order_by(Personnel.last_name.asc()).all()
    choices = []
    if len(personnel) != 0:
        choices.append({'id': 0, 'name':'Please select a submitter'})
        for item in personnel:
            choice = {}
            choice['id'] = item.id
            choice['name'] = f"{item.last_name}, {item.first_name}"
            choices.append(choice)
    else:
        choices.append({'id': 0, 'name': 'This agency has no submitters'})

    return jsonify({'choices': choices})



# def get_location_choices(location_type):
#     """
#
#     Args:
#         location_type (str): name of location table (e.g., Cooled Storage)
#
#     Returns:
#         choices (list): an array of dictionaries containing choice id and choice name
#     """
#
#     # Get relevant table
#     table = tables.get(location_type)
#
#     # Initialize choices array
#     choices = []
#
#     if table:
#         # Get all items in relevant table
#         items = table.query
#         if items.count() != 0:
#             # Add initial choice
#             choices.append({'id': " ", 'name': f'Please select a {location_type.lower()}'})
#             for item in items:
#                 # Clear choice
#                 choice = {}
#                 # Clear name
#                 name = None
#                 # Get relevant name column dependant on table
#                 if not hasattr(item, 'status_id'):
#                     if hasattr(item, 'status'):
#                         if item.status == 'Active':
#                             name = getattr(item, aliases[location_type])
#                             id = item.id
#                 elif hasattr(item, 'status_id'):
#                     if getattr(item, 'status_id') == 1:
#                         name = getattr(item, aliases[location_type])
#                         id = item.id
#                 else:
#                     name = getattr(item, aliases[location_type])
#                     id = item.id
#
#                 # Add choice to choices
#                 if name:
#                     choice['id'] = id
#                     choice['name'] = name
#                     choices.append(choice)
#         else:
#             choices.append({'id': " ", 'name': 'This location type has no items'})
#     else:
#         choices.append({'id': " ", 'name': 'No location type selected'})
#
#     return jsonify({'choices': choices})