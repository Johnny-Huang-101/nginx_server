from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, ValidationError


class Base(FlaskForm):
    name = StringField('Retention Policy Name', validators=[DataRequired()])
    date_selection = SelectField('Date Selection', choices=[('Automatic', 'Automatic'), ('Manual', 'Manual')])
    retention_length = StringField('Retain for (days)')

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    def validate_retention_length(self, retention_length):
        if self.date_selection.data == 'Automatic':
            if not retention_length.data:
                raise ValidationError("The number of days must be specified")

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
