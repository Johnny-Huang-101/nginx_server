from lims.models import CaseTypes, Agencies, Divisions


def get_form_choices(form, agency_id=None):

    # Case Types
    case_types = [(item.id, item.name) for item in CaseTypes.query.order_by(CaseTypes.name)]
    case_types.insert(0, (0, 'Please select a case type'))
    form.case_type_id.choices = case_types

    # Agencies
    agencies = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name)]
    agencies.insert(0, (0, 'Please select an agency'))
    form.agency_id.choices = agencies

    # Division
    if not agency_id:
        agency_id = form.agency_id.data

    if agency_id:
        divisions = [(item.id, item.name) for item in Divisions.query.filter_by(agency_id=agency_id)]
        divisions.insert(0, (0, 'Please select a division'))
    else:
        divisions = [(0, 'No agency selected')]

    form.division_id.choices = divisions


    return form