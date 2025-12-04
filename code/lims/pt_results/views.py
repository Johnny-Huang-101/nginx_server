from sqlalchemy import case

from lims.models import PTResults, Results, Tests
from lims.pt_results.forms import Add, Edit, Approve
from lims.pt_results.functions import get_form_choices, process_form
from lims.forms import Attach, Import
from lims.view_templates.views import *


# Set item global variables
item_type = 'Proficiency Test Result'  # singular
item_name = 'Proficiency Test Results'
table = PTResults
table_name = 'pt_results'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to,
                  'disable_fields': ['case_id', 'result_id']
                  }

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@blueprint.route(f'/{table_name}/add/<int:case_id>', methods=['GET', 'POST'])
@login_required
def add(case_id=None):
    kwargs = {'template': template, 'redirect': redirect_to}
    requires_approval = False

    # inherit from previously submitted form, if available
    if case_id is None:
        case_id = request.args.get('case_id', type=int)
    else:
        case_id = case_id
        kwargs.update({'disable_fields': ['case_id']})

    # initialize form
    form = get_form_choices(Add(), case_id=case_id)

    # inherit from previously submitted form, if available
    eval_date = request.args.get('eval_date')
    notes = request.args.get('notes')
    informal = request.args.get('informal')
    a_ref = request.args.get('a_ref')
    b_ref = request.args.get('b_ref')

    if request.method == 'POST' and form.validate():

        result = Results.query.get(
            form.result_id.data)  # Getting row of Results table based on selection of official result
        official_result_id = result.id  # ID from Results of the selected official result
        official_item_id = official_result_id

        # set pt_id as the next unused id within PTResults
        try:
            pt_id = PTResults.query.order_by(PTResults.id.desc()).first().id + 1
        except:
            pt_id = PTResults.query.count() + 1

        # Extracting component_id, specimen_id, and test_ids based on selection to obtain shared_results
        component_id = result.component_id
        is_etoh = True if result.component_name == "Ethanol" else False
        specimen_id = result.test.specimen.id
        official_test_id = result.test.id
        test_ids = [item.id for item in Tests.query.filter_by(specimen_id=specimen_id)]

        # organize the test_ids to obtain shared_results and return the official result first
        official_test_idx = test_ids.index(official_test_id)
        test_ids.pop(official_test_idx)
        test_ids.insert(0, official_test_id)
        when_clauses = [
            (Results.test_id == value, index)
            for index, value in enumerate(test_ids)
        ]
        case_expression = case(*when_clauses, else_=len(test_ids))
        shared_results = Results.query.filter(Results.test_id.in_(test_ids),
                                              Results.component_id == component_id).order_by(case_expression)

        for result in shared_results:
            kwargs = {}
            kwargs['result_official'] = pt_id
            is_official = True if result.id == official_item_id else False

            new_kwargs, requires_approval = process_form(form, is_etoh, is_official, result)
            kwargs.update(new_kwargs)

            # Adding item(s) to the database
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

        # Redirecting to pt_results.add with persisting form data to submit again with the same basic eval data
        return redirect(url_for('pt_results.add',
                                case_id=form.case_id.data,
                                eval_date=form.eval_date.data,
                                informal=form.eval_informal.data,
                                notes=form.notes.data,
                                a_ref=form.eval_A_ref.data,
                                b_ref=form.eval_B_ref.data))

    elif request.method == 'GET':
        # Populating form fields with request data from the redirect above
        form.case_id.data = case_id
        if eval_date is None:
            form.eval_date.data = eval_date
        else:
            eval_date = datetime.strptime(eval_date, '%Y-%m-%d')
            form.eval_date.data = eval_date
        form.eval_informal.data = informal
        form.notes.data = notes
        form.eval_A_ref.data = a_ref
        form.eval_B_ref.data = b_ref

    # loads form again
    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = {}
    kwargs = default_kwargs.copy()

    # identifies which item of PTResults is being edited, passes relevant case_id to form
    item = table.query.get(item_id)
    case_id = item.case_id
    # initialize form
    form = get_form_choices(Edit(), case_id)

    pt_eval = item.id  # ID of official result row of PTResults
    is_etoh = True if item.result.component_name == "Ethanol" else False
    shared_evals = PTResults.query.filter_by(result_official=item.id).order_by(
        PTResults.id.asc())  # shared rows of PT Evals

    if request.method == 'POST' and form.validate():

        for eval in shared_evals:
            is_official = True if eval.id == eval.result_official else False

            new_kwargs, requires_approval = process_form(form, is_etoh, is_official, result=eval.result)
            kwargs.update(new_kwargs)

            if is_official:  # if current eval is the official result
                edit_item(form, eval.id, table, item_type, item_name, table_name, name, **kwargs)

            else:
                if shared_evals.all()[-1].id == eval.id:  # if this is the last shared result
                    _update = update_item(form, eval.id, table, item_type, item_name, table_name, requires_approval,
                                          name, **kwargs)
                    return _update
                update_item(form, eval.id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)
    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = {}
    kwargs = default_kwargs.copy()

    # identifies which item of PTResults is being edited, passes relevant case_id to form
    item = table.query.get(item_id)
    case_id = item.case_id
    # initialize form
    form = get_form_choices(Approve(), case_id)

    pt_eval = item.id  # ID of official result row of PTResults
    is_etoh = True if item.result.component_name == "Ethanol" else False
    shared_evals = PTResults.query.filter_by(result_official=item.id).order_by(
        PTResults.id.asc())  # shared rows of PT Evals

    if request.method == 'POST' and form.validate():

        for eval in shared_evals:
            is_official = True if eval.id == eval.result_official else False

            new_kwargs, requires_approval = process_form(form, is_etoh, is_official, result=eval.result)
            kwargs.update(new_kwargs)

            if is_official:  # if current eval is the official result
                approve_item(form, eval.id, table, item_type, item_name, table_name, name, **kwargs)

            else:
                if shared_evals.all()[-1].id == eval.id:  # if this is the last shared result
                    _update = update_item(form, eval.id, table, item_type, item_name, table_name, requires_approval,
                                          name, **kwargs)
                    return _update
                update_item(form, eval.id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = {}
    kwargs = default_kwargs.copy()
    requires_approval = False

    # identifies which item of PTResults is being edited, passes relevant case_id to form
    item = table.query.get(item_id)
    case_id = item.case_id
    # initialize form
    form = get_form_choices(Edit(), case_id)

    pt_eval = item.id  # ID of official result row of PTResults
    is_etoh = True if item.result.component_name == "Ethanol" else False
    shared_evals = PTResults.query.filter_by(result_official=item.id).order_by(
        PTResults.id.asc())  # shared rows of PT Evals

    if request.method == 'POST' and form.validate():

        for eval in shared_evals:
            is_official = True if eval.id == eval.result_official else False

            new_kwargs, requires_approval = process_form(form, is_etoh, is_official, result=eval.result)
            kwargs.update(new_kwargs)

            update_item(form, eval.id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

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
    _view_list = view_items(table, item_name, item_type, table_name)

    return _view_list


# view disabled form for the official result
@blueprint.route(f'/{table_name}/<int:item_id>/view', methods=['GET'])
@login_required
def view(item_id):
    kwargs = {'template': template,
              'redirect': redirect_to,
              'disable_fields': ['case_id',
                                 'result_id',
                                 'pt_component_id',
                                 'pt_unit_id',
                                 'notes',
                                 'eval_date',
                                 'eval_informal',
                                 'pt_reporting_limit',
                                 'pt_participants',
                                 'target',
                                 'median',
                                 'mean_all',
                                 'sd_all',
                                 'mean_sub',
                                 'sd_sub',
                                 'eval_A_ref',
                                 'eval_B_ref',
                                 'eval_manual_min',
                                 'eval_manual_max',
                                 'eval_FLD_conclusion',
                                 ]
              }

    item = table.query.get(item_id)
    case_id = item.case_id
    eval_date = item.eval_date

    form = get_form_choices(Add(), case_id)

    _view = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/view_eval', methods=['GET'])
@login_required
def view_eval(item_id):
    item = table.query.get(item_id)

    evals = table.query.filter_by(case_id=item.case_id, eval_date=item.eval_date)

    processed_evals = []
    sample = 0

    for eval in evals:
        if sample != eval.result.test.specimen.id:
            sample = eval.result.test.specimen.id
            eval.new_sample = True
        else:
            eval.new_sample = False
        processed_evals.append(eval)

    return render_template(
        f'{table_name}/view_eval.html',
        item=item,
        evals=processed_evals,
    )


@blueprint.route('/get_results/')
@login_required
def get_results():  # originally copied from Personnel views.py -- agency --> case and division --> results

    case_id = request.args.get('case_id', type=int)
    results = Results.query.filter_by(case_id=case_id)  # TODO add to criteria result="Y"
    choices = []

    if case_id != 0:
        if results.count() != 0:
            choices.append({'id': 0, 'name': 'Please select a result'})
            for item in results:
                choice = {}
                choice['id'] = item.id
                choice['name'] = f"{item.test.specimen.accession_number} | {item.component_name} |  {item.result} | " \
                                 f"{item.concentration} | {item.test.batch.batch_id}"  # defined here and in functions.py
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This case has no results'})
    else:
        choices.append({'id': 0, 'name': 'No case selected'})

    return jsonify({'results': choices})


@blueprint.route(f'/{table_name}/<int:item_id>/approve_all_fields', methods=['GET', 'POST'])
@login_required
def approve_all_fields(item_id):
    shared_evals = PTResults.query.filter_by(result_official=item_id)
    for eval in shared_evals:
        eval.db_status = 'Active'
        eval.modified_by = current_user.initials
        eval.modify_date = datetime.now()

        modifications = Modifications.query.filter_by(table_name=item_name, record_id=eval.id, status='Pending')
        for mod in modifications:
            mod.status = 'Approved'
            mod.reviewed_by = current_user.id
            mod.review_date = datetime.now()

    db.session.commit()

    flash(Markup(f"<b>{item_id}</b> successfully approved"), 'success')
    # flash(Markup(f"<b>{alias}</b> updated successfully"), "success")

    return redirect(url_for('pt_results.view_list'))
