from flask import flash
from lims.models import *


def get_form_choices(form, agency_id=None):
    """
   Get the choices for:
        - agency_id - Agencies
        - division_id - Divisions

    Parameters
    ----------
    form (FlaskForm)
    agency_id (int): None
        pre-filter divisions list on form render if agency_id is not None.

    Returns
    -------
    form (FLaskForm)
    """

    # Agencies
    agencies = [(agency.id, agency.name) for agency in
                Agencies.query.filter_by(db_status='Active').order_by(Agencies.name)]
    agencies.insert(0, (0, 'Please select an agency'))
    form.agency_id.choices = agencies

    #Statuses
    statuses = [(item.id, item.name) for item in Statuses.query.order_by(Statuses.name.asc())]
    statuses.insert(0, (0, 'Please select a status'))
    form.status_id.choices = statuses

    # Get divisions for the selected agency
    if form.agency_id.data:
        agency_id = form.agency_id.data

    if agency_id:
        divisions = [(division.id, division.name) for division in
                     Divisions.query.filter_by(agency_id=agency_id).order_by(Divisions.name)]
        divisions.insert(0, (0, '---'))
    else:
        divisions = [(0, '---')]

    form.division_id.choices = divisions

    return form



def process_form(form):
    """

    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------
    kwargs (dict)
    """
    if form.middle_name.data != "" and form.middle_name.data is not None:
        kwargs = {'full_name': " ".join([form.first_name.data, form.middle_name.data, form.last_name.data])}
    else:
        kwargs = {'full_name': " ".join([form.first_name.data, form.last_name.data])}
    if form.titles.data:
        kwargs['full_name'] += f", {form.titles.data}"

    return kwargs

def check_duplicate_personnel (form):
    new_first  = (form.first_name.data or "").strip()
    new_last   = (form.last_name.data or "").strip()
    new_agency = form.agency_id.data 
    new_divsion = form.division_id.data

    existing_personnel =  Personnel.query.filter(Personnel.first_name == new_first, Personnel.last_name == new_last, Personnel.agency_id == new_agency, Personnel.division_id == new_divsion).first()

    if existing_personnel:
        flash("A personnel record with this name already exists.", "warning")
        return True
    return False