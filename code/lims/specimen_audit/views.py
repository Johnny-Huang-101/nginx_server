from lims.models import SpecimenAudit, Specimens
from lims.view_templates.views import *
from lims.forms import Import

# Set item variables
item_type = 'Specimen Audit'
item_name = 'Specimen Audit'
table = SpecimenAudit
table_name = 'specimen_audit'
name = 'id'
requires_approval = False  # controls whether the approval process is required
ignore_fields = []  # fields not added to the modification table
disable_fields = []
template = 'form.html'
redirect_to = 'view.html'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'ignore_fields': ignore_fields,
    'disable_fields': disable_fields
}
blueprint = Blueprint('specimen_audit', __name__)


def add_specimen_audit(specimen_id, destination, reason, o_time, status, created_by=None, modified_by=None,
                       db_status='Active'):

    item = {
        'specimen_id': specimen_id,
        'destination': destination,
        'reason': reason,
        'o_time': o_time,
        'status': status,
        'db_status': db_status,
        'created_by': created_by,
        'modified_by': modified_by,
    }

    # specimen = Specimens.query.get(specimen_id)

    db.session.add(SpecimenAudit(**item))
    db.session.commit()


##### ADD #####

# @blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
# @login_required
# def add():
#
#     form = Add()
#     status = 'Approved'
#
#     _add = add_item(form, table, item_type, item_name, table_name, status, name)
#
#     return _add

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    _view_list = view_items(table, item_name, item_type, table_name,
                            add_item_button=False)

    return _view_list


##### VIEW #####

@blueprint.route(f'/{table_name}/<item_id>', methods=['GET'])
@login_required
def view(item_id):

    item = table.query.get_or_404(item_id)

    return render_template(
        f'{table_name}/view.html',
        item=item
    )


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    item = SpecimenAudit.query.get(item_id)
    specimen = Specimens.query.get(item.specimen_id)
    form = None
    # db.session.commit()

    delete_item(form, item_id, table, table_name, item_name, name)

    updated_custody = SpecimenAudit.query.filter_by(specimen_id=specimen.id)\
        .order_by(SpecimenAudit.o_time.desc()).first()

    specimen.custody = updated_custody.destination
    print(f'NEW CUSTODY: {specimen.custody}')
    db.session.commit()

    print(f'CUSTODY: {updated_custody}')

    return redirect(url_for(f'{table_name}.view_list'))


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():

    SpecimenAudit.query.delete()

    db.session.commit()

    return redirect(url_for(f'{table_name}.view_list'))


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


@blueprint.route(f'/{table_name}/<int:item_id>/remove', methods=['GET', 'POST'])
@login_required
def remove(item_id):

    redirect_url = request.form.get('redirect')

    remove_item(item_id, table, table_name, item_name, name)

    if redirect_url:
        return redirect(redirect_url)
    else:
        return redirect(url_for(f'{table_name}.view_list'))
