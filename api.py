"""Stateless FastAPI adapter for hosted layout generation tests."""

import ipaddress
import json
import logging
import secrets
from functools import cache
from time import perf_counter
from typing import Annotated, Literal
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from core.config import AppConfig
from core.logger import setup_logging
from schemas.layout_schema import LayoutProject
from services.output_service import OutputService
from services.requirement_agent import RequiredField, RequirementAgent
from services.template_service import TemplateRegistry

setup_logging(hosted=True)
logger = logging.getLogger(__name__)
logging.getLogger("services").setLevel(logging.WARNING)
logging.getLogger("services.pipeline_service").setLevel(logging.INFO)
app = FastAPI(title="Layout Test API", version="1.0.0")

ShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
PromptString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
AnswerString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
RequestId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class LayoutRequest(ApiModel):
    request_id: RequestId | None = None
    prompt: PromptString
    template_id: ShortString
    answers: dict[ShortString, AnswerString | None] = Field(default_factory=dict, max_length=100)
    publish: bool = False


class FieldDefinition(ApiModel):
    name: str
    question: str
    type: Literal["text", "image"]
    required: bool
    placeholder: str


class TemplateDefinition(ApiModel):
    id: str
    name: str
    fields: list[FieldDefinition]


class TemplatesResponse(ApiModel):
    templates: list[TemplateDefinition]


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"


class NeedsInputResponse(ApiModel):
    status: Literal["needs_input"] = "needs_input"
    request_id: str
    known_values: dict[str, str]
    missing_fields: list[FieldDefinition]


class TimingResponse(ApiModel):
    retrieval: int = Field(ge=0)
    reranking: int = Field(ge=0)
    generation: int = Field(ge=0)
    validation: int = Field(ge=0)
    total: int = Field(ge=0)


class PublisherResponse(ApiModel):
    status_code: int
    body: str


class CompletedResponse(ApiModel):
    status: Literal["completed"] = "completed"
    request_id: str
    layout: LayoutProject
    publisher: PublisherResponse | None = None
    timing_ms: TimingResponse


class PublishFailedResponse(ApiModel):
    status: Literal["publish_failed"] = "publish_failed"
    request_id: str
    layout: LayoutProject
    publisher: None = None
    timing_ms: TimingResponse
    error: str = "Publisher submission failed"


class GenerationFailedResponse(ApiModel):
    status: Literal["generation_failed"] = "generation_failed"
    request_id: str
    retryable: Literal[True] = True
    error: str


def _event(request_id: str, stage: str, started: float, retries: int, result: str) -> None:
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "stage": stage,
                "duration_ms": round((perf_counter() - started) * 1000),
                "retries": retries,
                "result": result,
            },
            separators=(",", ":"),
        )
    )


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = AppConfig.LAYOUT_API_KEY
    if not expected:
        raise HTTPException(status_code=503, detail="LAYOUT_API_KEY is not configured")
    if not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


@cache
def get_template_registry() -> TemplateRegistry:
    return TemplateRegistry(AppConfig.TEMPLATE_DIR)


def get_pipeline_service():
    """Import the AI stack only after the request has all required values."""
    from services.pipeline_service import get_pipeline_service as get_service

    return get_service()


def _field_definition(field: RequiredField) -> FieldDefinition:
    return FieldDefinition(
        name=field.name,
        question=field.question,
        type=field.field_type,
        required=field.required,
        placeholder=field.placeholder,
    )


def _public_https_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return False
    try:
        return ipaddress.ip_address(hostname).is_global
    except ValueError:
        return "." in hostname


@app.get("/health", response_model=HealthResponse)
@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()


@app.get(
    "/v1/templates",
    response_model=TemplatesResponse,
    dependencies=[Depends(require_api_key)],
)
def templates() -> TemplatesResponse:
    definitions = []
    for template in get_template_registry().templates:
        fields = RequirementAgent().resolve("", template)
        definitions.append(
            TemplateDefinition(
                id=template["id"],
                name=template["name"],
                fields=[_field_definition(field) for field in fields],
            )
        )
    return TemplatesResponse(templates=definitions)


@app.post(
    "/v1/layouts",
    response_model=NeedsInputResponse | CompletedResponse,
    responses={502: {"model": GenerationFailedResponse | PublishFailedResponse}},
    dependencies=[Depends(require_api_key)],
)
def create_layout(request: LayoutRequest) -> NeedsInputResponse | CompletedResponse | JSONResponse:
    request_id = request.request_id or f"req_{uuid4().hex}"
    started = perf_counter()
    template = next(
        (
            item
            for item in get_template_registry().templates
            if item.get("id") == request.template_id
        ),
        None,
    )
    if template is None:
        raise HTTPException(status_code=422, detail="Unknown template_id")

    requirement_agent = RequirementAgent()
    fields = requirement_agent.resolve(request.prompt, template)
    field_map = {field.name: field for field in fields}
    unknown_answers = sorted(request.answers.keys() - field_map.keys())
    if unknown_answers:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown answer fields: {', '.join(unknown_answers)}",
        )

    known_values = requirement_agent.extract_known_values(request.prompt, fields)
    known_values.update(
        {
            name: field_map[name].placeholder if value is None else value
            for name, value in request.answers.items()
        }
    )
    invalid_images = [
        field.name
        for field in fields
        if field.field_type == "image"
        and field.name in known_values
        and known_values[field.name] != field.placeholder
        and not _public_https_url(known_values[field.name])
    ]
    if invalid_images:
        raise HTTPException(
            status_code=422,
            detail=f"Image values must be public HTTPS URLs: {', '.join(invalid_images)}",
        )

    missing_fields = [
        field for field in fields if field.required and field.name not in known_values
    ]
    if missing_fields:
        _event(request_id, "requirements", started, 0, "needs_input")
        return NeedsInputResponse(
            request_id=request_id,
            known_values=known_values,
            missing_fields=[_field_definition(field) for field in missing_fields],
        )

    if request.publish:
        try:
            OutputService.validate_publisher_config(
                AppConfig.PUBLISHER_API_URL, AppConfig.PUBLISHER_API_KEY
            )
        except ValueError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        result = get_pipeline_service().generate(
            request.prompt, known_values, template, request_id=request_id
        )
    except RuntimeError as error:
        failure = GenerationFailedResponse(request_id=request_id, error=str(error))
        return JSONResponse(status_code=502, content=failure.model_dump(mode="json"))

    publisher = None
    if request.publish:
        publish_started = perf_counter()
        output = OutputService(
            output_file=AppConfig.OUTPUT_FILE,
            local_output=False,
            publisher_url=AppConfig.PUBLISHER_API_URL,
            publisher_api_key=AppConfig.PUBLISHER_API_KEY,
            publisher_created_by=AppConfig.PUBLISHER_CREATED_BY,
            publisher_project=AppConfig.PUBLISHER_PROJECT,
        )
        try:
            publisher_result = output.queue_job(result.layout)
        except RuntimeError:
            _event(request_id, "publisher", publish_started, result.retries, "failed")
            failure = PublishFailedResponse(
                request_id=request_id,
                layout=result.layout,
                timing_ms=result.timing_ms,
            )
            return JSONResponse(status_code=502, content=failure.model_dump(mode="json"))
        if publisher_result:
            publisher = PublisherResponse(
                status_code=publisher_result[0], body=publisher_result[1]
            )
        _event(request_id, "publisher", publish_started, result.retries, "completed")

    _event(request_id, "request", started, result.retries, "completed")
    return CompletedResponse(
        request_id=request_id,
        layout=result.layout,
        publisher=publisher,
        timing_ms=result.timing_ms,
    )
