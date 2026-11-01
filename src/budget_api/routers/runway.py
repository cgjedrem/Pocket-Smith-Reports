"""Runway routes. Local source validation and calculation live in service."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from budget_api.models.runway import RunwayResponse, RunwaySettings, RunwayUpdate
from budget_api.services import runway


async def _validate_request(request: Request):
    if request.query_params:
        raise HTTPException(400, "Runway endpoints do not accept query parameters.")
    if request.method == "GET" and await request.body():
        raise HTTPException(400, "Runway GET endpoints do not accept a request body.")
    if request.method == "PUT":
        def unique_fields(pairs):
            keys = [key for key, _ in pairs]
            if len(keys) != len(set(keys)):
                raise ValueError
            return dict(pairs)

        try:
            json.loads(await request.body(), object_pairs_hook=unique_fields)
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(400, "Runway settings require valid JSON with unique fields.") from None


router = APIRouter(dependencies=[Depends(_validate_request)])


def _call(operation, *args):
    try:
        return operation(*args)
    except runway.RunwayServiceError as error:
        raise HTTPException(error.status, error.detail) from None
    except Exception:
        # No raw source or exception details in logs/responses.
        raise HTTPException(500, "Runway request could not be completed safely.") from None


@router.get("/bills/runway", response_model=RunwayResponse)
def result():
    return _call(runway.calculate_runway)


@router.get("/settings/runway", response_model=RunwaySettings)
def settings():
    return _call(runway.get_settings)


@router.put("/settings/runway", response_model=RunwaySettings)
def save(body: RunwayUpdate):
    return _call(runway.save_settings, body)
