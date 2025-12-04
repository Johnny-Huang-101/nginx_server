from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, IntegerField, TextAreaField, SelectMultipleField
from wtforms.validators import DataRequired, ValidationError

choices = [
    ('Automatic', 'Automatic'),
    ('Manual', 'Manual')
]


class Base(FlaskForm):

    name = StringField('Name', validators=[DataRequired(message="Case type must have a name.")])
    code = StringField('Code')
    accession_level = IntegerField('Accession Level')
    batch_level = IntegerField('Batch Level')
    case_number_type = SelectField('Case Number Type', choices=choices)
    case_number_start = IntegerField('Case Number Start', default=1, render_kw={'disabled': True})
    retention_policy = SelectField('Default Retention Policy', coerce=int)
    toxicology_report_template_id = SelectField('Default Toxicology Report Template', coerce=int)
    biochemistry_report_template_id = SelectField('Default Biochemistry Report Template', coerce=int)
    histology_report_template_id = SelectField('Default Histology Report Template', coerce=int)
    external_report_template_id = SelectField('Default External Report Template', coerce=int)
    litigation_packet_template_id = SelectField('Default Lit Packet Template', coerce=int)
    notes = TextAreaField('Notes')
    default_assays = SelectMultipleField('Default Assays')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    def validate_case_number_start(self, case_number_start):
        if self.case_number_type.data == 'Automatic':
            if not case_number_start.data:
                raise ValidationError('This field is required')
class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
