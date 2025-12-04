from datetime import datetime, timedelta
import sqlalchemy as sa
from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import func, case


def get_alerts(app):
    """
        Get the number of alerts for each module. Alerts can be either:
            - Normal
            - Warning
            - Danger
        The function returns a dictionary with the number of alerts per module and per tier:
            - e.g., alerts = {
                    cases_normal: 5,
                    cases_warning: 2,
                    cases_danger: 0,
                    ...
                }

        Pending and locked items are considered normal alerts.

        Since we can't import the tables from models.py (circular imports) we will
        create the models dictionary where the key is the __tablename__ for each
        table and the value is the db.Model class of your table i.e.

        models = {
            'reports': Reports,
            'case_types': CaseTypes,
        }

        To get the table we want to query we just use:
            reports = models['reports']
    """

    from lims import cache

    cache.set('locked', True, timeout=300)

    def set_cache(k, query, model_name=None, timeout=300):

        if model_name and should_skip_cache(model_name):
            val = query()
            cache.set(k, val, timeout)
        else:
            val = cache.get(k)
            if val is None:
                val = query()
                cache.set(k, val, timeout)

        return val

    #
    # # helper function for redis cache
    # def get_or_cache(key, query_func, timeout=300):
    #     val = cache.get(key)
    #     if val is None:
    #         val = query_func()
    #         cache.set(key, val, timeout=timeout)
    #     return val
    #
    # # caching for more important info
    # def get_or_cache_count(key, query, model_name=None, timeout=300):
    #
    #     if model_name and should_skip_cache(model_name):
    #         # print(f"\033[1;34mThe model {model_name} is important and we are not caching it \033[0m")
    #         count = query()
    #         cache.set(key, count, timeout=15)
    #         return count
    #
    #     count = cache.get(key)
    #     if count is None:
    #         count = query()
    #         cache.set(key, count, timeout=timeout)
    #     return count

    def should_skip_cache(model_name: str) -> bool:
        return any(keyword in model_name.lower() for keyword in SKIP_CACHE_KEYWORDS)

    # def get_alert_counts_combined(table, name, ignore_statuses, timeout=300):
    #     if not hasattr(table, 'db_status'):
    #         return 0, 0, 0  # danger, normal_pending, normal_locked

    #     skip_cache = should_skip_cache(name)

    #     key = f"{name}_combined_alerts"

    #     if not skip_cache:
    #         cached = cache.get(key)
    #         if cached is not None:
    #             return cached

    #     clauses = []

    #     # Danger: db_status == 'Removal Pending'
    #     if hasattr(table, 'db_status'):
    #         clauses.append(
    #             func.count(case((table.db_status == 'Removal Pending', 1))).label('danger')
    #         )

    #     # Normal: db_status not in ignore_statuses
    #     if hasattr(table, 'db_status') and hasattr(table, 'locked'):
    #         clauses.append(
    #             func.count(case((table.db_status.notin_(ignore_statuses), 1))).label('normal_pending')
    #         )

    #         clauses.append(
    #             func.count(
    #                 case((
    #                     and_(
    #                         table.locked == True,
    #                         table.db_status.notin_(ignore_statuses)
    #                     ), 1)
    #                 )
    #             ).label('normal_locked')
    #         )
    #     else:
    #         # pad with 0s if missing columns
    #         clauses.append(sa.literal(0).label('normal_pending'))
    #         clauses.append(sa.literal(0).label('normal_locked'))

    #     result = table.query.with_entities(*clauses).one()
    #     result_tuple = tuple(result)

    #     if not skip_cache:
    #         cache.set(key, result_tuple, timeout=timeout)

    #     return result_tuple  # (danger, normal_pending, normal_locked)

    models = {}
    for cls in app.extensions['sqlalchemy'].db.Model.registry.mappers:
        table = cls.class_
        name = table.__tablename__
        models[name] = table

    SKIP_CACHE_KEYWORDS = ['case', 'container', 'specimen', 'draft', 'report', 'batches']
    ignore_statuses = ['Active', 'Removed']
    alerts = {}

    alerts['total_locked_by_user'] = 0
    alerts['total_pending_by_user'] = 0

    for name, table in models.items():

        alerts[f'{name}_normal'] = 0
        alerts[f'{name}_warning'] = 0
        alerts[f'{name}_danger'] = 0
        alerts[f'{name}_locked_by_user'] = 0
        alerts[f'{name}_pending_by_user'] = 0

        # danger, pending, locked = get_alert_counts_combined(table,name,ignore_statuses)

        # alerts[f'{name}_danger'] += danger
        # alerts[f'{name}_normal'] += pending + locked
        if hasattr(table, 'db_status'):
            key = f'{name}_danger_removal_pending'

            alerts[f'{name}_danger'] += set_cache(
                key,
                lambda: table.query.filter_by(db_status='Removal Pending').count(),
                model_name=name
            )

            if hasattr(table, 'locked'):
                key1 = f'{name}_normal_pending'
                q1 = table.query.filter(table.db_status.not_in(ignore_statuses)).distinct(table.id)
                count1 = set_cache(key1, lambda: q1.count(), model_name=name)

                key2 = f'{name}_normal_locked'
                q2 = table.query.filter(
                    and_(
                        table.locked == True,
                        table.db_status.not_in(ignore_statuses)
                    )
                ).distinct(table.id)
                count2 = set_cache(key2, lambda: q2.count(), model_name=name)

                alerts[f'{name}_normal'] += count1 + count2

                if current_user.is_active and current_user.is_authenticated:
                    # query = table.query.with_entities(
                    #     func.count(
                    #         case((table.locked_by==current_user.initials,1))
                    #     ).label('user_locked'),
                    #     func.count(
                    #         case((table.pending_submitter==current_user.initials,1))
                    #     ).label('user_pending')
                    # )
                    # user_locked,user_pending = query.one()

                    # user_locked = table.query.filter_by(locked_by=current_user.initials).count()
                    # user_pending = table.query.filter_by(pending_submitter=current_user.initials).count()

                    user_locked = set_cache(
                        f'{name}_locked_by_user_{current_user.initials}',
                        lambda: table.query.filter_by(locked_by=current_user.initials).count(),
                        model_name=name,
                        timeout=60
                    )
                    user_pending = set_cache(
                        f'{name}_pending_by_user_{current_user.initials}',
                        lambda: table.query.filter_by(pending_submitter=current_user.initials).count(),
                        model_name=name,
                        timeout=60
                    )

                    alerts[f'{name}_locked_by_user'] = user_locked
                    alerts[f'{name}_pending_by_user'] = user_pending
                    alerts['total_locked_by_user'] += user_locked
                    alerts['total_pending_by_user'] += user_pending

        ######

    ### CUSTOM ALERTS ###
    """
        If you want alerts in addition to the ones above for a module
        e.g., number of reports that are "Ready for CR" and "Ready for DR" you can
        append the counts to that <module_name> in the dictionary i.e.:

        reports = models['reports']
        module_alerts['reports_normal'] += Reports.query.filter(Reports.report_status.in_(['Ready for CR', 'Ready for DR']).count())

    """

    thirty_days = datetime.today() + timedelta(days=30)

    cases = models['cases']
    calibrated = models['calibrated_labware']
    general = models['general_labware']
    histo = models['histology_equipment']
    inst = models['instruments']
    cooled = models['cooled_storage']
    probes = models['probes']
    hoods = models['fume_hoods']
    reports = models['reports']
    packets = models['litigation_packets']
    requests = models['requests']
    standards_and_solutions = models['standards_and_solutions']
    solvents_and_reagents = models['solvents_and_reagents']

    alerts['cases_normal'] = cases.query.filter(
        sa.or_(
            cases.case_status.in_(['Need Accessioning', 'Need Test Addition']),
            cases.priority == 'High'
        )
    ).distinct(cases.id).count()

    disciplines = ['Toxicology', 'Biochemistry', 'Histology', 'External', 'Physical', 'Drug']
    filter_query = tuple(
        getattr(cases, f"{discipline.lower()}_status") == 'Ready for Drafting'
        for discipline in disciplines
    )

    alerts['drafting_normal'] = cases.query.filter(
        sa.or_(*filter_query)
    ).count()

    alerts['calibrated_labware_warning'] = set_cache('calibrated_labware_warning', lambda: calibrated.query.filter(
        calibrated.status_id == 1,
        calibrated.due_service_date <= thirty_days,
        calibrated.due_service_date > datetime.now(),
    ).count(), model_name='calibrated_labware')

    alerts['calibrated_labware_danger'] = set_cache('calibrated_labware_danger', lambda: calibrated.query.filter(
        calibrated.status_id == 1,
        calibrated.due_service_date <= datetime.today()
    ).count(), model_name='calibrated_labware')

    alerts['general_labware_warning'] = set_cache('general_labware_warning', lambda: general.query.filter(
        general.status_id == 1,
        general.due_service_date <= thirty_days,
        general.due_service_date > datetime.now(),
    ).count(), model_name='general_labware')

    alerts['general_labware_danger'] = set_cache('general_labware_danger', lambda: general.query.filter(
        general.status_id == 1,
        general.due_service_date <= datetime.today()
    ).count(), model_name='general_labware')

    alerts['histology_equipment_warning'] = set_cache('histology_equipment_warning', lambda: histo.query.filter(
        histo.status_id == 1,
        histo.due_service_date <= thirty_days,
        histo.due_service_date > datetime.now(),
    ).count(), model_name='histology_equipment')

    alerts['histology_equipment_danger'] = set_cache('histology_equipment_danger', lambda: histo.query.filter(
        histo.status_id == 1,
        histo.due_service_date <= datetime.today()
    ).count(), model_name='histology_equipment')

    alerts['instruments_warning'] = set_cache('instruments_warning', lambda: inst.query.filter(
        inst.status_id == 1,
        inst.due_service_date <= thirty_days,
        inst.due_service_date > datetime.now(),
    ).count(), model_name='instruments')

    alerts['instruments_danger'] = set_cache('instruments_danger', lambda: inst.query.filter(
        inst.status_id == 1,
        inst.due_service_date <= datetime.today()
    ).count(), model_name='instruments')

    alerts['cooled_storage_warning'] = set_cache('cooled_storage_warning', lambda: cooled.query.filter(
        cooled.status_id == 1,
        cooled.due_service_date <= thirty_days,
        cooled.due_service_date > datetime.now(),
    ).count(), model_name='cooled_storage')

    alerts['cooled_storage_danger'] = set_cache('cooled_storage_danger', lambda: cooled.query.filter(
        cooled.status_id == 1,
        cooled.due_service_date <= datetime.today()
    ).count(), model_name='cooled_storage')

    alerts['probes_warning'] = set_cache('probes_warning', lambda: probes.query.filter(
        probes.status_id == 1,
        probes.due_service_date <= thirty_days,
        probes.due_service_date > datetime.now(),
    ).count(), model_name='probes')

    alerts['probes_danger'] = set_cache('probes_danger', lambda: probes.query.filter(
        probes.status_id == 1,
        probes.due_service_date <= datetime.today()
    ).count(), model_name='probes')

    alerts['fume_hoods_warning'] = set_cache('fume_hoods_warning', lambda: hoods.query.filter(
        hoods.status_id == 1,
        hoods.due_service_date <= thirty_days,
        hoods.due_service_date > datetime.now(),
    ).count(), model_name='fume_hoods')

    alerts['fume_hoods_danger'] = set_cache('fume_hoods_danger', lambda: hoods.query.filter(
        hoods.status_id == 1,
        hoods.due_service_date <= datetime.today()
    ).count(), model_name='fume_hoods')

    alerts['reports_normal'] = set_cache('reports_normal', lambda: reports.query.filter(
        reports.report_status.in_(['Ready for CR', 'Ready for DR']),
        reports.db_status != 'Removed'
    ).count(), model_name='reports')

    alerts['litigation_packets_normal'] = set_cache('litigation_packets_normal', lambda: packets.query.filter(
        packets.packet_status.in_(['Ready for PP', 'Ready for PR'])
    ).count())

    # Requests
    now           = datetime.now()
    lower_bound   = now + timedelta(days=2)
    upper_bound   = now + timedelta(days=30)
    one_day = now + timedelta(days=1)

    alerts['requests_normal'] = set_cache('requests_normal',
                                          lambda: requests.query.filter(requests.status != 'Finalized').count())
    
    alerts['requests_warning'] = set_cache('requests_warning',
                                            lambda: requests.query.filter(
                                                requests.request_type_id == 4,
                                                requests.status != 'Finalized',
                                                # due_date between now+2 days and now+30 days
                                                requests.due_date  >= lower_bound,
                                                requests.due_date  <= upper_bound,
                                            ).count())
    
    alerts['requests_danger'] = set_cache('requests_danger', 
                                          lambda: requests.query.filter(
                                              requests.request_type_id == 4,
                                              requests.status != 'Finalized',
                                              requests.due_date  <= one_day
                                          ).count())

    # Batches
    batches = models['batches']
    alerts['batches_normal'] = set_cache('batches_normal',
                                         lambda: batches.query.filter(batches.batch_status == 'Processing').count(),
                                         'batches')
    
    alerts['standards_and_solutions_warning'] = set_cache('standards_and_solutions_warning', lambda: standards_and_solutions.query.filter(
        standards_and_solutions.in_use == 1,
        standards_and_solutions.retest_date <= thirty_days,
        standards_and_solutions.retest_date > datetime.now(),
    ).count(), model_name='standards_and_solutions')

    alerts['standards_and_solutions_danger'] = set_cache('standards_and_solutions_danger', lambda: standards_and_solutions.query.filter(
        standards_and_solutions.in_use == 1,
        standards_and_solutions.retest_date <= datetime.today()
    ).count(), model_name='standards_and_solutions')

    alerts['solvents_and_reagents_warning'] = set_cache('solvents_and_reagents_warning', lambda: solvents_and_reagents.query.filter(
        solvents_and_reagents.in_use == 1,
        solvents_and_reagents.exp_date <= thirty_days,
        solvents_and_reagents.exp_date > datetime.now(),
    ).count(), model_name='solvents_and_reagents')

    alerts['solvents_and_reagents_danger'] = set_cache('solvents_and_reagents_danger', lambda: solvents_and_reagents.query.filter(
        solvents_and_reagents.in_use == 1,
        solvents_and_reagents.exp_date <= datetime.today()
    ).count(), model_name='solvents_and_reagents')

    cache.set('locked', False, timeout=300)

    return alerts
