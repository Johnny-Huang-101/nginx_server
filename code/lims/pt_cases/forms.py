from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField

status_dict = [
     ('Need Provider Evaluation', 'Need Provider Evaluation'),
     ('Need Internal Evaluation', 'Need Internal Evaluation'),
     ('Need Approval', 'Need Approval'),
]


class Base(FlaskForm):
    summary = TextAreaField('Evaluation Summary', render_kw={'rows': '2'})

    good_qual_comment = TextAreaField('expected, in scope, reported [Successful Qualitative]', render_kw={'rows': '2'})
    good_quant_comment = TextAreaField('expected, in scope, reported [Successful Quantitation]', render_kw={'rows': '2'})
    bad_quant_comment = TextAreaField('expected, in scope, reported [Unsuccessful Quantitation]', render_kw={'rows': '2'})
    bad_FN_comment = TextAreaField('expected, in scope, not reported [Unsuccessful (false negative)]', render_kw={'rows': '2'})
    bad_FP_comment = TextAreaField('not expected, in scope, reported [Unsuccessful (false positive)]', render_kw={'rows': '2'})
    incidental_neutral_comment = TextAreaField('not expected, in scope, reported in comments [Incidental - In Scope]', render_kw={'rows': '2'})
    beyondscope_good_comment = TextAreaField('expected, out of scope, not reported [Incidental - Beyond Scope]', render_kw={'rows': '2'})
    incidental_good_comment = TextAreaField('expected, out of scope, reported in comments [Incidental - Expected Monitored/Trace]', render_kw={'rows': '2'})
    incidental_bad_comment = TextAreaField('not expected, out of scope, reported in comment [Incidental - Unexpected Monitored/Trace]', render_kw={'rows': '2'})

    notes = TextAreaField('Q-Case Notes', render_kw={'rows': '2'})
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
