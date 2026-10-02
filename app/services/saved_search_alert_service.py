from urllib.parse import parse_qsl, urlencode

from sqlalchemy import select

from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.saved_search import SavedSearch
from app.models.saved_search_match import SavedSearchMatch
from app.models.user import User
from app.models.venue import Venue
from app.repositories.property_listing_repository import PropertyListingRepository
from app.schemas.property_listing import PropertySearch


def pending_properties(search_id, since):
    return select(PropertyListing.id).where(
        PropertyListing.first_published_at >= since,
        ~select(SavedSearchMatch.search_id)
        .where(
            SavedSearchMatch.search_id == search_id,
            SavedSearchMatch.property_id == PropertyListing.id,
        )
        .correlate(PropertyListing, SavedSearch)
        .exists(),
    )


class SavedSearchAlertService:
    def __init__(self, db):
        self.db = db

    async def candidates(self, limit=25):
        result = await self.db.scalars(
            select(SavedSearch.id)
            .where(
                SavedSearch.alerts_enabled.is_(True),
                SavedSearch.alerts_since.is_not(None),
                pending_properties(SavedSearch.id, SavedSearch.alerts_since).exists(),
            )
            .order_by(SavedSearch.id)
            .limit(limit)
        )
        return list(result.all())

    async def process(self, search_id, limit=50):
        user_id = await self.db.scalar(
            select(SavedSearch.user_id).where(SavedSearch.id == search_id)
        )
        if user_id is None:
            return 0
        # Same lock order as saving, deleting and changing opt-in preferences.
        locked = await self.db.scalar(
            select(User.id).where(User.id == user_id).with_for_update(skip_locked=True)
        )
        if locked is None:
            return 0
        search = await self.db.scalar(
            select(SavedSearch)
            .where(SavedSearch.id == search_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if search is None or not search.alerts_enabled or search.alerts_since is None:
            return 0
        ids = await self.db.scalars(
            pending_properties(search.id, search.alerts_since)
            .order_by(PropertyListing.id)
            .limit(limit)
        )
        filters = PropertySearch(**dict(parse_qsl(search.path.partition("?")[2])))
        arguments = filters.model_dump(exclude={"limit", "offset"})
        repository = PropertyListingRepository(self.db)
        sent = 0
        for property_id in ids.all():
            items, _ = await repository.search(
                **arguments, property_id=property_id, limit=1
            )
            owner_id = await self.db.scalar(
                select(Venue.owner_id)
                .join(PropertyListing, PropertyListing.venue_id == Venue.id)
                .where(PropertyListing.id == property_id)
            )
            matched = bool(items) and owner_id != user_id
            self.db.add(
                SavedSearchMatch(
                    search_id=search.id, property_id=property_id, matched=matched
                )
            )
            if not matched:
                continue
            listing = items[0]
            path = f"/properties/{listing.id}"
            if filters.check_in is not None:
                path += "?" + urlencode(
                    {
                        "check_in": str(filters.check_in),
                        "check_out": str(filters.check_out),
                        "guests": filters.guests,
                    }
                )
            self.db.add(
                Notification(
                    user_id=user_id,
                    title=f"Novi oglas: {search.name}",
                    message=(
                        f"{listing.title} ({listing.city}) odgovara pretrazi "
                        f"„{search.name}“. Proveri aktuelnu ponudu "
                        "i dostupnost na oglasu."
                    ),
                    action_path=path,
                    deduplication_key=f"saved-search:{search.id}:property:{property_id}",
                )
            )
            sent += 1
        # Matches (including non-matches) and notifications commit together.
        await self.db.commit()
        return sent


async def run_saved_search_alerts(sessions, search_limit=25, property_limit=50):
    async with sessions() as db:
        ids = await SavedSearchAlertService(db).candidates(search_limit)
    sent = 0
    for search_id in ids:
        async with sessions() as db:
            sent += await SavedSearchAlertService(db).process(search_id, property_limit)
    return {"searches": len(ids), "notifications": sent}
