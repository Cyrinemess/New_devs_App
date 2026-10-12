from typing import Annotated, Any

from app.core.auth import authenticate_request as get_current_user
from app.models.auth import AuthenticatedUser
from app.services.cache import get_revenue_summary
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter()


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, Any]:

    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A tenant context is required",
        )

    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Revenue data is temporarily unavailable",
        ) from error

    return {
        "property_id": revenue_data["property_id"],
        # Keep the exact two-decimal value in JSON instead of introducing
        # binary floating-point drift at the API boundary.
        "total_revenue": revenue_data["total"],
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
    }
