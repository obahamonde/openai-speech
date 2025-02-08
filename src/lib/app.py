import typing as tp

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse


def create_application(
    *, title: str, description: str, version: str, routers: tp.List[APIRouter]
) -> FastAPI:
    app = FastAPI(title=title, description=description, version=version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def _(_: Request, exc: HTTPException):
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail, "code": exc.status_code},
        )

    for router in routers:
        app.include_router(router, prefix="/v1")
    return app
