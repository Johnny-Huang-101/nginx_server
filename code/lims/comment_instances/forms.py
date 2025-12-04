from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, ValidationError


class Base(FlaskForm):
    comment_item_type = SelectField('Item Type', coerce=str, validators=[DataRequired()])
    comment_item_id = SelectField('Item', validate_choice=False, coerce=int, validators=[DataRequired()])
    comment_id = SelectField('Select from Comment Reference', coerce=int, validate_choice=False)
    comment_text = StringField('Enter Manual Comment')
    include_in_report = BooleanField('Include in Report')

    notes = TextAreaField('Notes')
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    def validate_comment_id(self, comment_id):
        """
        If the comment_text field is blank, ensure there is a value in
        the comment_id field.
        """
        if not self.comment_text.data:
            if not comment_id.data:
                raise ValidationError('Please select or enter a comment')

    def validate_comment_text(self, comment_text):
        """
        If the comment_id field is blank, ensure there is a value in
        the comment_id text.
        """
        if not self.comment_id.data:
            if not comment_text.data:
                raise ValidationError('Please select or enter a comment')

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
