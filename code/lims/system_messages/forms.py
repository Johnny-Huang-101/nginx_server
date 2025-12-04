from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional


class Base(FlaskForm):

    name = SelectField('What type of addition is this?', choices=[(0,'--'), ('LIMS Name','LIMS Name'),
                                                                            ('System Message','System Message')])
    message = StringField('Your text:', validators=[DataRequired(message='Must have a message.')])

class Add(Base):
    submit = SubmitField('Submit')

class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')


