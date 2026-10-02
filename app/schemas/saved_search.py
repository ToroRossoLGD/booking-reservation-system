from urllib.parse import parse_qsl, urlencode

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.property_listing import PropertySearch


class SavedSearchWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    path: str = Field(max_length=2000)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, path):
        if (path != "/" and not path.startswith("/?")) or "#" in path:
            raise ValueError("Use an internal property search path")
        pairs = parse_qsl(
            path[2:] if path.startswith("/?") else "", keep_blank_values=True
        )
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("Duplicate search parameters")
        values = {
            key: value
            for key, value in pairs
            if key in PropertySearch.model_fields and key not in {"offset", "limit"}
        }
        for key in ("city", "neighborhood"):
            if key in values:
                values[key] = values[key].strip()
                if not values[key]:
                    del values[key]
        search = PropertySearch(**values)
        params = search.model_dump(
            mode="json", exclude_defaults=True, exclude_none=True
        )
        params.pop("offset", None)
        params.pop("limit", None)
        encoded = urlencode(
            sorted(
                (key, str(value).lower() if isinstance(value, bool) else value)
                for key, value in params.items()
            )
        )
        result = "/?" + encoded if encoded else "/"
        if len(result) > 2000:
            raise ValueError("Search URL is too long")
        return result


class SavedSearchRead(SavedSearchWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
