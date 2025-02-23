"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getAvailableSeats } from "@/lib/api";
import { Seat, TicketStatus } from "@/lib/interfaces";

export default function SeatSelection({ eventId }: { eventId: number }) {
	const [availableSeats, setAvailableSeats] = useState<Seat[]>([]);
	const [selectedSeats, setSelectedSeats] = useState<number[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchSeats = async () => {
			try {
				const seats = await getAvailableSeats(eventId);
				setAvailableSeats(seats);
			} catch (err) {
				setError("Failed to load seats.");
			} finally {
				setLoading(false);
			}
		};
		fetchSeats();
	}, [eventId]);

	const toggleSeat = (seatId: number) => {
		setSelectedSeats((prev) => (prev.includes(seatId) ? prev.filter((s) => s !== seatId) : [...prev, seatId]));
	};

	if (loading) return <p className="text-gray-600 text-center">Loading available seats...</p>;
	if (error) return <p className="text-red-500 text-center">{error}</p>;

	return (
		<div className="mt-6 p-6 bg-gray-100 rounded-lg">
			<h3 className="text-lg text-black font-semibold mb-4">🎟️ Select Your Seats</h3>

			{/* Render seat buttons */}
			<div className="grid grid-cols-10 gap-2">
				{availableSeats.map((seat) => {
					const isReserved = seat.status === TicketStatus.RESERVED || seat.status === TicketStatus.SOLD;
					const isSelected = selectedSeats.includes(seat.id);

					return (
						<button
							key={seat.id}
							className={`w-10 h-10 text-sm font-medium rounded-md 
                ${isReserved ? "bg-gray-400 text-white cursor-not-allowed" : isSelected ? "bg-blue-600 text-white" : "bg-gray-300 hover:bg-gray-400"}`}
							onClick={() => !isReserved && toggleSeat(seat.id)}
							disabled={isReserved}
							title={isReserved ? `Seat ${seat.seat_number} is ${seat.status}` : ""}
						>
							{seat.seat_number}
						</button>
					);
				})}
			</div>

			{selectedSeats.length > 0 && <p className="mt-3 text-sm text-gray-600">Selected Seats: {selectedSeats.join(", ")}</p>}

			<Link
				href={`/checkout?eventId=${eventId}&seats=${selectedSeats.join(",")}`}
				className={`mt-6 block text-center bg-blue-600 text-white font-medium py-3 px-8 rounded-md 
          hover:bg-blue-700 transition-colors ${selectedSeats.length === 0 ? "opacity-50 pointer-events-none" : ""}`}
			>
				Buy Tickets ({selectedSeats.length} Selected)
			</Link>
		</div>
	);
}
