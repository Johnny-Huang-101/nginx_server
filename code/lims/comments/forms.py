from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired
from lims.models import module_definitions

# Comment types are all the different modules in the LIMS. There is also a
# Global type. Global comment types are accessible by all modules
comment_type_choices = [(module, module) for module in module_definitions.keys()]
comment_type_choices.insert(0, ('Global', 'Global'))
comment_type_choices.insert(0, (0, 'Please select a comment type'))


class Base(FlaskForm):
    code = StringField('Code')
    comment_type = SelectField('Type', choices=comment_type_choices, validators=[DataRequired()])
    comment = StringField('Comment', validators=[DataRequired()])

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
