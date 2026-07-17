from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.document_store import doc_store_client
from app.core.logging import logger, setup_logging

# Configure logging before application startup
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle events."""
    logger.info(
        "Initializing FastAPI app",
        project=settings.PROJECT_NAME,
        env=settings.ENVIRONMENT,
    )

    # Initialize external resources (e.g. MongoDB/JSON store connections)
    await doc_store_client.connect()

    yield

    # Clean up resources
    logger.info("Shutting down FastAPI app")
    await doc_store_client.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Configure CORS (Cross-Origin Resource Sharing)
# In production, restrict the allowed origins to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(api_router)
