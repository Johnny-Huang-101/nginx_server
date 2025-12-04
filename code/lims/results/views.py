import re

import numpy as np
import pandas as pd
import fitz
from flask_wtf.csrf import generate_csrf

from lims.models import *
from lims.forms import Attach
from lims.forms import Import as ImportToxDB
from lims.view_templates.views import *

from lims.results.forms import Add, Edit, Approve, Update, Import, AlcoholVerbal, UpdateStatus
from lims.results.functions import get_form_choices, get_test_choices, get_components_and_results, print_alcohol_verbal

from markupsafe import escape

# Set item global variables
item_type = 'Result'
item_name = 'Results'
table = Results
table_name = 'results'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = True  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

blueprint = Blueprint(table_name, __name__)
path = os.path.join(app.config['FILE_SYSTEM'], table_name)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'add_form.html'
    case_id = request.args.get('case_id', type=int)
    test_id = request.args.get('test_id', type=int)

    comment_url = url_for('comment_instances.add')
    kwargs['comment_url'] = comment_url

    form = get_form_choices(Add(), case_id, test_id)


    exit_route=None
    test = Tests.query.filter_by(id=test_id).first()
    batch_id = test.batch_id if test else None
    if batch_id:
        exit_route = url_for('batches.view', item_id=batch_id)

    if request.method == 'POST':
        case_id = form.case_id.data
        test_id = form.test_id.data
        component_id = form.component_id.data
        if form.is_submitted() and form.validate():

            # Set the component_name string
            kwargs['component_name'] = Components.query.get(component_id).name
            result = form.result.data

            # If the component is in the assays scope, set the scope_id by
            # getting the assay from the test and querying the scope table.
            assay_id = Tests.query.get(test_id).assay_id
            scope_component = Scope.query.filter_by(assay_id=assay_id, component_id=component_id).first()
            if scope_component:
                kwargs['scope_id'] = scope_component.id

            # If the supplementary result is numerical, set the concentration
            # by trying to coerce into int.
            if form.supplementary_result.data:
                try:
                    kwargs['concentration'] = int(form.supplementary_result.data)
                except:
                    pass

            # Add the result
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

            # Redirect the user back to the add form with the case and test already selected
            return redirect(url_for(f"{table_name}.add", case_id=case_id, test_id=test_id))
        else:
            form = get_form_choices(form, case_id=form.case_id.data, test_id=form.test_id.data)

    # Get the tests for the case_id and results for the test_id
    kwargs['tests'] = Tests.query.filter_by(case_id=case_id).filter(Tests.test_status != "Pending").order_by(
        Tests.create_date.asc())
    kwargs['results'] = Results.query.filter_by(test_id=test_id)

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, exit_route=exit_route, **kwargs)

    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/results/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    item = Results.query.get_or_404(item_id)
    kwargs['item'] = item

    form = Approve(obj=item)
    form.result_status.choices = [
        ('Confirmed', 'Confirmed'), 
        ('Unconfirmed', 'Unconfirmed'),
        ('Saturated', 'Saturated'), 
        ('Withdraw', 'Withdraw'),
        ('DNR', 'DNR'), 
        ('Omit', 'Omit')
    ]

    if request.method == 'POST':
        # manually approve like the bulk logic (no need to use approve_item if not working)
        mods = Modifications.query.filter_by(
            table_name='Results',
            record_id=str(item.id),
            status='Pending'
        ).all()

        if mods:
            for mod in mods:
                setattr(item, mod.field_name, mod.new_value)
                mod.status = 'Approved'
                mod.reviewed_by = current_user.id
                mod.review_date = datetime.utcnow()

            item.db_status = 'Active'
            item.pending_submitter = None
            item.modify_date = datetime.utcnow()
            item.modified_by = current_user.initials

            db.session.commit()
            flash(Markup(f"<b>Result {item.id}</b> approved successfully."), 'success')
        else:
            flash('No pending modifications found.', 'warning')

        return redirect(url_for('results.view', item_id=item.id))
    
    case_comments = (
        CommentInstances.query
        .filter(
            CommentInstances.comment_item_type == 'Cases',
            CommentInstances.comment_item_id == item.case_id
        )
        .order_by(CommentInstances.id.desc())
        .all()
    )

    # GET: show the approval form
    return render_template('results/form.html', form=form, function='Approve', item=item, case_comments=case_comments)



@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):

    item = table.query.get(item_id)
    alias = item.component.name

    kwargs = default_kwargs.copy()
    kwargs['disable_fields'] = ['case_id', 'test_id', 'component_id']
    form = get_form_choices(Update(), item.case_id, item.test_id)

    if request.method == 'GET':
        form.case_id.data = item.case_id
        form.test_id.data = item.test_id
        form.component_id.data = item.component_id
        form.unit_id.data = item.unit_id
        form.result_status.data = item.result_status
        form.result.data = item.result
        form.result_type.data = item.result_type
        form.supplementary_result.data = item.supplementary_result
        form.concentration.data = item.concentration
        form.measurement_uncertainty.data = item.measurement_uncertainty
        form.qualitative.data = item.qualitative
        form.qualitative_reason.data = item.qualitative_reason
        form.component_name.data = item.component_name
        form.notes.data = item.notes
    #
    # if item.result_type == 'None Detected':
    #     kwargs['report_none_detected'] = True
    #     kwargs['disable_fields'] += ['result_status', 'result_type', 'result',
    #                                  'supplementary_result', 'concentration',
    #                                  'measurement_uncertainty', 'qualitative',
    #                                  'qualitative_reason', 'outlier_reason']
    #
    # else:
    #     kwargs['disable_fields'] += ['report_none_detected']


    case_id = item.case_id
    test_id = item.test_id

    if request.method == 'POST':
        case_id = form.case_id.data
        test_id = form.test_id.data
        component_id = form.component_id.data
        if form.is_submitted() and form.validate():

            # Set the component_name string
            kwargs['component_name'] = Components.query.get(component_id).name
            result = form.result.data

            # If the component is in the assays scope, set the scope_id by
            # getting the assay from the test and querying the scope table.
            assay_id = Tests.query.get(test_id).assay_id
            scope_component = Scope.query.filter_by(assay_id=assay_id, component_id=component_id).first()
            if scope_component:
                kwargs['scope_id'] = scope_component.id

            # If the supplementary result is numerical, set the concentration
            # by trying to coerce into int.
            if form.supplementary_result.data:
                try:
                    kwargs['concentration'] = int(form.supplementary_result.data)
                except:
                    pass

        else:
            form = get_form_choices(form, case_id=form.case_id.data, test_id=form.test_id.data)

    # Get the tests for the case_id and results for the test_id
    kwargs['tests'] = Tests.query.filter_by(case_id=case_id).filter(Tests.test_status != "Pending").order_by(
        Tests.create_date.asc())
    kwargs['results'] = Results.query.filter_by(test_id=test_id)

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name,
                          alias=alias, **kwargs)

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
    CommentInstances.query.filter(
        CommentInstances.comment_item_type == 'Results',
        CommentInstances.comment_item_id == item_id
    ).delete()
    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():


    result_ids = [item.id for item in Results.query]
    CommentInstances.query.filter(
        CommentInstances.comment_item_type == 'Results',
        CommentInstances.comment_item_id.in_(result_ids)
    ).delete()

    _delete_items = delete_items(table, table_name, item_name)


    return _delete_items


@blueprint.route(f'/{table_name}/import_file', methods=['GET', 'POST'])
@login_required
def import_file():
    form = ImportToxDB()
    _import = import_items(form, table, table_name, item_name)

    return _import

    # form = ImportToxDB()
    # kwargs = {}
    # status = "Approved"
    # name = ""
    #
    # if request.method == 'POST':
    #     f = request.files.get('file')
    #     filename = f.filename
    #     savename = f"{f.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
    #     path = os.path.join(current_app.config['FILE_SYSTEM'], 'imports', savename)
    #     f.save(path)
    #     df = pd.read_csv(path)
    #
    #     date_cols = []
    #
    #     for col in df.columns:
    #         if 'date' in col:
    #             df[col] = pd.to_datetime(df[col], errors='ignore')
    #             date_cols.append(col)
    #         else:
    #             df[col].fillna("", inplace=True)
    #
    #     df['concentration'] = df['concentration'].replace("", np.nan).astype(float)
    #     df['measurement_uncertainty'] = df['measurement_uncertainty'].replace("", np.nan).astype(float)
    #
    #     field_data = {'db_status': 'Active',
    #                   'create_date': datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')),
    #                   'created_by': current_user.initials,
    #                   'modify_date': None,
    #                   'modified_by': "",
    #                   'revision': 0,
    #                   'delete_reason': "",
    #                   }
    #
    #     for idx, row in enumerate(df.iterrows()):
    #         dict = {}
    #         row = row[1]
    #         # print(idx)
    #         for item in row.iteritems():
    #             val = item[1]
    #             # print(val)
    #             if item[0] in date_cols:
    #                 if pd.isnull(item[1]):
    #                     val = None
    #             dict[item[0]] = val
    #             # dict[item[0]] = item[1]
    #             # print(type(item[1]))
    #
    #         field_data.update(dict)
    #         item = table(**field_data)
    #         db.session.add(item)
    #
    #     db.session.commit()
    #
    #     return redirect(url_for('results.view_list'))
    #
    # return render_template('import.html', form=form)


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():
    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    item = table.query.get(item_id)
    form = Attach()

    if request.method == 'POST':
        file = request.files['files']
        aux_results = AttachmentTypes.query.filter_by(name='External Results').first().id
        if form.type_id.data == aux_results:
            with fitz.open(stream=file.read(), filetype='pdf') as doc:
                item.result = len(doc)

            file.seek(0)
            db.session.commit()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    kwargs = default_kwargs.copy()

    alcohol_verbal_form = AlcoholVerbal()

    alcohol_verbal_form.batch_id.choices = [
        (batch.id, batch.batch_id)
        for batch in (
            Batches.query
            .join(Tests, Batches.id == Tests.batch_id)  # Join Batches to Tests
            .join(Results, Tests.id == Results.test_id)  # Join Tests to Results
            .join(Cases, Tests.case_id == Cases.id)  # Join Tests to Cases
            .join(CaseTypes, Cases.case_type == CaseTypes.id)  # Join Cases to CaseTypes
            .filter(CaseTypes.code.in_(['M', 'D']))  # Filter by CaseType codes
            .filter(Results.component_name.in_(['Ethanol', 'None Detected']))  # Filter by component name
            .filter(Results.result_status == 'Confirmed')  # Filter by result status
            .filter(Results.result_type.in_(['Detected', 'None Detected', 'Quantitated']))  # Filter by result type
            .filter(Batches.assay_id == 1)
            .filter(Results.id.isnot(None))  # Ensure the batch has results
            .order_by(Batches.create_date.desc())  # Order by creation date
            .distinct()  # Ensure unique batches
        )
    ]
    kwargs['alcohol_verbal_form'] = alcohol_verbal_form

    if alcohol_verbal_form.is_submitted() and alcohol_verbal_form.validate():
        batch_ids = [int(bid) for bid in alcohol_verbal_form.batch_id.data]
        alcohol_verbal_results = (
            Results.query
            .join(Cases, Results.case_id == Cases.id)  # Join Results to Cases
            .join(CaseTypes, Cases.case_type == CaseTypes.id)  # Join Cases to CaseTypes
            .join(Tests, Results.test_id == Tests.id)  # Join Results to Tests
            .join(Batches, Tests.batch_id == Batches.id)
            .join(Agencies, Cases.submitting_agency == Agencies.id)
            .filter(CaseTypes.code.in_(['M', 'D']))  # Filter by CaseType names
            .filter(Batches.id.in_(batch_ids))
            .filter(Results.component_name.in_(['Ethanol', 'None Detected']))
            .filter(Results.result_status == 'Confirmed')
            .filter(Results.result_type.in_(['Detected', 'None Detected', 'Quantitated']))
            .order_by(Agencies.name.asc(), Cases.case_number.asc())
            .all()
        )

        print(f'Results from form submission -- {alcohol_verbal_results}')

        print_alcohol_verbal(alcohol_verbal_results)
        todays_date = datetime.now().strftime('%Y%m%d')
        return redirect(f'/static/alcohol_verbal/{todays_date} Alcohol Verbal.xlsx')


    # kwargs['comments'] = {}
    # kwargs['comment_text'] = {}
    # results_comments = CommentInstances.query.filter_by(table_name=item_name). \
    #     with_entities(CommentInstances.item_id).all()
    # for x in results_comments:
    #     comment_codes = []
    #     comment_text = []
    #     comments = CommentInstances.query.filter_by(item_id=x[0]). \
    #         order_by(CommentInstances.comment_id.asc())
    #     for comment in comments:
    #         comment_codes.append(comment.comment.code)
    #         comment_text.append(comment.comment.comment)
    #     kwargs['comments'][x[0]] = comment_codes
    #     kwargs['comment_text'][x[0]] = comment_text

    kwargs['discipline'] = disciplines

    query = request.args.get('query')
    query_type = request.args.get('query_type')
    items = None

    print(kwargs)
    # If none selected, default to all
    query = Results.query

    if request.args.get('query') == 'pending':
        query = query.filter(Results.db_status == 'Active With Pending Changes')
    elif request.args.get('query') == 'removed':
        query = query.filter(Results.db_status == 'Removed')
    elif request.args.get('query') == 'removal-pending':
        query = query.filter(Results.db_status == 'Removal Pending')

    result_status_options = [
        'Withdrawn',
        'Not Tested',
        'Confirmed',
        'Saturated',
        'Trace',
        'Omit',
        'DNR',
        'Unconfirmed'
    ]

    result_type_options = [
        'Approximated',
        'Trace Detected',
        'None Detected',
        'Unsuitable For Analysis',
        'Quantitated',
        'Detected'
    ]
    result_statuses = request.args.getlist('result_statuses') or result_status_options
    result_types = request.args.getlist('result_types') or result_type_options

    query = query.filter(Results.result_status.in_(result_statuses))
    query = query.filter(Results.result_type.in_(result_types))

    kwargs['result_status_options'] = result_status_options
    kwargs['result_type_options'] = result_type_options
    kwargs['result_statuses'] = result_statuses
    kwargs['result_types'] = result_types

    kwargs['assays'] = [item.assay_name for item in Assays.query.order_by(Assays.assay_name)]
    selected_assays = request.args.getlist('assays')
    assay_options = [a.assay_name for a in Assays.query.filter_by(db_status='Active').order_by(Assays.assay_name)]

    # Default to all if none selected
    if not selected_assays:
        selected_assays = assay_options

    # Predefined list of disciplines
    discipline_options = ['Toxicology', 'Biochemistry', 'Histology', 'External']
    selected_disciplines = request.args.getlist('disciplines') or discipline_options

    # Join once, apply both filters
    query = query.join(Tests).join(Assays)
    query = query.filter(Assays.assay_name.in_(selected_assays))
    query = query.filter(Assays.discipline.in_(selected_disciplines))

    kwargs['assay_options'] = assay_options
    kwargs['selected_assays'] = request.args.getlist('assays')  # don't overwrite with all
    kwargs['discipline_options'] = discipline_options
    kwargs['selected_disciplines'] = selected_disciplines




    query_type = request.args.get('query_type')
    items = query

    _view_list = view_items(table, 
                            item_name, 
                            item_type, 
                            table_name, 
                            items=items, 
                            query=query, 
                            **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)
    kwargs = default_kwargs.copy()

    alias = f"{getattr(item, 'component_name')}"

    status_form = UpdateStatus()

    status_form.result_status.choices = [('Confirmed', 'Confirmed'), ('Unconfirmed', 'Unconfirmed'),
                                         ('Saturated', 'Saturated'), ('Withdraw', 'Withdraw'), ('DNR', 'DNR'),
                                         ('Omit', 'Omit')]
    status_form.result_type.choices = [('Detected', 'Detected'), ('Approximated', 'Approximated'),
                                       ('Quantitated', 'Quantitated'), ('None Detected', 'None Detected')]

    if request.method == 'GET':
        status_form.result_status.data = item.result_status
        status_form.result_type.data = item.result_type

    if status_form.is_submitted and status_form.validate():
        status_changed = item.result_status != status_form.result_status.data
        type_changed = item.result_type != status_form.result_type.data
        reason_only_status = not status_changed and status_form.result_status_update_reason.data.strip()
        reason_only_type = not type_changed and status_form.result_type_update_reason.data.strip()

        if status_changed or reason_only_status or type_changed or reason_only_type:
            form_clone = UpdateStatus(obj=item)
            form_data = form_clone.data

            if status_changed or reason_only_status:
                form_data['result_status'] = status_form.result_status.data
                form_data['result_status_updated'] = 'Y'
                form_data['result_status_update_reason'] = f'{status_form.result_status_update_reason.data} ({current_user.initials} {datetime.now().strftime("%m/%d/%Y %H:%M")})'

            if type_changed or reason_only_type:
                form_data['result_type'] = status_form.result_type.data
                form_data['result_type_updated'] = 'Y'
                form_data['result_type_update_reason'] = f'{status_form.result_type_update_reason.data} ({current_user.initials} {datetime.now().strftime("%m/%d/%Y %H:%M")})'

            form_clone.result_status.choices = status_form.result_status.choices
            form_clone.result_type.choices = status_form.result_type.choices
            form_clone.process(data=form_data)

            update_item(
                form_clone,
                item_id,
                table,
                item_type,
                item_name,
                table_name,
                requires_approval,
                name,
                **kwargs
            )

        return redirect(url_for('results.view', item_id=item.id))

    kwargs['status_form'] = status_form

    _view = view_item(item, alias, item_name, table_name, export_attachments=False, **kwargs)
    return _view



@blueprint.route(f'/{table_name}/get_tests/', methods=['GET', 'POST'])
@login_required
def get_tests():
    case_id = request.args.get('case_id', type=int)
    response = get_test_choices(case_id)

    return jsonify(response)


@blueprint.route(f'/{table_name}/get_components_and_results_json/', methods=['GET', 'POST'])
@login_required
def get_components_and_results_json():
    test_id = request.args.get('test_id', type=int)

    response = get_components_and_results(test_id)
    return jsonify(response)


@blueprint.route(f'/{table_name}/get_components/', methods=['GET', 'POST'])
@login_required
def get_components():
    test_id = request.args.get('test_id', type=int)

    assay_id = test_id.assay.id
    items = Components.query.filter_by(assay_id=assay_id).all()

    items_lst = []

    if len(items) != 0:
        for item in items:
            dict = {}
            dict['items'] = [item.id,
                             item.name,
                             ]

            items_lst.append(dict)

    return jsonify({'components': items_lst})


@blueprint.route(f'/{table_name}/get_units/', methods=['GET', 'POST'])
@login_required
def get_units():
    component_id = request.args.get('component_id', type=int)
    test_id = request.args.get('test_id', type=int)

    unit_id = 0
    test = Tests.query.get(test_id)
    assay_id = test.assay.id
    scope = Scope.query.filter_by(assay_id=assay_id, component_id=component_id).first()
    print(scope)
    if scope:
        unit_id = scope.unit.id

    print(unit_id)
    return jsonify(unit_id=unit_id)


def get_transition(component):
    transition = 0
    if component[-2] == " ":
        transition = int(component[-1])
        component = component[:-2]

    return component, transition


@blueprint.route(f'/{table_name}/import_results/', methods=['GET', 'POST'])
@login_required
def import_results():
    redirect_url = request.args.get('redirect_url')
    form = ImportToxDB()
    # batches = [(item.id, item.batch_id) for item in Batches.query.order_by(Batches.create_date.desc())]
    # batches.insert(0, (0, 'Please select a batch'))
    # form.batch_id.choices = batches
    new_df = None
    batch_id = request.args.get('batch_id', int)
    batch = Batches.query.get(batch_id)
    filename = None
    savename = None

    def map_status(x):
        try:
            return result_status_dict[x]
        except KeyError:
            raise ValueError(
                f"result_status value '{x}' not found in dictionary keys: {list(result_status_dict.keys())}")

    def parse_string(string, string_type=None):

        replace_dict = {
            "H ": " ",  # Remove H (homicide) from case number. Historical data only
            "S ": " ",  # Remove S (suspicious) from case number. Historical data only
            "  ": " ",  # Replace double-space with single space. This is present in test_id prior to LIMS
            "\uFF3B": "\u005B",  # Replace full-width left square bracket with standard keyboard left bracket
            "\uFF3D": "\u005D",  # Replace full-width right square bracket with standard keyboard right bracket
            "≥": "\u2265",
            "≤": "\u2264",
            "\u2032": "'"
        }

        if string_type != 'test_id':
            # For components we only want to replace the square brackets and double spaces (if any). So we remove
            # these the "H " and "S " from the dictionary prior to doing the replacement.
            del replace_dict['H ']
            del replace_dict['S ']

        if not pd.isnull(string):
            # If the file is imported and the left and right square brackets are displayed as
            # ï¼» and ï¼½, respectively, try to convert them into UTF-8. This may happen if the results file is
            # opened prior to import as Excel may change the encoding.
            try:
                string = string.encode("windows-1252").decode("utf-8")
            except:
                pass

            # Replace any values in the replace_dict
            for k, v in replace_dict.items():
                string = string.replace(k, v)

        return string

    def parse_comments(comment_string, column, item_id):
        comment_numbers = []
        comment_types = {'test_comments': 'Tests',
                         'result_comments': 'Results',
                         'component_comments': 'Components'}

        item_types = {'test_comments': 'Tests',
                      'result_comments': 'Results',
                      'component_comments': 'Results'}

        comment_type = comment_types[column]
        item_type = item_types[column]

        if not pd.isnull(comment_string):
            comments = re.findall("{(\d{1,2})}", comment_string)
            if comments:
                comment_numbers += comments
            matches = re.findall("{\d{1,2}}", comment_string)
            # Remove {X} from comments
            for match in matches:
                comment_string = comment_string.replace(match, "")

            if comment_string:
                # if the comment starts now with ;, get rid of it
                if comment_string[0] == ';':
                    comment_string = comment_string[1:].strip()
                    if not comment_string:
                        comment_string = None
            else:
                comment_string = None

            # Add manual comments to CommentInstances
            if comment_string and comment_string.strip():
                manual_comments = comment_string.split(";")
                print(manual_comments)
                if manual_comments:
                    for manual_comment in manual_comments:
                        # query the Comment Instances table to see if the comment already exists:
                        comment_exists = CommentInstances.query.filter_by(comment_item_id=item_id, comment_item_type=item_type, comment_text=manual_comment).count()
                        # if it doesn't exist, add the comment
                        if not comment_exists:
                            comment_item = CommentInstances(**{
                                'comment_text': manual_comment,
                                'comment_type': 'Manual',
                                'comment_item_id': item_id,
                                'comment_item_type': item_type,
                                'created_by': current_user.initials,
                                'create_date': datetime.now(),
                                'db_status': 'Active',
                                'locked': False,
                                'revision': 0
                            })

                            db.session.add(comment_item)

        # Add numbered comments to CommentInstances
        if comment_numbers:
            for comment_number in comment_numbers:
                comment = Comments.query.filter_by(code=comment_number, comment_type=comment_type).first()
                if comment:
                    comment_exists = CommentInstances.query.filter_by(
                        comment_id=comment.id,
                        comment_item_id=item_id,
                        comment_item_type=item_type
                    ).count()
                    if not comment_exists:
                        comment_item = CommentInstances(**{
                            'comment_id': comment.id,
                            'comment_type': comment.comment_type,
                            'comment_item_id': item_id,
                            'comment_item_type': item_type,
                            'created_by': current_user.initials,
                            'create_date': datetime.now(),
                            'db_status': 'Active',
                            'locked': False,
                            'revision': 0
                        })
                        db.session.add(comment_item)

        if comment_numbers:
            comment_numbers = ", ".join(sorted(comment_numbers))
        else:
            comment_numbers = None

        return comment_numbers, comment_string

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            f = request.files.get('file')
            import_path = os.path.join(current_app.config['FILE_SYSTEM'], 'imports')
            filename = secure_filename(f.filename)
            savename = f"{f.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
            save_path = os.path.join(import_path, savename)

            # batch_id = filename.split('.')[0].replace("_CSV_Report", "")
            batch_name = f.filename.split('.')[0].split(' ')[0]
            tests = Tests.query.filter_by(batch_id=batch_id)
            test_ids = [test.id for test in tests]
            results_dict = {result.test.test_name: [result.component_id for result in table.query.filter(Results.test_id.in_(test_ids))] for result in table.query.filter(Results.test_id.in_(test_ids))}

            if batch_name != batch.batch_id:
                flash(Markup('The filename of the selected CSV does not match the name of your batch'), 'error')
                return redirect(url_for(f'{table_name}.import_results', batch_id=batch_id,
                                        redirect_url=url_for('batches.view', item_id=batch_id)))

            result_no_unit = []

            if tests.count():

                # test_dict = {item.test_name[:-3].replace("_", " "): item.id for item in tests}
                test_dict = {item.test_name: item.id for item in tests}
                component_dict = {item.name: item.id for item in Components.query}
                checks_dict = {item.test_name: [item.specimen_check, item.gcet_specimen_check,
                                                item.transfer_check, item.sequence_check,
                                                item.sequence_check_2, item.load_check] for item in tests}

                f.save(save_path)
                df = pd.read_csv(save_path, dtype={'result': str})

                # helper: any of the checks contain 'NT'?
                def _has_nt(checks):
                    return any(c and 'NT' in str(c).upper() for c in (checks or []))

                # expected tests = all tests in batch that are NOT NT and not SAMQ
                expected = {name for name, checks in checks_dict.items() if not _has_nt(checks) and 'SAMQ' not in name}

                # find which column has test ids in raw CSV
                if 'test_id' in df.columns:
                    test_col = 'test_id'
                elif 'Sample Name' in df.columns:
                    test_col = 'Sample Name'
                else:
                    flash(Markup('This file does not match any test ids of this batch'), 'message')
                    return redirect(url_for(f'{table_name}.import_results',
                                            batch_id=batch_id,
                                            redirect_url=url_for('batches.view', item_id=batch_id)))

                # normalize CSV test ids the same way you do later
                def _norm_tid(x):
                    if pd.isna(x): return None
                    try:           return parse_string(str(x), string_type='test_id').strip()
                    except Exception:return str(x).strip()

                csv_ids = {t for t in (_norm_tid(v) for v in df[test_col]) if t and t.lower() not in ('sample name','test id')}

                # intersection count
                matched = expected & csv_ids

                if len(matched) < len(expected):
                    missing = sorted(expected - csv_ids)
                    preview = ", ".join(missing[:10]) + (" …" if len(missing) > 10 else "")
                    flash(Markup('This file does not match any test ids of this batch'), 'message')
                    # IMPORTANT: redirect back to import page, which renders flashes
                    return redirect(url_for(f'{table_name}.import_results',
                                            batch_id=batch_id,
                                            redirect_url=url_for('batches.view', item_id=batch_id)))

                if batch.assay.assay_name in ['GCVO-ZZ', 'GCNO-ZZ']:
                    header_dict = {
                        'Sample Name': 'test_id',
                        'Component': 'component_id',
                        'Est. Conc.': 'concentration',
                        'Reported Result': 'result',
                        'Result Confirmed': 'result_status',
                        'Test Comments': 'test_comments'
                    }
                    blank_columns = ['supplementary_result', 'measurement_uncertainty', 'report_reason',
                                     'result_comments', 'component_comments', 'qual', 'QN_QU', 'trace_detected']
                    df.columns = [header_dict.get(col, col) for col in df.columns]

                    mask = df['test_id'] == 'Sample Name'
                    df.loc[mask, :] = np.nan
                    df['result'] = df['result'].str.replace('>', '\u2265', regex=False)
                    df['component_id'] = df['component_id'].str[:-2]
                    df.dropna(inplace=True, how='all')
                    for column in blank_columns:
                        df[column] = np.nan
                    print(f'DF: {df}')
                # Remove blank rows
                df = df[~df['test_id'].isna()]

                # result_status, trace_detected, qualitative, qual, QN_QU - only in LCQ and QTON exports and not in GCET
                # For GCET, PRIM, COHN all results are confirmed
                result_status_dict = {'c': 'Confirmed', 'x': 'Unconfirmed', 's': 'Saturated', np.nan: 'Trace',
                                      '-': 'Not Assessed - Recon Dil'}
                if 'result_status' not in df.columns:
                    df['result_status'] = 'c'
                if 'trace_detected' not in df.columns:
                    df['trace_detected'] = np.nan
                if 'qualitative' not in df.columns:
                    df['qualitative'] = np.nan
                else:
                    df['qualitative'] = df['qualitative'].map(lambda x: x.lower() if not pd.isnull(x) else x)
                if 'qual' not in df.columns:
                    df['qual'] = np.nan
                else:
                    df['qual'] = df['qual'].map(lambda x: x.lower() if not pd.isnull(x) else x)
                if 'QN_QU' not in df.columns:
                    df['QN_QU'] = 'QN'

                df['qual'] = df['qual'].map(lambda x: x.lower().replace('q', 'Y') if not pd.isnull(x) else x)
                df['test_id'] = df['test_id'].map(lambda x: parse_string(x, string_type='test_id'))

                # parse_comments for tests_comments here BEFORE rows are removed
                test_names0 = []
                for test in tests:
                    test_name0 = test.test_name
                    if test_name0 not in test_names0:
                        test_names0.append(test_name0)
                        test_df0 = df[df['test_id'] == test_name0]
                        if len(test_df0):
                            if 'test_comments' in test_df0.columns:
                                parse_comments(test_df0['test_comments'].iloc[0], 'test_comments', test.id)

                # Remove rows where there is no result_status unless trace_detected has a value
                df = df[
                    (~df['component_id'].isna()) 
                    & (~df['result_status'].isna()) 
                    | (~df['trace_detected'].isna())
                ].reset_index(drop=True)

                try:
                    df['result_status'] = df['result_status'].str.lower().apply(map_status)
                except AttributeError:
                    raise ValueError('ALL rows of result_status are blank. Check CSV before proceeding.')
                df['result'] = df['result'].map(lambda x: parse_string(x))
                df['supplementary_result'] = df['supplementary_result'].map(lambda x: parse_string(x))

                new_df = pd.DataFrame()

                if table.query.count():
                    result_id = table.query.order_by(table.id.desc()).first().id
                else:
                    result_id = 0

                test_names = []
                for test in tests:
                    test_name = test.test_name
                    # test_name = test.test_name[:-3].replace("_", " ")
                    if test_name not in test_names:
                        test_names.append(test_name)
                        test_df = df[df['test_id'] == test_name]
                        confirmed_results = test_df[test_df['result_status'] == 'Confirmed']
                        row = pd.Series()
                        row_test_id = False
                        try:
                            placeholder = int(test_dict[test_name])
                            row_test_id = True
                        except KeyError:
                            row_test_id = False

                        if any('NT' in str(check) for check in checks_dict[test_name] if check) and \
                                'SAMQ' not in test_name:
                            result_id += 1
                            row['id'] = result_id
                            row['test_id'] = int(test_dict[test_name])
                            row['case_id'] = Tests.query.get(int(row['test_id'])).case.id
                            print(f'FOUND NT')
                            row['result_status'] = 'Not Tested'
                            row['component_name'] = 'None Tested'
                            row['component_id'] = 954
                            row['result_type'] = 'None Detected'
                            new_df = pd.concat([new_df, row], axis=1)
                        elif not len(confirmed_results) and row_test_id and 'SAMQ' not in test_name:
                            result_id += 1
                            row['id'] = result_id
                            row['test_id'] = int(test_dict[test_name])
                            # print(row)
                            # print(row['test_id'])
                            # print(type(row['test_id']))
                            row['case_id'] = Tests.query.get(int(row['test_id'])).case.id
                            # row['case_id'] = Tests.query.get(84619).case.id
                            print(f'CHECKS DICT TEST NAME: {checks_dict[test_name]}')
                            row['result_status'] = 'Confirmed'
                            row['component_name'] = 'None Detected'
                            row['component_id'] = 1
                            row['result_type'] = 'None Detected'
                            # print(row)
                            new_df = pd.concat([new_df, row], axis=1)

                        skip_row_loop = (
                            batch.assay.assay_name == 'GCNO-ZZ' and
                            not len(confirmed_results) and
                            row_test_id and
                            'SAMQ' not in test_name
                        )

                        if not any('NT' in str(check) for check in checks_dict[test_name] if check) and not skip_row_loop:

                            for idx, row in test_df.iterrows():
                                # Remove leading/trailing white spaces
                                test_name = row['test_id'].strip()
                                component_name = parse_string(row['component_id'].strip(), 'component')
                                if component_name not in component_dict.keys():
                                    raise ValueError(f'The following result is not in the LIMS Components table: '
                                                     f'{component_name}. Please contact the FLD LIMS team.')

                                # if test_name not in result_tests and row['result_status'] == 'Confirmed':
                                #     result_tests.append(test_name)
                                # Get test_id using the test_name
                                # test_id = test_dict.get(test_name)
                                # test = None
                                # if test_id:
                                #     test = Tests.query.get(test_id)
                                # else:
                                #     print(test_name)

                                # If the test_id is not None, i.e., the test name from the import matches
                                # a test name in the database, add the result.
                                if test:
                                    try:
                                        if component_dict.get(component_name) in results_dict[test_name]:
                                            flash(Markup(f'Results have already been uploaded'), 'message')
                                            return redirect(url_for('batches.view', item_id=test.batch_id))
                                    except KeyError:
                                        pass
                                    result_id += 1
                                    row['id'] = result_id
                                    row['test_id'] = test.id
                                    # case_id
                                    row['case_id'] = test.case.id
                                    # component_name
                                    row['component_name'] = component_name
                                    #component_id
                                    row['component_id'] = component_dict.get(component_name)
                                    # scope_id
                                    #scope_id = None
                                    component_scope = Scope.query.filter_by(assay_id=test.assay_id,
                                                                            component_id=row['component_id']).first()
                                    if component_scope:
                                        scope_id = component_scope.id
                                        row['scope_id'] = scope_id
                                        row['unit_id'] = component_scope.unit_id
                                    # if component is not in scope AND unit_id is in the results CSV, leave scope_id None and use the imported unit_id
                                    elif 'unit_id' in df.columns:
                                        row['scope_id'] = None
                                        try:
                                            row['unit_id'] = int(row['unit_id'])
                                        except:
                                            row['unit_id'] = None
                                    else:
                                        row['scope_id'] = None
                                        row['unit_id'] = None
                                        this_result = (test.id, component_name, result_id)
                                        result_no_unit.append(this_result)
                                        # flash(Markup(f"{this_result}, This test's scope does not include this component. Thus, NO SCOPE or UNIT is stored for this result."), 'error') # turn into pop-up so it doesn't disappear
                                        

                                    # result - No action
                                    # concentration, result_type and supplementary_result
                                        # if "concentration" can be passed to a float, set concentration
                                        # to that value and the result_type to 'Quantitated'
                                        # if supplementary_result can be passed as float, set concentration
                                        # as the supplementary_results (removing ',') and result_type = 'Approximated'
                                        # If the supplementary result has "<", set concentration to nan and result_type
                                        # to 'Detected'.

                                    conc = None
                                    measurement_uncertainty = None
                                    # concentration and measurement_uncertainty are not in LCQ reports
                                    if 'concentration' not in df.columns:
                                        if '\u00B1' in row['result']:
                                            conc = row['result'].split(' \u00B1')[0].strip().replace(",", "")
                                            measurement_uncertainty = \
                                                row['result'].split(' \u00B1')[1].strip().replace(",", "")
                                    else:
                                        conc = row['concentration']
                                        if isinstance(conc, str):
                                            conc = conc.replace(",", "")
                                        measurement_uncertainty = row['measurement_uncertainty']
                                        if isinstance(measurement_uncertainty, str):
                                            measurement_uncertainty = measurement_uncertainty.replace(",", "")
                                    # Remove tilda from the supplementary result
                                    supp_result = row['supplementary_result']
                                    if isinstance(supp_result, str):
                                        supp_result = supp_result[supp_result.find("~")+1:]

                                    trace = row['trace_detected']

                                    if row['result'] == 'Detected':
                                        if supp_result is not None and not pd.isna(supp_result):
                                            result_type = 'Approximated'
                                        else:
                                            result_type = 'Detected'
                                    elif row['result'] == 'Not Detected':
                                        result_type = 'None Detected'
                                    else:
                                        result_type = 'Quantitated'
                                    try:
                                        conc = float(conc)
                                    except:
                                        if (not pd.isnull(supp_result)) and (pd.isnull(trace)):
                                            conc = np.nan
                                            result_type = 'Detected'
                                            if '<' not in supp_result:
                                                try:
                                                    conc = float(supp_result.replace(",", ""))
                                                    result_type = 'Approximated'
                                                except:
                                                    pass

                                        else:
                                            if not pd.isnull(trace):
                                                supp_result = trace[trace.find(":") + 2:]
                                                conc = np.nan
                                                result_type = "Trace Detected"
                                            else:
                                                conc = np.nan
                                                result_type = 'Detected'

                                    # if row['result_status'] == 'x':
                                    #     result_type = 'Not Detected'

                                    row['concentration'] = conc
                                    row['measurement_uncertainty'] = measurement_uncertainty
                                    row['result_type'] = result_type
                                    row['supplementary_result'] = supp_result
                                    print('ROW RESULT ----------')
                                    print(row['result'])
                                    print('END RESULT --------------')
                                    if isinstance(row['result'], str) and row['result'].strip() == 'UNA':
                                        row['result'] = None
                                        row['result_type'] = 'Unsuitable For Analysis'
                                        row['scope_id'] = None
                                        row['unit_id'] = None

                                    # qualitative and qualitative_reason
                                    qual = np.nan
                                    qual_reason = np.nan
                                    if not pd.isnull(row['qual']) and row['qual'] == 'y' and not \
                                            row['qualitative'] == 'y':
                                        qual = 'Y'
                                        qual_reason = 'Batch Qual (PA)'
                                    elif row['qualitative'] == 'y':
                                        qual = 'Y'
                                        qual_reason = 'Batch Qual'
                                    if row['QN_QU'] == 'QU':
                                        qual = 'Y'
                                        qual_reason = 'Assay Qual'

                                    row['qualitative'] = qual
                                    row['qualitative_reason'] = qual_reason

                                    comment_columns = ['result_comments', 'component_comments']

                                    result_comment_numbers = []
                                    for column in comment_columns:
                                        if column in df.columns:
                                            comments = row[column]
                                            comment_numbers, comments = parse_comments(comments, column, result_id)
                                            result_comment_numbers.append(comment_numbers)
                                            row[f'{column}_manual'] = comments

                                    row['comment_numbers'] = ", ".join(sorted([x for x in result_comment_numbers if x]))
                                    new_df = pd.concat([new_df, row], axis=1)

                new_df = new_df.T.sort_values(by='test_id').reset_index(drop=True)
                #new_df.to_csv(rf"F:\ForensicLab\LIMS\LIMS Modules\1. Case Management\Results\Imported batches\{batch_name}.csv", index=False)

                if not len(result_no_unit) == 0:
                    flash(Markup(f"{escape(result_no_unit)} - "f"These test(s) scope does not include this component. Thus, NO SCOPE or UNIT is stored for this result. (tests.id, component, results.id)"), 'message')                
                redirect_url = url_for('batches.view', item_id=batch_id)

            else:
                flash(Markup(f"Batch <b>{batch_name}</b> not found! No results imported"), 'warning')
                return redirect(redirect_url)

    _import = import_items(form, table, table_name, item_name, df=new_df, admin_only=False, redirect_url=redirect_url,
                            filename=filename, savename=savename
                          )

    return _import


@blueprint.route(f'/{table_name}/<int:item_id>/set_result_status/', methods=['GET', 'POST'])
@login_required
def set_result_status(item_id):
    item = table.query.get(item_id)
    result_status = request.args.get('result_status')

    if result_status:
        item.result_status = result_status

        db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


@blueprint.route(f'/{table_name}/add_external_result/', methods=['GET', 'POST'])
@login_required
def add_external_result():
    kwargs = default_kwargs.copy()
    test_id = request.args.get('test_id', type=int)
    case_id = Tests.query.get(test_id).case_id
    page_unit = Units.query.filter_by(name='page(s)').first().id
    kwargs['request'] = 'POST'

    form = get_form_choices(Add(), case_id, test_id)

    component_name = 'See Attached Report'
    component_id = Components.query.filter_by(name=component_name).first().id

    form.case_id.data = case_id
    form.test_id.data = test_id
    form.component_id.data = component_id
    form.unit_id.data = page_unit
    form.result_status.data = 'Confirmed'
    form.result.data = '0'  # Number of pages
    form.result_type.data = 'Detected'
    form.qualitative.data = ''
    form.qualitative_reason.data = ''
    form.component_name.data = component_name
    form.submit.data = True
    form.csrf_token.data = generate_csrf()

    add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    result_id = table.query.filter_by(test_id=test_id, component_id=component_id).order_by(table.id.desc()).first().id

    return redirect(url_for(f'{table_name}.attach', item_id=result_id))
