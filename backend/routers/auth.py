"""
Authentication Router for LoanIQ.
Demo login accepts only a verified Merchant ID from merchants.csv.
"""

from fastapi import APIRouter, HTTPException
from backend.schemas.merchant import MerchantAuthRequest, MerchantAuthResponse
from backend.services.merchant_service import get_all_merchant_ids, get_merchant_profile

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/login", response_model=MerchantAuthResponse)
def login(req: MerchantAuthRequest):
    merchant_id = req.merchant_id.strip().upper()
    valid_ids = get_all_merchant_ids()
    if merchant_id not in valid_ids:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid demo Merchant ID '{merchant_id}'. Valid IDs are: {', '.join(valid_ids)}"
        )

    profile = get_merchant_profile(merchant_id)
    return MerchantAuthResponse(
        authenticated=True,
        merchant_id=merchant_id,
        profile=profile,
        message=f"Welcome {profile.business_name}! Demo authentication successful."
    )


@auth_router.post("/logout")
def logout():
    return {"authenticated": False, "message": "Demo session closed successfully."}


@auth_router.get("/merchants")
def get_available_merchants():
    """Returns the list of valid demo merchant IDs to populate the login selector."""
    valid_ids = get_all_merchant_ids()
    merchants = []
    for m_id in valid_ids:
        p = get_merchant_profile(m_id)
        if p:
            merchants.append({
                "merchant_id": p.merchant_id,
                "business_name": p.business_name,
                "city": p.city,
                "merchant_type": p.merchant_type
            })
    return {"merchants": merchants}

