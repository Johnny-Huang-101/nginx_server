from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, SelectField, \
    TextAreaField, SelectMultipleField, DateField
from wtforms.validators import DataRequired, Optional
from flask_wtf.file import FileField

select_int_choices = [
    (0, 'Please select a value'),
    (1, 'Choice 1'),
    (2, 'Choice 2'),
    (3, 'Choice 3'),
    (4, 'Choice 4'),
    (5, 'Choice 5'),
]

select_str_choices = [
    ('', 'Please select a value'),
    ('1', 'String Choice 1'),
    ('2', 'String Choice 2'),
    ('3', 'String Choice 3'),
    ('4', 'String Choice 4'),
    ('5', 'String Choice 5'),
]

select_multiple_choices = [
    ('1', 'Multiple Choice 1'),
    ('2', 'Multiple Choice 2'),
    ('3', 'Multiple Choice 3'),
    ('4', 'Multiple Choice 4'),
    ('5', 'Multiple Choice 5'),
]



class Base(FlaskForm):
    string_field = StringField('String Field', validators=[DataRequired('Message')])
    text_field = TextAreaField('Text Field')
    int_select_field = SelectField('Select Field (Int)', coerce=int, choices=select_int_choices)
    str_select_field = SelectField('Select Field (Str)', coerce=str,  choices=select_str_choices)
    select_multiple_field = SelectMultipleField('Select Multiple Field', choices=select_multiple_choices)
    date_field = DateField('Date Field', validators=[Optional()])
    file_field = FileField('File Field')
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})
class Add(Base):
    submit = SubmitField('Submit')

class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Update')


