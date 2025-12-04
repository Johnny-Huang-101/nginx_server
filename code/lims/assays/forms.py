from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, DateField, IntegerField, FloatField
from wtforms.validators import DataRequired, Optional
from lims.models import discipline_choices


class Base(FlaskForm):

    assay_name = StringField("Assay Name")
    discipline = SelectField('Discipline', validators=[DataRequired()])
    sop_ref = StringField("SOP Reference")
    instrument_id = SelectField('Default Instrument', coerce=int)
    batch_template_id = SelectField('Default Batch Template', coerce=int, validators=[Optional()])
    sample_volume = StringField('Sample Volume (mL)')
    num_tests = StringField('Number of Tests')
    order = StringField('Order')
    specimen_type_in_test_name = SelectField('Include Specimen Type in Test name?', choices=[('Yes', 'Yes'), ('No', 'No')])
    status_id = SelectField('Status', coerce=int, validators=[DataRequired()])
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
