# -*- coding: utf-8 -*-
"""
    common.core.logger_fmt
    ~~~~~~~~~~~~~~~~~~~~~~

    Logging formatters.
"""

import json
import logging
import socket
import traceback
from datetime import datetime

from dateutil import tz

from common.core.middleware import X_CORRELATION_ID, X_REQUEST_ID, X_RESPONSE_TIME

# get attributes of LogRecord
# noinspection PyTypeChecker
log_record_attrs = [attr for attr in dir(logging.LogRecord("", 0, "", 0, "", "", "")) if not attr.startswith("__")]
log_record_attrs.extend(["message", "asctime"])
attr_names = {X_CORRELATION_ID: "correlation_id", X_REQUEST_ID: "request_id", X_RESPONSE_TIME: "response_time"}


class JSONFormatter(logging.Formatter):
    """
    JSON logging formatter.

    :param scope_attributes: attributes that we want to log from request scope
    :param component_log: component-specific log attributes
    """

    def __init__(self, scope_attributes: list[str] | None = None, component_log: dict[str, str] | None = None):
        super().__init__()
        self.host = socket.gethostname()
        self.scope_attributes = scope_attributes
        self.component_log = component_log

    @staticmethod
    def add_extra_fields(record: logging.LogRecord) -> dict:
        """Add fields to application log."""

        # if the field is not in the LogRecord class then add it
        rec = {k: v for k, v in record.__dict__.items() if k not in log_record_attrs}

        # rename some attributes defined in attr_names
        for old, new in attr_names.items():
            if old in rec:
                rec[new] = rec.pop(old)

        return rec

    @staticmethod
    def add_exc_info(record: logging.LogRecord) -> dict:
        """Add information if an exception was raised."""

        if not record.exc_info:
            return {}

        return {
            "exception": " ".join(traceback.format_exception(*record.exc_info)),
            "lineno": record.lineno,
            "process": record.process,
            "thread_name": record.threadName,
            "process_name": record.processName,
        }

    def add_scope(self, record: logging.LogRecord) -> dict:
        """Response log only: parse information in scope and add it to the log."""

        if not (scope := record.__dict__.get("scope")):
            return {}

        def get_key_fmt(_scope: dict, key: str) -> str:
            if len(_scope[key]) == 2:
                return f"{scope[key][0]}:{scope[key][1]}"
            return str(_scope[key])

        def get_key_decode(_scope: dict, key: str) -> str:
            if isinstance(_scope[key], bytes):
                try:
                    return _scope[key].decode()
                except Exception as e:
                    return str(e)
            return str(_scope[key])

        v = {
            "method": scope.get("method"),
            "server": get_key_fmt(scope, "server"),
            "client": get_key_fmt(scope, "client"),
            # "headers": [h for h in scope["headers"] if b"x-api-key" not in h],
            "path": scope["path"],
            "path_params": scope.get("path_params"),
            "query_string": get_key_decode(scope, "query_string"),
            "request_url": scope.get("request_url"),
            "correlation_id": scope.get(X_CORRELATION_ID, ""),
            "request_id": scope.get(X_REQUEST_ID, ""),
            "response_time": scope.get(X_RESPONSE_TIME, ""),
        }

        # add extra attributes from scope
        if self.scope_attributes:
            for k in self.scope_attributes:
                if value := scope.get(k):
                    v[k] = value

        return v

    def update_application_log(self, d_log, record):
        d_log["log_type"] = "log"
        d_log.update(self.add_extra_fields(record))

    def update_request_log(self, d_log, record):
        d_log["log_type"] = "request"
        d_log.update(self.add_extra_fields(record))

    def update_response_log(self, d_log, record):
        d_log["log_type"] = "response"
        d_log.update(self.add_scope(record))

        if code := record.__dict__.get("status_code"):
            if isinstance(code, str):
                code = int(code.split(" ", 1)[0])
            d_log["status_code"] = code

        d_log.update(self.add_extra_fields(record))
        d_log.pop("scope", None)

    def prepare_log(self, record: logging.LogRecord) -> dict:

        # create log dict
        d_log = {
            "@timestamp": datetime.fromtimestamp(record.created, tz=tz.UTC).isoformat(),
            "@version": "1",
            "host": self.host,
            "message": record.getMessage(),
            "level": record.levelname,
            "logger_name": record.name,
            "filename": record.filename,
            "func_name": record.funcName,
            "module": record.module,
        }

        # overwrite func_name and module from decorator
        if hasattr(record, "func_name_override"):
            d_log["func_name"] = record.func_name_override
            del record.func_name_override

        if hasattr(record, "module_override"):
            d_log["module"] = record.module_override
            del record.module_override

        # add component-specific attributes
        if self.component_log:
            d_log.update(self.component_log)

        # update fields based on log type
        if "uvicorn.access" in record.name or (getattr(record, "log_type", "")):
            self.update_response_log(d_log, record)
        elif "urllib3" in record.name:
            self.update_request_log(d_log, record)
        else:
            self.update_application_log(d_log, record)

        # add debug info for exceptions
        d_log.update(self.add_exc_info(record))

        return d_log

    def format(self, record: logging.LogRecord) -> str:
        d_log = self.prepare_log(record)
        return json.dumps(d_log)


class JSONFormatterLogstash(JSONFormatter):
    """
    JSON logging formatter for Logstash.

    Difference to JSONFormatter is that the formatter is returning bytes instead of str.
    """

    def format(self, record: logging.LogRecord) -> bytes:
        d_log = self.prepare_log(record)
        return bytes(json.dumps(d_log), "utf-8")
