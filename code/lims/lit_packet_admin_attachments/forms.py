from flask_wtf import FlaskForm

from wtforms import StringField, SubmitField, TextAreaField, SelectField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    route = SelectField('Route', validators=[DataRequired(message="Route required.")])

    attachment_type = SelectField('Attachment Type', validators=[DataRequired(message="Attachment Type Required")])
    attachment_name = StringField('Attachment Name', validators=[Optional()])
    attachment_path = HiddenField('Attachment Path', validators=[Optional()])
    lit_admin_template_id = IntegerField('Template Name', validators=[Optional()], render_kw={'disabled': 'disabled'})


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')

