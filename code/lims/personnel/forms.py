from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField
from wtforms.fields.simple import HiddenField
from wtforms.validators import DataRequired, Email, Optional, Regexp
from lims.choices import yes_no

class Base(FlaskForm):

    first_name = StringField('First Name', validators=[DataRequired()])
    middle_name = StringField('Middle Name/Initial')
    last_name = StringField('Last Name', validators=[DataRequired()])
    titles = StringField('Title(s)', render_kw={"placeholder": "e.g., PhD, MD, DO, etc."})
    agency_id = SelectField('Agency', coerce=int, validators=[DataRequired()], validate_choice=False)
    division_id = SelectField('Division/Unit', coerce=int, validate_choice=False)
    job_title = StringField('Job Title', validators=[DataRequired()])
    id_number = StringField('Badge/ID Number')
    email = StringField('Email', validators=[Email(), DataRequired()])
    phone = StringField('Phone', validators=[Optional(), Regexp(r'^\d{3}-\d{3}-\d{4}$',  message="Please re-enter phone number with format 123-456-7890.")])
    cell = StringField('Cell', validators=[Optional(), Regexp(r'^\d{3}-\d{3}-\d{4}$', message="Please re-enter phone number with format 123-456-7890.")])
    submitter = SelectField('Submitter?', choices=yes_no)
    receives_report = SelectField('Receives Report?', choices=yes_no)
    status_id = SelectField('Status', coerce=int, validators=[DataRequired()])

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Submit')


class AddFromRequest(FlaskForm):

    first_name = StringField('First Name', validators=[DataRequired()])
    middle_name = StringField('Middle Name/Initial')
    last_name = StringField('Last Name', validators=[DataRequired()])
    titles = StringField('Title(s)', render_kw={"placeholder": "e.g., PhD, MD, DO, etc."})
    agency_id = SelectField('Agency', coerce=int, validators=[DataRequired()], validate_choice=False)
    division_id = SelectField('Division/Unit', coerce=int, validate_choice=False)
    job_title = StringField('Job Title', validators=[DataRequired()])
    id_number = StringField('Badge/ID Number')
    email = StringField('Email', validators=[Email(), DataRequired()])
    phone = StringField('Phone')
    cell = StringField('Cell')
    submitter = HiddenField()
    receives_report = HiddenField()


    personnel_submit = SubmitField('Submit')