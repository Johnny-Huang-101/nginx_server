from lims.models import *
from lims.view_templates.views import *
from lims.forms import Import, Attach

from lims.comment_instances.forms import *
from lims.comment_instances.functions import get_form_choices, process_form

# Set item global variables
item_type = 'Comment Instance'
item_name = 'Comment Instances'
table = CommentInstances
table_name = 'comment_instances'
name = ['comment_type', 'comment_text']  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {'template': template,
                  'redirect': redirect_to}

# Create blueprint
blueprint = Blueprint(table_name, __name__)
# Filesystem path
path = None


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    comment_item_type = request.args.get('comment_item_type')
    comment_item_id = request.args.get('comment_item_id', type=int)

    print(comment_item_type)

    # If a redirect_url parameter is provided as an argument.
    # redirect the user to that URL. Useful to redirect the user
    # back to the view page after adding a comment
    redirect_url = request.args.get('redirect_url')
    if redirect_url:
        kwargs['redirect'] = redirect_url

    form = get_form_choices(Add(), comment_item_id=comment_item_id, comment_item_type=comment_item_type)
    if request.method == 'POST':
        if form.validate_on_submit():
            form = get_form_choices(form, comment_item_id=comment_item_id, comment_item_type=form.comment_item_type.data)
            kwargs.update(process_form(form))
        else:
            form = get_form_choices(form, comment_item_id=comment_item_id, comment_item_type=form.comment_item_type.data)



    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
    return _add


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    comment_item_type = request.args.get('comment_item_type')
    comment_item_id = request.args.get('comment_item_id')
    redirect_url = request.args.get('redirect_url')

    if redirect_url:
        kwargs['redirect'] = redirect_url

    form = get_form_choices(Edit(), comment_item_id=comment_item_id, comment_item_type=comment_item_type)
    if request.method == 'POST':
        if form.validate_on_submit():
            form = get_form_choices(form, comment_item_id=form.comment_item_id.data, comment_item_type=form.comment_item_type.data)
            kwargs.update(process_form(form))
        else:
            form = get_form_choices(form, comment_item_id=form.comment_item_id.data, comment_item_type=form.comment_item_type.data)

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, admin_only=True, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    comment_item_type = request.args.get('comment_item_type')
    comment_item_id = request.args.get('comment_item_id', int)
    redirect_url = request.args.get('redirect_url')

    if redirect_url:
        kwargs['redirect'] = redirect_url

    form = get_form_choices(Approve(), comment_item_id=comment_item_id, comment_item_type=comment_item_type)
    if request.method == 'POST':
        if form.validate_on_submit():
            form = get_form_choices(form, comment_item_id=form.comment_item_id.data, comment_item_type=form.comment_item_type.data)
            kwargs.update(process_form(form))
        else:
            form = get_form_choices(form, comment_item_id=form.comment_item_id.data, comment_item_type=form.comment_item_type.data)

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, admin_only=True, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    comment_item_type = request.args.get('comment_item_type')
    comment_item_id = request.args.get('comment_item_id', type=int)
    redirect_url = request.args.get('redirect_url')

    if redirect_url:
        kwargs['redirect'] = redirect_url

    form = get_form_choices(Update(), comment_item_id=comment_item_id, comment_item_type=comment_item_type)
    if request.method == 'POST':
        if form.validate_on_submit():
            form = get_form_choices(form, comment_item_id=form.comment_item_id.data, comment_item_type=form.comment_item_type.data)
            kwargs.update(process_form(form))
        else:
            form = get_form_choices(form, comment_item_id=form.comment_item_id.data, comment_item_type=form.comment_item_type.data)

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, admin_only=True, **kwargs)

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



    _delete_item = delete_item(form, item_id, table, table_name, item_name, name, admin_only=False)

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    if current_user.permissions not in ['Owner', 'Admin']:
        abort(403)

    kwargs = {'modules': module_definitions}

    _view_list = view_items(table, item_name, item_type, table_name, **kwargs)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = " - ".join([getattr(item, x) for x in name])
    _view = view_item(item, alias, item_name, table_name,)
    return _view


@blueprint.route(f'/{table_name}/get_items/')
@login_required
def get_items():
    """
    Dynamically populate the item_id field based on the selected item_type/module.
    Items from that module will be displayed using their alias.

    """

    item_type = request.args.get('item_type')
    item_choices = []
    comment_choices = []
    item_table = module_definitions[item_type][0]
    item_alias = module_definitions[item_type][2]
    if item_type:
        items = item_table.query.order_by(getattr(item_table, item_alias))
        comments = Comments.query.filter(Comments.comment_type.in_(['Global', item_type]))
        if items.count():
            item_choices = [{'id': item.id, 'name': getattr(item, item_alias)} for item in items]
            item_choices.insert(0, {'id': 0, 'name': 'Please select an item'})
        else:
            item_choices.append({'id': 0, 'name': 'This item type has no types'})

        if comments.count():
            comment_choices = [{'id': comment.id, 'name': f"{comment.code} - {comment.comment_type} - {comment.comment}"} for comment in comments]
            comment_choices.insert(0, {'id': 0, 'name': '---'})
        else:
            comment_choices.append({'id': 0, 'name': 'This item type has no comments'})

    else:
        item_choices.append({'id': 0, 'name': 'No item type selected'})


    return jsonify({'items': item_choices, 'comments': comment_choices})