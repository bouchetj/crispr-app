from fastapi import APIRouter
from api.routes import validate, design, jobs

api_router = APIRouter()
api_router.include_router(validate.router, tags=["validate"])
api_router.include_router(design.router, tags=["design"])
api_router.include_router(jobs.router, tags=["jobs"])
