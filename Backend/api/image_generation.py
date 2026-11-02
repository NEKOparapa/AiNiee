"""Independent generated-image translation and export endpoints."""
from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import Field

from Backend.api.schemas import RequestModel
from Backend.api.image_schemas import ImageReadOptions, ImagePipelineResponse
from Backend.api.image_generation_schemas import (
    ImageGenerationOptions, ImageGenerationRequest, GeneratedImageWriteOptions, GeneratedImageWriteRequest,
)
from Backend.application.execution_context import ExecutionContext
from Backend.core.log_system import redact
from Backend.core.protocol import to_wire


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
                details = [{"loc": [redact(part) for part in issue["loc"]],
                            "type": issue["type"], "msg": redact(issue["msg"])}
                           for issue in error.errors()]
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
    def generate(body: GenerationRequest):
        from Backend.application.image_generation_pipeline_service import generate_with_checkpoint
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("image/generate-translation", context=context, operation_id=body.operation_id):
            return to_wire(generate_with_checkpoint(body.model.model_dump(),
                                                   body.config.model_dump(exclude_unset=True), context=context))

    @router.post("/write/generated-image", response_model=ImagePipelineResponse)
    def write(body: GeneratedImageWriteRequest):
        from Backend.application.generated_image_write_service import write_generated_images
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("write/generated-image", context=context):
            return to_wire(write_generated_images(body.model.model_dump(), body.options.model_dump(), context=context))

    @router.post("/image/generate-pipeline", response_model=ImagePipelineResponse)
    def pipeline(body: GenerationPipelineRequest):
        from Backend.application.image_generation_pipeline_service import translate_image_generation
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("image/generate-pipeline", context=context, operation_id=body.operation_id):
            return to_wire(translate_image_generation(body.path, read_options=body.read_options.model_dump(),
                         generation=body.generation.model_dump(exclude_unset=True), output=body.output.model_dump(), context=context))

    @router.post("/image/operations/{operation_id}/stop")
    def stop(operation_id: str):
        return runtime.stop_model_operation(operation_id)

    return router
