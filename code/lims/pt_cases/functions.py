from lims.models import Cases, CaseTypes, Components, Results, Units, PTCases


# def get_form_choices(form):
#
#     q_case = CaseTypes.query.filter_by(code="Q").first().id
#
#     q_case_id = []  # list of Q-case case IDs
#     q_cases = []  # list of tuples (id, Q-case numbers)
#     for item in Cases.query.filter_by(case_type=q_case).order_by(Cases.create_date.desc()):
#         q_case_id.append(item.id)
#         q_cases.append((item.id, item.case_number))
#
#     q_cases.insert(0,(0,'Select a Q-Case'))
#     # form.case_id.choices = q_cases
#
#     return form
