from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, SelectMultipleField, DateField
from wtforms.validators import DataRequired, Optional
from flask_wtf.file import FileField

class Base(FlaskForm):

    equipment_type = SelectField('Equipment Type', validators=[DataRequired()])
    equipment_id = SelectField('Equipment ID', coerce=str, validate_choice=False, validators=[DataRequired()])
    service_types = SelectMultipleField('Service Type(s)', validators=[DataRequired()])
    # vendor_agency = SelectField('Vendor Agency', coerce=int, validators=[Optional()])
    vendor_division = SelectField('Vendor Division', coerce=int, validate_choice=False, validators=[Optional()])
    vendor_id = SelectField('Vendor Personnel', coerce=int, validate_choice=False, validators=[DataRequired()])
    service_date = DateField('Service Date', validators=[DataRequired()], render_kw={'type': 'date'})
    issue = TextAreaField('Reason')
    resolution = TextAreaField('Action(s) Taken')
    attachments = FileField('Attachments', render_kw={'multiple': True})

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
    submit = SubmitField('Update')
