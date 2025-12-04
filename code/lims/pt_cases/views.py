
from lims.models import PTCases, PTResults, Cases
from lims.pt_cases.forms import Base, Add, Edit, Approve, Update
from lims.forms import Attach, Import
from lims.view_templates.views import *

# Set item global variables
item_type = 'Proficiency Test Case'
item_name = 'Proficiency Test Cases'
table = PTCases
table_name = 'pt_cases'
name = 'id'  # This selects what property is displayed in the flash messages
requires_approval = True  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/<int:item_id>/add', methods=['GET', 'POST'])
@login_required
def add(item_id):
    kwargs = default_kwargs.copy()
    form = Add()

    viewtable = PTResults
    viewtable_name = 'proficiencytests'
    viewitems = [item for item in viewtable.query.filter_by(case_id=item_id).all()]
    kwargs['items'] = viewitems
    kwargs['viewtable_name'] = viewtable_name

    try:
        thiscase = viewtable.query.filter_by(case_id=item_id).first().case.case_number
        kwargs['case_num'] = thiscase
        caseid = viewtable.query.filter_by(case_id=item_id).first().case.id
        kwargs['case_id'] = caseid
    except:
        pass

    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()

    case_id = PTCases.query.filter_by(id=item_id).first().case_id  # .first().case_id
    case_num = Cases.query.filter_by(id=case_id).first().case_number
    kwargs['case_id'] = case_id
    kwargs['case_num'] = case_num

    viewtable = PTResults
    viewtable_name = 'proficiencytests'
    viewitems = [item for item in viewtable.query.filter_by(case_id=case_id).all()]
    kwargs['items'] = viewitems
    kwargs['viewtable_name'] = viewtable_name

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = Approve()

    case_id = PTCases.query.filter_by(id=item_id).first().case_id  # .first().case_id
    case_num = Cases.query.filter_by(id=case_id).first().case_number
    kwargs['case_id'] = case_id
    kwargs['case_num'] = case_num

    viewtable = PTResults
    viewtable_name = 'proficiencytests'
    viewitems = [item for item in viewtable.query.filter_by(case_id=case_id).all()]
    kwargs['items'] = viewitems
    kwargs['viewtable_name'] = viewtable_name

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = Update()

    case_id = PTCases.query.filter_by(id=item_id).first().case_id  # .first().case_id
    case_num = Cases.query.filter_by(id=case_id).first().case_number
    kwargs['case_id'] = case_id
    kwargs['case_num'] = case_num

    viewtable = PTResults
    viewtable_name = 'proficiencytests'
    viewitems = [item for item in viewtable.query.filter_by(case_id=case_id).all()]
    kwargs['items'] = viewitems
    kwargs['viewtable_name'] = viewtable_name

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
    # Get just Q-Cases from Cases table then outerjoin with PTCases to show all Q-Cases regardless of PT status
    items = Cases.query.filter_by(case_type=1)
    items = items.outerjoin(PTCases)

    _view_list = view_items(table, item_name, item_type, table_name, length=-1, items=items, PTCases=PTCases)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):

    my_form = Base()
    labels = {
        'notes': my_form.notes.label.text,
        'summary': my_form.summary.label.text,
        'good_qual_comment': my_form.good_qual_comment.label.text,
        'good_quant_comment': my_form.good_quant_comment.label.text,
        'bad_quant_comment': my_form.bad_quant_comment.label.text,
        'bad_FN_comment': my_form.bad_FN_comment.label.text,
        'bad_FP_comment': my_form.bad_FP_comment.label.text,
        'incidental_neutral_comment': my_form.incidental_neutral_comment.label.text,
        'beyondscope_good_comment': my_form.beyondscope_good_comment.label.text,
        'incidental_good_comment': my_form.incidental_good_comment.label.text,
        'incidental_bad_comment': my_form.incidental_bad_comment.label.text,
    }

    item = PTCases.query.get_or_404(item_id)

    case_id = PTCases.query.filter_by(id=item_id).first().case_id  # .first().case_id
    case_num = Cases.query.filter_by(id=case_id).first().case_number

    viewtable = PTResults
    viewtable_name = 'pt_results'
    viewitems = [item for item in viewtable.query.filter_by(case_id=case_id).all()]

    delete_mod = Modifications.query.filter_by(record_id=str(item_id), event='DELETE',
                                               status='Approved', table_name=item_name).first()

    mods = Modifications.query.filter_by(record_id=str(item_id),
                                         status='Approved', table_name=item_name)

    # Generate modification tooltips (hover behaviour) for item fields
    tooltips = {}
    for mod in mods:
        if mod.field != "Reason":
            if mod.original_value == "":
                original_value = "[None]"
            else:
                original_value = mod.original_value
            if mod.new_value == "":
                new_value = "[None]"
            else:
                new_value = mod.new_value

            tooltips[mod.field] = f"{original_value} > {new_value}" \
                                       f"({mod.submitter.initials} > {mod.reviewer.initials})"

    # Get pending modifications for alerts
    pending_mods = Modifications.query.filter_by(record_id=str(item_id),
                                                 status='Pending',
                                                 table_name=item_name).all()

    # This will show which fields are pending changes
    pending_mods = [mod for mod in pending_mods]
    # This says how many fields are pending changes
    n_pending = len(pending_mods)
    submitter = ""
    for mod in pending_mods:
        submitter += mod.submitter.initials

    return render_template(
        f'{table_name}/view.html',
        item=item,
        pending_submitter=submitter,
        delete_mod=delete_mod,
        tooltips=tooltips,
        n_pending=n_pending,
        pending_mods=pending_mods,
        labels=labels,
        case_id=case_id,
        case_num=case_num,
        viewitems=viewitems,
    )
