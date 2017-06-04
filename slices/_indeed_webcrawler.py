import json
import queue
import sys
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

import os
import requests
import scrapy
from scrapy.http import FormRequest
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from bs4 import BeautifulSoup as bs
from oauth2client.service_account import ServiceAccountCredentials
from pyvirtualdisplay import Display
from selenium.webdriver.support import expected_conditions as EC
from sqlalchemy.orm import sessionmaker, scoped_session

from common_resources import *
from common_funcs import CommonFuncs
from apps_db_declaratives import *


class IndeedWebcrawler(scrapy.Spider):
    name = 'indeedwebcrawler'

    def start_requests(self):
        '''return iterable of job links'''

        with CommonFuncs.get_db() as db:
            todoforsite = db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == 'Indeed_Bot').all()
        if len(todoforsite) >= 100:
            return

        start_time = datetime.now()

        job_profile = CommonFuncs.get_job_profile()
        locations = CommonFuncs.get_locations_list(job_profile)
        query_list = CommonFuncs.build_query_string(job_profile=job_profile, or_delim='or', bracket1='(', bracket2=')', adv_supp=True)
        query_string = query_list[0]

        if len(query_string) == 0: return

        ##########
        # URL ENCODE EACH QUERY
        ##########
        start_urls = []
        for location in locations:
            query_dict = {'q':query_string, 'l':location}
            encoded_query = urllib.parse.urlencode(query_dict, safe='')
            job_url = JOB_SITE_LINKS['Indeed']['query'] + '&' + encoded_query
            start_urls.append(job_url)

        # CommonFuncs.log('time spent building start_urls for Indeed: ' + str(datetime.now() - start_time))

        ##########
        # GET URL RESPONSES AND CALL PARSE FUNCTION TO ITERATE OVER PAGES
        ##########
        for url in start_urls:
            yield scrapy.Request(url=url, callback=self.parse)
    def parse(self, response):

        with CommonFuncs.get_db() as db:
            todoforsite = db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == 'Indeed_Bot').all()
        if len(todoforsite) >= 100:
            return

        this_url = response._url
        try:
            searching_by = dict(parse_qsl(urlsplit(this_url).query))
            print('searching by: ' + str(searching_by))
        except:
            pass
        # CommonFuncs.log('starting parsing job page for IndeedWebcrawler: ' + response.url)

        # COLLECT NEW JOB LINKS FROM SITE
        jobs = response.xpath("//div[@data-tn-component='organicJob']")
        new_count = 0
        for job in jobs:
            bot = CommonFuncs.get_bot('Indeed_Bot')
            if not bot.is_running: return    # exit if the bot is not running
            extracted_job = job.extract()
            job_state = None
            if 'Easily apply' in extracted_job:
                job_link = JOB_SITE_LINKS[ 'Indeed' ][ 'job_site_base' ] + job.xpath('h2/a/@href').extract()[0]
                with CommonFuncs.get_db() as db:
                    db_results = db.query(Job).filter(Job.link_to_job == job_link).all()
                if db_results is None or db_results == []:
                    new_count += 1
                    try:
                        with CommonFuncs.get_db() as db:
                            u_job = UnprocessedJob()
                            u_job.bot_type = 'Indeed_Bot'
                            u_job.job = job_link
                            db.add(u_job)
                            db.commit()
                    except:
                        pass

        # CommonFuncs.log('%s new jobs found on page %s' % (new_count, response.url))
        if new_count > 0: print('%s new jobs found on page' % new_count)

        ##########
        # JUMP TO NEXT PAGE WHILE THE BOT IS STILL RUNNING
        ##########
        pagination_links = response.xpath( "//div[@class='pagination']/a" ).extract()
        for link in pagination_links:
            if 'Next' in link:
                bot = CommonFuncs.get_bot('Indeed_Bot')
                if bot.is_running:  # verify that the bot is running before continuing to the next page
                    # CommonFuncs.log('finished parsing job page for IndeedWebcrawler: ' + this_url)
                    next_link = bs(link,'lxml').body.find('a').get('href')
                    full_link = JOB_SITE_LINKS[ 'Indeed' ][ 'job_site_base' ] + next_link
                    yield scrapy.Request( url=full_link, callback=self.parse )
                else:
                    return


# if __name__ == '__main__':
#     runner = CrawlerRunner()
#     runner.crawl(IndeedWebcrawler)
#     d = runner.join()
#     d.addBoth(lambda _: reactor.stop())
#     reactor.run()