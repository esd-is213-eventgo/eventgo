from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime
from . import models, schemas
from .database import engine, get_db, Base
from sqlalchemy.sql import text

app = FastAPI(title="Events Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Create database tables on application startup."""
    Base.metadata.create_all(bind=engine)


# 🩺 Health check
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🎟 Get all events 
@app.get("/events", response_model=List[schemas.EventResponse])
async def list_events(is_featured: bool = False, db: Session = Depends(get_db)):
    """Retrieve all events or only featured ones based on query parameter."""
    query = db.query(models.Event)
    if is_featured:
        query = query.filter(models.Event.is_featured == True)
    events = query.options(joinedload(models.Event.seats)).all()
    return events


# 🎟 Get event details of specific event
@app.get("/events/{event_id}", response_model=schemas.EventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    """Retrieve event details including available seats."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


# ✅ 1️⃣ Create an event (Automatically generates seats)
@app.post("/events", response_model=schemas.EventResponse)
async def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    """Create a new event and automatically generate seats."""
    db_event = models.Event(**event.dict())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # Generate seats
    seats = []
    for i in range(1, event.capacity + 1):
        seat_number = f"{event.venue[:3].upper()}-{i}"  # Unique seat ID per venue
        seat = models.Seat(
            event_id=db_event.id, seat_number=seat_number, category="Standard"
        )
        seats.append(seat)

    db.add_all(seats)
    db.commit()

    return db_event

# ✅ Update an event 
@app.patch("/events/{event_id}", response_model=schemas.EventResponse)
def update_event(event_id: int, event_data: schemas.EventUpdate, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    for key, value in event_data.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    
    db.commit()
    db.refresh(event)
    return event

# ✅ Delete an event
@app.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    return {"status": "success", "message": "Event deleted successfully"}

