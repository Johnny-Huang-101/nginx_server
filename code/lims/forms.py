from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
from wtforms import SubmitField, TextAreaField, SelectField
from flask_wtf.file import FileField
from wtforms.validators import Optional

class Import(FlaskForm):
    file = FileField('Select File', render_kw={'accept': ".csv"}, validators=[DataRequired()])
    submit = SubmitField('Submit')

class Attach(FlaskForm):
    files = FileField('Select File(s) to attach', validators=[Optional()], render_kw={'multiple': True})
    type_id = SelectField('Attachment Type', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Submit')
