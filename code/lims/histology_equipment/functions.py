from lims import db
from lims.models import Agencies, Divisions, Statuses, HistologyEquipmentTypes
from lims.locations.functions import location_dict


def get_form_choices(form):

    statuses = [(item.id, item.name) for item in Statuses.query.order_by(Statuses.name.asc())]
    statuses.insert(0, (0, 'Please select a status'))
    form.status_id.choices = statuses

    manufacturers = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name.asc())]
    manufacturers.insert(0, (0, 'Please select a manufacturer'))
    form.manufacturer_id.choices = manufacturers

    vendors = [(item.id, f"{item.name} [{item.agency.name}]" if item.name == "Service" else item.name) for item in
               Divisions.query.filter_by(service_provider='Yes')]
    vendors.insert(0, (0, 'Please select a service provider'))
    form.vendor_id.choices = vendors

    choices = [(k, v['option']) for k, v in location_dict.items()]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices

    form.type_id.choices = [(item.id, item.name) for item in HistologyEquipmentTypes.query.all()]
    form.type_id.choices.insert(0, (0, 'Please select a type'))

    return form
