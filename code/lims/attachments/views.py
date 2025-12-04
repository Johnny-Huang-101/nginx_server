# Application Imports
from lims.models import *
from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.models import module_definitions
import os

# Set item variables
item_type = 'Attachment'
item_name = 'Attachments'
table = Attachments
table_name = 'attachments'
name = 'name'

# Filesystem path
path = os.path.join(current_app.config['FILE_SYSTEM'], table_name)

# Create Blueprint
blueprint = Blueprint(table_name, __name__)

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    if current_user.permissions not in ['Owner', 'Admin', 'ADM-Management']:
        abort(403)

    kwargs = {'modules': module_definitions}

    _view_list = view_items(table, item_name, item_type, table_name,
                            add_item_button=False, export_buttons=False, import_file_button=False,
                            **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    item = table.query.get(item_id)

    # Get the url of the page the use came from to redirect back to
    redirect_url = request.referrer

    # Delete the file if it exists
    try:
        # os.remove(fr"{path}\{item.table_name}\{item.record_id}\{item.name}")
        os.remove(item.path)
    except FileNotFoundError:
        pass

    db.session.delete(item)
    db.session.commit()

    flash(Markup(f'<b>{item.name}</b> successfully deleted'), 'error')

    return redirect(redirect_url)


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_items():

    if current_user.permissions not in ['Owner']:
        abort(403)

    table.query.delete()

    mods = Modifications.query.filter_by(table_name=item_name).all()

    for mod in mods:
        db.session.delete(mod)

    db.session.commit()

    return redirect(url_for(f'{table_name}.view_list'))


@blueprint.route(f'/{table_name}/<item_id>', methods=['GET'])  # HAD TO ADD TO MAKE ATTACHMENTS VIEW_LIST WORK
@login_required
def view(item_id):

    item = Attachments.query.get_or_404(item_id)
    return render_template(
        f'{table_name}/view.html',
        item=item
    )


@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()

    _import = import_items(form, table, table_name, item_name, dtype={'collection_time': str})

    return _import

