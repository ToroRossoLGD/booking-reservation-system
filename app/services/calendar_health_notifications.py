from app.models.notification import Notification

PROBLEMS = {
    "conflict": "Termini se preklapaju sa postojećom zauzetošću.",
    "fetch_error": "Kalendar nije preuzet ili njegov format nije podržan.",
    "key_error": (
        "Sačuvani link nije moguće dešifrovati. "
        "Ponovo poveži izvor ili se obrati administratoru."
    ),
    "blocked_empty": (
        "Prazan kalendar bi uklonio sve blokade izvora, pa je uvoz zaustavljen."
    ),
}


def add_calendar_health_notification(db, row, previous_status):
    """Use the caller's connection lock and transaction; never commit separately."""
    status = row.last_status
    if status == previous_status:
        return
    recovered = status == "applied" and previous_status in PROBLEMS
    if status not in PROBLEMS and not recovered:
        return
    # IDs and fixed text only: provider URLs, source names and guest data stay out.
    detail = (
        "Automatski uvoz je ponovo uspešan. Proveri ažuriranu zauzetost."
        if recovered
        else f"{PROBLEMS[status]} Prethodne blokade su sačuvane."
    )
    db.add(
        Notification(
            user_id=row.owner_id,
            title="Kalendar se ponovo osvežava"
            if recovered
            else "Proveri kalendar zauzetosti",
            message=(
                f"Oglas #{row.property_id}, izvor #{row.source_id}: {detail} "
                "Otvori Zauzetost u panelu svojih oglasa, "
                "zatim izvor i automatsko osvežavanje."
            ),
            action_path="/owner",
        )
    )
