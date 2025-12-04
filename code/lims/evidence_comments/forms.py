from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf.file import FileField


class Base(FlaskForm):

    section = SelectField('Section', validators=[DataRequired()])
    field = SelectField('Field', render_kw={'disabled': True}, validators=[DataRequired()])
    issue = SelectField('Issue', render_kw={'disabled': True}, validators=[DataRequired()])
    comment = StringField('Comment (if other)', render_kw={'readonly': True})

class Add(Base):

    submit = SubmitField("Submit")

class Edit(Base):
    submit = SubmitField("Submit")


class Approve(Base):
    submit = SubmitField("Submit")

class Update(Base):
    submit = SubmitField("Submit")


class UploadEnvelopeReference(FlaskForm):

    file = FileField('Select File')
    submit = SubmitField('Submit')