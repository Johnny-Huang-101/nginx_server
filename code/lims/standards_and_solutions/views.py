import qrcode
from sqlalchemy import and_

from lims.locations.functions import set_location, models_iter, location_dict, get_location_display
from lims.models import BatchConstituents, Batches, Components, StandardsAndSolutions, CalibratedLabware, Assays, AssayConstituents, SolutionTypes, Locations, \
    SolventsAndReagents, Cases, Specimens
from lims.standards_and_solutions.forms import *
from lims.standards_and_solutions.functions import get_form_choices
from lims.view_templates.views import *
from lims.forms import Attach, Import
from lims.labels import fields_dict
import base64

# Set item global variables
item_type = 'Standards and Solutions'
item_name = 'Prepared Standards and Reagents'  # ie display name in navbar, Modifications and Attachments tables
table = StandardsAndSolutions
table_name = 'standards_and_solutions'
name = 'lot'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)

# All form fields in standards_and_solutions
optional_fields = {
    'Concentrator Multiplier': 'concentrator_multiplier',
    'Parent Standard Lot': 'parent_standard_lot',
    'Part A Table': 'part_a_table',
    'Part A ID': 'part_a_id',
    'Part B Table': 'part_b_table',
    'Part B ID': 'part_b_id',
    'Part C Table': 'part_c_table',
    'Part C ID': 'part_c_id',
    'Equipment Used': 'equipment_used',
    'Volume Prepared': 'volume_prepared',
    'Solvent Used': 'solvent_used',
    'Aliquot Volume': 'aliquot_volume',
    'Total Aliquots': 'total_aliquots',
    'Pipette Check': 'pipette_check',
    'Verification Batches': 'verification_batches',
    'Previous Lot': 'previous_lot',  # To be updated to string column with multiple select 
    'Previous Lot Comments': 'previous_lot_comments',
    'Qualitative Comments': 'qualitative_comments',
    'Additional Comments': 'additional_comments',
    'Quantitative Comments': 'quantitative_comments',
    'Calibration Comments': 'calibration_comments',
    'Verification Comments': 'verification_comments',
    'Preservatives': 'preservatives',
    'Component': 'component'
}

# All expected attachments
expected_attachments = {
    'qualitative_comments': 'Qualitative Assessment',
    'quantitative_comments': 'Quantitative Assessment',
    'calibration_comments': 'Calibration Assessment'
}

# All relevant column types
column_types = {
    'Concentrator Multiplier': 'string',
    'Parent Standard Lot': 'integer',
    'Part A': 'string',
    'Part A Lot': 'string',
    'Part A Expiration': 'datetime',
    'Part B': 'string',
    'Part B Lot': 'string',
    'Part B Expiration': 'datetime',
    'Part C': 'string',
    'Part C Lot': 'string',
    'Part C Expiration': 'datetime',
    'Equipment Used': 'string',
    'Volume Prepared': 'integer',
    'Solvent Used': 'integer',
    'Aliquot Volume': 'integer',
    'Total Aliquots': 'integer',
    'Pipette Check': 'boolean',
    'Verification Batches': 'string',
    'Previous Lot': 'string', 
    'Previous Lot Comments': 'string',
    'Qualitative Comments': 'string',
    'Additional Comments': 'string',
    'Quantitative Comments': 'string',
    'Calibration Comments': 'string',
    'Verification Comments': 'string',
    'Preservatives': 'integer',
    'Part A Table': 'string',
    'Part A ID': 'integer',
    'Part B Table': 'string',
    'Part B ID': 'integer',
    'Part C Table': 'string',
    'Part C ID': 'integer',
    'Component': 'string'
}


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():

    # Set kwargs and form
    kwargs = default_kwargs.copy()
    form = get_form_choices(InitialAdd(), initial=True)

    # Check form submission
    if form.is_submitted() and form.validate():

        # Initialize no_location
        no_location = False

        # Check if no_location checked on form
        if form.no_location.data:
            
            # If no location is selected, set all location data to None and no_location True
            form.location_table.data = None
            form.location_id.data = None
            no_location = True

        add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
        
        # Get most recently added item
        new_item_id = table.query.order_by(table.id.desc()).first().id
        item = table.query.get(new_item_id)

        # Set to pending
        item.db_status = 'Pending'
        db.session.commit()

        # Set location if relevant
        if not no_location:
            set_location(table_name, new_item_id, form.location_table.data, form.location_id.data)

        # Set all unnecessary fields to 'N/A' if string
        for k, v in optional_fields.items():
            if v not in item.type.expected_fields and column_types[k] == 'string':
                setattr(item, v, 'N/A')

        # Check if submit additional was selected
        if 'submit_additional' in request.form:
            return redirect(url_for(f'{table_name}.additional_information', item_id=new_item_id))  # Redirect to additional info form
        else:
            return redirect(url_for(f'{table_name}.view', item_id=new_item_id))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Edit())
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):

    # Initialize kwargs
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'additional_information.html'

    # Get approve form
    form = get_form_choices(Approve(), initial=False)

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    item = StandardsAndSolutions.query.get(item_id)
    form = get_form_choices(Update())

    standards = [4, 5, 6, 7, 8, 9, 10, 11, 13, 14]
    requires_approval = True

    form.solution_type_id.data = item.type.id

    constituents = [int(x) for x in SolutionTypes.query.get(item.type.id).constituents.split(', ')]

    form.name.choices = [(item.id, item.name) for item in
                         AssayConstituents.query.filter(AssayConstituents.id.in_(constituents))]

    if form.is_submitted() and form.validate():
        set_location(table_name, item_id, form.location_table.data, form.location_id.data)

        # if form.verification.data:
        #     print('FORM VERIFICATION DATA')
        #     o_filename = form.verification.data.filename
        #     ext_type = o_filename.split('.')[-1]
        #     filename = form.lot.data + '_Verification.' + ext_type
        #     filepath = os.path.join(current_app.root_path, 'static')
        #     filepath2 = os.path.join(filepath + 'Verification_and_Memos' + filename)
        #     form.verification.data.save(filepath2)
        #
        #     form.verification.data = filename

        item.in_use = False

        if form.solution_type_id.data not in standards:
            requires_approval = False

        for field in form:

            if field.name in ['submit', 'csrf_token', 'location_id', 'location_table', 'no_location', 'submit_additional']:
                pass
            else:
                attribute = getattr(item, field.name)

                if field.data != attribute:
                    if field.type == 'SelectMultipleField':
                        field.data = ', '.join(map(str, field.data))
                    elif field.type in ['DateField', 'NullableDateField']:
                        print("Handling DateField/NullableDateField")
                        if field.data is not None:
                            field.data = datetime.combine(field.data, datetime.min.time())
                            print(f"Combined datetime: {field.data}")
                        else:
                            print(f"WARNING: field.data is None for {field.name}, skipping datetime.combine()")
                    if attribute is None:
                        if field.data == '' or field.data == 0 or field.data == []:
                            field.data = None
                            print(f'ATTRIBUTE: {attribute}')
                            print(f'FIELD DATA: {field.data}')
                            print(f'UPDATE: {field.data}')
                        else:
                            setattr(item, field.name, field.data)
                            print(f'NEW ATTR: {attribute}')

                    else:
                        setattr(item, field.name, field.data)
                        print(f'NEW ATTR: {attribute}')
        db.session.commit()

        return redirect(url_for(f'{table_name}.view', item_id=item.id))

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs,
                          locking=False)

    return _update


@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):
    _lock = lock_item(item_id, table, name)

    return _lock


@blueprint.route(f'/{table_name}/<int:item_id>/unlock', methods=['GET', 'POST'])
@login_required
def unlock(item_id):
    _unlock = unlock_item(item_id, table, name)

    return _unlock


@blueprint.route(f'/{table_name}/revert_changes/')
@login_required
def revert_changes():
    item_id = request.args.get('item_id', 0, type=int)
    field = request.args.get('field_name', type=str)
    field_value = request.args.get('field_value', type=str)
    field_type = request.args.get('field_type', type=str)
    multiple = request.args.get('multiple', type=str)

    _revert_changes = revert_item_changes(item_id, field, field_value, item_name, field_type, multiple)

    return _revert_changes


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
    form = InitialAdd()

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


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    # Initialize kwargs
    kwargs = default_kwargs.copy()
    kwargs['assays'] = dict([(item.id, item.assay_name) for item in Assays.query.all()])
    kwargs['standards'] = StandardsAndSolutions
    kwargs['locations'] = [Locations.query.all(), {'models': models_iter}, {'location_dict': location_dict}]

    # Get 30 days as time
    thirty_days = datetime.today() + timedelta(days=30)

    # Get 30-day and 1-day queries
    thirty_day_query = table.query.filter(
        table.in_use == 1,
        table.retest_date <= thirty_days,
        table.retest_date > datetime.now()
        ).count()
    
    one_day_query = table.query.filter(
        table.in_use == 1,
        table.retest_date <= datetime.today()
        ).count()

    # Get warnings and dangers for table
    warning_alerts = [
        (url_for(f'{table_name}.view_list', query='thirty_day_query'), thirty_day_query,
         Markup('in use with <b>retest dates within 30 days</b>')),
    ]

    danger_alerts = [
        (url_for(f'{table_name}.view_list', query='one_day_query'), one_day_query,
         Markup('in use <b>retest dates that have passed or are within 1 day</b>')),
    ]

    _view_list = view_items(table, item_name, item_type, table_name, 
                            warning_alerts=warning_alerts, danger_alerts=danger_alerts, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    kwargs = default_kwargs.copy()
    item = StandardsAndSolutions.query.get_or_404(item_id)
    requires_attachments = False

    # Get all names for series
    kwargs['series_names'] = [
        "Mix Check", "ISTD", "LOD", 
        "Calibrator", "QC (Quant)", "QC (Qual)", 
        "Calibrator (SAMQ)", "QC (SAMQ)", "QC", "LOS"
        ]
    
    # Get all batches using prepared standard/reagent
    batch_ids = [const.batch_id for const in BatchConstituents.query.filter_by(constituent_id=item_id).all()]

    if batch_ids:
        kwargs['batches'] = Batches.query.filter(Batches.id.in_(batch_ids)).all()
    else:
        kwargs['batches'] = []

    # Form to update retest date
    update_retest = UpdateRetest()

    # Handle retest form submission
    if update_retest.is_submitted() and update_retest.validate():
        update_item(update_retest, item_id, table, item_type, item_name, table_name, requires_approval, name)

    # Get all required values for view
    if not item.parent_standard_lot:
        
        # Check if current standard is a "parent" standard
        if table.query.filter_by(parent_standard_lot=item.id).count():
            # Get all child standards to view
            kwargs['child_standards'] = table.query.filter_by(parent_standard_lot=item.id)

        # Initialize and set assay information
        assays = []
        if item.assay is not None:
            for assay in item.assay.split(', '):
                assays.append(Assays.query.get(int(assay)).assay_name)
        kwargs['assays'] = assays

        # Initialize and set equipment ids
        eq_ids = None
        if item.equipment_used and item.equipment_used != 'N/A':
            eq_ids = [CalibratedLabware.query.get(int(s.strip())).equipment_id for s in item.equipment_used.split(',') if s.strip()]
        kwargs['eq_ids'] = eq_ids

        # Initialize and set parent standard lot data
        kwargs['parent'] = None
        if item.parent_standard_lot is not None and item.parent_standard_lot != 'N/A':
            kwargs['parent'] = table.query.get(item.parent_standard_lot).lot

        # Initialize and set verification batch data
        kwargs['verification'] = None
        if item.verification_batches is not None and item.verification_batches != 'N/A':
            kwargs['verification'] = [Batches.query.get(int(s)).batch_id for s in item.verification_batches.split(',') if s.strip()]

        # Initialize and set previous lot data
        kwargs['previous_lots'] = None
        if item.previous_lot is not None and item.previous_lot != 'N/A':
            kwargs['previous_lots'] = [StandardsAndSolutions.query.get(int(s)).lot for s in item.previous_lot.split(',') if s.strip()]

        # Handle information if blank matrix
        if item.type.name == 'Blank Matrix':
            case_number = Cases.query.filter_by(case_number=item.lot).first().id
        else:
            case_number = None

        # Get current location information
        kwargs['location'] = get_location_display(table_name, item_id)

        # Initialize kwargs
        kwargs['approval_ready'] = True
        kwargs['missing_fields'] = []

        # Reverse optional_fields dict
        reverse_fields = {v: k for k,v in optional_fields.items()}

        # Determine if standard ready for approval
        for field in item.type.expected_fields.split(', '):
            # If "part" field expected, maintain N/A entry
            if field in ['part_a_exp', 'part_b_exp', 'part_c_exp']:
                if getattr(item, f'no_{field}') == 'N/A':
                    pass
                else:
                    if getattr(item, f'no_{field}') is None and getattr(item, field) is None:
                        kwargs['approval_ready'] = False
                        kwargs['missing_fields'].append(reverse_fields[field])
            
            # Handle empty fields
            elif getattr(item, field) in [None, [], '']:
                kwargs['approval_ready'] = False
                kwargs['missing_fields'].append(reverse_fields[field])

            # Check if all expected attachments are present
            if field in expected_attachments.keys():
                requires_attachments = True
                if getattr(item, field) == 'N/A':
                    pass
                else:
                    attachment_type = AttachmentTypes.query.filter_by(name=expected_attachments[field]).first()
                    if Attachments.query.filter(and_(Attachments.type_id == attachment_type.id, Attachments.record_id == item_id)).count():
                        pass
                    else:
                        kwargs['approval_ready'] = False
                        kwargs['missing_fields'].append(f'{expected_attachments[field]} Attachment')

        # Ensure log and labels have been verified
        if item.verified_by is None:
            kwargs['approval_ready'] = False
            kwargs['missing_fields'].append('Location and Labels Verification')

        # If requires attachments, count all attachments
        if requires_attachments:
            # Count number of attachments
            kwargs['attachments'] = db.session.query(Attachments).filter_by(table_name=item_name, record_id=str(item_id)).count()
        else:
            kwargs['attachments'] = 'N/A'
    
    else:

        # Get the "parent" standard
        parent_standard = table.query.get(item.parent_standard_lot)
        kwargs['parent_standard'] = parent_standard

        # Check if "parent" standard has been approved and if "child" standard needs to be approved
        if parent_standard.approved_by and item.approved_by is None:
            item.approved_by = parent_standard.approved_by
            item.approve_date = parent_standard.approve_date
            db.session.commit()

        # Initialize and set assay information
        assays = []
        if parent_standard.assay is not None:
            for assay in parent_standard.assay.split(', '):
                assays.append(Assays.query.get(int(assay)).assay_name)
        kwargs['assays'] = assays

        # Initialize and set equipment ids
        eq_ids = None
        if item.equipment_used and item.equipment_used != 'N/A':
            eq_ids = [CalibratedLabware.query.get(int(s.strip())).equipment_id for s in item.equipment_used.split(',') if s.strip()]
        kwargs['eq_ids'] = eq_ids

        # Initialize and set parent standard lot data
        kwargs['parent'] = None
        if item.parent_standard_lot is not None and item.parent_standard_lot != 'N/A':
            kwargs['parent'] = table.query.get(item.parent_standard_lot).lot

        # Initialize and set verification batch data
        kwargs['verification'] = None
        if parent_standard.verification_batches is not None and parent_standard.verification_batches != 'N/A':
            kwargs['verification'] = [Batches.query.get(int(s)).batch_id for s in parent_standard.verification_batches.split(',') if s.strip()]

        # Initialize and set previous lot data
        kwargs['previous_lots'] = None
        if parent_standard.previous_lot is not None and parent_standard.previous_lot != 'N/A':
            kwargs['previous_lots'] = [StandardsAndSolutions.query.get(int(s)).lot for s in parent_standard.previous_lot.split(',') if s.strip()]

        # Get current location information
        kwargs['location'] = get_location_display(table_name, item_id)

        # Initialize kwargs
        kwargs['approval_ready'] = True
        kwargs['missing_fields'] = []

        # Reverse optional_fields dict
        reverse_fields = {v: k for k,v in optional_fields.items()}

        # Determine if standard ready for approval
        for field in parent_standard.type.expected_fields.split(', '):

            # This is already for a 'child' standard so we do not need to check parent_standard_lot
            if field == 'parent_standard_lot':
                pass

            # If "part" field expected, maintain N/A entry
            elif field in ['part_a_exp', 'part_b_exp', 'part_c_exp']:
                if getattr(parent_standard, f'no_{field}') == 'N/A':
                    pass
                else:
                    if getattr(parent_standard, f'no_{field}') is None and getattr(parent_standard, field) is None:
                        kwargs['approval_ready'] = False
                        kwargs['missing_fields'].append(reverse_fields[field])
            
            # Handle empty fields
            elif getattr(parent_standard, field) in [None, [], '']:
                kwargs['approval_ready'] = False
                kwargs['missing_fields'].append(reverse_fields[field])

        # Ensure log and labels have been verified
        if item.verified_by is None:
            kwargs['approval_ready'] = False
            kwargs['missing_fields'].append('Log and Labels Verification')

        # If requires attachments, count all attachments
        if requires_attachments:
            # Count number of attachments
            kwargs['attachments'] = db.session.query(Attachments).filter_by(table_name=item_name, record_id=str(parent_standard.id)).count()
        else:
            kwargs['attachments'] = 'N/A'

    # Initialize part variables
    part_a = None
    part_b = None
    part_c = None

    # Check which part_a column was used and set part_a for display accordingly
    if getattr(item, 'part_a') not in [None, 'N/A']:
        part_a = f'{item.part_a} {item.part_a_lot} (exp. {item.part_a_exp.strftime("%m-%d-%Y") if item.part_a_exp is not None else ""})'
    elif getattr(item, 'part_a_id') not in [None, 'N/A']:
        if item.part_a_table == 'standards_and_solutions':
            part_a_item = table.query.get(item.part_a_id)
            part_a = f'{part_a_item.lot} (exp. {part_a_item.retest_date.strftime("%m-%d-%Y")})'
        else:
            part_a_item = SolventsAndReagents.query.get(item.part_a_id)
            part_a = f'{part_a_item.name} {part_a_item.lot} (exp. {part_a_item.exp_date.strftime("%m-%d-%Y") if part_a_item.exp_date is not None else ""})'
    # Set to part_a or part_a_table depending on value
    else:
        part_a = item.part_a if item.part_a is not None else item.part_a_table

    # Check which part column was used and set part_b for display accordingly
    if getattr(item, 'part_b') not in [None, 'N/A']:
        part_b = f'{item.part_b} {item.part_b_lot} (exp. {item.part_b_exp.strftime("%m-%d-%Y") if item.part_b_exp is not None else ""})'
    elif getattr(item, 'part_b_id') not in [None, 'N/A']:
        if item.part_b_table == 'standards_and_solutions':
            part_b_item = table.query.get(item.part_b_id)
            part_b = f'{part_b_item.lot} (exp. {part_b_item.retest_date.strftime("%m-%d-%Y")})'
        else:
            part_b_item = SolventsAndReagents.query.get(item.part_b_id)
            part_b = f'{part_b_item.name} {part_b_item.lot} (exp. {part_b_item.exp_date.strftime("%m-%d-%Y") if part_b_item.exp_date is not None else ""})'
    # Set to part_b or part_b_table depending on value
    else:
        part_b = item.part_b if item.part_b is not None else item.part_b_table

    # Check which part column was used and set part_c for display accordingly
    if getattr(item, 'part_c') not in [None, 'N/A']:
        part_c = f'{item.part_c} {item.part_c_lot} (exp. {item.part_c_exp.strftime("%m-%d-%Y") if item.part_c_exp is not None else ""})'   
    elif getattr(item, 'part_c_id') not in [None, 'N/A']:
        if item.part_c_table == 'standards_and_solutions':
            part_c_item = table.query.get(item.part_c_id)
            part_a = f'{part_c_item.lot} (exp. {part_c_item.retest_date.strftime("%m-%d-%Y")})'
        else:
            part_c_item = SolventsAndReagents.query.get(item.part_c_id)
            part_c = f'{part_c_item.name} {part_c_item.lot} (exp. {part_c_item.exp_date.strftime("%m-%d-%Y") if part_c_item.exp_date is not None else ""})'
    # Set to part_c or part_c_table depending on value
    else:
        part_c = item.part_c if item.part_c is not None else item.part_c_table

    # Update missing_fields kwargs depending on part_a, part_b, part_c
    if part_a is not None:
        try:
            kwargs['missing_fields'].remove('Part A Table')
        except ValueError:
            pass

        try:
            kwargs['missing_fields'].remove('Part A ID')
        except ValueError:
            pass
    
    if part_b is not None:
        try:
            kwargs['missing_fields'].remove('Part B Table')
        except ValueError:
            pass
        try:
            kwargs['missing_fields'].remove('Part B ID')
        except ValueError:
            pass

    if part_c is not None:
        try:
            kwargs['missing_fields'].remove('Part C Table')
        except ValueError:
            pass
        try:
            kwargs['missing_fields'].remove('Part C ID')
        except ValueError:
            pass
    
    # Check if approval ready after updating missing_fields
    if len(kwargs['missing_fields']) == 0:
        kwargs['approval_ready'] = True

    # Set all parts for view
    kwargs['part_a'] = part_a
    kwargs['part_b'] = part_b
    kwargs['part_c'] = part_c

    kwargs['component'] = None

    # Get component name(s) if applicable
    if 'component' in item.type.expected_fields and item.component is not None:
        comps = [Components.query.get(int(comp)).name for comp in item.component.split(', ') if comp.strip()]
        kwargs['component'] = ', '.join(comps)

    # Get item alias information
    if not item.in_use:
        alias = Markup(f"{getattr(item, name)} <span class='text-danger'>NOT IN USE</span>")
    else:
        alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name, default_buttons=False, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/import_prep_log/', methods=['GET', 'POST'])
@login_required
def import_prep_log():
    form = ImportPrepLog()
    kwargs = {}
    status = "Approved"
    name = ""

    if request.method == 'POST':
        f = request.files.get('file')
        filename = f"{f.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
        path = os.path.join(current_app.root_path, 'static/Uploads', filename)
        f.save(path)
        df = pd.read_csv(path)
        name = f.filename
        dates = ['date', 'exp']
        date_cols = []

        for col in df.columns:
            if any(x in col for x in dates):
                df[col] = pd.to_datetime(df[col], errors='ignore')
                date_cols.append(col)
            else:
                df[col].fillna("", inplace=True)
        print(date_cols)

        # df['submission_time'] = df['submission_time'].map(lambda x : str(int(x)).rjust(4, '0') if x != "" else "")

        # df = df.iloc[:1,:]
        # df['tat_start_date'] = pd.to_datetime(df['tat_start_date'], errors='ignore')
        # df['tat_alternate_start_date'] = pd.to_datetime(df['tat_alternate_start_date'], errors='ignore')
        # df['case_close_date'] = pd.to_datetime(df['tat_start_date'], errors='ignore')
        # df['tat_start_date'] = pd.to_datetime(df['tat_start_date'], errors='ignore')
        # df['date_of_birth'] = pd.to_datetime(df['date_of_birth'], errors='ignore')
        # df['date_of_incident'] = pd.to_datetime(df['date_of_incident'], errors='ignore')
        # df['discard_date'] = pd.to_datetime(df['discard_date'], errors='ignore')
        # df['create_date'] = pd.to_datetime(df['create_date'], errors='ignore')
        # print(df.iloc[0])
        # df.replace(np.nan, "", inplace=True)

        field_data = {'db_status': 'Active',
                      'create_date': datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')),
                      'created_by': current_user.initials,
                      'modify_date': None,
                      'modified_by': "",
                      'revision': 0,
                      'delete_reason': "",
                      }

        for idx, row in enumerate(df.iterrows()):
            dict = {}
            row = row[1]
            # print(idx)
            for item in row.iteritems():
                val = item[1]
                # print(val)
                if item[0] in date_cols:
                    if pd.isnull(item[1]):
                        val = None
                dict[item[0]] = val
                # dict[item[0]] = item[1]
                # print(type(item[1]))

            field_data.update(dict)
            item = table(**field_data)
            db.session.add(item)

            # modification = Modifications(
            #     event='IMPORTED',
            #     status=status,
            #     table_name=item_name,
            #     record_id=item.id,
            #     revision=0,
            #     field="File",
            #     field_name="file_name",
            #     original_value=f.filename,
            #     original_value_text=f.filename,
            #     new_value=filename,
            #     new_value_text=filename,
            #     submitted_by=current_user.id,
            #     submitted_date=datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')),
            #     reviewed_by=current_user.id,
            #     review_date=datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific'))
            # )
            # db.session.add(modification)

        db.session.commit()

        return redirect(url_for('standards_and_solutions.view_list'))

    return render_template('standards_and_solutions/import.html', form=form)


@blueprint.route(f'/{table_name}/<int:item_id>/series', methods=['GET', 'POST'])
@login_required
def series(item_id):

    # Initialize necessary variables
    kwargs = default_kwargs.copy()
    errors = []
    exit_route = url_for(f'{table_name}.view', item_id=item_id)
    requires_approval = False

    # Get request method to pass into other functions
    is_post = True if request.method == 'POST' else False

    # Get parent standard
    parent = StandardsAndSolutions.query.get(item_id)

    # Get selected series number (how many child standards to be added)
    series_num = request.args.get('series_num')

    # Set form and set fields that are inherited by child standards
    form = get_form_choices(Series(), initial=True, item=parent, series=True, is_post=is_post)

    # Get counter variable if it exists or initialize
    if request.args.get('counter'):
        counter = int(request.args.get('counter'))
    else:
        counter = 1

    # Check form submission
    if form.is_submitted() and form.validate():

        # Initialize no_location variable and set based on form field
        no_location = False
        if form.no_location.data:
            no_location = True

        # Check if no_location form field was not selected and set location if necessary
        if not no_location:
            set_location(table_name, None, form.location_table.data, form.location_id.data)

        # Check if series num exists
        if series_num is not None:
            # Increment counter here to ensure counter matches series_num
            counter += 1

            # Add standards until correct amount has been reached
            if counter <= int(series_num):
                add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                table.query.order_by(table.id.desc()).first().db_status = 'Pending'
                db.session.commit()

                return redirect(url_for(f'{table_name}.series', item_id=parent.id, series_num=series_num,
                                        counter=counter))
            else:
                add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                table.query.order_by(table.id.desc()).first().db_status = 'Pending'
                db.session.commit()

                return redirect(url_for(f'{table_name}.view_list'))
            
        # Add one standard if series_num doesn't exist
        else:
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
            table.query.order_by(table.id.desc()).first().db_status = 'Pending'
            db.session.commit()
            
            return redirect(url_for(f'{table_name}.view_list'))

    return render_template(f'/{table_name}/series.html', form=form, 
                           series_num=series_num, errors=errors, 
                           exit_route=exit_route)


@blueprint.route(f'/{table_name}/get_constituents/', methods=['GET', 'POST'])
@login_required
def get_constituents():
    # Get solution type from frontend
    solution_type = request.args.get('solution_type', type=int)

    # Get solution query object
    solution = SolutionTypes.query.get(solution_type)

    # Initialize choices
    choices = [({'id': 0, 'name': f'Please select {solution.name}'})]

    # Initialize constituents
    constituents = []

    # Get individual constituent ids (stored as comma separated string)
    constituent_id = solution.constituents.split(', ')

    # Get each choice and append for each constituent id present
    for x in constituent_id:
        constituents.append(AssayConstituents.query.get(x))
        choices.append({'id': AssayConstituents.query.get(x).id, 'name': AssayConstituents.query.get(x).name})

    return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/get_constituent_data/', methods=['GET', 'POST'])
@login_required
def get_constituent_data():

    # Initialize and get relevant variables
    item_table = request.args.get('table')
    item_id = request.args.get('id')
    data = {'name': None, 'constituent': None}

    # Get relevant data dependant of resource type
    if item_table == 'standards_and_solutions':
        data['name'] = StandardsAndSolutions.query.get(item_id).constituent.id
    elif item_table == 'solvents_and_reagents':
        data['constituent'] = SolventsAndReagents.query.get(item_id).const.id

    return jsonify({'name': data['name'], 'constituent': data['constituent']})


@blueprint.route(f'/{table_name}/<int:item_id>/submit', methods=['GET', 'POST'])
@login_required
def submit(item_id):

    # Get item
    item = StandardsAndSolutions.query.get(item_id)

    # Set item to submitted
    item.db_status = 'Submitted'

    # Set pending_submitter
    item.pending_submitter = current_user.initials

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item.id))


@blueprint.route(f'/{table_name}/<int:item_id>/print_label', methods=['GET', 'POST'])
@login_required
def print_labels(item_id):
    # Get current item
    item = StandardsAndSolutions.query.get(item_id)

    # Set printer to reagents printer
    printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 – Reagent Prep'
    attributes_list = []

    # Check for solution type and set label_attributes accordingly some solution types require different label template
    if item.type.id == SolutionTypes.query.filter_by(name='Blank Matrix').first().id:
        # assays = [item.name for item in Assays.query.filter(Assays.id in item.assay.split(', ')).all()]
        assay_names = []
        for assay in Assays.query.filter(Assays.id.in_(item.assay.split(', '))):
            assay_names.append(assay.assay_name)
        counter = 1
        for i in range(0, int(item.total_aliquots)):
            printer = r'\\OCMEG9M022.medex.sfgov.org\BS11 - Accessioning'
            case_id_search = Cases.query.filter_by(case_number=item.lot).first().id
            specimen = Specimens.query.filter_by(case_id=case_id_search).first()
            assays = Assays.query.filter(Assays.id)
            label_attributes = fields_dict['blank_matrix']
            label_attributes['CASE_NUM'] = item.lot
            if 'Blood' in item.constituent.name:
                label_attributes['MATRIX'] = 'Blood'
            elif 'Oral Fluid' in item.constituent.name:
                label_attributes['MATRIX'] = 'Oral Fluid'
            else:
                label_attributes['MATRIX'] = 'URINE'
            if len(assay_names) > 1:
                label_attributes['ASSY'] = '\n'.join(assay_names)
            else:
                label_attributes['ASSY'] = assay_names[0]

            qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'{table_name}{item.id}.png')
            qrcode.make(f'standards_and_solutions: {item.id}').save(qr_path)

            with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

            label_attributes['ACC_NUM'] = specimen.accession_number
            label_attributes['PREP_DATE'] = item.prepared_date.strftime('%m/%d/%Y')
            label_attributes['EXP_DATE'] = item.retest_date.strftime('%m/%d/%Y')
            label_attributes['COUNTER'] = f'{counter}/{item.total_aliquots}'
            label_attributes['QR'] = qr_encoded
            
            attributes_list.append(label_attributes.copy())

            counter += 1

    elif item.type.id == AssayConstituents.query.filter_by(name='Volatile ISTD').first().id:
        label_attributes = fields_dict['gcet_istd']

        counter = 1

        for i in range(0, item.total_aliquots):
            qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'{table_name}{item.id}.png')
            qrcode.make(f'standards_and_solutions: {item.id}').save(qr_path)

            with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

            label_attributes['COUNTER'] = f'{counter}/{item.total_aliquots}'
            label_attributes['LOT_NUM'] = item.lot
            label_attributes['PREP_BY'] = item.prep_by.initials
            label_attributes['PREP_DATE'] = item.prepared_date.strftime('%m/%d/%Y')
            label_attributes['EXP_DATE'] = item.retest_date.strftime('%m/%d/%Y')
            label_attributes['QR'] = qr_encoded

            attributes_list.append(label_attributes.copy())

    elif item.type.id == SolutionTypes.query.filter_by(name='QC (GCET)').first().id:
        printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 - Extraction'
        label_attributes = fields_dict['gcet_qc']

        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'{table_name}{item.id}.png')
        qrcode.make(f'standards_and_solutions: {item.id}').save(qr_path)

        with open(qr_path, "rb") as qr_file:
            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

        counter = 1
        try:
            max_num = item.total_aliquots / 2
            if max_num % 1 == 0.5:
                max_num += 0.5
        except TypeError:
            max_num = 1

        for i in range(0, int(max_num)):
            label_attributes['COUNTER'] = f'{counter} of {item.total_aliquots}'
            label_attributes['COUNTER_1'] = f'{counter + 1} of {item.total_aliquots}'
            label_attributes['LOT'] = item.lot.replace('_', '\n_')
            label_attributes['LOT_1'] = item.lot.replace('_', '\n_')
            label_attributes['PREP_BY'] = item.prep_by.initials
            label_attributes['PREP_BY_1'] = item.prep_by.initials
            label_attributes['EXP'] = item.retest_date.strftime('%m/%d/%Y')
            label_attributes['EXP_1'] = item.retest_date.strftime('%m/%d/%Y')
            label_attributes['QR'] = qr_encoded
            label_attributes['QR_1'] = qr_encoded

            attributes_list.append(label_attributes.copy())

            counter += 2

    else:
        label_attributes = fields_dict['reagent_lg']
        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'{table_name}{item.id}.png')
        qrcode.make(f'standards_and_solutions: {item.id}').save(qr_path)

        with open(qr_path, "rb") as qr_file:
                qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

        # Length for descitption == 41
        try:
            item_desc = list(item.description)
        except TypeError:
            item_desc = ''

        y = 0

        for x in item_desc:
            y += 1
            if y == 41:
                item_desc.insert(y, '\n')

        label_attributes['REAGENT'] = item.constituent.name
        label_attributes['DESCRIPTION'] = "".join(item_desc)
        label_attributes['LOT_NUM'] = item.lot
        label_attributes['PREP_DATE'] = item.prepared_date.strftime('%m/%d/%Y')
        label_attributes['EXP_DATE'] = item.retest_date.strftime('%m/%d/%Y')
        label_attributes['PREP_BY'] = item.prep_by.initials
        label_attributes['QR'] = qr_encoded

        attributes_list.append(label_attributes.copy())


    # print_label(printer, attributes_list)

    print(f'DONE PRINT LABEL HERE')

    # return redirect(url_for(f'{table_name}.view', item_id=item.id))

    return jsonify((attributes_list, printer, None, None, url_for(f'{table_name}.view', item_id=item.id, _external = True)))


@blueprint.route(f'/{table_name}/<int:item_id>/approve_with_date', methods=['POST'])
@login_required
def approve_with_date(item_id):
    item = StandardsAndSolutions.query.get_or_404(item_id)

    # Parse date coming in as yyyy-mm-dd from <input type="date" name="authorized_date">
    raw = request.form.get('authorized_date', '').strip()
    try:
        # store as a datetime at midnight to match your existing authorized_date usage
        selected_dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        # fallback: use now if parsing fails or field is empty
        selected_dt = datetime.now()

    # Check if there are any "child" standards and approve as well
    if StandardsAndSolutions.query.filter_by(parent_standard_lot=item.id).count():
        for x in StandardsAndSolutions.query.filter_by(parent_standard_lot=item.id).all():
            x.in_use = True
            x.approved_by = current_user.id
            x.authorized_date = selected_dt
            x.db_status = 'Active'
            x.pending_submitter = None
            x.approve_date = datetime.now()

    # Mirror your existing approve() side-effects
    item.in_use = True
    item.approved_by = current_user.id
    item.authorized_date = selected_dt
    item.db_status = 'Active'
    item.pending_submitter = None
    item.approve_date = datetime.now()

    db.session.commit()
    return redirect(url_for(f'{table_name}.view', item_id=item.id))


@blueprint.route(f'/{table_name}/<int:item_id>/additional_information', methods=['GET', 'POST'])
@login_required
def additional_information(item_id):

    item = table.query.get(item_id)

    exit_route = url_for(f'{table_name}.view', item_id=item_id)

    # Set function for frontend display
    function = 'Additional Information'

    # For render_template
    errors=[]

    # Dictionary that relates N/A form field to relevant column
    part_dict = {
        'no_part_a': 'part_a_table',
        'no_part_b': 'part_b_table',
        'no_part_c': 'part_c_table'
    }

    # Initialize AdditionalInformation form
    form = get_form_choices(AdditionalInformation(), initial=False, item=item)

    # Get required_fields based on solution_type
    required_fields = item.type.expected_fields.split(', ')

    # Check if form has been submitted
    if form.is_submitted():

        if form.no_previous_lot.data is True:
            form.previous_lot.data = ['N/A']
        
        # Iterate through form
        for field in form:

            # Get data from form field
            val = field.data

            # Skip all logic if part table column is None
            if val is None and field.name in part_dict.values():
                pass
            
            # Check if required_field
            elif field.name in required_fields:

                # Continue if data is None
                if val in [None, '', 0, []]:
                    setattr(item, field.name, None)
                    val = None

                # Hanle date fields
                if field.type == 'DateField' and val is not None:
                    val = datetime.combine(val, datetime.min.time())

                # If data is list (from SelectMultipleField) turn it into a string of comma separated values and set attribute
                if isinstance(val, list):
                    cleaned = [str(x) for x in val if str(x) != '']
                    setattr(item, field.name, ', '.join(cleaned))
                # Set attribute for all other types
                else:
                    setattr(item, field.name, val)

            # If field is "N/A" for part, set data to "N/A"
            elif field.data and field.name in part_dict.keys():
                setattr(item, part_dict[field.name], 'N/A')

        if item.db_status == 'Active':
            return redirect(url_for(f'comment_instances.add', comment_item_id=item_id, comment_item_type='Prepared Standards and Reagents'))
        
        # Redirect to item view
        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Iterate through form and set fields that already exist in backend
    for field in form:

        try:
            # Set attribute in field if backend data is not none or blank
            if getattr(item, field.name) is not None and getattr(item, field.name) != '':
                field_data = getattr(item, field.name)

                # Handle data if field is SelectMultipleField
                if field.type == 'SelectMultipleField':
                    if not isinstance(field_data, int):
                        if field_data:
                            if ", " in field_data:
                                field.data = field_data.split(", ")
                            else:
                                field.data = field_data.split("; ")
                
                # Set all other field.data
                else:            
                    field.data = getattr(item, field.name)
        # Catch AttributeError and pass
        except AttributeError:
            # Check no_previous_lot on form load if previous_lot is "N/A"
            if field.name == 'no_previous_lot':
                if getattr(item, 'previous_lot') == 'N/A':
                    field.data = True
            # Check no_part_a if part_a is "N/A"
            elif field.name == 'no_part_a':
                if getattr(item, 'part_a_table') == 'N/A' or getattr(item, 'part_a') == 'N/A':
                    field.data = True
            # Check no_part_b if part_b is "N/A"
            elif field.name == 'no_part_b':
                if getattr(item, 'part_b_table') == 'N/A' or getattr(item, 'part_b') == 'N/A':
                    field.data = True
            # Check no_part_c if part_c is "N/A"
            elif field.name == 'no_part_c':
                if getattr(item, 'part_c_table') == 'N/A' or getattr(item, 'part_c') == 'N/A':
                    field.data = True
            else:
                pass

    # Render additional information form
    return render_template(f'{table_name}/additional_information.html',
                           form=form,
                           errors=errors,
                           required_fields=required_fields,
                           item_name=item_name,
                           function=function,
                           item=item,
                           exit_route=exit_route)


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}/<int:item_id>/update_location', methods=['GET', 'POST'])
@login_required
def update_location(item_id):

    item = table.query.get(item_id)

    # Initialize form
    form = UpdateLocation()

    errors = []

    if form.is_submitted():

        if form.no_location.data:

            # Remove location entry
            item.location = None
            location_item = Locations.query.filter_by(item_table=table_name,
                                                      item_id=item_id).first()
            location_item.db_status = 'Removed'
            db.session.commit()
        else:
            set_location(table_name, item_id, form.location_table.data, form.location_id.data)

        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    # Initialize form fields
    form.location_table.choices = [(k, v['option']) for k, v in location_dict.items()]
    form.location_table.choices.insert(0, ('', 'Please select a location type'))

    return render_template(f'{table_name}/update_location.html',
                           form=form,
                           errors=errors,
                           item_id=item_id)


@blueprint.route(f'/{table_name}/<int:item_id>/verify', methods=['GET', 'POST'])
@login_required
def log_labels_verify(item_id):
    item = table.query.get(item_id)

    item.verified_by = current_user.id

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/update_in_use', methods=['GET', 'POST'])
@login_required
def update_in_use(item_id):
    item = table.query.get(item_id)

    if item.in_use:
        item.in_use = False
    else:
        item.in_use = True

    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/get_table_items/', methods=['GET', 'POST'])
@login_required
def get_table_items():

    # Check which table was selected
    part_table = request.args.get('part_table')

    # Query depending on table
    if part_table == 'standards_and_solutions':
        items = table.query.filter_by(in_use=True).all()
    else:
        items = SolventsAndReagents.query.filter_by(in_use=True).all()

    # Initialize choices
    choices = [({'id': 0, 'name': f'--'})]

    # Iterate through each item from query and set choices
    for each in items:
        if part_table == 'standards_and_solutions':
            choices.append({'id': each.id, 'name': f'{each.type.name} &nbsp &nbsp | &nbsp &nbsp {each.lot} '\
                            f'&nbsp &nbsp | &nbsp &nbsp (exp. {each.retest_date.strftime("%m/%d/%Y") if each.retest_date is not None else ""})'})
        else:
            choices.append({'id': each.id, 'name': f'{each.name} &nbsp &nbsp | &nbsp &nbsp {each.lot} '\
                            f'&nbsp &nbsp | &nbsp &nbsp (exp. {each.exp_date.strftime("%m/%d/%Y") if each.exp_date is not None else ""})'})

    return jsonify({'choices': choices})

