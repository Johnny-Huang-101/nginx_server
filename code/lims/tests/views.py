import qrcode
from sqlalchemy import and_, or_

from lims.labels import fields_dict
from lims.models import *
from lims.tests.forms import Add, Edit, Approve, Update, Cancel, Reinstate
from lims.comment_instances.forms import Add as AddComment
from lims.comment_instances.functions import get_form_choices as get_comment_form_choices
from lims.forms import Import, Attach
from lims.tests.functions import get_form_choices
from lims.results.forms import UpdateStatus
from lims.view_templates.views import *
import base64

# Set item global variables
item_type = 'Test(s)'
item_name = 'Tests'
table = Tests
table_name = 'tests'
name = 'test_name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
# fields not added to the modification table
ignore_fields = ['toxicology', 'biochemistry', 'histology', 'external',
                 'toxicology_requested', 'biochemistry_requested', 'histology_requested',
                 'external_requested', 'discipline']
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'view'
default_kwargs = {'template': template,
                  'redirect': redirect_to,
                  'ignore_fields': ignore_fields}

blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    case_id = request.args.get('case_id', type=int)
    exit_route = None
    redir = request.args.get('redir')

    form = get_form_choices(Add(), case_id)

    kwargs['specimens'] = []
    kwargs['tests'] = []
    adding_test_discipline = ""

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            case_id = form.case_id.data
            case = Cases.query.get(case_id)
            print(form.discipline.data)
            form = get_form_choices(form, case_id, form.discipline.data)
            print('Specimens', form.specimen_id.choices)
            if form.specimen_id.data:
                for assay_id in form.assay_id.data:

                    kwargs['assay_id'] = assay_id
                    assay_name = dict(form.assay_id.choices).get(assay_id)

                    # Update test count of assay
                    assay = Assays.query.get(assay_id)
                    assay.test_count = assay.test_count + 1

                    tests = Tests.query.filter_by(assay_id=assay_id).order_by(Tests.test_id.desc())

                    # Subtract assay volume from specimen only if liquid
                    specimen = Specimens.query.get(form.specimen_id.data)
                    if specimen.type.state:
                        if specimen.type.state.name == 'liquid' and specimen.submitted_sample_amount:
                            if assay.sample_volume:
                                if form.dilution.data.lower() == 'hv':
                                    kwargs['dilution'] = 'HV'
                                    specimen.current_sample_amount = round(float(specimen.current_sample_amount) -
                                                                           float(assay.sample_volume) / 2, 2)
                                elif form.dilution.data == 2:
                                    specimen.current_sample_amount = round(float(specimen.current_sample_amount) -
                                                                           float(assay.sample_volume) / 2, 2)
                                elif form.dilution.data == 5:
                                    specimen.current_sample_amount = round(float(specimen.current_sample_amount) -
                                                                           float(assay.sample_volume) / 5, 2)
                                else:
                                    specimen.current_sample_amount = round(float(specimen.current_sample_amount) -
                                                                           float(assay.sample_volume), 2)
                                    
                                if specimen.current_sample_amount < 0:
                                    specimen.current_sample_amount = 0

                    kwargs['test_id'] = ""
                    test_name = f"{case.case_number} {specimen.accession_number}"
                    if assay.specimen_type_in_test_name == 'Yes':
                        test_name += f" [{specimen.type.code}]"

                    kwargs['test_name'] = test_name
                    kwargs['test_status'] = 'Pending'

                    # Generate custom flash message to display
                    custom_flash_message = (
                        Markup(
                            f"<b>{assay.assay_name} - {test_name}</b> has been successfully added to <b>{case.case_number}</b>"),
                        'success'
                    )
                    adding_test_discipline = form.discipline.data

                    add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                             custom_flash_message=custom_flash_message, **kwargs)

                    # if assay_id != form.assay_id.data[-1]:
                    #     add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                    #              custom_flash_message=custom_flash_message, **kwargs)
                    #
                    # else:
                    #     if redir:
                    #         add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                    #                  custom_flash_message=custom_flash_message, **kwargs)
                    #         return redirect(url_for(f'{table_name}.add', case_id=case_id, redir=redir))
                    #     else:
                    #         add_item(form, table, item_type, item_name, table_name, requires_approval, name,
                    #                  custom_flash_message=custom_flash_message, **kwargs)

            statuses = []
            for discipline in disciplines:
                if adding_test_discipline == discipline and f'{discipline.lower()}' in form.data.keys():
                    if form.data[f'{discipline.lower()}']:
                        if hasattr(case, f'{discipline.lower()}_performed'):
                            setattr(case, f'{discipline.lower()}_performed', 'Yes')

                            # If a test is added for a discipline that was not requested, set the <discipline>_start_date as the date the
                            # the first specimen was created. Skip the filter for External discipline.
                            if discipline == "External":
                                first_specimen = Specimens.query.filter_by(case_id=case_id).first()
                            else:
                                first_specimen = Specimens.query.filter_by(case_id=case_id).join(SpecimenTypes).filter(
                                    SpecimenTypes.discipline.contains(discipline)).first()

                            if not getattr(case, f'{discipline.lower()}_start_date'):
                                if discipline in ["Toxicology", "Histology"]:
                                    setattr(case, f'{discipline.lower()}_start_date', first_specimen.create_date)
                                else:
                                    setattr(case, f'{discipline.lower()}_start_date', datetime.now())

                            if not form.data[f'{discipline.lower()}_requested']:
                                setattr(case, f'{discipline.lower()}_requested', 'No')

                            tests = Tests.query.filter_by(case_id=case_id).join(Assays).filter(
                                Assays.discipline == discipline)
                            if tests.count() == 0:
                                setattr(case, f'{discipline.lower()}_status', 'No Tests Added')
                            elif 'Processing' in [x[0] for x in tests.with_entities(Tests.test_status).distinct()]:
                                setattr(case, f'{discipline.lower()}_status', 'Testing')
                            else:
                                setattr(case, f'{discipline.lower()}_status', 'Initiated')

                    if hasattr(case, f'{discipline.lower()}_performed'):
                        if getattr(case, f'{discipline.lower()}_status'):
                            statuses.append(getattr(case, f'{discipline.lower()}_status'))

            print(statuses)
            print(any(x in ['Testing', 'Drafting', 'CR', 'DR', 'Disseminated'] for x in statuses))

            if 'No Tests Added' in statuses:
                setattr(case, 'case_status', 'Need Test Addition')
            elif all(x == 'Initiated' for x in statuses):
                setattr(case, 'case_status', 'Queued')
            elif any(x in ['Testing', 'Drafting', 'CR', 'DR', 'Disseminated'] for x in statuses):
                setattr(case, 'case_status', 'In Progress')

            db.session.commit()

            if redir:
                return redirect(url_for(f'{table_name}.add', case_id=case_id, redir=redir))
            else:
                return redirect(url_for('cases.view', item_id=case_id, view_only=True))
    # Exit button: if case_id is in URL, go back to that case view; otherwise default to the table/list view
    if case_id:
        exit_route = url_for('cases.view', item_id=case_id, view_only=True)
    else:
        exit_route = url_for(f'{table_name}.view_list')
    kwargs['exit_route'] = exit_route

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
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
    # case_id = request.args.get('item_id', type=int)
    # form = get_form_choices(Update(), case_id)

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
    item = table.query.get(item_id)
    # If the test_status is pending, no removal approval is required
    requires_approval = True
    if item.test_status == 'Pending':
        requires_approval = False

        # Remove status to prevent including removed tests in workflows. Since this is only for pending tests
        item.test_status = None
        # Get the discipline of the specimen that is being tested
        discipline = item.specimen.discipline
        # Check if there are any tests for that discipline. We subtract 1 because the test hasn't been removed yet.
        # We want to make sure we're counting active tests (i.e. ones that have not been removed).
        n_tests = table.query.join(Specimens).filter(Tests.case_id == item.case_id, Specimens.discipline == discipline,
                                                     Specimens.db_status == 'Active').count() - 1
        # If there are no tests, set the discipline_status as No Tests Added. Set the case status to 'Need Test Addition'
        if not n_tests:
            case = item.case
            setattr(case, f"{discipline.lower()}_status", 'No Tests Added')
            case.case_status = 'Need Test Addition'

    # Clear the status and batch_id if 'Admin' or 'Owner' are removing tests
    if current_user.permissions in ['Admin', 'Owner']:
        item.batch_id = None
        item.test_status = None
    _remove = remove_item(item_id, table, table_name, item_name, name, requires_approval=requires_approval)

    return _remove


@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    item = table.query.get(item_id)
    if item.test_status != 'Pending' and current_user.permissions not in ['Admin', 'Owner']:
        abort(403)

    # Remove status and batch ID to prevent including removed tests in workflows
    item.test_status = None
    item.batch_id = None
    # Get the discipline of the specimen that is being tested
    discipline = item.specimen.discipline
    # Check if there are any tests for that discipline. We subtract 1 because the test hasn't been removed yet.
    # We want to make sure we're counting active tests (i.e. ones that have not been removed).
    n_tests = table.query.join(Specimens).filter(Tests.case_id == item.case_id, Specimens.discipline == discipline,
                                                 Specimens.db_status == 'Active').count() - 1
    # If there are no tests, set the discipline_status as No Tests Added. Set the case status to 'Need Test Addition'
    if not n_tests:
        case = item.case
        setattr(case, f"{discipline.lower()}_status", 'No Tests Added')
        case.case_status = 'Need Test Addition'

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
    item = table.query.get(item_id)
    # If a test is restored set the test_status to 'Pending'
    item.test_status = 'Pending'
    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    item = table.query.get(item_id)
    if item.test_status != 'Pending' and current_user.permission not in ['Admin', 'Owner']:
        abort(403)

    # Get the discipline of the specimen that is being tested
    discipline = item.specimen.discipline
    # Check if there are any tests for that discipline. We subtract 1 because the test hasn't been deleted yet.
    n_tests = table.query.join(Specimens).filter(Tests.case_id == item.case_id,
                                                 Specimens.discipline == discipline).count() - 1
    # If there are no tests, set the discipline_status as No Tests Added. Set the case status to 'Need Test Addition'
    if not n_tests:
        case = item.case
        setattr(case, f"{discipline.lower()}_status", 'No Tests Added')
        case.case_status = 'Need Test Addition'

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():
    assays = Assays.query
    for assay in assays:
        assay.test_count = 0

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):
    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = default_kwargs.copy()

    kwargs['discipline'] = disciplines

    discipline = kwargs['discipline']

    query = request.args.get('query')
    query_type = request.args.get('query_type')
    items = None

    if query_type == 'discipline':
        if query:
            items = table.query.join(Assays).filter(Assays.discipline.contains(query))

    kwargs = {}
    # Get assays to display in the Filter by Assay button
    kwargs['assays'] = [item.assay_name for item in Assays.query.order_by(Assays.assay_name)]
    query_type = request.args.get('query_type')
    items = None
    if query_type == 'assay':
        assay = request.args.get('query')
        if assay:
            items = table.query.join(Assays).filter(Assays.assay_name == assay)

    # Filter based on status
    kwargs['statuses'] = ['Pending', 'Processing', 'Finalised']
    if query_type == 'status':
        status = request.args.get('query')
        if status:
            items = table.query.filter_by(test_status=status)

    _view_list = view_items(table, item_name, item_type, table_name, items=items, query=query,
                            pending_submitter_column=False, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    kwargs = default_kwargs.copy()
    if current_user.permissions in ['MED-Autopsy', 'INV', 'MED', 'ADM']:
        return render_template('/error_pages/403.html'), 403

    item = table.query.get_or_404(item_id)
    results = Results.query.filter_by(test_id=item_id).all()

    # Initialize result status update form
    status_form = UpdateStatus()
    status_form.result_status.choices = [('Withdrawn', 'Withdrawn'), ('Omit', 'Omit'), ('DNR', 'DNR')]

    status_form.result_type.choices = []
    status_form.result_type.render_kw = {'disabled': True}
    status_form.result_type_update_reason.render_kw = {'disabled': True}
    status_form.type_dont_change.render_kw = {'disabled': True}

    if status_form.is_submitted() and status_form.validate():

        # Initialize status_changed
        status_changed = False

        # Check if result_status for any result in results is different from status_form.result_status
        if any(result.result_status != status_form.result_status.data for result in results):
            status_changed = True

        # Will never change result_type at test level
        type_changed = False

        # Update fields only if values changed and reason is provided
        if status_changed and status_form.result_status_update_reason.data.strip():
            now = datetime.utcnow()
            stamp = f"{current_user.initials} {now.strftime('%m/%d/%Y %H:%M')}"
            reason_text = f"{status_form.result_status_update_reason.data} ({stamp})"

            def _s(v):  # normalize None -> ''
                return '' if v is None else str(v)

            for result in results:
                if result.result_status != status_form.result_status.data:
                    new_status  = _s(status_form.result_status.data)
                    new_updated = 'Y'
                    new_reason  = _s(reason_text)

                    # --- 1) result_status ---
                    orig_status = _s(result.result_status)
                    if orig_status != new_status:
                        rev = Modifications.get_next_revision('Results', result.id, 'result_status')
                        db.session.add(Modifications(
                            event='UPDATED',
                            status='Pending',
                            table_name='Results',
                            record_id=str(result.id),
                            revision=rev,
                            field_name='result_status',
                            field='Result Status',
                            original_value=orig_status,
                            original_value_text=orig_status,
                            new_value=new_status,
                            new_value_text=new_status,
                            submitted_by=current_user.id,
                            submitted_date=now
                        ))

                    # --- 2) result_status_updated ---
                    orig_updated = _s(result.result_status_updated)
                    if orig_updated != new_updated:
                        rev = Modifications.get_next_revision('Results', result.id, 'result_status_updated')
                        db.session.add(Modifications(
                            event='UPDATED',
                            status='Pending',
                            table_name='Results',
                            record_id=str(result.id),
                            revision=rev,
                            field_name='result_status_updated',
                            field='Result Status Updated',
                            original_value=orig_updated,
                            original_value_text=orig_updated,
                            new_value=new_updated,
                            new_value_text=new_updated,
                            submitted_by=current_user.id,
                            submitted_date=now
                        ))

                    # --- 3) result_status_update_reason ---
                    orig_reason = _s(result.result_status_update_reason)
                    if orig_reason != new_reason:
                        rev = Modifications.get_next_revision('Results', result.id, 'result_status_update_reason')
                        db.session.add(Modifications(
                            event='UPDATED',
                            status='Pending',
                            table_name='Results',
                            record_id=str(result.id),
                            revision=rev,
                            field_name='result_status_update_reason',
                            field='Result Status Update Reason',
                            original_value=orig_reason,
                            original_value_text=orig_reason,
                            new_value=new_reason,
                            new_value_text=new_reason,
                            submitted_by=current_user.id,
                            submitted_date=now
                        ))

                    # Mirror row changes (no mods for these admin fields)
                    result.result_status = new_status
                    result.result_status_updated = new_updated
                    result.result_status_update_reason = new_reason
                    result.db_status = "Active With Pending Changes"
                    result.pending_submitter = current_user.initials
                    result.modify_date = now
                    result.modified_by = current_user.initials

            db.session.commit()


        return redirect(url_for(f'{table_name}.view', item_id=item_id))

    result_comment_dict = {}
    for result in results:
        comments = CommentInstances.query.filter_by(comment_item_type='Results', comment_item_id=result.id) \
            .order_by(CommentInstances.comment_id.desc())
        if comments.count():
            comment_text = '<ul>'
            for comment in comments:
                comment_text += '<li>'
                if getattr(comment, 'comment_id'):
                    if comment.comment.code:
                        comment_text += f"{comment.comment.code} - "
                    comment_text += f"{comment.comment.comment}"
                else:
                    comment_text += f"{comment.comment_text}"

                comment_text += f" ({comment.created_by})</li>"
            comment_text += "</ul>"
            result_comment_dict[result.id] = comment_text
    alias = f"{getattr(item, name)} | {item.assay.assay_name}"

    return view_item(item, alias, item_name, table_name,
                     results=results,
                     result_comment_dict=result_comment_dict,
                     status_form=status_form)


@blueprint.route(f'/{table_name}/get_disciplines/', methods=['GET', 'POST'])
@login_required
def get_disciplines():
    case_id = request.args.get('case_id', type=int)

    disciplines_performed = [{'id': 0, 'name': 'Please select a discipline'}]

    response = {
        'toxicology_requested': False,
        'biochemistry_requested': False,
        'histology_requested': False,
        'external_requested': False,
        'toxicology': False,
        'biochemistry': False,
        'histology': False,
        'external': False,
    }

    if case_id != 0:
        case = Cases.query.get(case_id)

        for discipline in disciplines:
            if hasattr(case, f"{discipline.lower()}_requested"):
                if getattr(case, f"{discipline.lower()}_requested") == 'Yes':
                    response[f'{discipline.lower()}_requested'] = True

                if getattr(case, f"{discipline.lower()}_performed") == 'Yes':
                    response[f'{discipline.lower()}'] = True
                    discipline_choice = {'id': discipline, 'name': discipline}
                    disciplines_performed.append(discipline_choice)

    response['disciplines_performed'] = disciplines_performed

    print(response)
    return jsonify(response)


@blueprint.route(f'/{table_name}/get_specimens/', methods=['GET', 'POST'])
@login_required
def get_specimens():
    case_id = request.args.get('case_id', type=int)
    discipline = request.args.get('discipline')
    response = {}
    specimen_choices = []
    specimens_lst = []
    test_lst = []
    discipline_tests = []

    if case_id:
        if discipline:
            specimens = Specimens.query.join(SpecimenTypes).filter(
                Specimens.case_id == case_id,
                Specimens.db_status.in_(['Active', 'Active With Pending Changes']),
                or_(
                    Specimens.discipline.contains(discipline),
                    SpecimenTypes.discipline.contains(discipline)
                )
            ).order_by(
                Specimens.collection_date.asc(),
                Specimens.collection_time.asc()
            )

            tests = Tests.query.join(Assays).filter(
                Tests.case_id == case_id,
                Assays.discipline == discipline
            )

            assays = Assays.query.filter(Assays.discipline == discipline, Assays.status_id == 1).order_by(
                Assays.assay_order.asc()).all()
            assay_choices = [{'id': assay.id, 'name': assay.assay_name} for assay in assays]

            if tests.count() != 0:
                for test in tests:
                    if test.batch is None:
                        batch_id = ""
                    else:
                        batch_id = test.batch.batch_id
                    test_dict = {
                        "accession_number": test.specimen.accession_number,
                        "code": f"[{test.specimen.type.code}]",
                        "description": test.specimen.type.name,
                        "assay": test.assay.assay_name,
                        "test_name": test.test_name,
                        "batch_id": batch_id
                    }
                    test_lst.append(test_dict)

            if specimens.count() != 0:
                collection_date = ""

                for specimen in specimens:
                    specimen_choices.append({'id': specimen.id, 'name': specimen.accession_number})
                    if specimen.collection_date is not None:
                        collection_date = specimen.collection_date.strftime('%m/%d/%Y')
                    specimen_dict = {"id": specimen.id,
                                     "accession_number": specimen.accession_number,
                                     "code": f"[{specimen.type.code}]",
                                     "description": specimen.type.name,
                                     "collection_date": collection_date,
                                     "collection_time": specimen.collection_time,
                                     "current_sample_amount": f"~{specimen.current_sample_amount}",
                                     "submitted_sample_amount": f"~{specimen.submitted_sample_amount}",
                                     "condition": specimen.condition,
                                     }

                    specimens_lst.append(specimen_dict)

        response['tests'] = test_lst
        response['specimens'] = specimens_lst
        response['specimen_choices'] = specimen_choices
        response['discipline_tests'] = discipline_tests
        response['assay_choices'] = assay_choices

    return jsonify(response)


@blueprint.route(f'/{table_name}/get_case/', methods=['GET', 'POST'])
@login_required
def get_case():
    specimen_id = request.args.get('specimen_id', type=int)

    specimen = Specimens.query.get(specimen_id)
    case_id = specimen.case_id
    case_number = Cases.query.get(case_id).case_number

    return jsonify(case_id=case_id, case_number=case_number)


@blueprint.route(f'/{table_name}/get_assays/', methods=['GET', 'POST'])
@login_required
def get_assays():
    discipline = request.args.get('discipline')
    print(discipline)
    items = Assays.query.filter_by(discipline=discipline).order_by(Assays.assay_order).all()
    print(items)
    message = "Nothing Selected"
    choices = []
    if discipline != 0:
        if len(items) != 0:
            for item in items:
                choice = {'id': item.id, 'name': item.assay_name}
                choices.append(choice)
        else:
            message = "This discipline has no assays"
    else:
        message = 'No discipline selected'

    print(choices)
    return jsonify({'choices': choices, 'message': message})


@blueprint.route(f'/{table_name}/get_default_assays/', methods=['GET', 'POST'])
@login_required
def get_default_assays():
    specimen_id = request.args.get('specimen_id', type=int)
    specimen = Specimens.query.get(specimen_id)
    specimen_type = SpecimenTypes.query.get(specimen.type.id)
    case_type = CaseTypes.query.get(int(specimen.case.case_type))

    # Initialize assay arrays
    assays = []
    case_assays = []
    spec_assays = []

    # Get specimen type default assays
    if specimen_type.default_assays:
        spec_type_assays = specimen_type.default_assays.split(", ")
        
        for x in spec_type_assays:
            assay = Assays.query.get(x).id
            spec_assays.append(assay)
    
    # Get case type default assays
    if case_type.default_assays:
        case_type_assays = case_type.default_assays.split(", ")
        for x in case_type_assays:
            assay = Assays.query.get(x).id
            case_assays.append(assay)

    # If both the case_assays and spec_assays, return only matching assays
    if len(case_assays) > 0 and len(spec_assays) > 0:
        for assay in case_assays:
            if assay in spec_assays:
                assays.append(assay)
            else:
                pass
    
    # If only case_assays, return case_assays
    elif len(case_assays) > 0:
        assays = case_assays
    
    # If only spec_assays, return spec_assays
    elif len(spec_assays) > 0:
        assays = spec_assays
    
    # Else return blank array
    else:
        pass

    return jsonify(assays=assays)


@blueprint.route(f'/{table_name}/cancel', methods=['GET', 'POST'])
@login_required
def cancel():
    form = Cancel()
    data = request.form.to_dict(flat=True)
    item_id = int(data['test_id'])
    item = Tests.query.get(item_id)
    # form.test_id.data = item_id
    form.test_status.data = 'Cancelled'
    # form.test_comment.data = data['test_comment']

    # Add comment
    comment_form = get_comment_form_choices(AddComment(), item_id, 'Tests')
    comment_form.comment_item_id.data = item_id
    comment_form.comment_item_type.data = item_type
    # comment_form.comment_type.data = item_type
    comment_form.comment_text.data = data['test_comment']

    if request.method == 'POST':
        update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name)
        add_item(comment_form, CommentInstances, 'Comment Instance', 'Comment Instances', 'comment_instances', False,
                 'id')

    return redirect(url_for('batches.view', item_id=item.batch_id))


@blueprint.route(f'/{table_name}/reinstate', methods=['GET', 'POST'])
@login_required
def reinstate():
    form = Reinstate()
    data = request.form.to_dict(flat=True)
    item_id = int(data['test_id'])
    item = Tests.query.get(item_id)
    # form.test_id.data = item_id
    form.test_status.data = 'Processing'

    if request.method == 'POST':
        update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name)
    return redirect(url_for('batches.view', item_id=item.batch_id))


@blueprint.route(f'/{table_name}/<int:item_id>/comments', methods=['GET', 'POST'])
@login_required
def view_comments(item_id):
    item = table.query.get(item_id)
    comments = CommentInstances.query.filter_by(comment_item_type='Tests', comment_item_id=item_id)
    alias = f"{getattr(item, name)}"

    return render_template(
        f'{table_name}/view_comments.html',
        item=item,
        comments=comments,
        alias=alias,
        table_name=table_name
    )


@blueprint.route(f'/{table_name}/<int:item_id>/print_ex_label', methods=['GET', 'POST'])
@login_required
def print_ex_label(item_id):
    item = table.query.get(item_id)
    batch = Batches.query.get(item.batch_id)
    attributes_list = []

    # Get worklist for batch
    worklist = BatchRecords.query.filter(and_(BatchRecords.batch_id == batch.id,
                                              BatchRecords.file_type == 'Worklist')).first()

    df = pd.read_excel(worklist.file_path)

    if 'GCET' in batch.assay.assay_name:
        worklist_dict = {y['SampleName'].rstrip(): [f"{y['FilterVialLabware']}-{y['FilterVialPos']}",
                                                    y['SampleCarrierPos']] for x, y in df.iterrows()
                         if y['Type'] == 1
                         }

    elif 'SAMQ' in batch.assay.assay_name:
        worklist_dict = {y['SampleName'].rstrip(): ['', ''] for x, y in df.iterrows()
                         if y['Type'] == 1
                         }
    else:
        worklist_dict = {y['SampleName'].rstrip(): [f"{y['FilterVialLabware'][-1]}-{y['FilterVialPos']}",
                                                    y['SampleCarrierPos']] for x, y in df.iterrows()
                         if y['Type'] == 1
                         }

    if 'COHB' in batch.assay.assay_name or 'PRIM' in batch.assay.assay_name:
        label_attributes = fields_dict['extraction_cohb']
    else:
        label_attributes = fields_dict['extraction']

    # Default printer for extraction labels
    printer = r'\\OCMEG9M026.medex.sfgov.org\BS21 - Extraction'

    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'tests{item.id}.png')
    qrcode.make(f'tests: {item.id}').save(qr_path)
    with open(qr_path, "rb") as qr_file:
        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

    label_attributes['CASE_NUM'] = item.case.case_number
    label_attributes['TEST_NAME'] = item.test_name.split(' ')[2]
    label_attributes['ACC_NUM'] = item.specimen.accession_number
    label_attributes['QR'] = qr_encoded
    label_attributes['CASE_NUM_1'] = item.case.case_number
    label_attributes['TEST_NAME_1'] = item.test_name.split(' ')[2]
    label_attributes['ACC_NUM_1'] = item.specimen.accession_number
    label_attributes['QR_1'] = qr_encoded

    # Set relevant extraction data for non COHB/PRIM and for Manual vs Automated batches
    if 'COHB' not in batch.assay.assay_name and 'PRIM' not in batch.assay.assay_name:
        if item.dilution == 'HV':
            label_attributes['VIAL_POS'] = f'{item.vial_position}*'
            label_attributes['VIAL_POS_1'] = f'{item.vial_position}*'
        else:
            label_attributes['VIAL_POS'] = item.vial_position
            label_attributes['VIAL_POS_1'] = item.vial_position
        if batch.technique == 'Hamilton':
            label_attributes['HAMILTON_FV'] = worklist_dict[item.test_name][0]
            label_attributes['HAMILTON_SC'] = worklist_dict[item.test_name][1]
            label_attributes['HAMILTON_FV_1'] = worklist_dict[item.test_name][0]
            label_attributes['HAMILTON_SC_1'] = worklist_dict[item.test_name][1]
        else:
            label_attributes['HAMILTON_FV'] = ''
            label_attributes['HAMILTON_SC'] = ''
            label_attributes['HAMILTON_FV_1'] = ''
            label_attributes['HAMILTON_SC_1'] = ''

    attributes_list.append(label_attributes.copy())

    # print_label(printer, attributes_list)

    # return redirect(url_for(f'batches.view', item_id=batch.id))

    return jsonify(attributes_list, printer, None, None, url_for(f'batches.view', item_id=batch.id, ))


@blueprint.route(f'/{table_name}/<int:item_id>/set_result_status', methods=['GET', 'POST'])
@login_required
def set_result_status(item_id):
    result_status = request.args.get('result_status')

    results = [result for result in Results.query.filter_by(test_id=item_id)]

    if result_status:
        for result in results:
            result.result_status = result_status

        db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/tests/<int:test_id>/review_pending_results', methods=['GET', 'POST'])
@login_required
def review_pending_results(test_id):
    test = Tests.query.get_or_404(test_id)
    results = Results.query.filter_by(test_id=test.id).all()
    form = Approve()

    def latest_with_original(record_id: int, field_name: str):
        """Latest Mod row for this record+field that has a non-null original_value."""
        return (Modifications.query
                .filter_by(table_name='Results',
                           record_id=str(record_id),
                           field_name=field_name)
                .filter(Modifications.original_value.isnot(None))
                .order_by(Modifications.id.desc())
                .first())

    def restore_from_snapshot(result_obj, field_name: str):
        """
        Restore a field using the latest snapshot with original_value.
        - If snapshot.original_value is blank/empty -> set None
        - Else set to snapshot.original_value
        (If no snapshot exists, leave the field unchanged)
        """
        snap = latest_with_original(result_obj.id, field_name)
        if snap is not None:
            val = snap.original_value
            # Normalize blanks to None
            if val is None or str(val) == '':
                setattr(result_obj, field_name, None)
            else:
                setattr(result_obj, field_name, val)

    if request.method == 'POST':
        action = request.form.get('action', 'approve')  # default to approve
        changed_count = 0
        now = datetime.utcnow()

        for result in results:
            # All pending changes for this result
            pending_mods = (Modifications.query
                            .filter_by(table_name='Results',
                                       record_id=str(result.id),
                                       status='Pending')
                            .order_by(Modifications.id.asc())
                            .all())
            if not pending_mods:
                continue

            if action == 'approve':
                # Apply pending new values and approve the mods
                for mod in pending_mods:
                    setattr(result, mod.field_name, mod.new_value)
                    mod.status = 'Approved'
                    mod.reviewed_by = current_user.id
                    mod.review_date = now

            elif action == 'reject':
                # Restore each of the three fields from their snapshots
                restore_from_snapshot(result, 'result_status')
                restore_from_snapshot(result, 'result_status_updated')
                restore_from_snapshot(result, 'result_status_update_reason')

                # Mark all pending mods as Rejected
                for mod in pending_mods:
                    mod.status = 'Rejected'
                    mod.reviewed_by = current_user.id
                    mod.review_date = now

            # Clear pending state + audit stamps (both paths)
            result.db_status = "Active"
            result.pending_submitter = None
            result.modify_date = now
            result.modified_by = current_user.initials

            changed_count += 1

        db.session.commit()

        if action == 'approve':
            flash(Markup(f"<b>{changed_count}</b> Results approved successfully."), 'success')
        else:
            flash(Markup(
                f"<b>{changed_count}</b> Results rejected. "
                f"Fields restored from snapshots (blank originals cleared to None)."
            ), 'warning')

        return redirect(url_for('tests.view', item_id=test.id))

    # GET: only show results that still have pending modifications
    pending_results = []
    for result in results:
        mods = (Modifications.query
                .filter_by(table_name='Results', record_id=str(result.id), status='Pending')
                .all())
        if mods:
            fields_changed = {m.field_name for m in mods}
            pending_results.append({
                'result': result,
                'status_changed': 'result_status' in fields_changed,
                'reason_changed': 'result_status_update_reason' in fields_changed
            })

    return render_template('tests/review_pending_results.html',
                           test=test,
                           pending_results=pending_results)




