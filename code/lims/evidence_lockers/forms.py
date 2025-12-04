from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    equipment_id = StringField('Equipment ID', validators=[DataRequired()])
    status_id = SelectField('Status', coerce=int, validators=[DataRequired()])
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()], validate_choice=False,
                              choices=[(0, 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[DataRequired()],
                                 choices=[('', 'Please Select')])

    occupied = BooleanField('Occupied?')
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
