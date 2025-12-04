from lims import db
from lims.models import Agencies, Statuses, Divisions, CooledStorageTypes
from lims.locations.functions import location_dict, models_iter


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

    choices = [
        (k, v['option'])
        for k, v in location_dict.items()
        if v['table'] in models_iter
           and hasattr(v['table'], 'resource_level')
           and getattr(v['table'], 'resource_level') == 'primary'
    ]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices

    types = [(item.id, item.name) for item in CooledStorageTypes.query.order_by(CooledStorageTypes.name.asc())]
    types.insert(0, (0, 'Please select a type'))
    form.type_id.choices = types

    return form

