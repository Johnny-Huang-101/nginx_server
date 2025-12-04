from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp
from wtforms import ValidationError
from wtforms.widgets import PasswordInput
from lims.models import Users
# Select Field Choices

background_check = [
    ('Yes', 'Yes'),
    ('No', 'No')
]

permissions = [
    ('Owner', 'Owner'),
    ('Admin', 'Admin'),
    ('Developer', 'Developer'),
    ('FLD', 'FLD'),
    ('MED', 'MED'),
    ('INV', 'INV'),
    ('ADM', 'ADM'),
    ('FLD-MethodDevelopment', 'FLD-MethodDevelopment'),
    ('MED-Autopsy', 'MED-Autopsy'),
    ('FLD-Administrative', 'FLD-Administrative'),
    ('ADM-Management', 'ADM-Management')
]

status = [
    ('Active', 'Active'),
    ('Paused', 'Paused'),
    ('Blocked', 'Blocked'),
    ('Deactivated', 'Deactivated')
]

# Messages


# Login Form
class Login(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()],
                             widget=PasswordInput(hide_value=False))
    submit = SubmitField('Login')


class Base(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    middle_initial = StringField('Middle Initial')
    last_name = StringField('Last Name', validators=[DataRequired()])
    initials = StringField('Initials', validators=[DataRequired(),
                                                   Length(3, 3, message='Initials must be 3 characters long')])
    title = StringField('Title', render_kw={'placeholder': 'B.S., M.S., Ph.D., etc.'})
    email = StringField('Email', validators=[DataRequired(),Email(message='This must be a valid email')])
    username = StringField('Username', validators=[DataRequired()])
    job_class = StringField('Job Class', validators=[DataRequired()])
    job_title = StringField('Job Title', validators=[DataRequired()])
    background_check = SelectField('Background Check', choices=background_check)
    permissions = SelectField('Permissions', default='FLD', choices=permissions)
    status = SelectField('Status', choices=status)
    signature_file = FileField('Signature file', render_kw={'accept': ".png"})
    create_personnel = SelectField('Create Personnel Entry?', choices=[('Yes', 'Yes'), ('No', 'No')])
    cellphone_number = StringField('Cell', validators=[Optional(), Regexp(r'^\d{3}-\d{3}-\d{4}$', message="Please re-enter phone number with format 123-456-7890.")])
    telephone_number = StringField('Telephone', validators=[Optional(), Regexp(r'^\d{3}-\d{3}-\d{4}$', message="Please re-enter phone number with format 123-456-7890.")])

    unique_fields = ['initials', 'email', 'username']

    def validate_job_class(self, job_class):
        if not job_class.data.isnumeric():
            raise ValidationError('Job class must be numeric')


class Add(Base):
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message="Please enter a password"),
            EqualTo('pass_confirm', message="Passwords must match"),
            Length(8, 32, message='Password must be between 8 and 32 characters')
        ],
    )
    pass_confirm = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message="Please re-enter your password")
        ],
    )
    submit = SubmitField('Submit')

    # def validate_email(self, email):
    #     if Users.query.filter_by(email=email.data).first():
    #         raise ValidationError('Email has already been registered!')
    #
    # def validate_initials(self, initials):
    #     if Users.query.filter_by(initials=initials.data).first():
    #         raise ValidationError('Initials have already been used!')
    #
    # def validate_username(self, username):
    #     if Users.query.filter_by(username=username.data.lower()).first():
    #         raise ValidationError('Username has already been used!')
    #

class Edit(Base):
    password = PasswordField(
        'Password',
        # validators=[
        #     EqualTo('pass_confirm', message="Passwords must match"),
        #     Length(8, 32, message='Password must be between 8 and 32 characters')
        # ],
    )
    pass_confirm = PasswordField('Confirm Password')
    submit = SubmitField('Submit')

    def validate_password(self, password):
        if password.data != "":
            password.validators = [
            EqualTo('pass_confirm', message="Passwords must match"),
            Length(8, 32, message='Password must be between 8 and 32 characters')
            ]
            self.pass_confirm.validators = [DataRequired(message="Please re-enter your password")]


class Approve(Base):
    password = PasswordField(
        'Password',
        # validators=[
        #     EqualTo('pass_confirm', message="Passwords must match"),
        #     Length(8, 32, message='Password must be between 8 and 32 characters')
        # ],
    )
    pass_confirm = PasswordField('Confirm Password')
    submit = SubmitField('Submit')

    def validate_password(self, password):
        if password.data != "":
            password.validators = [
            EqualTo('pass_confirm', message="Passwords must match"),
            Length(8, 32, message='Password must be between 8 and 32 characters')
            ]
            self.pass_confirm.validators = [DataRequired(message="Please re-enter your password")]


class Update(Base):
    password = PasswordField(
        'Password',
        # validators=[
        #     EqualTo('pass_confirm', message="Passwords must match"),
        #     Length(8, 32, message='Password must be between 8 and 32 characters')
        # ],
    )
    pass_confirm = PasswordField('Confirm Password')
    submit = SubmitField('Submit')

    def validate_password(self, password):
        if password.data != "":
            password.validators = [
            EqualTo('pass_confirm', message="Passwords must match"),
            Length(8, 32, message='Password must be between 8 and 32 characters')
            ]
            self.pass_confirm.validators = [DataRequired(message="Please re-enter your password")]


# Change Password Form
class UpdatePassword(FlaskForm):
    password = PasswordField('Password', default='password',
                             validators=[DataRequired(message="Please enter a password"),
                                         EqualTo('pass_confirm', message="Passwords must match.")])
    pass_confirm = PasswordField('Confirm Password',default='password',
                                 validators=[DataRequired(message="Please re-enter your password")])
    submit = SubmitField('Submit')
