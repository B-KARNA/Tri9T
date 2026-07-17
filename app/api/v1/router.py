from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.endpoints.documents import documents_router, versions_router
from app.api.v1.endpoints.nodes import changes_router, nodes_router, search_router

api_router = APIRouter()

# Include resource routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(
    documents_router, prefix="/documents", tags=["documents"]
)
api_router.include_router(versions_router, prefix="/versions", tags=["versions"])
api_router.include_router(nodes_router, prefix="/nodes", tags=["nodes"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(changes_router, prefix="/changes", tags=["changes"])
