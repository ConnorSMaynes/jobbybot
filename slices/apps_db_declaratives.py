from sqlalchemy import Column, ForeignKey, Integer, String, Date, Boolean, PickleType, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from os.path import dirname, abspath

Base = declarative_base()
DB_PATH = r"sqlite:///%s\db.db" % dirname(abspath(__file__))


class UnprocessedJob(Base):
    __tablename__ = 'unprocessedjob'
    job = Column(String, primary_key=True)
    bot_type = Column(String, nullable=True)
    date_created = Column(Date, nullable=True)


class JobProfile(Base):
    __tablename__ = 'jobprofile'
    id = Column(Integer, autoincrement=True, primary_key=True)
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    your_address = Column(String, nullable=True)
    your_city = Column(String, nullable=True)
    your_state = Column(String, nullable=True)
    applicant_name = Column(String, nullable=True)
    areas_of_study = Column(String, nullable=True)
    keywords = Column(String, nullable=True)
    industries = Column(String, nullable=True)
    work_authorizations = Column(String, nullable=True)
    job_types = Column(String, nullable=True)
    terms_of_employment = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    radius = Column(Integer, nullable=True)
    states = Column(String, nullable=True)
    countries = Column(String, nullable=True)
    resume = Column(String, nullable=True)
    cover_letter = Column(String, nullable=True)
    supporting_docs = Column(String, nullable=True)


class Job(Base):
    __tablename__ = 'job'
    app_date = Column(Date, nullable=True)
    applied = Column(Boolean, nullable=True)
    on_hold = Column(Boolean, nullable=True)
    link_to_job = Column(String, primary_key=True)
    job_title = Column(String, nullable=True)
    job_site = Column(String, nullable=True)
    location = Column(String, nullable=True)
    company = Column(String, nullable=True)
    company_site = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)


class JobSiteAccount(Base):
    __tablename__ = 'jobsiteaccount'
    site_bot_name = Column(String, primary_key=True)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    is_running = Column(Boolean, nullable=True)


class JobbybotSettings(Base):
    __tablename__ = 'jobbybotsettings'
    id = Column(Integer, autoincrement=True, primary_key=True)
    connect_to_gsheets = Column(Boolean, nullable=True)
    job_tracking_gsheet = Column(String, nullable=True)
    delete_ujobs_on_jprofile_edit = Column(Boolean, nullable=True)


engine = create_engine(DB_PATH)
Base.metadata.create_all(engine)