from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, ValidationError

choices = [
    (0, 'Please select type'),
    ('Section', 'Section'),
    ('Field', 'Field'),
    ('issue', 'Issue')
]


class Base(FlaskForm):

    type = SelectField('Type', choices=choices, validators=[DataRequired()])
    name = StringField('Name')
    code = StringField('Code')
    
    # The backend db parent_section id is NOT one-to-one with the labeled section in INF-0043 Evidence Receipt Comments. 
    # The front-end displayed prefixes (i.e. Code of the Parent Section) in the Select Field correspond one-to-one to those in INF-0043.
    parent_section = SelectField("Parent section", coerce=int, render_kw={'disabled': True})
    

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    def validate_parent_section(self, parent_section):
        """
        If the user selects the type as 'Field' and there is no selection
        for parent_selection, raise validation error.
        """
        if self.type.data == 'Field':
            if not parent_section.data:
                raise ValidationError('A parent section must be select if type is Field')

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
