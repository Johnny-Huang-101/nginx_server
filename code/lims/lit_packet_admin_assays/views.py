from wtforms import ValidationError

# from lims import admin_only
from lims.models import Agencies, Divisions, Personnel, LitPacketAdminAssays, LitPacketAdminTemplates, \
    LitPacketAdminFiles, Assays
from lims.lit_packet_admin_assays.forms import *
from lims.lit_packet_admin_files.forms import FilesUpdate
from lims.forms import Attach, Import
from lims.view_templates.views import *

# Set item global variables
item_type = 'Lit Packet Admin Assay'
item_name = 'Lit Packet Admin Assays'
table = LitPacketAdminAssays
table_name = 'lit_packet_admin_assays'
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
    kwargs = {'template': template,
              'redirect': '/lit_packet_admin_templates'}
    form = Add()
    template_id = request.args.get('template_id')
    form.lit_admin_template_id.choices = [(t.id, t.name) for t in LitPacketAdminTemplates.query.filter_by(id=template_id)]
    # form.lit_admin_template_id.choices = template_id
    form.name.choices = [(a.assay_name, a.assay_name) for a in Assays.query.all()]

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    if form.is_submitted():
        return redirect(f'/lit_packet_admin_templates/{form.lit_admin_template_id.data}')
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
    kwargs = {'template': 'overview_sheet_form.html',
                          'redirect': redirect_to}
    form = UpdateOverview()
    item = table.query.get_or_404(item_id)

    # Ensure the choices are set
    form.overview_sheet.choices = [('Yes', 'Yes'), ('No', 'No')]

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
    item = table.query.get_or_404(item_id)
    temp_id = item.lit_admin_template_id
    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return redirect(f'/lit_packet_admin_templates/{temp_id}')


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
    item = table.query.get_or_404(item_id)
    kwargs = default_kwargs.copy()

    alias = getattr(item, name)
    kwargs['template_id'] = item.lit_admin_template_id
    for t in LitPacketAdminTemplates.query.filter_by(id=kwargs['template_id']):
        kwargs['template_name'] = t.name
    # Sort files by sort order
    kwargs['files'] = LitPacketAdminFiles.query.filter_by(
        lit_packet_admin_id=item_id).order_by(LitPacketAdminFiles.batch_record_sort_order).all()

    form = FilesUpdate()
    form.lit_packet_admin_id.choices = [(t.id, t.name) for t in LitPacketAdminAssays.query.all()]
    file_choices = [('Yes', 'Yes'), ('No', 'No')]
    form.use_file.choices = file_choices
    redact_type_choices = [('Redact', 'Redact'), ('Delete Pages', 'Delete Pages'), ('None', 'None')]
    form.redact_type.choices = redact_type_choices
    kwargs['form'] = form

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


# this route will fetch file data and return it as JSON for file update modal
@blueprint.route(f'/{table_name}/get_file_data', methods=['GET'])
@login_required
def get_file_data():
    file_id = request.args.get('id', type=int)
    file = LitPacketAdminFiles.query.get_or_404(file_id)
    file_data = {
        'file_name': file.file_name,
        'use_file': file.use_file,
        'redact_type': file.redact_type,
        'update_url': url_for('lit_packet_admin_assays.update_file', file_id=file_id)
    }

    return jsonify(file_data)


# this route will be responsible for handling the form submission when updating LitPacketAdminFiles


@blueprint.route(f'/{table_name}/<int:file_id>/update_file', methods=['POST'])
@login_required
def update_file(file_id):
    file = LitPacketAdminFiles.query.get_or_404(file_id)
    form = FilesUpdate()

    # Set the choices for the select fields
    file_choices = [('Yes', 'Yes'), ('No', 'No')]
    form.use_file.choices = file_choices
    redact_type_choices = [('Redact', 'Redact'), ('Delete Pages', 'Delete Pages'), ('None', 'None')]
    form.redact_type.choices = redact_type_choices

    if form.is_submitted() and form.validate():
        file.use_file = form.use_file.data
        print(file.use_file.data)
        file.redact_type = form.redact_type.data
        print(file.redact_type.data)
        db.session.commit()
        flash('File updated successfully', 'success')

        return redirect(url_for('lit_packet_admin_assays.view', item_id=file.lit_packet_admin_id))

    flash('Error updating file', 'danger')

    return redirect(url_for('lit_packet_admin_assays.view', item_id=file.lit_packet_admin_id))


@blueprint.route(f'/{table_name}/<int:item_id>/update_sort_order', methods=['POST', 'GET'])
@login_required
def update_sort_order(item_id):

    # Get item
    item = table.query.get(item_id)

    # Initialize relevant varables
    errors = []
    counter = 1

    # Set exit route
    exit_route = url_for(f'{table_name}.view', item_id=item.id)

    # Create id: item dict of relevant LitPacketAdminFiles
    lit_packet_files = {item.id: item for item in
                        LitPacketAdminFiles.query.filter_by(
                            lit_packet_admin_id=item_id).order_by(LitPacketAdminFiles.batch_record_sort_order).all()}

    # Initialize SortOrder form
    form = SortOrder()

    # Set form choices
    choices = [(x, x) for x in range(1, len(lit_packet_files) + 1)]
    choices.insert(0, (0, 0))

    # Set field names, choices and data
    for i, file in enumerate(lit_packet_files.values(), start=1):
        field_name = f'sort_order_{i}'
        field = getattr(form, field_name, None)

        if field:
            field.choices = choices
            field.id = file.id
            if request.method != 'POST':
                try:
                    field.data = int(file.batch_record_sort_order)
                except TypeError:
                    pass

    # Handle form submission
    if form.is_submitted():
        # Initialize relevant variables
        numbers_used = []
        dup_order = False

        # Get all form data
        for field in form:
            # Check if sort order position has already been used
            if field.data not in numbers_used:
                # Add sort order to numbers_used
                numbers_used.append(field.data)

            # Handle 0 submission
            elif not field.data and field.data is not None:
                flash(Markup(f'ERROR: 0 Cannot be a sort order'), 'error')
                break

            # Handle duplicate sort order
            elif field.data is not None:
                # Return error for duplicate sort order
                dup_order = True
                flash(Markup(f'ERROR: Sort order must be unique, {field.data} used multiple times'), 'error')

        # Handle form validation
        if form.validate() and not dup_order:
            for field in form:
                # Set sort order for each item
                if field.id in lit_packet_files.keys():
                    lit_packet_files[field.id].batch_record_sort_order = field.data
            db.session.commit()

            return redirect(url_for(f'{table_name}.view', item_id=item.id))
        else:
            print('INVALID')
            print(f'ERRORS: {form.errors}')

    return render_template(f'{table_name}/update_sort_order.html', files=lit_packet_files, form=form, errors=errors,
                           exit_route=exit_route)
