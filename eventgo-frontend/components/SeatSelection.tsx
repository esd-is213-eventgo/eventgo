"use client";

import { useState, useEffect } from "react";
// No longer import getAvailableSeats
import { getTicketsForEvent } from "@/lib/api";
import { Ticket, TicketStatus } from "@/lib/interfaces";

export default function SeatSelection({
  eventId,
  selectedSeats,
  toggleSeat,
  availableSeats = [],
}: {
  eventId: number;
  selectedSeats: number[];
  toggleSeat: (seatId: number) => void;
  availableSeats?: any[];
}) {
  const [localAvailableSeats, setLocalAvailableSeats] = useState<
    { id: number; seat_number: string; status: TicketStatus; price: number }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If seats are provided by parent, use those
    if (availableSeats && availableSeats.length > 0) {
      setLocalAvailableSeats(availableSeats);
      setLoading(false);
      return;
    }

    // Otherwise fetch seats
    const fetchSeats = async () => {
      try {
        // 1) Grab all tickets for this event
        const tickets: Ticket[] = await getTicketsForEvent(eventId);

        // 2) Transform them to the shape your UI expects: { id, seat_number, status }
        //    (Your UI references seat.id, seat.seat_number, seat.status, etc.)
        const transformedSeats = tickets.map((ticket) => ({
          id: ticket.ticket_id,
          seat_number: ticket.seat_number,
          status: ticket.status,
          price: ticket.price,
        }));

        // 3) If you only want "available" seats, you could filter them.
        //    But your code checks isReserved = seat.status===RESERVED||SOLD,
        //    so let's just keep the entire array in order to show them all
        //    with gray for sold/reserved seats.
        setLocalAvailableSeats(transformedSeats);
      } catch (err) {
        setError("Failed to load seats.");
      } finally {
        setLoading(false);
      }
    };

    fetchSeats();
  }, [eventId, availableSeats]);

  if (loading) {
    return (
      <p className="text-gray-600 text-center">Loading available seats...</p>
    );
  }
  if (error) {
    return <p className="text-red-500 text-center">{error}</p>;
  }

  const seatsToRender =
    availableSeats.length > 0 ? availableSeats : localAvailableSeats;

  return (
    <div className="mt-6 p-6 bg-gray-100 rounded-lg">
      <h3 className="text-lg text-black font-semibold mb-4">
        🎟️ Select Your Seats
      </h3>

      <p className="text-sm text-gray-600 mb-3">
        Selected Seats:{" "}
        {selectedSeats.length > 0
          ? selectedSeats
              // For each selected seatId, find its seat_number in availableSeats
              .map(
                (seatId) =>
                  seatsToRender.find((s) => s.id === seatId)?.seat_number ||
                  `Seat ${seatId}`
              )
              .join(", ")
          : "None"}
      </p>

      {/* Render seat buttons */}
      <div className="grid grid-cols-10 gap-2">
        {seatsToRender.map((seat) => {
          const isReserved =
            seat.status === TicketStatus.RESERVED ||
            seat.status === TicketStatus.SOLD;
          const isSelected = selectedSeats.includes(seat.id);

          return (
            <button
              key={seat.id}
              className={`w-10 h-10 text-sm font-medium rounded-md
                ${
                  isReserved
                    ? "bg-gray-400 text-white cursor-not-allowed"
                    : isSelected
                    ? "bg-blue-600 text-white"
                    : "bg-gray-300 hover:bg-gray-400"
                }`}
              onClick={() => !isReserved && toggleSeat(seat.id)}
              disabled={isReserved}
              title={
                isReserved
                  ? `Seat ${seat.seat_number} is ${seat.status}`
                  : `Seat ${seat.seat_number} - $${
                      seat.price?.toFixed(2) || "0.00"
                    }`
              }
            >
              {seat.seat_number}
            </button>
          );
        })}
      </div>
    </div>
  );
}
