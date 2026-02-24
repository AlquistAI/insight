# -*- coding: utf-8 -*-
"""
    common.services.elastic
    ~~~~~~~~~~~~~~~~~~~~~~~

    ElasticSearch service utilities.
"""

from cachetools.func import ttl_cache
from elastic_transport.client_utils import DEFAULT
from elasticsearch import Elasticsearch

from common.config import CONFIG, PATH_ES_CERT


@ttl_cache(ttl=600)
def get_client(**kwargs) -> Elasticsearch:
    return Elasticsearch(
        hosts=str(CONFIG.ES_URL),
        basic_auth=(CONFIG.ES_USER, CONFIG.ES_PASSWORD.get_secret_value()),
        ca_certs=PATH_ES_CERT if PATH_ES_CERT.exists() else DEFAULT,
        **kwargs,
    )
