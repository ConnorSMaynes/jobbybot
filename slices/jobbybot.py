'''
Purpose: Automatically race through job postings for which you qualify /
         are in your area of study / have not previously applied to,
         find the jobs with easy apply button and apply. '''

import ctypes
import os
import sys

import inspect
import json
import logging
import queue
import urllib
from contextlib import contextmanager
from datetime import datetime
from os.path import dirname, abspath
from threading import Thread
from time import sleep
from urllib.parse import urlparse
from urllib.parse import urlparse, parse_qs
from urllib.parse import urlsplit, parse_qsl
from urllib.request import ProxyHandler
import docx2txt
import gspread
import pygame
import requests
import pip
import importlib

from scrapy.spiders import BaseSpider
from scrapy.http import FormRequest
import textract
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import *
from bs4 import BeautifulSoup
from bs4 import BeautifulSoup as bs
from indeed import IndeedClient
from lxml import html
from oauth2client.service_account import ServiceAccountCredentials
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from sqlalchemy import create_engine, inspect, and_, or_
from sqlalchemy.orm import sessionmaker, scoped_session
import webbrowser
from common_resources import *
from common_funcs import CommonFuncs
from apps_db_declaratives import *
from _ziprecruiter import Ziprecruiter_Bot
from _rit_jobzone import Rit_Jobzone_Bot
from _ziprecruiter_webcrawler import ZiprecruiterWebcrawler
from _indeed_webcrawler import IndeedWebcrawler
from _indeed import Indeed_Bot
from gui import Ui_MainWindow


# import all bot classes
THIS_DIR = dirname(abspath(__file__))
CHROME_DRIVER_PATH = THIS_DIR + r'/' + 'drivers\chromedriver.exe'
PHANTOMJS_DRIVER_PATH = THIS_DIR +  r'/' + 'drivers\phantomjs.exe'
LOG_FILE_PATH = THIS_DIR + '/log.log'

WEB_DRIVERS_VISIBLE = False
WEB_DRIVERS_HEADLESS = False
START_SHRINKED = True

bot_threads = {}    # dictionary of bot threads initialize
[ bot_threads.update( { job_site + '_Bot' : { 'applier': None } } ) for job_site in JOB_SITE_LINKS ]
THREADS_DICT = {
            'verify_job_site_account':None,
            'stats':None,
            'job_profile_search_results':None,
            'database_tables':None
        }
QTHREAD_SLEEP_TIMES = {
    'stats': 3,
    'database_tables': 60
}


class DatabaseTablesThread(QThread):
    '''emit signal, to update the database tables when the data changes.'''

    update_tables = pyqtSignal()  # emit a string of stats, comma-separated

    def __init__(self):
        super().__init__()

        self.error = False

    def __del__(self):
        self.wait()

    def set_error(self, error_bool):
        self.error = error_bool

    def run(self):
        self.isRunning()
        self.set_error(False)  # reset error
        cached_db_results = []
        while True:
            fresh_results = []
            with CommonFuncs.get_db() as db:
                jobs = db.query(Job).all()
                if not jobs is None:
                    fresh_results += jobs
                if cached_db_results != fresh_results:
                    cached_db_results = fresh_results
                    self.update_tables.emit()
            sleep(QTHREAD_SLEEP_TIMES['database_tables'])


class StatsUpdateThread(QThread):
    '''query the db, get the stats and emit signals to update these in the GUI'''

    stats = pyqtSignal(str) # emit a string of stats, comma-separated

    def __init__(self):
        super().__init__()

        self.error = False

    def __del__(self):
        self.wait()

    def set_error(self, error_bool):
        self.error = error_bool

    def run(self):
        self.isRunning()
        self.set_error(False)   # reset error
        while True:
            stats_dict = {}
            with CommonFuncs.get_db() as db:
                try:
                    processed = len(db.query(Job).all())
                except:
                    processed = 0
                stats_dict.update({'processed': str(processed)})

                try:
                    applied = len(db.query(Job).filter(Job.applied == True).all())
                except:
                    applied = 0
                stats_dict.update({'applied': str(applied)})

                try:
                    todo = len(db.query(UnprocessedJob).all())
                except:
                    todo = 0
                stats_dict.update({'todo': str(todo)})

                for j_site in JOB_SITE_LINKS:
                    try:
                        bot_name = j_site + '_Bot'
                        try:
                            todo_count = len(db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == bot_name).all())
                            applied_count = len(db.query(Job).filter(
                                and_(
                                    Job.job_site == JOB_SITE_LINKS[j_site]['job_site'],
                                    Job.applied == True
                                )).all())
                        except:
                            todo_count = 0
                            applied_count = 0
                        stats_dict.update({bot_name + '_todo': str(todo_count)})
                        stats_dict.update({bot_name + '_applied': str(applied_count)})
                    except:
                        pass

                stats_dict = str(stats_dict)
                self.stats.emit(str(stats_dict))

            sleep( QTHREAD_SLEEP_TIMES['stats'] )


class BotThread(QThread):
    '''run the login verification process on a separate thread'''

    def __init__(self, site_bot_name):
        super(self.__class__, self).__init__()

        self.site_bot_name = site_bot_name
        self.error = False

    def __del__(self):
        self.wait()

    def set_error(self, error_bool):
        self.error = error_bool

    def run(self):
        self.isRunning()

        self.set_error(False)   # reset error

        Bot_Class = eval(self.site_bot_name)

        site_name = self.site_bot_name.split('_Bot')[0]
        spider_name = '_' + site_name.lower() + '_' + 'webcrawler.py'

        cached_username = ''
        cached_password = ''
        logged_in = False

        # APPLY LOOP
        bot = CommonFuncs.get_bot(self.site_bot_name)
        new_links = ['']
        with CommonFuncs.get_driver(visible=WEB_DRIVERS_VISIBLE, headless=WEB_DRIVERS_HEADLESS) as driver:
            bot_inst = Bot_Class(driver)
            while bot.is_running and len(new_links)>0:
                if cached_username != bot.username or cached_password != bot.password:  # if the username or password changed, attempt new login
                    cached_username = bot.username
                    cached_password = bot.password
                    logged_in = bot_inst.login(bot)
                if logged_in:  # if logged in and bot is running, apply to a job
                    with CommonFuncs.get_db() as db:
                        try:
                            new_to_db = False
                            while not new_to_db:
                                unprocessed_job = db.query(UnprocessedJob).filter(
                                    UnprocessedJob.bot_type == self.site_bot_name).all()
                                new_link = unprocessed_job[0].job
                                db.delete(unprocessed_job[0])
                                db.commit()
                                db_results = db.query(Job).filter(Job.link_to_job == new_link).all()
                                if db_results is None or db_results == []: new_to_db = True
                        except:
                            new_link = None
                            pass
                    if not new_link is None:
                        CommonFuncs.log(self, 'attempting to apply to: ' + new_link)
                        new_job = bot_inst.apply(new_link)  # goto page and apply
                        if new_job != False and isinstance(new_job, Job):    # only add the job to database, if it is an instance
                            with CommonFuncs.get_db() as db:    # save job object to db
                                try:
                                    db.add(new_job)
                                    db.commit()
                                except Exception as e:
                                    print(e)
                    else:
                        CommonFuncs.log('applier taking a timeout as it waits for more job links')
                        Jobbybot.run_bot_job_link_webcrawler( spider_name=spider_name ) # start the webcrawler for this bot
                        sleep_count = 100
                        for i in range(sleep_count):    # wait for more results, check to make sure the bot is still running
                            if CommonFuncs.is_bot_running(self.site_bot_name):
                                sleep(1)
                            else:
                                break
                bot = CommonFuncs.get_bot(self.site_bot_name)
                sleep(0.1)

        self.isFinished()


class VerifyLoginThread(QThread):
    '''run the login verification process on a separate thread'''

    def __init__(self, jobsiteaccount=None):
        super(self.__class__, self).__init__()

        self.jobsiteaccount = jobsiteaccount
        self.error = False

    def __del__(self):
        self.wait()

    def set_error(self, error_bool):
        self.error = error_bool

    def run(self):
        self.isRunning()

        self.set_error(False)   # reset error

        bot_class_string = self.jobsiteaccount.site_bot_name   # create instance of bot
        Bot_Class = eval(bot_class_string)
        with CommonFuncs.get_driver(headless=WEB_DRIVERS_HEADLESS, visible=WEB_DRIVERS_VISIBLE) as driver:
            bot_instance = Bot_Class(driver=driver)
            if not bot_instance.login(self.jobsiteaccount):    # attempt login
                self.set_error(True)
            else:   # if login successful
                self.set_error(False)

        self.isFinished()


class JobProfileResultsThread(QThread):
    '''run the login verification process on a separate thread'''

    def __init__(self):
        super(self.__class__, self).__init__()

        self.results = []
        self.error = False

    def __del__(self):
        self.wait()

    def set_error(self, error_bool):
        self.error = error_bool

    def run(self):
        self.isRunning()
        self.set_error(False)   # reset error
        bot_inst = Indeed_Bot(suppress_driver=True)
        self.results = bot_inst.get_api_results(desired_result_count=50)
        self.isFinished()


class Jobbybot:
    
    def __init__(self):

        self.init_process = True    # some processes in functions disabled during initialization

        if os.path.isfile(LOG_FILE_PATH): os.remove(LOG_FILE_PATH)    # delete the log from the last session
        CommonFuncs.log(self, 'Jobbybot session started')

        self.user_settings = None   # store login creds, job profile, etc
        self.threads = THREADS_DICT

        # RESET ALL BOTS TO NOT IS_RUNNING
        for j_site in JOB_SITE_LINKS:
            site_bot_name = j_site + '_Bot'
            with CommonFuncs.get_db() as db:
                try:
                    bot = CommonFuncs.get_bot(site_bot_name)
                    bot.is_running = False
                except:
                    bot = JobSiteAccount()
                    bot.is_running = False
                    bot.site_bot_name = site_bot_name
                db.add(bot)
                db.commit()
                CommonFuncs.log(self,'reset %s to not running in db' % site_bot_name)

        # CHECK FOR SETTINGS OBJECT - create if it does not exist
        settings = None
        with CommonFuncs.get_db() as db:
            try:
                settings = db.query(JobbybotSettings).one()
            except:
                pass
            if not settings:
                new_settings = JobbybotSettings()
                new_settings.connect_to_gsheets = False
                new_settings.delete_ujobs_on_jprofile_edit = True
                db.add(new_settings)
                db.commit()    # add settings object to database

        # START GUI SETUP
        app = QApplication(sys.argv)
        self.MainWindow = QtWidgets.QMainWindow()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.MainWindow)
        QApplication.setStyle(QStyleFactory.create('Fusion'))
        self.MainWindow.setWindowIcon(QIcon(STATIC_FILES['logo']))
        self.MainWindow.setGeometry(0,60,778,629)

        self.initialize_gui()

        CommonFuncs.log(self,'finished initializing gui')
        CommonFuncs.log(self,'Launching Jobbybot!')

        self.threads['stats'].start()
        self.threads['database_tables'].start()

        # OPEN AND RUN THE GUI
        self.init_process = False
        self.MainWindow.show()
        self.job_profile_table_edited()  # initial population of the results for the job profile
        sys.exit(app.exec_())

    def initialize_gui(self):
        '''initialize numerous gui settings before launching the application'''

        # JOB SITE ACCOUNT SECTION
        self.setup_job_site_account_section()

        # JOB PROFILE TABLE
        jobprofile = None
        try:
            with CommonFuncs.get_db() as db:
                jobprofile = db.query(JobProfile).one()
        except:
            pass
        if not jobprofile:
            jobprofile = JobProfile()
        job_profile_fields = JobProfile.__table__.columns.keys()
        self.ui.jobprofile_table.doubleClicked.connect(self.file_select)
        self.ui.jobprofile_table.setColumnCount(1)
        self.ui.jobprofile_table.setRowCount(len(job_profile_fields) - 1)
        self.ui.jobprofile_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        header = self.ui.jobprofile_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # JOB PROFILE TABLE HEADERS
        i = 0
        for field in job_profile_fields:  # build headers
            if not field == 'id':  # don't show the id
                self.ui.jobprofile_table.setVerticalHeaderItem(i, QTableWidgetItem(field))
            else:
                i -= 1
            i += 1

        # LOAD JOB PROFILE FROM DB
        i = -1  # when setting table widget values, the index starts at -1
        for field in job_profile_fields:
            if not field == 'id':  # don't show the id
                self.ui.jobprofile_table.setItem(i, 1, QTableWidgetItem(getattr(jobprofile, field)))
            else:  # return to previous row, to avoid skipping a row's header
                i -= 1
            i += 1
        CommonFuncs.log(self,'finished loading job profile from db')
        self.ui.jobprofile_table.setHorizontalHeaderItem(0, QTableWidgetItem('values'))
        self.ui.jobprofile_table.cellChanged.connect(self.job_profile_table_edited)

        # JOB PROFILE SEARCH RESULTS
        self.set_progress_bar_gif(self.ui.matchupload_lbl, static_key='hourglass_big')
        self.ui.matchupload_lbl.setStyleSheet('background-color: rgb(225,225,225)')
        self.ui.matchupload_lbl.setAlignment(Qt.AlignCenter)
        self.ui.matchupload_lbl.hide()
        self.ui.matchup_table.setColumnCount(1)
        self.ui.matchup_table.setHorizontalHeaderItem(0, QTableWidgetItem('Top Results'))
        header = self.ui.matchup_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # DELETE ON JOB PROFILE EDIT -- this must be initialized after table edit function run
        with CommonFuncs.get_db() as db:
            try:
                settings = db.query(JobbybotSettings).one()
            except:
                pass
            if settings.delete_ujobs_on_jprofile_edit == True:
                self.ui.delete_ujobs_on_jprofile_edit_check.setChecked(True)

        # SEARCH INTERFACE SETUP
        self.ui.search_btn.setIcon(QIcon(STATIC_FILES['search']))
        self.ui.search_btn.setIconSize(QSize(28, 28))

        # STATS THREADS
        self.threads['stats'] = StatsUpdateThread()
        self.threads['stats'].stats.connect(self.update_stats)

        # SEARCH TABLE AND BOX
        self.ui.tabs.setCurrentIndex(0)  # select jobs tab
        self.ui.search_btn.clicked.connect(self.search_table_btn_clicked)
        self.ui.search_box.returnPressed.connect(self.search_table_btn_clicked)
        self.threads['database_tables'] = DatabaseTablesThread()
        self.threads['database_tables'].update_tables.connect(self.search_table_btn_clicked)
        self.search_table_btn_clicked()

    def search_table_btn_clicked(self):
        '''run query of jobs in db and return results.'''
        CommonFuncs.log('running query on jobs in db')
        try:
            search_string = self.ui.search_box.text()
            results={
                'jobs':[],
            }
            self.ui.jobs_table.clear()
            job_fields = Job.__table__.columns.keys()
            with CommonFuncs.get_db() as db:
                for field in job_fields:
                    field_results = db.query(Job).filter(getattr(Job,field).contains(search_string)).all()
                    if field_results:
                        results['jobs'] += field_results
                results['jobs'] = list(set(results['jobs']))    # remove duplicates
            self.ui.jobs_table.setRowCount(len(job_fields))
            header = self.ui.jobprofile_table.verticalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)
            i = 0
            for field in job_fields:  # build headers
                self.ui.jobs_table.setVerticalHeaderItem(i, QTableWidgetItem(field))
                i += 1
            results['jobs'].sort(key=lambda x: x.app_date and x.link_to_job, reverse=True)    # sort by app_date
            if results['jobs']:
                col = 0
                self.ui.jobs_table.setColumnCount(len(results['jobs']))
                for result in results['jobs']:
                    row = 0
                    for field in job_fields:
                        cell_val = getattr(result,field)
                        if cell_val is None:
                            cell_val = ''
                        self.ui.jobs_table.setItem(row,col,QTableWidgetItem(str(cell_val)))
                        row+=1
                        if row>len(job_fields)-1:
                            break
                    col+=1
            else:
                self.ui.jobs_table.setColumnCount(0)
        except:
            CommonFuncs.log(self,'query unsuccessful',level='debug')
            pass
        CommonFuncs.log('query of jobs in db successful')

    def file_select(self):
        '''upload a file path to the user's job profile in the db on click in cell.'''
        CommonFuncs.log(self,'attempting to update a user job file')
        for currentTableWidgetItem in self.ui.jobprofile_table.selectedItems():
            current_row = currentTableWidgetItem.row()
            cell_text = self.ui.jobprofile_table.verticalHeaderItem(currentTableWidgetItem.row()).text()
            dlg = None
            if cell_text == 'resume' or cell_text == 'cover_letter':
                dlg = QFileDialog()
                dlg.setFileMode(QFileDialog.AnyFile)
            elif cell_text == 'supporting_docs':
                dlg = QFileDialog()
                dlg.setFileMode(QFileDialog.ExistingFiles)
            if dlg and dlg.exec_():
                filenames = dlg.selectedFiles()
                with CommonFuncs.get_db() as db:
                    job_profile = db.query(JobProfile).one()
                    setattr(job_profile, cell_text, str(filenames))
                    db.add(job_profile)
                    db.commit()
                    CommonFuncs.log(self,'successfully committed doc to job profile: %s' % str(filenames))
                self.ui.jobprofile_table.setItem(
                    current_row-1, 1, QTableWidgetItem(str(filenames)))

            break

    def update_stats(self, stats):
        '''update stats whenever they are emitted by the Stats thread'''
        CommonFuncs.log('updating stats on gui from db')
        stats_dict = eval(stats)
        if self.ui.applied_btn.text().isdigit():    # if the number of applied jobs changes, play the happy popping sound
            if int(stats_dict['applied']) > int(self.ui.applied_btn.text()):
                t = Thread(target=CommonFuncs.play_sound, args=(STATIC_FILES['job_applied_pop'],))
                t.daemon = True
                t.start()

        job_site_bot_name = self.ui.jobsite_select.currentText() + '_Bot'
        self.ui.todoforsite_btn.setText(str(stats_dict[job_site_bot_name + '_todo']))
        self.ui.todoforsite_btn.repaint()
        self.ui.appliedforsite_btn.setText(str(stats_dict[job_site_bot_name + '_applied']))
        self.ui.appliedforsite_btn.repaint()
        self.ui.todo_btn.setText(str(stats_dict['todo']))
        self.ui.todo_btn.repaint()
        self.ui.processed_btn.setText(str(stats_dict['processed']))
        self.ui.processed_btn.repaint()
        self.ui.applied_btn.setText(str(stats_dict['applied']))
        self.ui.applied_btn.repaint()

    def pause_selected_bot_thread(self):
        job_site_bot_name = self.ui.jobsite_select.currentText() + '_Bot'
        CommonFuncs.log(self, 'attempting to send pause signal to bot: %s' % job_site_bot_name )
        with CommonFuncs.get_db() as db:
            try:
                bot = CommonFuncs.get_bot(job_site_bot_name)
                if bot.is_running:
                    self.ui.pauseload_lbl.show()    # only show loading gif if there is bot to pause
                    bot.is_running = False
                    db.add(bot)
                    db.commit()
            except:
                CommonFuncs.log(self, 'problem sending pause signal for bot: %s' % job_site_bot_name, level='debug')
                pass
        CommonFuncs.log(self,'pause signal for %s successfully sent' % job_site_bot_name)

    def play_selected_bot_thread(self):
        '''run the bot selected from the dropdown menu.'''

        job_site_bot_name = self.ui.jobsite_select.currentText() + '_Bot'
        CommonFuncs.log( self, 'attempting to play selected: %s' % job_site_bot_name)
        with CommonFuncs.get_db() as db:
            try:
                bot = CommonFuncs.get_bot(job_site_bot_name)
                bot.is_running = True
            except:
                bot = JobSiteAccount()
                bot.site_bot_name = job_site_bot_name
                bot.is_running = True
            db.add(bot)
            db.commit()

        jobsiteaccount = CommonFuncs.get_bot( job_site_bot_name )
        if jobsiteaccount.username is None or jobsiteaccount.password is None:
            CommonFuncs.log(self, 'no valid login creds available')
            CommonFuncs.log(self, 'playing of bot canceled')
            return

        if bot_threads[job_site_bot_name]['applier'] is None or not bot_threads[job_site_bot_name]['applier'].isRunning():
            bot_threads[job_site_bot_name]['applier'] = BotThread(job_site_bot_name)  # only build thread, if it doesn't exist
            bot_threads[job_site_bot_name]['applier'].started.connect(self.bot_thread_started)
            bot_threads[job_site_bot_name]['applier'].finished.connect(self.bot_thread_finished)
            bot_threads[job_site_bot_name]['applier'].start()

            CommonFuncs.log(self, 'playing of %s successful!' % job_site_bot_name)
        else:
            CommonFuncs.log(self, 'playing of %s unsuccessful!' % job_site_bot_name)

    @staticmethod
    def run_bot_job_link_webcrawler(spider_name):
        '''run the webcrawler of the currently selected bot.'''

        def find_file(name, path):
            for root, dirs, files in os.walk(path):
                if name in files:
                    return os.path.join(root, name)
        def _crawl(spider_name): os.system('scrapy runspider %s' % spider_name)
        file_location = find_file( name=spider_name, path=dirname(THIS_DIR) )
        print("*****")
        print(file_location)
        print("*****")
        t = Thread(target=os.system, args=('scrapy runspider %s' % file_location,))
        t.daemon = True
        t.start()

    def bot_thread_finished(self):
        self.ui.playload_lbl.hide()
        self.ui.pauseload_lbl.hide()
        pass

    def bot_thread_started(self):
        self.ui.playload_lbl.show()
        pass

    def setup_job_site_account_section(self):

        # JOB SITE ACCOUNT LOADING GIF LABELS
        self.set_progress_bar_gif(self.ui.verifyload_lbl)
        self.ui.verifyload_lbl.hide()
        self.ui.verifyload_lbl.setAlignment(Qt.AlignCenter)
        self.set_progress_bar_gif(self.ui.playload_lbl, static_key='ripple')
        self.ui.playload_lbl.hide()
        self.ui.playload_lbl.setAlignment(Qt.AlignCenter)
        self.set_progress_bar_gif(self.ui.pauseload_lbl, static_key='ripple')
        self.ui.pauseload_lbl.hide()
        self.ui.pauseload_lbl.setAlignment(Qt.AlignCenter)
        self.set_progress_bar_gif(self.ui.deleteload_lbl, static_key='ripple')
        self.ui.deleteload_lbl.hide()
        self.ui.deleteload_lbl.setAlignment(Qt.AlignCenter)

        # BUTTON ICONS AND CONNECTIONS
        self.ui.jobsiteaccountcancel_btn.show()
        self.ui.jobsiteaccountcancel_btn.setIcon(QIcon(STATIC_FILES['revert']))
        self.ui.jobsiteaccountcancel_btn.setIconSize(QSize(20, 20))
        self.ui.jobsiteaccountcancel_btn.clicked.connect(
            self.revert_btn_clicked)  # refresh from db
        self.ui.shrink_expand_btn.setIconSize(QSize(15, 15))
        self.ui.shrink_expand_btn.clicked.connect(self.shrink_expand_window_btn_clicked)
        self.MainWindow.setGeometry(QtCore.QRect(0, 60, 778, 629))
        if START_SHRINKED: self.shrink_expand_window_btn_clicked()
        self.ui.shrink_expand_btn.setIcon(QtGui.QIcon(STATIC_FILES['shrink']))
        self.ui.moreinfo_btn.setIconSize(QSize(15, 15))
        self.ui.moreinfo_btn.setIcon(QtGui.QIcon(STATIC_FILES['more']))
        self.ui.moreinfo_btn.clicked.connect(self.show_more_info_btn_clicked)
        self.ui.verify_btn.setIcon(QtGui.QIcon(STATIC_FILES['checked']))
        self.ui.verify_btn.setIconSize(QSize(27, 27))
        self.ui.verify_btn.clicked.connect(self.verify_jobsiteaccount_btn_clicked)
        self.ui.stop_btn.setIcon(QIcon(STATIC_FILES['stop']))
        self.ui.stop_btn.setIconSize(QSize(27,27))
        self.ui.stop_btn.clicked.connect(self.pause_selected_bot_thread)
        self.ui.play_btn.setIcon(QIcon(STATIC_FILES['play']))
        self.ui.play_btn.setIconSize(QSize(27,27))
        self.ui.play_btn.clicked.connect(self.play_selected_bot_thread)
        self.ui.delete_btn.setIcon(QIcon(STATIC_FILES['delete']))
        self.ui.delete_btn.setIconSize(QSize(27,27))
        self.ui.delete_btn.clicked.connect(self.delete_selected_job_site)
        self.ui.gotosite_btn.setIcon(QIcon(STATIC_FILES['export']))
        self.ui.gotosite_btn.setIconSize(QSize(27,27))
        self.ui.gotosite_btn.clicked.connect(self.open_job_site_link)
        self.ui.todoforsite_btn.setIcon(QIcon(STATIC_FILES['inbox_site']))
        self.ui.todoforsite_btn.setIconSize(QSize(27, 27))
        self.ui.todo_btn.setIcon(QIcon(STATIC_FILES['inbox']))
        self.ui.todo_btn.setIconSize(QSize(27, 27))
        self.ui.processed_btn.setIcon(QIcon(STATIC_FILES['outbox']))
        self.ui.processed_btn.setIconSize(QSize(27, 27))
        self.ui.appliedforsite_btn.setIcon(QIcon(STATIC_FILES['applied']))
        self.ui.appliedforsite_btn.setIconSize(QSize(27, 27))
        self.ui.applied_btn.setIcon(QIcon(STATIC_FILES['applied_for_site']))
        self.ui.applied_btn.setIconSize(QSize(27, 27))
        
        # IF USERNAME OR PASSWORD IS CHANGED, RESET BOX COLORS AND REQUIRE VERIFICATION
        self.ui.jobsitepassword_box.textChanged.connect(
            self.show_job_site_account_verification_required)  # show re-verification needed image on button
        self.ui.jobsiteusername_box.textChanged.connect(self.show_job_site_account_verification_required)
        self.ui.jobsitepassword_box.setEchoMode(QLineEdit.Password) # mask password

        # JOB SITE ACCOUNT COMBO SELECT
        self.ui.jobsite_select.addItems(JOB_SITE_LINKS)
        self.job_site_account_select()  # initially load creds by comboselect
        self.ui.jobsite_select.currentTextChanged.connect(self.job_site_account_select) # load account on select change

    def delete_selected_job_site(self):
        msg = QMessageBox()  # show error message
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Your login creds and unprocessed jobs will be deleted for this site.")
        msg.setInformativeText( "Are you sure you want to continue?" )
        msg.setWindowTitle("Warning About Deletion: Irreversible")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        reply = msg.exec()

        if reply == QMessageBox.Ok:
            self.ui.deleteload_lbl.show()
            job_site = self.ui.jobsite_select.currentText() + '_Bot'
            with CommonFuncs.get_db() as db:
                # DELETE ACCOUNT
                jobsiteaccount = CommonFuncs.get_bot( job_site )
                if not jobsiteaccount is None:
                    db.delete(jobsiteaccount)
                    db.commit()
                    CommonFuncs.log(self, 'successfully deleted account for: ' + job_site)
                # DELETE ANY UNPROCESSED JOBS
                db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == job_site).delete(synchronize_session=False)
                db.commit()
                CommonFuncs.log(self, 'successfully deleted all unprocessed jobs for account: ' + job_site)
            self.job_site_account_select()  # refresh job site account section of gui
            self.ui.deleteload_lbl.hide()

    def show_more_info_btn_clicked(self):
        '''show/hide the event log for the session.'''
        if self.ui.tabs.height() > 211:
            self.ui.tabs.setGeometry(QtCore.QRect(10, 200, 461, 211))
            self.ui.jobs_table.setGeometry(QtCore.QRect(-1, -1, 459, 184))
        else:
            self.ui.tabs.setGeometry(QtCore.QRect(10, 200, 461, 391))
            self.ui.jobs_table.setGeometry(QtCore.QRect(-1, -1, 459, 362))
        self.ui.tabs.repaint()

    def shrink_expand_window_btn_clicked(self):
        '''show window maximized or minimized and adjust the icon.'''
        if self.MainWindow.height() > 174:  # SHRINK WINDOW
            self.MainWindow.setGeometry(QtCore.QRect(0, 60, 478, 174))
            self.ui.shrink_expand_btn.setIcon(QtGui.QIcon(STATIC_FILES['expand']))
        else:   # EXPAND WINDOW
            self.MainWindow.setGeometry(QtCore.QRect(0, 60, 778, 629))
            self.ui.shrink_expand_btn.setIcon(QtGui.QIcon(STATIC_FILES['shrink']))

    def open_job_site_link(self):
        '''open browser tab to goto the corresponding job site.'''
        job_site_name = self.ui.jobsite_select.currentText()
        webbrowser.open( url=JOB_SITE_LINKS[job_site_name]['applied_jobs'], new=2 )
        CommonFuncs.log(self, 'opened link to job site for user: ' + JOB_SITE_LINKS[job_site_name]['applied_jobs'] )

    def job_profile_table_edited(self):
        '''commit the change to the database and update the results returned from jobs sites for the new
        profile version.'''
        jobprofile = None
        try:
            with CommonFuncs.get_db() as db:
                jobprofile = db.query(JobProfile).one()
        except:
            pass
        if not jobprofile:
            jobprofile = JobProfile()

        job_profile_fields = JobProfile.__table__.columns.keys()    # get the column headers for the Job Profile table

        i=0
        for field in job_profile_fields:
            if not field == 'id':   # skip the id value, which is autoincremented
                try:
                    cell_text = self.ui.jobprofile_table.item(i,0).text()
                    setattr(jobprofile, field, cell_text)
                except:
                    pass
            else:   # reset the index, so we don't skip a row
                i-=1
            i+=1

        with CommonFuncs.get_db() as db:
            db.add(jobprofile)
            db.commit()

        # if the user has checked that they want to delete unprocessed jobs on job profile edit, delete them
        if not self.init_process:
            with CommonFuncs.get_db() as db:
                try:
                    settings = db.query(JobbybotSettings).one()
                except:
                    pass
                if settings.delete_ujobs_on_jprofile_edit == True:
                    db.query(UnprocessedJob).delete(synchronize_session=False)
                    db.commit()

        CommonFuncs.log(self, 'committed update to job profile for user')
        CommonFuncs.log(self, 'starting query thread to find jobs related to their profile')

        self.threads['job_profile_search_results'] = JobProfileResultsThread()
        self.threads['job_profile_search_results'].started.connect(self.job_profile_search_results_started)
        self.threads['job_profile_search_results'].finished.connect(self.job_profile_search_results_finished)
        self.threads['job_profile_search_results'].start()

    def job_profile_search_results_started(self):
        self.ui.matchupload_lbl.show()  # display loading gif over the matching job results table

    def job_profile_search_results_finished(self):
        CommonFuncs.log(self, 'completed query for jobs matching the user job profile')
        if not self.threads['job_profile_search_results'].isRunning(): # multiple edits may lead to multiple threads
            self.ui.matchupload_lbl.hide()
            if self.threads['job_profile_search_results'].results:
                self.ui.matchup_table.setRowCount(len(self.threads['job_profile_search_results'].results))
                i=0
                for result in self.threads['job_profile_search_results'].results:
                    self.ui.matchup_table.setItem(i, 0, QTableWidgetItem(result['jobtitle']))
                    i+=1
            else:
                self.ui.matchup_table.clear()
            self.ui.matchup_table.setHorizontalHeaderItem(0, QTableWidgetItem('Top Results'))

    @staticmethod
    def set_progress_bar_gif(lbl, static_key='hourglass'):
        '''show the progress bar in the job site account frame.'''
        hourglass = STATIC_FILES[static_key]
        progress_bar = QMovie(hourglass)
        lbl.setMovie(progress_bar)
        progress_bar.start()
        lbl.hide()

    def revert_btn_clicked(self):
        '''refresh the user's login creds for the selected job site from the db'''
        if not self.threads['verify_job_site_account']:
            self.job_site_account_select()
            return
        elif not self.threads['verify_job_site_account'].isRunning():  # make sure the verification process will not be interrupted
            self.job_site_account_select()
            return

    def job_site_account_select(self):
        '''load user's account creds for the selected site.'''
        job_site_bot_name = self.ui.jobsite_select.currentText() + '_Bot'
        CommonFuncs.log(self, 'starting to find the account creds and stats for the user after job site account select')
        todo_count = 0
        applied_count = 0
        try:
            with CommonFuncs.get_db() as db:
                todo_count = len(db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == job_site_bot_name).all())
                applied_count = len(db.query(Job).filter(
                    and_(
                        Job.job_site == JOB_SITE_LINKS[self.ui.jobsite_select.currentText()]['job_site'],
                        Job.applied == True
                    )).all())
        except:
            pass
        self.ui.todoforsite_btn.setText(str(todo_count))
        self.ui.appliedforsite_btn.setText(str(applied_count))
        jobsiteaccount = None
        jobsiteaccount = CommonFuncs.get_bot(job_site_bot_name)
        if not jobsiteaccount:
            self.ui.jobsiteusername_box.setText('')
            self.ui.jobsitepassword_box.setText('')
        else:
            self.ui.jobsiteusername_box.setText(jobsiteaccount.username)
            self.ui.jobsitepassword_box.setText(jobsiteaccount.password)
            if jobsiteaccount.is_running:
                self.ui.playload_lbl.show()
            else:
                self.ui.playload_lbl.hide()
        self.ui.jobsiteusername_box.setStyleSheet( 'background-color: white' )
        self.ui.jobsitepassword_box.setStyleSheet( 'background-color: white' )
        self.ui.verify_btn.setIcon( QtGui.QIcon( STATIC_FILES[ 'checked' ] ) )
        CommonFuncs.log(self, 'finished finding the account creds and stats for the user after job site account select')

    def verify_jobsiteaccount_btn_clicked(self):

        # GET LOGIN CREDS FROM THE GUI
        jobsitestring = str(self.ui.jobsite_select.currentText()) + '_Bot'
        jobsiteaccount = JobSiteAccount()
        jobsiteaccount.site_bot_name = jobsitestring
        jobsiteaccount.username = self.ui.jobsiteusername_box.text()
        jobsiteaccount.password = self.ui.jobsitepassword_box.text()

        CommonFuncs.log(self, 'building thread to verify the new login creds for the selected job site')

        self.threads['verify_job_site_account'] = VerifyLoginThread(jobsiteaccount=jobsiteaccount)  # open thread
        # SHOW PROGRESS BAR WHILE VERIFYING LOGIN
        self.threads['verify_job_site_account'].started.connect(self.verify_job_site_account_thread_started)
        # HIDE PROGRESS BAR WHEN LOGIN VERIFICATION TERMINATES
        self.threads['verify_job_site_account'].finished.connect(self.verify_job_site_account_thread_finished)
        # RUN THE THREAD TO VERIFY THE ACCOUNT
        self.threads['verify_job_site_account'].start()

        CommonFuncs.log(self, 'finished building thread to verify the new login creds for the selected job site')

    def show_job_site_account_verification_required(self):
        '''update the button icon to indicate the user must verify their account creds before they can be saved.'''
        self.ui.verify_btn.setIcon(QtGui.QIcon(STATIC_FILES['submit']))
        self.ui.jobsiteusername_box.setStyleSheet('background-color: white')   # remove green/red coloring from previous changes
        self.ui.jobsitepassword_box.setStyleSheet('background-color: white')

    def verify_job_site_account_thread_started(self):
        self.ui.verifyload_lbl.show()
        self.ui.verify_btn.setIcon(QtGui.QIcon(STATIC_FILES['blank']))
        self.ui.jobsiteusername_box.setEnabled(False)
        self.ui.jobsitepassword_box.setEnabled(False)
        self.ui.jobsite_select.setEnabled(False)
        self.ui.jobsiteaccountcancel_btn.setEnabled(False)

    def verify_job_site_account_thread_finished(self):

        CommonFuncs.log(self, 'completed verification process of account creds')

        self.ui.jobsiteusername_box.setEnabled(True)
        self.ui.jobsitepassword_box.setEnabled(True)
        self.ui.jobsite_select.setEnabled(True)
        self.ui.jobsiteaccountcancel_btn.setEnabled(True)
        self.ui.verifyload_lbl.hide()
        self.ui.jobsiteaccountcancel_btn.setIcon(QIcon(STATIC_FILES['revert']))
        if self.threads['verify_job_site_account'].error == True:
            self.ui.jobsiteusername_box.setStyleSheet('background-color: rgb(247, 126, 74)')
            self.ui.jobsitepassword_box.setStyleSheet('background-color: rgb(247, 126, 74)')
            self.ui.verify_btn.setIcon(
                QtGui.QIcon(STATIC_FILES['submit']))  # show the site creds need to be verified
            msg = QMessageBox() # show error message
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Job Site Account Verification Failed")
            msg.setInformativeText("Please correct your username and password and try again.")
            msg.setWindowTitle("Job Site Login Failed")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        else:
            # COMMIT THE JOB SITE ACCOUNT CREDS
            jobsitestring = str(self.ui.jobsite_select.currentText()) + '_Bot'
            jobsiteaccount = None
            try:
                jobsiteaccount = CommonFuncs.get_bot(jobsitestring)
            except:
                pass
            if not jobsiteaccount:
                jobsiteaccount = JobSiteAccount()

            jobsiteaccount.site_bot_name = jobsitestring
            jobsiteaccount.username = self.ui.jobsiteusername_box.text()
            jobsiteaccount.password = self.ui.jobsitepassword_box.text()

            with CommonFuncs.get_db() as db:
                db.add(jobsiteaccount)
                db.commit()

            CommonFuncs.log(self, 'successfully stored valid account creds')

            self.ui.verify_btn.setIcon(
                QtGui.QIcon(STATIC_FILES['checked']))  # show the site creds have been verified
            self.ui.jobsiteusername_box.setStyleSheet('background-color: rgb(70, 188, 128)')
            self.ui.jobsitepassword_box.setStyleSheet('background-color: rgb(70, 188, 128)')


if __name__ == '__main__':
    Jobbybot()