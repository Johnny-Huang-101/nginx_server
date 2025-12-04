from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, SelectField, SubmitField, SelectMultipleField, TextAreaField
from wtforms.validators import ValidationError, DataRequired
from lims.models import Users

# The result statuses for the filter
result_status_choices = [
    ('Confirmed', 'Confirmed'),
    ('Saturated', 'Saturated'),
    ('Trace', 'Trace'),
    ('Unconfirmed', 'Unconfirmed'),
    ('Not Tested', 'Not Tested')
]

class Base(FlaskForm):
    report_type = SelectField('Report Type', choices=[('Auto-generated', 'Auto-generated'),
                                                      ('Manual Upload', 'Manual Upload')])
    case_id = SelectField('Case', coerce=int, validators=[DataRequired()])
    discipline = SelectField('Discipline', validators=[DataRequired()], validate_choice=False)
    result_status_filter = SelectMultipleField("Show results with result status", choices=result_status_choices,
                                               default=['Confirmed', 'Saturated', 'Not Tested'])
    report_file = FileField('Report File', render_kw={'accept': 'docx'})
    report_template_id = SelectField('Report Template', coerce=int, validate_choice=False)
    result_id_order = StringField('Result Order')
    result_id = SelectMultipleField('Results', coerce=int)
    primary_result_id = SelectMultipleField('Official Results', coerce=int)
    supplementary_result_id = SelectMultipleField('Supplementary Result', coerce=int)
    observed_result_id = SelectMultipleField('Observed Results', coerce=int)
    qualitative_result_id = SelectMultipleField('Qualitative Results', coerce=int)
    approximate_result_id = SelectMultipleField('Approximate Result', coerce=int)
    communications = TextAreaField('Communications', render_kw={
            'style': "background-color: rgb(221, 204, 238); width:60%; height:120px;"
        })

    def validate_report_template_id(self, report_template_id):
        if self.report_type.data == 'Auto-generated':
            if not report_template_id.data:
                raise ValidationError('A template must be selected')

    def validate_report_file(self, report_file):
        if self.report_type.data == 'Manual Upload':
            if not report_file.data:
                raise ValidationError('A file must be selected')

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


class Communications(FlaskForm):
    communications = TextAreaField('Communications', render_kw={
            'style': "background-color: rgb(221, 204, 238); width:60%; height:120px;"
        })
    submit = SubmitField('Submit')
class AssignDRForm(FlaskForm):
    assigned_dr = SelectField('Assigned DR', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit')

class AssignCRForm(FlaskForm):
    assigned_cr = SelectField('Assigned CR', coerce=int, validators=[DataRequired()])
    submit_cr = SubmitField('Submit')

      
