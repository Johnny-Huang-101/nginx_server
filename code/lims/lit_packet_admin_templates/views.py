# from lims import admin_only
from lims.models import *
from lims.lit_packet_admin_templates.forms import *
from lims.forms import Attach, Import
from lims.view_templates.views import *

# Set item global variables
item_type = 'Lit Packet Admin Template'
item_name = 'Lit Packet Admin Templates'
table = LitPacketAdminTemplates
table_name = 'lit_packet_admin_templates'
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
    form = Add()

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
    kwargs = {'template': 'case_content_form.html',
              'redirect': redirect_to}
    form = UpdateCaseContents()
    # form.case_contents.choices = [('Yes', 'Yes'), ('No', 'No')]
    template_choices = [(t.name, t.name) for t in LitigationPacketTemplates.query.all()]
    template_choices.insert(0, ('None', 'None'))
    form.case_contents.choices = template_choices

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _update


# SWEEP #

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


# END SWEEP #
@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    _view_list = view_items(table, item_name, item_type, table_name)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)
    kwargs['assays'] = LitPacketAdminAssays.query.filter_by(
        lit_admin_template_id=item_id).order_by(LitPacketAdminAssays.lit_admin_sort_order).all()
    kwargs['attachments'] = LitPacketAdminAttachments.query.filter_by(lit_admin_template_id=item_id).all()
    for a in kwargs['attachments']:
        print(a)
        kwargs['attachment_type'] = AttachmentTypes.query.filter_by(name=a.attachment_type)
        for name_a in AttachmentTypes.query.filter_by(name=a.attachment_type):
            print(name_a.name)

    # print()
    alias = getattr(item, name)

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/update_sort_order', methods=['POST', 'GET'])
@login_required
def update_sort_order(item_id):

    # Get item
    item = table.query.get(item_id)

    # Initialize relevant variables
    errors = []
    counter = 1

    # Set exit route
    exit_route = url_for(f'{table_name}.view', item_id=item.id)

    # Create lit_packet_assays dict of id: item for all relevant assays sorted by sort order
    lit_packet_assays = {item.id: item for item in
                         LitPacketAdminAssays.query.filter_by(
                             lit_admin_template_id=item_id).order_by(LitPacketAdminAssays.lit_admin_sort_order).all()}

    # Initialize SortOrder form
    form = SortOrder()

    # Initialize form choices
    choices = [(x, x) for x in range(1, len(lit_packet_assays) + 1)]
    choices.insert(0, (0, 0))

    # Set field.name, field.choices and field.data for all form fields
    for i, assay in enumerate(lit_packet_assays.values(), start=1):
        field_name = f'sort_order_{i}'
        field = getattr(form, field_name, None)

        if field:
            field.choices = choices
            field.id = assay.id
            if request.method != 'POST':
                try:
                    field.data = int(assay.lit_admin_sort_order)
                except TypeError:
                    pass

    # Handle form submission
    if form.is_submitted():
        # Set relevant variables
        numbers_used = []
        dup_order = False

        # Check field data for duplicate sort orders
        for field in form:
            if field.data not in numbers_used:
                # If sort order has not been used, add to numbers_used
                numbers_used.append(field.data)
            elif not field.data and field.data is not None:
                # Handle 0 sort order choice
                flash(Markup(f'ERROR: 0 Cannot be a sort order'), 'error')
                break
            elif field.data is not None:
                # Handle duplicate sort order entries
                dup_order = True
                flash(Markup(f'ERROR: Sort order must be unique, {field.data} used multiple times'), 'error')

        # Handle form validation
        if form.validate() and not dup_order:
            for field in form:
                # Set sort order for each item
                if field.id in lit_packet_assays.keys():
                    lit_packet_assays[field.id].lit_admin_sort_order = field.data
            db.session.commit()

            return redirect(url_for(f'{table_name}.view', item_id=item.id))
        else:
            print('INVALID')
            print(f'ERRORS: {form.errors}')

    return render_template(f'{table_name}/update_sort_order.html', assays=lit_packet_assays, form=form, errors=errors,
                           exit_route=exit_route)
