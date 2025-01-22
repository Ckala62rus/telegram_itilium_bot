import logging.config
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
            '()': ErrorLogFilter, # custom filter
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
            'formatter': 'formatter_2',
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
        'rotating_to_file': {
            'level': MAIN_LEVEL,
            'class': "logging.handlers.RotatingFileHandler",
            'formatter': 'default',
            "filename": "log.log",
            "maxBytes": 10,
            "backupCount": 10,
        },
    },
    'loggers': {
        'handlers': {
            'level': MAIN_LEVEL,
            'handlers': ['error_file', ]

        },
        'db': {
            'level': MAIN_LEVEL,
            'handlers': ['error_file', ]
        },
        'config': {
            'level': MAIN_LEVEL,
            'handlers': ['error_file', ]
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
            'some_logs',
            'critical_file',
            'error_file',
        ],
        'level': MAIN_LEVEL
    }
}
