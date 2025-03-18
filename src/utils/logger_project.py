import logging.config
from logging.handlers import RotatingFileHandler
import sys

MAIN_LEVEL = logging.DEBUG


class ErrorLogFilter(logging.Filter):
    def filter(self, record):
        return record.levelname == 'ERROR'


class DebugWarningLogFilter(logging.Filter):
    def filter(self, record):
        return record.levelname in ('DEBUG', 'WARNING')


class CriticalLogFilter(logging.Filter):
    def filter(self, record):
        return record.levelname == 'CRITICAL'


logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            # 'format': '#%(levelname)-8s %(name)s:%(funcName)s - %(message)s'
            'format': '[%(asctime)s] #%(levelname)-8s %(filename)s:'
                      '%(lineno)d - %(name)s:%(funcName)s - %(message)s'
        },
        'formatter_1': {
            'format': '[%(asctime)s] #%(levelname)-8s %(filename)s:'
                      '%(lineno)d - %(name)s:%(funcName)s - %(message)s'
        },
        'formatter_2': {
            'format': '#%(levelname)-8s [%(asctime)s] - %(filename)s:'
                      '%(lineno)d - %(name)s:%(funcName)s - %(message)s'
        },
        'formatter_3': {
            'format': '#%(levelname)-8s [%(asctime)s] - %(message)s'
        }
    },
    'filters': {
        'critical_filter': {
            '()': CriticalLogFilter,  # custom filter
        },
        'error_filter': {
            '()': ErrorLogFilter,  # custom filter
        },
        # 'debug_warning_filter': {
        #     '()': DebugWarningLogFilter, # custom filter
        # }
    },
    'handlers': {
        'default': {
            'class': 'logging.StreamHandler',
            'level': MAIN_LEVEL,
            'formatter': 'default'
        },
        'stderr': {
            'class': 'logging.StreamHandler',
        },
        'stdout': {
            'class': 'logging.StreamHandler',
            # 'formatter': 'formatter_2',
            'formatter': 'formatter_1',
            'level': MAIN_LEVEL,
            # 'filters': ['debug_warning_filter'],
            'stream': sys.stdout
        },
        'error_file': {
            'class': 'logging.FileHandler',
            'filename': 'error.log',
            'mode': 'w',
            # 'level': logging.ERROR,
            'formatter': 'formatter_1',
            'filters': ['error_filter']
        },
        'critical_file': {
            'class': 'logging.FileHandler',
            'filename': 'critical.log',
            'mode': 'a',  # a - append
            'formatter': 'formatter_1',
            'filters': ['critical_filter']
        },
        'some_logs': {
            'class': 'logging.FileHandler',
            'filename': 'log.log',
            'mode': 'a',
            'level': MAIN_LEVEL,
            'formatter': 'default',
            # 'filters': ['error_filter']
        },
        # 'rotating': {
        #     'level': 'DEBUG',
        #     'class': "logging.handlers.RotatingFileHandler",
        #     'formatter': 'default',
        #     "filename": "app.log",
        #     "maxBytes": 1000,
        #     "backupCount": 10,
        # },
    },
    'loggers': {
        # '': {
        #     'level': MAIN_LEVEL,
        #     'handlers': ['stdout', 'rotating']
        # },
        'handlers': {
            'level': MAIN_LEVEL,
            # 'handlers': ['error_file', ]
            'handlers': ['stdout', ]

        },
        'db': {
            'level': MAIN_LEVEL,
            # 'handlers': ['error_file', ]
            'handlers': ['stdout', ]
        },
        'config': {
            'level': MAIN_LEVEL,
            # 'handlers': ['error_file', ]
            'handlers': ['stdout', ]
        },
        # 'module_2': {
        #     'handlers': ['stdout']
        # },
        # 'module_3': {
        #     'handlers': ['stderr', 'critical_file']
        # }
    },
    'root': {
        'formatter': 'default',
        'handlers': [
            'default',
            # 'some_logs',
            # 'critical_file',
            # 'stdout',
            # 'rotating',
        ],
        'level': MAIN_LEVEL
    }
}
