# -*- coding: utf-8 -*-
"""
    common.utils.api
    ~~~~~~~~~~~~~~~~

    Utility functions used in APIs.
"""

from base64 import b64encode
from functools import wraps

from fastapi import status
from fastapi.exceptions import HTTPException
from pydantic import ValidationError

from common.core import get_component_logger
from common.utils import exceptions as exc

logger = get_component_logger()

EXC_TO_STATUS = {
    exc.DBRecordAlreadyExists: status.HTTP_409_CONFLICT,
    exc.DBRecordNotFound: status.HTTP_404_NOT_FOUND,
    exc.InvalidModelProvider: status.HTTP_400_BAD_REQUEST,
    exc.ResourceNotFound: status.HTTP_404_NOT_FOUND,
    exc.ResourceNotFoundURL: status.HTTP_404_NOT_FOUND,
    exc.UnsupportedContentType: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
}

HANDLED_EXCEPTIONS = tuple(EXC_TO_STATUS.keys())


def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
        except HTTPException as e:
            logger.error(e)
            raise e
        except HANDLED_EXCEPTIONS as e:
            logger.error(e)
            raise HTTPException(EXC_TO_STATUS[type(e)], str(e))
        except Exception as e:
            logger.exception(msg := f"Unhandled exception occurred: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, msg) from e

    return wrapper


def error_handler_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):

        try:
            return await func(*args, **kwargs)
        except ValidationError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
        except HTTPException as e:
            logger.error(e)
            raise e
        except HANDLED_EXCEPTIONS as e:
            logger.error(e)
            raise HTTPException(EXC_TO_STATUS[type(e)], str(e))
        except Exception as e:
            logger.exception(msg := f"Unhandled exception occurred: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, msg) from e

    return wrapper


def encode_header_string(v: str) -> str:
    """
    Encode a string to be passed in the headers.

    :param v: input string
    :return: encoded string
    """

    return b64encode(v.encode("utf-8")).decode()
