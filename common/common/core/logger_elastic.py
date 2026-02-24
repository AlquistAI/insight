# -*- coding: utf-8 -*-
"""
    common.core.logger_elastic
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    ElasticSearch logging utilities.

    WARNING: This is just a quick/ugly implementation of logging to ElasticSearch!
    ToDo: Use a proper ES logging framework (e.g. Logstash).
"""

import json
import logging

from elasticsearch import Elasticsearch

from common.core.logger_fmt import JSONFormatter


class JSONFormatterElastic(JSONFormatter):

    def __init__(self, /, es_client: Elasticsearch | None = None, es_index: str = "logs", **kwargs):
        super().__init__(**kwargs)
        self.es_client = es_client
        self.es_index = es_index

    def format(self, record: logging.LogRecord) -> str:
        d_log = self.prepare_log(record)
        self.log_es(d_log)
        return json.dumps(d_log)

    def log_es(self, d_log: dict):
        if self.es_client is None:
            return

        try:
            self.es_client.index(index=self.es_index, body=d_log)
        except Exception as e:
            logging.error("Failed to log to ES: %s", e)
