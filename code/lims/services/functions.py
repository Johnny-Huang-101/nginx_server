from lims import db
from lims.models import *

def get_form_choices(form, item_id=None, equipment_type=None, division_id=None):

    if form.equipment_type.data:
        equipment_type = form.equipment_type.data

    if equipment_type:
        table = module_definitions[equipment_type][0]
        name = module_definitions[equipment_type][2]
        equipment_types = [(equipment_type, equipment_type)]
        equipment_ids = [(item.id, getattr(item, name)) for item in table.query]
        equipment_ids.insert(0, (0, 'Please select an equipment ID'))

    else:
        equipment_types = []
        for cls in db.Model.__subclasses__():
            if hasattr(cls, '__itemname__'):
                equipment_types.append(cls.__itemname__)
        equipment_types = [(x, x) for x in sorted(equipment_types)]
        equipment_types.insert(0, (0, 'Please select an equipment type'))
        equipment_ids = [(0, 'No equipment type selected')]

    form.equipment_type.choices = equipment_types
    form.equipment_id.choices = equipment_ids
    types = [(item.name, item.name) for item in ServiceTypes.query]
    form.service_types.choices = types

    vendor_divisions = [(item.id, f"{item.name} [{item.agency.name}]" if item.name == "Service" else item.name) for item in
               Divisions.query.filter_by(service_provider='Yes')]
    vendor_divisions.insert(0, (0, 'Please select a service provider'))
    form.vendor_division.choices = vendor_divisions

    if vendor_divisions:
        vendors = [(item.id, item.full_name) for item in Personnel.query.filter_by(division_id=division_id, status_id='1')]
        vendors.insert(0, (0, 'Please select a vendor'))
    else:
        vendors = [(0, 'No agency selected')]
    form.vendor_id.choices = vendors

    if item_id:
        item = Services.query.get(item_id)
        form.vendor_division.data = item.vendor.division_id
    return form

