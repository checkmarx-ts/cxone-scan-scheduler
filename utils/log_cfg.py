import logging.config, os


def get_log_level():
    return "INFO" if os.getenv('LOG_LEVEL') is None else os.getenv('LOG_LEVEL')

default_log_config = {
    "version" : 1,
    "handlers" : {
        "console" : {
            "class" : "logging.StreamHandler",
            "formatter" : "default",
            "level" : get_log_level(),
            "stream" : "ext://sys.stdout"
        }
    },
    "formatters" : {
        "default" : {
            "format" : "[%(asctime)s][%(process)d][%(name)s][%(levelname)s] %(message)s",
            "datefmt" : "%Y-%m-%dT%H:%M:%S%z"
        }
    },
    "loggers" : {
        "root" : {
            "handlers" : ["console"],
            "level" : get_log_level()
        }
    }
}

logging.config.dictConfig(default_log_config)


