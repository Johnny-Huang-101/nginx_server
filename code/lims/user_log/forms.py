from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, TextAreaField, SelectField, DateField, BooleanField
from wtforms.validators import DataRequired, Optional
from lims.fields import NullableDateField

"""
FORMS NOT USED IN THIS MODULE - 
"""
class Base(FlaskForm):

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


class CustomExport(FlaskForm):
    user = SelectField('Users')
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])
    # include_date_range = BooleanField('Include Date Range')
    submit = SubmitField('Submit')
