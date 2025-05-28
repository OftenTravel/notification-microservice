from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
import logging

from app.core.database import get_db
from app.repositories.provider_repository import ProviderRepository
from app.providers.msg91_provider import MSG91Provider

router = APIRouter(tags=["MSG91-Templates"])
logger = logging.getLogger(__name__)

async def get_msg91_provider(db: AsyncSession = Depends(get_db)):
    """Get properly configured MSG91 provider from database."""
    repo = ProviderRepository(db)
    provider_entity = await repo.get_provider_by_name("msg91")
    
    if not provider_entity or not provider_entity.config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="MSG91 provider not configured"
        )
    
    # Print the auth key from the provider for debugging
    auth_key = provider_entity.config.get("authkey")
    print(f"PROVIDER DB RECORD - Using MSG91_AUTH_KEY: '{auth_key}'")
    
    # Initialize MSG91 provider with database config
    provider = MSG91Provider(provider_entity.config)
    provider.initialize_provider()
    
    return provider

@router.post("/email", status_code=status.HTTP_201_CREATED)
async def create_email_template(
    name: str,
    slug: str,
    subject: str,
    body: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new email template in MSG91.
    
    - **name**: Template name
    - **slug**: Unique template identifier
    - **subject**: Email subject
    - **body**: HTML body with variables like ##name##
    """
    try:
        # Get provider from database instead of hardcoded config
        provider = await get_msg91_provider(db)
        
        # Create the template
        response = await provider.create_email_template(
            name=name,
            slug=slug,
            subject=subject,
            body=body
        )
        
        # Close the provider resources
        await provider.close()
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create template: {str(e)}"
        )


@router.get("/email")
async def list_email_templates(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    keyword: str = Query(""),
    provider: MSG91Provider = Depends(get_msg91_provider),
):
    """
    List all email templates from MSG91.
    """
    try:
        response = await provider.get_email_templates(
            page=page,
            per_page=per_page,
            keyword=keyword
        )
        
        # Close the provider resources
        if hasattr(provider, 'http_client'):
            await provider.http_client.aclose()
            
        return response
    except Exception as e:
        logger.exception(f"Error listing templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list templates: {str(e)}"
        )


@router.get("/email/{version_id}")
async def get_email_template_version(
    version_id: str = Path(..., description="Template version ID"),
    provider: MSG91Provider = Depends(get_msg91_provider),
):
    """
    Get details of a specific email template version.
    
    - **version_id**: Template version ID
    """
    try:
        response = await provider.get_template_version_details(version_id)
        
        # Close the provider resources
        if hasattr(provider, 'http_client'):
            await provider.http_client.aclose()
            
        return response
    except Exception as e:
        logger.exception(f"Error getting template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template: {str(e)}"
        )


@router.post("/email/inline-css")
async def inline_css_for_email(
    html: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Inline CSS in HTML using MSG91's inliner service.
    
    - **html**: HTML content with CSS
    """
    try:
        # Get provider from database instead of hardcoded config
        provider = await get_msg91_provider(db)
        
        # Inline CSS
        result = await provider.inline_email_css(html)
        
        # Close the provider resources
        await provider.close()
        
        return {"html": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inline CSS: {str(e)}"
        )


@router.post("/email/validate")
async def validate_email_address(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate an email address using MSG91's validation service.
    
    - **email**: Email address to validate
    
    Returns:
    ```json
    {
      "status": "success",
      "data": {
        "_id": "string",
        "user_id": 0,
        "count": 1,
        "is_bulk": false,
        "route": 1,
        "email": "email@example.com",
        "created_at": "ISO8601 timestamp",
        "updated_at": "ISO8601 timestamp",
        "charged": 1,
        "result": {
          "valid": true,
          "result": "deliverable|undeliverable|risky|unknown",
          "reason": "ACCEPTED_EMAIL|...",
          "is_disposable": false,
          "is_free": false,
          "is_role": false
        },
        "summary": {
          "total": 1,
          "deliverable": 0,
          "undeliverable": 0,
          "risky": 0,
          "unknown": 0
        }
      },
      "hasError": false,
      "errors": {}
    }
    ```
    """
    try:
        # Get provider from database
        provider = await get_msg91_provider(db)
        
        # Validate email
        result = await provider.validate_email(email)
        
        # Close the provider resources
        await provider.close()
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate email: {str(e)}"
        )