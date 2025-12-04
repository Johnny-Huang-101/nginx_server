from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, TextAreaField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Email
from lims.models import discipline_choices


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    discipline = SelectField('Discipline', choices=discipline_choices, validators=[DataRequired()])
    template_file = FileField('Record Template', render_kw={'accept': ".docx, .dotx"})


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
