from lims.locations.functions import set_location, models_iter, location_dict, get_location_display
from lims.models import ReferenceMaterials, Compounds, Salts, Locations, StatesOfMatter
from lims.reference_materials.forms import Add, Edit, Approve, Update
from lims.reference_materials.functions import get_form_choices, get_set_letter
from lims.forms import Attach, Import
from lims.view_templates.views import *


# Set item global variables
item_type = 'Reference Material'
item_name = 'Reference Materials'
table = ReferenceMaterials
table_name = 'reference_materials'
name = 'name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add())

    if request.method == 'POST':
        if form.is_submitted() and form.validate():

            compound = Compounds.query.get(form.compound_id.data)
            # TODO: after "z" the set should go to "aa"

            # Generate unique set_id. If this is the first reference material for the selected compound
            # set the code to "a" else get the last code and increment letter by 1.
            n_ref_mat = db.session.query(ReferenceMaterials).filter_by(compound_id=form.compound_id.data).\
                order_by(ReferenceMaterials.set.asc()).count()

            if n_ref_mat == 0:
                set_letter = 'a'
            else:
                latest_set_code = db.session.query(ReferenceMaterials).filter_by(compound_id=form.compound_id.data). \
                    order_by(ReferenceMaterials.set.desc()).first().set
                set_letter = get_set_letter(latest_set_code)

            # Calculate correction factor for solid preparations which are salts otherwise
            # assign correction factor as 1.
            state = StatesOfMatter.query.get(form.state_id.data)
            if state.name == 'Solid':
                if form.salt_id.data != 0:
                    salt = Salts.query.get(form.salt_id.data)
                    correction_factor = round(float(compound.mass) / (float(compound.mass) + float(salt.mass)), 4)
                else:
                    correction_factor = 1
            else:
                correction_factor = 1

            if form.cert_of_analysis.data:
                file = form.cert_of_analysis.data
                file.save(os.path.join(current_app.root_path, 'static\CoA', secure_filename(file.filename)))

            kwargs['set'] = set_letter
            kwargs['correction_factor'] = correction_factor
            kwargs['status'] = 'Received'

            set_location(table_name, None, form.location_table.data, form.location_id.data)

            _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
            return _add

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = Approve()
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = get_form_choices(Update())

    if form.is_submitted() and form.validate():
        set_location(table_name, item_id, form.location_table.data, form.location_id.data)

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


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = {'locations': Locations.query.all(), 'models': models_iter, 'location_dict': location_dict}
    _view_list = view_items(table, item_name, item_type, table_name, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)
    kwargs = {'location_display': get_location_display(table_name, item.id)}

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view
