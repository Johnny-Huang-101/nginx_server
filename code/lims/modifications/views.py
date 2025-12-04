
from lims.view_templates.views import *
from lims import db
from lims.models import module_definitions, Specimens, Containers, Users, Scope
from lims.forms import Import

item_type = 'Modifications'
item_name = 'Modifications'
table = Modifications
table_name = 'modifications'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}


blueprint = Blueprint('modifications',__name__)

##### VIEW MODIFICATIONS #####

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required

def view_list(result=None):
    if current_user.permissions not in ['Owner', 'Admin', 'ADM-Management']:
        abort(403)

    kwargs = {'modules': module_definitions}

    # Specimens.query.get(258).container_id = 132
    #
    # Containers.query.get(185).n_specimens = 1
    # Containers.query.get(185).n_specimens_submitted = 1
    #
    # db.session.commit()

    # Users.query.get(46).personnel_id = 193
    # db.session.commit()

    _view_list = view_items(table, item_name, item_type, table_name, add_item_button=False, **kwargs)

    return _view_list


@blueprint.route('/modifications/delete_all', methods=['GET', 'POST'])
@login_required
def delete_items():

    Modifications.query.delete()

    db.session.commit()

    return redirect(url_for('modifications.view_list'))

@blueprint.route('/modifications/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):

    mod = Modifications.query.get_or_404(item_id)

    db.session.delete(mod)
    db.session.commit()
    return redirect(url_for('modifications.view_list'))

@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():

    _export = export_items(table)

    return _export

@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    _import = import_items(form, table, table_name, item_name)

    return _import


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = getattr(item, name)

    _view = view_item(item, alias, item_name, table_name)
    return _view