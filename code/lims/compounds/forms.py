from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, TextAreaField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):

    name = StringField('SFOCME Name', validators=[DataRequired()])
    synonyms = StringField("Synonym(s)")
    code = StringField('Code', validators=[DataRequired()])
    inventory_add_date = DateField('Inventory Add Date', render_kw={'type': 'date'}, validators=[Optional()])
    drug_class_id = SelectField("Drug Class", coerce=int, validators=[DataRequired()])
    drug_monograph_id = SelectField('Drug Monograph', coerce=int)
    iupac = StringField('IUPAC Name')
    cas_no = StringField('CAS No.')
    formula = StringField('Molecular Formula')
    mass = StringField('Mass')
    inchikey = StringField('InChIKey')
    smiles = StringField('SMILES')

    notes = TextAreaField('Notes')
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
