""" Configure a logger using a dictionary
"""

import logging.config
from typing import Optional

# Formatters: change what gets logged
minimal = '%(message)s'
medium = '%(asctime)s.%(msecs)01d | %(levelname)s | %(name)s | %(message)s'
detailed = '%(asctime)s.%(msecs)01d | %(process)d | %(levelname)s | %(name)s | %(message)s'
formatters = {
    'minimal': {'format': minimal},
    'medium': {'format': medium, 'datefmt': '%Y-%m-%d %H:%M:%S'},
    'detailed': {'format': detailed, 'datefmt': '%Y-%m-%d %H:%M:%S'}
}

class Logger:
    """
    A configurable logger for console and file outputs.

    Attributes:
        log_config (dict): Configuration dictionary for the logger.

    Methods:
        start(name: Optional[str]): Initializes and retrieves the logger instance.
    """

    def __init__(self,
                 console: bool = True, 
                 console_format: str = 'medium', 
                 console_level: str = 'INFO',                
                 file_name: str = '',  
                 file_mode: str = 'w', 
                 file_format: str = 'detailed',
                 file_level: str = 'INFO') -> None:
        """
        Initializes the Logger configuration.

        Args:
            console (bool): Flag to enable or disable console logging.
            console_format (str): Format of the console logging. Should be either 'minimal' or 'detailed'.
            console_level (str): Logging level for the console. Default is 'INFO'.
            file_name (str): Name of the file to log messages. If empty, file logging is disabled.
            file_mode (str): File mode for file logging. Default is 'w' (write).
            file_format (str): Format of the file logging. Should be either 'minimal' or 'detailed'.
            file_level (str): Logging level for the file. Default is 'INFO'.
        """
    
        # Handlers: change file and console logging details
        handlers = {}
        if console:
            assert console_format in formatters.keys(), \
                f'Console format must be one of {list(formatters.keys())}'
            handlers['console_handle'] = { 
                'class': 'logging.StreamHandler',
                'level': console_level,
                'formatter': console_format,
            }

        if file_name:
            assert type(file_name) is str, 'File name must be a string'
            assert file_format in formatters.keys(), \
                f'File format must be one of {list(formatters.keys())}'
            handlers['file_handle'] = { 
                'class': 'logging.FileHandler',
                'level': file_level,
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
            'asyncio': {'level': 'INFO'},
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
        
    def start(self, name: Optional[str] = __name__) -> logging.Logger:
        logging.config.dictConfig(self.log_config)
        return logging.getLogger(name)