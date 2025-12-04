from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired
from lims.models import Genders


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    # abbreviation = StringField('Abbreviation')

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
