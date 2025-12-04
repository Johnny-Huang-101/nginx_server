from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional
from lims.models import Assays, Instruments, Tests
from flask_wtf.file import FileField, FileAllowed



class Base(FlaskForm):
    report_id = SelectField('report', coerce=int)
    comment_id = SelectField('Comment', coerce=int)

class Add(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')

