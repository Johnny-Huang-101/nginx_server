from flask_login import login_user, logout_user
from flask_mail import Message
from werkzeug.security import generate_password_hash

from lims import mail
from lims.models import Users, Agencies, Personnel
from lims.users.forms import Add, Edit, Approve, Update, Login, UpdatePassword
from lims.personnel.forms import Add as PersonnelAdd
from lims.personnel.functions import get_form_choices as get_personnel_form_choices
from lims.view_templates.views import *
from lims.forms import Import, Attach


item_name = 'Users'
item_type = 'User'
table_name = 'users'
table = Users
name = 'full_name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = ['password', 'pass_confirm']  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
default_kwargs = {'template': template}
# FIle system path
file_system_path = os.path.join(current_app.config['FILE_SYSTEM'], 'signatures')
# Create Blueprint
blueprint = Blueprint('users', __name__)

# File system path

##### ADD #####

@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
def add():
    kwargs = default_kwargs.copy()
    form = Add()
    redirect_url = request.args.get('redirect_url')

    # If there are currently no users
    # Set the permissions field to 'Owner' and disable
    if not table.query.count():
        form.permissions.data = 'Owner'
        form.permissions.render_kw = {'disabled': True}
        form.create_personnel.data = "No"
        form.create_personnel.render_kw = {'disabled': True}

    # Remove 'Owner' and 'Admin' from permission choices for 'Admin'
    if current_user.is_active and current_user.permissions == "Admin":
        form.permissions.choices = form.permissions.choices[2:]


    # Do not include the password fields in the modifications table
    kwargs['ignore_fields'] = ignore_fields
    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            # for field in form:
            #     kwargs[field.name] = field.data
            kwargs['initials'] = form.initials.data
            # Generate the users full name
            kwargs['full_name'] = " ".join([form.first_name.data, form.middle_initial.data, form.last_name.data])
            # Generate password hash to store in database
            kwargs['password_hash'] = generate_password_hash(form.password.data)
            # Set the number of inccorect logins to 0
            kwargs['incorrect_logins'] = 0

            kwargs['create_date'] = datetime.now()
            # If this is the first user being added, get the initials from the form
            # rather than current_user. Ignore all fields in the form.
            redirect_url = url_for(f"personnel.view_list")

            if table.query.count() == 0:
                kwargs['created_by'] = form.initials.data
                kwargs['ignore_fields'] = [field.name for field in form]
            else:
                kwargs['created_by'] = current_user.initials

            # Save signature to the users folder in the filesystem
            # set the has_signature property to 'Yes'
            if form.signature_file.data:
                # Create new folder in the filesystem if needed
                os.makedirs(file_system_path, exist_ok=True)
                file = form.signature_file.data
                kwargs['has_signature'] = 'Yes'
                path = os.path.join(file_system_path, f"{form.initials.data}.png")
                file.save(path)
                flash('Signature file successfully uploaded', 'success')

            # Create a personnel entry for the user. All required fields need to be provided.
            if form.create_personnel.data == 'Yes':
                kwargs['personnel_id'] = Personnel.get_next_id()
                personnel_form = get_personnel_form_choices(PersonnelAdd())
                personnel_form.first_name.data = form.first_name.data
                personnel_form.last_name.data = form.last_name.data
                personnel_form.agency_id.data = 1 # San Francisco Office of the Chief Medical Examiner
                personnel_form.email.data = form.email.data
                personnel_form.job_title.data = form.job_title.data
                personnel_form.cell.data = form.cellphone_number.data
                personnel_form.phone.data = form.telephone_number.data
                # Without lines below, there will be a validation error
                personnel_form.submitter.data = "Yes"
                personnel_form.receives_report.data = "No"

                add_item(personnel_form, Personnel, 'Personnel', 'Personnel', 'personnel', False, 'full_name', **kwargs.copy())
            if form.create_personnel.data == 'Yes' and redirect_url:
                return redirect(redirect_url)
            
    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, admin_only=True, redirect_url=redirect_url, **kwargs)
    return _add

@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = Approve()
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    form = Update()
    kwargs = default_kwargs.copy()
    # Ignore password fields
    kwargs['ignore_fields'] = ignore_fields
    item = Users.query.get_or_404(item_id)

    # Remove 'Owner' and 'Admin' from permission choices for 'Admin'
    if current_user.is_active and current_user.permissions == "Admin":
        form.permissions.choices = form.permissions.choices[2:]

    if request.method == 'POST':
        # Update the users full name if any of first_name, middle_initials or last_name change
        item.full_name = " ".join([form.first_name.data, form.middle_initial.data, form.last_name.data])
        if form.is_submitted() and form.validate():
            # If both the password fields are not blank (i.e. a new password was chosen)
            # create new password hash.
            if (form.password.data != "") and (form.pass_confirm.data != ""):
                item.password_hash = generate_password_hash(form.password.data)

            # If a signature file was provided, save the file to the filesystem
            if form.signature_file.data:
                file = form.signature_file.data
                kwargs['has_signature'] = 'Yes'
                path = os.path.join(file_system_path, f"{form.initials.data}.png")
                file.save(path)
                flash('Signature file successfully uploaded', 'success')

            # Reset the number of correct logins if the status is Active
            if form.status.data == 'Active':
                item.incorrect_logins = 0


    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, admin_only=True, **kwargs)

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

@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments

@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    _view_list = view_items(table, item_name, item_type, table_name, admin_only=True)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name, admin_only=True)
    return _view


##### UPDATE PASSWORD #####

@blueprint.route('/users/<int:item_id>/update_password', methods = ['GET', 'POST'])
@login_required
def update_password(item_id):
    item = table.query.get_or_404(item_id)

    if (current_user.id != item.id) and (current_user.permissions not in ['Admin', 'Owner']):
        abort(403)

    form = UpdatePassword()

    if form.is_submitted() and form.validate():
        item.password_hash = generate_password_hash(form.password.data)
        db.session.commit()

        flash('Password Successfully Changed!', 'success')
        return redirect(url_for('core.index'))

    return render_template(f'{table_name}/update_password.html', item=item, form=form)


@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_users():
    form = Import()
    df = None
    filename = None
    savename = None

    if request.method == 'POST':
        f = request.files.get('file')
        filename = f.filename
        ext = filename.split(".")[1]
        print(ext)
        savename = f"{f.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.{ext}"
        path = os.path.join(current_app.root_path, 'static/Uploads', savename)
        f.save(path)
        if ext == 'csv':
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        print(df)

    _import = import_items(form, table, table_name, item_name, df, filename, savename)

    return _import

@blueprint.route('/login', methods = ['GET', 'POST'])
def login():
    form = Login()
    user_lst = Users.query.all()
    invalid_credentials = False
    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            user = Users.query.filter_by(username=str.lower(form.username.data)).first()
            if user is not None:
                if user.status == 'Active':
                    if user.check_password(form.password.data) and user is not None:
                        session.clear()
                        session.permanent = True
                        user.last_login = datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific'))
                        user.incorrect_logins = 0
                        db.session.add(user)
                        db.session.commit()

                        session['case_search_error'] = ""
                        session['case_pending'] = False

                        print(f"{user.initials} logged in - {datetime.now()}")
                        login_user(user)
                        flash('Successfully logged in', 'success')
                        # If a user was trying to visit a page that requires a login
                        # flask saves that URL as 'next'.
                        next = request.args.get('next')

                        # So let's now check if that next exists, otherwise we'll go to
                        # the welcome page.
                        if next == None or not next[0]=='/':
                            next = url_for('core.home')

                        return redirect(next)
                    else:
                        # if the user submits the wrong username/password,
                        # increment the incorrect_logins property. If the number
                        # of correct logins is 5 or greater, set the status to blocked.
                        invalid_credentials = True
                        # flash('Invalid credentials!', 'error')
                        user.incorrect_logins += 1
                        user.last_incorrect_login = datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific'))
                        if user.incorrect_logins >= 5:
                            user.status = 'Blocked'
                            db.session.commit()
                            return render_template('error_pages/password_attempts_exceeded.html')
                        db.session.commit()
                else:
                    return render_template('error_pages/password_attempts_exceeded.html')
            else:
                flash('Invalid credentials', 'error')
        else:
            invalid_credentials = True

    return render_template(f'{table_name}/login.html', form=form, user_lst=user_lst, invalid_credentials=invalid_credentials)


##### LOGOUT #####

@blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have successfully logged out', 'success')
    return redirect(url_for(f'{table_name}.login'))


@blueprint.route(f'/{table_name}/<int:item_id>/send_email', methods=['GET', 'POST'])
@login_required

def send_email(item_id):

    user = Users.query.get_or_404(item_id)
    user_email = user.email

    msg = Message('Automated Email from FLDB',
                  sender='no-reply@sfgov.org',
                  recipients=['luke.rodda@sfgov.org', 'tyler.devincenzi@sfgov.org'],
                  cc=['daniel.pasin@sfgov.org'],
                  html=f"Hi<br>"
                       "<br>"
                       f"<b>This is a test email using SMTP relay with mercury.sfgov.org</b>")
    mail.send(msg)
    print("Email successfully sent!")
    return redirect(url_for(f'{table_name}.view', item_id=user.id))