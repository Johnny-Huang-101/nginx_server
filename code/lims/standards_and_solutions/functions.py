from flask import request
import sqlalchemy as sa

from lims import db
from lims.models import AssayConstituents, Components, StandardsAndSolutions, SolutionTypes, Users, CalibratedLabware, SolventsAndReagents, Batches, \
    Assays, Preservatives, CooledStorage
from lims.locations.functions import location_dict



def get_form_choices(form, initial=True, item=None, series=False, is_post=False):

    # Get user choices who can create standards/solutions
    by_choices = [(query_item.id, query_item.initials) for query_item in Users.query.filter(sa.and_(Users.job_class.in_(['2403', '2456',
                                                                                                        '2457', '2458']), 
                                                                                                        Users.status.in_(['Active'])))]

    # Check if initial submission
    if initial:
        
        # Get all solution types
        solution_types = [(query_item.id, query_item.name) for query_item in SolutionTypes.query.all()]
        solution_types.insert(0, (0, '--'))
        form.solution_type_id.choices = solution_types

        sorted_loc_dict = dict(sorted(location_dict.items(), key=lambda item: item[1]['option']))

        # Get all location table choices
        choices = [(k, v['option']) for k, v in sorted_loc_dict.items()]
        choices.insert(0, ('', 'Please select a location type'))
        form.location_table.choices = choices

        # Get all assay choices
        form.assay.choices = [
            (str(query_item.id), query_item.assay_name)
            for query_item in Assays.query.filter_by(status_id=1).order_by(Assays.assay_name.asc()).all()
        ]

        # Set prepared_by choices
        form.prepared_by.choices = by_choices

        # Check if a series is being added
        if series:
            
            # Set relevant fields to readonly
            form.solution_type_id.render_kw = {'readonly': True}
            form.description.render_kw = {'readonly': True}

            # Set name and parent_standard_lot choices
            form.name.choices = [(const.id, const.name) for const in 
                                 AssayConstituents.query.filter(AssayConstituents.id.in_(item.type.constituents.split(', ')))]
            
            form.parent_standard_lot.choices = [(query_item.id, query_item.lot) for query_item in
                                                StandardsAndSolutions.query.filter_by(solution_type_id=item.solution_type_id)]
            
            # If not submitting form
            if not is_post:
                
                if isinstance(item.assay, str):
                    form.assay.data = [v.strip() for v in item.assay.split(", ") if v.strip()]
                else:
                    form.assay.data = list(item.assay)

                # Set all data inherited from parent
                form.description.data = item.description
                form.solution_type_id.data = item.solution_type_id
                form.parent_standard_lot.data = item.id

    # If not initial submission
    else:
        
        # Render extra spaces for form choices
        nbsp = '\u00A0'

        # Get all standards_and_solutions choices
        prepared_standard_choices = [(query_item.id, 
                                       f'{query_item.type.name} {nbsp} {nbsp} | {nbsp} {nbsp} {query_item.lot} {nbsp} {nbsp} '\
                                        f'| {nbsp} {nbsp} (exp. {query_item.retest_date.strftime("%m/%d/%Y") if query_item.retest_date is not None else ""})') 
                                        for query_item in StandardsAndSolutions.query.filter_by(in_use=True)]
        # Get all solvents_and_reagents choices
        purchased_reagent_choices = [(query_item.id, 
                                       f'{query_item.type.name} {nbsp} {nbsp} | {nbsp} {nbsp} {query_item.lot} {nbsp} {nbsp} '\
                                        f'| {nbsp} {nbsp} (exp. {query_item.exp_date.strftime("%m/%d/%Y") if query_item.exp_date is not None else ""})') 
                                        for query_item in SolventsAndReagents.query.filter_by(in_use=True)]

        # Set form field choices if relevant
        if item.part_a_table not in [None, 'N/A']:
            if item.part_a_table == 'standards_and_solutions':
                form.part_a_id.choices = prepared_standard_choices
            else:
                form.part_a_id.choices = purchased_reagent_choices

        if item.part_b_table not in [None, 'N/A']:
            if item.part_b_table == 'standards_and_solutions':
                form.part_b_id.choices = prepared_standard_choices
            else:
                form.part_b_id.choices = purchased_reagent_choices

        if item.part_c_table not in [None, 'N/A']:
            if item.part_c_table == 'standards_and_solutions':
                form.part_c_id.choices = prepared_standard_choices
            else:
                form.part_c_id.choices = purchased_reagent_choices

        form.component.choices = [(comp.id, comp.name) for comp in Components.query]
        form.component.choices.insert(0, ('', '--'))

        # If not a child standard
        if not item.parent_standard_lot:

            # Get standard type choices
            standard_type_ids = [query_item.id for query_item in SolutionTypes.query.filter_by(id=item.type.id)]
            standard_choices = [(query_item.id, query_item.lot) for query_item in
                                StandardsAndSolutions.query.filter(
                                    StandardsAndSolutions.solution_type_id.in_(standard_type_ids))]
            standard_choices = standard_choices[::-1]
            standard_choices.insert(0, (0, '--'))

            # Get calibrated labware choices
            labware_choices = [(str(query_item.id), f'{query_item.type.name} - {query_item.equipment_id}') for query_item in CalibratedLabware.query]
            labware_choices.insert(0, (0, '--'))

            # Get solvent choices
            form.solvent_used.choices = [(solution.id, f'{solution.name} / {solution.lot}') for solution in SolventsAndReagents.query]
            form.solvent_used.choices.insert(0, (0, '--'))

            # Get relevant batch choices
            batch_choices = [(query_item.id, query_item.batch_id) for query_item in Batches.query.filter(Batches.db_status != 'Removed').all()]
            batch_choices = batch_choices[::-1]
            batch_choices.insert(0, (0, '--'))

            # Preservative choices for blank matrices
            form.preservatives.choices = [(query_item.id, query_item.name) for query_item in Preservatives.query]
            form.preservatives.choices.insert(0, (0, '--'))

            # Set relevant choices
            form.parent_standard_lot.choices = standard_choices
            form.equipment_used.choices = labware_choices
            form.verification_batches.choices = batch_choices
            form.previous_lot.choices = standard_choices
        
        # If is child standard
        else:
            
            # Get parent standard object from child
            parent_standard = StandardsAndSolutions.query.get(item.parent_standard_lot)

            # Get standard type choices
            standard_type_ids = [query_item.id for query_item in SolutionTypes.query.filter_by(id=item.type.id)]
            standard_choices = [(query_item.id, query_item.lot) for query_item in
                                StandardsAndSolutions.query.filter(
                                    StandardsAndSolutions.solution_type_id.in_(standard_type_ids))]
            standard_choices = standard_choices[::-1]
            standard_choices.insert(0, (0, '--'))

            # Get calibrated labware choices
            labware_choices = [(str(query_item.id), f'{query_item.type.name} - {query_item.equipment_id}') for query_item in CalibratedLabware.query]
            labware_choices.insert(0, (0, '--'))

            # Get solvent choices
            form.solvent_used.choices = [(solution.id, f'{solution.name} / {solution.lot}') for solution in SolventsAndReagents.query]
            form.solvent_used.choices.insert(0, (0, '--'))

            # Get relevant batch choices
            batch_choices = [(query_item.id, query_item.batch_id) for query_item in Batches.query.filter(Batches.db_status != 'Removed').all()]
            batch_choices = batch_choices[::-1]
            batch_choices.insert(0, (0, '--'))

            # Preservative choices for blank matrices
            form.preservatives.choices = [(query_item.id, query_item.name) for query_item in Preservatives.query]
            form.preservatives.choices.insert(0, (0, '--'))

            # Set all relevant choices
            form.parent_standard_lot.choices = standard_choices
            form.equipment_used.choices = labware_choices
            form.verification_batches.choices = batch_choices
            form.previous_lot.choices = standard_choices
            form.parent_standard_lot.data = item.parent_standard_lot
            form.solvent_used.data = parent_standard.solvent_used
            form.preservatives.data = parent_standard.preservatives
            form.verification_batches.data = parent_standard.verification_batches
            form.verification_comments.data = parent_standard.verification_comments
            form.previous_lot.data = parent_standard.previous_lot
            form.previous_lot_comments.data = parent_standard.previous_lot_comments
            form.calibration_comments.data = parent_standard.calibration_comments
            form.qualitative_comments.data = parent_standard.qualitative_comments
            form.quantitative_comments.data = parent_standard.quantitative_comments
            form.additional_comments.data = parent_standard.additional_comments

            # Set no+_previous_lot to True if parent has it as True
            if parent_standard.previous_lot_comments == 'N/A':
                form.no_previous_lot.data = True

            # Set inherited fields to disabled
            form.solvent_used.render_kw = {'disabled': True}
            form.preservatives.render_kw = {'disabled': True}
            form.verification_batches.render_kw = {'disabled': True}
            form.verification_comments.render_kw = {'disabled': True}
            form.previous_lot.render_kw = {'disabled': True}
            form.calibration_comments.render_kw = {'disabled': True}
            form.qualitative_comments.render_kw = {'disabled': True}
            form.quantitative_comments.render_kw = {'disabled': True}
            form.additional_comments.render_kw = {'disabled': True}

    return form
