from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, DateField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):

    equipment_id = HiddenField('Equipment ID', validators=[DataRequired()])
    serial_number = StringField('Serial Number', validators=[DataRequired()])
    acquired_date = DateField("Acquired Date", validators=[Optional()])
    status_id = SelectField('Status', coerce=int, validators=[DataRequired()])
    last_service_date = DateField('Last Service Date', validators=[Optional()])
    due_service_date = DateField("Service Due Date", validators=[Optional()])
    vendor_id = SelectField('Service Provider', coerce=int)  # validators=[DataRequired()])
    model_number = StringField('Model Number')
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()], validate_choice=False,
                              choices=[(0, 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[DataRequired()],
                                 choices=[('', 'Please Select')])
    hub_id = SelectField('Hub', coerce=int, validators=[Optional()])
    glycol = StringField('Glycol', validators=[Optional()])
    cims = StringField('SmartScan Name', validators=[Optional()])

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
