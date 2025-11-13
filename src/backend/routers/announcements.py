"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    title: str
    message: str
    priority: Optional[str] = "medium"  # low, medium, high
    start_date: Optional[str] = None
    end_date: str
    is_active: Optional[bool] = True


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements():
    """
    Get all active announcements that should be displayed
    Filters by date range and active status
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    query = {
        "is_active": True,
        "end_date": {"$gte": current_date}
    }
    
    # Also check start_date if it exists
    announcements = []
    for announcement in announcements_collection.find(query):
        # Check start date if it exists
        if announcement.get("start_date"):
            if announcement["start_date"] <= current_date:
                announcement["_id"] = str(announcement["_id"])
                announcements.append(announcement)
        else:
            # No start date means it's always active (until end date)
            announcement["_id"] = str(announcement["_id"])
            announcements.append(announcement)
    
    # Sort by priority and creation date
    priority_order = {"high": 0, "medium": 1, "low": 2}
    announcements.sort(key=lambda x: (
        priority_order.get(x.get("priority", "medium"), 1),
        x.get("created_at", "")
    ))
    
    return announcements


@router.get("", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)):
    """
    Get all announcements for management - requires teacher authentication
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    announcements = []
    for announcement in announcements_collection.find().sort("created_at", -1):
        announcement["_id"] = str(announcement["_id"])
        announcements.append(announcement)
    
    return announcements


@router.post("", response_model=Dict[str, str])
def create_announcement(
    announcement_data: AnnouncementCreate,
    teacher_username: str = Query(...)
):
    """
    Create a new announcement - requires teacher authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    # Validate dates
    try:
        if announcement_data.start_date:
            datetime.strptime(announcement_data.start_date, "%Y-%m-%d")
        datetime.strptime(announcement_data.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Create announcement document
    announcement_doc = {
        "title": announcement_data.title,
        "message": announcement_data.message,
        "priority": announcement_data.priority,
        "start_date": announcement_data.start_date,
        "end_date": announcement_data.end_date,
        "created_by": teacher_username,
        "created_at": datetime.now().isoformat(),
        "is_active": announcement_data.is_active
    }

    result = announcements_collection.insert_one(announcement_doc)
    
    if not result.inserted_id:
        raise HTTPException(
            status_code=500, detail="Failed to create announcement")

    return {"message": "Announcement created successfully", "id": str(result.inserted_id)}


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    announcement_data: AnnouncementUpdate,
    teacher_username: str = Query(...)
):
    """
    Update an existing announcement - requires teacher authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    # Find the announcement
    try:
        from bson import ObjectId
        announcement = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    # Prepare update data
    update_data = {}
    for field, value in announcement_data.dict(exclude_unset=True).items():
        if value is not None:
            # Validate dates if provided
            if field in ["start_date", "end_date"] and value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid {field} format. Use YYYY-MM-DD")
            update_data[field] = value

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Update the announcement
    result = announcements_collection.update_one(
        {"_id": ObjectId(announcement_id)},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=500, detail="Failed to update announcement")

    return {"message": "Announcement updated successfully"}


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
):
    """
    Delete an announcement - requires teacher authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    # Delete the announcement
    try:
        from bson import ObjectId
        result = announcements_collection.delete_one({"_id": ObjectId(announcement_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}