from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    assay_id = SelectField('Assay', coerce=int, validators=[DataRequired()])
    constituent_id = SelectMultipleField('Constituent', coerce=str, validators=[DataRequired()])


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
