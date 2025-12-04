from flask import jsonify

from lims.models import *
from lims.view_templates.views import *
from lims.locations.forms import *
from sqlalchemy import and_, or_


# Set item global variables
item_type = 'Location'
item_name = 'Locations'
table = Locations
table_name = 'locations'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level

# Create array of all secondary location choices
# secondary_locations = [('cabinets', 'Cabinets'), ('benches', 'Benches'), ('compactors', 'Compactors'),
#                        ('fume_hoods', 'Fume Hoods'), ('cooled_storage', 'Refrigerators and Freezers'),
#                        ('evidence_lockers', 'Evidence Lockers')]
# # Assign primary location variable
# primary_location = 'rooms'
# Used to find table for querying
models_iter = db.Model.__subclasses__()

## used for options in location choices, lookup of locations in various resources
## also, used in add/update and functions of Locations, Cases, Containers, Specimens
location_dict = {
    'Benches': {'option': 'Benches', 'table': Benches, 'alias': 'equipment_id'},
    'Cabinets': {'option': 'Cabinets', 'table': Cabinets, 'alias': 'equipment_id'},
    'Storage': {'option': 'Storage', 'table': Compactors, 'alias': 'equipment_id'},
    'Evidence Lockers': {'option': 'Evidence Lockers', 'table': EvidenceLockers, 'alias': 'equipment_id'},
    'Evidence Storage': {'option': 'Evidence Storage', 'table': EvidenceStorage, 'alias': 'equipment_id'},
    'Hoods': {'option': 'Hoods', 'table': FumeHoods, 'alias': 'equipment_id'},
    'Cooled Storage': {'option': 'Cooled Storage', 'table': CooledStorage, 'alias': 'equipment_id'},
    'Rooms': {'option': 'Rooms', 'table': Rooms, 'alias': ['room_number', 'name']},
    'Person': {'option': 'Person', 'table': Users, 'alias': 'initials'},
    'Agencies': {'option': 'Agencies', 'table': Agencies, 'alias': 'name'}
}


# tables = {
#     {k: v['table'] for k, v in location_dict.items()}
# }
#
# aliases = {
#     {k: v['aliases'] for k, v in location_dict.items()}
# }


def set_location(item_table, item_id, location_table, location_id):

    form = Add()

    # Set form data
    # if location_table in ['Person']:
    #     form.location_table.data = 'Users'
    # elif location_table in ['Storage']:
    #     form.location_table.data = 'Compactors'
    # else:
    #     form.location_table.data = location_table
    form.location_table.data = location_table

    form.item_table.data = item_table
    form.submit.data = True

    # Initialize relevant variables
    updated_id = None
    item_table_object = None
    location_table_object = None

    # Search db models for item_table and location_table
    for cls in db.Model.__subclasses__():
        if cls.__tablename__ == item_table.lower().replace(' ', '_'):
            item_table_object = cls
    #     elif cls.__tablename__ == location_table.lower().replace(' ', '_'):
    #         location_table_object = cls
    # item_table_object = tables[item_table]
    location_table_object = location_dict[location_table]['table']
    form.location_id.data = int(location_id)

    # TODO DELETE Check if item_id contains alpha characters
    # if any(char.isalpha() for char in str(location_id)):
    #     print('alpha-char in location_id')
    #     if location_table in ['Rooms']:
    #         form.location_id.data = int(location_table_object.query.filter_by(name=location_id.split('- ')[1])
    #                                     .first().id)
    #     else:
    #         # Get relevant id and set form data
    #         form.location_id.data = int(location_table_object.query.filter_by(equipment_id=location_id).first().id)
    # else:
    #     # Set form data with id
    #     form.location_id.data = int(location_id)

    if item_id is None:
        # Set item id for add function
        try:
            updated_id = item_table_object.query.order_by(item_table_object.id.desc()).first().id
        except AttributeError:
            updated_id = 0
        form.item_id.data = updated_id + 1
        add_item(form, table, item_type, item_name, table_name, requires_approval, name, admin_only=False)
    else:
        form.item_id.data = item_id
        try:
            # Try to get location entry id and update locations
            current = table.query.filter(and_(Locations.item_table == item_table,
                                                 Locations.item_id == item_id)).first()
            
            # Check if location had been removed and set to active
            if current.db_status == 'Removed':
                current.db_status = 'Active'
                db.session.commit()

            update_item(form, current.id, table, item_type, item_name, table_name, requires_approval, name,
                        admin_only=False, locking=False)
        except AttributeError:
            # Create new locations table entry if entry does not already exist
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, admin_only=False)

    updated_id = int(form.item_id.data)
    # Set location_type and location column for item (resource)
    assigned_item_table = item_table_object

    # If assigned_item_table exists, update item location_type and location columns
    if assigned_item_table is not None:
        if updated_id is None:
            item = assigned_item_table.query.get(item_id)
        else:
            item = assigned_item_table.query.get(updated_id)
            print(f'ITEM: {item}')
        try:
            item.location_type = form.location_table.data
            print(f'ITEM {item}')
            item.location = form.location_id.data
        except AttributeError:
            pass

        db.session.commit()


def get_location_choices(location_type, store_as='id', return_var=False):
    """

    Args:
        location_type (str): name of location table (e.g., Cooled Storage)
        store_as (str): id
            value stored in the database. Default is store the item's id, pass in
            'alias' to store the item's alias.
        module (str): None
            Used to control querying of EvidenceLockers. In the 'specimens' module, we
            don't want to restrict the evidence lockers.

    Returns:
        choices (list): an array of dictionaries containing choice id (or name) and choice name
    """

    print(f'LOCATION TYPE: {location_type}')

    table = location_dict[location_type]['table']
    print(f'Table: {table}')
    alias = location_dict[location_type]['alias']
    print(f'Alias: {alias}')

    choices = []
    # Check if a table has been passed in
    if table:

        # Sort items by their alias. Many are sorted by equipment ID. Also handles if the alias
        # is a list like with rooms
        if isinstance(alias, list):
            order_by = text(alias[0])
        else:
            order_by = text(alias)

        # If table is evidence lockers, get unoccupied evidence lockers or lockers currently used by the user.
        if table == EvidenceLockers:
            # submitter_evidence_lockers = [container.submission_route for container in
            #                               Containers.query.filter_by(pending_submitter=current_user.initials,
            #                                                          location_type='Evidence Lockers')]
            # items = table.query.filter(or_(or_(EvidenceLockers.occupied != True, EvidenceLockers.occupied == None),
            #                                EvidenceLockers.equipment_id.in_(submitter_evidence_lockers)))

            items = table.query.filter(or_(EvidenceLockers.occupied != True,
                                           EvidenceLockers.occupied == None)).order_by(order_by)

        else:
            items = table.query.order_by(order_by)
        if items.count() != 0:
            # Add initial choice
            choices.append({'id': "", 'name': f'Please select a location'})
            for item in items:
                # Clear choice and name
                choice = {}

                if isinstance(alias, list):
                    name = " - ".join([getattr(item, x) for x in alias])
                else:
                    name = getattr(item, alias)

                # Get relevant name column based on attribute present
                # if not hasattr(item, 'status_id') and hasattr(item, 'status'):
                #     if item.status == 'Active':
                #         name = getattr(item, alias)
                # elif hasattr(item, 'status_id'):
                #     if getattr(item, 'status_id') == 1:
                #         name = getattr(item, alias)
                # else:
                #     name = getattr(item, alias)

                # Set id and name for choice and add to choices
                if name:
                    if store_as == 'id':
                        choice['id'] = item.id
                    else:
                        choice['id'] = name
                    choice['name'] = name

                    if not hasattr(item, 'status_id') and hasattr(item, 'status'):
                        if item.status == 'Active':
                            choices.append(choice)
                    elif hasattr(item, 'status_id'):
                        if getattr(item, 'status_id') == 1:
                            choices.append(choice)
                    else:
                        choices.append(choice)

        else:
            choices.append({'id': "", 'name': 'This location type has no items'})
    else:
        choices.append({'id': "", 'name': 'No location type selected'})

    # Determine if default_choice should be id or name and set default_choice
    if location_type == 'Cooled Storage':
        try:
            if current_user.job_class in ['2456', '2403', '2458', '2457']:
                if store_as == 'id':
                    default_choice = CooledStorage.query.filter_by(equipment_id='09R').first().id
                else:
                    default_item = CooledStorage.query.filter_by(equipment_id='09R').first()
                    default_choice = getattr(default_item, alias)

            else:
                if store_as == 'id':
                    default_choice = CooledStorage.query.filter_by(equipment_id='08R').first().id
                else:
                    default_item = CooledStorage.query.filter_by(equipment_id='08R').first()
                    default_choice = getattr(default_item, alias)
        except AttributeError:
            default_choice = ''
    elif location_type == 'Benches':
        try:
            if store_as == 'id':
                default_choice = Benches.query.filter_by(equipment_id='BS60').first().id
            else:
                default_item = Benches.query.filter_by(equipment_id='BS60').first()
                default_choice = getattr(default_item, alias)
        except AttributeError:
            default_choice = ''
    elif location_type == 'Hoods':
        try:
            if current_user.job_class in ['2456', '2403', '2458', '2457']:
                if store_as == 'id':
                    default_choice = FumeHoods.query.filter_by(equipment_id='HF07').first().id
                else:
                    default_item = FumeHoods.query.filter_by(equipment_id='HF07').first()
                    default_choice = getattr(default_item, alias)

            else:
                if store_as == 'id':
                    default_choice = CooledStorage.query.filter_by(equipment_id='08R').first().id
                else:
                    default_item = CooledStorage.query.filter_by(equipment_id='08R').first()
                    default_choice = getattr(default_item, alias)
        except AttributeError:
            default_choice = ''
    elif location_type == 'Benches':
        try:
            if current_user.job_class in ['2456', '2403', '2458', '2457']:
                default_choice = 0
            else:
                default_choice = Benches.query.filter_by(equipment_id='BS60').first().id
        except AttributeError:
            default_choice = ''
    elif location_type == 'Evidence Storage':
        try:
            default_choice = 0
        except AttributeError:
            default_choice = ''
    
    else:
        default_choice = ""

    if return_var:
        return choices, str(default_choice)
    else:
        return jsonify({'choices': choices, 'default_choice': str(default_choice)})


def get_location_display(item_table, item_id):

    location = Locations.query.filter(
        Locations.item_table == item_table,
        Locations.item_id == item_id,
        Locations.db_status == 'Active'
    ).first()

    if location:
        location_id = location.location_id
        location_table = location_dict[location.location_table]['table']
        location_alias = location_dict[location.location_table]['alias']
    else:
        return None

    instance = location_table.query.get(location_id)
    if not instance:
        return None

    if isinstance(location_alias, list):
        return " - ".join(str(getattr(instance, attr, '')) for attr in location_alias)
    else:
        return getattr(instance, location_alias, None)
