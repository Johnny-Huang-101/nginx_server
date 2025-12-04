
# from lims import admin_only
from lims.models import Agencies, Divisions, Personnel, LitPacketAdminAssays, LitPacketAdminTemplates, \
    LitPacketAdminFiles, Assays, LitPacketAdminAttachments, module_definitions
from lims.lit_packet_admin_attachments.forms import Add, Edit, Approve, Update
from lims.forms import Attach, Import
from lims.view_templates.views import *
import logging

# Set item global variables
item_type = 'Lit Packet Admin Attachment'
item_name = 'Lit Packet Admin Attachments'
table = LitPacketAdminAttachments
table_name = 'lit_packet_admin_attachments'
name = 'attachment_name'  # This selects what property is displayed in the flash messages
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

    form.route.choices = [(0, 'Please select a route')] + [(key, key) for key in module_definitions.keys()]

    if form.route.data and form.route.data != '0':
        attachment_types = AttachmentTypes.query.filter_by(source=form.route.data).all()
        form.attachment_type.choices = [(item.name, item.name) for item in attachment_types]
        form.attachment_type.choices.insert(0, ('', 'Please select a type'))
    else:
        form.attachment_type.choices = [('', 'Please select a type')]

    if form.is_submitted() and form.validate():
        template_id = request.args.get('template_id')
        new_attachment = LitPacketAdminAttachments(
            route=form.route.data,
            attachment_name=form.attachment_name.data,
            attachment_path=form.attachment_path.data,
            attachment_type=form.attachment_type.data,  # Store as string
            lit_admin_template_id=template_id
        )
        db.session.add(new_attachment)
        db.session.commit()
        flash(f'{item_name} has been added successfully!', 'success')
        return redirect(f'/lit_packet_admin_templates/{template_id}')
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
    form = Add()
    item = table.query.get_or_404(item_id)

    form.route.choices = [(0, 'Please select a route')] + [(key, key) for key in module_definitions.keys()]

    # Check if a route is selected and set attachment_type choices
    if form.route.data and form.route.data != '0':
        attachment_types = AttachmentTypes.query.filter_by(source=form.route.data).all()
        form.attachment_type.choices = [(item.name, item.name) for item in attachment_types]
        form.attachment_type.choices.insert(0, ('', 'Please select a type'))
    else:
        form.attachment_type.choices = [('', 'Please select a type')]

    if form.is_submitted() and form.validate():
        template_id = request.args.get('template_id')
        new_attachment = LitPacketAdminAttachments(
            route=form.route.data,
            attachment_name=form.attachment_name.data,
            attachment_path=form.attachment_path.data,
            attachment_type=form.attachment_type.data,  # Store as string
            lit_admin_template_id=template_id
        )

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

    _view = view_item(item, alias, item_name, table_name, **kwargs)
    return _view


@app.route('/get_attachment_types/', methods=['GET'])
def get_attachment_types():
    route = request.args.get('route')
    if route:
        attachment_types = [at_type for at_type in AttachmentTypes.query.filter_by(source=route).all()]
        attachment_types.extend([at_type for at_type in AttachmentTypes.query.filter_by(source='Global')])
        data = [{'id': at.id, 'name': at.name} for at in attachment_types]
    else:
        data = []
    return jsonify(data)

