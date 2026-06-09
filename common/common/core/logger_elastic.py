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

DEFAULT_INDEX_SETTINGS = {
    "mappings": {
        "properties": {
            # General log fields
            "@timestamp": {"type": "date"},
            "@version": {"type": "keyword", "ignore_above": 256},
            "logger_name": {"type": "keyword", "ignore_above": 256},
            "log_type": {"type": "keyword", "ignore_above": 256},
            "level": {"type": "keyword", "ignore_above": 256},
            "host": {"type": "keyword", "ignore_above": 256},
            "filename": {"type": "keyword", "ignore_above": 256},
            "func_name": {"type": "keyword", "ignore_above": 256},
            "module": {"type": "keyword", "ignore_above": 256},
            "message": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 1024}}},

            # Component log fields
            "component_id": {"type": "keyword", "ignore_above": 256},
            "component_name": {"type": "keyword", "ignore_above": 256},
            "component_version": {"type": "keyword", "ignore_above": 256},

            # Scope logs for 'response' logs only
            "correlation_id": {"type": "keyword", "ignore_above": 256},
            "method": {"type": "keyword", "ignore_above": 256},
            "server": {"type": "keyword", "ignore_above": 256},
            "client": {"type": "keyword", "ignore_above": 256},
            "path": {"type": "keyword", "ignore_above": 1024},
            "query_string": {"type": "keyword", "ignore_above": 1024},
            "request_url": {"type": "keyword", "ignore_above": 1024},
            "request_id": {"type": "keyword", "ignore_above": 256},
            "response_time": {"type": "long"},

            # Exception info
            "exception": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 1024}}},
            "lineno": {"type": "long"},
            "process": {"type": "long"},
            "process_name": {"type": "keyword", "ignore_above": 256},
            "thread_name": {"type": "keyword", "ignore_above": 256},

            # Logged IDs
            "kb_id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "project_id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "session_id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "user_id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},

            # Logs object
            "logs": {
                "properties": {
                    "project_id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                    "session_id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                },
            },
        },
    },
    "settings": {
        "number_of_replicas": 1,
        "number_of_shards": 1,
    },
}


class JSONFormatterElastic(JSONFormatter):

    def __init__(self, /, es_client: Elasticsearch | None = None, es_index: str = "logs", **kwargs):
        super().__init__(**kwargs)
        self.es_client = es_client
        self.es_index = es_index

        if self.es_client is not None:
            if not self.es_client.indices.exists(index=self.es_index):
                self.es_client.indices.create(index=self.es_index, body=DEFAULT_INDEX_SETTINGS)

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
