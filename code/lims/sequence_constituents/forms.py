from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    sequence_name = StringField('Name in Sequence (Must be exact spelling)', validators=[DataRequired()])
    solution_type = SelectField('Solution Type', coerce=int, validate_choice=False)
    constituent_type = SelectField('Constituent Type', coerce=int, validate_choice=False,
                                   choices=[(0, 'Please select a standard/solution type')])
    extracted = BooleanField('Constituent gets extracted', default=False)



class Add(Base):
    submit = SubmitField('Submit')

    # def validate_name(self, name):
    #     if DrugClasses.query.filter_by(name=name.data).first():
    #             raise ValidationError('Drug class already exists!')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
