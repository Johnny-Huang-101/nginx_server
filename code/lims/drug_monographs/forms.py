from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    formulation_tradename = TextAreaField('Tradename')
    pharm_class = TextAreaField('Pharm Class')
    intended_use = TextAreaField('Intended Use')
    mech_of_action = TextAreaField('Mechanism of Action')
    effects_and_tox = TextAreaField('Effects and Toxicity')
    impairment = TextAreaField('Impairment')
    half_life = TextAreaField('Half Life')
    time_to_peak_conc = TextAreaField('Time to Peak Concentration')
    am_nontox_blood_serum_conc = TextAreaField('AM Non-toxic Blood or Serum Concentrations')
    am_nontox_information = TextAreaField('AM Non-toxic Blood or Serum Concentration Information')
    pm_tox_blood_serum_conc = TextAreaField('PM Toxic/Lethal Blood or Serum Concentrations')
    ampm_tox_lethal_coc_info = TextAreaField('AM and PM Toxic/Lethal Blood or Serum Concentration Information')
    blood_to_serum_ratio = TextAreaField('Blood to Serum Ratio')
    adme = TextAreaField('ADME: Absorption, Distribution, Metabolism, Excretion')
    pk_variability = TextAreaField('PK Variability')
    drug_interaction = TextAreaField('DDI (Drug-Drug Interactions)')
    drug_interaction_ref = TextAreaField('DDI Reference')
    pm_redistribution = TextAreaField('Postmortem Redistribution')
    pm_considerations = TextAreaField('Postmortem Considerations')
    hp_considerations = TextAreaField('Human Performance Considerations')
    references = TextAreaField('References')


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
