from lims.models import *
from lims.view_templates.views import *
from lims.forms import Attach, Import
from lims.user_log.forms import Add, Edit, Approve, Update, CustomExport

import sqlalchemy as sa
import pandas as pd
import os

# Set item global variables
item_type = 'Log Entry'
item_name = 'User Log'
table = UserLog
table_name = 'user_log'
name = 'id'  # This selects what property is displayed in the flash messages
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
    kwargs = default_kwargs.copy()
    form = Update()

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
@login_required
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
    _view_list = view_items(table, item_name, item_type, table_name,
                            admin_only=True, import_file_button=False, add_item_button=False)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name, admin_only=True)
    return _view


@blueprint.route(f'/{table_name}/custom_export', methods=['GET', 'POST'])
@login_required
def custom_export():
    # Initialize custom export form
    form = render_form(CustomExport())
    errors = {}

    # Only populate the user list with users in the UserLog table
    users = [(user.user, user.user) for user in UserLog.query
        .with_entities(UserLog.user)  # Select only the UserLog.user column
        .group_by(UserLog.user)  # Group by UserLog.user to satisfy SQL Server
        .distinct()  # Ensure distinct users
        .all()]

    users.insert(0, ("All Users", 'All Users'))
    form.user.choices = users
    # Initialize start/end_date
    selected_user = form.user.data
    start_date = form.start_date.data
    end_date = form.end_date.data

    if form.is_submitted():

        data = table.query
        if selected_user != 'All Users':
            data = data.filter_by(user=selected_user)
        if start_date:
            data = data.filter(table.date_accessed >= start_date)
        if end_date:
            # For end_date we need to add +1 day to the entered end_date to ensure
            # data that occurred on the selected end_date is included.
            data = data.filter(table.date_accessed <= end_date + timedelta(days=1))

        if data.count():
            df = pd.DataFrame([item.__dict__ for item in data])
            df = df[['id', 'user', 'route', 'view_function', 'date_accessed']]
            file_name = f"{selected_user}_Log_{datetime.now().strftime('%Y-%m-%d_%H%M')}.csv"
            path = os.path.join(app.config['FILE_SYSTEM'], 'exports', file_name)
            df.to_csv(path, index=False, date_format='%m/%d/%Y %H:%M')

            return send_file(path,
                             mimetype='"text/csv"',
                             as_attachment=True,
                             download_name=file_name
                             )
        else:
            flash('There is no data matching these filter criteria', 'error')

    return render_template(f'{table_name}/form.html',
                           form=form,
                           errors=errors,
                           errors_json=json.dumps(errors),
                           function='Custom Export',
                           required_fields=json.dumps([]),
                           item_name='User Log',
                           pending_fields=json.dumps([]),
                           default_header=True)


