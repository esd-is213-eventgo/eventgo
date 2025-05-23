import os
import requests
from fastapi import FastAPI, Depends, HTTPException, Body, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.sql import text
from . import models, schemas
from .database import engine, get_db
from .dependencies import get_current_user

app = FastAPI(title="Tickets Service")

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# On startup, create the database schema
@app.on_event("startup")
async def startup():
    models.Base.metadata.create_all(bind=engine)


# Health-check endpoint
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------
# EVENTS-SERVICE CONFIG
# ----------------------------------------------------------
# Uses correct Docker internal network URL
EVENTS_SERVICE_URL = os.getenv("EVENTS_SERVICE_URL", "http://events-service:8000")


# ----------------------------------------------------------
# GET Booked Seats (Fetches from Events Service)
# ----------------------------------------------------------
@app.get("/events/{event_id}/booked-seats", response_model=List[int])
async def get_booked_seats(event_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a list of seat IDs that are either RESERVED or SOLD for a given event.
    """
    booked_tickets = (
        db.query(models.Ticket)
        .filter(models.Ticket.event_id == event_id)
        .filter(
            models.Ticket.status.in_(
                [models.TicketStatus.RESERVED, models.TicketStatus.SOLD]
            )
        )
        .all()
    )

    booked_seat_ids = [ticket.seat_id for ticket in booked_tickets]
    return booked_seat_ids


# ----------------------------------------------------------
# REPLACE or UPDATE this endpoint
# ----------------------------------------------------------
@app.get("/events/{event_id}/seats", response_model=List[schemas.SeatWithStatus])
async def get_seats_with_status(event_id: int, db: Session = Depends(get_db)):
    """
    Return all seats (from Events Service) for the given event_id,
    each with a real-time status: "AVAILABLE", "RESERVED", or "SOLD".
    """
    # 1) Fetch the seat list from the Events-Service (via /events/{event_id})
    EVENTS_SERVICE_URL = os.getenv("EVENTS_SERVICE_URL", "http://events-service:8000")
    try:
        resp = requests.get(f"{EVENTS_SERVICE_URL}/events/{event_id}", timeout=5)
        resp.raise_for_status()
        event_data = resp.json()
        seats_from_events = event_data.get("seats", [])
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving seats from Events Service: {e}"
        )

    # If no seats exist in the event-service, just return an empty list
    if not seats_from_events:
        return []

    # 2) Build a map of seat_id -> ticket.status from the local tickets DB
    seat_ids = [s["id"] for s in seats_from_events]
    tickets = db.query(models.Ticket).filter(models.Ticket.seat_id.in_(seat_ids)).all()
    seat_status_map = {
        ticket.seat_id: ticket.status.value  # e.g. "RESERVED" or "SOLD"
        for ticket in tickets
    }

    # 3) Combine seat data (from Events) with seat status (from Tickets)
    result = []
    for seat in seats_from_events:
        seat_id = seat["id"]
        # If a seat is not in seat_status_map, that means no ticket was created => "AVAILABLE"
        status = seat_status_map.get(seat_id, "AVAILABLE")

        # Build a unified seat-with-status dictionary
        item = {
            "id": seat_id,
            "event_id": seat["event_id"],
            "seat_number": seat["seat_number"],
            "category": seat["category"],
            "status": status,
        }
        result.append(item)

    return result


# ----------------------------------------------------------
# GET Available Seats (Fetches from Events Service)
# ----------------------------------------------------------
@app.get("/events/{event_id}/seats", response_model=List[schemas.SeatResponse])
async def get_available_seats(event_id: int):
    """Fetch available seats from events-service instead of using local database."""
    try:
        print(
            f"[DEBUG] Fetching seats for event {event_id} from {EVENTS_SERVICE_URL}/events/{event_id}"
        )
        response = requests.get(f"{EVENTS_SERVICE_URL}/events/{event_id}", timeout=5)
        response.raise_for_status()
        event_data = response.json()
        seats = event_data.get("seats", [])
        print(f"[DEBUG] Retrieved {len(seats)} seats from events-service")
        return seats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving seats: {e}")


# ----------------------------------------------------------
# POST /tickets/reserve (Now fetches seats from Events-Service)
# ----------------------------------------------------------
@app.post("/tickets/reserve")
async def reserve_tickets(
    seat_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ✅ Requires authentication
):
    """Reserve multiple tickets after verifying seat availability."""

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized: Login required.")

    print(
        f"[DEBUG] Authenticated user {current_user['email']} is reserving seats {seat_ids}"
    )

    # 🔍 Fetch event data from Events-Service
    try:
        response = requests.get(f"{EVENTS_SERVICE_URL}/events", timeout=5)
        response.raise_for_status()
        all_events = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching events: {e}")

    # 🔍 Aggregate all valid seat IDs from all events
    valid_seat_ids = {
        seat["id"] for event in all_events for seat in event.get("seats", [])
    }

    print(f"[DEBUG] Valid seat IDs from events-service: {valid_seat_ids}")

    # ✅ Ensure all requested seat IDs exist
    if not set(seat_ids).issubset(valid_seat_ids):
        print(f"[ERROR] Invalid seat selection. Requested: {seat_ids}")
        raise HTTPException(
            status_code=400, detail="One or more selected seats are invalid."
        )

    # ✅ Check if any of these seats are already reserved or sold
    existing_tickets = (
        db.query(models.Ticket).filter(models.Ticket.seat_id.in_(seat_ids)).all()
    )
    if existing_tickets:
        reserved_ids = [t.seat_id for t in existing_tickets]
        print(f"[ERROR] Some seats are already reserved: {reserved_ids}")
        raise HTTPException(
            status_code=400, detail=f"Seats {reserved_ids} are already taken."
        )

    # ✅ Create tickets for the selected seats
    tickets = []
    for seat_id in seat_ids:
        ticket = models.Ticket(
            event_id=None,  # No local event reference needed, as it exists in events-service
            seat_id=seat_id,
            price=50.0,
            status=models.TicketStatus.RESERVED,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        tickets.append(ticket)

    print(f"[DEBUG] Successfully reserved tickets: {[t.id for t in tickets]}")

    return {
        "message": "Tickets reserved successfully. Proceed to payment.",
        "tickets": [t.id for t in tickets],
    }


# ----------------------------------------------------------
# POST /tickets/purchase (Purchases Reserved Tickets)
# ----------------------------------------------------------
@app.post("/tickets/purchase")
async def purchase_tickets(
    ticket_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ✅ Requires authentication
):
    """Confirm payment for multiple reserved tickets and mark them as SOLD."""

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized: Login required.")

    print(f"[DEBUG] User {current_user['email']} is purchasing tickets {ticket_ids}")

    tickets = db.query(models.Ticket).filter(models.Ticket.id.in_(ticket_ids)).all()

    if len(tickets) != len(ticket_ids):
        raise HTTPException(
            status_code=400, detail="One or more ticket IDs are invalid."
        )

    for ticket in tickets:
        if ticket.status != models.TicketStatus.RESERVED:
            raise HTTPException(
                status_code=400, detail=f"Ticket {ticket.id} is not reserved."
            )

    for ticket in tickets:
        ticket.status = models.TicketStatus.SOLD
    db.commit()

    print(f"[DEBUG] Tickets purchased successfully: {ticket_ids}")

    return {"message": "Payment confirmed. Tickets are now SOLD."}
