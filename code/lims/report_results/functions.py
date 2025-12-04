from flask import jsonify
from lims import db
from lims.models import Cases, Results, Tests, Specimens, Batches, \
    Components, DrugClasses, SpecimenTypes, ReportResults, Modifications, disciplines


# def get_form_choices(form, case_id=None, discipline='Toxicology'):
#     kwargs = {}
#
#     if case_id:
#
#
#         # case = Cases.query.get(case_id)
#         # discipline_choices = [(0, 'Please select a discipline')]
#         # for discipline in disciplines:
#         #     print(getattr(case, f"{discipline.lower()}_performed"))
#         #     if getattr(case, f"{discipline.lower()}_performed") == 'Yes':
#         #         discipline_choices.append((discipline, discipline))
#
#         results = Results.query.filter(Results.case_id == case_id) \
#             .join(Components) \
#             .join(DrugClasses) \
#             .join(Tests)\
#             .join(Specimens).join(SpecimenTypes)\
#             .join(Batches)\
#             .filter(SpecimenTypes.discipline == 'Toxicology')\
#             .order_by(Tests.specimen_id, Results.component_name.asc()).distinct(Results.id)
#
#         specimen_ids = []
#         result_choices = []
#         result_ids = []
#         primary_result_ids = []
#         component = ""
#         # specimen_id = ""
#         for result in results:
#             # spec_id = result.test.specimen_id
#             specimen_ids.append(result.test.specimen_id)
#             result_choices.append((result.id, result.id))
#             result_ids.append(result.id)
#             if (component != result.component_name):
#                 primary_result_ids.append(result.id)
#
#             component = result.component_name
#             # specimen_id = spec_id
#
#
#         specimens = [(specimen.id, f"{specimen.type.code} | {specimen.accession_number}") for specimen in Specimens.query.filter(Specimens.id.in_(specimen_ids))]
#         kwargs['specimen_n'] = len(specimens)
#         if len(specimens):
#             kwargs['specimen_text'] = f'Specimen 1 of {len(specimens)}'
#         else:
#             kwargs['specimen_text'] = 'No specimens with finalized tests'
#
#         if not len(specimen_ids):
#             specimens.insert(0, (0, 'No specimens with finalized tests'))
#
#         # form.discipline.choices = discipline_choices
#         form.specimen_id.choices = specimens
#         form.result_id.choices = result_choices
#         form.primary_result_id.choices = result_choices
#
#         kwargs['result_id'] = result_ids
#         kwargs['primary_result_id'] = primary_result_ids
#
#     else:
#         # cases = [(case.id, case.case_number) for case in Cases.query.order_by(Cases.id.desc())]
#         # cases.insert(0, (0, 'Please select a case'))
#         # form.case_id.choices = cases
#
#         form.specimen_id.choices = [(0, 'No Case Selected')]
#         # form.discipline.choices = [(0, 'No Case Selected')]
#         form.result_id.choices = [(0, 'No Results')]
#         form.primary_result_id.choices = [(0, 'No Results')]
#
#         kwargs['specimen_text'] = "No case selected"
#
#     cases = [(case.id, case.case_number) for case in Cases.query.order_by(Cases.id.desc())]
#     cases.insert(0, (0, 'Please select a case'))
#     form.case_id.choices = cases
#
#     return form, kwargs


def get_form_choices(form, case_id=None, discipline=None):
    kwargs = {}

    if case_id:

        case = Cases.query.get(case_id)

        discipline_choices = [(0, 'Please select a discipline')]
        for disc in disciplines:
            print(getattr(case, f"{disc.lower()}_performed"))
            if getattr(case, f"{disc.lower()}_performed") == 'Yes':
                discipline_choices.append((disc, disc))

        form.discipline.choices = discipline_choices

        if discipline:

            results = Results.query.filter(Results.case_id == case_id) \
                .join(Components) \
                .join(DrugClasses) \
                .join(Tests) \
                .join(Specimens).join(SpecimenTypes) \
                .join(Batches) \
                .filter(SpecimenTypes.discipline == discipline) \
                .order_by(Tests.specimen_id, Results.component_name.asc()).distinct(Results.id)

            specimen_ids = []
            result_choices = []
            result_ids = []
            primary_result_ids = []
            component = ""
            # specimen_id = ""
            for result in results:
                # spec_id = result.test.specimen_id
                specimen_ids.append(result.test.specimen_id)
                result_choices.append((result.id, result.id))
                result_ids.append(result.id)
                if (component != result.component_name):
                    primary_result_ids.append(result.id)

                component = result.component_name
                # specimen_id = spec_id

            specimens = [(specimen.id, f"{specimen.type.code} | {specimen.accession_number}") for specimen in
                         Specimens.query.filter(Specimens.id.in_(specimen_ids))]
            kwargs['specimen_n'] = len(specimens)
            if len(specimens):
                kwargs['specimen_text'] = f'Specimen 1 of {len(specimens)}'
            else:
                kwargs['specimen_text'] = 'No specimens with finalized tests'

            if not len(specimen_ids):
                specimens.insert(0, (0, 'No specimens with finalized tests'))

            form.specimen_id.choices = specimens
            form.result_id.choices = result_choices
            form.primary_result_id.choices = result_choices
            form.observed_result_id.choices = result_choices
            form.qualitative_result_id.choices = result_choices

            kwargs['result_id'] = result_ids
            kwargs['primary_result_id'] = primary_result_ids

        else:
            form.record_template_id = []
            form.specimen_id.choices = [(0, 'No discipline selected')]
            form.result_id.choices = [(0, 'No discipline selected')]
            form.primary_result_id.choices = [(0, 'No discipline selected')]
            form.observed_result_id.choices = [(0, 'No discipline selected')]
            form.qualitative_result_id.choices = [(0, 'No discipline selected')]
            kwargs['specimen_text'] = "No discipline selected"

    else:
        # cases = [(case.id, case.case_number) for case in Cases.query.order_by(Cases.id.desc())]
        # cases.insert(0, (0, 'Please select a case'))
        # form.case_id.choices = cases
        form.discipline.choices = [(0, 'No case selected')]
        form.specimen_id.choices = [(0, 'No case selected')]
        form.result_id.choices = [(0, 'No case selected')]
        form.primary_result_id.choices = [(0, 'No case selected')]
        form.observed_result_id.choices = [(0, 'No case selected')]
        form.qualitative_result_id.choices = [(0, 'No case selected')]
        kwargs['specimen_text'] = "No case selected"

    cases = [(case.id, case.case_number) for case in Cases.query.order_by(Cases.id.desc())]
    cases.insert(0, (0, 'Please select a case'))
    form.case_id.choices = cases

    return form, kwargs


def get_disciplines(case_id):
    case = Cases.query.get(case_id)

    choices = []

    if case_id:
        for discipline in disciplines:
            if getattr(case, f"{discipline.lower()}_performed") == 'Yes':
                choices.append({'id': discipline, 'name': discipline})

        if len(choices):
            choices.insert(0, {'id': 0, 'name': 'Please select a discipline'})
        else:
            choices.append({'id': 0, 'name': 'No disciplines performed for this case'})

    else:
        choices.append({'id': 0, 'name': 'Please select a case'})

    print(choices)

    return jsonify({'choices': choices})



# def get_specimens(case_id):
#
#     results = Results.query.filter_by(case_id=case_id)
#     specimen_ids = sorted([result.test.specimen.id for result in results])
#     specimens = Specimens.query.filter(Specimens.id.in_(specimen_ids))
#     results = Results.query.filter_by(case_id=case_id)
#     specimen_choices = []
#     result_choices = []
#     result_ids = []
#     specimen_id = None
#     if case_id:
#         if specimens.count():
#             specimen_id = specimen_ids[0]
#             # choices.append({'id': 0, 'name': 'Please select a specimen'})
#             for specimen in specimens:
#                 choice = {}
#                 choice['id'] = specimen.id
#                 choice['name'] = f"{specimen.type.code} | {specimen.accession_number}"
#                 specimen_choices.append(choice)
#         else:
#             specimen_choices.append({'id': 0, 'name': 'No specimens for this case have been tested'})
#
#         if results.count():
#             result_choices = [{'id': result.id, 'name': result.id} for result in results]
#             result_ids = [result.id for result in results]
#     else:
#         result_choices.append({'id': 0, 'name': 'No case selected'})
#
#     return jsonify({'specimen_choices': specimen_choices,
#                     'result_choices': result_choices,
#                     'result_ids': result_ids,
#                     'primary_result_ids'
#                     'current': 1,
#                     'total': specimens.count(),
#                     'specimen_id': specimen_id}
#                    )


def get_results(specimen_id):
    results = []
    result_ids = []
    # primary_result_ids = []
    if specimen_id:
        case_type = Specimens.query.get(specimen_id).case.type.code
        test_ids = [test.id for test in Tests.query.filter_by(specimen_id=specimen_id)]
        items = Results.query.filter(Results.test_id.in_(test_ids)).\
            join(Components).\
            join(DrugClasses).\
            join(Tests).join(Batches)

        if case_type == 'PM':
            items = items.order_by(DrugClasses.pm_rank, Components.rank, Results.result_type.desc(), Batches.extraction_date)
        elif case_type == 'X':
            items = items.order_by(DrugClasses.x_rank, Components.rank, Results.result_type.desc(), Batches.extraction_date)
        else:
            items = items.order_by(DrugClasses.m_d_rank, Components.rank, Results.result_type.desc(), Batches.extraction_date)

        if items.count():
            x = 0
            component = ""
            for item in items:
                result_ids.append(item.id)
                x += 1
                primary = ""
                # result_ids.append(item.id)

                # Handle primary result
                if component != item.component_name:
                    component = item.component_name
                    primary = "checked"
                    # primary_result_ids.append(item.id)

                # Handle dilutions
                dilution = ""
                if item.test.dilution:
                    if item.test.dilution == '1':
                        dilution = ''
                    elif item.test.dilution.isnumeric():
                        if int(item.dilution) > 1:
                            dilution = f"d1/{item.test.dilution}"
                    else:
                        dilution = item.test.dilution

                # Handle units
                units = ""
                supp_units = ""
                if item.scope and item.scope.unit:
                    if item.result != "Not Detected":
                        units = item.scope.unit.name
                    if item.supplementary_result:
                        supp_units = units

                unit = ""
                if item.scope.unit:
                    unit = item.scope.unit.name

                # Handle ranks
                drug_class = 99
                if case_type == 'PM':
                    drug_class = f"{item.component.drug_class.name} ({item.component.drug_class.pm_rank})"
                elif case_type == 'X':
                    drug_class = f"{item.component.drug_class.name} ({item.component.drug_class.x_rank})"
                else:
                    drug_class = f"{item.component.drug_class.name} ({item.component.drug_class.m_d_rank})"

                result_dict = {}
                result_dict['items'] = [
                    x,
                    primary,
                    item.component_name,
                    item.result,
                    item.supplementary_result,
                    unit,
                    item.test.assay.assay_name,
                    item.test.batch.batch_id,
                    item.test.batch.extraction_date.strftime('%m/%d/%Y'),
                    dilution,
                    item.component.rank,
                    drug_class,
                    item.id,
                ]

                results.append(result_dict)


    return {'results': results, 'result_ids': result_ids} #, 'primary_result_ids': primary_result_ids}



def add_report_results(**kwargs):

    item = ReportResults(**kwargs)
    db.session.add(item)

    modification = Modifications(


    )




    return None