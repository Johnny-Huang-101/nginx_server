from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    zipcode = StringField('Zipcode', validators=[DataRequired()])
    neighborhood = StringField('Neighborhood', validators=[DataRequired()])

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
