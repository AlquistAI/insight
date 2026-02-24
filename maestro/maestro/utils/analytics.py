# -*- coding: utf-8 -*-
"""
    maestro.utils.analytics
    ~~~~~~~~~~~~~~~~~~~~~~~

    Utils for getting analytics data.
"""

from datetime import datetime, timedelta
from enum import Enum, unique
from typing import Any

from dateutil import tz
from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule


@unique
class TimeRange(str, Enum):
    ALL = "all"
    DAY = "day"
    HOUR = "hour"
    MONTH = "month"
    WEEK = "week"


def get_time_range(range_str: TimeRange = TimeRange.DAY) -> tuple[datetime, datetime]:
    """
    Get time range based on period.

    :param range_str: one of ['hour', 'day', 'week', 'month', 'all']
    :return: tuple of start & end time in UTC
    """

    end_time = datetime.now(tz=tz.UTC)

    if range_str == TimeRange.HOUR:
        start_time = end_time - timedelta(hours=1)
    elif range_str == TimeRange.DAY:
        start_time = end_time - timedelta(hours=24)
    elif range_str == TimeRange.WEEK:
        start_time = end_time - timedelta(weeks=1)
    elif range_str == TimeRange.MONTH:
        start_time = end_time - timedelta(weeks=4)
    elif range_str == TimeRange.ALL:
        start_time = end_time - relativedelta(months=12)
    else:
        raise ValueError(f"Invalid time range: {range_str}")

    return start_time, end_time


def get_detailed_time_range(time_range: TimeRange) -> list[tuple[datetime, datetime]]:
    """
    Get custom time ranges based on the period with special handling for the last day.

    :param time_range: one of ['hour', 'day', 'week', 'month', 'all']
    :return: list of tuples containing start & end time in UTC
    """

    end_time = datetime.now(tz=tz.UTC)
    ranges = []

    if time_range == TimeRange.HOUR:
        start_time = end_time - timedelta(hours=1)
        ranges.append((start_time, end_time))

    elif time_range == TimeRange.DAY:
        start_time = end_time - timedelta(hours=24)

        # Create 2-hour segments for the last day
        while start_time < end_time:
            segment_end = start_time + timedelta(hours=2)
            if segment_end > end_time:
                segment_end = end_time
            ranges.append((start_time, segment_end))
            start_time += timedelta(hours=2)

    elif time_range == TimeRange.WEEK:
        start_time = end_time - timedelta(weeks=1)

        # Create daily segments for the last week
        while start_time < end_time:
            segment_end = start_time + timedelta(days=1)
            ranges.append((start_time, segment_end))
            start_time += timedelta(days=1)

    elif time_range == TimeRange.MONTH:
        start_time = end_time - timedelta(weeks=4)

        while start_time < end_time:
            segment_end = start_time + timedelta(weeks=1)
            ranges.append((start_time, segment_end))
            start_time += timedelta(weeks=1)

    elif time_range == TimeRange.ALL:
        # Assuming 'all' is for the last year
        current_month_start = end_time.replace(day=1)
        start_time = current_month_start - relativedelta(months=12)

        # Use rrule to generate a list of month boundaries between start_time and end_time
        boundaries = list(rrule(freq=MONTHLY, dtstart=start_time, until=end_time))

        # Create segments from the boundaries:
        for i in range(len(boundaries) - 1):
            ranges.append((boundaries[i], boundaries[i + 1]))

        # If the last boundary is before end_time, add the final segment
        if boundaries and boundaries[-1] < end_time:
            ranges.append((boundaries[-1], end_time))

    return ranges


def build_start_session_query(start: datetime, end: datetime, project_id: str) -> dict[str, Any]:
    """Build query to get session start times."""

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"func_name.keyword": "start_session"}},
                    {"term": {"project_id.keyword": project_id}},
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                ],
            },
        },
        "aggs": {
            "unique_sessions": {
                "terms": {
                    "field": "session_id.keyword",
                    "size": 1000,
                    "order": {"first_start_timestamp": "desc"},
                },
                "aggs": {
                    "first_start_timestamp": {"min": {"field": "@timestamp"}},
                },
            },
        },
    }


def build_metrics_query(start: datetime, end: datetime, project_id: str) -> dict[str, Any]:
    """Build query to get session metrics."""

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"project_id.keyword": project_id}},
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                ],
            },
        },
        "aggs": {
            "by_session_id": {
                "terms": {"field": "session_id.keyword", "size": 1000},
                "aggs": {
                    "query_count": {"filter": {"term": {"message.keyword": "query"}}},
                    "feedback_count": {
                        "filter": {"term": {"message.keyword": "user_feedback"}},
                        "aggs": {
                            "positive_feedback": {"filter": {"term": {"feedback": 1}}},
                            "negative_feedback": {"filter": {"term": {"feedback": -1}}},
                        },
                    },
                },
            },
        },
    }


def build_session_count_query(start: datetime, end: datetime, project_id: str) -> dict[str, Any]:
    """Build query to count unique sessions that have a query field."""

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"project_id.keyword": project_id}},
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                    {"exists": {"field": "query"}},  # Ensures the query field is present
                ],
            },
        },
        "aggs": {
            "unique_sessions": {
                "cardinality": {
                    "field": "session_id.keyword",
                    "precision_threshold": 40000,
                },
            },
        },
    }


def build_summary_metrics_query(start: datetime, end: datetime, project_id: str) -> dict[str, Any]:
    """Build query for total query and feedback counts."""

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"project_id.keyword": project_id}},
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                ],
            },
        },
        "aggs": {
            "total_queries": {
                "filter": {"term": {"message.keyword": "query"}},
            },
            "total_feedbacks": {
                "filter": {"term": {"message.keyword": "user_feedback"}},
                "aggs": {
                    "positive": {"filter": {"term": {"feedback": 1}}},
                    "negative": {"filter": {"term": {"feedback": -1}}},
                },
            },
        },
    }


def build_unique_users_query(project_id: str, start: datetime, end: datetime) -> dict[str, Any]:
    """Build query to get the number of unique users filtered by project_id and a given time range."""

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"project_id.keyword": project_id}},
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                ],
            },
        },
        "aggs": {
            "unique_users": {
                "cardinality": {"field": "user_id.keyword"},
            },
        },
    }


def build_session_events_query(session_id: str) -> dict[str, Any]:
    """Build query to retrieve events for a specific session."""

    return {
        "size": 1000,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "query": {
            "bool": {
                "must": [
                    {"term": {"session_id.keyword": session_id}},
                    {"terms": {"message.keyword": ["start_session", "query", "user_feedback", "answer"]}},
                ],
            },
        },
    }


def build_project_sessions_query_errors(project_id: str) -> dict[str, Any]:
    """Build query to retrieve unique session_ids and their occurrence counts for logs matching a given project_id."""

    return {
        "size": 0,
        "query": {
            "term": {
                "logs.project_id.keyword": project_id,
            },
        },
        "aggs": {
            "session_occurrences": {
                "terms": {
                    "field": "session_id.keyword",
                    "size": 10000,
                },
            },
        },
    }


def build_session_events_query_errors(session_id: str) -> dict[str, Any]:
    """Build query to retrieve events for a specific session."""

    return {
        "size": 1000,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "query": {
            "bool": {
                "must": [
                    {"term": {"logs.session_id.keyword": session_id}},
                    {"exists": {"field": "logs.session_id"}},
                ],
            },
        },
        "_source": [
            "logs.timestamp",
            "logs.type",
            "logs.level",
            "logs.stack",
            "logs.message",
        ],
    }


def process_responses(start_response: dict, metrics_response: dict) -> list[dict]:
    """Process and merge results from both ElasticSearch queries."""

    sessions = _extract_base_sessions(start_response)
    _enrich_with_metrics(sessions, metrics_response)
    _calculate_feedback_percentages(sessions)
    return _format_output(sessions)


def _extract_base_sessions(response: dict) -> dict[str, Any]:
    """Extract session data from start_session query response."""

    return {
        bucket["key"]: {
            "start_timestamp": bucket["first_start_timestamp"]["value_as_string"],
            "query_count": 0,
            "feedback_count": 0,
            "positive_feedback": 0,
            "negative_feedback": 0,
        }
        for bucket in response["aggregations"]["unique_sessions"]["buckets"]
    }


def _enrich_with_metrics(sessions: dict, metrics_response: dict):
    """Add metrics data to session records."""

    for bucket in metrics_response["aggregations"]["by_session_id"]["buckets"]:
        if (session_id := bucket["key"]) in sessions:
            sessions[session_id].update({
                "query_count": bucket["query_count"]["doc_count"],
                "feedback_count": bucket["feedback_count"]["doc_count"],
                "positive_feedback": bucket["feedback_count"]["positive_feedback"]["doc_count"],
                "negative_feedback": bucket["feedback_count"]["negative_feedback"]["doc_count"],
            })


def _calculate_feedback_percentages(sessions: dict):
    """Calculate feedback percentages for each session."""

    for session in sessions.values():
        total = session["positive_feedback"] + session["negative_feedback"]
        session["feedback_percentage"] = round((session["positive_feedback"] / total * 100) if total > 0 else 0, 2)


def _format_output(sessions: dict) -> list[dict]:
    """Convert sessions dict to sorted list."""

    return sorted(
        [{"session_id": k, **v} for k, v in sessions.items()],
        key=lambda x: x["start_timestamp"],
        reverse=True,
    )


def process_session_events(response: dict[str, Any]) -> list[dict]:
    """Process raw ElasticSearch logs into simplified event format, shifting timestamps +2h."""

    events = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]

        # Parse original UTC timestamp, add 2 hours, re-serialize to ISO
        if ts := source.get("@timestamp"):
            # ElasticSearch ISO ends with 'Z' for UTC
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            dt_plus2 = dt + timedelta(hours=2)
            adjusted_ts = dt_plus2.isoformat().replace("+00:00", "Z")
        else:
            adjusted_ts = ts

        event = {"timestamp": adjusted_ts}
        event = map_event_data(source, event)
        events.append(event)

    return events


def process_unique_users_response(response: dict) -> int:
    """
    Process the raw ElasticSearch aggregation response to extract the total number of unique users.

    :param response: raw response from ElasticSearch after executing the unique users query
    :return: total number of unique users
    """

    return response.get("aggregations", {}).get("unique_users", {}).get("value", 0)


def process_session_events_errors(response: dict) -> list[dict]:
    """Process raw ElasticSearch error logs into a simplified event format."""

    events = []
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        event = {}

        # Optionally include timestamp if available in the source
        if "@timestamp" in source:
            event["timestamp"] = source["@timestamp"]

        # Extract the error log fields from the nested "logs" object
        logs = source.get("logs", {})
        event["timestamp"] = logs.get("timestamp", "")
        event["type"] = logs.get("type", "")
        event["level"] = logs.get("level", "")
        event["stack"] = logs.get("stack", "")
        event["message"] = logs.get("message", "")
        events.append(event)

    return events


def process_session_error_occurrences(response: dict) -> list[dict]:
    """
    Process the raw ElasticSearch aggregation response to extract session_ids and their occurrence counts.

    :param response: raw response from ElasticSearch after executing the session occurrences query
    :return: list of dictionaries containing 'session_id' and 'occurrences' count
    """

    return [
        {"session_id": bucket.get("key"), "occurrences": bucket.get("doc_count")}
        for bucket in response.get("aggregations", {}).get("session_occurrences", {}).get("buckets", [])
    ]


def map_event_data(source: dict, event: dict) -> dict:
    """Map event types to their respective payloads."""

    match source["message"]:
        case "start_session":
            event["start_session"] = {"component_id": source.get("component_id"), "user_id": source.get("user_id")}
        case "query":
            event["query"] = source.get("query")
        case "answer":
            event["answer"] = source.get("answer")
        case "user_feedback":
            event["feedback"] = source.get("feedback")
    return event


def process_project_stats_aggregations(session_count_response: dict, metrics_response: dict) -> dict:
    """Process ElasticSearch aggregation results for project statistics."""

    try:
        total_sessions = session_count_response["aggregations"]["unique_sessions"]["value"]
        total_queries = metrics_response["aggregations"]["total_queries"]["doc_count"]
        total_positive = metrics_response["aggregations"]["total_feedbacks"]["positive"]["doc_count"]
        total_negative = metrics_response["aggregations"]["total_feedbacks"]["negative"]["doc_count"]

        return {
            "total_queries": total_queries,
            "total_positive_feedback": total_positive,
            "total_negative_feedback": total_negative,
            "total_sessions": total_sessions,
        }

    except KeyError as e:
        raise ValueError(f"Error processing aggregation results: Missing key {e}")
