from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    pm_rank = StringField('PM Case Rank')
    m_d_rank = StringField('M/D/P Case Rank')
    x_rank = StringField('X Case Rank')
    q_rank = StringField('Q Case Rank')
    scope_rank = StringField("Scope Rank")
    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})


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
