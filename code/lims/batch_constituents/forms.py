from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional
from flask_wtf.file import FileRequired
from lims.models import Agencies, CaseTypes, RetentionPolicies
from datetime import datetime
import pytz
from pytz import timezone
from flask_wtf.file import FileField
from flask import Markup

class Base(FlaskForm):
    batch_id = SelectField('Batch', coerce=int, validators=[DataRequired('Must select a batch')])
    instrument_id = SelectField('Instrument', coerce=int, validators=[DataRequired('Please select an instrument')])
    batch_template_id = SelectField('Batch Template ID', coerce=int)
    constituent_id = SelectMultipleField('Available Constituents', coerce=int,
                                                validators=[DataRequired('Please select at least one standard/solution')])

class Add(Base):
    submit = SubmitField('Submit')

class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Submit')


