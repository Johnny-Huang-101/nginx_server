from lims import db
from lims.models import Divisions, Statuses, InstrumentTypes, Agencies, Hubs
from lims.locations.functions import location_dict


def get_form_choices(form):

    statuses = [(item.id, item.name) for item in Statuses.query.order_by(Statuses.name.asc())]
    statuses.insert(0, (0, 'Please select a status'))
    form.status_id.choices = statuses

    vendors = [(item.id, f"{item.name} [{item.agency.name}]" if item.name == "Service" else item.name) for item in
               Divisions.query.filter_by(service_provider='Yes')]
    vendors.insert(0, (0, 'Please select a service provider'))
    form.vendor_id.choices = vendors

    choices = [(k, v['option']) for k, v in location_dict.items()]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices

    hubs = [(item.id, item.equipment_id) for item in Hubs.query.order_by(Hubs.equipment_id.asc())]
    hubs.insert(0, (0, 'Please select a hub, if applicable'))
    form.hub_id.choices = hubs

    return form
