from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, SelectField, \
    TextAreaField, SelectMultipleField, DateField
import numpy as np
from datetime import datetime
import datetime as dt
class MODFilter(FlaskForm):
    mod_choices = [
        ('All', 'All'),
        ('Accident', 'Accident'),
        ('Homicide', 'Homicide'),
        ('Suicide', 'Suicide'),
        ('Natural', 'Natural'),
        ('Undetermined', 'Undetermined'),
        (None, 'Not Listed')
    ]

    start_date = DateField('Start Date', default=datetime.today()-dt.timedelta(days=30))
    end_date = DateField('End Date', default=datetime.now().date())
    mod = SelectField('MOD', choices=mod_choices)
    component = SelectField('Component', coerce=int)
    case_number = StringField('Case Number')

    submit = SubmitField('Apply')


class ComponentFilter(FlaskForm):

    start_date = DateField('Start Date', default=datetime(2023, 1, 1))
    end_date = DateField('End Date', default=datetime.now().date())
    component = SelectField('Component', coerce=int)
    case_number = StringField('Case Number')
    submit = SubmitField('Apply')
