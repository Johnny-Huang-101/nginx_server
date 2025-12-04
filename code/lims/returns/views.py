from datetime import datetime, date
from lims.models import *
from lims.cases import *
from lims.personnel.forms import AddFromRequest
from lims.personnel.functions import process_form
from lims.returns.forms import *
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.returns.functions import *
from lims.specimen_audit.views import add_specimen_audit
from lims.locations.functions import location_dict
from lims.locations.functions import get_location_choices
from lims.returns.forms import ReturnedSpecimensForm
from lims.returns.forms import StoredSpecimensForm
from lims.models import Specimens
from lims import db
from lims.personnel.forms import AddFromRequest
from lims.personnel.functions import process_form
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.specimen_audit.views import add_specimen_audit
from lims.locations.functions import get_location_choices
from lims.returns.forms import Add
from lims.locations.functions import location_dict
from lims.returns.forms import LegacySpecimenAdd


# Set item global variables
item_type = 'Returns'
item_name = 'Returns'
table = Returns
table_name = 'returns'
name = 'name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'view'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = Add(request.form)
    form = get_form_choices(form)
    # form = get_form_choices(Add())
    

    if form.is_submitted() and form.validate():
    
        last_returns = Returns.query.order_by(Returns.id.desc()).first()

        # Determine the next ID by incrementing the last ID or setting it to 1 if no requests exist
        if last_returns:
            next_id = last_returns.id + 1
            print(f'next id = {next_id}')
        else:
            next_id = 1

        # Format the ID as a 4-digit number with leading zeros
        formatted_id = f"{next_id:04d}"
        print(f'formatted id - {formatted_id}')

        # Set the name field to include the formatted ID
        form.name.data = f"Return_{formatted_id}"
        form.status.data = 'Incomplete Request'

        #HANDLING LIMS CASES#
        selected_case_ids = form.case_id.data
        # If it's a single integer, wrap it in a list
        if isinstance(selected_case_ids, int):
            selected_case_ids = [selected_case_ids]

        #Turn list into comma separated strings 
        case_id_str = ','.join(str(cid) for cid in selected_case_ids)
        kwargs['case_id'] = case_id_str

        cases = Cases.query.filter(Cases.id.in_(selected_case_ids)).all()
        specimen_ids = []

        for case in cases:
            specimens = Specimens.query.filter_by(case_id=case.id).all()
            specimen_ids.extend([specimen.id for specimen in specimens])
        
        #HANDLING LEGACY CASES#
        if form.legacy_case_number.data:
            kwargs['legacy_case'] = form.legacy_case_number.data.strip()

        if form.notes.data:
            form.notes.data = f"{form.notes.data} ({current_user.initials} {datetime.now().strftime('%m/%d/%Y %H:%M')})"
        
    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, case_id=kwargs.get('case_id', ''),legacy_case=kwargs.get('legacy_case'))
    return _add

@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit

@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)

    item_type = "Return"
    item_name = str(item)  # or item.return_number
    table_name = "returns"
    requires_approval = False
    name = "name" 

    print(f"{item_type}")
    form = get_form_choices(
        Update(),
        # case_id = item.case_id,
        # case_id=kwargs.get('case_id', ''),
        agency_id=item.returning_agency,
        division_id=item.returning_division,
        item=item  #pass the model instance here
    )
    # Make case_id non-editable in update view
    form.case_id.render_kw = {'disabled': True}


    if form.is_submitted():
        item.returning_agency = form.returning_agency.data
        item.returning_division = form.returning_division.data
        item.returning_personnel = form.returning_personnel.data
        item.notes = form.notes.data
        if isinstance(form.return_date.data, date) and not isinstance(form.return_date.data, datetime):
            item.return_date = datetime.combine(form.return_date.data, datetime.min.time())
        else:
            item.return_date = form.return_date.data

        return redirect(url_for('returns.view', item_id=item.id))
                
    return update_item(
        form, item_id, table,
        item_type, item_name, table_name,
        requires_approval, name,
        **kwargs
    )


@blueprint.route(f'/{table_name}/<int:item_id>/remove', methods=['GET', 'POST'])
@login_required
def remove(item_id):
    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove

@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    _approve_remove = approve_remove_item(item_id, table, table_name, item_name, name)

    return _approve_remove

@blueprint.route(f'/{table_name}/<int:item_id>/reject_remove', methods=['GET', 'POST'])
@login_required
def reject_remove(item_id):
    _reject_remove = reject_remove_item(item_id, table, table_name, item_name, name)

    return _reject_remove


@blueprint.route(f'/{table_name}/<int:item_id>/restore', methods=['GET', 'POST'])
@login_required
def restore(item_id):
    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():
    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items


@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    _import = import_items(form, table, table_name, item_name)

    return _import


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():
    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = default_kwargs.copy()

    items = Returns.query.all()  # Replace with your query for the list

    case_ids = set()

    print(len(current_user.permissions))

    # Collect all case IDs from items
    for item in items:
        if item.case_id:
            case_ids.update(map(int, item.case_id.split(',')))  # Convert to integers
            # case_ids.update(int(float(x)) for x in item.case_id.split(','))  # use this for sqlite

    # Fetch the corresponding cases from the database
    cases = Cases.query.filter(Cases.id.in_(case_ids)).all()
    kwargs['case_number_map'] = {case.id: case.case_number for case in cases}

    _view_list = view_items(table, item_name, item_type, table_name, order_by=['ID DESC'], **kwargs)

    return _view_list

"""
view() Route Summary
--------------------
- Fetches a Returns item and initializes forms.
- Parses related case IDs, queries Cases, and formats case numbers.
- Handles Returned Specimens:
    * Populates choices, updates custody/audits, merges IDs, builds display.
- Handles Stored Specimens:
    * Populates choices, updates custody/audits, merges IDs.
- Handles Legacy Specimens:
    * Appends legacy metadata fields and commits.

Future Improvements ( pls refer to bottom of page for ideas on helper functions):
- Extract repeated blocks into helpers (cases, returned, stored, legacy).
- Create utility function for ID parsing/merging and custody updates.
- Consolidate commits (one per form).
"""
@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    
    item = Returns.query.get_or_404(item_id)
    alias = getattr(item, name)
 
    # ===================================================
    # 1. INITIALIZE 
    # ===================================================
    stored_specimens_instance = StoredSpecimensForm()  
    returned_specimens_instance = ReturnedSpecimensForm()
    legacy_specimen_add_form = LegacySpecimenAdd()
    user_initials = current_user.initials




    # =========================================================
    # 2. HANDLE CASES (parse, query, format)
    # NOTE: This whole block can become a helper function later.
    # =========================================================


    case_ids_str = item.case_id  #start with a comma-separated string of IDs, example: "101, 102, 103"
    case_ids = [int(cid.strip()) for cid in case_ids_str.split(',') if cid.strip().isdigit()]  # convert to list of ints 

   
    cases = Cases.query.filter(Cases.id.in_(case_ids)).all() # query the cases
    cases.sort(key=lambda c: case_ids.index(c.id))#preserve order of the original ID list

    # format for display
    case_number_str = ', '.join([
        f"{c.case_number} ({c.division.abbreviation})"
        if c.case_type == 7 and c.division else c.case_number
        for c in cases
    ]) if cases else "N/A"

    # ===================================================
    # 3.NON-LEGACY RETURNED SPECIMENS HANDLING
    # ===================================================
    # Populate specimen choices
    returned_specimens = []
    selected_specimens_str = ""
    specimen_objects = Specimens.query.filter(Specimens.case_id.in_(case_ids)).all()
    returned_specimens_instance.returned_specimens.choices = []

    if specimen_objects:
        returned_specimens_instance.returned_specimens.choices = [
            (
                specimen.id,
                f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]"
            )
            for specimen in specimen_objects
        ]  

    # Form submission handling
    if returned_specimens_instance.is_submitted() and returned_specimens_instance.validate() and 'submit' in request.form:
        # Assign collector and date
        item.collector = current_user.initials
        item.collect_date = datetime.now()
        item.status = 'Pending Return'
        db.session.commit()

        new_specimens = returned_specimens_instance.returned_specimens.data  # e.g., [101, 102, 104]

        #Get existing returned specimens (if any)
        existing_ids = [
            int(i.strip()) for i in item.returned_specimens.split(',')
            if i.strip()
        ] if item.returned_specimens else []

        #Filter new specimens
        truly_new_ids = [i for i in new_specimens if i not in existing_ids]

        #Query full records
        selected_specimens = Specimens.query.filter(Specimens.id.in_(new_specimens)).all()
        selected_specimens.sort(key=lambda s: new_specimens.index(s.id))

        #Save combined list as comma-separated string
        combined_ids = list(set(existing_ids + new_specimens))
        combined_ids.sort()
        accession_str = ','.join(str(sid) for sid in combined_ids)
        item.returned_specimens = accession_str

        #Audit + custody updates
        for i in truly_new_ids:
            add_specimen_audit(
                i,
                current_user.initials,
                f'{current_user.initials} collected for return',
                datetime.now(),
                'OUT'
            )

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = current_user.initials
            specimen_location.custody_type = 'Person'
        db.session.commit()

    # Display returned specimens

    if item.returned_specimens is not None:
        returned_ids = [int(i.strip()) for i in (item.returned_specimens or "").split(',') if i.strip().isdigit()]
        returned_specimens = Specimens.query.filter(Specimens.id.in_(returned_ids)).all() if returned_ids else []

         # Format for display
        selected_specimens_str = '<br>'.join(
            f"{s.case.case_number if s.case else 'No Case'}&emsp;"
            f"{s.accession_number if s.accession_number else 'No Accession'}&emsp;"
            f"{s.type.code if s.type and s.type.code else 'Unknown'}&emsp;"
            f"{s.custody if s.custody else 'Unknown'}"
            for s in returned_specimens if s
        )

    # =========================================================
    # 4. NON-LEGACY STORED SPECIMENS HANDLING
    #NOTE: This whole block can become a helper function later.
    # =========================================================
    returned_ids = [int(i.strip()) for i in (item.returned_specimens or "").split(',') if i.strip().isdigit()]
    stored_ids = [int(i.strip()) for i in item.stored_specimens.split(',') if i.strip()] if item.stored_specimens else []
    returned_specimens = Specimens.query.filter(Specimens.id.in_(returned_ids)).all()
    available_for_storage = [s for s in returned_specimens if s.id not in stored_ids]


    # Set choices for the form
    stored_specimens_instance.stored_specimens.choices = [
        (
            specimen.id,
            f"{specimen.case.case_number}_{specimen.accession_number}[{specimen.type.code if specimen.type else 'Unknown'}]"
        )
        for specimen in available_for_storage
    ]

    tables = {
        'Evidence Storage': EvidenceStorage,
        'Benches': Benches,
        'Cabinets': Cabinets,
        'Storage': Compactors,
        'Evidence Lockers': EvidenceLockers,
        'Hoods': FumeHoods,
        'Person': Users,
        'Cooled Storage': CooledStorage
    }

    stored_specimens_instance.custody_type.choices = [('', '---')] + [(key, key) for key in tables.keys()]
      
     # Form submission handling
    if stored_specimens_instance.is_submitted() and 'submit_stored' in request.form:
        specimens_to_store = stored_specimens_instance.stored_specimens.data  # e.g., [101, 102, 104]
        selected_specimens = Specimens.query.filter(Specimens.id.in_(specimens_to_store)).all()
        selected_specimens.sort(key=lambda s: specimens_to_store.index(s.id))
        item.status ='Finalized'

        # Get previous stored IDs (if any)
        existing_ids = [int(i.strip()) for i in item.stored_specimens.split(',') if i.strip()] if item.stored_specimens else []
        #Combine wit new selections
        new_ids = [s.id for s in selected_specimens]
        combined_ids = list(set(existing_ids + new_ids))  # remove duplicates
        combined_ids.sort()
        # Save as comma-separated string
        item.stored_specimens = ','.join(str(i) for i in combined_ids)

        for i in specimens_to_store:
            add_specimen_audit(i, stored_specimens_instance.custody.data,
                               f'{current_user.initials} stored specimen after return',
                               datetime.now(), 'IN')

            specimen_location = Specimens.query.filter_by(id=i).first()
            specimen_location.custody = f'{stored_specimens_instance.custody.data}'
            specimen_location.custody_type = f'{stored_specimens_instance.custody_type.data}'
        db.session.commit()

    # ========================================================
    # 5. LEGACY SPECIMEN HANDLING
    #NOTE: This whole block can become a helper function later.
    # ========================================================
    # Safe defaults before form submission check
    legacy_code = None
    legacy_accession_number = None
    legacy_date_created = None
    legacy_created_by = None
    legacy_checked_by = None

     # Handle form submission for adding legacy  specimens
    if legacy_specimen_add_form.is_submitted():
        # Get new values from form
        item.status = 'Pending Return'
        new_code = legacy_specimen_add_form.legacy_code.data
        new_accession = legacy_specimen_add_form.legacy_accession_number.data
        new_date_created = legacy_specimen_add_form.legacy_date_created.data
        new_created_by = legacy_specimen_add_form.legacy_created_by.data
        new_checked_by = legacy_specimen_add_form.legacy_checked_by.data

        # Append to existing values with commas
        def append(existing, new):
            return f"{existing}, {new}" if existing else new
        item.legacy_code = append(item.legacy_code, new_code)
        item.legacy_accession_number = append(item.legacy_accession_number, new_accession)
        item.legacy_date_created = append(item.legacy_date_created, new_date_created)
        item.legacy_created_by = append(item.legacy_created_by, new_created_by)
        item.legacy_checked_by = append(item.legacy_checked_by, new_checked_by)

        db.session.commit()
        return redirect(url_for(f'{table_name}.view', item_id=item_id))
    
    #Handling Finalized status
    if item.legacy_case and item.checker: #legacy specimens location of storage not being tracked
        item.status = 'Finalized'
        item.communications = ''
    if item.legacy_case is None and item.returned_specimens is not None and  len(item.stored_specimens or []) == len(item.returned_specimens or []): #once all returned specimens are stored
        item.status = 'Finalized'
        item.communications = ''
   

    kwargs= { 'returned_specimens' : returned_specimens_instance,
            'stored_specimens': stored_specimens_instance,
            'user_initials': user_initials,
            'cases': cases,
            'case_number_str': case_number_str,
            'selected_specimens_str': Markup(selected_specimens_str),
            'selected_specimens_list': returned_specimens,  # for table display
            'returned_specimens': returned_specimens_instance,
            'legacy_specimen_add_form': legacy_specimen_add_form,
            'legacy_code': legacy_code,
            'legacy_accession_number': legacy_accession_number,
            'legacy_date_created': legacy_date_created,
            'legacy_created_by': legacy_created_by,
            'legacy_checked_by': legacy_checked_by
            }
    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view

@blueprint.route(f'/{table_name}/<int:item_id>/verify')
@login_required
def verify_initials(item_id):
    item = table.query.get_or_404(item_id)
    item.checker = current_user.id
    item.check_date = datetime.now()
    db.session.commit()

    return redirect(url_for(f'{table_name}.view',item_id = item_id))


# Remove route for non-legacy specimens
@blueprint.route(f'/{table_name}/<int:item_id>/remove_specimen', methods=['POST'])
@login_required
def remove_specimen(item_id):
    item = table.query.get_or_404(item_id)
    specimen_id = (request.form.get('specimen_id') or '').strip()
    if not specimen_id:
        flash('No specimen id provided.', 'warning')
        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Work only against the CSV you already use in view()
    csv_raw = item.returned_specimens or ''
    ids = [x.strip() for x in csv_raw.split(',') if x.strip()]

    # Remove the ID (compare as strings)
    new_ids = [x for x in ids if x != specimen_id]

    if new_ids != ids:
        item.returned_specimens = ','.join(new_ids) if new_ids else None
        db.session.commit()
        flash('Specimen removed successfully!', 'success')
    else:
        flash('Nothing changed — that specimen wasn’t linked here.', 'info')

    return redirect(url_for(f'{table_name}.view', item_id=item_id))

# Remove route for legacy specimens
@blueprint.route(f'/{table_name}/<int:item_id>/remove_legacy_specimen', methods=['POST'])
@login_required
def remove_legacy_specimen(item_id):
    item = table.query.get_or_404(item_id)
    index_raw = request.form.get('legacy_index', None)
    try:
        index = int(index_raw)
    except (TypeError, ValueError):
        flash('Invalid legacy index.', 'danger')
        return redirect(url_for('returns.view', item_id=item.id))

    def split_csv(s): return [] if not s else [seg.strip() for seg in s.split(',')]
    def join_csv(lst): return None if not lst else ','.join(lst)
    def pop_if_ok(lst, idx):
        if 0 <= idx < len(lst): lst.pop(idx); return True
        return False

    codes       = split_csv(item.legacy_code)
    accessions  = split_csv(item.legacy_accession_number)
    dates       = split_csv(item.legacy_date_created)
    created_bys = split_csv(item.legacy_created_by)
    checked_bys = split_csv(item.legacy_checked_by)

    removed = False
    for lst in (codes, accessions, dates, created_bys, checked_bys):
        removed = pop_if_ok(lst, index) or removed

    if not removed:
        flash('Nothing to remove at that index.', 'warning')
        return redirect(url_for('returns.view', item_id=item.id))

    try:
        item.legacy_code = join_csv(codes)
        item.legacy_accession_number = join_csv(accessions)
        item.legacy_date_created = join_csv(dates)
        item.legacy_created_by = join_csv(created_bys)
        item.legacy_checked_by = join_csv(checked_bys)
        db.session.commit()
        flash('Legacy specimen removed.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to remove legacy specimen.', 'danger')

    return redirect(url_for('returns.view', item_id=item.id))

# NOTE: The following routes are used for dynamic filtering:
@blueprint.route('/get_all_personnel/')
@login_required
def get_personnel():
    division = request.args.get('division', type=int)
    agency = request.args.get('agency', type=int)

    # Filter personnel based on both agency and division
    personnel = Personnel.query.filter_by(division_id=division, agency_id=agency, status_id='1').all()
    choices = []

    if division != 0:
        if len(personnel) != 0:
            choices.append({'id': 0, 'name': '---'})
            for person in personnel:
                choice = {
                    'id': person.id,
                    'name': f"{person.first_name} {person.last_name}"
                }
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This division has no personnel'})
    else:
        choices.append({'id': 0, 'name': 'No division selected'})

    return jsonify({'personnel': choices})


@blueprint.route('/returns/get_divisions/')
@login_required
def get_divisions():
    agency_id = request.args.get('agency', type=int)

    # Query divisions based on the provided agency ID
    divisions = Divisions.query.filter_by(agency_id=agency_id).all()
    choices = []

    # Build the choices list based on available divisions
    if agency_id != 0:
        if divisions:
            choices.append({'id': 0, 'name': 'Please select a division'})
            for division in divisions:
                choice = {
                    'id': division.id,
                    'name': division.name
                }
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'No divisions available for this agency'})
    else:
        choices.append({'id': 0, 'name': 'No agency selected'})

    return jsonify({'divisions': choices})

@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):
    _lock = lock_item(item_id, table, name)

    return _lock


# NOTE: The following blocks are notes for refactoring the view() 
"""
def prepare_cases(item: Returns) -> tuple[list[Cases], str]:
    Parse item.case_id, query Cases, preserve order, and return (cases, display_string).

def handle_returned_specimens(item: Returns, form: ReturnedSpecimensForm, user_initials: str) -> None:
   Process returned specimens form, update item + custody, audit new specimens.

def handle_stored_specimens(item: Returns, form: StoredSpecimensForm, user_initials: str) -> None:
    Process stored specimens form, update item + custody, audit stored specimens.

def handle_legacy_specimens(item: Returns, form: LegacySpecimenAdd) -> None:
    Process legacy specimen form, append metadata fields, commit.

# === Utility helpers (shared) ===

def parse_id_list(raw_ids: str) -> list[int]:
    Turn a comma-separated string into list[int].

def combine_ids(existing: list[int], new: list[int]) -> list[int]:
    Merge two ID lists, remove duplicates, and sort.

def update_specimen_custody(specimen_id: int, custodian: str, custodian_type: str, note: str, action: str) -> None:
    Audit + update custody for a specimen.
"""