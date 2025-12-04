from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional
from lims.models import Assays, Instruments, Tests
from flask_wtf.file import FileField, FileAllowed



class Base(FlaskForm):
    case_id = SelectField('Case', coerce=int)
    discipline = SelectField('Discipline')
    report_template_id = SelectField('Record Template', coerce=int, validate_choice=False)
    specimen_id = SelectField('Specimen', coerce=int)
    result_id_order = StringField('Result Order')  # , render_kw={'hidden': True})
    result_id = SelectMultipleField('Results', coerce=int)
    primary_result_id = SelectMultipleField('Primary Results', coerce=int)
    observed_result_id = SelectMultipleField('Observed Results', coerce=int)
    qualitative_result_id = SelectMultipleField('Qualitative Results', coerce=int)
    submit = SubmitField('Submit')

class Add(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')

