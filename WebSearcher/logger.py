""" Configure a logger using a dictionary
"""

import sys
import logging.config
from datetime import datetime

# Formatters: change what gets logged
minimal = '%(message)s'
detailed  = '%(asctime)s | %(process)d | %(levelname)s | %(name)s | %(message)s'
formatters = { 
    'minimal': {'format': minimal},
    'detailed': {'format': detailed}
}

class Logger(object):
    """ Get logger and set console and file outputs

        Ex: 
        ```
        from logger import Summary
        log = Logger('summary.log').get_logger('mylogger')
         
        ```
    """
    def __init__(self, 
        file_name='', file_format='detailed', file_mode='w',
        console=True, console_format='detailed', console_level='DEBUG'):
    
        # Handlers: change file and console logging details
        handlers = {}
        if console:
            assert console_format in formatters.keys(), \
                f'Must select formatting type from {list(formatters.keys())}'

            handlers['console_handle'] = { 
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': console_format,
            }

        if file_name:
            assert type(file_name) is str, \
                'Must provide name for file logging'
            assert file_format in formatters.keys(), \
                f'Must select formatting type from {list(formatters.keys())}'

            handlers['file_handle'] = { 
                'class': 'logging.FileHandler',
                'level': 'INFO',
                'formatter': file_format,
                'filename': file_name,
                'mode': file_mode
            }
        
        # Loggers: change logging options for root and other packages
        loggers = {
            # Root logger
            '': { 
                'handlers': list(handlers.keys()),
                'level': 'DEBUG',
                'propagate': True
            },
            # External loggers
            'requests': {'level': 'WARNING'},
            'urllib3': {'level': 'WARNING'},
            'chardet.charsetprober': {'level': 'INFO'},
            'parso': {'level': 'INFO'} # Fix for ipython autocomplete bug
        }

        self.log_config = { 
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': formatters,
            'handlers': handlers,
            'loggers': loggers
        }
        
    def start(self, name=__name__):
        logging.config.dictConfig(self.log_config)
        return logging.getLogger(name)

    def header(log, title, script=sys.argv[0]):
        script = script.split('/')[-1].split('.')[0]
        log.info(f'# {title}\n')
        log.info(f'By: {script}')
        log.info(f'On: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

    # def generated_by(logger, scriptname):

