# -*- coding: utf-8 -*-
"""
    kronos
    ~~~~~~
"""

import uuid

from common.api.security_apikey import set_api_key
from common.config import CONFIG
from common.core import logger_console, set_component_logger
from common.models.enums import LogFormat

COMPONENT_NAME = "kronos"
COMPONENT_ID = uuid.uuid4().hex
COMPONENT_LOG = {
    "component_name": COMPONENT_NAME,
    "component_id": COMPONENT_ID,
    "component_version": CONFIG.KRONOS_VERSION,
}

# Set up logging
# ToDo: Enable this after ES logging is properly set up for Kronos.
CONFIG.ES_LOGGING_ENABLED = False

if CONFIG.ES_LOGGING_ENABLED:
    from common.core import logger_elastic
    from common.services import elastic

    FMT = logger_elastic.JSONFormatterElastic(
        es_client=elastic.get_client(),
        es_index=CONFIG.ES_INDEX_LOGS,
        component_log=COMPONENT_LOG,
    )

elif CONFIG.KRONOS_LOG_FORMAT == LogFormat.json:
    from common.core import logger_fmt

    FMT = logger_fmt.JSONFormatter(component_log=COMPONENT_LOG)

else:
    FMT = None

logger = logger_console.setup(logger_name=COMPONENT_NAME, log_level=CONFIG.KRONOS_LOG_LEVEL, fmt=FMT)
set_component_logger(logger)

# Set up API key
set_api_key(CONFIG.KRONOS_API_KEY)
