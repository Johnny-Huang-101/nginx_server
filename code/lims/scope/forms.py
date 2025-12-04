from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired
from lims.choices import *


class Base(FlaskForm):

    component_id = SelectMultipleField('Component', coerce=int, validators=[DataRequired()])
    assay_id = SelectMultipleField('Assay(s)', coerce=int, validators=[DataRequired()])
    limit_of_detection = StringField('Limit of Detection')
    internal_standard = SelectField('Internal Standard?', choices=no_yes)
    internal_standard_conc = StringField('Internal Standard Conc.', render_kw={'disabled': True})
    unit_id = SelectField('Default Units', coerce=int, validators=[DataRequired()])
    validated = SelectField('Validation Completed', choices=yes_no)
    # rank = StringField('Rank')
    report_notes = TextAreaField('Report Notes')
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
