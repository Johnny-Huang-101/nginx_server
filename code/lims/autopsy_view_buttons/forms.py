from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, TextAreaField, SubmitField, DateField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):

    button = SelectField('Button', validators=[DataRequired()])
    discipline = SelectField('Discipline', validators=[Optional()], validate_choice=False, render_kw={'disabled': True})
    specimen_types = SelectMultipleField('Specimen Types', validators=[Optional()], coerce=str,
                                         render_kw={'disabled': True})

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
