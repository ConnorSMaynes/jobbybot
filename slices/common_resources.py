from os.path import dirname, abspath

THIS_DIR = dirname(abspath(__file__))

JOB_SITE_LINKS = {
    'Indeed':
        {
            "login_site": "https://secure.indeed.com/account/login",
            "job_site": "https://www.indeed.com/",
            "job_site_base": "https://www.indeed.com",
            "query": "https://www.indeed.com/jobs?",
            "applied_jobs": "https://www.indeed.com/myjobs?from=desktopnavmenu#applied"
        },
    'Rit_Jobzone': {
        "login_site": "https://shibboleth-rit-csm.symplicity.com/sso/",
        "job_site": "https://rit-csm.symplicity.com/students/index.php?s=jobs&ss=jobs&mode=list",
        "job_site_base": "https://rit-csm.symplicity.com/students/index.php",
        "job_site_docs_page": "https://rit-csm.symplicity.com/students/index.php?mode=list&s=resume&ss=resumes"
    },
    'Ziprecruiter': {
        "login_site": "https://www.ziprecruiter.com/login",
        "job_site": "https://www.ziprecruiter.com/",
        "job_site_base": "https://www.ziprecruiter.com",
        "query": "https://www.ziprecruiter.com/candidate/search?",
        "applied_jobs": "https://www.ziprecruiter.com/candidate/my-jobs"
    }
}
STATIC_FILE_PATH = THIS_DIR + '/static/'
STATIC_FILES = {
    "submit": STATIC_FILE_PATH + 'submit.png',
    "checked": STATIC_FILE_PATH + 'checked.png',
    "hourglass": STATIC_FILE_PATH + 'hourglass.gif',
    'hourglass_big': STATIC_FILE_PATH + 'hourglass_big.gif',
    "ripple": STATIC_FILE_PATH + 'ripple.gif',
    'blank': STATIC_FILE_PATH + 'blank.png',
    'cancel': STATIC_FILE_PATH + 'cancel.png',
    'revert': STATIC_FILE_PATH + 'revert.png',
    'search': STATIC_FILE_PATH + 'search.png',
    'edit': STATIC_FILE_PATH + 'edit.png',
    'create': STATIC_FILE_PATH + 'create.png',
    'duplicate': STATIC_FILE_PATH + 'duplicate.png',
    'delete': STATIC_FILE_PATH + 'delete.png',
    'play': STATIC_FILE_PATH + 'play.png',
    'stop': STATIC_FILE_PATH + 'stop.png',
    'runner': STATIC_FILE_PATH + 'runner.png',
    'logo': STATIC_FILE_PATH + 'logo.png',
    'export': STATIC_FILE_PATH + 'export.png',
    'job_applied_pop': STATIC_FILE_PATH + 'job_applied_pop.wav',
    'shrink': STATIC_FILE_PATH + 'shrink.png',
    'expand': STATIC_FILE_PATH + 'expand.png',
    'more': STATIC_FILE_PATH + 'more.png',
    'outbox': STATIC_FILE_PATH + 'outbox.png',
    'inbox': STATIC_FILE_PATH + 'inbox.png',
    'applied': STATIC_FILE_PATH + 'applied.png',
    'inbox_site': STATIC_FILE_PATH + 'inbox_site.png',
    'applied_for_site': STATIC_FILE_PATH + 'applied_site.png'
}