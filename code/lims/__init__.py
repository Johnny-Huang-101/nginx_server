import os
import csv
from datetime import timedelta, datetime, date
import time

# Flask Imports
from flask import Flask, render_template, session, request, g
from flask_login import LoginManager, current_user
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from lims.config import get_config
from lims.alerts import get_alerts
from win32com.client import Dispatch
from flask_caching import Cache
from cryptography.fernet import Fernet

SSN_ENCRYPTION_KEY = 'YC_s85YpwXpI3URcsxDOTxKqXh0CLaYG784VFJmCVtU='

fernet = Fernet(SSN_ENCRYPTION_KEY.encode())

app = Flask(__name__)
app.config['CACHE_TYPE'] = 'RedisCache'
app.config['CACHE_REDIS_HOST'] = 'localhost'
app.config['CACHE_REDIS_PORT'] = 6379
cache = Cache(app)

### Displayed in the bottom-left of the screen ###

# Initialize printing information on app start/restart
global_context = {'printer_com': Dispatch('Dymo.DymoAddIn')}

# Version parameters
major = 2
minor = 2
patch = 12

developer = "Office of the Chief Medical Examiner"
year = datetime.now().year

app.config['VERSION'] = f"v{major}.{minor}.{patch} {developer}, {year}"

# Can use this to do certain things to data prior/after to implementation date for historical data.
app.config['IMPLEMENTATION_DATE'] = date(2025, 1, 1)
##################################################

# # if true it will show the Werkzeug traceback, else it will show an generic Internal Server Error (500) will be shown
app.debug = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # This is how long before the session times out.
app.config['SECRET_KEY'] = 'mysecret'

# Set the logger to only show error level logs in the console
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

# Configure the SQLALCHEMY_DATABASE_URI from config.py
get_config(app)

# Instantiate LoginManager and define login route e.g. users.login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'users.login'

# Configure and create instance of SQLAlchemy
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False

# Create instance of FlaskMigrate
migrate = Migrate()
migrate.init_app(app, db, render_as_batch=True)

# Create instance of FlaskMail
mail = Mail()
mail.init_app(app)

# Create instance of DebugToolbar
# toolbar = DebugToolbarExtension()
# toolbar.init_app(app)
# app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

# Create instance of FlaskSession
# sess = Session()
# sess.init_app(app)
# app.config['SESSION_TYPE'] = 'filesystem'

# Create instance of Flask Cache
# cache = Cache(app)
# app.config['CACHE_TYPE'] = 'SimpleCache'


# This is the file system folder for the LIMS
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['FILE_SYSTEM'] = os.path.join(basedir, 'static', 'filesystem')
app.app_context().push()  # allows access to the current_app
# app.config['FILE_SYSTEM'] = os.path.join(current_app.root_path, 'static', 'filesystem')
#
from lims.models import CurrentSystemDisplay

app.config['SYSTEM_NAME'] = None
app.config['SYSTEM_WELCOME'] = None
app.config['ICON_IMG'] = None
app.config['LOGO_IMG'] = None
app.config['BACKGROUND_IMG'] = None
app.config['OVERLAY_IMG'] = None
with app.app_context():
    if CurrentSystemDisplay.query.get(1):
        if CurrentSystemDisplay.query.get(1).db_names:
            app.config['SYSTEM_NAME'] = CurrentSystemDisplay.query.get(1).db_names.message

        if CurrentSystemDisplay.query.get(1).welcome_messages:
            app.config['SYSTEM_WELCOME'] = CurrentSystemDisplay.query.get(1).welcome_messages.message

        if hasattr(CurrentSystemDisplay, 'icon'):
            icon_image = CurrentSystemDisplay.query.get(1).icon
            if icon_image:
                # icon_image = icon_image.image_file
                app.config['ICON_IMG'] = '/static/filesystem/current_system_display/icon.png'

            logo_image = CurrentSystemDisplay.query.get(1).logo
            if logo_image:
                # logo_image = logo_image.image_file
                app.config['LOGO_IMG'] = '/static/filesystem/current_system_display/logo.png'

            bg_img = CurrentSystemDisplay.query.get(1).background
            if bg_img:
                # bg_img = bg_img.image_file
                app.config['BACKGROUND_IMG'] = '/static/filesystem/current_system_display/background.png'

            overlay_img = CurrentSystemDisplay.query.get(1).overlay
            if overlay_img:
                # welcome_img = overlay_img.image_file
                app.config['OVERLAY_IMG'] = '/static/filesystem/current_system_display/overlay.png'


# Error handlers
@app.errorhandler(403)
def incorrect_permissions(error):
    return render_template('/error_pages/403.html'), 403


@app.errorhandler(404)
def not_found(error):
    return render_template('/error_pages/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('/error_pages/500.html'), 500


# # Configure logging
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# from sqlalchemy import event
# from sqlalchemy.pool import Pool
# @event.listens_for(Pool, "checkout")
# def checkout_listener(dbapi_conn, conn_record, conn_proxy):
#     print("Connection checked out")

# @event.listens_for(Pool, "checkin")
# def checkin_listener(dbapi_conn, conn_record):
#     print("Connection returned")

# def log_step(desc, start):
#     print(f"\033[1;36m{desc} took {(time.perf_counter() - start)*1000} ms\033[0m")

# Request handlers
@app.before_request
def before_request():
    """
    Before each request, check all tables in the database and count the number of items
    that are pending and locked. This number is used to add the bubbles with the number
    of action (pending and locked) items next to sidebar items.
    """
    # greceived = time.perf_counter()
    if "static" in request.path:
        return

    redis_backend = cache.cache
    r = redis_backend._read_client
    prefix = redis_backend.key_prefix or ''

    # Init session key
    if 'pending_case_id' not in session.keys():
        session['pending_case_id'] = None

    if len(request.path.split('/')) <= 3:
        # print(f"\033[1;34m Path: {request.path}\033[0m")

        session['VERSION'] = app.config['VERSION']

        locked = cache.get('locked') if cache.get('locked') is not None else None

        if locked is None or not locked:
            g.module_alerts = get_alerts(app)
            # log_step("get_alerts(app)", greceived)
        else:
            alerts = {}
            for full_key in r.scan_iter(f'{prefix}*'):
                key = full_key.decode()[len(prefix):]
                val = cache.get(key)
                if val != 0:
                    try:
                        alerts[key] = val
                    except (KeyError, TypeError) as e:
                        alerts = []

            g.module_alerts = alerts

    else:
        try:
            if g.module_alerts is None:
                g.module_alerts = []
            else:
                pass
        except (KeyError, AttributeError):
            g.module_alerts = []

        # log_step("Fallback session['module_alerts'] logic", greceived)

    # log_step("Before request processing", start)

    return


@app.context_processor
def inject_module_alerts():
    # make available in all templates as `module_alerts`
    return {"module_alerts": getattr(g, "module_alerts", [])}


@app.after_request
def after_request(response):
    """
    After every request:
    1. set the case_search_error value to "", this will clear any errors
       from underneath the search error bar
    2. This will prevent any modal popups after searching for a pending case.

    Prevents reloading form when back is clicked.

    Parameters
    -------
    response


    """
    if "static" in request.path:
        if request.path.endswith(".js") or request.path.endswith(".png"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
            return response
        return response

    # start = time.perf_counter()

    # Create models for user_log
    models = {}
    for cls in app.extensions['sqlalchemy'].db.Model.registry.mappers:
        table = cls.class_
        name = table.__tablename__
        models[name] = table

    if response.status_code == 200:
        if current_user.is_authenticated:
            # if 'case_search_error' in session.keys():
            if session['case_search_error'] != "":
                session['case_search_error'] = ""
            # if 'case_pending' in session.keys():
            if session['case_pending']:
                session['case_pending'] = False

    # Prevent back button onto form
    # response.cache_control.no_store = True
    response.headers["Cache-Control"] = "no-cache, no-store, post-check=0, pre-check=0"

    # Set user log to model
    user_log = models['user_log']
    # Record user if user is signed in, doesn't record users on login page, not logged in
    try:
        user = current_user.initials
    except AttributeError:
        user = None

    # Get the path, view_function and date user is accessing page
    route = request.path
    view_function = request.endpoint
    # date_accessed = datetime.now()

    # Ignore requests to static folder
    if 'static' in route.split('/'):
        pass
    # If user is assigned, update field_data
    elif user is not None:
        field_data = {
            'user': user,
            'route': route,
            'view_function': view_function,
            'date_accessed': datetime.now()
        }
        # Add entry to user_log table
        item = user_log(**field_data)
        db.session.add(item)
        db.session.commit()
    else:
        pass

    # log_step("After request processing", start)
    return response


# def admin_only(func):
#     def wrapper():
#         if current_user.permissions not in ['Admin', 'Owner']:
#             return abort(403)
#         else:
#             return func
#     return wrapper


# Used to display resource location
# Can also be used for getattr() needs in jinja templating - TLD
@app.template_filter('getattr')
def getattr_filter(obj, attr):
    return getattr(obj, attr)


@app.template_filter('hasattr')
def hasattr_filter(obj, attr):
    return hasattr(obj, attr)


app.jinja_env.filters['getattr'] = getattr_filter
app.jinja_env.filters['hasattr'] = hasattr_filter
app.jinja_env.globals.update(zip=zip)
app.jinja_env.globals.update(datetime=datetime)

# Import and register blueprints

from lims.agencies.views import blueprint as agencies
from lims.assay_constituents.views import blueprint as assay_constituents
from lims.assays.views import blueprint as assays
from lims.attachment_types.views import blueprint as attachment_types
from lims.attachments.views import blueprint as attachments
from lims.autopsy_view_buttons.views import blueprint as autopsy_view_buttons
from lims.batch_comments.views import blueprint as batch_comments
from lims.batch_comments_reference.views import blueprint as batch_comments_reference
from lims.batch_constituents.views import blueprint as batch_constituents
from lims.batch_records.views import blueprint as batch_records
from lims.batch_templates.views import blueprint as batch_templates
from lims.batches.views import blueprint as batches
from lims.bench_types.views import blueprint as bench_types
from lims.benches.views import blueprint as benches
from lims.booking_changes.views import blueprint as booking_changes
from lims.booking_formats.views import blueprint as booking_formats
from lims.booking_information_provided.views import blueprint as booking_information_provided
from lims.booking_information_provider.views import blueprint as booking_information_provider
from lims.booking_locations.views import blueprint as booking_locations
from lims.booking_jurisdiction.views import blueprint as booking_jurisdiction
from lims.booking_purposes.views import blueprint as booking_purposes
from lims.booking_types.views import blueprint as booking_types
from lims.bookings.views import blueprint as bookings
from lims.cabinet_types.views import blueprint as cabinet_types
from lims.cabinets.views import blueprint as cabinets
from lims.calibrated_labware.views import blueprint as calibrated_labware
from lims.calibrated_labware_types.views import blueprint as calibrated_labware_types
from lims.case_map.views import case_map
from lims.case_types.views import blueprint as case_types
from lims.cases.views import blueprint as cases
from lims.comment_instances.views import blueprint as comment_instances
from lims.comments.views import blueprint as comments
from lims.compactors.views import blueprint as compactors
from lims.components.views import blueprint as components
from lims.compounds.views import blueprint as compounds
from lims.compounds_components_reference.views import blueprint as compounds_components_reference
from lims.container_types.views import blueprint as container_types
from lims.containers.views import blueprint as containers
from lims.cooled_storage.views import blueprint as cooled_storage
from lims.cooled_storage_types.views import blueprint as cooled_storage_types
from lims.core.views import core
from lims.current_assay_constituents.views import blueprint as current_assay_constituents
from lims.current_system_display.views import blueprint as current_system_display
from lims.dashboard.views import dashboard
from lims.ame_dashboard.views import ame_dashboard
from lims.default_assay_constituents.views import blueprint as default_assay_constituents
from lims.default_clients.views import blueprint as default_clients
from lims.disseminations.views import blueprint as disseminations
from lims.divisions.views import blueprint as divisions
from lims.drug_classes.views import blueprint as drug_classes
from lims.drug_monographs.views import blueprint as drug_monographs
from lims.drug_prevalence.views import drug_prevalence
from lims.evidence_comments.views import blueprint as evidence_comments
from lims.evidence_comments_reference.views import blueprint as evidence_comments_reference
from lims.evidence_lockers.views import blueprint as evidence_lockers
from lims.evidence_storage.views import blueprint as evidence_storage
from lims.evidence_storage_types.views import blueprint as evidence_storage_types
from lims.fa_personal_effects.views import blueprint as fa_personal_effects
from lims.fume_hoods.views import blueprint as fume_hoods
from lims.genders.views import blueprint as genders
from lims.general_labware.views import blueprint as general_labware
from lims.general_labware_types.views import blueprint as general_labware_types
from lims.histology_equipment.views import blueprint as histology_equipment
from lims.histology_equipment_types.views import blueprint as histology_equipment_types
from lims.hood_types.views import blueprint as hood_types
from lims.hubs.views import blueprint as hubs
from lims.instrument_types.views import blueprint as instrument_types
from lims.instruments.views import blueprint as instruments
from lims.lit_packet_admin_assays.views import blueprint as lit_packet_admin_assays
from lims.lit_packet_admin_attachments.views import blueprint as lit_packet_admin_attachments
from lims.lit_packet_admin_files.views import blueprint as lit_packet_admin_files
from lims.lit_packet_admin_templates.views import blueprint as lit_packet_admin_templates
from lims.lit_packet_admins.views import blueprint as lit_packet_admins
from lims.litigation_packet_templates.views import blueprint as litigation_packet_templates
from lims.litigation_packets.views import blueprint as litigation_packets
from lims.locations.views import blueprint as locations
from lims.modifications.views import blueprint as modifications
from lims.narratives.views import blueprint as narratives
from lims.personnel.views import blueprint as personnel
from lims.preservatives.views import blueprint as preservatives
from lims.probes.views import blueprint as probes
from lims.pt_cases.views import blueprint as pt_cases
from lims.pt_results.views import blueprint as pt_results
from lims.qr_reference.views import blueprint as qr_reference
from lims.races.views import blueprint as races
from lims.record_types.views import blueprint as record_types
from lims.records.views import blueprint as records
from lims.reference_material_solvents.views import blueprint as reference_material_solvents
from lims.reference_materials.views import blueprint as reference_materials
from lims.report_comments.views import blueprint as report_comments
from lims.report_results.views import blueprint as draft_results
from lims.report_templates.views import blueprint as report_templates
from lims.reports.views import blueprint as reports
from lims.results.views import blueprint as results
from lims.retention_policies.views import blueprint as retention_policies
from lims.requests.views import blueprint as requests
from lims.request_types.views import blueprint as request_types
from lims.rooms.views import blueprint as rooms
from lims.salts.views import blueprint as salts
from lims.sample_formats.views import blueprint as sample_formats
from lims.scope.views import blueprint as scope
from lims.sequence_constituents.views import blueprint as sequence_constituents
from lims.sequence_header_mappings.views import blueprint as sequence_header_mappings
from lims.service_types.views import blueprint as service_types
from lims.services.views import blueprint as services
from lims.solution_types.views import blueprint as solution_types
from lims.solvents_and_reagents.views import blueprint as solvents_and_reagents
from lims.specimen_audit.views import blueprint as specimen_audit
from lims.specimen_collection_container_types.views import blueprint as specimen_collection_container_types
from lims.specimen_collection_containers.views import blueprint as collection_containers
from lims.specimen_conditions.views import blueprint as specimen_conditions
from lims.specimen_types.views import blueprint as specimen_types
from lims.specimens.views import blueprint as specimens
from lims.standards_and_solutions.views import blueprint as standards_and_solutions
from lims.states_of_matter.views import blueprint as states_of_matter
from lims.statuses.views import blueprint as statuses
from lims.storage_temperatures.views import blueprint as storage_temperatures
from lims.storage_types.views import blueprint as storage_types
from lims.system_images.views import blueprint as system_images
from lims.system_messages.views import blueprint as system_messages
from lims.test_comments.views import blueprint as test_comments
from lims.tests.views import blueprint as tests
from lims.unit_types.views import blueprint as unit_types
from lims.united_states.views import blueprint as united_states
from lims.units.views import blueprint as units
from lims.user_log.views import blueprint as user_log
from lims.users.views import blueprint as users
from lims.zipcodes.views import blueprint as zipcodes
from lims.returns.views import blueprint as returns
from lims.qtus_ai_pipeline import blueprint as results_api


app.register_blueprint(agencies)
app.register_blueprint(ame_dashboard)
app.register_blueprint(assay_constituents)
app.register_blueprint(assays)
app.register_blueprint(attachment_types)
app.register_blueprint(attachments)
app.register_blueprint(autopsy_view_buttons)
app.register_blueprint(batch_comments)
app.register_blueprint(batch_comments_reference)
app.register_blueprint(batch_constituents)
app.register_blueprint(batch_records)
app.register_blueprint(batch_templates)
app.register_blueprint(batches)
app.register_blueprint(bench_types)
app.register_blueprint(benches)
app.register_blueprint(booking_changes)
app.register_blueprint(booking_formats)
app.register_blueprint(booking_information_provided)
app.register_blueprint(booking_information_provider)
app.register_blueprint(booking_locations)
app.register_blueprint(booking_jurisdiction)
app.register_blueprint(booking_purposes)
app.register_blueprint(booking_types)
app.register_blueprint(bookings)
app.register_blueprint(cabinet_types)
app.register_blueprint(cabinets)
app.register_blueprint(calibrated_labware)
app.register_blueprint(calibrated_labware_types)
app.register_blueprint(case_map)
app.register_blueprint(case_types)
app.register_blueprint(cases)
app.register_blueprint(collection_containers)
app.register_blueprint(comment_instances)
app.register_blueprint(comments)
app.register_blueprint(compactors)
app.register_blueprint(components)
app.register_blueprint(compounds)
app.register_blueprint(compounds_components_reference)
app.register_blueprint(container_types)
app.register_blueprint(containers)
app.register_blueprint(cooled_storage)
app.register_blueprint(cooled_storage_types)
app.register_blueprint(core)
app.register_blueprint(current_assay_constituents)
app.register_blueprint(current_system_display)
app.register_blueprint(dashboard)
app.register_blueprint(default_assay_constituents)
app.register_blueprint(default_clients)
app.register_blueprint(disseminations)
app.register_blueprint(divisions)
app.register_blueprint(draft_results)
app.register_blueprint(drug_classes)
app.register_blueprint(drug_monographs)
app.register_blueprint(drug_prevalence)
app.register_blueprint(evidence_comments)
app.register_blueprint(evidence_comments_reference)
app.register_blueprint(evidence_lockers)
app.register_blueprint(evidence_storage)
app.register_blueprint(evidence_storage_types)
app.register_blueprint(fa_personal_effects)
app.register_blueprint(fume_hoods)
app.register_blueprint(genders)
app.register_blueprint(general_labware)
app.register_blueprint(general_labware_types)
app.register_blueprint(histology_equipment)
app.register_blueprint(histology_equipment_types)
app.register_blueprint(hood_types)
app.register_blueprint(hubs)
app.register_blueprint(instrument_types)
app.register_blueprint(instruments)
app.register_blueprint(lit_packet_admins)
app.register_blueprint(lit_packet_admin_assays)
app.register_blueprint(lit_packet_admin_attachments)
app.register_blueprint(lit_packet_admin_files)
app.register_blueprint(lit_packet_admin_templates)
app.register_blueprint(litigation_packets)
app.register_blueprint(litigation_packet_templates)
app.register_blueprint(locations)
app.register_blueprint(modifications)
app.register_blueprint(narratives)
app.register_blueprint(personnel)
app.register_blueprint(preservatives)
app.register_blueprint(probes)
app.register_blueprint(pt_cases)
app.register_blueprint(pt_results)
app.register_blueprint(qr_reference)
app.register_blueprint(races)
app.register_blueprint(record_types)
app.register_blueprint(records)
app.register_blueprint(reference_material_solvents)
app.register_blueprint(reference_materials)
app.register_blueprint(report_comments)
app.register_blueprint(report_templates)
app.register_blueprint(reports)
app.register_blueprint(results)
app.register_blueprint(results_api)
app.register_blueprint(retention_policies)
app.register_blueprint(requests)
app.register_blueprint(request_types)
app.register_blueprint(rooms)
app.register_blueprint(salts)
app.register_blueprint(sample_formats)
app.register_blueprint(scope)
app.register_blueprint(sequence_constituents)
app.register_blueprint(sequence_header_mappings)
app.register_blueprint(service_types)
app.register_blueprint(services)
app.register_blueprint(solution_types)
app.register_blueprint(solvents_and_reagents)
app.register_blueprint(specimen_audit)
app.register_blueprint(specimen_collection_container_types)
app.register_blueprint(specimen_conditions)
app.register_blueprint(specimen_types)
app.register_blueprint(specimens)
app.register_blueprint(standards_and_solutions)
app.register_blueprint(states_of_matter)
app.register_blueprint(statuses)
app.register_blueprint(storage_temperatures)
app.register_blueprint(storage_types)
app.register_blueprint(system_images)
app.register_blueprint(system_messages)
app.register_blueprint(test_comments)
app.register_blueprint(tests)
app.register_blueprint(unit_types)
app.register_blueprint(united_states)
app.register_blueprint(units)
app.register_blueprint(user_log)
app.register_blueprint(users)
app.register_blueprint(zipcodes)
app.register_blueprint(returns)


# #### Initialize DB Name on restart ####
#
# name_reference = CurrentSystemDisplay.query.first()
# sys_name = [(item.id, item.message) for item in SystemMessages.query.filter_by(id=int(name_reference.db_name))]
# app.config['SYSTEM_NAME'] = sys_name[0][1]
#
# #### Initialize Welcome Message on restart ####
#
# message_reference = CurrentSystemDisplay.query.first()
# sys_welcome = [(item.id, item.message) for item in SystemMessages.query.filter_by(
#     id=int(message_reference.welcome_message))]
# app.config['SYSTEM_WELCOME'] = sys_welcome[0][1]


@app.context_processor
def inject_import_status():
    log_path = os.path.join(app.config['D_FILE_SYSTEM'], "Exports", "export-log.csv")
    minutes_since_import = 999

    try:
        with open(log_path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
            completed_times = [
                datetime.fromisoformat(row['LIMS_Completed'])
                for row in rows
                if row.get('LIMS_Completed')
            ]
            if completed_times:
                delta = datetime.now() - max(completed_times)
                minutes_since_import = round(delta.total_seconds() / 60)

    except Exception as e:
        print(f"⚠️ Failed to read FA export log: {e}")

    return {
        'minutes_since_import': minutes_since_import
    }
