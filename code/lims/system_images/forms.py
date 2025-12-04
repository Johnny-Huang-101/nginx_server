from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional

from flask_wtf.file import FileField, FileAllowed, FileRequired


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    image_file = FileField('Select File', validators=[FileRequired(),
                                                      FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])

class Add(Base):
    submit = SubmitField('Submit')

class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')


