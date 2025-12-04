from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional
from lims.models import Assays, Instruments, Tests
from flask_wtf.file import FileField
class Base(FlaskForm):

    name = StringField('Template Name')
    instrument_id = SelectField('Instrument', coerce=int)
    sample_format_id = SelectField('Sample Format', coerce=int)
    max_samples = StringField('Maximum Samples')
    template_file = FileField('Sequence Template File', render_kw={'accept': ".csv"})

class Add(Base):
    submit = SubmitField('Submit')

class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')
