from datetime import timezone

from app.models.notification import Notification


def add_rental_notification(db, inquiry, actor_id, action, *, sale=False):
    """Persist milestone notifications in the inquiry's existing transaction."""
    titles = {
        "created": "Novi upit za dugoročni najam",
        "propose": "Predložen termin razgledanja",
        "confirm": "Razgledanje je potvrđeno",
        "decline": "Predloženi termin nije prihvaćen",
        "close": "Upit za najam je zatvoren",
        "withdraw": "Zakupac je povukao upit",
    }
    owner = actor_id != inquiry.owner_id
    if sale:
        titles.update(
            created="Novi upit za kupovinu",
            close="Upit za kupovinu je zatvoren",
            withdraw="Kupac je povukao upit",
        )
    path = "/sales" if sale else "/rentals"
    prefix = "sale" if sale else "rental"
    recipient = inquiry.owner_id if owner else inquiry.user_id
    message = f"Upit #{inquiry.id}: {inquiry.title}."
    if action in {"propose", "confirm"} and inquiry.viewing_at:
        viewing = inquiry.viewing_at
        if viewing.tzinfo is None:
            viewing = viewing.replace(tzinfo=timezone.utc)
        message += f" Termin: {viewing.astimezone(timezone.utc):%d.%m.%Y. %H:%M} UTC."
    message += " Otvori upite za detalje i nastavak dogovora."
    db.add(
        Notification(
            user_id=recipient,
            title=titles[action],
            message=message,
            action_path=f"/owner{path}" if owner else path,
            deduplication_key=(
                f"{prefix}:{inquiry.id}:{inquiry.version}:{action}:user:{recipient}"
            ),
        )
    )
