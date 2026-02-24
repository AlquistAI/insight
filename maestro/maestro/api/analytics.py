# -*- coding: utf-8 -*-
"""
    maestro.api.analytics
    ~~~~~~~~~~~~~~~~~~~~~

    Endpoints used for getting analytics data.

    ToDo: Add JWT auth to these endpoints. They are called only from the admin console.
"""

from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.routing import APIRouter

from common.config import CONFIG
from common.services import elastic
from common.utils.api import error_handler
from maestro.utils import analytics as ua

router = APIRouter()
es_client = elastic.get_client()


@router.get(
    "/project-total-users",
    status_code=status.HTTP_200_OK,
    summary="Get total number of users for given time range",
)
@error_handler
def get_session_events_errors(project_id: str, time_range: ua.TimeRange = ua.TimeRange.DAY):
    """
    Get total number of users for given time range.

    :param project_id: project ID
    :param time_range: time range
    :return: total number of users
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    # Get time range and fetch data
    start_time, end_time = ua.get_time_range(time_range)

    # Build query and fetch events
    query_body = ua.build_unique_users_query(project_id, start_time, end_time)
    response = es_client.search(index=CONFIG.ES_INDEX_LOGS, body=query_body)

    # Process and return events
    return {"data": ua.process_unique_users_response(response)}


@router.get(
    "/session-events",
    status_code=status.HTTP_200_OK,
    summary="Get event logs for a specific session",
)
@error_handler
def get_session_events(session_id: str):
    """
    Get event logs for a specific session.

    :param session_id: session ID
    :return: list of events ordered chronologically
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    # Build query and fetch events
    query_body = ua.build_session_events_query(session_id)
    response = es_client.search(index=CONFIG.ES_INDEX_LOGS, body=query_body)

    # Process and return events
    return {"data": ua.process_session_events(response)}


@router.get(
    "/session-events-errors",
    status_code=status.HTTP_200_OK,
    summary="Get error logs for a specific session",
)
@error_handler
def get_session_events_errors(session_id: str):
    """
    Get error logs for a specific session.

    :param session_id: session ID
    :return: list of errors ordered chronologically
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    # Build query and fetch events
    query_body = ua.build_session_events_query_errors(session_id)
    response = es_client.search(index=CONFIG.ES_INDEX_LOGS, body=query_body)

    # Process and return events
    return {"data": ua.process_session_events_errors(response)}


@router.get(
    "/project-stats-errors",
    status_code=status.HTTP_200_OK,
    summary="Get total number of errors for project",
)
@error_handler
def get_session_events_errors_count(project_id: str):
    """
    Get total number of errors for project.

    :param project_id: project ID
    :return: error count
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    # Build query and fetch events
    query_body = ua.build_project_sessions_query_errors(project_id)
    response = es_client.search(index=CONFIG.ES_INDEX_LOGS, body=query_body)

    # Process and return events
    return {"data": ua.process_session_error_occurrences(response)}


@router.get(
    "/project-stats",
    status_code=status.HTTP_200_OK,
    summary="Get session analytics for project",
)
@error_handler
def get_latest_logs(project_id: str, time_range: ua.TimeRange = ua.TimeRange.DAY):
    """
    Get session analytics for project.

    :param project_id: project ID
    :param time_range: time range
    :return: list of sessions with timestamps, query counts and feedback metrics
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    # Get time range and fetch data
    start_time, end_time = ua.get_time_range(time_range)
    start_response = es_client.search(
        index=CONFIG.ES_INDEX_LOGS,
        body=ua.build_start_session_query(start_time, end_time, project_id),
    )
    metrics_response = es_client.search(
        index=CONFIG.ES_INDEX_LOGS,
        body=ua.build_metrics_query(start_time, end_time, project_id),
    )

    # Process and return data
    return {"status": "success", "sessions": ua.process_responses(start_response, metrics_response)}


@router.get(
    "/project-stats-summary",
    status_code=status.HTTP_200_OK,
    summary="Get aggregated statistics for project",
)
@error_handler
def get_project_stats_summary(project_id: str, time_range: ua.TimeRange = ua.TimeRange.DAY):
    """
    Get aggregated statistics for project.

    :param project_id: project ID
    :param time_range: time range
    :return: total queries, feedback counts and unique sessions
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    # Get time range and fetch data
    start_time, end_time = ua.get_time_range(time_range)
    session_count_response = es_client.search(
        index=CONFIG.ES_INDEX_LOGS,
        body=ua.build_session_count_query(start_time, end_time, project_id),
    )
    metrics_response = es_client.search(
        index=CONFIG.ES_INDEX_LOGS,
        body=ua.build_summary_metrics_query(start_time, end_time, project_id),
    )

    # Process and return stats
    stats = ua.process_project_stats_aggregations(session_count_response, metrics_response)
    return {"status": "success", "stats": stats}


@router.get(
    "/project-stats-timerange-summary",
    status_code=status.HTTP_200_OK,
    summary="Get aggregated statistics for project within specific timerange",
)
@error_handler
def get_project_stats_timerange_summary(project_id: str, time_range: ua.TimeRange = ua.TimeRange.DAY):
    """
    Get aggregated statistics for project within specific timerange.

    :param project_id: project ID
    :param time_range: time range
    :return: total queries, feedback counts and unique sessions
    """

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    res = []

    # Get time range and fetch data
    for start_time, end_time in ua.get_detailed_time_range(time_range):
        session_count_response = es_client.search(
            index=CONFIG.ES_INDEX_LOGS,
            body=ua.build_session_count_query(start_time, end_time, project_id),
        )
        metrics_response = es_client.search(
            index=CONFIG.ES_INDEX_LOGS,
            body=ua.build_summary_metrics_query(start_time, end_time, project_id),
        )

        res.append(ua.process_project_stats_aggregations(session_count_response, metrics_response))

    return {"status": "success", "stats": res}


@router.get(
    "/debug_latest_logs",
    status_code=status.HTTP_200_OK,
    summary="Get latest ElasticSearch logs for debugging",
)
@error_handler
def debug_latest_logs():
    """Get latest ElasticSearch logs for debugging."""

    if not es_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ElasticSearch client not initialized")

    response = es_client.search(
        index=CONFIG.ES_INDEX_LOGS,
        body={"size": 1000, "sort": [{"@timestamp": {"order": "desc"}}]},
    )

    return {
        "status": "debug",
        "count": response["hits"]["total"]["value"],
        "logs": [hit["_source"] for hit in response["hits"]["hits"]],
    }
