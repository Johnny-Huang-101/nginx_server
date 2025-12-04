from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectField, TextAreaField, DateField, FloatField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    case_id = SelectField('Case', coerce=int, validators=[DataRequired()])
    # result_component_id = SelectField('Reported Component', coerce=int)
    result_id = SelectField('Result: Acc# | Component | Result | Conc | BatchID)', coerce=int, validate_choice=False, validators=[DataRequired()])

    # concentration, component, unit when units are different
    pt_component_id = SelectField('Component, if different', coerce=int, validate_choice=False)  # if not selected, value is ''
    pt_unit_id = SelectField('Unit, if different', coerce=int, validate_choice=False)

    pt_reporting_limit = FloatField('PT Provider Reporting Limit', validators=[Optional()])
    pt_participants = TextAreaField('(# of N) or (%) of participants', render_kw={'rows': '1'})

    eval_date = DateField('Evaluation Date Issued', render_kw={'type': 'date'}, validators=[DataRequired()])
    eval_informal = SelectField('Informal?', choices=[("No", 'No'), ("Yes", "Yes")])  # changed from Boolean
    eval_FLD_conclusion = SelectField('FLD Conclusion', validate_choice=False)

    target = FloatField('Target', validators=[Optional()])
    median = FloatField('Median, if provided', validators=[Optional()])

    mean_all = FloatField('Mean - All Methods', validators=[Optional()])
    sd_all = FloatField('Standard Deviation - All Methods', validators=[Optional()])
    mean_sub = FloatField('Mean - Sub-Group', validators=[Optional()])
    sd_sub = FloatField('Standard Deviation - Sub-Group', validators=[Optional()])

    eval_A_ref = SelectField('Reference A', validators=[Optional()], id='eval_A_ref')
    eval_B_ref = SelectField('Reference B', validators=[Optional()])

    eval_manual_min = FloatField('Manual Min', validators=[Optional()], id='eval_manual_min')
    eval_manual_max = FloatField('Manual Max', validators=[Optional()], id='eval_manual_max')

    notes = TextAreaField('Evaluation Comments', render_kw={'rows': '2'})
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
