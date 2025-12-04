
from lims.models import *
from lims.forms import Attach, Import
from lims.view_templates.views import *
from sqlalchemy import or_

from lims.components.forms import Add, Edit, Approve, Update
from lims.components.functions import get_form_choices, process_form, get_drug_classes

from lims.drug_classes.forms import Add as DrugClassAdd

# Set item global variables
item_type = 'Component'
item_name = 'Components'
table = Components
table_name = 'components'
name = 'name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = ['component_id']  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'ignore_fields': ignore_fields,  # unique
    'disable_fields': disable_fields,  # unique
}

# Create blueprint
blueprint = Blueprint(table_name, __name__)
# Filesystem path
path = None


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

    # Get the id of the next component to be added
    if request.method == 'POST':
        if form.compound_id.data:
            kwargs.update(process_form(form))
            # Add the component to the database
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
            # Add the drug class to the database
            if kwargs['add_drug_class']:
                drug_class_form = DrugClassAdd()
                drug_class_form.name.data = kwargs['component_drug_class']
                add_item(drug_class_form, DrugClasses, 'Drug Class', 'Drug Classes', 'drug_classes', False, 'name',
                         **default_kwargs.copy())
                # redirect the user to the update form so they can update the drug class information.
                return redirect(url_for("drug_classes.update", item_id=kwargs['drug_class_id']))
            
            if kwargs['compound_component_dict']:
                item = CompoundsComponentsReference(**kwargs['compound_component_dict'])
                db.session.add(item)
                db.session.commit()
            
            return redirect(url_for(f'{table_name}.view', item_id=kwargs['compound_component_dict']['component_id']))

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    kwargs['disable_fields'].append('compound_id')
    form = get_form_choices(Edit())
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    kwargs['disable_fields'].append('compound_id')
    form = get_form_choices(Approve())
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get(item_id)
    #kwargs['disable_fields'].append('compound_id')
    form = get_form_choices(Update())
    compound_ids = [item.compound_id for item in CompoundsComponentsReference.query.filter_by(component_id=item_id)]
    kwargs['compound_id'] = compound_ids
    kwargs['drug_class_name'], kwargs['ranks'], kwargs['rank_str'] = get_drug_classes(compound_ids)

    if request.method == 'POST':
        if form.compound_id.data:
            kwargs.update(process_form(form, component_id=item_id))
            if kwargs['add_drug_class']:
                update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
                drug_class_form = DrugClassAdd()
                drug_class_form.name.data = kwargs['component_drug_class']
                add_item(drug_class_form, DrugClasses, 'Drug Class', 'Drug Classes', 'drug_classes', False, 'name', **default_kwargs.copy())
                return redirect(url_for("drug_classes.update", item_id=kwargs['drug_class_id']))

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

    CompoundsComponentsReference.query.filter_by(component_id=item_id).delete()

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

@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    missing_compounds = CompoundsComponentsReference.query.filter(
        or_(CompoundsComponentsReference.compound_id.is_(None), CompoundsComponentsReference.compound_id == 0)
    ).all()

    _view_list = view_items(table, item_name, item_type, table_name, length=1000, order_by=['name'],
                            missing_compounds=missing_compounds)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    compound_ids = [x.compound_id for x in CompoundsComponentsReference.query.filter_by(component_id=item_id)]
    compounds = Compounds.query.filter(Compounds.id.in_(compound_ids))

    scope = Scope.query.filter_by(component_id=item_id)

    _view = view_item(item, alias, item_name, table_name,
                      compounds=compounds, scope=scope)
    return _view


@blueprint.route(f'/{table_name}/get_drug_classes/', methods=['GET', 'POST'])
@login_required
def get_drug_classes_json():
    compound_ids = request.args.get('compound_id').split(", ")

    drug_class, ranks, rank_str = get_drug_classes(compound_ids)

    return jsonify(drug_class=drug_class, ranks=ranks, rank_str=rank_str)
