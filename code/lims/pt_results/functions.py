from sqlalchemy import case

from lims.models import Cases, CaseTypes, Components, Results, Units

eval_dict = {'': (0, 0, 0),  # default selection is blank and would error
             '10% from mean (All)': (0.10, 'mean_all', 'mean_all'),  # key: (amt, prod, center)
             '20% from mean (All)': (0.20, 'mean_all', 'mean_all'),  # ex: eval_A_ref = key4 (30%)
             '25% from mean (All)': (0.25, 'mean_all', 'mean_all'),  # ... eval_B_ref = key5 (2SDs)
             '30% from mean (All)': (0.30, 'mean_all', 'mean_all'),
             '2 SDs (All)': (2, 'sd_all', 'mean_all'),
             '3 SDs (All)': (3, 'sd_all', 'mean_all'),
             '10% from mean (Sub)': (0.10, 'mean_sub', 'mean_sub'),
             '20% from mean (Sub)': (0.20, 'mean_sub', 'mean_sub'),
             '25% from mean (Sub)': (0.25, 'mean_sub', 'mean_sub'),
             '30% from mean (Sub)': (0.30, 'mean_sub', 'mean_sub'),
             '2 SDs (Sub)': (2, 'sd_sub', 'mean_sub'),
             '3 SDs (Sub)': (3, 'sd_sub', 'mean_sub'),
             '10% from target': (0.10, 'target', 'target'),
             '20% from target': (0.20, 'target', 'target'),
             '25% from target': (0.25, 'target', 'target'),
             '30% from target': (0.30, 'target', 'target'),
             'Absolute 2 from mean (Sub)': (2, 1, 'mean_sub'),  # if prod is num, use the value, not the lookup
             'Absolute 3 from mean (Sub)': (3, 1, 'mean_sub'),
             'Absolute 7 from mean (Sub)': (7, 1, 'mean_sub'),
             # 'Qualitative': (0, 0, 0),
             'Qualitative - POS': (0, 1, 1),
             'Qualitative - NEG': (0, 1, 0),
             'Manual': (0, 0, 0)  # if center is num, use the value, not the lookup
             }

eval_choices = [(key, key) for key in eval_dict.keys()]
eval_types = ['eval_A', 'eval_B']



conclusions = [('good_qual', 'good_qual'), ('good_quant', 'good_quant'), ('bad_quant', 'bad_quant'), ('bad_FN', 'bad_FN'),
               ('bad_FP', 'bad_FP'), ('incidental_neutral', 'incidental_neutral'), ('beyondscope_good', 'beyondscope_good'), ('incidental_good', 'incidental_good'),
               ('incidental_bad', 'incidental_bad')]
conclusions.insert(0, (0, 'Select the FLD conclusion'))


def get_form_choices(form, case_id=None):

    pt_components = [(item.id, item.name) for item in Components.query]
    pt_components.insert(0, (0, 'If applicable, select the PT Component Name'))

    units = [(item.id, item.name) for item in Units.query]
    units.insert(0, (0, 'If applicable, select the PT Unit'))

    q_case = CaseTypes.query.filter_by(code="Q").first().id
    q_case_id = []  # list of Q-case case IDs
    q_cases = []  # list of tuples (id, Q-case numbers)
    for item in Cases.query.filter_by(case_type=q_case).order_by(Cases.create_date.desc()):
        q_case_id.append(item.id)
        q_cases.append((item.id, item.case_number))

    q_cases.insert(0,(0,'Select a Q-Case'))
    form.case_id.choices = q_cases

    if case_id is not None:
        results = [(item.id, f"{item.test.specimen.accession_number} | {item.component_name} |  {item.result} | "\
                    f"{item.concentration} | {item.test.batch.batch_id}") for item in Results.query.filter_by(case_id=case_id)]  # TODO add filter_by criteria of reported="Y"
        # defined here and in views.py
        results.insert(0,(0,'Select a result'))
        form.result_id.choices = results
        form.case_id.data = case_id
    else:
        form.result_id.choices = [(0, 'No case selected')]

    form.eval_A_ref.choices = eval_choices
    form.eval_B_ref.choices = eval_choices
    form.pt_component_id.choices = pt_components
    form.pt_unit_id.choices = units
    form.eval_FLD_conclusion.choices = conclusions

    return form


def process_form(form, is_etoh, is_official, result, **kwargs):

# ALL
    # Initializing evaluation flags and variables
    overall_conclusion = False
    eval_min = None
    eval_max = None
    abft_conclusion = False
    display_abft = None
    is_qual = True if form.eval_A_ref.data == "Qualitative - POS" or form.eval_A_ref.data == "Qualitative - NEG" else False

    kwargs['result_id'] = result.id

# ALL
    # Checking if the result requires approval (only official results do)
    if is_official:
        kwargs['eval_FLD_conclusion'] = form.eval_FLD_conclusion.data
        kwargs['pt_reporting_limit'] = form.pt_reporting_limit.data
        kwargs['pt_participants'] = form.pt_participants.data
        requires_approval = True
    else:
        kwargs['eval_FLD_conclusion'] = None
        kwargs['pt_reporting_limit'] = None
        kwargs['pt_participants'] = None
        requires_approval = False

    # for now, Results only contains Results and Concentrations
    calc = result.concentration if result.concentration != 0 else None
    if result.result is None:
        conc = 0
    else:
        if result.result == "ND" or result.result == "Not Detected":
            conc = 0
        else:
            if is_qual:
                conc = 1
            else:
                try:
                    conc = float(result.concentration)
                except ValueError:
                    conc = 1
                except TypeError:
                    conc = 1

    print("is etoh: ", is_etoh)
    print("calc is: ", calc)
    print("conc is: ", conc)

    if form.eval_A_ref.data == '':
        overall_conclusion = "N/A"
    else:
        for eval_type in eval_types:
            form_eval_choice = form.data[f"{eval_type}_ref"]

            if form_eval_choice == '':
                continue
            else:
                if form_eval_choice == "Manual":
                    eval_min = form.eval_manual_min.data
                    eval_max = form.eval_manual_max.data

                else:
                    # Handling other evaluation criteria based on dictionary
                    eval_criteria = eval_dict[form_eval_choice]  # (0.30, mean_all, mean_all)
                    amt, prod_item, center_item = eval_criteria

                    print("amt: ", amt)
                    print("prod_item is: ", prod_item)
                    print("center_item is: ", center_item)

                    # Calculating evaluation min and max using eval_dict's prod and center as additional cues
                    eval_value = center_item if isinstance(center_item, int) else form.data[center_item]
                    eval_prod = prod_item if isinstance(prod_item, int) else form.data[prod_item]

                    eval_min = eval_value - amt * eval_prod
                    eval_max = eval_value + amt * eval_prod
                eval_conclusion = eval_min <= conc <= eval_max
                print('eval_conclusion is: ',eval_conclusion)
                print('initial overall_conclusion is: ',overall_conclusion)
                overall_conclusion = overall_conclusion or eval_conclusion
                print('overall_conclusion is: ',overall_conclusion)

    print('eval_min is: ', eval_min)
    print('eval_max is: ', eval_max)
    print('FINAL overall_conclusion is: ',overall_conclusion)
    kwargs['eval_overall_conclusion'] = overall_conclusion

    # Performing and recording ABFT evaluation and flags
    if is_official and is_qual:
        abft_conclusion = overall_conclusion
        display_abft = 'OK' if abft_conclusion else 'Qual OOO'

    elif is_official:
        ### Quant ABFT Evaluation ###
        if form.mean_all.data is None and form.mean_sub.data is None:
            abft_conclusion_mean = None
            abft_conclusion_2sd = None
        else:
            abft_mean = form.mean_sub.data if form.mean_all.data is None else form.mean_all.data
            abft_sd = form.sd_sub.data if form.sd_all.data is None else form.sd_all.data

            if is_etoh:
                abft_conclusion_mean = 0.9 * abft_mean <= conc <= 1.1 * abft_mean
            else:
                abft_conclusion_mean = 0.8 * abft_mean <= conc <= 1.2 * abft_mean

            abft_conclusion_2sd = abft_mean - 2 * abft_sd <= conc <= abft_mean + 2 * abft_sd

        abft_conclusion = abft_conclusion_mean or abft_conclusion_2sd

        if not abft_conclusion_mean and not abft_conclusion_2sd:
            display_abft = '%Mean and 2SD'
        elif not abft_conclusion_mean:
            display_abft = '%Mean'
        elif not abft_conclusion_2sd:
            display_abft = '2SD'
        else:
            display_abft = 'OK'
    else:
        abft_conclusion = ''
        display_abft = ''

    # Updating kwargs with ABFT conclusions and other calculated values for each shared result
    kwargs['calc'] = calc
    kwargs['conc'] = conc
    kwargs['eval_manual_min'] = eval_min
    kwargs['eval_manual_max'] = eval_max
    kwargs['eval_ABFT_conclusion'] = abft_conclusion
    kwargs['eval_ABFT_display'] = display_abft

    try:
        kwargs['target_percent'] = (calc - form.target.data) / form.target.data
    except TypeError:  # could leave it as "except:" - broad is OK
        pass
    if form.mean_all.data is not None:
        try:
            kwargs['mean_all_percent'] = (calc - form.mean_all.data) / form.mean_all.data
            kwargs['z_all'] = (calc - form.mean_all.data) / form.sd_all.data
        except TypeError:
            pass
    try:
        kwargs['mean_sub_percent'] = (calc - form.mean_sub.data) / form.mean_sub.data
        kwargs['z_sub'] = (calc - form.mean_sub.data) / form.sd_sub.data
    except TypeError:
        pass

    return kwargs, requires_approval
