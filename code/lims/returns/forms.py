from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, IntegerField, DateField, SelectMultipleField, BooleanField

from wtforms.fields.simple import HiddenField
from wtforms.validators import DataRequired, Optional, ValidationError


#CUSTOM VALIDATOR FOR LEGACY CASES
def validate_case_id(form, field):
    # If no legacy case and no LIMS case selected → raise error
    if not form.legacy_case_number.data and not field.data:
        raise ValidationError("Please select a Case Number or enter a Legacy Case Number.")


class Base(FlaskForm):
    name = HiddenField()
    case_id = SelectMultipleField(
        'Case Number(s)',
        choices=[('', '---')],
        coerce=int,
        validators=[validate_case_id]  
    )
    returning_agency = SelectField('Returning Agency', choices=[('', '---')],
                                    validators=[DataRequired(message='Returning Agency Required')], coerce=int)
    returning_division = SelectField('Returning Division', choices=[('', '---')],
                                      validators=[DataRequired(message='Returning  Division Required')], coerce=int)
    returning_personnel = SelectField('Returning Personnel',choices=[('', '---')], coerce=int)
    return_date = DateField('Return Date', 
                            render_kw={'type': 'date'}, validators=[DataRequired()])
    no_case = BooleanField('No case number')
 
    notes = TextAreaField('Notes', render_kw={'rows': '2'})
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})
    legacy_case_check = BooleanField('Legacy Case')
    legacy_case_number = StringField('Legacy Case Number', validators=[Optional()])
    legacy_case = HiddenField()
    return_items_multi = SelectMultipleField('Returned Items', choices=[('', '---')],)
    return_items = HiddenField()
    status = HiddenField()

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')

class ReturnedSpecimensForm(FlaskForm):
    returned_specimens = SelectMultipleField('Returned Specimens:', choices=[('', '---')], coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit')  

class StoredSpecimensForm(FlaskForm):
    stored_specimens = SelectMultipleField('Specimens to Store:', choices=[('', '---')], coerce=int, validators=[DataRequired()])
    custody_type = SelectField('Custody Type:', choices=[('', '---')], validators=[DataRequired()])
    custody = SelectField('Custody:', choices=[('', '---')], validators=[DataRequired()])
    submit_stored = SubmitField('Submit')  

# NOTE:Legacy fields are free text and are NOT linked to the specimen/cases tables
class LegacySpecimenAdd(FlaskForm):
    legacy_code = StringField('Description (Legacy)')
    legacy_accession_number = StringField('Accession Number (Legacy)')
    legacy_date_created = StringField(' Date Collected/Prepared (Legacy)')
    legacy_created_by = StringField('Received/Prepared By (Legacy)')
    legacy_checked_by = StringField('Checked By (Legacy)')
    legacy_specimens_submit = SubmitField('Submit')