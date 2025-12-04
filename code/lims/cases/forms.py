from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateField, SelectMultipleField, BooleanField, IntegerField, DateTimeField, HiddenField, TimeField
from wtforms.validators import DataRequired, Optional, ValidationError, StopValidation
from lims.models import discipline_choices, RetentionPolicies
from datetime import datetime, timedelta, time
from wtforms import SelectMultipleField, widgets
# class NoCSRFForm(FlaskForm):
#     # To force form validation if not rendering hidden_tag in html
#     class Meta:
#         csrf = False


class Base(FlaskForm):
    birth_sex_choices = [
        ('', '---'),
        ('Female', 'Female'),
        ('Male', 'Male')
    ]

    yes_no = [
        ('Yes', 'Yes'),
        ('No', 'No')
    ]

    priority_choices = [
        ('Normal', 'Normal'),
        ('High', 'High')
    ]

    sensitivity_choices = [
        ('Normal', 'Normal'),
        ('Restricted', 'Restricted')
    ]

    case_status_choices = [
        ('Submitted', 'Submitted'),
        ('Testing', 'Testing'),
        ('CR1', 'CR1'),
        ('CR2', 'CR2'),
        ('DR', 'DR'),
        ('Closed', 'Closed')
    ]

    home_status_choices = [
        ('UNK', 'Unknown'),
        ('NFA', 'No Fixed Address')
    ]

    testing_choices = discipline_choices[1:]

    case_type = SelectField('Case Type', coerce=int, validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()],
                            render_kw={"oninput": "this.value = this.value.toUpperCase()"})
    middle_name = StringField('Middle Name/Initial')
    first_name = StringField('First Name', validators=[DataRequired()])
    gender_id = SelectField('Gender', coerce=int, validators=[DataRequired()])
    birth_sex = SelectField('Birth Sex', choices=birth_sex_choices)
    race_id = SelectField('Race', coerce=int)
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    age = StringField('Age')
    date_of_incident = DateField('Date of Incident/Death', validators=[Optional()])
    time_of_incident = StringField('Time of Incident/Death')
    submitting_agency = SelectField('Submitter (Agency)', coerce=int, validators=[DataRequired()])
    submitting_division = SelectField('Client (Division)', coerce=int, validate_choice=False, validators=[DataRequired()])
    submitter_case_reference_number = StringField('Submitter Reference Number')
    alternate_case_reference_number_1 = StringField('Alternate Case Reference Number 1')
    alternate_case_reference_number_2 = StringField('Alternate Case Reference Number 2')
    testing_requested = SelectMultipleField('Testing Requested', coerce=str, choices=testing_choices)
    no_testing_requested = BooleanField('No Testing Requested')
    submitter_requests = TextAreaField('Submitter Requests', render_kw={'rows': '2', 'style': 'padding: 0px'})
    priority = SelectField('Priority', choices=priority_choices, render_kw={'disabled': True})
    sensitivity = SelectField('Sensitivity', choices=sensitivity_choices, render_kw={'disabled': True})
    #retention_policy = SelectField('Retention Policy', coerce=int)
    #discard_date = DateField('Discard Date', render_kw={'readonly': True})
    #discard_eligible = SelectField('Eligible For Discard', choices=yes_no, default='No', render_kw={'readonly': True})
    #case_status = SelectField('Case Status', choices=case_status_choices)
    notes = TextAreaField('Notes', render_kw={'rows': '2'})
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    def validate_time_of_incident(self, time_of_incident):
        if time_of_incident.data:
            if len(time_of_incident.data) != 4:
                raise ValidationError("Time of incident must be in the format of 'HHMM'.")

            try:
                datetime.strptime(time_of_incident.data, '%H%M')
            except:
                raise ValidationError(f"{time_of_incident.data} in not a valid time.")

    def validate_testing_requested(self, testing_requested):
        if not self.no_testing_requested.data:
            if not testing_requested.data:
                raise ValidationError('Please select the testing requested or check "No testing requested".')

    # def validate_case_number(self, case_number):
    #     value = dict(self.case_type.choices).get(self.case_type.data)
    #     if (value == 'PM - Postmortem') and (case_number.data == ""):
    #         raise ValidationError('Case number cannot be blank')

    # def validate_date_of_birth(self, date_of_birth):
    #     today = datetime.date(datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')))
    #     if date_of_birth.data is not None:
    #         if date_of_birth.data > today:
    #             raise ValidationError('Date of Birth cannot be in the future.')
    #         if date_of_birth.data > self.date_of_incident.data:
    #             raise ValidationError('Date of Birth cannot be after the incident/death date.')

    # def validate_date_of_incident(self, date_of_incident):
    #     today = datetime.date(datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')))
    #     if date_of_incident.data > today:
    #         raise ValidationError('Date of Incident/Death cannot be in the future.')
    #     if date_of_incident.data < self.date_of_birth.data:
    #         raise ValidationError('Date of Incident/Death cannot be before date of birth.')
    #

    #
    #     if self.date_of_incident.data == datetime.today().date():
    #         if datetime.strptime(time_of_incident.data, '%H%M').time() > datetime.today().time():
    #             raise ValidationError("Submission time is in the future based on submission date")


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Submit')







    

class DuplicateCase(FlaskForm):
    case_id = SelectField('Case', coerce=int)
    submit = SubmitField('Submit')

class ImportFA(FlaskForm):
    file = FileField('FA File', validators=[DataRequired()], render_kw={'accept': ".csv"})
    submit = SubmitField('Submit')


class FAExportControlForm(FlaskForm):
    run_now = BooleanField("Force Export")
    delay_until = DateTimeField("Delay Until", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    start_date = DateField("Start Date", validators=[Optional()])
    end_date = DateField("End Date", validators=[Optional()])
    submit = SubmitField("Update Export Settings")

    def validate_date_range(self, field):
        """Custom validator to ensure startDate and endDate are ≤ 183 days apart."""
        if self.start_date.data and self.end_date.data:
            delta = self.end_date.data - self.start_date.data
            if delta.days > 183:
                raise ValidationError("Date range cannot exceed 6 months (i.e., 183 days).")

class Attach(FlaskForm):
    file = FileField('Select File(s) to attach', render_kw={'multiple': 'true'})
    submit = SubmitField('Submit')


class LitPacket(FlaskForm):
    case_id = StringField('Case ID', render_kw={'readonly': True})
    agency_id = SelectField('Requested Agency', coerce=int, validators=[Optional()],
                            choices=[(0, 'Please select an Agency')], validate_choice=False)
    division_id = SelectField('Requested Division', coerce=int, validators=[Optional()],
                              choices=[(0, 'Please Select Division')], validate_choice=False)
    personnel_id = SelectField('Requested Personnel', coerce=int, validators=[Optional()],
                               choices=[(0, 'Please select Personnel')], validate_choice=False)
    del_agency_id = SelectField('Delivered Agency', coerce=int, validators=[Optional()],
                                choices=[(0, 'Please select an Agency')], validate_choice=False)
    del_division_id = SelectField('Delivered Division', coerce=int, validators=[Optional()],
                                  choices=[(0, 'Please Select Division')], validate_choice=False)
    del_personnel_id = SelectField('Delivered Personnel', coerce=int, validators=[Optional()],
                                   choices=[(0, 'Please select Personnel')], validate_choice=False)
    packet_name = StringField('Packet Name', validators=[Optional()], render_kw={"hidden": "True"})
    redact = BooleanField('No Redaction', validators=[Optional()])
    remove_pages = BooleanField('No Page Removal', validators=[Optional()])
    requested_date = DateField('Requested Date', render_kw={'type': 'date'}, validators=[Optional()])
    due_date = DateField('Due Date', render_kw={'type': 'date'}, validators=[Optional()])
    delivery_date = DateField('Delivery Date', render_kw={'type': 'date'}, validators=[Optional()])
    delivered_to = StringField('Delivered To', validators=[Optional()])
    n_pages = IntegerField('Number of Pages', validators=[Optional()])
    postage_and_delivery = StringField('Postage and Delivery', validators=[Optional()])
    additional_costs = StringField('Additional Costs', validators=[Optional()])
    total_costs = StringField('Total Costs', validators=[Optional()])
    paid_date = DateField('Paid Date', render_kw={'type': 'date'}, validators=[Optional()])
    packet_status = StringField('Packet Status', validators=[Optional()], render_kw={"hidden": "True"})
    submit = SubmitField('Submit')


class LitPacketZip(FlaskForm):
    case_id = StringField('Case ID', render_kw={'readonly': True})
    template_id = SelectField('Template Name', coerce=int, validators=[DataRequired()])
    packet_name = StringField('Packet Name', validators=[Optional()], render_kw={"hidden": "True"})
    redact = BooleanField('No Redaction', validators=[Optional()])
    remove_pages = BooleanField('No Page Removal', validators=[Optional()])
    schedule_generation = BooleanField('Generate Right Now?', validators=[Optional()])
    # scheduled_time = DateTimeField('Scheduled Time', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    submit = SubmitField('Submit')

    def default_7_30_pm():
        now = datetime.now()
        today_7_30_pm = datetime.combine(now.date(), time(19, 30))
        if now >= today_7_30_pm:
            # if past 7:30 pm, schedule for tomorrow 7:30 pm
            return today_7_30_pm + timedelta(days=1)
        return today_7_30_pm

    scheduled_time = DateTimeField(
        'Scheduled Time',
        format='%Y-%m-%dT%H:%M',
        default=default_7_30_pm,
        validators=[Optional()],
        render_kw={'disabled': True}
    )

    # def validate_scheduled_time(form, field):

    #     if not form.schedule_generation.data and form.scheduled_time.data:
    #         raise ValidationError(r'Check "schedule later" if you want to schedule for later!')
    #     if form.schedule_generation.data:
    #         if not field.data:
    #             raise ValidationError('Please provide a scheduled time.')
    #         if field.data <= datetime.now():
    #             raise ValidationError('Scheduled time must be in the future.')

class UpdateRetentionPolicy(FlaskForm):
    retention_policy = SelectField("Retention Policy", coerce=int, validators=[DataRequired()])
    discard_date = DateField("Discard Date (if Custom)", validators=[Optional()])
    type_id = SelectField('Attachment Type', coerce=int, validate_choice=False)
    description = TextAreaField('Description')
    files = FileField('Attachments', render_kw={'multiple': True})  # , validators=[DataRequired()])
    mode = StringField('Hidden')
    submit = SubmitField('Submit')

    def validate_discard_date(self, discard_date):
        retention_policy = self.retention_policy.data
        retention_policy = RetentionPolicies.query.get_or_404(retention_policy)
        if not discard_date.data:
            if retention_policy.date_selection == 'Manual':
                raise ValidationError('A date must be selected for this retention policy')


class AutopsyScan(FlaskForm):
    # Form for autopsy view
    initial_label = StringField('Scan Histology Label', validators=[Optional()])
    cases_selected = SelectField('Cases Selected ID', coerce=int, validators=[Optional()])
    specimen_discipline = SelectField('Discipline', validators=[Optional()])
    specimen_type = SelectMultipleField(
        'Specimen Type',
        coerce=int,
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
        validators=[Optional()]
    )
    submit_scan = SubmitField('Submit')
    submit_toxicology_print = SubmitField('Print Autopsy')
    submit_physical_print = SubmitField('Print Admin Review/External')
    submit_physical_sa_print = SubmitField('Print Physical (SA)')
    submit_bundle_print = SubmitField('Print Homicide')
    submit_histology_print = SubmitField('Print Histology (Tissue)')
    submit_histology_sa_print = SubmitField('Print Histology (Smear)')
    submit_drug_print = SubmitField('Print Drug')
    submit_other_print = SubmitField('Submit')
    submit_generic_print = SubmitField('Print Generic Label')
    submit_histo_scan = SubmitField('Submit')
    submit_five_generic = SubmitField('Print Generic (x5)')

class ExportFiltered(FlaskForm):
    created_start = DateField('Start', validators=[DataRequired()])
    created_end = DateField('End', validators=[DataRequired()])
    mod = SelectMultipleField('MOD, optional', coerce=str, choices=[
        ('Natural', 'Natural'),
        ('Accident', 'Accident'),
        ('Suicide', 'Suicide'),
        ('Homicide', 'Homicide'),
        ('Undetermined', 'Undetermined')
    ], validators=[Optional()])
    cod = StringField('COD keyword', validators=[Optional()])
    # acc_od = SelectField('Accidental OD', choices=[
    #     ('', 'Any'),
    #     ('Yes', 'Yes'),
    #     ('No', 'No')
    # ], validators=[Optional()])
    # format = SelectField('File Format', choices=[('csv', 'CSV'), ('xlsx', 'XLSX')])
    content_preset = SelectField("Contents", choices=[
        ('Default', 'Default'),
        ('Additional', 'Include Additional Fields (SSN, Home Address, Home Zip)')
    ], validators=[DataRequired()])
    submit = SubmitField('Submit')

class UpdateStartDate (FlaskForm):
    column_name = StringField()  # type: ignore # to know which field to update
    toxicology_alternate_start_date = DateField('Alternate Tox Date', format='%m/%d/%Y', validators=[Optional()])
    biochemistry_alternate_start_date  = DateField('Alternate Biochem Date', format='%m/%d/%Y', validators=[Optional()])
    histology_alternate_start_date = DateField('Alternate Histo Date', format='%m/%d/%Y', validators=[Optional()])
    external_alternate_start_date = DateField('Alternate External Date', format='%m/%d/%Y', validators=[Optional()])
    physical_alternate_start_date = DateField('Alternate Physical Date', format='%m/%d/%Y', validators=[Optional()])
    drug_alternate_start_date = DateField('Alternate Drug Date', format='%m/%d/%Y', validators=[Optional()])\
    
    toxicology_alternate_start_time = TimeField('Alternate Tox Date', format='%H:%M', validators=[Optional()])
    biochemistry_alternate_start_time  = TimeField('Alternate Biochem Date', format='%H:%M', validators=[Optional()])
    histology_alternate_start_time = TimeField('Alternate Histo Date', format='%H:%M', validators=[Optional()])
    external_alternate_start_time = TimeField('Alternate External Date', format='%H:%M', validators=[Optional()])
    physical_alternate_start_time = TimeField('Alternate Physical Date', format='%H:%M', validators=[Optional()])
    drug_alternate_start_time = TimeField('Alternate Drug Date', format='%H:%M', validators=[Optional()])\
    
    alternate_date_submit = SubmitField('Submit')


class UpdateSensitivity(FlaskForm):
    sensitivity = SelectField('Sensitivity', choices=[
        ('Normal', 'Normal'),
        ('Restricted', 'Restricted')
    ])
    sensitivity_submit = SubmitField('Submit')

class UpdatePriority(FlaskForm):
    priority = SelectField('Priority', choices=[
        ('Normal', 'Normal'),
        ('High', 'High')
    ])
    priority_submit = SubmitField('Submit')

class Communications(FlaskForm):
    communications = TextAreaField('Communications', render_kw={
            'style': "background-color: rgb(221, 204, 238); width:60%; height:120px;"
        })
    submit = SubmitField('Submit')