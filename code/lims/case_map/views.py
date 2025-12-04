# Application Imports
import time

from flask import request, Blueprint, render_template
from flask_login import login_required, current_user
from lims.models import Cases, Results, Components, Records, Zipcodes
from lims.case_map.forms import MODFilter, ComponentFilter
import folium
from lims import db
from folium.plugins import MarkerCluster
import numpy as np
import sqlalchemy as sa
from sqlalchemy import func, distinct
from sqlalchemy.dialects.postgresql import array_agg
from datetime import datetime
import datetime as dt
import os
from sqlalchemy.sql import text

from jinja2 import Template
# Set item variables

case_map = Blueprint('case_map', __name__)

colors = [
    'red',
    'blue',
    'gray',
    'darkred',
    'lightred',
    'orange',
    'beige',
    'green',
    'darkgreen',
    'lightgreen',
    'darkblue',
    'lightblue',
    'purple',
    'darkpurple',
    'pink',
    'cadetblue',
    'lightgray',
    'black'
]


@case_map.route(f'/case_map', methods=['GET', 'POST'])
@login_required
def map():

    ### 837 MS

    start = datetime.now()

    form = MODFilter()

    component_ids = [x[0] for x in db.session.query(Results).with_entities(Results.component_id).distinct().all()]
    form.component.choices = [(item.id, item.name) for item in Components.query.filter(Components.id.in_(component_ids)).order_by(Components.name.asc()).all()]

    #component_ids = [(item.id, item.name) for item in Components.query.all()]
    #form.component.choices = component_ids
    form.component.choices.insert(0, (0, 'Any'))

    component_dict = {item.id: item.name for item in Components.query.all()}
    zip_dict = {item.zipcode: item.neighborhood for item in Zipcodes.query.all()}
    start_date = datetime.today()-dt.timedelta(days=30)
    end_date = datetime.today()
    mod_select = 'All'
    component = ""
    component_name = ""
    case_number = ""
    case_id = request.args.get('case_id')
    error = ""
    component_name = 'Any'
    mod_dict = {}

    color_dict = {'Homicide': 'red',
                  'Suicide': 'purple',
                  'Accident': 'green',
                  'Natural': 'black',
                  'Natural-': 'black',
                  'Undetermined': 'gray',
                  None: 'blue'
                  }

    sa_filter = sa.and_(Cases.latitude.is_not(None),
                        Cases.date_of_incident >= start_date,
                        Cases.date_of_incident <= end_date)

    sf_map = folium.Map(location=['37.7550694', '-122.442887'],
                        zoom_start=12,
                        tiles='cartodbpositron'
                        )

    if form.is_submitted():
        mod_dict = {}
        case_number = form.case_number.data
        start_date = form.start_date.data
        end_date = form.end_date.data
        mod_select = form.mod.data
        component = form.component.data

        print(mod_select)
        print(start_date)
        print(end_date)
        print(component)
        print(case_number)

        if component != 0:
            component_name = component_dict[component]


        if case_number:

            case_id = db.session.query(Cases).filter(Cases.case_number == case_number).first().id
            case = Cases.query.get(case_id)
            items = Cases.query.join(Results).join(Components).filter(Cases.id == case_id)
            case_lst = [case_id]
            item = items.first()
            form.mod.data = "All"
            manner_of_death = "Not Listed"
            if not case.manner_of_death:
                manner_of_death = case.manner_of_death
            mods = [manner_of_death]
            mod_dict = {manner_of_death: color_dict[manner_of_death]}
            form.component.data = 0
            n_cases = 1

            if case is not None:
                if case.latitude is not None:

                    sf_map = folium.Map(location=[case.latitude, case.longitude],
                                        zoom_start=15,
                                        tiles='cartodbpositron'
                                        )
                else:
                    error = f"Coordinates could not be determined from death address: {case.death_address}"

            else:
                error = f"Uh-oh! Looks like {case_number} does not exist in FLDB :("

        else:

            if mod_select == 'All':

                lst = db.session.query(Cases).filter(sa.and_(Cases.latitude.is_not(None),
                                                                                       Cases.date_of_incident >= start_date,
                                                                                       Cases.date_of_incident <= end_date))
                case_ids = [case.id for case in lst]


                # case_ids = [case.id for case in db.session.query(Cases).filter(sa.and_(Cases.latitude.is_not(None),
                #                                                                        Cases.date_of_incident >= start_date,
                #                                                                        Cases.date_of_incident <= end_date))]

                if component == 0:

                    results = db.session.query(Results).filter(Results.case_id.in_(case_ids))

                    # items = results.join(Cases).join(Components)

                    # items = Cases.query.outerjoin(Results).join(Components).filter(sa.and_(Cases.latitude.is_not(None),
                    #                                    Cases.date_of_incident >= start_date,
                    #                                    Cases.date_of_incident <= end_date))

                elif component != 0:
                    # items = Cases.query.outerjoin(Results).join(Components).filter(sa.and_(Cases.latitude.is_not(None),
                    #                                                                    Cases.date_of_incident >= start_date,
                    #                                                                    Cases.date_of_incident <= end_date,
                    #                                                                    Results.component_id.is_(component)))

                    results = db.session.query(Results).filter(sa.and_(Results.case_id.in_(case_ids),
                                                                       Results.component_id.is_(component)))


                #items = results.outerjoin(Cases).join(Components)
                items = lst.outerjoin(Results).outerjoin(Components)
                #mods = [x[0] for x in items.with_entities(distinct(Cases.manner_of_death))]



            elif (mod_select != 'All') and (component != 0):

                mod_dict.update({mod_select: color_dict[mod_select]})
                # items = Cases.query.outerjoin(Results).join(Components).filter(sa.and_(Cases.latitude.is_not(None),
                #                                                                    Cases.date_of_incident >= start_date,
                #                                                                    Cases.date_of_incident <= end_date,
                #                                                                    Cases.manner_of_death.is_(mod),
                #                                                                    Results.component_id.is_(component)
                #                                                                     ))
                lst = db.session.query(Cases).filter(sa.and_(Cases.latitude.is_not(None),
                                                                                       Cases.date_of_incident >= start_date,
                                                                                       Cases.date_of_incident <= end_date),
                                                                                       Cases.manner_of_death.is_(mod_select))
                case_ids = [case.id for case in lst]


                results = db.session.query(Results).filter(sa.and_(Results.case_id.in_(case_ids),
                                                                   Results.component_id.is_(component)))
                items = results.join(Cases).join(Components)
                #mods = [x[0] for x in items.with_entities(Cases.manner_of_death).distinct()]

            else:
                print(mod_select)
                mod_dict.update({mod_select: color_dict[mod_select]})
                # items = Cases.query.outerjoin(Results).join(Components).filter(sa.and_(Cases.latitude.is_not(None),
                #                                    Cases.date_of_incident >= start_date,
                #                                    Cases.date_of_incident <= end_date,
                #                                    Cases.manner_of_death.is_(mod)))

                items = db.session.query(Cases).filter(sa.and_(Cases.latitude.is_not(None),
                                                                                       Cases.date_of_incident >= start_date,
                                                                                       Cases.date_of_incident <= end_date),
                                                                                       Cases.manner_of_death.is_(mod_select))
                case_ids = [case.id for case in items]
                case_lst = case_ids
                print(case_ids)

                results = items.join(Results)#.filter(Results.case_id.in_(case_ids))
                results = results.join(Components)


            mods = []
            for case in items:
                mod = case.manner_of_death
                # if not mod:
                #     mod = 'Not Listed'
                if mod not in mods:
                    mods.append(mod)

            for x in mods:
                mod_dict[x] = color_dict[x]

            print(mod_dict)
            if len(case_ids) == 0:
                error = "Uh-oh! Looks like there are no cases which match these criteria :("
            #     n_cases = len(case_ids)
            # else:
            #     n_cases = len(case_ids)

        # case_lst = [x[0] for x in items.with_entities(Cases.id).group_by(Cases.id).distinct()]
        #
        # counts = Cases.query.filter(Cases.id.in_(case_lst)). \
        #     with_entities(Cases.manner_of_death, sa.func.count(Cases.manner_of_death)). \
        #     group_by(Cases.manner_of_death).all()
        #
        # counts = {x[0]: x[1] for x in counts}
        # counts = {k: v for k, v in sorted(counts.items(), key=lambda item: item[1], reverse=True)}
        #
        # zips = Cases.query.filter(Cases.id.in_(case_lst)). \
        #     with_entities(Cases.death_zip, sa.func.count(Cases.death_zip)). \
        #     group_by(Cases.death_zip).all()
        #
        # zips = {(x[0].split('.')[0] if x[0] != '' else 'Not Listed'): (x[1] if x[0] != '' else x[1]) for x
        #         in zips}
        # zips = {k: v for k, v in sorted(zips.items(), key=lambda item: item[1], reverse=True)}
        #
        # premises = Cases.query.filter(Cases.id.in_(case_lst)). \
        #     with_entities(Cases.death_premises, sa.func.count(Cases.death_premises)). \
        #     group_by(Cases.death_premises).all()
        #
        # premises = {x[0]: x[1] for x in premises}
        # premises = {k: v for k, v in sorted(premises.items(), key=lambda item: item[1], reverse=True)}
        #
        # unique_components = [x for x in items.with_entities(Results.component_id).distinct()]
        # component_counts = {}
        # for x in unique_components:
        #     component_counts[component_dict[x[0]]] = len(
        #         items.filter(Results.component_id == x[0]).with_entities(Cases.id).distinct().all())
        #
        # component_counts = {k: v for k, v in sorted(component_counts.items(), key=lambda item: item[1], reverse=True)}
        #
        form.case_number.data = ""

    else:
        print(case_id)
        if case_id is not None:
            case = Cases.query.get(case_id)
            lst = db.session.query(Cases).filter(Cases.id == case_id)
            if case.latitude is not None:
                sf_map = folium.Map(location=[case.latitude, case.longitude],
                                    zoom_start=15,
                                    tiles='cartodbpositron'
                                    )
        else:
            lst = db.session.query(Cases).filter(sa_filter)
        case_ids = [case.id for case in lst]
        # results = db.session.query(Results).filter(Results.case_id.in_(case_ids))
        # # items = results.join(Cases).join(Components)
        items = lst
        mods = set([case.manner_of_death for case in lst])# if case.manner_of_death])
        for x in mods:
            mod_dict[x] = color_dict[x]

    print(mod_dict)
    # From form submit 1553 MS
    print(f"From start: {datetime.now() - start}")

    start = datetime.now()
    ### THIS LINE IS SLOW - 2,500 MS
    case_lst = [x[0] for x in items.with_entities(distinct(Cases.id))]
    n_cases = len(case_lst)
    print(f"Unique case_ids with results: {datetime.now() - start}")

    start = datetime.now()
    cases = Cases.query.filter(Cases.id.in_(case_lst))
    last_case = Cases.query.order_by(Cases.date_of_incident.desc()).first()
    print(last_case)

    # for case in cases:
    #     if not case.manner_of_death:
    #         case.manner_of_death = 'Not Listed'
    counts = cases.filter(Cases.id.in_(case_lst)) \
              .with_entities(Cases.manner_of_death, sa.func.count(Cases.manner_of_death)) \
              .group_by(Cases.manner_of_death)

    counts = {x[0]: x[1] for x in counts}
    print(counts)
    counts = {k: v for k, v in sorted(counts.items(), key=lambda item: item[1], reverse=True) }

    zips = Cases.query.filter(Cases.id.in_(case_lst)). \
        with_entities(Cases.death_zip, sa.func.count(Cases.death_zip)). \
        group_by(Cases.death_zip)

    # zip = {}
    # zips = {(x[0].split('.')[0] if x[0] != '' else 'Not Listed'): (x[1] if x[0] != '' else x[1]) for x in zips}
    # zips = {(x[0].split('.')[0] if x[0] != '' else 'Not Listed'): (x[1] if x[0] != '' else x[1]) for x in zips}
    # zips = {k: v for k, v in sorted(zips.items(), key=lambda item: item[1], reverse=True)}

    premises = Cases.query.filter(Cases.id.in_(case_lst)). \
        with_entities(Cases.death_premises, sa.func.count(Cases.death_premises)). \
        group_by(Cases.death_premises)

    premises = {x[0]: x[1] for x in premises}
    premises = {k: v for k, v in sorted(premises.items(), key=lambda item: item[1], reverse=True)}


    # unique_components = [x for x in
    #                      items.with_entities(Results.component_id).distinct()]
    #
    # component_counts = {}
    # for x in unique_components:
    #
    #     if component_dict[x[0]] not in ['Ethanol','Methanol','Isopropanol','Acetone', 'ND', 'TBR', 'NT']:
    #         start = datetime.now()
    #         component_counts[component_dict[x[0]]] = items.filter(Results.component_id == x[0]).with_entities(
    #                distinct(Cases.id))
    #         #print(component_counts[component_dict[x[0]]])
    #         #print(datetime.now() - start)

    results = db.session.query(Results).filter(Results.case_id.in_(case_ids))
    items = results.join(Cases).join(Components)
    component_counts = items.with_entities(Results.component_id, sa.func.count(distinct(Cases.id))).\
                group_by(Components.id).all()

    # result_case_ids = [result.case.id for result in results]
    # print('Result Case IDS', len(set(result_case_ids)))
    #### THIS LINE IS SLOW - 3,300 MS

    count_start = datetime.now()

    component_counts = {component_dict[x[0]]: x[1] for x in component_counts}

    print(f"Component counts: {datetime.now() - count_start}")


    ####


    component_counts = {k: v for  k, v in sorted(component_counts.items(), key=lambda item: item[1], reverse=True)
                        if k not in ['Ethanol', 'Methanol', 'Acetone', 'Isopropanol', 'ND', 'NT']}



    folium.TileLayer('cartodbpositron').add_to(sf_map)
    folium.TileLayer('openstreetmap').add_to(sf_map)
    marker_cluster = MarkerCluster(control=False, spiderfyDistanceMultiplier=1.5).add_to(sf_map)

    print(f"Get counts: {datetime.now() - start}")
    start = datetime.now()
    # for each coordinate, create circlemarker of user percent

    # for idx, item in enumerate(items):
    #     if item.latitude is not None:
    #         manner_of_death = "Not Listed"
    #         if item.manner_of_death != "":
    #             manner_of_death = item.manner_of_death
    #
    #         if item.death_zip == "":
    #             neighborhood = 'Not Listed'
    #         else:
    #             neighborhood = zip_dict[item.death_zip.split('.')[0]]
    #         html = f"<p style='font-family:calibri;'>" \
    #                f"<strong><a href='http://{request.host}/cases/{item.id}' target='_blank'>{item.case_number}</a></strong><br>" \
    #                f"<strong>Name</strong>: {item.last_name} {item.first_name}<br>" \
    #                f"<strong>Date of Death</strong>: {item.date_of_incident.strftime('%m/%d/%Y')}<br>" \
    #                f"<strong>Death Address</strong>: {item.death_address}<br>" \
    #                f"<strong>Death ZIP</strong>: {item.death_zip.split('.')[0]}<br>" \
    #                f"<strong>Neighborhood</strong>: {neighborhood}<br>"\
    #                f"<strong>Premises type</strong>: {item.death_premises}<br>" \
    #                f"<strong>MOD</strong>: {manner_of_death}<br>" \
    #                f"<strong>COD</strong>: {item.cod_a}<br>"\
    #                f"<strong>Case Comments</strong>: {item.fa_case_comments}<br>"\
    #                f"<br>" \
    #
    #         reports = Reports.query.filter_by(case_id=item.id).all()
    #         if len(reports) > 0:
    #             html += f"<strong>Reports (if available)</strong><br>"
    #         for report in reports:
    #             if f"{report.report_name}.pdf" in os.listdir(
    #                     fr"F:\ForensicLab\LIMS\sfocme_LIMS\code\lims\static\reports"):
    #                 html += f"<a href='http://{request.host}/static/reports/{report.report_name}.pdf' target='_blank'>{report.report_name}</a><br>"
    #         html += "<br></p>"
    #
    #         iframe = folium.IFrame(html, height=300)
    #         popup = folium.Popup(iframe, min_width=400, max_width=500)
    #         lat = item.latitude
    #         long = item.longitude
    #         radius = 7
    #         folium.CircleMarker(location=[lat, long],
    #                             radius=radius,
    #                             popup=popup,
    #                             color=color_dict[item.manner_of_death],
    #                             fill=True).add_to(marker_cluster)
    #
    #         # folium.CircleMarker(location=[lat, long],
    #         #                    radius=radius,
    #         #                    popup=popup,
    #         #                    color=color_dict[item.manner_of_death],
    #         #                    fill=True).add_to(sf_map)
    #
    #
    # lgd_txt = '<span style="color:{col};">{txt}</span>'
    #
    # for k, v in mod_dict.items():  # color choice is limited
    #     if k == "":
    #         k = 'Not Listed'
    #     fg = folium.FeatureGroup(name=lgd_txt.format(txt=k, col=v))
    #     sf_map.add_child(fg)
    #
    # folium.LayerControl(collapsed=False).add_to(sf_map)


    ### 2225 MS

    lgd_txt = '<span style="color:{col};">{txt}</span>'
    for mod in mods:

        print(mod)
        #mod_cases = items.filter(Cases.manner_of_death == mod)


        mod_cases = db.session.query(Cases).filter(sa.and_(Cases.manner_of_death == mod,
                                                Cases.id.in_(case_lst)))

        print(mod_cases.count())
        if not mod:
            txt = 'Not Listed'
        else:
            txt = mod
        subg = folium.plugins.FeatureGroupSubGroup(marker_cluster,
                                                   name=lgd_txt.format(txt=txt, col=mod_dict[mod]))
        for item in mod_cases:

            if item.latitude is not None:
                manner_of_death = "Not Listed"
                if item.manner_of_death != "":
                    manner_of_death = item.manner_of_death

                neighborhood = ""
                # if item.death_zip == "":
                #     neighborhood = 'Not Listed'
                # else:
                #     try:
                #         neighborhood = zip_dict[item.death_zip.split('.')[0]]
                #     except:
                #         neighborhood = item.death_zip.split('.')[0]
                html = f"<p style='font-family:calibri;'>" \
                       f"<strong><a href='http://{request.host}/cases/{item.id}' target='_blank'>{item.case_number}</a></strong><br>" \
                       f"<strong>Name</strong>: {item.last_name}, {item.first_name}<br>" \
                       f"<strong>Date of Death</strong>: {item.date_of_incident.strftime('%m/%d/%Y')}<br>" \
                       f"<strong>Death Address</strong>: {item.death_address}<br>" \
                       f"<strong>Death ZIP</strong>:<br>" \
                       f"<strong>Neighborhood</strong>: {neighborhood}<br>"\
                       f"<strong>Premises type</strong>: {item.death_premises}<br>" \
                       f"<strong>MOD</strong>: {manner_of_death}<br>" \
                       f"<strong>COD</strong>: {item.cod_a}<br>"\
                       f"<strong>Case Comments</strong>: {item.fa_case_comments}<br>"\
                       f"<br>" \

                reports = db.session.query(Records).filter(Records.case_id == item.id).all()
                if len(reports) > 0:
                    html += f"<strong>Reports (if available)</strong><br>"
                # for report in reports:
                #     if f"{report.report_name}.pdf" in os.listdir(
                #             fr"F:\ForensicLab\LIMS\sfocme_LIMS\code\lims\static\reports"):
                #         html += f"<a href='http://{request.host}/static/reports/{report.report_name}.pdf' target='_blank'>{report.report_name}</a><br>"
                html += "<br></p>"

                iframe = folium.IFrame(html, height=300)
                popup = folium.Popup(iframe, min_width=400, max_width=500)
                lat = item.latitude
                long = item.longitude
                radius = 7
                folium.CircleMarker(location=[lat, long],
                                    radius=radius,
                                    popup=popup,
                                    color=color_dict[item.manner_of_death],
                                    fill=True).add_to(subg)

                # folium.CircleMarker(location=[lat, long],
                #                    radius=radius,
                #                    popup=popup,
                #                    color=color_dict[item.manner_of_death],
                #                    fill=True).add_to(sf_map)



            sf_map.add_child(subg)



    folium.LayerControl(collapsed=False).add_to(sf_map)

    sf_map.get_root().width = "1400px"
    sf_map.get_root().height = "850px"
    map = sf_map.get_root()._repr_html_()

    start_date = start_date.strftime('%m/%d/%Y')
    end_date = end_date.strftime('%m/%d/%Y')

    print(f"{current_user.initials} opened the Case Map - {datetime.now()}")
    print(f"Generate map: {datetime.now()-start}")
    return render_template('case_map.html', form=form, map=map,
                           start_date=start_date, end_date=end_date, case_number=case_number,
                           mod=mod_select, component_name=component_name, n_cases=n_cases, error=error,
                           counts=counts, zips=zips, zip_dict=zip_dict, premises=premises,
                           component_counts=component_counts,
                           cases=cases, last_case=last_case)

