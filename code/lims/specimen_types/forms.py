from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired
from lims.models import discipline_choices


class Base(FlaskForm):

    name = StringField('Name', validators=[DataRequired(message="Specimen type must have a name.")])
    code = StringField('Code', validators=[DataRequired(message="Specimen type must have a code.")])
    state_id = SelectField("State", coerce=int)
    # preparation_id = SelectField('Type', coerce=int)
    discipline = SelectMultipleField('Discipline', choices=discipline_choices)
    # specimen_site_id = SelectField('Default Specimen Collection Site', coerce=int)
    collection_container_id = SelectField('Default Collection Container', coerce=int)
    unit_id = SelectField('Default Units', coerce=int)
    default_assays = SelectMultipleField('Default Assays')

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
