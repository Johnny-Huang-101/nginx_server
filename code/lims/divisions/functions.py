from lims.models import *

def get_form_choices(form):
    """
    Get the choices for:
        - agency_id - Agencies
        - state_id - US States

    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------
    form (FLaskForm)

    """

    # Agencies
    agencies = [(agency.id, agency.name) for agency in Agencies.query.filter_by(db_status='Active').order_by(Agencies.name.asc())]
    agencies.insert(0, (0, 'Please select an agency'))
    form.agency_id.choices = agencies

    # US States
    states = [(item.id, f"{item.name} ({item.abbreviation})") for item in UnitedStates.query]
    states.insert(0, (0, '---'))
    form.state_id.choices = states

    return form


def process_form(form):
    """

    Generate the division's full_address by concatenating the street_number,
    street_address, city, state's abbreviation and zipcode data.

    full_address = <street_number> <street_address>, <city> <state_abbreviation> <zipcode>

    Parameters
    ----------
    form

    Returns
    -------
    kwargs
    """

    # If state is selected, get the state's abbreviation
    state = None
    if form.state_id.data:
        state = UnitedStates.query.get(form.state_id.data).abbreviation

    # join the street number and street address with a space and end with a comma
    # if both street_number and street_address not provided, set as None (i.e. it will be ignored).
    address = [x for x in [form.street_number.data, form.street_address.data] if x]
    if len(address):
        address = " ".join(address) +","
    else:
        address = None

    # Join all of the address compounds with a space
    address_components = [
        address,
        form.city.data,
        state,
        form.zipcode.data,
    ]

    address_components = [x for x in address_components if x]
    full_address = " ".join(address_components)

    kwargs = {'full_address': full_address}

    return kwargs
