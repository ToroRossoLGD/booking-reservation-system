from app.models.notification import Notification
from app.models.stay import Stay


def add_stay_notifications(db, stay: Stay, owner_id: int):
    """Queue both recipients in the caller's booking transaction; never commit here."""
    cancelled = stay.status == "cancelled"
    dates = f"{stay.check_in:%d.%m.%Y.} – {stay.check_out:%d.%m.%Y.}"
    amount = f"{stay.total_cents // 100}.{stay.total_cents % 100:02d} {stay.currency}"
    details = f"Rezervacija #{stay.id}: {stay.title}. {dates} ({stay.timezone})."
    for user_id, path, title, message in (
        (
            stay.user_id,
            "/stays",
            "Boravak je otkazan" if cancelled else "Boravak je potvrđen",
            "Besplatno otkazivanje je potvrđeno."
            if cancelled
            else f"Ukupno: {amount}. Plaćanje kod domaćina.",
        ),
        (
            owner_id,
            "/owner/stays",
            "Gost je otkazao rezervaciju" if cancelled else "Nova rezervacija stana",
            "Termin je ponovo slobodan za rezervisanje."
            if cancelled
            else (
                f"Broj gostiju: {stay.guests}. Ukupno: {amount}. Plaćanje kod domaćina."
            ),
        ),
    ):
        db.add(
            Notification(
                user_id=user_id,
                title=title,
                message=f"{details} {message}",
                action_path=path,
                deduplication_key=f"stay:{stay.id}:{stay.status}:user:{user_id}",
            )
        )
