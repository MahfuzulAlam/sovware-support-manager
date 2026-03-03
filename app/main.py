"""Main FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.routes import reply
from app.routes import translate
from app.routes import webhook
# Database disabled for now
# from app.database import init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Starting application...")
    # Database initialization disabled
    # try:
    #     await init_db()
    #     logger.info("Database initialized")
    # except Exception as e:
    #     logger.error(f"Failed to initialize database: {e}")
    #     raise
    logger.info("Application started (database disabled)")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    # Database cleanup disabled
    # await close_db()
    logger.info("Application shut down complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered support ticket evaluation system for Help Scout",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(reply.router)
app.include_router(translate.router)
app.include_router(webhook.router)


@app.get("/", tags=["health"])
async def root():
    """
    Root endpoint - health check.

    Returns:
        Dict with application status
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Dict with health status
    """
    return {"status": "healthy", "service": "sovware-support-manager"}


@app.get("/doc", tags=["documentation"])
async def api_doc():
    """
    Returns the full OpenAPI schema with all API info (endpoints, methods, schemas, descriptions).
    """
    return app.openapi()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions.

    Args:
        request: The request that caused the exception
        exc: The exception that was raised

    Returns:
        JSONResponse with error details
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "error": str(exc) if settings.debug else "Internal server error",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )

