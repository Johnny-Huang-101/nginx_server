from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    record_id = SelectField('Record(s)', coerce=int, validators=[DataRequired()])
    disseminated_to = SelectField('Disseminated To', validators=[DataRequired()])
    disseminated_by = SelectField('Disseminated By', validators=[DataRequired()])
    date = DateField('Dissemination Date', validators=[DataRequired()])


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')

