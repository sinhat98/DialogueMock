import logging
import sys
import os

class AbsolutePathFormatter(logging.Formatter):
    """
    Custom formatter to display the absolute path of the filename.
    """
    def format(self, record):
        if record.pathname:
            record.pathname = os.path.abspath(record.pathname)
        return super().format(record)


def get_custom_logger(name, level=logging.DEBUG):
    """
    Setup a custom logger.

    Parameters:
    - name: str - Name of the logger.
    - level: int - Logging level (default is logging.DEBUG).

    Returns:
    A configured logger instance.
    """

    formatter = AbsolutePathFormatter(
        fmt="%(levelname)s:%(name)s:[%(pathname)s - %(lineno)d]: %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    # Prevent logging messages from being propagated to the root logger
    logger.propagate = False

    return logger
