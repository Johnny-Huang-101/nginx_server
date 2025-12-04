from lims import db
from lims.models import Divisions, Statuses, InstrumentTypes, Agencies
from lims.locations.functions import location_dict


def get_form_choices(form):

    choices = [(k, v['option']) for k, v in location_dict.items()]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices
    form.status_id.choices = [(status.id, status.name) for status in Statuses.query.all()]

    agency_id = Agencies.query.filter_by(abbreviation='SFOCME').first().id

    form.division_id.choices = [(item.id, item.name) for item in Divisions.query.filter_by(agency_id=agency_id)]
    form.division_id.choices.insert(0, (0, 'Please select a division'))

    return form
