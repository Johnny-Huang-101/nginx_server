from lims.models import *
from lims.forms import Attach, Import
from lims.view_templates.views import *

from lims.compounds.functions import get_form_choices, process_form
from lims.compounds.forms import Add, Edit, Approve, Update

import pubchempy as pcp
import cirpy as cp
from bs4 import BeautifulSoup
from urllib.request import urlopen

# Item Global Variables
item_type = 'Compound'
item_name = 'Compounds'
table = Compounds
table_name = 'compounds'
name = 'name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Filesystem path
path = os.path.join(app.config['FILE_SYSTEM'], 'structures')
os.makedirs(path, exist_ok=True)
# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

    if request.method == 'POST':
        item_id = table.get_next_id()
        process_form(form, path, item_id)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())  # or Edit
    if request.method == 'POST':
        process_form(form, path, item_id)

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Approve())
    if request.method == 'POST':
        process_form(form, path, item_id)

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Approve())  # or Update
    if request.method == 'POST':
        process_form(form, path, item_id)

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

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
    form = Add()

    item = table.query.get_or_404(item_id)

    drug_class_id = item.drug_class_id
    drug_class = DrugClasses.query.get(drug_class_id)
    drug_class.compound_counts = table.query.filter_by(drug_class_id=drug_class_id).count()
    db.session.commit()

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():

    for drug_class in DrugClasses.query.all():
        drug_class.analyte_counts = 0

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    query = request.args.get('query')
    items = None
    filter_message = None
    kwargs = {}

    # Get compounds with missing drug classes
    missing_drug_class = table.query.filter(table.drug_class_id == None,
            func.length(table.code) == 3).count()
    if query == 'missing-drug-class':
        items = table.query.filter(table.drug_class_id == None,
            func.length(table.code) == 3)
        filter_message = Markup("You are currently viewing non-ISTD items with <b>missing drug class</b>")

    # Get compounds with missing IUPAC names
    missing_iupac = table.query.filter(table.iupac == None).count()
    if query == 'missing-iupac':
        items = table.query.filter(table.iupac == None)
        filter_message = Markup("You are currently viewing items with <b>missing IUPAC name</b>")

    # Set normal alerts for missing drug classes and iupac names
    normal_alerts = [
        (url_for(f'{table_name}.view_list', query='missing-drug-class'), missing_drug_class,
         Markup('with <b>missing drug classes</b>')),
        (url_for(f'{table_name}.view_list', query='missing-iupac'), missing_iupac,
         Markup('with <b>missing IUPAC name</b>')),
    ]

    _view_list = view_items(table, item_name, item_type, table_name, order_by=['code'],
                            filter_message=filter_message, normal_alerts=normal_alerts,
                            items=items, locked_column=False, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    component_ids = [item.component_id for item in CompoundsComponentsReference.query.filter_by(compound_id=item_id)]
    components = Components.query.filter(Components.id.in_(component_ids))
    scope = Scope.query.filter(Scope.component_id.in_(component_ids))

    _view = view_item(item, alias, item_name, table_name,
                      components=components, scope=scope)
    return _view


@blueprint.route(f'/{table_name}/get_identifiers/')
@login_required
def get_identifiers():
    """
    Performs a request to OPSIN (https://opsin.ch.cam.ac.uk/opsin/) API and returns
    the SMILES and InChIKey.

    Using the InChIKey, the molecular formula and exact mass are determined using the
    PubChem API, pubchempy (https://pubchempy.readthedocs.io/en/latest/).

    The InChIKey is also used to get  CAS numbers using the Chemical Identifier Resolver (CIR)
    API (https://cirpy.readthedocs.io/en/latest/).

    In addition, it gets the OPSIN url to display the structure at the bottom of the form.
    It also displays a list of s

    Returns
    -------

    inchikey
    smiles
    formula
    mass
    cas_no
    synonyms
    structure

    """
    inchikey = ""
    smiles = ""
    formula = ""
    mass = ""
    cas_no = ""
    structure = ""
    identifiers = ""
    error = ""
    iupac = request.args.get('iupac', type=str)
    # Replace spaces in the name to URL accepted charaters (space = %20)
    iupac = iupac.strip().replace(" ", "%20")
    # URL for OPSIN API
    url = "https://opsin.ch.cam.ac.uk/opsin/"
    if iupac:
        try:
            # Open URL and get response text as json
            opsin = urlopen(url + iupac)
            opsin_text = json.loads(BeautifulSoup(opsin, "lxml").get_text())

            print(opsin_text)
            # If IUPAC could parsed
            if opsin_text['status'] == 'SUCCESS':
                inchikey = opsin_text['stdinchikey']
                smiles = opsin_text['smiles']
                # Get formula using pubchempy API

                try:
                    formula = pcp.get_properties(
                        'MolecularFormula', inchikey, 'inchikey'
                    )[0]['MolecularFormula']
                    # Get exact mass using pubchempy API
                    mass = pcp.get_properties(
                        'ExactMass', inchikey, 'inchikey'
                    )[0]['ExactMass'][:-3]
                except:
                    error = "Could not complete request"

                try:
                    if len(cp.query(iupac, 'cas')) == 0:
                        cas_no = "No CAS No. found"
                    else:
                        cas_no = cp.query(inchikey, 'cas')[0].value
                        if type(cas_no) is list:
                            cas_no = "; ".join(cas_no)
                except:
                    error = "Could not complete request"

                # Get the stucture url to display in the form.
                structure = f'{url}{iupac}.png'

                # synonyms obtained from pubchempy
                identifiers = ", ".join(pcp.get_compounds(inchikey, 'inchikey')[0].synonyms[:10])
            else:
                error = "IUPAC could not be interpreted"
        except:
            error = "Failed to parse IUPAC name"
    else:
        error = "No IUPAC entered"


    return jsonify(cas_no=cas_no, formula=formula, mass=mass,
                   smiles=smiles, inchikey=inchikey, structure=structure,
                   identifiers=identifiers, error=error)


@blueprint.route('/compounds/get_columns/', methods=['GET', 'POST'])
@login_required
def get_columns():
    form = Import()
    file = request.files.get('file')
    df = pd.read_csv(file)
    columns = df.columns

    print(file.filename)

    choices = [(column, column) for column in columns]
    choices.insert(0, (0, '---'))

    for field in form:
        if field.name not in ['submit', 'csrf_token']:
            field.choices = choices
            if field.name in columns:
                field.data = field.name

    return render_template(f'{table_name}/import.html', form=form, file=file)
