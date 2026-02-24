# -*- coding: utf-8 -*-
"""
    maestro.api.dialogue
    ~~~~~~~~~~~~~~~~~~~~

    Endpoints responsible for handling the FSM and other dialogue operations.
"""

from typing import Any

from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models import api_maestro as mam
from common.models.enums import ResourceType
from common.models.fsm import Dialogue, State
from common.utils.api import error_handler, error_handler_async
from maestro.services import kronos

logger = get_component_logger()
router = APIRouter()


@router.post(
    "/projects/{project_id}/sessions/",
    response_model=mam.SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a project session",
)
@error_handler_async
async def start_session(
        project_id: str,
        starting_state_id: int = 1,
        user_id: str | None = None,
        name: str = "",
        description: str = "",
) -> mam.SessionStartResponse:
    """
    Start a project session.

    :param project_id: project ID for which to start a session
    :param starting_state_id: ID of the starting/entry state
    :param user_id: user ID for user tracking
    :param name: optional session name
    :param description: optional session description
    :return: created session data
    """

    # fsm = json.load(open("fsm/mf-ai.json"))     # for local testing
    fsm, _ = await kronos.get_resource(resource_type=ResourceType.DIALOGUE_FSM, project_id=project_id, as_json=True)
    dialogue = Dialogue.model_validate(fsm)
    logger.debug("Dialogue instance created: %s", dialogue)

    session = await kronos.create_session(
        project_id=project_id,
        user_id=user_id,
        name=name,
        description=description,
        language=dialogue.language,
    )
    logger.info("Starting session", extra={"session_id": session["_id"]})

    if not (state := next((s for s in dialogue.states if s.state_id == starting_state_id), None)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"State {starting_state_id} not found")

    return mam.SessionStartResponse(
        session_id=session["_id"],
        state_id=starting_state_id,
        state=state,
        commands=dialogue.commands,
        language=dialogue.language,
    )


@router.get(
    "/projects/{project_id}/states/{state_id}/",
    response_model=State,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a state by ID",
)
@error_handler_async
async def get_state(
        project_id: str,
        state_id: int,

        # for context logging
        session_id: str | None = None,  # noqa
        user_id: str | None = None,  # noqa
) -> State:
    """
    Retrieve a state by ID.

    :param project_id: project ID
    :param state_id: state ID to retrieve
    :param session_id: current session ID
    :param user_id: user ID for user tracking
    :return: state data
    """

    # fsm = json.load(open("fsm/mf-ai.json"))     # for local testing
    fsm, _ = await kronos.get_resource(resource_type=ResourceType.DIALOGUE_FSM, project_id=project_id, as_json=True)
    dialogue = Dialogue.model_validate(fsm)
    logger.debug("Dialogue instance created: %s", dialogue)

    if not (state := next((s for s in dialogue.states if s.state_id == state_id), None)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"State {state_id} not found")
    return state


@router.post(
    "/projects/{project_id}/feedback/",
    status_code=status.HTTP_201_CREATED,
    summary="Log user feedback",
)
@error_handler
def user_feedback(
        payload: mam.FeedbackPayload,

        # for context logging
        project_id: str,  # noqa
        session_id: str | None = None,  # noqa
        user_id: str | None = None,  # noqa
):
    """
    Log user feedback.

    :param payload: request payload containing user feedback details
    :param project_id: project ID
    :param session_id: current session ID
    :param user_id: user ID for user tracking
    """

    logger.info("user_feedback", extra=payload.model_dump())


@router.post(
    "/client_logs/",
    status_code=status.HTTP_201_CREATED,
    summary="Log client-side events",
)
@error_handler
def log_client_event(payload: Any = Body(...)):
    """
    Log client-side events.

    :param payload: request payload containing log details
    """

    logger.info("client_log", extra=payload)
