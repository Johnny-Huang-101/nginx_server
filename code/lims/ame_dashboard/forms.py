from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, SelectField, IntegerField, \
    TextAreaField, SelectMultipleField, DateField
import numpy as np
from datetime import datetime
import datetime as dt

from wtforms.fields.simple import HiddenField


class CaseFilter(FlaskForm):

    submit = SubmitField('Apply')


class SpecialProjectForm(FlaskForm):
    submit = SubmitField('Submit')