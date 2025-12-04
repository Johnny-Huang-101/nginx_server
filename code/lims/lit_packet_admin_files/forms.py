from flask_wtf import FlaskForm

from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    lit_packet_admin_id = SelectField('Assay Name', coerce=int, validators=[DataRequired(message="ID Required")], render_kw={'disabled': 'disabled'})
    file_name = StringField('File Name', validators=[DataRequired(message="File Name Required")])
    redact_type = SelectField('Redact Type', validators=[DataRequired(message='Redact Type Required')])

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    lit_packet_admin_id = SelectField('Assay Name', coerce=int, validators=[DataRequired(message="ID Required")], render_kw={'disabled': 'disabled'})
    file_name = StringField('File Name', validators=[DataRequired(message="File Name Required")])
    redact_type = SelectField('Redact Type', validators=[DataRequired(message='Redact Type Required')])
    submit = SubmitField('Update')


class FilesUpdate(Base):
    use_file = SelectField('Include this file', validators=[DataRequired(message='Required')])
    redact_type = SelectField('Redact Type', validators=[DataRequired(message='Redact Type Required')])
    submit = SubmitField('Update')
