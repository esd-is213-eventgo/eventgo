import { getFeaturedEvents, getTicketsForEvent } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { Event, Ticket, TicketStatus } from "@/lib/interfaces";

// Loading skeleton for events
function EventsSkeleton() {
	return (
		<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
			{[1, 2, 3, 4].map((i) => (
				<div key={i} className="bg-white rounded-lg shadow-md p-4 animate-pulse">
					<div className="h-48 bg-gray-200 rounded-md mb-4"></div>
					<div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
					<div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
					<div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
					<div className="h-4 bg-gray-200 rounded w-2/3 mb-4"></div>
					<div className="h-10 bg-gray-200 rounded"></div>
				</div>
			))}
		</div>
	);
}

// Fetch and display event list with ticket prices
async function EventsList() {
	let events: Event[] = [];
	try {
		events = await getFeaturedEvents();
	} catch (error) {
		console.error("Error fetching featured events:", error);
	}

	// Fetch ticket prices for each event
	const eventsWithPrices = await Promise.all(
		events.map(async (event) => {
			try {
				const tickets = await getTicketsForEvent(event.event_id);
				const availableTickets = tickets.filter((ticket) => ticket.status === TicketStatus.AVAILABLE);

				// Get the lowest ticket price
				const lowestPrice = availableTickets.length > 0 ? Math.min(...availableTickets.map((ticket) => ticket.price)) : null;

				return { ...event, price: lowestPrice };
			} catch (error) {
				console.error(`Error fetching tickets for event ${event.event_id}:`, error);
				return { ...event, price: null }; // Handle failure gracefully
			}
		})
	);

	return (
		<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
			{eventsWithPrices.map((event) => (
				<div key={event.event_id} className="bg-white rounded-lg shadow-md overflow-hidden flex flex-col">
					<div className="relative h-48">
						<Image src={event.image_url} alt={event.title} fill className="object-cover" />
					</div>
					<div className="p-4 bg-white flex flex-col flex-grow justify-between">
						<div>
							<span className="text-blue-600 text-sm font-medium">{event.category}</span>
							<h3 className="text-black font-semibold mt-1">{event.title}</h3>
							<p className="text-black mt-1">{formatDate(event.date)}</p>
							<p className="text-black mt-1">{event.venue}</p>
							<p className="text-black font-medium mt-2">{event.price !== null ? `Starting at $${event.price}` : "No tickets available"}</p>
						</div>
						<Link href={`/events/${event.event_id}`} className="mt-4 block text-center bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors">
							View Details
						</Link>
					</div>
				</div>
			))}
		</div>
	);
}

export default function EventsPage() {
	return (
		<div className="min-h-screen bg-white">
			<section className="py-16 bg-gray-50">
				<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
					<h2 className="text-3xl font-bold text-center mb-12 text-black">All Events</h2>
					<Suspense fallback={<EventsSkeleton />}>
						<EventsList />
					</Suspense>
				</div>
			</section>
		</div>
	);
}
