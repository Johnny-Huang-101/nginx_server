# lims/forensight/forms.py
from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    DateField, SelectField, SelectMultipleField,
    IntegerField, SubmitField
)
from wtforms.validators import Optional, NumberRange

# ---------- Static choice lists ----------
CASE_STATUS_CHOICES = [
    ("Open", "Open"),
    ("Closed", "Closed"),
]

DISCIPLINE_CHOICES = [
    ("Toxicology", "Toxicology"),
    ("Biochemistry", "Biochemistry"),
    ("Drug", "Drug"),
    ("External", "External"),
]

RESULT_STATUS_CHOICES = [
    ("Confirmed", "Confirmed"),
    ("Saturated", "Saturated"),
    ("Trace", "Trace"),
    ("Unconfirmed", "Unconfirmed"),
    ("Not tested", "Not tested"),
    ("Withdrawn", "Withdrawn"),
    ("DNR", "DNR"),
    ("Omit", "Omit"),
]

MANNER_CHOICES = [
    ("Suicide", "Suicide"),
    ("Undetermined", "Undetermined"),
    ("Homicide", "Homicide"),
    ("Accident", "Accident"),
    ("Natural", "Natural"),
]
# Back-compat alias if anything still imports the old name
MANNER_OPTIONS = MANNER_CHOICES

AUTOPSY_TYPE_CHOICES = [
    ("ADMINISTRATIVE REVIEW", "ADMINISTRATIVE REVIEW"),
    ("AUTOPSY", "AUTOPSY"),
    ("AUTOPSY AND  CT", "AUTOPSY AND  CT"),
    ("EXTERNAL AND CT", "EXTERNAL AND CT"),
    ("EXTERNAL EXAMINATION", "EXTERNAL EXAMINATION"),
    ("INDIGENT", "INDIGENT"),
    ("PARTIAL AUTOPSY (NAME)", "PARTIAL AUTOPSY (NAME)"),
    ("PARTIAL AUTOPSY AND CT", "PARTIAL AUTOPSY AND CT"),
    ("PENDING EXAMINATION", "PENDING EXAMINATION"),
]


class ForenSightFilterForm(FlaskForm):
    # Dates
    from_date = DateField("From Date", validators=[Optional()], default=date(2025, 1, 1))
    to_date   = DateField("To Date",   validators=[Optional()], default=date.today)

    # Top section (rows of 3 in template)
    case_status = SelectMultipleField("Case Status", coerce=str, choices=CASE_STATUS_CHOICES)  # Closed default in view
    genders     = SelectMultipleField("Gender",     coerce=int)   # from Genders.id, label = Genders.name
    races       = SelectMultipleField("Race",       coerce=int)   # from Races.id,   label = Races.name

    start_age = IntegerField("Start Age (Years)",
                             validators=[Optional(), NumberRange(min=0, max=150)],
                             default=0)
    end_age   = IntegerField("End Age (Years)",
                             validators=[Optional(), NumberRange(min=0, max=150)],
                             default=110)

    case_types  = SelectMultipleField("Case Types",  coerce=int)  # from CaseTypes.id, label = CaseTypes.code
    disciplines = SelectMultipleField("Discipline",  choices=DISCIPLINE_CHOICES, coerce=str)

    specimen_types = SelectMultipleField("Specimen Type", coerce=int)  # from SpecimenTypes.id, label = .name
    drug_class     = SelectField("Drug Class", coerce=str, choices=[("", "— Select —")])  # single-select, no default
    components     = SelectMultipleField("Component(s)", coerce=int)    # from Components.id, label = .name

    component_logic = SelectField(
        "Component Match",
        coerce=str,
        choices=[("AND", "AND"), ("OR", "OR")],
        default="OR"
    )


    reported_results = SelectField("Reported Results", coerce=str,
                                   choices=[("", "— Select —"), ("Yes", "Yes"), ("No", "No")])

    result_status = SelectMultipleField("Result Status", choices=RESULT_STATUS_CHOICES, coerce=str)

    # PM-only section
    autopsy_type    = SelectMultipleField("Autopsy Type", choices=AUTOPSY_TYPE_CHOICES, coerce=str)
    death_types     = SelectMultipleField("Death Type", coerce=int)  # from DeathTypes.id, label = .name
    manner_of_death = SelectMultipleField("Manner of Death", choices=MANNER_CHOICES, coerce=str)

    fixed_address = SelectField("Fixed Address", coerce=str,
                                choices=[("Yes", "Yes"), ("No", "No")])

    fixed_address_location = SelectMultipleField("Fixed Address Location", coerce=str)  # Zipcodes.zipcode
    death_location         = SelectMultipleField("Death Address",         coerce=str)  # Zipcodes.zipcode

    # Actions
    submit = SubmitField("Apply")
    clear  = SubmitField("Reset")
