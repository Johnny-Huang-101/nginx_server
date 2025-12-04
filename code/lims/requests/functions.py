from lims.models import *
from sqlalchemy import case


def get_form_choices(form, agency_id=None, division_id=None, dest_agency_id=None, dest_division_id=None):

    # case_id
    cases = [
    (str(case.id), case.case_number)
    for case in Cases.query
        .filter(Cases.create_date >= datetime(2025, 1, 1))
        .order_by(case((Cases.case_type == 7, 0), else_=1), Cases.case_type.asc(),Cases.id.desc()).all()]
    form.case_id.choices = cases
    
    if form.no_case.data:
        form.case_id.render_kw = {'disabled': True}
    # request_type_id
    request_types = [(request_type.id, request_type.name) for request_type in RequestTypes.query.all()]
    request_types.insert(0, (0, 'Please select a request type'))
    form.request_type_id.choices = request_types
    # requesting_agency
    agencies = [(agency.id, agency.name) for agency in Agencies.query.filter_by(db_status='Active')]
    agencies.insert(0, (0, 'Please select an agency'))
    form.requesting_agency.choices = agencies
    # requesting_division

    if form.requesting_agency.data:
        agency_id = form.requesting_agency.data

    if agency_id:
        divisions = [(division.id, division.name) for division in Divisions.query.filter_by(agency_id=agency_id)]
        divisions.insert(0, (0, 'Please select a division'))
    else:
        divisions = [(0, '---')]

    form.requesting_division.choices = divisions
    # requesting_personnel
    if form.requesting_division.data:
        division_id = form.requesting_division.data

    print(division_id)

    if division_id:
        personnel = [(personnel.id, personnel.full_name) for personnel in Personnel.query.filter_by(division_id=division_id, status_id='1')]
        personnel.insert(0, (0, 'Please select a personnel'))
    else:
        personnel = [(0, '---')]

    form.requesting_personnel.choices = personnel

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
    form.destination_agency.choices = agencies  # Reuse agency choices
    if form.destination_agency.data:
        dest_agency_id = form.destination_agency.data

    # destination_division
    if dest_agency_id:
        dest_divisions = [(division.id, division.name) for division in
                          Divisions.query.filter_by(agency_id=dest_agency_id)]
        dest_divisions.insert(0, (0, 'Please select a division'))
    else:
        dest_divisions = [(0, '---')]
    form.destination_division.choices = dest_divisions

    # destination_personnel
    if form.destination_division.data:
        dest_division_id = form.destination_division.data

    # due_date
    # specimens -- multi select field

    return form

