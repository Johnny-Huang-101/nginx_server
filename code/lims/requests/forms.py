from flask_wtf import FlaskForm
from wtforms import DateTimeField, StringField, SubmitField, TextAreaField, SelectField, IntegerField, DateField, SelectMultipleField, BooleanField

from wtforms.fields.simple import HiddenField
from wtforms.validators import DataRequired, Optional, ValidationError


# need to create custom validator - dont use datarequired

def validate_case_id(form, field):
    # If 'no_case' is unchecked and 'case_id' is empty, raise a validation error
    if not form.no_case.data and not field.data:
        raise ValidationError("Case Number is required.")


class Base(FlaskForm):
    name = HiddenField()
    case_id = SelectMultipleField('Case Number(s)', choices=[])
    request_type_id = SelectField('Request Type', validators=[DataRequired(message='Request Type Required')], coerce=int)
    requesting_agency = SelectField('Requesting Agency',
                                    validators=[DataRequired(message='Requesting Agency Required')], coerce=int)
    requesting_division = SelectField('Requesting Division',
                                      validators=[DataRequired(message='Requesting Division Required')], coerce=int)
    requesting_personnel = SelectField('Requesting Personnel',
                                       validators=[DataRequired(message='Requesting Personnel Required')], coerce=int)
    due_date = DateField('Due Date', render_kw={'type': 'date'}, validators=[DataRequired()])
    specimens = SelectMultipleField('Specimens')
    intake_user = HiddenField()
    intake_date = HiddenField()
    status = HiddenField() #In Progress; Finalized: finalization reason may vary(i.e., withdrawn, no evidence found)
    no_case = BooleanField('No case number')
    next_of_kin_confirmation = HiddenField()
    payment_confirmation = HiddenField()
    email_confirmation = HiddenField()
    me_confirmation = HiddenField()
    destination_agency = SelectField('Destination Agency', validators=[DataRequired(message='Destination Agency Required')], coerce=int)
    destination_division = SelectField('Destination Division', validators=[DataRequired(message='Destination Division Required')], coerce=int)
    # destination_personnel = SelectField('Destination Personnel',
    #                                     coerce=int)
    notes = TextAreaField('Notes', render_kw={'rows': '2'})
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})
    prepare_status = HiddenField()
    check_status = HiddenField()
    release_status = HiddenField()#None:---, N/A: not applicable, No Available Evidence: no evidence was found, Withdrawn: requesting party withdraws request
    legacy_case_check = BooleanField('Legacy Case')
    legacy_case_number = StringField('Legacy Case Number', validators=[Optional()])
    legacy_case = HiddenField() 
    requested_items_multi = SelectMultipleField('Requested Items', choices=[])
    requested_items = HiddenField()
    requested_items_other = StringField('Other')
   


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


class SpecimenAdd(FlaskForm):
    specimens = SelectMultipleField("Specimens", choices=[], validators=[DataRequired()])
    specimens_submit = SubmitField('Submit')


class SpecimenReview(FlaskForm):
    approved_specimens = SelectMultipleField("Specimens", choices=[], validators=[DataRequired()])
    denied_specimens = HiddenField()
    approved_submit = SubmitField('Approve')


class CollectSpecimen(FlaskForm):
    collected_specimen = SelectField("Specimens", choices=[], validators=[DataRequired()])
    collected_submit = SubmitField('Submit')


class AddNote(FlaskForm):
    notes = StringField("Add Note", validators=[DataRequired()])
    note_submit = SubmitField('Submit')


class PrepareSpecimen(FlaskForm):
    prepared_specimen = SelectMultipleField('Specimens', choices=[], validators=[DataRequired()])
    prepared_submit = SubmitField('Submit')


class ReturnPreparedSpecimen(FlaskForm):
    custody_type = SelectField('Custody Type', choices=[], validators=[DataRequired()])
    custody = SelectField('Custody', choices=[], validators=[DataRequired()])
    return_prepared_submit = SubmitField('Submit')


class CheckSpecimen(FlaskForm):
    checked_specimen = SelectMultipleField('Specimens', choices=[], validators=[DataRequired()])
    checked_specimen_submit = SubmitField('Submit')


class ReturnCheckedSpecimen(FlaskForm):
    custody_type_checked = SelectField('Custody Type', choices=[], validators=[DataRequired()])
    custody_checked = SelectField('Custody', choices=[], validators=[DataRequired()])
    return_checked_submit = SubmitField('Submit')


class ReleaseSpecimen(FlaskForm):
    released_specimen = SelectMultipleField('Specimens', choices=[], validators=[DataRequired()])
    released_specimen_submit = SubmitField('Submit')


class ReturnReleaseSpecimen(FlaskForm):
    receiving_agency = SelectField('Receiving Agency',
                                   validators=[DataRequired(message='Receiving Agency Required')], coerce=int)
    receiving_division = SelectField('Receiving Division',
                                     validators=[DataRequired(message='Receiving Division Required')], coerce=int)
    receiving_personnel = SelectField('Receiving Personnel',
                                      validators=[DataRequired(message='Receiving Personnel Required')], coerce=int)
    in_person = BooleanField('Received by Personnel')
    drop_off_type = SelectField('Custody Type', choices=[], validators=[DataRequired()])
    drop_off_location = SelectField('Custody', choices=[], validators=[DataRequired()])
    return_released_submit = SubmitField('Submit')

class NoEvidenceFound(FlaskForm):
    evidence_confirm = SubmitField('Confirm')

# Note:Legacy fields are free text and are NOT linked to the specimen/cases tables
class LegacySpecimenAdd(FlaskForm):
    legacy_code = StringField('Description (Legacy)')
    legacy_accession_number = StringField('Accession Number (Legacy)')
    legacy_date_created = StringField('Date Collected/Prepared (Legacy)')
    legacy_created_by = StringField('Received/Prepared By (Legacy)')
    legacy_checked_by = StringField('Checked By (Legacy)')
    legacy_specimens_submit = SubmitField('Submit')

class AddCommunication(FlaskForm):
    communications = TextAreaField("Add Communication", validators=[DataRequired()])
    communication_submit = SubmitField('Submit')

class WithdrawRequest(FlaskForm):
    withdraw_request_submit = SubmitField('Confirm')

class CancelRequest(FlaskForm):
    cancel_request_submit = SubmitField('Confirm')

class UpdateReceivedDate(FlaskForm):
    received_date = DateTimeField('Release Date', format='%Y-%m-%dT%H:%M', render_kw={'type': 'datetime-local'})
    update_received_date_submit = SubmitField('Update')