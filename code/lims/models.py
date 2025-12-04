from lims import db, login_manager
from werkzeug.security import check_password_hash
from flask_login import UserMixin
from sqlalchemy.orm import DeclarativeBase, Query, scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base, as_declarative
from datetime import datetime
from sqlalchemy import UniqueConstraint, func
from flask_login import current_user
from abc import abstractmethod
from sqlalchemy import Enum
from sqlalchemy.types import TypeDecorator, LargeBinary
from lims import fernet

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(user_id)


# Create the declarative base
Base = declarative_base()

session = scoped_session(sessionmaker())


# Define the base template table class
class BaseTemplate(Base):
    """
    A set of columns which can be inherited by calling the BaseTemplate class when defining a table.

    Columns:
        id (int): the id assigned to the item in the table.
        db_status (str): the internal status of the item i.e., Approved, Pending, Pending with Active Changes.
        locked (bool): if the item is locked or not.
        revision (int): the revision number of the item.
        comments (str): the general comments for the item.
        communications (str): a field to store peer-to-peer comments if the approval process is used. Deletes on approval
        delete_reason (str): the reason an item was removed.
        create_date (datetime): the date the item was created.
        created_by (str): initials of the user who created the item.
        modify_date (datetime): the date the item was modified.
        modified_by (str): the initials of the user who modified the item.
        lock_date (datetime): the date the item was locked.
        locked_by (str): the initials of the user who locked the item.
    """

    __abstract__ = True  # Indicates that this is an abstract base class

    id = db.Column(db.Integer, primary_key=True)
    db_status = db.Column(db.String(32))
    locked = db.Column(db.Boolean)
    revision = db.Column(db.Integer)
    notes = db.Column(db.Text)
    communications = db.Column(db.Text)
    remove_reason = db.Column(db.Text)
    # delete_reason = db.Column(db.Text)
    create_date = db.Column(db.DateTime)
    created_by = db.Column(db.String(128))
    modify_date = db.Column(db.DateTime)
    modified_by = db.Column(db.String(128))
    locked_by = db.Column(db.String(16))
    lock_date = db.Column(db.DateTime)
    pending_submitter = db.Column(db.String)

    # def __init__(self, **entries):
    #     if 'db_status' not in entries.keys():
    #         print('You are in models.py')
    #         entries['db_status'] = 'Active'
    #         entries['created_by'] = current_user.initials
    #         entries['create_date'] = datetime.now()
    #     self.__dict__.update(entries)

    @classmethod
    def select_field_query(cls):
        """
        Method to only get entries in a table that have a db_status of 'Active' or 'Active With Pending Changes' and
        are also not locked.
        """
        # Return a query object with the default filter
        return cls.query.filter_by(locked=False).filter(cls.db_status.in_(['Active', 'Active With Pending Changes']))

    @classmethod
    def get_next_id(cls):
        """
        Method to get the next id. Useful when needing the item id before it has been added to the database
        """
        # Return a query object with the default filter
        if cls.query.count():
            next_id = cls.query.order_by(cls.id.desc()).first().id + 1
        else:
            next_id = 1
        return next_id


############## ADMIN ##############

class Modifications(db.Model):
    """
    Modifications for all forms throughout the LIMS. The combination of table_name and id allows were querying

    Columns:
        id (int): the id assigned to the item in the table.
        event (str): whether the modification is a CREATED or UPDATED modification.
        status (str):
        table_name (str): the name of the table the modification pertains to
        record_id (str): the id of the item
        revision (int): the revision number for the field.
        field_name (str):
        field (str):
        original_value (str):
        original_value_text (str):
        new_value (str):
        new_value_text (str):
        submitted_date (datetime): the date the item was created.
        submitted_by (int): id of the user who created the item.
        review_date (datetime): the date the item was modified.
        reviewed_by (int): id of the user who modified the item.

    Relationships
        submitted_by: Users (backref = submitter)
        reviewed_by: Users (backref = reviewer)

    """

    __tablename__ = 'modifications'

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(64))
    status = db.Column(db.String(32))
    table_name = db.Column(db.String(64), index=True)
    record_id = db.Column(db.String(512), index=True)
    revision = db.Column(db.Integer)
    field_name = db.Column(db.String(512), index=True)
    field = db.Column(db.String(512), index=True)
    original_value = db.Column(db.String)
    original_value_text = db.Column(db.String)
    new_value = db.Column(db.String)
    new_value_text = db.Column(db.String)
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = submitter
    submitted_date = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = reviewer
    review_date = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)

    @classmethod
    def get_next_revision(cls, table_name, record_id, field_name):
        """
        Method to get the next revision for a field. Useful when needing the item id before it has been added to the database
        """
        revision = cls.query \
            .filter_by(table_name=table_name, record_id=str(record_id), field_name=field_name) \
            .order_by(cls.revision.desc()) \
            .first()

        if revision:
            revision = revision.revision + 1
        else:
            revision = 0

        return revision


class Attachments(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'attachments'

    table_name = db.Column(db.String(32), index=True)
    record_id = db.Column(db.Integer, index=True)
    type_id = db.Column(db.Integer, db.ForeignKey('attachment_types.id'))
    description = db.Column(db.Text)
    name = db.Column(db.String(128))
    save_name = db.Column(db.String)
    path = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class AttachmentTypes(db.Model, BaseTemplate):
    """

    """

    attachment_types_attachments = db.relationship('Attachments', backref='type', lazy=True)

    __tablename__ = 'attachment_types'

    name = db.Column(db.String)
    source = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Users(db.Model, UserMixin):
    """

    """

    __tablename__ = 'users'
    resource_level = 'secondary'
    __itemname__ = 'Person'
    __itemtype__ = 'Person'

    submitter = db.relationship('Modifications', backref='submitter', lazy=True,
                                foreign_keys='Modifications.submitted_by')

    reviewer = db.relationship('Modifications', backref='reviewer', lazy=True,
                               foreign_keys='Modifications.reviewed_by')

    receiver = db.relationship('ReferenceMaterials', backref='receiver', lazy=True,
                               foreign_keys='ReferenceMaterials.received_by')

    opener = db.relationship('ReferenceMaterials', backref='opener', lazy=True,
                             foreign_keys='ReferenceMaterials.opened_by')

    discarder = db.relationship('ReferenceMaterials', backref='discarder', lazy=True,
                                foreign_keys='ReferenceMaterials.discarded_by')

    users_specimens = db.relationship('Specimens', backref='accessioner', lazy=True)
    users_bookings = db.relationship('Bookings', backref='expert', lazy=True)

    users_litigation_packets = db.relationship('LitigationPackets', backref='user', lazy=True,
                                               foreign_keys='LitigationPackets.prepared_by')
    
    decleration_sent_packets = db.relationship('LitigationPackets', backref='declaration_sent', lazy=True, 
                                               foreign_keys='LitigationPackets.declaration_sent_by' )

    reports_case_reviewer = db.relationship('Reports', backref='case_reviewer', lazy=True,
                                            foreign_keys='Reports.case_review')

    reports_divisional_reviewer = db.relationship('Reports', backref='divisional_reviewer', lazy=True,
                                                  foreign_keys='Reports.divisional_review')

    solv_receiver = db.relationship('SolventsAndReagents', backref='solv_receiver', lazy=True,
                                    foreign_keys='SolventsAndReagents.recd_by')

    prep_by = db.relationship('StandardsAndSolutions', backref='prep_by', lazy=True,
                              foreign_keys='StandardsAndSolutions.prepared_by')

    verif_by = db.relationship('StandardsAndSolutions', backref='verif_by', lazy=True,
                               foreign_keys='StandardsAndSolutions.verified_by')

    approved = db.relationship('StandardsAndSolutions', backref='approved', lazy=True,
                               foreign_keys='StandardsAndSolutions.approved_by')

    extracting_analyst = db.relationship('Batches', backref='extractor', lazy=True,
                                         foreign_keys='Batches.extracted_by_id')

    specimen_checker = db.relationship('Batches', backref='specimen_checker', lazy=True,
                                       foreign_keys='Batches.checked_by_id')

    processing_analyst = db.relationship('Batches', backref='processor', lazy=True,
                                         foreign_keys='Batches.processed_by_id')

    batch_reviewer = db.relationship('Batches', backref='batch_reviewer', lazy=True,
                                     foreign_keys='Batches.reviewed_by_id')
    extracting_analyst_2 = db.relationship('Batches', backref='extractor_2', lazy=True,
                                           foreign_keys='Batches.extracted_by_2_id')

    processing_analyst_2 = db.relationship('Batches', backref='processor_2', lazy=True, 
                                           foreign_keys='Batches.processed_by_2_id')

    batch_reviewer_2 = db.relationship('Batches', backref='batch_reviewer_2', lazy=True, 
                                       foreign_keys='Batches.reviewed_by_2_id')
    
    extracting_analyst_3 = db.relationship('Batches', backref='extractor_3', lazy=True,
                                           foreign_keys='Batches.extracted_by_3_id')

    processing_analyst_3 = db.relationship('Batches', backref='processor_3', lazy=True, 
                                           foreign_keys='Batches.processed_by_3_id')

    batch_reviewer_3 = db.relationship('Batches', backref='batch_reviewer_3', lazy=True, 
                                       foreign_keys='Batches.reviewed_by_3_id')

    specimen_check = db.relationship('Tests', backref='specimen_checker', lazy=True, foreign_keys='Tests.checked_by')

    gcet_specimen_check = db.relationship('Tests', backref='gcet_checker', lazy=True,
                                          foreign_keys='Tests.gcet_checked_by')

    transfer_check = db.relationship('Tests', backref='transfer_checker', lazy=True,
                                     foreign_keys='Tests.transfer_check_by')

    sequence_check = db.relationship('Tests', backref='sequence_checker', lazy=True,
                                     foreign_keys='Tests.sequence_check_by')

    gcet_sequence_check = db.relationship('Tests', backref='gcet_sequence_checker', lazy=True,
                                          foreign_keys='Tests.sequence_check_2_by')

    const_specimen_check = db.relationship('BatchConstituents', backref='specimen_checker', lazy=True,
                                           foreign_keys='BatchConstituents.specimen_check_by')

    const_gcet_check = db.relationship('BatchConstituents', backref='gcet_checker', lazy=True,
                                       foreign_keys='BatchConstituents.gcet_sequence_check_by')

    const_transfer_check = db.relationship('BatchConstituents', backref='transfer_checker', lazy=True,
                                           foreign_keys='BatchConstituents.transfer_check_by')

    const_sequence_check = db.relationship('BatchConstituents', backref='sequence_checker', lazy=True,
                                           foreign_keys='BatchConstituents.sequence_check_by')

    load_check = db.relationship('Tests', backref='load_checker', lazy=True,
                                 foreign_keys='Tests.load_check_by')
    load_const = db.relationship('BatchConstituents', backref='loader', lazy=True,
                                 foreign_keys='BatchConstituents.load_check_by')

    litigation_preparer_user = db.relationship('LitigationPackets', backref='prep_user', lazy=True,
                                               foreign_keys='LitigationPackets.litigation_preparer')

    litigation_reviewer_user = db.relationship('LitigationPackets', backref='rev_user', lazy=True,
                                               foreign_keys='LitigationPackets.litigation_reviewer')
    request_intake_user = db.relationship('Requests', backref='intake_user_id', lazy=True,
                                          foreign_keys='Requests.intake_user')
    request_approver = db.relationship('Requests', backref='approver', lazy=True, foreign_keys='Requests.approver_id')
    request_preparer = db.relationship('Requests', backref='preparing_user', lazy=True,
                                       foreign_keys='Requests.preparer')
    request_checker = db.relationship('Requests', backref='checking_user', lazy=True, foreign_keys='Requests.checker')
    request_releaser = db.relationship('Requests', backref='releasing_user', lazy=True,
                                       foreign_keys='Requests.releaser')
    instrument_checker = db.relationship('Batches', backref='inst_check', lazy=True,
                                         foreign_keys='Batches.instrument_check_by')
    extraction_checker = db.relationship('Batches', backref='ext_check', lazy=True,
                                         foreign_keys='Batches.extraction_check_by')

    transferred_by = db.relationship('Containers', backref='transfer', lazy=True)
    assigned_dr = db.relationship('Reports', backref='assigned_dr_user', lazy = True, foreign_keys='Reports.assigned_dr')
    assigned_cr = db.relationship('Reports', backref='assigned_cr_user', lazy = True, foreign_keys='Reports.assigned_cr')
    return_checker = db.relationship('Returns', backref = 'checker_user', lazy = True, foreign_keys= 'Returns.checker')

    id = db.Column(db.Integer, primary_key=True)
    db_status = db.Column(db.String)
    first_name = db.Column(db.String(64))
    middle_initial = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    title = db.Column(db.String(64))
    full_name = db.Column(db.String(64))
    initials = db.Column(db.String(3))
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    job_class = db.Column(db.String(64))
    job_title = db.Column(db.String(64))
    background_check = db.Column(db.String(64))
    permissions = db.Column(db.String(64))
    status = db.Column(db.String(16))
    has_signature = db.Column(db.String(16))
    password_hash = db.Column(db.String(512))
    last_login = db.Column(db.DateTime)
    incorrect_logins = db.Column(db.Integer)
    last_incorrect_login = db.Column(db.DateTime)
    locked = db.Column(db.Boolean)
    revision = db.Column(db.Integer)
    notes = db.Column(db.Text)
    communications = db.Column(db.Text)
    remove_reason = db.Column(db.Text)
    create_date = db.Column(db.DateTime)
    created_by = db.Column(db.String(128))
    modify_date = db.Column(db.DateTime)
    modified_by = db.Column(db.String(128))
    locked_by = db.Column(db.String(16))
    lock_date = db.Column(db.DateTime)
    pending_submitter = db.Column(db.String)
    dashboard_discipline = db.Column(db.String)
    personnel_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # backref = personnel
    default_printer = db.Column(db.String(128))
    telephone_number = db.Column(db.String(128)) # Duplicate of Personnel.phone
    cellphone_number = db.Column(db.String(128)) # Duplicate of Personnel.cell

    def __init__(self, **entries):
        self.__dict__.update(**entries)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @classmethod
    def get_next_id(cls):
        """
        Method to get the next id. Useful when needing the item id before it has been added to the database
        """
        # Return a query object with the default filter
        if cls.query.count():
            next_id = cls.query.order_by(cls.id.desc()).first().id + 1
        else:
            next_id = 1
        return next_id


class UserLog(db.Model):
    """

    """

    __tablename__ = 'user_log'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(64))
    route = db.Column(db.String(7936))
    view_function = db.Column(db.String(128))
    date_accessed = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(**entries)


class SpecimenAudit(db.Model, BaseTemplate):
    """
    Notes:
        created_by is used as submitter and is only recorded for manual custody changes.
    """

    __tablename__ = 'specimen_audit'

    origin = db.Column(db.String(64))
    destination = db.Column(db.String(64))
    reason = db.Column(db.String(256))
    specimen_id = db.Column(db.Integer, db.ForeignKey('specimens.id'))  # backref = specimen
    o_time = db.Column(db.DateTime)
    d_time = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## PERSONNEL ##############


class Agencies(db.Model, BaseTemplate):
    """
    List of agencies.

    Columns:
       name (str): the name of the agency.
       abbreviation (str): the abbreviation of the agency.

    Backrefs:
        agency: Divisions. Personnel, Cases, DefaultClients, GeneralLabware, CalibratedLabware, Instruments,
        FumeHoods, CooledStorage, Histology, Hubs, Probes

    """

    __tablename__ = 'agencies'

    divisions = db.relationship('Divisions', backref='agency', lazy=True)
    personnel = db.relationship('Personnel', backref='agency', lazy=True)
    agencies_cases = db.relationship('Cases', backref='agency', lazy=True)
    agencies_default_clients = db.relationship('DefaultClients', backref='agency', lazy=True)
    agencies_bookings = db.relationship('Bookings', backref='agency_A', foreign_keys='Bookings.agency_id', lazy=True)
    cross_bookings = db.relationship('Bookings', backref='agency_B', foreign_keys='Bookings.cross_examined', lazy=True)
    agencies_litigation = db.relationship('LitigationPackets', backref='agency', lazy=True,
                                          foreign_keys='LitigationPackets.agency_id')
    agencies_litigation_del = db.relationship('LitigationPackets', backref='del_agency', lazy=True,
                                              foreign_keys='LitigationPackets.del_agency_id')  # delivered agency
    general_manufacturer = db.relationship('GeneralLabware', backref='agency', lazy=True)
    calibrated_manufacturer = db.relationship('CalibratedLabware', backref='agency', lazy=True)
    instruments_manufacturer = db.relationship('Instruments', backref='agency', lazy=True)
    fumehoods_manufacturer = db.relationship('FumeHoods', backref='agency', lazy=True)
    cooledstorage_manufacturer = db.relationship('CooledStorage', backref='agency', lazy=True)
    histo_manufacturer = db.relationship('HistologyEquipment', backref='agency', lazy=True)
    hubs_manufacturer = db.relationship('Hubs', backref='agency', lazy=True)
    probes_manufacturer = db.relationship('Probes', backref='agency', lazy=True)
    requests_agency = db.relationship('Requests', backref='agency_req', lazy=True,
                                      foreign_keys='Requests.requesting_agency')
    request_receiving_agency = db.relationship('Requests', backref='agency_rec', lazy=True,
                                               foreign_keys='Requests.receiving_agency')
    request_destination_agency = db.relationship('Requests', backref='dest_agency', lazy=True,
                                                 foreign_keys='Requests.destination_agency')
    solvents_manufacturer = db.relationship('SolventsAndReagents', backref='agency', lazy=True)

    name = db.Column(db.String(128), unique=True)
    abbreviation = db.Column(db.String(128))
    vendor = db.Column(db.String)
    manufacturer = db.Column(db.String)
    returns = db.relationship('Returns', backref='agency', lazy=True, foreign_keys ='Returns.returning_agency')

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Divisions(db.Model, BaseTemplate):
    """
    List of divisions.

    Columns:
       name (str): the name of the agency.
       abbreviation (str): the abbreviation of the agency.
       agency_id (int): parent agency
       vendor (str): vendor status of the division
       street_number (str): the address number
       street_address (str): address name and type of the division
       unit_number (str): unit number of the division
       floor (str): floor of the division
       city (str): city the division is located
       state (int): The US state the division is located in
       zipcode (str): the zipcode of the city

    Relationships
        agency_id: Agencies (backref = agency)

    Backrefs division: Personnel, ReferenceMaterials, Instruments, CooledStorage, CalibratedLabware, Cases,
    DefaultClients, Hubs, Probes, GeneralLabware, HistologyEquipment, FumeHoods

    """

    __tablename__ = 'divisions'

    fridges_freezers = db.relationship('CooledStorage', backref='division', lazy=True)
    personnel = db.relationship('Personnel', backref='division', lazy=True)
    reference_materials = db.relationship('ReferenceMaterials', backref='division', lazy=True)
    calibrated_labware = db.relationship('CalibratedLabware', backref='division', lazy=True)
    divisions_instruments = db.relationship('Instruments', backref='vendor', lazy=True)
    divisions_cases = db.relationship('Cases', backref='division', lazy=True)
    divisions_default_clients = db.relationship('DefaultClients', backref='division', lazy=True)
    hubs = db.relationship('Hubs', backref='division', lazy=True)
    divisions_probes = db.relationship('Probes', backref='vendor', lazy=True)
    general_vendor = db.relationship('GeneralLabware', backref='vendor', lazy=True,
                                     foreign_keys='GeneralLabware.vendor_id')
    histology_vendor = db.relationship('HistologyEquipment', backref='vendor', lazy=True,
                                       foreign_keys='HistologyEquipment.vendor_id')
    divisions_litigation = db.relationship('LitigationPackets', backref='division', lazy=True,
                                           foreign_keys='LitigationPackets.division_id')
    divisions_litigation_del = db.relationship('LitigationPackets', backref='del_division', lazy=True,
                                               foreign_keys='LitigationPackets.del_division_id')  # delivered division

    fumehoods_vendor = db.relationship('FumeHoods', backref='vendor', lazy=True,
                                       foreign_keys='FumeHoods.vendor_id')
    request_division = db.relationship('Requests', backref='division_req', lazy=True,
                                       foreign_keys='Requests.requesting_division')
    request_receiving_division = db.relationship('Requests', backref='division_rec', lazy=True,
                                                 foreign_keys='Requests.receiving_division')
    request_destination_division = db.relationship('Requests', backref='dest_division', lazy=True,
                                                   foreign_keys='Requests.destination_division')
    divisions_record_types = db.relationship('RecordTypes', backref='division', lazy=True)
    
    returns = db.relationship('Returns', backref='division', lazy=True, foreign_keys ='Returns.returning_division')

    name = db.Column(db.String(128))
    abbreviation = db.Column(db.String(32))
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = agency
    street_number = db.Column(db.String(128))
    street_address = db.Column(db.String(128))
    unit_number = db.Column(db.String(128))
    floor = db.Column(db.String(128))
    city = db.Column(db.String(128))
    state = db.Column(db.Integer, db.ForeignKey('united_states.id'))  # Needs to be defined in UnitedStates model
    zipcode = db.Column(db.String(128))
    full_address = db.Column(db.String)
    email = db.Column(db.String)
    client = db.Column(db.String)
    stakeholder = db.Column(db.String)
    reference_material_provider = db.Column(db.String)
    service_provider = db.Column(db.String)

    __table_args__ = (UniqueConstraint('agency_id', 'name', name='uix_agency-id_name'),)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Personnel(db.Model, BaseTemplate):
    """
    List of personnel.

    Columns:
       first_name (str): the name of the agency.
       middle_name (str): the abbreviation of the agency.
       last_name (str): parent agency.
       full_name (str) : full name of the person. Concatenation of first_name, middle_name and last_name.
       titles (str): the person's title(s).
       division_id (int): the division the person belongs to.
       job_title (str): person's title/position in division.
       id_number (str): person's divisional ID number.
       email (str): person's email address.
       phone (str): person's phone number.
       cell (str): person's cell number.
       submitter (str): person's submitter status.

    Relationships
        agency_id: Agencies (backref = agency)

    Backrefs
        submitter: Containers, EvidenceComments
        pathologist: Cases (Cases.primary_pathologist)
        investigator: Cases (Cases.primary_investigator)
        status_id : Statuses (Statuses.personnel_statuses)
        observer: Containers (Containers.observed_by)

    """

    __tablename__ = 'personnel'

    personnel_containers = db.relationship('Containers', backref='submitter', lazy=True, foreign_keys='Containers.submitted_by')
    personnel_evidence_comments = db.relationship('EvidenceComments', backref='submitter', lazy=True)
    personnel_cases_pathologist = db.relationship('Cases', backref='pathologist', lazy=True,
                                                  foreign_keys='Cases.primary_pathologist')
    personnel_cases_investigator = db.relationship('Cases', backref='investigator', lazy=True,
                                                   foreign_keys='Cases.primary_investigator')
    personnel_cases_investigator_second = db.relationship('Cases', backref='investigator_second', lazy=True,
                                                          foreign_keys='Cases.secondary_investigator')
    cases_certifier = db.relationship('Cases', backref='certifier', lazy=True,
                                      foreign_keys='Cases.certified_by')
    personnel_specimens = db.relationship('Specimens', backref='collector', lazy=True)
    personnel_services = db.relationship('Services', backref='vendor', lazy=True)
    personnel_users = db.relationship('Users', backref='personnel', lazy=True)

    personnel_litigation = db.relationship('LitigationPackets', backref='personnel', lazy=True,
                                           foreign_keys='LitigationPackets.personnel_id')

    personnel_litigation_del = db.relationship('LitigationPackets', backref='del_personnel', lazy=True,
                                               foreign_keys='LitigationPackets.del_personnel_id')  # delivered personnel

    request_personnel = db.relationship('Requests', backref='personnel_req', lazy=True,
                                        foreign_keys='Requests.requesting_personnel')
    request_receiving_personnel = db.relationship('Requests', backref='personnel_rec', lazy=True,
                                                  foreign_keys='Requests.receiving_personnel')
    request_destination_personnel = db.relationship('Requests', backref='dest_personnel', lazy=True,
                                                    foreign_keys='Requests.destination_personnel')
    personnel_bookings = db.relationship('Bookings', backref='person_A1', lazy=True,
                                         foreign_keys='Bookings.personnel_id')
    personnel_A2_bookings = db.relationship('Bookings', backref='person_A2', lazy=True,
                                            foreign_keys='Bookings.personnelA2_id')
    personnel_B1_bookings = db.relationship('Bookings', backref='person_B1', lazy=True,
                                            foreign_keys='Bookings.personnelB1_id')
    personnel_B2_bookings = db.relationship('Bookings', backref='person_B2', lazy=True,
                                            foreign_keys='Bookings.personnelB2_id')
    personnel = db.relationship('Returns', backref='personnel', lazy=True,
                                                  foreign_keys='Returns.returning_personnel')
    personnel_property = db.relationship('FAPersonalEffects', backref='personnel', lazy=True)
    personnel_observer = db.relationship('Containers', backref='observer', lazy=True,
                                        foreign_keys='Containers.observed_by')

    first_name = db.Column(db.String(64))
    middle_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    full_name = db.Column(db.String(128))
    titles = db.Column(db.String(64))
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = agency
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = division
    job_title = db.Column(db.String(128))
    id_number = db.Column(db.String(128))
    email = db.Column(db.String(128))
    phone = db.Column(db.String(128))# Duplicate of Users.telephone_number
    cell = db.Column(db.String(128)) # Duplicate of Users.cellphone_number
    submitter = db.Column(db.String(128))
    receives_report = db.Column(db.String(128))
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id')) 

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### CASES #####
class EncryptedSSNType(TypeDecorator):
    impl = LargeBinary

    def process_bind_param(self, value, dialect):
        if value is not None:
            return fernet.encrypt(value.encode())
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return fernet.decrypt(value).decode()
        return None

    
class Cases(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'cases'

    evidence_comments_cases = db.relationship('EvidenceComments', backref='case', lazy=True)
    cases_specimens = db.relationship('Specimens', backref='case', lazy=True)
    cases_containers = db.relationship('Containers', backref='case', lazy=True)
    cases_tests = db.relationship('Tests', backref='case', lazy=True)
    cases_records = db.relationship('Records', backref='case', lazy=True)
    cases_results = db.relationship('Results', backref='case', lazy=True)
    cases_bookings = db.relationship('Bookings', backref='case', lazy=True)
    cases_pt = db.relationship('PTResults', backref='case', lazy=True)
    cases_pt_cases = db.relationship('PTCases', backref='case', lazy=True)
    cases_reports = db.relationship('Reports', backref='case', lazy=True)
    cases_narratives = db.relationship('Narratives', backref='case', lazy=True)
    cases_packets = db.relationship('LitigationPackets', backref='case', lazy=True)
    cases_property = db.relationship('FAPersonalEffects', backref='case', lazy=True)

    case_type = db.Column(db.Integer, db.ForeignKey('case_types.id'))  # backref = type
    case_distinguisher = db.Column(db.String) # UNUSED and removed elsewhere SLP 10/02/25
    case_number = db.Column(db.String)
    case_status = db.Column(db.String)
    tat_start_date = db.Column(db.DateTime)             # unused currently, replaced by discipline_start_date
    tat_alternate_start_date = db.Column(db.DateTime)   # unused currently, replaced by discipline_alt_start_date
    case_close_date = db.Column(db.DateTime)
    turn_around_time = db.Column(db.Integer)
    last_name = db.Column(db.String)
    middle_name = db.Column(db.String)
    first_name = db.Column(db.String)
    gender_id = db.Column(db.Integer, db.ForeignKey('genders.id'))  # Backref = genders
    birth_sex = db.Column(db.String)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'))  # Backref = races
    hispanic_ethnicity = db.Column(db.String)
    marital_status = db.Column(db.String)
    pregnant_status = db.Column(db.String)
    date_of_birth = db.Column(db.DateTime)
    age_years = db.Column(db.Integer)
    age_months = db.Column(db.Integer)
    age_days = db.Column(db.Integer)
    age = db.Column(db.String)
    age_status = db.Column(db.String)
    height_inches = db.Column(db.Integer)
    weight_pounds = db.Column(db.Integer)
    next_of_kin_relationship = db.Column(db.String(512))
    ssn = db.Column(EncryptedSSNType)
    date_of_incident = db.Column(db.DateTime)
    time_of_incident = db.Column(db.String)
    medical_record = db.Column(db.String)
    home_address = db.Column(db.String)
    home_city = db.Column(db.String)
    home_county = db.Column(db.String)
    home_zip = db.Column(db.String)
    home_status = db.Column(db.String(32))
    death_address = db.Column(db.String)
    death_zip = db.Column(db.String)
    death_premises = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    cod_a = db.Column(db.String)
    cod_b = db.Column(db.String)
    cod_c = db.Column(db.String)
    cod_d = db.Column(db.String)
    other_conditions = db.Column(db.String)
    how_injury_occured = db.Column(db.String)
    manner_of_death = db.Column(db.String(512), index=True)
    method_of_death = db.Column(db.String)
    fa_case_comments = db.Column(db.Text)
    case_comments_ai = db.Column(db.Text) 
    fa_case_stage = db.Column(db.String)
    fa_case_entry_date = db.Column(db.DateTime)
    fa_case_death_type = db.Column(db.String)
    fa_scene_arrival_datetime = db.Column(db.DateTime)
    fa_scene_dept_datetime = db.Column(db.DateTime)
    fa_cooler_datetime = db.Column(db.DateTime) # when body is received
    exam_status = db.Column(db.String)
    autopsy_type = db.Column(db.String)
    autopsy_start_date = db.Column(db.DateTime)
    autopsy_end_date = db.Column(db.DateTime)
    autopsy_finalized_date = db.Column(db.DateTime) # when body is released
    autopsy_performed = db.Column(db.String)
    certificate_status = db.Column(db.String)
    certificate_report_date = db.Column(db.DateTime) # in FA this is CODFinalizedDate, expect NULL for ADMIN REVIEW
    certified_by = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # Backref = certifier
    primary_pathologist = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # Backref = pathologist
    primary_investigator = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # Backref = investigator
    secondary_investigator = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # Backref = investigator_second
    fa_restrict_public_access = db.Column(db.String)    # UNUSED in FA and not displayed
    submitting_agency = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # Backref = agency
    submitting_division = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # Backref = division
    submitter_case_reference_number = db.Column(db.String)
    alternate_case_reference_number_1 = db.Column(db.String)
    alternate_case_reference_number_2 = db.Column(db.String)
    n_containers = db.Column(db.Integer)
    testing_requested = db.Column(db.String)
    toxicology_requested = db.Column(db.String)
    toxicology_performed = db.Column(db.String)
    toxicology_status = db.Column(db.String)
    toxicology_start_date = db.Column(db.DateTime)
    toxicology_alternate_start_date = db.Column(db.DateTime)
    toxicology_end_date = db.Column(db.DateTime)
    toxicology_tat = db.Column(db.Integer)
    biochemistry_requested = db.Column(db.String)
    biochemistry_performed = db.Column(db.String)
    biochemistry_status = db.Column(db.String)
    biochemistry_start_date = db.Column(db.DateTime)
    biochemistry_alternate_start_date = db.Column(db.DateTime)
    biochemistry_end_date = db.Column(db.DateTime)
    biochemistry_tat = db.Column(db.Integer)
    histology_requested = db.Column(db.String)
    histology_performed = db.Column(db.String)
    histology_status = db.Column(db.String)
    histology_start_date = db.Column(db.DateTime)
    histology_alternate_start_date = db.Column(db.DateTime)
    histology_end_date = db.Column(db.DateTime)
    histology_tat = db.Column(db.Integer)
    external_requested = db.Column(db.String)
    external_performed = db.Column(db.String)
    external_status = db.Column(db.String)
    external_start_date = db.Column(db.DateTime)
    external_alternate_start_date = db.Column(db.DateTime)
    external_end_date = db.Column(db.DateTime)
    external_tat = db.Column(db.Integer)
    submitter_requests = db.Column(db.Text)
    priority = db.Column(db.String)
    sensitivity = db.Column(db.String)          # see fa_restrict_public_access
    retention_policy = db.Column(db.Integer, db.ForeignKey('retention_policies.id'))  # Backref = retention
    discard_date = db.Column(db.DateTime)
    discard_eligible = db.Column(db.String)
    accidental_overdose = db.Column(db.String)  # UNUSED
    physical_requested = db.Column(db.String)
    physical_performed = db.Column(db.String)
    physical_status = db.Column(db.String)
    physical_start_date = db.Column(db.DateTime)
    physical_alternate_start_date = db.Column(db.DateTime)
    physical_end_date = db.Column(db.DateTime)
    physical_tat = db.Column(db.Integer)
    drug_requested = db.Column(db.String)
    drug_performed = db.Column(db.String)
    drug_status = db.Column(db.String)
    drug_start_date = db.Column(db.DateTime)
    drug_alternate_start_date = db.Column(db.DateTime)
    drug_end_date = db.Column(db.DateTime)
    drug_tat = db.Column(db.Integer)
    review_discipline = db.Column(db.String(256))
    ocme_status = db.Column(db.String)          # populated on load of and for AME Dashboard, no other meaning; ETK replacing usage, then UNUSED
    pending_dc = db.Column(db.String)           # populated on load of and for AME Dashboard, no other usage
    pending_ar = db.Column(db.String)           # populated on load of and for AME Dashboard, no other usage
    body_received_date = db.Column(db.DateTime) # DELETE - UNUSED
    mortuary = db.Column(db.String)
    referred_to_pub_adm = db.Column(db.Boolean) # IS THIS DATA VALID?
    body_released_time = db.Column(db.String)
    public_administrator = db.Column(db.String) # IS THIS DATA VALID?
    pa_notified_date = db.Column(db.DateTime)   # IS THIS DATA VALID?
    alias_names = db.Column(db.String) 
    prouncement_of_death = db.Column(db.DateTime) # DELETE - UNUSED
    nok_notify_date = db.Column(db.DateTime)    # in FA, sometimes includes time
    nok_notify_time = db.Column(db.String)      # in FA, sometimes null despite nok_notify_date not null
    fa_inv_start_datetime = db.Column(db.DateTime)
    fa_inv_end_datetime = db.Column(db.DateTime)
    fa_ident_datetime = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CaseTypes(db.Model, BaseTemplate):
    """
    List of case types i.e., PM, X, D, M, N, etc.

    Columns:
        name (str): the name of the case type.
        code (str): the code for the case type.
        accession_level (str): the order with which it appears in the drop-down when creating a case.
        batch_level (str) : the order with which it is sorted when creating a batch.
        case_number_type (str): whether the case number is generated automatically or manually.
        case_number_start (int): the starting number rolled over from ToxDB.
        current_case_number (int): the case types current case number
        retention_policy_id (int): the default retention policy for the case type.
        default_assays (str): the default assays for the case type.

    Relationships
        retention_policy_id: RetentionPolicies (backref = retention)

    Backrefs
        type: Cases, CaseDistinguishers

    """
    __tablename__ = 'case_types'

    case_types = db.relationship('Cases', backref='type', lazy=True)
    types_distinguishers = db.relationship('CaseDistinguishers', backref='type', lazy=True) # DELETE with next migration
    case_types_default_clients = db.relationship('DefaultClients', backref='type', lazy=True)

    name = db.Column(db.String(64))
    code = db.Column(db.String(32), unique=True)
    accession_level = db.Column(db.Integer)
    batch_level = db.Column(db.Integer)
    case_number_type = db.Column(db.String(32))
    case_number_start = db.Column(db.Integer)
    current_case_number = db.Column(db.Integer)
    retention_policy = db.Column(db.Integer, db.ForeignKey('retention_policies.id'))  # backref = retention
    toxicology_report_template_id = db.Column(db.Integer,
                                              db.ForeignKey('report_templates.id'))  # backref = report_template
    biochemistry_report_template_id = db.Column(db.Integer,
                                                db.ForeignKey('report_templates.id'))  # backref = report_template
    histology_report_template_id = db.Column(db.Integer,
                                             db.ForeignKey('report_templates.id'))  # backref = report_template
    external_report_template_id = db.Column(db.Integer,
                                            db.ForeignKey('report_templates.id'))  # backref = report_template
    litigation_packet_template_id = db.Column(db.Integer, db.ForeignKey(
        'litigation_packet_templates.id'))  # backref = lit_packet_template
    default_assays = db.Column(db.String)


    def __init__(self, **entries):
        self.__dict__.update(entries)


class DefaultClients(db.Model, BaseTemplate):
    __tablename__ = 'default_clients'

    case_type_id = db.Column(db.Integer, db.ForeignKey('case_types.id'))
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CaseDistinguishers(db.Model, BaseTemplate): # UNUSED and removed elsehere SLP 10/02/25
    """
    List of case distinguihsers i.e., suicide, homicide

    Columns:
        name (str): the name of the case distinguisher.
        case_type_id (int): the id of the case type that the distinguisher corresponds to.

    Relationships
        case_type_id: CaseTypes (backref = type)

    """

    __tablename__ = 'case_distinguishers' # UNUSED and removed elsehere SLP 10/02/25

    name = db.Column(db.String(32))
    case_type_id = db.Column(db.Integer, db.ForeignKey('case_types.id'))  # backref = type

    __table_args__ = (UniqueConstraint('name', 'case_type_id', name='uix_name_case-type-id'),)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class RetentionPolicies(db.Model, BaseTemplate):
    """
    List of retention policies i.e., RERDP 8a, RERDP 8b, RERDP 37

    Columns:
        name (str): the name of the retention policy.
        retention_length (int): the length (days) of the retention policy.
        date_selection (str): whether the selection of the policy allows for manual selection of policy end date

    Backrefs
        retention : Cases, CaseTypes

    """

    __tablename__ = "retention_policies"

    retention_policies_case_types = db.relationship('CaseTypes', backref='retention', lazy=True)
    retention_policies_cases = db.relationship('Cases', backref='retention', lazy=True)

    name = db.Column(db.String(32), unique=True)
    retention_length = db.Column(db.Integer)
    date_selection = db.Column(db.String(32))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Genders(db.Model, BaseTemplate):
    """
    List of genders.

    Columns:
        name (str): the name of the gender.

    Backrefs
       gender: Cases

    """

    __tablename__ = 'genders'

    gender_cases = db.relationship('Cases', backref='gender', lazy=True)

    name = db.Column(db.String(32), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Races(db.Model, BaseTemplate):
    """
    List of races.

    Columns:
        name (str): the name of the race.

    Backrefs
       race: Cases

    """

    __tablename__ = 'races'

    race_cases = db.relationship('Cases', backref='race', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### CONTAINERS #####


class ContainerTypes(db.Model, BaseTemplate):
    """
    List of container types i.e., AM Bag, Evidence Envelope, etc.

    Columns:
        name (str): the name of the container type. Simplified name for lab use.
        code (str): the code for the container type.
        description (str): Formal name for reporting.

    Backrefs
        type: Containers

    """

    __tablename__ = 'container_types'

    description = db.Column(db.String(64))  # TO DELETE

    types_containers = db.relationship('Containers', backref='type', lazy=True)

    name = db.Column(db.String(64))  # This column is displayed as "Description" in the HTML
    code = db.Column(db.String(32), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Containers(db.Model, BaseTemplate):
    """
    List of containers.

    Columns:
        case_id (id): the id of the case.
        container_type_id (int): the id of the container type.
        accession_number (str): the accession number of the specimen.
        n_specimens (int): the number of specimens in a container.
        submitted_by (int): the id of the person who submitted the container.
        submission_date (datetime): the date of the container submission.
        submission_time (str): the time of the container submission.
        submission_route_type (str): the route type of the submission (i.e., By Hand, By Location).
        received_time (str): the time the container was received:
        evidence_comments (str): list of evidence comments
        observed_by (int): the id of the person present and observing the receipt of the container (i.e., secondary personnel during drug receipt)

    Relationships
        case_id: Cases (backref = case)
        container_type_id: Containers (backref = container)
        submitted_by: Personnel (submitter)
        submission_route: EvidenceLockers (backref = storage)
        observed_by: Personnel (observer)

    Backrefs
        container: Specimens

    """
    __tablename__ = 'containers'

    specimen_containers = db.relationship('Specimens', backref='container', lazy=True)

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)  # Backref = case
    container_type_id = db.Column(db.Integer, db.ForeignKey('container_types.id'))  # Backref = type
    accession_number = db.Column(db.String(32))
    n_specimens_submitted = db.Column(db.Integer)
    n_specimens = db.Column(db.Integer)
    submitted_by = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # Backref = submitter
    submission_date = db.Column(db.DateTime)
    submission_time = db.Column(db.String(4))
    submission_route_type = db.Column(db.String(32))
    submission_route = db.Column(db.String)
    location_type = db.Column(db.String(128))  # Submission location type
    received_time = db.Column(db.String(4))
    evidence_comments = db.Column(db.Text)
    discipline = db.Column(db.String(128))
    transfer_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Backref = transfer
    observed_by = db.Column(db.Integer, db.ForeignKey('personnel.id')) # Backref = observer
 

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### SPECIMENS #####


class SpecimenTypes(db.Model, BaseTemplate):
    """
    List of specimen types i.e., Postmortem Blood, peripheral, Postmortem Blood, Cardiac

    Columns:
        name (str): the name of the specimen type. Simplified name for lab use.
        code (str): the code for the specimen type.
        description (str): Formal name for reporting.
        discipline (str): the discipline the specimen type is used for (toxicology, biochemistry, histology, external).
        specimen_site_id (int): the id of the site the specimen was collected from.
        collection_container_id (int): the id of the collection container type the specimen was submitted in.
        unit_id (int): the default units of the specimen type
        default_assays: list of default assays to pre-select when adding tests

    Relationships
        specimen_site_id: SpecimenSites (backref = specimen_site)
        collection_container_id: SpecimenCollectionContainers (backref = collection_container)
        unit_id: Units (backref = unit)

    Backrefs
        type: Specimens

    """

    __tablename__ = 'specimen_types'

    types_specimens = db.relationship('Specimens', backref='type', lazy=True)

    name = db.Column(db.String(64))  # This column is displayed as "Description" in the HTML
    code = db.Column(db.String(32))
    state_id = db.Column(db.Integer, db.ForeignKey('states_of_matter.id'))  # backref = state
    discipline = db.Column(db.String(32))
    description = db.Column(db.String(64))
    collection_container_id = db.Column(db.Integer, db.ForeignKey("specimen_collection_containers.id"))
    # backref = collection_container
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"))
    default_assays = db.Column(db.String)

    __table_args__ = (UniqueConstraint('discipline', 'code', name='uix_discipline_code'),)

    specimen_site_id = db.Column(db.Integer, db.ForeignKey("specimen_sites.id"))  # to DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SpecimenSites(db.Model, BaseTemplate):
    """
### NOT USED ###

    """

    __tablename__ = "specimen_sites"

    sites_types = db.relationship('SpecimenTypes', backref='specimen_site', lazy=True)
    sites_specimens = db.relationship('Specimens', backref='specimen_site', lazy=True)

    name = db.Column(db.String(32), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SpecimenCollectionContainers(db.Model, BaseTemplate):
    """
    List of specimen collection containers types (i.e., range of BD Vacutainers).

    Columns:
        name (str): the name of the specimen collection site.
        code (str): the simplified name for internal use.
        type (str): the type of container (i.e. tube, jar, envelope).

    Backrefs
        collection_container: SpecimenTypes, Specimens

    """

    __tablename__ = "specimen_collection_containers"

    collection_containers_types = db.relationship('SpecimenTypes', backref='collection_container', lazy=True)
    collection_containers_specimens = db.relationship('Specimens', backref='collection_container', lazy=True)

    name = db.Column(db.String)
    display_name = db.Column(db.String)
    type_id = db.Column(db.Integer, db.ForeignKey('specimen_collection_container_types.id'))
    discipline = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SpecimenCollectionContainerTypes(db.Model, BaseTemplate):
    __tablename__ = "specimen_collection_container_types"

    collection_containers_container_types = db.relationship('SpecimenCollectionContainers', backref='type', lazy=True)

    name = db.Column(db.String(256), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SpecimenConditions(db.Model, BaseTemplate):
    """
    List of specimen conditions.

    Columns:
        name (str): the name of the specimen condition.

    """

    __tablename__ = 'specimen_conditions'

    name = db.Column(db.String(32), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Specimens(db.Model, BaseTemplate):
    """

    """

    # Add Units to table
    __tablename__ = 'specimens'

    specimens_tests = db.relationship('Tests', backref='specimen', lazy=True)
    specimen_audit = db.relationship('SpecimenAudit', backref='specimen', lazy=True)

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)  # Backref = case
    container_id = db.Column(db.Integer, db.ForeignKey('containers.id'))  # Backref = container
    specimen_type_id = db.Column(db.Integer, db.ForeignKey('specimen_types.id'))  # Backref = type
    discipline = db.Column(db.String)
    accession_number = db.Column(db.String(32))
    collection_date = db.Column(db.DateTime)
    collection_time = db.Column(db.String(32))
    collected_by = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # Backref = collector
    submitted_sample_amount = db.Column(db.Float)
    current_sample_amount = db.Column(db.Float)
    collection_container_id = db.Column(db.Integer, db.ForeignKey(
        'specimen_collection_containers.id'))  # Backref = collection_container
    condition = db.Column(db.String(256))
    custody_type = db.Column(db.String)
    custody = db.Column(db.String)
    accessioned_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Backref = accessioner
    accession_date = db.Column(db.DateTime)
    evidence_comments = db.Column(db.Text)
    checked_in = db.Column(db.Boolean)
    start_time = db.Column(db.DateTime)  # Accessioning start time, used for specimen audit
    request_id = db.Column(db.Integer,
                           db.ForeignKey('requests.id'))  # backref = request | Shows status, date for request
    parent_specimen = db.Column(db.Integer)  # Used for sub-specimen
    label_mrn = db.Column(db.String(256))
    label_alias = db.Column(db.String(256))
    other_specimen = db.Column(db.String(256))

    collection_site_id = db.Column(db.Integer, db.ForeignKey('specimen_sites.id'))  # to DELETE Backref = specimen_site
    next_location_1 = db.Column(db.String(64))  # TO DELETE
    released = db.Column(db.Boolean)

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### ASSAYS #####


class Assays(db.Model, BaseTemplate):
    """

    """
    __tablename__ = 'assays'

    assays_tests = db.relationship('Tests', backref='assay', lazy=True)
    assays_batches = db.relationship('Batches', backref='assay', lazy=True,
                                     foreign_keys='Batches.assay_id')
    assays_gcdp = db.relationship('Batches', backref='gcdp_assay', lazy=True,
                                  foreign_keys='Batches.gcdp_assay_id')
    assays_scope = db.relationship('Scope', backref='assay', lazy=True)
    current_assay_constituents = db.relationship('CurrentAssayConstituents', backref='assay', lazy=True)
    default_assay_constituents = db.relationship('DefaultAssayConstituents', backref='assay', lazy=True)

    assay_name = db.Column(db.String(32), unique=True)
    discipline = db.Column(db.String(32))
    sop_ref = db.Column(db.String(32))
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'))
    batch_template_id = db.Column(db.Integer, db.ForeignKey('batch_templates.id'))
    sample_volume = db.Column(db.String(32))
    num_tests = db.Column(db.Integer)
    assay_order = db.Column(db.Integer)
    # order = db.Column(db.Integer)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    n_components = db.Column(db.Integer)  # not currently used; scope\views.py has a commented out block
    n_compounds = db.Column(db.Integer)  # that can increment this count when creating scopes; needs testing
    test_count = db.Column(db.Integer)
    batch_count = db.Column(db.Integer)
    specimen_type_in_test_name = db.Column(
        db.String)  # No for COHB, PRIM due to character limit on instruments; Yes for others

    def __init__(self, **entries):
        self.__dict__.update(entries)


class AssayConstituents(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'assay_constituents'

    assay_constituents_current_assay_constituents = db.relationship('CurrentAssayConstituents',
                                                                    backref='assay_constituents', lazy=True)
    standards = db.relationship('StandardsAndSolutions', backref='constituent', lazy=True)
    solvents_and_reagents = db.relationship('SolventsAndReagents', backref='const', lazy=True)
    sequence_constituents = db.relationship('SequenceConstituents', backref='const', lazy=True)

    name = db.Column(db.String(32), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class DefaultAssayConstituents(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'default_assay_constituents'

    assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'))  # backref = assay
    constituent_id = db.Column(db.String(64))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CurrentAssayConstituents(db.Model, BaseTemplate):
    """
### NOT USED ###

    """

    __tablename__ = 'current_assay_constituents'

    assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'))
    constituent_name = db.Column(db.Integer, db.ForeignKey('assay_constituents.id'))  # Backref = assay_constituents
    constituent_lot = db.Column(db.Integer, db.ForeignKey('standards_and_solutions.id'))
    constituent_status = db.Column(db.Boolean)  # "In Use" in table

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BatchConstituents(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'batch_constituents'

    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    constituent_id = db.Column(db.Integer, db.ForeignKey('standards_and_solutions.id'))  # backref = constituent
    reagent_id = db.Column(db.Integer, db.ForeignKey('solvents_and_reagents.id'))  # backref = reagent
    specimen_check = db.Column(db.String(128))
    specimen_check_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = specimen_checker
    specimen_check_date = db.Column(db.DateTime)
    transfer_check_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    transfer_check_date = db.Column(db.DateTime)
    transfer_check = db.Column(db.String(128))
    sequence_check = db.Column(db.String(32))
    sequence_check_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = sequence_checker
    sequence_check_date = db.Column(db.DateTime)
    gcet_sequence_check = db.Column(db.String(32))
    gcet_sequence_check_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = gcet_checker
    gcet_sequence_check_date = db.Column(db.DateTime)
    constituent_type = db.Column(db.String(64))
    constituent_source = db.Column(db.String(32))
    populated_from = db.Column(db.String(32))
    include_checks = db.Column(db.Boolean)
    load_check = db.Column(db.String(64))
    load_check_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = loader
    load_checked_date = db.Column(db.DateTime)
    vial_position = db.Column(db.Integer)
    label_made = db.Column(db.Boolean)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SequenceConstituents(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'sequence_constituents'

    sequence_name = db.Column(db.String(64))  # Constituent name in the sequence
    solution_type = db.Column(db.Integer, db.ForeignKey('solution_types.id'))  # backref = solution
    constituent_type = db.Column(db.Integer, db.ForeignKey('assay_constituents.id'))  # backref = const
    extracted = db.Column(db.Boolean)  # Determines if standard needs to be checked

    def __init__(self, **entries):
        self.__dict__.update(entries)


#####################################

##### TESTS #####


class Tests(db.Model, BaseTemplate):
    """

    """
    __tablename__ = 'tests'

    tests_results = db.Relationship('Results', backref='test', lazy=True)

    test_id = db.Column(db.String(128))
    test_name = db.Column(db.String(64))
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)  # backref = case
    specimen_id = db.Column(db.Integer, db.ForeignKey('specimens.id'), index=True)  # backref = specimen
    assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'), index=True)
    dilution = db.Column(db.String(10))
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), index=True)  # backref = batch
    test_status = db.Column(db.String(64), index=True)
    directives = db.Column(db.Text)
    specimen_check = db.Column(db.String(32))  # Source check
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = specimen_checker
    checked_date = db.Column(db.DateTime)  # Specimen check
    gcet_specimen_check = db.Column(db.String(32))  # Also used for REF requisition assignment
    gcet_checked_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = gcet_checker
    gcet_checked_date = db.Column(db.DateTime)  # Specimen check
    transfer_check = db.Column(db.String(32))
    transfer_check_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = transfer_checker
    transfer_check_date = db.Column(db.DateTime)
    sequence_check = db.Column(db.String(32))
    sequence_check_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = sequence_checker
    sequence_check_date = db.Column(db.DateTime)
    sequence_check_2 = db.Column(db.String(32))  # Now used for PA check - TLD 02/26/2025
    sequence_check_2_by = db.Column(db.Integer, db.ForeignKey('users.id'),
                                    index=True)  # backref = gcet_sequence_checker
    sequence_check_2_date = db.Column(db.DateTime)
    load_check = db.Column(db.String(32))
    load_check_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # backref = load_checker
    load_checked_date = db.Column(db.DateTime)
    vial_position = db.Column(db.Integer)

    test_comments = db.Relationship('TestComments', backref='test', lazy=True)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class TestComments(db.Model, BaseTemplate):
    """
### NOT USED ###

    """
    __tablename__ = 'test_comments'

    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), index=True)  # backref = test
    test_comment = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### BATCHES #####


class Batches(db.Model, BaseTemplate):
    """

    """

    __tablename__ = "batches"

    batches_tests = db.relationship('Tests', backref='batch', lazy=True)
    batch_constituents = db.relationship('BatchConstituents', backref='batch', lazy=True)
    batch_batch_records = db.relationship('BatchRecords', backref='batch', lazy=True)

    instrument_response_status = db.Column(db.String(32))  # Delete
    instrument_rt_status = db.Column(db.String(32))  # Delete
    extraction_response_status = db.Column(db.String(32))  # Delete
    extraction_rt_status = db.Column(db.String(32))  # Delete

    batch_id = db.Column(db.String(32))
    assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'))
    gcdp_assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'))
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'))
    instrument_2_id = db.Column(db.Integer, db.ForeignKey('instruments.id'))
    batch_template_id = db.Column(db.Integer, db.ForeignKey('batch_templates.id'))
    test_count = db.Column(db.Integer)
    extracted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = extractor
    extraction_date = db.Column(db.DateTime)  # start datetime
    extraction_finish_date = db.Column(db.DateTime)  # finish datetime
    extracted_by_2_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = extractor_2
    extraction_date_2 = db.Column(db.DateTime)  # start datetime
    extraction_finish_date_2 = db.Column(db.DateTime)  # finish datetime
    extracted_by_3_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = extractor_3
    extraction_date_3 = db.Column(db.DateTime)  # start datetime
    extraction_finish_date_3 = db.Column(db.DateTime)  # finish datetime
    checked_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    checked_date = db.Column(db.DateTime)
    processed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = processor
    process_date = db.Column(db.DateTime)  # start datetime
    process_finish_date = db.Column(db.DateTime)  # finish datetime
    processed_by_2_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = processor_2
    process_date_2 = db.Column(db.DateTime)  # start datetime
    process_finish_date_2 = db.Column(db.DateTime)  # finish datetime
    processed_by_3_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = processor_3
    process_date_3 = db.Column(db.DateTime)  # start datetime
    process_finish_date_3 = db.Column(db.DateTime)  # finish datetime
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = batch_reviewer
    review_date = db.Column(db.DateTime)  # start datetime
    review_finish_date = db.Column(db.DateTime)  # finish datetime
    reviewed_by_2_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_date_2 = db.Column(db.DateTime)  # start datetime
    review_finish_date_2 = db.Column(db.DateTime)  # finish datetime
    reviewed_by_3_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_date_3 = db.Column(db.DateTime)  # start datetime
    review_finish_date_3 = db.Column(db.DateTime)  # finish datetime
    batch_status = db.Column(db.String(32))
    instrument_check = db.Column(db.String(64))
    instrument_check_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = inst_check
    instrument_check_date = db.Column(db.DateTime)
    extraction_check = db.Column(db.String(64))
    extraction_check_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = ext_check
    extraction_check_date = db.Column(db.DateTime)
    lablink_uploaded = db.Column(db.String(16))
    directives = db.Column(db.Text)
    tandem_id = db.Column(db.Integer)
    technique = db.Column(db.Text)
    transfer_check = db.Column(db.String(32))
    pipettes = db.Column(db.String(128))

    batch_comments = db.relationship('BatchComments', backref='batch', lazy=True)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BatchComments(db.Model, BaseTemplate):
    """
### NOT USED ###

    """

    __tablename__ = 'batch_comments'

    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))  # backref = batch
    reference = db.Column(db.Boolean)  # Is the comment from the reference table?
    comment_reference = db.Column(db.Integer, db.ForeignKey('batch_comments_reference.id'))  # backref = comment
    comment_text = db.Column(db.Text)
    report = db.Column(db.Boolean)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BatchCommentsReference(db.Model, BaseTemplate):
    """
### NOT USED ###

    """

    __tablename__ = 'batch_comments_reference'

    batch_comments = db.relationship('BatchComments', backref='comment', lazy=True)

    comment = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BatchTemplates(db.Model, BaseTemplate):
    """

    """

    __tablename__ = "batch_templates"

    batch_template_assays = db.relationship('Assays', backref='batch_template', lazy=True)
    batch_templates_batches = db.relationship('Batches', backref='batch_template', lazy=True)
    batch_template_sequence_header_mapping = db.relationship('SequenceHeaderMappings', backref='batch_template',
                                                             lazy=True)

    name = db.Column(db.String(32))
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'))
    sample_format_id = db.Column(db.Integer, db.ForeignKey('sample_formats.id'))
    max_samples = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SequenceHeaderMappings(db.Model, BaseTemplate):
    """

    """

    __tablename__ = "sequence_header_mappings"

    id = db.Column(db.Integer, primary_key=True)
    db_status = db.Column(db.String(32))
    batch_template_id = db.Column(db.Integer, db.ForeignKey('batch_templates.id'))
    sample_name = db.Column(db.String(64))
    sample_type = db.Column(db.String(64))
    acq_method = db.Column(db.String(64))
    vial_position = db.Column(db.String(64))
    data_file = db.Column(db.String(64))
    dilution = db.Column(db.String(64))
    comments = db.Column(db.String(64))
    custom1 = db.Column(db.String(64))
    custom2 = db.Column(db.String(64))
    custom3 = db.Column(db.String(64))
    custom4 = db.Column(db.String(64))
    custom5 = db.Column(db.String(64))
    custom6 = db.Column(db.String(64))
    custom7 = db.Column(db.String(64))
    custom8 = db.Column(db.String(64))
    custom9 = db.Column(db.String(64))
    custom10 = db.Column(db.String(64))
    custom11 = db.Column(db.String(64))
    custom12 = db.Column(db.String(64))
    custom13 = db.Column(db.String(64))
    custom14 = db.Column(db.String(64))
    custom15 = db.Column(db.String(64))
    header_list = db.Column(db.String)
    communications = db.Column(db.Text)
    delete_reason = db.Column(db.Text)
    revision = db.Column(db.Integer)
    create_date = db.Column(db.DateTime)
    created_by = db.Column(db.String(128))
    modify_date = db.Column(db.DateTime)
    modified_by = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SampleFormats(db.Model, BaseTemplate):
    __tablename__ = "sample_formats"

    formats_batch_templates = db.relationship('BatchTemplates', backref='format', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BatchRecords(db.Model, BaseTemplate):
    """

    """

    __tablename__ = "batch_records"

    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    title = db.Column(db.String)
    file_name = db.Column(db.String(512))
    file_type = db.Column(db.String)
    file_path = db.Column(db.String(512))

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### RESULTS #####


class Results(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'results'

    results_pt = db.relationship('PTResults', backref='result', lazy=True)
    report_results_results = db.relationship("ReportResults", backref="result", lazy=True)

    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'))  # backref = test
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), index=True)
    component_name = db.Column(db.String(512))
    scope_id = db.Column(db.Integer, db.ForeignKey('scope.id'))
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    result_status = db.Column(db.String(128))
    result = db.Column(db.NVARCHAR(128))
    supplementary_result = db.Column(db.NVARCHAR(128))
    concentration = db.Column(db.Float)
    measurement_uncertainty = db.Column(db.Float)
    result_type = db.Column(db.String(32))
    qualitative = db.Column(db.String(32))
    qualitative_reason = db.Column(db.String(128))
    report_reason = db.Column(db.NVARCHAR(128))
    result_comments_manual = db.Column(db.Text)
    sample_comments_manual = db.Column(db.Text)
    test_comments_manual = db.Column(db.Text)
    component_comments_manual = db.Column(db.Text)
    comment_numbers = db.Column(db.String)
    reported = db.Column(db.String(32))  # populated based on user action, possible values "Y" or null
    primary = db.Column(db.String)
    result_status_updated = db.Column(db.String)
    result_status_update_reason = db.Column(db.Text)
    result_type_updated = db.Column(db.String)
    result_type_update_reason = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class PTCases(db.Model, BaseTemplate):
    """


    """

    __tablename__ = 'pt_cases'

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'))  # backref = case

    PT_status = db.Column(db.String(16))  # not being used
    challenges = db.Column(db.String(1024))
    summary = db.Column(db.String(1024))
    percent_max = db.Column(db.String(32))
    z_max = db.Column(db.String(32))

    good_qual_comment = db.Column(db.Text)
    good_quant_comment = db.Column(db.Text)
    bad_quant_comment = db.Column(db.Text)
    bad_FN_comment = db.Column(db.Text)
    bad_FP_comment = db.Column(db.Text)
    incidental_neutral_comment = db.Column(db.Text)
    beyondscope_good_comment = db.Column(db.Text)
    incidental_good_comment = db.Column(db.Text)
    incidental_bad_comment = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class PTResults(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'pt_results'

    # relationships are declared in the other source tables (cases, results)
    #   cases_pt = db.relationship('ProficiencyTests', backref='case', lazy=True)
    #   results_pt = db.relationship('ProficiencyTests', backref='result', lazy=True)

    # only columns linking the tables need to be called here - everything else comes with it
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'))  # backref = case
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'))  # backref = result
    pt_component_id = db.Column(db.Integer, db.ForeignKey('components.id'))  # backref = component
    pt_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))  # backref = unit; when units are different

    # unique to PT
    eval_date = db.Column(db.DateTime)
    result_official = db.Column(
        db.Integer)  # id of official result within PTResults TODO replace by trigger from T1 drafting process
    pt_reported = db.Column(db.String(32))  # concentration when units are different; not currently used

    target = db.Column(db.Float)
    target_percent = db.Column(db.Float)  # calc'd
    median = db.Column(db.Float)
    median_percent = db.Column(db.Float)  # calc'd
    mean_all = db.Column(db.Float)
    mean_all_percent = db.Column(db.Float)  # calc'd
    sd_all = db.Column(db.Float)
    z_all = db.Column(db.Float)  # calc'd
    mean_sub = db.Column(db.Float)
    mean_sub_percent = db.Column(db.Float)  # calc'd
    sd_sub = db.Column(db.Float)
    z_sub = db.Column(db.Float)  # calc'd

    eval_informal = db.Column(db.String(32))  # True or False

    eval_manual_min = db.Column(db.Float)
    eval_manual_max = db.Column(db.Float)

    eval_A_ref = db.Column(db.String(32))
    eval_B_ref = db.Column(db.String(32))  # single-select: target, median, all, sub

    eval_overall_conclusion = db.Column(db.String(32))  # calc'd
    eval_ABFT_conclusion = db.Column(db.String(32))  # calc'd
    eval_ABFT_display = db.Column(db.String(32))  # calc'd
    eval_FLD_conclusion = db.Column(db.String(32))

    pt_reporting_limit = db.Column(db.Float)  # not always provided; thus, optional
    pt_participants = db.Column(db.String(32))  # manual entry of either 'n of N' or '%' ex: 11 of 67; OR, 23%

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Reports(db.Model, BaseTemplate):
    __tablename__ = 'reports'

    reports_contents = db.relationship("ReportResults", backref='report', lazy=True)
    report_comments = db.relationship('ReportComments', backref='report', lazy=True)

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'))
    report_template_id = db.Column(db.Integer, db.ForeignKey('report_templates.id'))
    # record_template_id = db.Column(db.Integer, db.ForeignKey('record_templates.id'))
    report_status = db.Column(db.String(32))
    report_name = db.Column(db.String(32))
    file_name = db.Column(db.String)
    discipline = db.Column(db.String)
    report_number = db.Column(db.Integer)
    draft_number = db.Column(db.Integer)
    case_review = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    case_review_date = db.Column(db.DateTime)
    divisional_review = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    divisional_review_date = db.Column(db.DateTime)
    record_id = db.Column(db.Integer, db.ForeignKey('records.id'))
    assigned_dr = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_cr = db.Column(db.Integer, db.ForeignKey('users.id'))
    reverted_by = db.Column(db.String)
    revert_date = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class ReportTemplates(db.Model, BaseTemplate):
    """

    """

    report_templates_reports = db.relationship('Reports', backref='report_template', lazy=True)
    report_templates_case_types_toxicology = db.relationship('CaseTypes', backref='toxicology_template', lazy=True,
                                                             foreign_keys='CaseTypes.toxicology_report_template_id')
    report_templates_case_types_biochemistry = db.relationship('CaseTypes', backref='biochemistry_template', lazy=True,
                                                               foreign_keys='CaseTypes.biochemistry_report_template_id')
    report_templates_case_types_histology = db.relationship('CaseTypes', backref='histology_template', lazy=True,
                                                            foreign_keys='CaseTypes.histology_report_template_id')
    report_templates_case_types_external = db.relationship('CaseTypes', backref='external_template', lazy=True,
                                                           foreign_keys='CaseTypes.external_report_template_id')

    __tablename__ = 'report_templates'

    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    name = db.Column(db.String(128))
    discipline = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class ReportResults(db.Model, BaseTemplate):
    __tablename__ = 'report_results'

    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'))
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'))
    primary_result = db.Column(db.String)
    supplementary_result = db.Column(db.String)
    observed_result = db.Column(db.String)
    qualitative_result = db.Column(db.String)
    approximate_result = db.Column(db.String)
    order = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class ReportComments(db.Model, BaseTemplate):
    __tablename__ = 'report_comments'

    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comment_instances.id'))  # backref = comment
    order = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### RECORDS #####

class Records(db.Model, BaseTemplate):
    """

    """
    __tablename__ = "records"

    records_reports = db.relationship('Reports', backref='record', lazy=True)
    records_litigation_packets = db.relationship('LitigationPackets', backref='record', lazy=True)
    dissemination = db.relationship('Disseminations', backref='record', lazy=True)

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)
    record_status = db.Column(db.String(32))
    record_name = db.Column(db.String, unique=True)
    record_type = db.Column(db.Integer, db.ForeignKey('record_types.id'))
    record_number = db.Column(db.Integer)
    discipline = db.Column(db.String(32))
    dissemination_date = db.Column(db.DateTime)
    disseminated_by = db.Column(db.String(32))
    disseminated_to = db.Column(db.Text)
    fa_OR_version = db.Column(db.Integer)           ### fa_OR = Forensic Advantage, Object Repository
    fa_OR_importDate = db.Column(db.DateTime)       ### importDate of Autopsy Report is effectively the case closure date
    fa_OR_name = db.Column(db.String(32))           ### admin review cases don't get Autopsy Reports
    fa_OR_description = db.Column(db.String(64))
    fa_OR_importedBy = db.Column(db.String(64))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class RecordTypes(db.Model, BaseTemplate):
    """

    """

    types_records = db.relationship('Records', backref='type', lazy=True)

    __tablename__ = 'record_types'

    name = db.Column(db.String(128))
    suffix = db.Column(db.String(64))
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitigationPacketTemplates(db.Model, BaseTemplate):
    """

    """

    lit_templates_lit_packets = db.relationship('LitigationPackets', backref='temp', lazy=True)
    lit_templates_case_types = db.relationship('CaseTypes', backref='temp', lazy=True)

    __tablename__ = 'litigation_packet_templates'

    name = db.Column(db.String(128))
    path = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitigationPacketRequest(db.Model, BaseTemplate):
    """
    Model for tracking scheduled requests for litigation packets."""

    __tablename__ = 'litigation_packet_request'

    # id = db.Column(db.Integer, primary_key=True)
    redact = db.Column(db.Boolean, default=False)
    remove_pages = db.Column(db.Boolean, default=False)
    scheduled_exec = db.Column(db.DateTime) # should never trigger default
    status = db.Column(Enum('Scheduled', 'Processing', 'Success', 'Fail', name='status_enum'), default='Scheduled')
    requested_by = db.Column(db.String(50))  # if you have login system
    item_id = db.Column(db.Integer)  # if you have items to link to
    template_id = db.Column(db.Integer, db.ForeignKey('lit_packet_admin_templates.id'))  # backref = template
    packet_name = db.Column(db.String(64))
    zip = db.Column(db.String(256))
    packet_id = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)

class LitigationPackets(db.Model, BaseTemplate):

    """
    Now referred to as just Packets
    ------------------------------
    Statuses:
    - Created
    - Ready for PP
    - Waiting for Declaration
    - Ready for PR
    - Finalized 

    """

    __tablename__ = "litigation_packets"

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'))
    template_id = db.Column(db.Integer, db.ForeignKey('litigation_packet_templates.id'))
    packet_name = db.Column(db.String(32))
    packet_number = db.Column(db.Integer)
    file_name = db.Column(db.String)
    requested_date = db.Column(db.DateTime)
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))
    personnel_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    del_agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # delivered agency
    del_division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # delivered division
    del_personnel_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # delivered personnel
    due_date = db.Column(db.DateTime)
    delivery_date = db.Column(db.DateTime)
    delivered_to = db.Column(db.String(128))
    n_pages = db.Column(db.Integer)
    postage_and_delivery = db.Column(db.String(32))
    additional_costs = db.Column(db.String(32))
    total_costs = db.Column(db.String(32))
    paid_date = db.Column(db.DateTime)
    prepared_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    record_id = db.Column(db.Integer, db.ForeignKey('records.id'))
    subpoena_path = db.Column(db.Text)
    subpoena_file = db.Column(db.String(264))
    completed_packet_path = db.Column(db.String(264))
    packet_status = db.Column(db.String(128))
    litigation_preparer = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = prep_user
    litigation_prepare_date = db.Column(db.DateTime)
    litigation_reviewer = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = rev_user
    litigation_review_date = db.Column(db.DateTime)
    declaration_sent_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # user who sent declaration request 
    declaration_sent_datetime = db.Column(db.DateTime) # date declaration request is sent

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Bookings(db.Model, BaseTemplate):
    """

    """

    __tablename__ = "bookings"

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)  # backref = case
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = expert
    date = db.Column(db.DateTime) #used as start datetime
    finish_datetime = db.Column(db.DateTime)
    purpose_id = db.Column(db.Integer, db.ForeignKey('booking_purposes.id'))  # backref = purpose
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = agency_A
    personnel_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # backref = person_A1
    personnelA2_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # backref = person_A2
    change_id = db.Column(db.Integer, db.ForeignKey('booking_changes.id'))  # backref = change
    format_id = db.Column(db.Integer, db.ForeignKey('booking_formats.id'))  # backref = format
    location = db.Column(db.Integer, db.ForeignKey('booking_locations.id'))  # backref = book_location
    others_present = db.Column(db.String(64))
    cross_examined = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = agency_B
    personnelB1_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # backref = person_B1
    personnelB2_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # backref = person_B2
    start = db.Column(db.String(32))
    finish = db.Column(db.String(32))
    drive_time = db.Column(db.String(32)) #duration
    excluded_time = db.Column(db.String(32)) #duration
    waiting_time = db.Column(db.String(32)) #duration
    total_testifying_time = db.Column(db.String(32)) #duration
    total_work_time = db.Column(db.String(32)) #duration
    legacy_transferred = db.Column(db.String(32))
    information_provider = db.Column(db.String(32))
    topics_discussed = db.Column(db.String(32))
    narrative = db.Column(db.Text)
    booking_comment = db.Column(db.Text)
    type_id = db.Column(db.Integer, db.ForeignKey('booking_types.id'))  # backref = type
    jurisdiction_id = db.Column(db.Integer, db.ForeignKey('booking_jurisdiction.id'))  # backref = jurisdiction

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingTypes(db.Model, BaseTemplate):
    __tablename__ = 'booking_types'

    types_bookings = db.relationship('Bookings', backref='type', lazy=True)
    name = db.Column(db.String(128), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingJurisdiction(db.Model, BaseTemplate):
    __tablename__ = 'booking_jurisdiction'

    jurisdiction_bookings = db.relationship('Bookings', backref='jurisdiction', lazy=True)
    name = db.Column(db.String(128), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingChanges(db.Model, BaseTemplate):
    __tablename__ = "booking_changes"

    changes_bookings = db.relationship('Bookings', backref='change', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingPurposes(db.Model, BaseTemplate):
    __tablename__ = "booking_purposes"

    purposes_bookings = db.relationship('Bookings', backref='purpose', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingLocations(db.Model, BaseTemplate):
    __tablename__ = "booking_locations"

    locations_bookings = db.relationship('Bookings', backref='book_location', lazy=True,
                                         foreign_keys='Bookings.location')

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingFormats(db.Model, BaseTemplate):
    __tablename__ = "booking_formats"

    formats_bookings = db.relationship('Bookings', backref='format', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingInformationProvider(db.Model, BaseTemplate):
    __tablename__ = 'booking_information_provider'

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BookingInformationProvided(db.Model, BaseTemplate):
    __tablename__ = 'booking_information_provided'

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### TTEE #####
class TTEE(db.Model):
    """

    """

    __tablename__ = "ttee"

    id = db.Column(db.Integer, primary_key=True)
    db_status = db.Column(db.String(32))
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'))
    requester_name = db.Column(db.String(64))
    agency_id = db.Column(db.String(32))
    email_date = db.Column(db.DateTime)
    emailed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    file_path = db.Column(db.String(512))
    communications = db.Column(db.Text)
    delete_reason = db.Column(db.Text)
    revision = db.Column(db.Integer)
    create_date = db.Column(db.DateTime)
    created_by = db.Column(db.String(128))
    modify_date = db.Column(db.DateTime)
    modified_by = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


##### EVIDENCE COMMENTS #####


class EvidenceCommentsReference(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'evidence_comments_reference'

    type = db.Column(db.String(64))
    name = db.Column(db.String(128))
    code = db.Column(db.String(16))
    parent_section = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class EvidenceComments(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'evidence_comments'

    accession_number = db.Column(db.String(32))
    case_number = db.Column(db.Integer, db.ForeignKey('cases.id'))
    code = db.Column(db.String(32))
    statement = db.Column(db.String(512))  # Sentence form
    comment = db.Column(db.String(128))
    submitter_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    submitter_name = db.Column(db.String)
    submitter_division = db.Column(db.String)
    submitter_agency = db.Column(db.String)

    __table_args__ = (UniqueConstraint('accession_number', 'code', name='uix_accession-number_code'),)

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## RESOURCES ##############


class ReferenceMaterials(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'reference_materials'
    resource_level = 'tertiary'

    name = db.Column(db.String(128))
    status = db.Column(db.String(32))
    compound_id = db.Column(db.Integer, db.ForeignKey('compounds.id'))
    set = db.Column(db.String(8))
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # reference material provider
    product_no = db.Column(db.String(128))
    lot_no = db.Column(db.String(128))
    salt_id = db.Column(db.Integer, db.ForeignKey('salts.id'))
    correction_factor = db.Column(db.Float)
    state_id = db.Column(db.Integer, db.ForeignKey('states_of_matter.id'))
    solvent_id = db.Column(db.Integer, db.ForeignKey('reference_material_solvents.id'))
    amount = db.Column(db.String(32))
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    storage_temperature_id = db.Column(db.Integer, db.ForeignKey('storage_temperatures.id'))
    received_date = db.Column(db.DateTime)
    received_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    expire_retest = db.Column(db.String(64))
    expire_retest_date = db.Column(db.DateTime)
    cert_of_analysis = db.Column(db.String(128))
    opened_date = db.Column(db.DateTime)
    opened_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    discard_date = db.Column(db.DateTime)
    discarded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class RefMatSolvents(db.Model, BaseTemplate):
    """
    List of reference material solvents.

    Columns:
        name (str): the name of the solvent.
        abbreviation (str): the abbreviation of the solvent.

    Backrefs
        solvent: ReferenceMaterials

    """

    __tablename__ = 'reference_material_solvents'

    refmatsolvents = db.relationship('ReferenceMaterials', backref='solvent', lazy=True)

    name = db.Column(db.String(128))
    abbreviation = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class StatesOfMatter(db.Model, BaseTemplate):
    __tablename__ = 'states_of_matter'

    states_specimen_types = db.relationship('SpecimenTypes', backref='state', lazy=True)
    states_reference_materials = db.relationship('ReferenceMaterials', backref='state', lazy=True)
    # preparations_specimens = db.relationship('SpecimenTypes', backref='preparation', lazy=True)

    name = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Compounds(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'compounds'

    compounds_reference_materials = db.relationship('ReferenceMaterials', backref='compound', lazy=True)
    compounds_component_reference = db.relationship('CompoundsComponentsReference', backref='compound', lazy=True)

    name = db.Column(db.String(128))
    synonyms = db.Column(db.String(1024))
    code = db.Column(db.String(16), unique=True)
    inventory_add_date = db.Column(db.DateTime)
    drug_class_id = db.Column(db.Integer, db.ForeignKey('drug_classes.id'))
    drug_monograph_id = db.Column(db.Integer)  # , db.ForeignKey('drug_monographs.id'))
    # parent_metabolite = db.Column(db.String(128))
    # parent_id = db.Column(db.String(128))
    iupac = db.Column(db.String(512))
    cas_no = db.Column(db.String(128))
    formula = db.Column(db.String(128))
    mass = db.Column(db.String(32))
    inchikey = db.Column(db.String(32))
    smiles = db.Column(db.String(256))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CompoundsComponentsReference(db.Model):
    """

    """

    __tablename__ = 'compounds_components_reference'

    id = db.Column(db.Integer, primary_key=True)
    compound_id = db.Column(db.Integer, db.ForeignKey('compounds.id'))
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'))
    create_date = db.Column(db.DateTime)
    created_by = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Components(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'components'

    components_results = db.relationship('Results', backref='component', lazy=True)
    components_compound_reference = db.relationship('CompoundsComponentsReference', backref='component', lazy=True)
    components_scope = db.relationship('Scope', backref='component', lazy=True)
    components_pt = db.relationship('PTResults', backref='component', lazy=True)

    name = db.Column(db.String(512), unique=True)
    component_drug_class = db.Column(db.String(128))
    drug_class_id = db.Column(db.Integer, db.ForeignKey('drug_classes.id'))
    rank = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Scope(db.Model, BaseTemplate):
    """

    """

    scope_results = db.relationship('Results', backref='scope', lazy=True)

    __tablename__ = 'scope'

    component_id = db.Column(db.Integer, db.ForeignKey('components.id'))
    assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'))
    limit_of_detection = db.Column(db.String(32))
    internal_standard = db.Column(db.String(8))
    internal_standard_conc = db.Column(db.String(32))
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    validated = db.Column(db.String(32))
    report_notes = db.Column(db.Text)
    standard_name_1 = db.Column(db.String(32))
    standard_conc_1 = db.Column(db.String(32))
    standard_name_2 = db.Column(db.String(32))
    standard_conc_2 = db.Column(db.String(32))
    standard_name_3 = db.Column(db.String(32))
    standard_conc_3 = db.Column(db.String(32))
    standard_name_4 = db.Column(db.String(32))
    standard_conc_4 = db.Column(db.String(32))
    standard_name_5 = db.Column(db.String(32))
    standard_conc_5 = db.Column(db.String(32))
    standard_name_6 = db.Column(db.String(32))
    standard_conc_6 = db.Column(db.String(32))
    standard_name_7 = db.Column(db.String(32))
    standard_conc_7 = db.Column(db.String(32))
    standard_name_8 = db.Column(db.String(32))
    standard_conc_8 = db.Column(db.String(32))
    standard_name_9 = db.Column(db.String(32))
    standard_conc_9 = db.Column(db.String(32))
    standard_name_10 = db.Column(db.String(32))
    standard_conc_10 = db.Column(db.String(32))
    standard_name_11 = db.Column(db.String(32))
    standard_conc_11 = db.Column(db.String(32))
    standard_name_12 = db.Column(db.String(32))
    standard_conc_12 = db.Column(db.String(32))
    standard_name_13 = db.Column(db.String(32))
    standard_conc_13 = db.Column(db.String(32))
    standard_name_14 = db.Column(db.String(32))
    standard_conc_14 = db.Column(db.String(32))
    standard_name_15 = db.Column(db.String(32))
    standard_conc_15 = db.Column(db.String(32))
    standard_name_16 = db.Column(db.String(32))
    standard_conc_16 = db.Column(db.String(32))
    standard_name_17 = db.Column(db.String(32))
    standard_conc_17 = db.Column(db.String(32))
    standard_name_18 = db.Column(db.String(32))
    standard_conc_18 = db.Column(db.String(32))
    standard_name_19 = db.Column(db.String(32))
    standard_conc_19 = db.Column(db.String(32))
    standard_name_20 = db.Column(db.String(32))
    standard_conc_20 = db.Column(db.String(32))

    __table_args__ = (UniqueConstraint('component_id', 'assay_id', name='uix_component-id_assay-id'),)

    rank = db.Column(db.Integer)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class ComponentConcentrations(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'component_concentrations'

    component_id = db.Column(db.Integer)
    standard_name = db.Column(db.String(512))
    standard_conc = db.Column(db.String(32))
    assay_id = db.Column(db.Integer, db.ForeignKey('assays.id'))
    compound_id = db.Column(db.Integer, db.ForeignKey('compounds.id'))
    compound_code = db.Column(db.String(32))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class DrugClasses(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'drug_classes'

    drug_classes_compounds = db.relationship('Compounds', backref='drug_class', lazy=True)
    drug_classes_components = db.relationship('Components', backref='drug_class', lazy=True)

    name = db.Column(db.String(128), unique=True)
    pm_rank = db.Column(db.Integer)
    m_d_rank = db.Column(db.Integer)
    x_rank = db.Column(db.Integer)
    q_rank = db.Column(db.Integer)
    scope_rank = db.Column(db.Integer)
    compound_counts = db.Column(db.Integer)
    component_counts = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class StandardsAndSolutions(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'standards_and_solutions'
    resource_level = 'tertiary'

    batch_constituents = db.relationship('BatchConstituents', backref='constituent', lazy=True)

    name = db.Column(db.Integer, db.ForeignKey('assay_constituents.id'))  # Backref = constituent
    lot = db.Column(db.String(256), unique=True)
    prepared_date = db.Column(db.DateTime)
    prepared_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Backref = prep_by
    solution_type_id = db.Column(db.Integer, db.ForeignKey('solution_types.id'))  # Backref = type
    concentrator_multiplier = db.Column(db.String(128))
    parent_standard_lot = db.Column(db.Integer)
    retest_date = db.Column(db.DateTime)
    authorized_date = db.Column(db.DateTime)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    equipment_used = db.Column(db.String(128))
    volume_prepared = db.Column(db.Float)
    solvent_used = db.Column(db.Integer, db.ForeignKey('solvents_and_reagents.id'))
    aliquot_volume = db.Column(db.Integer)
    total_aliquots = db.Column(db.Integer)
    pipette_check = db.Column(db.Boolean)
    verification_batches = db.Column(db.String(128))
    verification_comments = db.Column(db.Text)
    previous_lot = db.Column(db.Text)
    previous_lot_comments = db.Column(db.Text)
    qualitative_comments = db.Column(db.Text)
    qualitative_attachments = db.Column(db.String(256))
    calibration_comments = db.Column(db.Text)
    calibration_attachments = db.Column(db.String(256))
    quantitative_comments = db.Column(db.Text)
    quantitative_attachments = db.Column(db.String(256))
    additional_comments = db.Column(db.Text)
    part_a = db.Column(db.String(256))  # Reference SolventsAndReagents name
    part_a_lot = db.Column(db.String(256))  # Reference SolventsAndReagents lot
    part_a_exp = db.Column(db.DateTime)  # Reference SolventsAndReagents expiry
    part_a_table = db.Column(db.String(256))  # Store table_name
    part_a_id = db.Column(db.Integer)  # Store table_id
    no_part_a_exp = db.Column(db.String(256))  # To store "N/A" if there is no exp for part a
    part_b = db.Column(db.String(256))  # See above
    part_b_lot = db.Column(db.String(256))  # See above
    part_b_exp = db.Column(db.DateTime)  # See above
    part_b_table = db.Column(db.String(256))  # Store table_name
    part_b_id = db.Column(db.Integer)  # Store table_id
    no_part_b_exp = db.Column(db.String(256))  # See above
    part_c = db.Column(db.String(256))  # See above
    part_c_lot = db.Column(db.String(256))  # See above
    part_c_exp = db.Column(db.DateTime)  # See above
    part_c_table = db.Column(db.String(256))  # Store table_name
    part_c_id = db.Column(db.Integer)  # Store table_id
    no_part_c_exp = db.Column(db.String(256))  # See above
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    series = db.Column(db.Integer)
    assay = db.Column(db.String(128))
    in_use = db.Column(db.Boolean)
    two_analyst = db.Column(db.Boolean)  # Was the standard extracted by two different analysts
    preservatives = db.Column(db.Integer, db.ForeignKey('preservatives.id'))  # backref = preservative
    location_type = db.Column(db.String(256))
    location = db.Column(db.String(256))
    description = db.Column(db.String(256))
    approve_date = db.Column(db.DateTime)
    component = db.Column(db.String(256))

    storage_location = db.Column(db.Integer, db.ForeignKey('cooled_storage.id'))  # DELETE
    current_assay = db.relationship('CurrentAssayConstituents', backref='standards', lazy=True)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)

    # this just allows us to print the object in a more readable way
    def __repr__(self):
        return f"<StandardsAndSolutions id={self.id} name={self.name}>"


class SolutionTypes(db.Model, BaseTemplate):
    __tablename__ = 'solution_types'

    standards_and_solutions = db.relationship('StandardsAndSolutions', backref='type', lazy=True)
    solvents_and_reagents = db.relationship('SolventsAndReagents', backref='type', lazy=True)
    sequence_constituents = db.relationship('SequenceConstituents', backref='solution', lazy=True)

    name = db.Column(db.String(128), unique=True)
    constituents = db.Column(db.String(128))
    expected_fields = db.Column(db.Text)
    requires_admin = db.Column(db.Boolean)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SolventsAndReagents(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'solvents_and_reagents'
    resource_level = 'tertiary'

    solvent = db.relationship('StandardsAndSolutions', backref='solvent', lazy=True)
    reagent = db.relationship('BatchConstituents', backref='reagent', lazy=True)

    name = db.Column(db.String(64))  # Used to display name
    lot = db.Column(db.String(32))
    exp_date = db.Column(db.DateTime)
    solution_type_id = db.Column(db.Integer, db.ForeignKey('solution_types.id'))  # Backref = type
    constituent = db.Column(db.Integer, db.ForeignKey('assay_constituents.id'))  # backref = const
    # location = db.Column(db.String(32))  # Reference Infrastructure
    recd_date = db.Column(db.DateTime)
    recd_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Backref = solv_receiver
    opened_date = db.Column(db.DateTime)  # Need?
    opened_by = db.Column(db.String(32))  # Need?
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))
    description = db.Column(db.String(64))
    in_use = db.Column(db.Boolean)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CalibratedLabware(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'calibrated_labware'
    resource_level = 'tertiary'
    __itemname__ = 'Calibrated Labware'

    equipment_id = db.Column(db.String(64), unique=True)
    serial_number = db.Column(db.String(64))
    acquired_date = db.Column(db.DateTime)
    last_service_date = db.Column(db.DateTime)
    due_service_date = db.Column(db.DateTime)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = division
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    model_number = db.Column(db.String(64))
    type_id = db.Column(db.Integer, db.ForeignKey('calibrated_labware_types.id'))
    low_range = db.Column(db.String(64))
    high_range = db.Column(db.String(64))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    pressure = db.Column(db.String(64))  # DELETE
    last_cal_date = db.Column(db.DateTime)  # DELETE
    cal_exp = db.Column(db.DateTime)  # DELETE
    part_number = db.Column(db.String(64)) # TO DELETE
    manufacturer = db.Column(db.String(64))  # TO DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CalibratedLabwareTypes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'calibrated_labware_types'

    calibrated_labware = db.relationship('CalibratedLabware', backref='type', lazy=True)

    name = db.Column(db.String(64))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class GeneralLabware(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'general_labware'
    resource_level = 'tertiary'
    __itemname__ = 'General Labware'

    equipment_id = db.Column(db.String(64), unique=True)
    model = db.Column(db.String(64))
    serial_number = db.Column(db.String(64))
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    last_serviced_date = db.Column(db.DateTime)  # aka last_service_date
    due_service_date = db.Column(db.DateTime)
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string
    type_id = db.Column(db.Integer, db.ForeignKey('general_labware_types.id'))
    date_acquired = db.Column(db.DateTime)

    name = db.Column(db.String(64), unique=True)  # DELETE, also in views.py and forms.py
    description = db.Column(db.String(128))  # DELETE
    quantity = db.Column(db.Integer)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class GeneralLabwareTypes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'general_labware_types'

    general_labware = db.relationship('GeneralLabware', backref='type', lazy=True)

    name = db.Column(db.String(64))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Probes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'probes'
    resource_level = 'tertiary'
    __itemname__ = 'Probes'

    equipment_id = db.Column(db.String(128))
    serial_number = db.Column(db.String(128))
    glycol = db.Column(db.String(128))
    model = db.Column(db.String(64))
    cims = db.Column(db.String(256))
    hub_id = db.Column(db.Integer, db.ForeignKey('hubs.id'))  # backref=hub
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))
    last_service_date = db.Column(db.DateTime)
    due_service_date = db.Column(db.DateTime)
    acquired_date = db.Column(db.DateTime)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Hubs(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'hubs'
    resource_level = 'tertiary'

    probes = db.relationship('Probes', backref='hub', lazy=True)

    equipment_id = db.Column(db.String(128))
    model_number = db.Column(db.String(128))
    serial_number = db.Column(db.String(128))  # MAC Address
    ip_address = db.Column(db.String(128))
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = division
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string
    acquired_date = db.Column(db.DateTime)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class HistologyEquipment(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'histology_equipment'
    resource_level = 'tertiary'
    __itemname__ = 'Histology Equipment'

    equipment_id = db.Column(db.String(64), unique=True)
    serial_number = db.Column(db.String(64))
    model = db.Column(db.String(64))
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    type_id = db.Column(db.Integer, db.ForeignKey('histology_equipment_types.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = vendor
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = agency
    date_acquired = db.Column(db.DateTime)
    last_service_date = db.Column(db.DateTime)
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string
    due_service_date = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class HistologyEquipmentTypes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'histology_equipment_types'

    histology_equipment = db.relationship('HistologyEquipment', backref='type', lazy=True)

    name = db.Column(db.String(64))

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## INFRASTRUCTURE ##############


class Instruments(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'instruments'
    resource_level = 'tertiary'
    __itemname__ = 'Instruments'
    __itemtype__ = "Instrument"

    instruments_assays = db.relationship('Assays', backref='instrument', lazy=True)
    instruments_batches = db.relationship('Batches', backref='instrument', lazy=True,
                                          foreign_keys='Batches.instrument_id')
    instruments_2_batches = db.relationship('Batches', backref='instrument_2', lazy=True,
                                            foreign_keys='Batches.instrument_2_id')
    instruments_batch_templates = db.relationship('BatchTemplates', backref='instrument', lazy=True)

    instrument_id = db.Column(db.String(32), unique=True)  # LCMS7
    instrument_type_id = db.Column(db.Integer, db.ForeignKey('instrument_types.id'))  # backref = type
    acquired_date = db.Column(db.DateTime)
    last_service_date = db.Column(db.DateTime)
    due_service_date = db.Column(db.DateTime)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = vendor
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    module_model_1 = db.Column(db.String(128))
    module_serial_1 = db.Column(db.String(128))
    module_model_2 = db.Column(db.String(128))
    module_serial_2 = db.Column(db.String(128))
    module_model_3 = db.Column(db.String(128))
    module_serial_3 = db.Column(db.String(128))
    module_model_4 = db.Column(db.String(128))
    module_serial_4 = db.Column(db.String(128))
    module_model_5 = db.Column(db.String(128))
    module_serial_5 = db.Column(db.String(128))
    module_model_6 = db.Column(db.String(128))
    module_serial_6 = db.Column(db.String(128))
    module_model_7 = db.Column(db.String(128))
    module_serial_7 = db.Column(db.String(128))
    module_model_8 = db.Column(db.String(128))
    module_serial_8 = db.Column(db.String(128))
    module_model_9 = db.Column(db.String(128))
    module_serial_9 = db.Column(db.String(128))
    module_model_10 = db.Column(db.String(128))
    module_serial_10 = db.Column(db.String(128))
    pc_os = db.Column(db.String(128))
    pc_model = db.Column(db.String(128))
    software = db.Column(db.String(128))
    software_version = db.Column(db.String(128))
    hostname = db.Column(db.String(128))
    ip_address = db.Column(db.String(128))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))  # DELETE
    last_pm = db.Column(db.DateTime)  # DELETE
    name = db.Column(db.String(32))  # DELETE Sciex Qtrap 5 LCMS7
    manufacturer = db.Column(db.String(64))  # TO DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class InstrumentTypes(db.Model, BaseTemplate):
    __tablename__ = "instrument_types"

    types_instruments = db.relationship('Instruments', backref='type', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CooledStorage(db.Model, BaseTemplate):
    """

    """
    __tablename__ = 'cooled_storage'
    resource_level = 'secondary'
    __itemname__ = 'Cooled Storage'
    __itemtype__ = 'Cooled Storage'

    standards_solutions_storage = db.relationship('StandardsAndSolutions', backref='storage', lazy=True)

    equipment_id = db.Column(db.String(64), unique=True)
    serial_number = db.Column(db.String(64))
    acquired_date = db.Column(db.DateTime)
    last_service_date = db.Column(db.DateTime)
    due_service_date = db.Column(db.DateTime)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = division
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    model_number = db.Column(db.String(64))
    type_id = db.Column(db.Integer, db.ForeignKey('cooled_storage_types.id'))  # backref = type

    bms_name = db.Column(db.String(64))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    name = db.Column(db.String(64))  # DELETE
    code = db.Column(db.String)  # DELETE
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))  # DELETE
    division_id = db.Column(db.Integer)  # DELETE
    last_pm = db.Column(db.DateTime)  # DELETE
    contents = db.Column(db.String)  # DELETE - this info is in notes

    probe_model = db.Column(db.String(64))  # DELETE
    probe_serial = db.Column(db.String(64))  # DELETE
    hub_info = db.Column(db.String(64))  # DELETE # ID (Serial) ex: HUB5 (0003F406DB1F)
    manufacturer = db.Column(db.String(64))  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CooledStorageTypes(db.Model, BaseTemplate):
    """

    """
    __tablename__ = 'cooled_storage_types'

    types_cooled_storage = db.relationship('CooledStorage', backref='type', lazy=True)

    name = db.Column(db.String(64), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class EvidenceLockers(db.Model, BaseTemplate):
    """


    """

    __tablename__ = "evidence_lockers"
    resource_level = 'secondary'
    __itemname__ = 'Evidence Locker'
    __itemtype__ = 'Evidence Locker'

    equipment_id = db.Column(db.String(64), unique=True)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string
    occupied = db.Column(db.Boolean)

    name = db.Column(db.String)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Statuses(db.Model, BaseTemplate):
    __tablename__ = "statuses"

    statuses_assays = db.relationship('Assays', backref='status', lazy=True)
    statuses_benches = db.relationship('Benches', backref='status', lazy=True)
    statuses_cabinets = db.relationship('Cabinets', backref='status', lazy=True)
    statuses_calibrated_labware = db.relationship('CalibratedLabware', backref='status', lazy=True)
    statuses_compactors = db.relationship('Compactors', backref='status', lazy=True)
    statuses_cooled_storage = db.relationship('CooledStorage', backref='status', lazy=True)
    statuses_evidence_lockers = db.relationship('EvidenceLockers', backref='status', lazy=True)
    statuses_fume_hoods = db.relationship('FumeHoods', backref='status', lazy=True)
    statuses_instruments = db.relationship('Instruments', backref='status', lazy=True)
    statuses_general = db.relationship('GeneralLabware', backref='status', lazy=True)
    histology_equipment = db.relationship('HistologyEquipment', backref='status', lazy=True)
    statuses_hubs = db.relationship('Hubs', backref='status', lazy=True)
    statuses_probes = db.relationship('Probes', backref='status', lazy=True)
    statuses_evidence = db.relationship('EvidenceStorage', backref='status', lazy=True)
    statuses_personnel = db.relationship('Personnel', backref='status', lazy=True)
    statuses_report_templates = db.relationship('ReportTemplates', backref='status', lazy=True)

    name = db.Column(db.String(512), unique=True)
    description = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Rooms(db.Model, BaseTemplate):
    """

    List of rooms.

    Columns:
        name (str): the name of the room.
        room_number (str): the number of the room.

    Backrefs
        room: CooledStorage, Instruments

    """

    __tablename__ = 'rooms'
    resource_level = 'primary'
    __itemname__ = 'Room'
    __itemtype__ = 'Room'

    name = db.Column(db.String(64))
    room_number = db.Column(db.String(64), unique=True)

    fridges_freezers = db.relationship('CooledStorage', backref='room', lazy=True)  # DELETE
    rooms_instruments = db.relationship('Instruments', backref='room', lazy=True)  # DELETE
    rooms_fume_hoods = db.relationship('FumeHoods', backref='room', lazy=True)  # DELETE
    rooms_benchs = db.relationship('Benches', backref='room', lazy=True)  # DELETE
    rooms_cabinets = db.relationship('Cabinets', backref='room', lazy=True)  # DELETE
    rooms_compactors = db.relationship('Compactors', backref='room', lazy=True)  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Locations(db.Model, BaseTemplate):
    """

    List of items (from other tables) and their locations (from other tables) (e.g., EquipmentA is in FumeHoodA).
    Some locations also appear as items as they have locations as well (e.g., FumeHoodA is in Room211).

    """

    __tablename__ = 'locations'

    item_table = db.Column(db.String(32), index=True)
    item_id = db.Column(db.Integer, index=True)
    location_table = db.Column(db.String(32), index=True)
    location_id = db.Column(db.Integer, index=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## CUSTOM LISTS ##############

class Units(db.Model, BaseTemplate):
    """

    List of units.

    Columns:
        name (str): the name of the unit.
        type (str): the type of unit (i.e., Mass, concentration, volume, etc.).

    Backrefs
        unit: ReferenceMaterials, SpecimenTypes, Scope

    """

    __tablename__ = 'units'

    units = db.relationship('ReferenceMaterials', backref='unit', lazy=True)
    units_types = db.relationship('SpecimenTypes', backref='unit', lazy=True)
    units_scope = db.relationship('Scope', backref='unit', lazy=True)
    units_results = db.relationship('Results', backref='unit', lazy=True)
    units_pt = db.relationship('PTResults', backref='unit', lazy=True)

    name = db.Column(db.String(64), unique=True)
    unit_type_id = db.Column(db.Integer, db.ForeignKey('unit_types.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class UnitTypes(db.Model, BaseTemplate):
    __tablename__ = 'unit_types'

    units_types = db.relationship('Units', backref='type', lazy=True)

    name = db.Column(db.String(64), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Salts(db.Model, BaseTemplate):
    """
    List of salts for calculating correction factors.

    Columns:
        name (str): the name of the salt.
        abbreviation (str): the abbreviation of the salt.
        mass (float): the mass of the salt

    Backrefs
        salt: ReferenceMaterials

    """
    __tablename__ = 'salts'

    salts = db.relationship('ReferenceMaterials', backref='salt', lazy=True)

    name = db.Column(db.String(128), unique=True)
    abbreviation = db.Column(db.String(128))
    mass = db.Column(db.Float)

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## Zipcodes ##############

class Zipcodes(db.Model, BaseTemplate):
    """
    List of zipcode.

    Columns:
        zipcode (str): the six-digit zipcode.
        neighborhood (str): the neighborhood name

    """
    # cases_home_zip = db.relationship('Cases', backref='home_zipcode', lazy=True, foreign_keys="Cases.home_zip")
    # cases_death_zip = db.relationship('Cases', backref='death_zipcode', lazy=True, foreign_keys="Cases.death_zip")

    __tablename__ = 'zipcodes'

    zipcode = db.Column(db.String(5), unique=True)
    neighborhood = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class UnitedStates(db.Model, BaseTemplate):
    __tablename__ = 'united_states'

    name = db.Column(db.String)
    abbreviation = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## Drug Monographs ##############

class DrugMonographs(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'drug_monographs'

    # drug_monographs_compounds = db.relationship('Compounds', backref='monograph', lazy=True)

    name = db.Column(db.String)
    formulation_tradename = db.Column(db.Text)
    pharm_class = db.Column(db.Text)
    intended_use = db.Column(db.Text)
    mech_of_action = db.Column(db.Text)
    effects_and_tox = db.Column(db.Text)
    impairment = db.Column(db.Text)
    half_life = db.Column(db.Text)
    time_to_peak_conc = db.Column(db.Text)
    am_nontox_blood_serum_conc = db.Column(db.Text)
    am_nontox_information = db.Column(db.Text)
    pm_tox_blood_serum_conc = db.Column(db.Text)
    ampm_tox_lethal_coc_info = db.Column(db.Text)
    blood_to_serum_ratio = db.Column(db.Text)
    adme = db.Column(db.Text)
    pk_variability = db.Column(db.Text)
    drug_interaction = db.Column(db.Text)
    drug_interaction_ref = db.Column(db.Text)
    pm_redistribution = db.Column(db.Text)
    pm_considerations = db.Column(db.Text)
    hp_considerations = db.Column(db.Text)
    references = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


############## Admin System Changes ##############

class SystemImages(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'system_images'

    system_images_icon_image = db.relationship('CurrentSystemDisplay', backref='icon', lazy=True,
                                               foreign_keys='CurrentSystemDisplay.icon_img_id')
    system_images_logo_images = db.relationship('CurrentSystemDisplay', backref='logo', lazy=True,
                                                foreign_keys='CurrentSystemDisplay.logo_img_id')
    system_images_bg_image = db.relationship('CurrentSystemDisplay', backref='background', lazy=True,
                                             foreign_keys='CurrentSystemDisplay.bg_img_id')
    system_images_overlay_image = db.relationship('CurrentSystemDisplay', backref='overlay', lazy=True,
                                                  foreign_keys='CurrentSystemDisplay.overlay_img_id')

    # Set name_of_image unique=True
    name = db.Column(db.String(32))
    image_file = db.Column(db.String(32))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SystemMessages(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'system_messages'

    db_name = db.relationship('CurrentSystemDisplay', backref='db_names', lazy=True,
                              foreign_keys='CurrentSystemDisplay.db_name')
    welcome_message = db.relationship('CurrentSystemDisplay', backref='welcome_messages', lazy=True,
                                      foreign_keys='CurrentSystemDisplay.welcome_message')

    name = db.Column(db.String(256))
    message = db.Column(db.String(256))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CurrentSystemDisplay(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'current_system_display'

    accession_letter = db.Column(db.String)
    accession_counter = db.Column(db.Integer)
    icon_img_id = db.Column(db.Integer, db.ForeignKey('system_images.id'))
    logo_img_id = db.Column(db.Integer, db.ForeignKey('system_images.id'))
    bg_img_id = db.Column(db.Integer, db.ForeignKey('system_images.id'))
    overlay_img_id = db.Column(db.Integer, db.ForeignKey('system_images.id'))
    db_name = db.Column(db.Integer, db.ForeignKey('system_messages.id'))
    welcome_message = db.Column(db.Integer, db.ForeignKey('system_messages.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class StorageTemperatures(db.Model, BaseTemplate):
    __tablename__ = "storage_temperatures"

    reference_material_temperatures = db.relationship('ReferenceMaterials', backref='temperature', lazy=True)

    name = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Benches(db.Model, BaseTemplate):
    __tablename__ = "benches"
    resource_level = 'secondary'
    __itemname__ = 'Benches'
    __itemtype__ = "Bench"

    equipment_id = db.Column(db.String(64), unique=True)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    bench_type = db.Column(db.Integer, db.ForeignKey('bench_types.id'))  # backref = type
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    name = db.Column(db.String)  # DELETE
    code = db.Column(db.String)  # DELETE
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class BenchTypes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'bench_types'

    benches = db.relationship('Benches', backref='type', lazy=True)

    name = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Cabinets(db.Model, BaseTemplate):
    __tablename__ = "cabinets"
    resource_level = 'secondary'
    __itemname__ = 'Cabinets'
    __itemtype__ = 'Cabinet'

    equipment_id = db.Column(db.String(64), unique=True)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    cabinet_type = db.Column(db.Integer, db.ForeignKey('cabinet_types.id'))  # backref = type
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    name = db.Column(db.String)  # DELETE
    code = db.Column(db.String)  # DELETE
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CabinetTypes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'cabinet_types'

    cabinets = db.relationship('Cabinets', backref='type', lazy=True)

    name = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


# Called storage on the front-end
class Compactors(db.Model, BaseTemplate):
    __tablename__ = "compactors"
    resource_level = 'secondary'
    __itemname__ = 'Storage'
    __itemtype__ = 'Storage'

    equipment_id = db.Column(db.String(64), unique=True)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    storage_type = db.Column(db.Integer, db.ForeignKey('storage_types.id'))  # backref = type
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    name = db.Column(db.String)  # DELETE
    code = db.Column(db.String)  # DELETE
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class StorageTypes(db.Model, BaseTemplate):
    """

    """
    __tablename__ = 'storage_types'

    compactors = db.relationship('Compactors', backref='type', lazy=True)

    name = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class FumeHoods(db.Model, BaseTemplate):
    __tablename__ = "fume_hoods"
    resource_level = 'secondary'
    __itemname__ = 'Hoods'
    __itemtype__ = "Hood"

    equipment_id = db.Column(db.String(64), unique=True)
    serial_number = db.Column(db.String(64))
    acquired_date = db.Column(db.DateTime)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    last_service_date = db.Column(db.DateTime)
    due_service_date = db.Column(db.DateTime)
    vendor_id = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = vendor
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = agency
    model_number = db.Column(db.String(64))
    hood_type = db.Column(db.Integer, db.ForeignKey('hood_types.id'))  # backref = type
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    name = db.Column(db.String)  # DELETE
    code = db.Column(db.String)  # DELETE
    brand = db.Column(db.String)  # DELETE
    model = db.Column(db.String)  # DELETE
    serial = db.Column(db.String)  # DELETE
    acquire_date = db.Column(db.DateTime)  # DELETE
    calibration_date = db.Column(db.DateTime)  # DELETE
    expiration_date = db.Column(db.DateTime)  # DELETE
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))  # DELETE
    manufacturer = db.Column(db.String(64))  # DELETE

    def __init__(self, **entries):
        self.__dict__.update(entries)


class HoodTypes(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'hood_types'
    fume_hoods = db.relationship('FumeHoods', backref='type', lazy=True)

    name = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SecurityLockers(db.Model, BaseTemplate):
    __tablename__ = "security_lockers"

    name = db.Column(db.String)
    code = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class EvidenceStorage(db.Model, BaseTemplate):
    __tablename__ = "evidence_storage"
    resource_level = 'secondary'
    __itemname__ = 'Evidence Storage'
    __itemtype__ = 'Evidence Storage'

    equipment_id = db.Column(db.String(64), unique=True)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'))
    evidence_storage_type = db.Column(db.Integer, db.ForeignKey('evidence_storage_types.id'))  # backref = type
    location_type = db.Column(db.String(64))
    location = db.Column(db.String(64))  # storing location_id though stored as string

    def __init__(self, **entries):
        self.__dict__.update(entries)


class EvidenceStorageTypes(db.Model, BaseTemplate):
    """

    """
    __tablename__ = 'evidence_storage_types'

    evidence_storage = db.relationship('EvidenceStorage', backref='type', lazy=True)

    name = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Comments(db.Model, BaseTemplate):
    __tablename__ = "comments"

    comments_instances = db.relationship('CommentInstances', backref='comment', lazy=True)

    code = db.Column(db.String(512), unique=True)
    comment_type = db.Column(db.String)
    comment = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class CommentInstances(db.Model, BaseTemplate):
    __tablename__ = 'comment_instances'

    report_comments = db.relationship('ReportComments', backref='comment', lazy=True)

    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    comment_text = db.Column(db.String)
    comment_type = db.Column(db.String)
    comment_item_id = db.Column(db.Integer)
    comment_item_type = db.Column(db.String)  # the table name
    include_in_report = db.Column(db.Boolean)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class SpecialProjects(db.Model, BaseTemplate):
    __tablename__ = 'special_projects'

    special_project_name = db.Column(db.String)
    num_items = db.Column(db.Integer)
    num_completed = db.Column(db.Integer)
    remove_view = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Preservatives(db.Model, BaseTemplate):
    __tablename__ = "preservatives"

    standards_solutions = db.relationship('StandardsAndSolutions', backref='preservative', lazy=True)

    name = db.Column(db.String(512), unique=True)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class QRReference(db.Model, BaseTemplate):
    __tablename__ = "qr_reference"

    text = db.Column(db.String(128))
    qr_path = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Services(db.Model, BaseTemplate):
    __tablename__ = 'services'

    equipment_type = db.Column(db.String)
    equipment_id = db.Column(db.String)
    service_types = db.Column(db.String)
    service_date = db.Column(db.DateTime)
    vendor_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # individual, not division/service provider
    issue = db.Column(db.Text)
    resolution = db.Column(db.Text)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class ServiceTypes(db.Model, BaseTemplate):
    __tablename__ = 'service_types'

    name = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitPacketAdminTemplates(db.Model, BaseTemplate):
    __tablename__ = "lit_packet_admin_templates"

    lit_packet_admins = db.relationship('LitPacketAdmins', backref='lit_template', lazy=True)
    lit_packet_assays = db.relationship('LitPacketAdminAssays', backref='lit_template', lazy=True)
    lit_packet_attachments = db.relationship('LitPacketAdminAttachments', backref='lit_template', lazy=True)

    name = db.Column(db.String(128))
    case_contents = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Narratives(db.Model, BaseTemplate):
    __tablename__ = 'narratives'

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'))
    narrative_type = db.Column(db.String)
    narrative = db.Column(db.Text)
    checked = db.Column(db.String)
    updated_date = db.Column(db.DateTime)
    # why not add this to make sure narratives are unique in database so no dyplicates?
    # __table_args__ = (
    #     UniqueConstraint('case_id', 'narrative_type', name='uix_case_type'),
    # )


    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitPacketAdmins(db.Model, BaseTemplate):
    __tablename__ = "lit_packet_admins"

    lit_admin_template_id = db.Column(db.Integer, db.ForeignKey('lit_packet_admin_templates.id'))  # backref = template
    name = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitPacketAdminAssays(db.Model, BaseTemplate):
    __tablename__ = "lit_packet_admin_assays"

    lit_packet_admin_file_location = db.relationship('LitPacketAdminFiles', backref='lit_file', lazy=True)

    name = db.Column(db.String(128))
    overview_sheet = db.Column(db.String(128))
    lit_admin_template_id = db.Column(db.Integer, db.ForeignKey('lit_packet_admin_templates.id'))
    lit_admin_sort_order = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitPacketAdminAttachments(db.Model, BaseTemplate):
    __tablename__ = "lit_packet_admin_attachments"

    parent_item = db.Column(db.String(128))
    route = db.Column(db.String(128))
    attachment_type = db.Column(db.String(128))
    attachment_path = db.Column(db.String(128))
    attachment_name = db.Column(db.String(128))
    lit_admin_template_id = db.Column(db.Integer, db.ForeignKey('lit_packet_admin_templates.id'))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class LitPacketAdminFiles(db.Model, BaseTemplate):
    __tablename__ = "lit_packet_admin_files"

    lit_packet_admin_id = db.Column(db.Integer, db.ForeignKey('lit_packet_admin_assays.id'))  # backref = lit_file
    file_name = db.Column(db.String(128))
    use_file = db.Column(db.String(128))
    redact_type = db.Column(db.String(128))
    batch_record_sort_order = db.Column(db.Integer)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Requests(db.Model, BaseTemplate):
    """
    status: Incomplete Request, Pending Request, Ready for Authorization, Ready for Preparation, Ready for Check, Ready for Finalization, Finalized
    release_status(leveraged to display finalization reason): None;---, N/A; Not Applicapble, Canceled, Withdrawn, No Evidence Found

    """
    __tablename__ = "requests"

    specimen_request = db.relationship('Specimens', backref='request', lazy=True)

    name = db.Column(db.String)
    request_type_id = db.Column(db.Integer, db.ForeignKey('request_types.id'))
    case_id = db.Column(db.String)  # this will be id's stored as a list ex - "23, 10, 4"
    status = db.Column(db.String)
    intake_user = db.Column(db.Integer, db.ForeignKey('users.id'))
    intake_date = db.Column(db.DateTime)
    requesting_agency = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    requesting_division = db.Column(db.Integer, db.ForeignKey('divisions.id'))
    requesting_personnel = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    due_date = db.Column(db.DateTime)
    specimens = db.Column(db.String)  # This will be id's stored as a list
    denied_specimens = db.Column(db.String)  # This will be id's stored as a list
    approved_specimens = db.Column(db.String)  # This will be id's stored as a list
    specimen_count = db.Column(db.Integer)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approve_date = db.Column(db.DateTime)
    preparer = db.Column(db.Integer, db.ForeignKey('users.id'))
    prepare_date = db.Column(db.DateTime)
    prepare_status = db.Column(db.String)
    checker = db.Column(db.Integer, db.ForeignKey('users.id'))
    check_date = db.Column(db.DateTime)
    check_status = db.Column(db.String)
    releaser = db.Column(db.Integer, db.ForeignKey('users.id'))
    release_date = db.Column(db.DateTime)
    release_status = db.Column(db.String)
    receiving_agency = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    receiving_division = db.Column(db.Integer, db.ForeignKey('divisions.id'))
    receiving_personnel = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    received_date = db.Column(db.DateTime)
    destination_agency = db.Column(db.Integer, db.ForeignKey('agencies.id'))  # backref = dest_agency
    destination_division = db.Column(db.Integer, db.ForeignKey('divisions.id'))  # backref = dest_division
    destination_personnel = db.Column(db.Integer, db.ForeignKey('personnel.id'))  # backref = dest_personnel
    next_of_kin_confirmation = db.Column(db.String)  # confirmation for letters, next of kin, etc
    next_of_kin_date = db.Column(db.DateTime)
    payment_confirmation = db.Column(db.String)
    payment_confirmation_date = db.Column(db.DateTime)
    email_confirmation = db.Column(db.String)
    me_confirmation = db.Column(db.String)  # medical examiner confirmation / submission agency
    me_confirmation_date = db.Column(db.DateTime)
    legacy_case = db.Column(db.String)  # identifies if request is from a legacy case
    in_custody_specimens = db.Column(db.String)  # holds specimen IDs for collecting and returning specimens
    requested_items = db.Column(db.String)  # holds a list of requested items
    #legacy_ columns are free text fields and not db linked, no validation
    legacy_code = db.Column(db.String)
    legacy_accession_number = db.Column(db.String)
    legacy_date_created = db.Column(db.String)
    legacy_created_by = db.Column(db.String)
    legacy_checked_by = db.Column(db.String)


    def __init__(self, **entries):
        self.__dict__.update(entries)


class RequestTypes(db.Model, BaseTemplate):
    __tablename__ = "request_types"

    requests = db.relationship('Requests', backref='request_type', lazy=True)

    name = db.Column(db.String(128))
    description = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class AutopsyViewButtons(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'autopsy_view_buttons'

    button = db.Column(db.String(128))
    specimen_types = db.Column(db.String(128))

    def __init__(self, **entries):
        self.__dict__.update(entries)


class Disseminations(db.Model, BaseTemplate):
    """

    """

    __tablename__ = 'disseminations'

    record_id = db.Column(db.Integer, db.ForeignKey('records.id'))
    disseminated_to = db.Column(db.String(64))
    disseminated_by = db.Column(db.String(64))
    date = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)

class Returns (db.Model, BaseTemplate):

    """ 
    status = In Progress, Finalized
    
    """

    __tablename__ = 'returns'

    name = db.Column(db.String)
    case_id =db.Column(db.String)
    # to add request type table
    receiver = db.Column(db.Integer, db.ForeignKey('users.id')) # UNUSED and removed elsehere BAL 10/09/25
    specimens = db.Column(db.String)  # UNUSED and removed elsehere BAL 10/09/25
    returning_agency = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    returning_division = db.Column(db.Integer, db.ForeignKey('divisions.id'))
    returning_personnel = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    return_date =db.Column(db.DateTime)
    return_route_type = db.Column(db.String(32)) # UNUSED and removed elsehere BAL 10/09/25
    location_type = db.Column(db.String(64)) # UNUSED and removed elsehere BAL 10/09/25
    location = db.Column(db.String(64))  # UNUSED and removed elsehere BAL 10/09/25
    checker = db.Column(db.Integer, db.ForeignKey('users.id'))
    check_date = db.Column(db.DateTime)
    returned_specimens = db.Column(db.String)# This will be id's stored as a list
    stored_specimens = db.Column(db.String)# This will be id's stored as a list
    status = db.Column(db.String)
    collector = db.Column(db.String)
    collect_date = db.Column(db.DateTime)
    legacy_case = db.Column(db.String)  # identifies if request is from a legacy case
     #legacy_ columns are free text fields and not db linked, no validation
    legacy_code = db.Column(db.String)
    legacy_accession_number = db.Column(db.String)
    legacy_date_created = db.Column(db.String)
    legacy_created_by = db.Column(db.String)
    legacy_checked_by = db.Column(db.String)

    def __init__(self, **entries):
        self.__dict__.update(entries)

class FAPersonalEffects(db.Model, BaseTemplate):

    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), index=True)
    type = db.Column(db.String)
    quantity = db.Column(db.Integer)
    description = db.Column(db.String)
    disposition = db.Column(db.String)
    received_by = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    received_date = db.Column(db.DateTime)
    released_to = db.Column(db.String)
    released_date = db.Column(db.DateTime)

    def __init__(self, **entries):
        self.__dict__.update(entries)

disciplines = ['Toxicology', 'Biochemistry', 'Histology', 'External', 'Physical', 'Drug']
discipline_codes = {
    'Toxicology': 'T',
    'Biochemistry': 'B',
    'Histology': 'H',
    'External': 'X',
    'Physical': 'P',
    'Drug': 'D'
}
discipline_choices = [
    (0, "Please select a discipline"),
    ('Toxicology', 'Toxicology'),
    ('Biochemistry', 'Biochemistry'),
    ('Histology', 'Histology'),
    ('External', 'External'),
    ('Physical', 'Physical'),
    ('Drug', 'Drug')
]

# 'item_name' : [Table, 'table_name', name]
module_definitions = {
    'Agencies': [Agencies, 'agencies', 'name'],
    'Assay Constituent Types': [AssayConstituents, 'assay_constituents', 'name'],
    'Assays': [Assays, 'assays', 'assay_name'],
    'Attachments': [Attachments, 'attachments', 'id'],
    'Attachment Types': [AttachmentTypes, 'attachment_types', 'name'],
    'Autopsy View Buttons': [AutopsyViewButtons, 'autopsy_view_buttons', 'button'],
    'Batch Comments': [BatchComments, 'batch_comments', 'id'],  # NOT USED
    'Batch Constituents': [BatchConstituents, 'batch_constituents', 'id'],
    'Batch Records': [BatchRecords, 'batch_records', 'id'],
    'Batch Templates': [BatchTemplates, 'batch_templates', 'name'],
    'Batches': [Batches, 'batches', 'batch_id'],
    'Bench Types': [BenchTypes, 'bench_types', 'name'],
    'Benches': [Benches, 'benches', 'equipment_id'],
    'Bookings': [Bookings, 'bookings', 'case_id'],
    'Booking Changes': [BookingChanges, 'booking_changes', 'name'],
    'Booking Formats': [BookingFormats, 'booking_formats', 'name'],
    'Booking Discussion Topic': [BookingInformationProvided, 'booking_information_provided', 'name'],
    'Booking Information': [Bookings, 'bookings', 'case_id'],
    'Booking Information Provider': [BookingInformationProvider, 'booking_information_provider', 'name'],
    'Booking Jurisdiction': [BookingJurisdiction, 'booking_jurisdiction', 'name'],
    'Booking Locations': [BookingLocations, 'booking_locations', 'name'],
    'Booking Purposes': [BookingPurposes, 'booking_purposes', 'name'],
    'Booking Types': [BookingTypes, 'booking_types', 'name'],
    'Cabinet Types': [CabinetTypes, 'cabinet_types', 'name'],
    'Cabinets': [Cabinets, 'cabinets', 'equipment_id'],
    'Calibrated Labware': [CalibratedLabware, 'calibrated_labware', 'equipment_id'],
    'Calibrated Labware Types': [CalibratedLabwareTypes, 'calibrated_labware_types', 'name'],
    'Case Distinguishers': [CaseDistinguishers, 'case_distinguishers', 'name'], # UNUSED and removed elsehere SLP 10/02/25
    'Case Types': [CaseTypes, 'case_types', 'name'],
    'Cases': [Cases, 'cases', 'case_number'],
    'Collection Vessel Types': [SpecimenCollectionContainerTypes, 'specimen_collection_container_types', 'name'],
    'Collection Vessels': [SpecimenCollectionContainers, 'specimen_collection_containers', 'display_name'],
    'Comment Instances': [CommentInstances, 'comment_instances', 'id'],
    'Comments': [Comments, 'comments', 'comment'],
    'Components': [Components, 'components', 'name'],
    'Compounds': [Compounds, 'compounds', 'name'],
    'Compound-Component Reference': [CompoundsComponentsReference, 'compounds_components_reference', 'id'],
    'Container Types': [ContainerTypes, 'container_types', 'name'],
    'Containers': [Containers, 'containers', 'accession_number'],
    'Cooled Storage': [CooledStorage, 'cooled_storage', 'equipment_id'],
    'Cooled Storage Types': [CooledStorageTypes, 'cooled_storage_types', 'name'],
    'Current System Display': [CurrentSystemDisplay, 'current_system_display', 'id'],
    'Default Assay Constituents': [DefaultAssayConstituents, 'default_assay_constituents', 'id'],
    'Default Clients': [DefaultClients, 'default_clients', 'id'],
    'Disseminations': [Disseminations, 'disseminations', 'id'],
    'Divisions': [Divisions, 'divisions', 'name'],
    'Drug Classes': [DrugClasses, 'drug_classes', 'name'],
    'Drug Monographs': [DrugMonographs, 'drug_monographs', 'id'],
    'Evidence Comments': [EvidenceComments, 'evidence_comments', 'id'],
    'Evidence Comments Reference': [EvidenceCommentsReference, 'evidence_comments_reference', 'name'],
    'Evidence Lockers': [EvidenceLockers, 'evidence_lockers', 'equipment_id'],
    'Evidence Storage': [EvidenceStorage, 'evidence_storage', 'equipment_id'],
    'Evidence Storage Types': [EvidenceStorageTypes, 'evidence_storage_types', 'name'],
    'FAPersonalEffects': [FAPersonalEffects, 'fa_personal_effects', 'id'],
    'Genders': [Genders, 'genders', 'name'],
    'General Labware': [GeneralLabware, 'general_labware', 'equipment_id'],
    'General Labware Types': [GeneralLabwareTypes, 'general_labware_types', 'name'],
    'Histology Equipment': [HistologyEquipment, 'histology_equipment', 'equipment_id'],
    'Histology Equipment Types': [HistologyEquipmentTypes, 'histology_equipment_types', 'name'],
    'Hood Types': [HoodTypes, 'hood_types', 'name'],
    'Hoods': [FumeHoods, 'fume_hoods', 'equipment_id'],
    'Hubs': [Hubs, 'hubs', 'equipment_id'],
    'Instrument Types': [InstrumentTypes, 'instrument_types', 'name'],
    'Instruments': [Instruments, 'instruments', 'instrument_id'],
    'Lit Packet Admins': [LitPacketAdmins, 'lit_packet_admins', 'id'],
    'Lit Packet Admin Assays': [LitPacketAdminAssays, 'lit_packet_admin_assays', 'id'],
    'Lit Packet Admin Files': [LitPacketAdminFiles, 'lit_packet_admin_files', 'id'],
    'Lit Packet Admin Templates': [LitPacketAdminTemplates, 'lit_packet_admin_templates', 'id'],
    'Litigation Packets': [LitigationPackets, 'litigation_packets', 'id'],
    'Litigation Packet Templates': ['LitigationPacketTemplates', 'litigation_packet_templates', 'id'],
    'Locations': [Locations, 'locations', 'id'],
    'Modifications': [Modifications, 'modifications', 'id'],
    'Narratives': [Narratives, 'narratives', 'id'],
    'Packets': [LitigationPackets, 'litigation_packets', 'id'],
    'Personnel': [Personnel, 'personnel', 'full_name'],
    'Prepared Standards and Reagents': [StandardsAndSolutions, 'standards_and_solutions', 'lot'],
    'Preservatives': [Preservatives, 'preservatives', 'name'],
    'Probes': [Probes, 'probes', 'equipment_id'],
    'Proficiency Test Cases': [PTCases, 'pt_cases', 'id'],
    'Proficiency Test Results': [PTResults, 'pt_results', 'id'],
    'Purchased Reagents': [SolventsAndReagents, 'solvents_and_reagents', 'name'],
    'QR Reference': [QRReference, 'qr_reference', 'id'],
    'Races': [Races, 'races', 'name'],
    'Record Types': [RecordTypes, 'record_types', 'name'],
    'Records': [Records, 'records', 'record_name'],
    'Reference Batch Comments': [BatchCommentsReference, 'batch_comments_reference', 'id'],  # NOT USED
    'Reference Material Preparations': [],
    'Reference Material Solvents': [RefMatSolvents, 'reference_material_solvents', 'name'],
    'Reference Materials': [ReferenceMaterials, 'reference_materials', 'name'],
    'Report Comments': [ReportComments, 'report_comments', 'name'],
    'Report Results': [ReportResults, 'report_results', 'name'],
    'Report Templates': [ReportTemplates, 'report_templates', 'name'],
    'Reports': [Reports, 'reports', 'report_name'],
    'Requests': [Requests, 'requests', 'name'],
    'Request Types': [RequestTypes, 'request_types', 'name'],
    'Results': [Results, 'results', 'id'],
    'Retention Policies': [RetentionPolicies, 'retention_policies', 'name'],
    'Rooms': [Rooms, 'rooms', 'name'],
    'Sample Formats': [SampleFormats, 'sample_formats', 'name'],
    'Salts': [Salts, 'salts', 'name'],
    'Scope': [Scope, 'scope', 'id'],
    'Sequence Constituents': [SequenceConstituents, 'sequence_constituents', 'id'],
    'Sequence Header Mappings': [SequenceHeaderMappings, 'sequence_header_mappings', 'id'],
    'Service Types': [ServiceTypes, 'service_types', 'name'],
    'Services': [Services, 'services', 'id'],
    'Solution Types': [SolutionTypes, 'solution_types', 'name'],
    'Solvents and Reagents': [SolventsAndReagents, 'solvents_and_reagents', 'name'],
    'Specimen Audit': [SpecimenAudit, 'specimen_audit', 'id'],
    'Specimen Conditions': [SpecimenConditions, 'specimen_conditions', 'name'],
    'Specimen Sites': [SpecimenSites, 'specimen_sites', 'name'],  # NOT USED
    'Specimen Types': [SpecimenTypes, 'specimen_types', 'name'],
    'Specimens': [Specimens, 'specimens', 'accession_number'],
    'States of Matter': [StatesOfMatter, 'states_of_matter', 'name'],
    'Statuses': [Statuses, 'statuses', 'name'],
    'Storage': [Compactors, 'compactors', 'equipment_id'],
    'Storage Temperatures': [StorageTemperatures, 'storage_temperatures', 'name'],
    'Storage Types': [StorageTypes, 'storage_types', 'name'],
    'System Messages': [SystemMessages, 'system_messages', 'id'],
    'System Images': [SystemImages, 'system_images', 'id'],
    'Test Comments': [TestComments, 'test_comments', 'id'],  # NOT USED
    'Tests': [Tests, 'tests', 'test_name'],
    'Unit Types': [UnitTypes, 'unit_types', 'name'],
    'United States': [UnitedStates, 'united_states', 'name'],
    'Units': [Units, 'units', 'name'],
    'Users': [Users, 'users', 'full_name'],
    'User Log': [UserLog, 'user_log', 'id'],
    'Zip Codes': [Zipcodes, 'zipcodes', 'zipcode'],
}

# Includes some codes that aren't for tables, e.g., an
table_codes = {
    'an': 'accession_numer',  # This is used when creating histology labels, not a table reference but still important
    'ca': 'cases',
    'co': 'container',
    'di': 'discipline',
    's': 'specimens',
    'st': 'specimen_types',
}
