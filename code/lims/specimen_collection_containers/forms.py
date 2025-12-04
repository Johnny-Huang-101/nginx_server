from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField, SelectMultipleField
from wtforms.validators import Optional, DataRequired
from lims.models import discipline_choices


class Base(FlaskForm):
    type_id = SelectField('Type', coerce=int)
    name = StringField('Descriptive Name', validators=[Optional()])
    discipline = SelectMultipleField('Discipline', choices=discipline_choices, validators=[DataRequired()])

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
