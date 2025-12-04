from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):

    equipment_id = StringField('Hub Name', validators=[DataRequired()])
    model_number = StringField('Model Number', validators=[DataRequired()])
    serial_number = StringField('Serial Number', validators=[DataRequired()])
    ip_address = StringField('IP Address', validators=[Optional()])
    division_id = SelectField('Division', coerce=int, validators=[DataRequired()])
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()], validate_choice=False,
                              choices=[(0, 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[DataRequired()],
                                 choices=[('', 'Please Select')])
    status_id = SelectField('Status', coerce=int, validate_choice=False)

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
