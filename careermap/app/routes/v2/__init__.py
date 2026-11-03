"""CareerMap V2.1 REST API Router Paketi."""
from .auth_api import router as auth_router
from .employers_api import router as employers_router
from .candidate_api import router as candidate_router, public_cv_router
from .applications_api import router as applications_router
from .admin_api import router as admin_router
from .research_api import router as research_router

__all__ = [
    "auth_router",
    "employers_router",
    "candidate_router",
    "public_cv_router",
    "applications_router",
    "admin_router",
    "research_router"
]
