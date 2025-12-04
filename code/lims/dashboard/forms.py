from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, SelectField, IntegerField, \
    TextAreaField, SelectMultipleField, DateField
import numpy as np
from datetime import datetime
import datetime as dt

from wtforms.fields.simple import HiddenField


class CaseFilter(FlaskForm):

    start_date = DateField('Start Date', default=datetime(2025, 1, 1).date())
    end_date = DateField('End Date', default=datetime.now().date())
    date_by= SelectField('By', choices=[('Month', 'Month'), ('Year', 'Year'), ('Quarter', 'Quarter')])
    case_type = SelectMultipleField('Case Type(s)', coerce=int)
    # tat_traces = SelectMultipleField('TAT Traces', coerce=int, choices=[(15, '<15 days'),
    #                                                         (30, '<30 days'),
    #                                                         (45, '<45 days'),
    #                                                         (60, '<60 days'),
    #                                                         (90, '<90 days')])
    submit = SubmitField('Apply')


class SpecialProjectForm(FlaskForm):
    special_project_name = StringField('Special Project Name')
    num_items = IntegerField('Number of Items')
    num_completed = IntegerField('Number of Completed Items')
    remove_view = HiddenField(default="no")
    submit = SubmitField('Submit')