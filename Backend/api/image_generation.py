"""Independent generated-image translation and export endpoints."""
from fastapi import APIRouter, Depends, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import Field

from Backend.api.schemas import RequestModel
from Backend.api.image_schemas import ImageReadOptions, ImagePipelineResponse
from Backend.api.image_generation_schemas import (
    ImageGenerationOptions, ImageGenerationRequest, GeneratedImageWriteOptions, GeneratedImageWriteRequest,
)
from Backend.api.queued import require_model_lane, run_queued
from Backend.api.error_logging import log_validation_error, validation_details


class GenerationRoute(APIRoute):
    """Keep submitted provider credentials out of validation responses."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_validation(request):
            try:
                return await handler(request)
            except RequestValidationError as error:
                # Pydantic includes the rejected input even for repr=False fields.
                # ctx can contain it too; expose only the useful diagnostics.
                details = validation_details(error)
                log_validation_error(request, details)
                return JSONResponse(status_code=422, content={"detail": details})

        return safe_validation


class GenerationRequest(ImageGenerationRequest):
    operation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,80}$")


class GenerationPipelineRequest(RequestModel):
    path: str = Field(min_length=1)
    read_options: ImageReadOptions = Field(default_factory=ImageReadOptions)
    generation: ImageGenerationOptions = Field(default_factory=ImageGenerationOptions)
    output: GeneratedImageWriteOptions
    operation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,80}$")


def create_image_generation_router(runtime, authorized):
    router = APIRouter(prefix="/api/v2", tags=["Generated image translation"],
                       dependencies=[Depends(authorized)], route_class=GenerationRoute)

    @router.post("/image/generate-translation", response_model=ImagePipelineResponse)
    async def generate(body: GenerationRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "image")
        def action(context):
            from Backend.application.image_generation_pipeline_service import generate_with_checkpoint
            return generate_with_checkpoint(model, body.config.model_dump(exclude_unset=True), context=context)
        return await run_queued(runtime, "image/generate-translation", action, lane="image", prefer=prefer,
                          operation_id=body.operation_id, project_id=model.get("project_id"))

    @router.post("/write/generated-image", response_model=ImagePipelineResponse)
    async def write(body: GeneratedImageWriteRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "image")
        def action(context):
            from Backend.application.generated_image_write_service import write_generated_images
            return write_generated_images(model, body.options.model_dump(), context=context)
        return await run_queued(runtime, "write/generated-image", action, lane="image", prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/image/generate-pipeline", response_model=ImagePipelineResponse)
    async def pipeline(body: GenerationPipelineRequest, prefer: str | None = Header(default=None)):
        def action(context):
            from Backend.application.image_generation_pipeline_service import translate_image_generation
            return translate_image_generation(body.path, read_options=body.read_options.model_dump(),
                         generation=body.generation.model_dump(exclude_unset=True), output=body.output.model_dump(), context=context)
        return await run_queued(runtime, "image/generate-pipeline", action, lane="image", prefer=prefer,
                          operation_id=body.operation_id)

    @router.post("/image/operations/{operation_id}/stop")
    def stop(operation_id: str):
        return runtime.stop_model_operation(operation_id)

    return router
