from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, SelectField, \
    TextAreaField, SelectMultipleField, DateField
import numpy as np
from datetime import datetime

class DrugFilter(FlaskForm):
    discipline = SelectField('Discipline', 
                             choices=[('Toxicology', 'Toxicology'), ('Biochemistry', 'Biochemistry'), ('Histology', 'Histology'), ('Drug', 'Drug'), ('External', 'External'), ('Physical', 'Physical')], 
                             default='Toxicology', coerce=str)
    date_type = SelectField('Date Type')
    start_date = DateField('Start Date', default=datetime(datetime.now().year, 1, 1))
    end_date = DateField('End Date', default=datetime.now().date())
    date_by = SelectField('By', choices=[('Month', 'Month'), ('Year', 'Year'), ('Quarter', 'Quarter')])
    case_type = SelectMultipleField('Case Type(s)', coerce=int)
    component_id = SelectMultipleField('Component', coerce=int)
    reported_only = SelectField('Reported Only Results',
                                choices=[('Yes', 'Yes'), ('No', 'No')], default=('Yes', 'Yes'))
    result_status = SelectMultipleField('Result Status',         
                                        choices=[
            ('Confirmed', 'Confirmed'),
            ('Saturated', 'Saturated'),
            ('Trace', 'Trace'),
            ('Unconfirmed', 'Unconfirmed'),
            ('Not Tested', 'Not Tested'),
            ('Withdrawn', 'Withdrawn'),
            ('DNR', 'DNR'),
            ('Omit', 'Omit')
        ], coerce=str)
    specimen_type = SelectMultipleField('Specimen Type', coerce=int)
    color_palette = SelectField('Color Palette', choices=[
        ('muted', 'Muted'),
        ('blues', 'Blues'),
        ('greens', 'Greens'),
        ('grays', 'Grays'),
        ('cool', 'Cool'),
    ], default='muted')
    drug_class = SelectField('Drug Class', coerce=int)
    and_or = SelectField('And/Or', choices=[('AND', 'AND'), ('OR', 'OR')], default='')
    submit = SubmitField('Apply')