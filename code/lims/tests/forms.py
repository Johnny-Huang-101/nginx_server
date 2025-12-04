from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, BooleanField, SelectMultipleField, \
    IntegerField
from wtforms.validators import ValidationError, DataRequired, Optional


class Base(FlaskForm):
    toxicology_requested = BooleanField('Toxicology', render_kw={'disabled': True})
    biochemistry_requested = BooleanField('Biochemistry', render_kw={'disabled': True})
    histology_requested = BooleanField('Histology', render_kw={'disabled': True})
    external_requested = BooleanField('External', render_kw={'disabled': True})
    physical_requested = BooleanField('Physical', render_kw={'disabled': True})
    drug_requested = BooleanField('Drug', render_kw={'disabled': True})
    toxicology = BooleanField('Toxicology', render_kw={'class': 'check', 'type': 'checkbox'})
    biochemistry = BooleanField('Biochemistry', render_kw={'class': 'check', 'type': 'checkbox'})
    histology = BooleanField('Histology', render_kw={'class': 'check', 'type': 'checkbox'})
    external = BooleanField('External', render_kw={'class': 'check', 'type': 'checkbox'})
    physical = BooleanField('Physical', render_kw={'class': 'check', 'type': 'checkbox'})
    drug = BooleanField('Drug', render_kw={'class': 'check', 'type': 'checkbox'})
    case_id = SelectField('Case Number', coerce=int, validators=[DataRequired()])
    specimen_id = SelectField('Specimens', coerce=int, validators=[DataRequired()], validate_choice=False)
    discipline = SelectField('Discipline', validate_choice=False, validators=[DataRequired()])  # render_kw={'disabled': True})
    assay_id = SelectMultipleField('Assays', coerce=int, validators=[DataRequired()], render_kw={'disabled': True})
    dilution = StringField('Dilution', default='1', validators=[DataRequired()])
    directives = TextAreaField("Directives", render_kw={'rows': 3})

    def validate_dilution(self, dilution):
        if dilution.data.isalpha():
            if dilution.data.lower() != 'hv':
                raise ValidationError("Dilution must be number or 'HV'")


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(FlaskForm):
    result_status = StringField('Result Status', validators=[DataRequired()])
    result_status_updated = BooleanField('Status Updated')
    result_status_update_reason = StringField('Update Reason', validators=[Optional()])
    submit = SubmitField('Submit')



class Update(FlaskForm):
    dilution = StringField('Dilution', default='1', validators=[DataRequired()])
    directives = TextAreaField("Directives", render_kw={'rows': 3})
    submit = SubmitField('Submit')


class Cancel(FlaskForm):
    test_id = IntegerField('Test ID', render_kw={'hidden': True}, validators=[Optional()])
    test_status = StringField('Test status', render_kw={'hidden': True}, validators=[Optional()])
    test_comment = SelectField('Reason for test cancellation', validate_choice=False, validators=[DataRequired()],
                               coerce=str)
    submit_cancel = SubmitField('Confirm')


class Reinstate(FlaskForm):
    test_id = IntegerField('Test ID', render_kw={'hidden': True}, validators=[Optional()])
    test_status = StringField('Test status', render_kw={'hidden': True}, validators=[Optional()])
    test_comment = SelectField('Reason for test cancellation', validate_choice=False, validators=[DataRequired()],
                               coerce=str, render_kw={'hidden':True})
    submit_reinstate = SubmitField('Confirm')
