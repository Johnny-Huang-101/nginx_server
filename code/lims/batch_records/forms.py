from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectField, TextAreaField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    batch_id = SelectField('Batch', coerce=int, validators=[DataRequired()])
    file_name = FileField('Select File(s) to attach', render_kw={'multiple': True}, validators=[DataRequired()])
    submit = SubmitField('Submit')

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
