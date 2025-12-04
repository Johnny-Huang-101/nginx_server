from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, SelectField, TextAreaField, SubmitField, BooleanField, IntegerField, \
    SelectMultipleField, RadioField, HiddenField
from wtforms.validators import DataRequired, ValidationError, Optional


class Base(FlaskForm):
    statuses = [
        ('Confirmed', 'Confirmed'),
        ('Not Tested', 'Not Tested'),
        ('Unconfirmed', 'Unconfirmed'),
        ('Saturated', 'Saturated'),
        ('Trace', 'Trace'),
    ]

    result_types = [
        ('Quantitated', 'Quantitated'),
        ('Detected', 'Detected'),
        ('None Detected', 'None Detected'),
        ('Approximated', 'Approximated'),
    ]

    qual_reasons = [
        ('', '---'),
        ('Assay Qual', 'Assay Qual'),
        ('Batch Qual', 'Batch Qual'),
        ('PA Qual', 'PA Qual'),
    ]

    case_id = SelectField('Case', coerce=int, validators=[DataRequired()])
    test_id = SelectField('Test', coerce=int, validators=[DataRequired()], validate_choice=False,
                          render_kw={'hidden': True})
    result_presets = RadioField('Result Presets',
                           choices=[
                               ('none', 'Manual Entry'),  # default
                               ('none_detected', 'None Detected'),
                               ('not_tested', 'Not Tested for ALL Components'),
                               ('not_reported', 'Not Tested for Selected Component'),
                               ('pp', 'Presump Pos'),
                               ('pos', 'Positive'),
                               ('det', 'Detected')
                           ],
                           default='none'
                           )
    no_unit = BooleanField('No Unit')
    component_id = SelectField('Component', coerce=int, validators=[DataRequired()])
    unit_id = SelectField('Units', coerce=int, validators=[Optional()])
    result_status = SelectField('Result Status', choices=statuses, validators=[DataRequired()])
    result = StringField('Result', validators=[Optional()])
    result_type = SelectField('Type', choices=result_types, validate_choice=False, validators=[DataRequired()])
    supplementary_result = StringField('Supplementary Result')
    concentration = StringField('Concentration', render_kw={'disabled': True})
    measurement_uncertainty = StringField('Measurement Uncertainty', render_kw={'disabled': True})
    reported_result = StringField('Reported Result')
    qualitative = SelectField("Qualitative?", choices=[('', '---'), ('Yes', 'Yes')])
    qualitative_reason = SelectField('Qualitative Reason', choices=qual_reasons)
    component_name = StringField('Component Name', validators=[Optional()])  # new??
    # report_reason = StringField('Report Reason')
    notes = TextAreaField('Notes')

    def validate_result(self, result):
        if (self.result_presets.data == 'none') and not self.result.data:
            if not self.result.data:
                raise ValidationError('No result entered')

    def validate_unit_id(self, unit_id):
        if (self.result_presets.data == 'none') and not self.unit_id.data:
            if not self.unit_id.data and self.no_unit.data is False:
                raise ValidationError('No unit selected')


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(FlaskForm):
    result_status = StringField()
    result_status_update_reason = StringField('Status Update Reason', validators=[Optional()])
    result_status_updated = HiddenField()
    submit = SubmitField('Approve')


class Update(Base):
    submit = SubmitField('Update')


class Import(FlaskForm):
    batch_id = SelectField('Batch', coerce=int, validators=[DataRequired()], render_kw={'class': 'form-control'})
    file = FileField('Select File', render_kw={'accept': '.csv'}, validators=[DataRequired()])
    submit = SubmitField('Submit')


class AlcoholVerbal(FlaskForm):
    batch_id = SelectMultipleField('Batch', coerce=int, validators=[DataRequired()])
    alcohol_verbal_submit = SubmitField('Submit')


class UpdateStatus(FlaskForm):
    result_status = SelectField('Result Status', coerce=str)
    result_type = SelectField('Result Type', coerce=str, validators=[Optional()])
    result_status_update_reason = StringField('Result Status Update Reason')
    result_status_updated = HiddenField()
    result_type_update_reason = StringField('Result Type Update Reason')
    result_type_updated = HiddenField()
    status_dont_change = BooleanField("Do not Change", default=True)
    type_dont_change = BooleanField("Do not Change", default=True)
    status_submit = SubmitField('Submit')
