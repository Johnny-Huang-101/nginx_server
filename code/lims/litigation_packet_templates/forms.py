from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, FileField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    name = StringField('Template Name', validators=[DataRequired(message='Must have a template name.')])
    file = FileField('Template File', validators=[DataRequired(message='Template file is required.')])
    path = StringField('Path', validators=[Optional()], render_kw={"hidden": "True"})

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
