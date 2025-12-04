### NOT USED ###

from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired


class Base(FlaskForm):

    assay_id = SelectField('Assay', validators=[DataRequired('Assay must be selected')], coerce=int)
    constituent_name = SelectField('Select standard/solution name',
                                   validators=[DataRequired('Must select a standard/solution name')], coerce=int)
    constituent_lot = SelectField('Select standard/solution',
                                  validators=[DataRequired('Must select standard/solution')], coerce=int)
    constituent_status = BooleanField('In Use')

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
