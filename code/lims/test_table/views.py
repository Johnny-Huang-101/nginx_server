# # Flask Imports
# from flask import request, Blueprint, render_template
# from flask_login import login_required
#
# # Application Imports
# from lims.models import Modifications, TestTable
# from lims.test_table.forms import Add, Edit, Approve, Update
# from lims.view_templates.views import add_item, edit_item, view_items, \
#     revert_item_changes, approve_item, update_item, delete_item_soft, \
#     approve_item_delete, reject_item_delete, restore_item, delete_item
#
# # Set item global variables
# item_type = 'Test Item'
# item_name = 'Test Table'
# table = TestTable
# table_name = 'test_table'
# name = 'string_field'  # This selects what property is displayed in the flash messages
# requires_approval = True  # controls whether the approval process is required. Can be set on a view level
# ignore_fields = []  # fields not added to the modification table
# disable_fields = []  # fields to disable
# template = 'form.html'  # template to use for add, edit, approve and update
# redirect = 'view'
# kwargs = {'template': template,
#           'redirect': redirect}
#
# blueprint = Blueprint('test_table', __name__)
#
# ##### ADD #####
#
# @blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
# @login_required
# def add():
#     form = Add()
#
#     _add = add_item(form=form, table=table, item_type=item_type, item_name=item_name, table_name=table_name,
#                     requires_approval=requires_approval, name=name, **kwargs)
#
#     if request.method == 'POST':
#         print(form.data)
#     return _add
#
#
# ##### EDIT #####
#
# @blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
# @login_required
# def edit(item_id):
#     form = Edit()
#     event = request.args.get('event')
#     name = form.string_field.data
#     _edit = edit_item(form, item_id, event, table, item_type, item_name, table_name, name)
#
#     return _edit
#
# ##### VIEW ALL #####
#
#
# @blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
# @login_required
# def view_list():
#
#     _view_list = view_items(table, item_name, item_type, table_name)
#
#     return _view_list
#
#
# ##### VIEW #####
#
#
# @blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
# @login_required
# def view(item_id):
#
#     item = table.query.get_or_404(item_id)
#
#     delete_mod = Modifications.query.filter_by(record_id=item_id, event='DELETE',
#                                                status='Approved', table_name=item_name).first()
#
#     mods = Modifications.query.filter_by(record_id=item_id,
#                                          status='Approved', table_name=item_name)
#
#     # Generate modification tooltips (hover behaviour) for item fields
#     tooltips = {}
#     for mod in mods:
#         if mod.field != "Reason":
#             if mod.original_value == "":
#                 original_value = "[None]"
#             else:
#                 original_value = mod.original_value
#             if mod.new_value == "":
#                 new_value = "[None]"
#             else:
#                 new_value = mod.new_value
#
#             tooltips[mod.field] = f"{original_value} > {new_value} " \
#                                        f"({mod.submitter.initials} > {mod.reviewer.initials})"
#
#     print(tooltips)
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
#     if item.db_status in ['Pending', 'Active']:
#         event = 'CREATED'
#     else:
#         event = 'UPDATED'
#
#     return render_template(
#         f'{table_name}/view.html',
#         item=item,
#         event=event,
#         pending_submitters = pending_submitters,
#         delete_mod=delete_mod,
#         tooltips=tooltips,
#         n_pending=n_pending,
#         pending_mods=pending_mods
#     )
#
#
# ##### APPROVE #####
#
# @blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
# @login_required
# def approve(item_id):
#     form = Approve()
#     event = request.args.get('event')
#     name = form.string_field.data
#     _approve = approve_item(form, item_id, event, table, item_type, item_name, table_name, name)
#
#     return _approve
#
#
# ##### UPDATE #####
#
#
# @blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
# @login_required
# def update(item_id):
#     form = Update()
#     name = form.string_field.data
#     status = 'Approved'
#     _update = update_item(form, item_id, table, item_type, item_name, table_name, status, name)
#
#     return _update
#
# ##### REVERT CHANGES #####
#
#
# @blueprint.route(f'/{table_name}/revert_changes/')
# @login_required
# def revert_changes():
#
#     item_id = request.args.get('item_id', 0, type=int)
#     field = request.args.get('field_name', type=str)
#     field_value = request.args.get('field_value', 0, type=str)
#
#     _revert_changes = revert_item_changes(item_id, field, field_value, item_name)
#
#     return _revert_changes
#
# ##### SOFT DELETE #####
#
# @blueprint.route(f'/{table_name}/<int:item_id>/delete_soft', methods=['GET', 'POST'])
# @login_required
# def delete_soft(item_id):
#     name = table.query.get_or_404(item_id).name
#     _delete_soft = delete_item_soft(item_id, table, table_name, item_name, name)
#
#     return _delete_soft
#
#
# ##### APPROVE DELETE #####
# @blueprint.route(f'/{table_name}/<int:item_id>/approve_delete', methods=['GET', 'POST'])
# @login_required
# def approve_delete(item_id):
#     name = table.query.get_or_404(item_id).name
#     _approve_delete = approve_item_delete(item_id, table, table_name, item_name, name)
#
#     return _approve_delete
#
#
# ##### REJECT DELETE #####
#
# @blueprint.route(f'/{table_name}/<int:item_id>/reject_delete', methods=['GET', 'POST'])
# @login_required
# def reject_delete(item_id):
#     name = table.query.get_or_404(item_id).name
#     _reject_delete = reject_item_delete(item_id, table, table_name, item_name, name)
#
#     return _reject_delete
#
#
# ##### RESTORE #####
#
# @blueprint.route(f'/{table_name}/<int:item_id>/restore', methods=['GET', 'POST'])
# @login_required
# def restore(item_id):
#     name = table.query.get_or_404(item_id).name
#     _restore_item = restore_item(item_id, table, table_name, item_name, name)
#
#     return _restore_item
#
#
# ##### HARD DELETE #####
#
# @blueprint.route(f'/{table_name}/<int:item_id>/delete_hard', methods=['GET', 'POST'])
# @login_required
# def delete(item_id):
#     form = Add()
#     name = table.query.get_or_404(item_id).string_field
#     _delete_item = delete_item(form, item_id, table, table_name, item_name, name)
#
#     return _delete_item
