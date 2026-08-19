from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reservation_event import ReservationEvent, ReservationEventType
from app.repositories.reservation_event_repository import ReservationEventRepository
from app.repositories.reservation_repository import ReservationRepository
from app.services.notification_service import NotificationService


class ReservationReminderService:
    def __init__(self, db: AsyncSession):
        self.reservation_repository = ReservationRepository(db)
        self.reservation_event_repository = ReservationEventRepository(db)
        self.notification_service = NotificationService(db)

    async def send_due_reminders(self, current_time: datetime | None = None) -> dict:
        now = current_time or datetime.now(UTC)
        first_hours = settings.RESERVATION_FIRST_REMINDER_HOURS
        final_hours = settings.RESERVATION_FINAL_REMINDER_HOURS
        if first_hours <= final_hours:
            raise ValueError(
                "RESERVATION_FIRST_REMINDER_HOURS must be greater than "
                "RESERVATION_FINAL_REMINDER_HOURS"
            )

        candidates = await self.reservation_repository.get_reminder_candidates(
            starts_after=now,
            final_window_ends=now + timedelta(hours=final_hours),
            starts_before=now + timedelta(hours=first_hours),
            first_reminder_hours=first_hours,
            final_reminder_hours=final_hours,
        )
        sent_count = 0
        duplicate_count = 0

        for reservation, user, resource, venue in candidates:
            hours_until_start = (reservation.start_time - now).total_seconds() / 3600
            reminder_hours = (
                final_hours if hours_until_start <= final_hours else first_hours
            )
            reminder_key = f"reservation:{reservation.id}:reminder:{reminder_hours}h"
            title = f"Reservation reminder: {resource.name}"
            message = (
                f"Your reservation #{reservation.id} at {venue.name} starts at "
                f"{reservation.start_time.isoformat()}."
            )

            notification = await self.notification_service.create_notification(
                user_id=reservation.user_id,
                title=title,
                message=message,
                user_email=user.email,
                deduplication_key=reminder_key,
            )
            if notification is None:
                duplicate_count += 1
                continue

            await self.reservation_event_repository.create(
                ReservationEvent(
                    reservation_id=reservation.id,
                    event_type=ReservationEventType.REMINDER_SENT.value,
                    actor_id=None,
                    actor_role="system",
                    previous_status=reservation.status,
                    new_status=reservation.status,
                    details={
                        "reminder_hours": reminder_hours,
                        "notification_id": notification.id,
                    },
                )
            )
            sent_count += 1

        return {
            "candidate_count": len(candidates),
            "sent_count": sent_count,
            "duplicate_count": duplicate_count,
        }
