from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional
from lims.choices import yes_no

class Base(FlaskForm):

    agency_id = SelectField('Agency', coerce=int, validators=[DataRequired()])
    name = StringField('Division/Unit Name', validators=[DataRequired()])
    abbreviation = StringField('Abbreviation')
    street_number = StringField('Street Number')
    street_address = StringField('Street Address')
    unit_number = StringField('Unit/Suite Number')
    floor = StringField('Floor')
    city = StringField('City')
    state_id = SelectField('State', coerce=int)
    zipcode = StringField('ZIP')
    client = SelectField('Client?', choices=yes_no)
    stakeholder = SelectField('Stakeholder?', choices=yes_no)
    reference_material_provider = SelectField('Reference Material Provider?', choices=yes_no)
    service_provider = SelectField('Service Provider?', choices=yes_no)
    email = StringField('Email', validators=[Email(), Optional()])

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    unique_fields = ['agency_id', 'name']

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
