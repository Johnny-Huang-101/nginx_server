import qrcode
from wtforms.validators import DataRequired, Optional
from sqlalchemy import or_

from lims.containers.forms import Add, Edit, Approve, Update
from lims.containers.functions import get_form_choices, process_form, get_division_choices, get_personnel_choices
from lims.forms import Attach, Import
from lims.models import *
from lims.view_templates.views import *
from lims.locations.functions import get_location_choices
from lims.labels import print_label, fields_dict
from lims.evidence_comments.forms import Base as Form
from lims.evidence_comments.functions import get_form_choices as get_evidence_comment_choices, add_comments, \
    delete_comments
from lims.comment_instances.forms import Add as CommentAdd
from lims.comment_instances.functions import get_form_choices as get_comment_form
import base64

# Set item Global Variables
item_type = 'Container'
item_name = 'Containers'
table = Containers
table_name = 'containers'
name = 'accession_number'
requires_approval = True  # controls whether the approval process is required
ignore_fields = []  # fields not added to the modification table
disable_fields = []
template = 'form.html'
redirect_to = 'view'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'ignore_fields': ignore_fields,
    'disable_fields': disable_fields
}

# Create Blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    # Request case id if adding a container is through the add case workflow
    # case_id will be None if added through the Containers table
    case_id = request.args.get('case_id', type=int)
    # If the user exits the form and case_id has been passed in as a URL arg, return the user to the case.
    exit_route = None
    if case_id:
        kwargs['case_number'] = Cases.query.get(case_id).case_number
        exit_route = url_for('cases.view', item_id=case_id, view_only=True)

    form = get_form_choices(Add(), case_id)

    # Boolean used to track if user is investigator and if submission route is evidence locker
    is_inv = False
    is_locker = False

    evidence_comment_form = get_evidence_comment_choices(Form())
    kwargs['evidence_comment_form'] = evidence_comment_form

    if request.method == 'POST':

        form = get_form_choices(Add(), case_id=form.case_id.data, division_id=form.division_id.data,
                                location_type=form.location_type.data)

        # TODO Vanilla form
        for field in form:
            print(f"{field.name} = {field.data}")

        if form.is_submitted() and form.validate():

            # Reinitialize form choices for select fields

            kwargs.update(process_form(form, 'Add'))

            # If evidence locker selected, set occupied status to True
            if form.location_type.data == 'Evidence Lockers':
                is_locker = True
                locker = EvidenceLockers.query.filter_by(equipment_id=form.submission_route.data).first()
                locker.occupied = True
            # If evidence comments are entered, add them to the EvidenceComments table.
            if form.evidence_comments.data:
                add_comments(form, kwargs['accession_number'], 'Container')

            # print(71)
            # if a new container is added to the case, set the case to pending.
            case = Cases.query.get(form.case_id.data)
            case.pending_submitter = current_user.initials
            case.db_status = 'Pending'

            attributes_list = []

            # Accessioning area printer
            if request.remote_addr == '10.63.21.58':
                printer = r'\\OCMEG9M020.medex.sfgov.org\BS01 - Accessioning'
            elif request.remote_addr == '10.63.21.64':
                printer = r'\\OCMEG9M022.medex.sfgov.org\BS11 - Accessioning'
            elif current_user.permissions == 'INV':
                # printer = current_user.default_printer
                printer = r'\\OCMEG9M042.medex.sfgov.org\DYMO LabelWriter 450 Turbo INV'
                is_inv = True
            else:
                printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'

            # Add the container and then redirect to adding specimens or the case list
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
            container = table.query.order_by(Containers.id.desc()).first()

            if form.comments.data is not None:
                comment_form = get_comment_form(CommentAdd(), comment_item_id=container.id, comment_item_type='Containers')
                comment_form.comment_text.data = form.comments.data
                comment_form.submit.data = True
                comment_kwargs = {'comment_type': 'Manual'}
                add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 
                         'comment_instances', False, ['comment_type', 'comment_text'], **comment_kwargs)


            if form.container_type_id.data == ContainerTypes.query.filter_by(name='No Container').first().id:
                print('DO NOT PRINT LABEL')

                if 'submit_exit' not in request.form:
                    print(f"GOING TO SPECIMENS NO CONTAINER ROUTE")
                    return jsonify([(None, None, None, None, url_for('specimens.add',
                                                                     case_id=form.case_id.data,
                                                                     container_id=kwargs['container_id'],
                                                                     specimen_n=1,
                                                                     custody_type=form.location_type.data,
                                                                     custody=form.submission_route.data,
                                                                     submission_time=form.submission_time.data,
                                                                     submission_date=form.submission_date.data,
                                                                     discipline=form.discipline.data,
                                                                     
                                                                     ))])
                else:
                    return jsonify([(None, None, None, None,
                                     url_for(f'cases.view', item_id=case.id, view_only=True, ))])

            else:
                container = Containers.query.filter_by(accession_number=kwargs['accession_number']).first()
                print(f"DONE PRINT LABEL")
                qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'container{container.id}.png')
                qrcode.make(f'containers: {container.id}').save(qr_path)

                with open(qr_path, "rb") as qr_file:
                    qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                label_attributes = fields_dict['container']
                label_attributes['CASE_NUM'] = case.case_number
                label_attributes['ACC_NUM'] = container.accession_number
                label_attributes['CODE'] = f'[{container.type.code}]'
                label_attributes['TYPE'] = container.type.name
                label_attributes['QR'] = qr_encoded
                label_attributes['DISCIPLINE'] = container.discipline

                attributes_list.append(label_attributes.copy())

                if is_locker and is_inv:
                    label_attributes = fields_dict['container']
                    label_attributes['CASE_NUM'] = container.accession_number
                    label_attributes['ACC_NUM'] = container.submission_route
                    label_attributes['CODE'] = ''
                    label_attributes['TYPE'] = ''
                    label_attributes['QR'] = qr_encoded
                    label_attributes['DISCIPLINE'] = ''

                    attributes_list.append(label_attributes.copy())

                if 'submit_exit' not in request.form:
                    print(f"GOING TO SPECIMENS")
                    return jsonify([(attributes_list, printer, None, None, url_for('specimens.add',
                                                                                   case_id=form.case_id.data,
                                                                                   container_id=kwargs['container_id'],
                                                                                   specimen_n=1,
                                                                                   custody_type=form.location_type.data,
                                                                                   custody=form.submission_route.data,
                                                                                   submission_time=form.submission_time.data,
                                                                                   submission_date=form.submission_date.data,
                                                                                   discipline=form.discipline.data,
                                                                                   
                                                                                   ))])
                else:
                    return jsonify([(attributes_list, printer, None, None,
                                     url_for(f'cases.view', item_id=case.id, view_only=True, ))])
                # print_label(printer, attributes_list)
        else:
            print(f"FORM NOT VALID with {form.errors}")
            form = get_form_choices(form, case_id=form.case_id.data, division_id=form.division_id.data,
                                    submission_route_type=form.submission_route_type.data,
                                    location_type=form.location_type.data)

            return jsonify({'success': False, 'errors': form.errors}), 400

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                    exit_route=exit_route, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    kwargs['locking'] = False
    item = table.query.get_or_404(item_id)
    form = Edit()

    evidence_comment_form = get_evidence_comment_choices(Form())
    kwargs['evidence_comment_form'] = evidence_comment_form
    kwargs['division_id'] = item.submitter.division.id
    kwargs['disable_fields'] = ['case_id']

    kwargs['comments'] = [comment for comment in CommentInstances.query.filter_by(comment_item_type='Containers',
                                                                                  comment_item_id=item.id)]

    if request.method == 'POST':
        form = get_form_choices(form, case_id=form.case_id.data, division_id=form.division_id.data,
                                submission_route_type=form.submission_route_type.data,
                                location_type=form.location_type.data,
                                item=item)
        if form.is_submitted() and form.validate():
            kwargs.update(process_form(form))
            if form.evidence_comments.data:
                add_comments(form, item.accession_number, 'Container')

            edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

            return redirect(url_for(f"cases.view", item_id=item.case_id))

    if request.method == 'GET':
        form = get_form_choices(form, case_id=item.case_id, division_id=item.submitter.division_id,
                                submission_route_type=item.submission_route_type, location_type=item.location_type,
                                item=item)
        if item.evidence_comments:
            kwargs['evidence_comments'] = "\n".join(item.evidence_comments.split("; "))

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    kwargs['redirect_to'] = request.referrer
    kwargs['locking'] = False
    item = table.query.get_or_404(item_id)
    form = Approve()

    evidence_comment_form = get_evidence_comment_choices(Form())
    kwargs['evidence_comment_form'] = evidence_comment_form
    kwargs['division_id'] = item.submitter.division.id
    kwargs['disable_fields'] = ['case_id']

    kwargs['comments'] = [comment for comment in CommentInstances.query.filter_by(comment_item_type='Containers',
                                                                                  comment_item_id=item.id)]

    if request.method == 'POST':
        form = get_form_choices(form, case_id=form.case_id.data, division_id=form.division_id.data,
                                submission_route_type=form.submission_route_type.data,
                                location_type=form.location_type.data,
                                item=item)
        if form.is_submitted() and form.validate():
            kwargs.update(process_form(form))

            if item.location_type is not None:
                if item.location_type == 'Evidence Lockers':
                    EvidenceLockers.query.filter_by(equipment_id=item.submission_route).first().occupied = False

            if form.evidence_comments.data:
                add_comments(form, item.accession_number, 'Container')

            approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

            case = Cases.query.get(item.case.id)
            case_id = case.id

            case_pending = Modifications.query.filter_by(table_name='Cases', record_id=case_id,
                                                         status='Pending').count()

            # If the container was not fully approved, set the pending_submitter of the case to the current user only if
            # the case details have been approved
            if item.pending_submitter:
                if not case_pending:
                    case.pending_submitter = item.pending_submitter

            pending_containers = Containers.query.filter(sa.and_(Containers.case_id == case_id,
                                                                 Containers.pending_submitter != None)).count()
            pending_specimens = Specimens.query.filter(sa.and_(Specimens.case_id == case_id,
                                                               Specimens.pending_submitter != None)).count()

            if not case_pending and not pending_containers and not pending_specimens:

                # if any discipline requested set status to "Need Test Addition" Only if there is specimens, no case_status and
                # no existing tests this should preserve the case status if updates are made to the case later on after testing
                # has been added
                if (case.testing_requested and not case.case_status and Specimens.query.filter_by(
                        case_id=case_id).count()
                        and not Tests.query.filter_by(case_id=case_id).count()):
                    case.case_status = 'Need Test Addition'

                unlock_item(case_id, Cases, 'case_number', request.referrer)
                locked_containers = Containers.query.filter_by(case_id=case_id, locked_by=current_user.initials)
                for container in locked_containers:
                    unlock_item(container.id, Containers, 'accession_number', request.referrer)

                locked_specimens = Specimens.query.filter_by(case_id=case_id, locked_by=current_user.initials)
                for specimen in locked_specimens:
                    unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)

                case.db_status = 'Active'
                case.pending_submitter = None
                case.review_discipline = None

                # Set evidence_locker occupied to false on approval
                # Get the equipment IDs for all security lockers
                for container in Containers.query.filter_by(case_id=case.id, location_type='Evidence Lockers'):
                    evidence_locker = EvidenceLockers.query.filter_by(
                        equipment_id=container.submission_route).first()
                    evidence_locker.occupied = False

                db.session.commit()

                # return redirect(url_for('tests.add', case_id=item.case.id))

            return redirect(url_for('cases.view', item_id=item.case.id))

    if request.method == 'GET':
        form = get_form_choices(form, case_id=item.case_id, division_id=item.submitter.division_id,
                                submission_route_type=item.submission_route_type, location_type=item.location_type,
                                item=item, submission_route=item.submission_route)

        for field in form:
            print(f"{field.name} = {field.data}")

        if item.evidence_comments:
            kwargs['evidence_comments'] = "\n".join(item.evidence_comments.split("; "))

        if form.submission_route.data:
            kwargs['submission_route'] = form.submission_route.data

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    item = table.query.get_or_404(item_id)
    form = Update()

    # Set the evidence comment form
    kwargs['evidence_comment_form'] = get_evidence_comment_choices(Form())

    kwargs['division_id'] = item.submitter.division.id
    kwargs['disable_fields'] = ['case_id']

    kwargs['comments'] = [comment for comment in CommentInstances.query.filter_by(comment_item_type='Containers',
                                                                                  comment_item_id=item.id)]

    if request.method == 'POST':
        form = get_form_choices(form, case_id=item.case_id, division_id=item.submitter.division_id,
                                submission_route_type=item.submission_route_type, location_type=item.location_type,
                                item=item)

        if form.is_submitted() and form.validate():
            kwargs.update(process_form(form))
            if form.evidence_comments.data:
                add_comments(form, item.accession_number, 'Container')

            update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

            if item.pending_submitter:
                item.case.pending_submitter = current_user.initials
                item.case.db_status = 'Pending'
                db.session.commit()

            return redirect(url_for(f"cases.view", item_id=item.case_id))

    if request.method == 'GET':
        form = get_form_choices(form, case_id=item.case_id, division_id=item.submitter.division_id,
                                submission_route_type=item.submission_route_type, location_type=item.location_type,
                                item=item, submission_route=item.submission_route)
        if item.evidence_comments:
            kwargs['evidence_comments'] = "\n".join(item.evidence_comments.split("; "))

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _update


@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):
    _unlock = unlock_item(item_id, table, name)

    return _unlock


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
    # Since admin removals don't go through the approve_remove function, we also need to
    # have the decrement code here
    if current_user.permissions in ['Admin', 'Owner']:
        case = table.query.get(item_id).case
        case.n_containers -= 1

    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove


@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    case = table.query.get(item_id).case
    case.n_containers -= 1

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
    # if the container is restores, increment n_containers for the case
    case = table.query.get(item_id).case
    case.n_containers += 1

    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    item = Containers.query.get_or_404(item_id)
    # case = Cases.query.get_or_404(item.case_id)
    # case.n_containers -= 1
    delete_comments(item_id, item_type)

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
    _import = import_items(form, table, table_name, item_name, dtype={'submission_time': str})

    return _import


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():
    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    redirect_url = request.args.get('redirect_url')
    alias = request.args.get('alias')

    item = table.query.get_or_404(item_id)
    view_only = True

    if form.is_submitted():
        redirect_url = url_for(f"cases.view", item_id=item.case_id, view_only=view_only)
 
    
    _attach = attach_items(form, item_id, table, item_name, table_name, name, redirect_url=redirect_url, alias=alias)

    return _attach


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):
    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = default_kwargs.copy()

    kwargs['discipline'] = disciplines
    items = None
    query = request.args.get('query')
    query_type = request.args.get('query_type')

    if query_type == 'discipline':
        if query:
            items = Containers.query.filter_by(discipline=query)

    _view_list = view_items(table, item_name, item_type, table_name, items=items, query=query, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    view_only = request.args.get('view_only', type=bool, default=None)

    item = Containers.query.get_or_404(item_id)

    if view_only is None:
        view_only = False
        if item.locked and item.locked_by != current_user.initials:
            view_only = True
        if item.pending_submitter:  # and item.pending_submitter != current_user.initials:
            view_only = True

    specimens = Specimens.query.filter_by(container_id=item.id)

    pending_submitters = {}
    # Get pending modifications for alerts
    pending_mods = Modifications.query.filter_by(record_id=str(item_id),
                                                 status='Pending',
                                                 table_name=item_name).all()
    # This will show which fields are pending changes
    pending_mods = [mod for mod in pending_mods]
    # This says how many fields are pending changes
    n_pending = len(pending_mods)
    for mod in pending_mods:
        pending_submitters[mod.field] = mod.submitter.initials

    evidence_comments = None
    if item.evidence_comments:
        evidence_comments = item.evidence_comments.split("\n")

    _view = view_item(item, alias, item_name, table_name,
                      n_pending=n_pending,
                      specimens=specimens,
                      pending_submitters=pending_submitters,
                      evidence_comments=evidence_comments,
                      default_header=False,
                      view_only=view_only
                      )
    return _view


# @blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
# @login_required
# def view(item_id):
#
#     item = Containers.query.get_or_404(item_id)
#     view_only = False
#     if item.locked and item.locked_by != current_user.initials:
#         view_only = True
#     if item.pending_submitter: #and item.pending_submitter != current_user.initials:
#         view_only = True
#
#     name = getattr(item, 'accession_number')
#     specimens = Specimens.query.filter_by(container_id=item.id)
#     attachments = db.session.query(Attachments).filter_by(table_name=item_name, record_id=item_id)
#     delete_mod = Modifications.query.filter_by(record_id=item_id, event='DELETE',
#                                                status='Approved', table_name=item_name).first()
#
#     mods = Modifications.query.filter_by(record_id=item_id, table_name=item_name). \
#         order_by(Modifications.submitted_date.desc())
#
#     # Generate modification tooltips (hover behaviour) for item fields
#     # tooltips = {}
#     # for mod in mods:
#     #     if mod.field != "Reason":
#     #         if mod.original_value == "":
#     #             original_value = "[None]"
#     #         else:
#     #             original_value = mod.original_value
#     #         if mod.new_value == "":
#     #             new_value = "[None]"
#     #         else:
#     #             new_value = mod.new_value
#     #
#     #         tooltips[mod.field] = f"{original_value} > {new_value}<br>" \
#     #                               f"({mod.submitter.initials} > {mod.reviewer.initials})"
#     #
#     # print(tooltips)
#     pending_submitters = {}
#     # Get pending modifications for alerts
#     pending_mods = Modifications.query.filter_by(record_id=item_id,
#                                                  status='Pending',
#                                                  table_name=item_name).all()
#
#     # This will show which fields are pending changes
#     pending_mods = [mod for mod in pending_mods]
#     # This says how many fields are pending changes
#     n_pending = len(pending_mods)
#     for mod in pending_mods:
#         pending_submitters[mod.field] = mod.submitter.initials
#     print(pending_submitters)
#
#     # if item.db_status == 'Pending':
#     #     pass
#
#
#
#     return render_template(
#         f'{table_name}/view.html',
#         item=item,
#         table_name=table_name,
#         name=name,
#         specimens=specimens,
#         mods=mods,
#         attachments=attachments,
#         pending_submitters=pending_submitters,
#         delete_mod=delete_mod,
#         #tooltips=tooltips,
#         n_pending=n_pending,
#         pending_mods=pending_mods,
#         view_only=view_only,
#     )


@blueprint.route(f'/{table_name}/get_divisions/', methods=['GET', 'POST'])
@login_required
def get_divisions():
    case_id = request.args.get('case_id', type=int)
    response = get_division_choices(case_id)
    return response


@blueprint.route(f'/{table_name}/get_personnel/', methods=['GET', 'POST'])
@login_required
def get_personnel():
    division_id = request.args.get('division_id', type=int)
    response = get_personnel_choices(division_id)
    return response


@blueprint.route(f'/{table_name}/set_submitter/', methods=['GET', 'POST'])
@login_required
def set_submitter():
    # Get container submitter and populate form.submitted_by
    try:
        item_id = request.args.get('id')
        submitter = table.query.get(item_id).submitted_by
    except AttributeError:
        if current_user.personnel.division_id != Divisions.query.filter_by(abbreviation='FLD').first().id:
            submitter = current_user.personnel_id
        else:
            submitter = None

    return jsonify({'selected_id': submitter})


@blueprint.route(f'/{table_name}/get_locations/', methods=['GET', 'POST'])
@login_required
def get_locations():
    location_type = request.args.get('location_type')
    response = get_location_choices(location_type, store_as='name')

    return response


# def get_locations():
#
#     # Get location type form request
#     location_type = request.args.get('location_type')
#     print(location_type)
#
#     # Get relevant table
#     table_choice = tables.get(location_type)
#
#     # Initialize choices
#     choices = []
#     if table_choice:
#         # If choice is evidence locker, get lockers that are not occupied
#         if table_choice == EvidenceLockers:
#             items = table_choice.query.filter(or_(EvidenceLockers.occupied != True, EvidenceLockers.occupied == None))
#         else:
#             # Get all items if not evidence locker
#             items = table_choice.query
#         if items.count() != 0:
#             choices.append({'id': "", 'name': f'Please select a {location_type.lower()}'})
#             for item in items:
#                 choice = {}
#                 name = None
#                 if not hasattr(item, 'status_id'):
#                     if hasattr(item, 'status'):
#                         if item.status == 'Active':
#                             name = getattr(item, aliases[location_type])
#                 elif hasattr(item, 'status_id'):
#                     if getattr(item, 'status_id') == 1:
#                         name = getattr(item, aliases[location_type])
#                 else:
#                     name = getattr(item, aliases[location_type])
#                 if name:
#                     choice['id'] = name
#                     choice['name'] = name
#                     choices.append(choice)
#         else:
#             choices.append({'id': "", 'name': 'This location type has no items'})
#     else:
#         choices.append({'id': "", 'name': 'No location type selected'})
#
#     return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/<int:item_id>/print')
@login_required
def print_container_label(item_id):
    # Get current specimen
    item = table.query.get(item_id)
    case = Cases.query.get(item.case.id)
    from_autopsy = False

    attributes_list = []

    # Accessioning area printer
    if request.remote_addr == '10.63.21.58':
        printer = r'\\OCMEG9M020.medex.sfgov.org\BS01 - Accessioning'

    elif request.remote_addr == '10.63.21.64':
        printer = r'\\OCMEG9M022.medex.sfgov.org\BS11 - Accessioning'
    elif 'MED-Autopsy' in current_user.permissions:
        printer = r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo'
        from_autopsy = True
    elif current_user.permissions == 'INV':
        # printer = current_user.default_printer
        printer = r'\\OCMEG9M042.medex.sfgov.org\DYMO LabelWriter 450 Turbo INV';
    else:
        printer = r'\\OCMEG9M012.medex.sfgov.org\BS02 - Accessioning'

    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'container{item.id}.png')
    qrcode.make(f'containers: {item.id}').save(qr_path)

    with open(qr_path, "rb") as qr_file:
        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

    label_attributes = fields_dict['container']
    label_attributes['CASE_NUM'] = case.case_number
    label_attributes['ACC_NUM'] = item.accession_number
    label_attributes['CODE'] = f'[{item.type.code}]'
    label_attributes['TYPE'] = item.type.name
    label_attributes['QR'] = qr_encoded
    label_attributes['DISCIPLINE'] = item.discipline

    attributes_list.append(label_attributes.copy())

    if from_autopsy:

        return jsonify(attributes_list, printer, True, 1, url_for(f'cases.autopsy_view', ))
        # print_label(printer, attributes_list, True, 1)
        # return redirect(url_for(f'cases.autopsy_view'))

    else:

        return jsonify(attributes_list, printer, None, None,
                       url_for(f'{table_name}.view', item_id=item_id, ))
    #     print_label(printer, attributes_list)

    # return redirect(url_for(f'{table_name}.view', item_id=item_id))
