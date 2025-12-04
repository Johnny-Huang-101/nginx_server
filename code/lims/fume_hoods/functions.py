from lims import db
from lims.models import Agencies, Divisions, Statuses, HoodTypes
from lims.locations.functions import models_iter, location_dict

def get_form_choices(form):

    statuses = [(item.id, item.name) for item in Statuses.query.order_by(Statuses.name.asc())]
    statuses.insert(0, (0, 'Please select a status'))
    form.status_id.choices = statuses

    manufacturers = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name.asc())]
    manufacturers.insert(0, (0, 'Please select a manufacturer'))
    form.manufacturer_id.choices = manufacturers

    vendors = [(item.id, f"{item.name} [{item.agency.name}]" if item.name == "Service" else item.name) for item in Divisions.query.filter_by(service_provider='Yes')]
    vendors.insert(0, (0, 'Please select a service provider'))
    form.vendor_id.choices = vendors

    choices = [
        (k, v['option'])
        for k, v in location_dict.items()
        if v['table'] in models_iter
           and hasattr(v['table'], 'resource_level')
           and getattr(v['table'], 'resource_level') == 'primary'
    ]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices

    form.hood_type.choices = [(item.id, item.name) for item in HoodTypes.query.all()]
    form.hood_type.choices.insert(0, (0, 'Please select a type'))

    return form
