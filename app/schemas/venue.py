from pydantic import BaseModel, Field, model_validator


class VenueBookingRulesMixin(BaseModel):
    minimum_booking_notice_minutes: int = Field(default=60, ge=0, le=10080)
    maximum_advance_booking_days: int = Field(default=365, ge=1, le=730)
    minimum_booking_duration_minutes: int = Field(default=30, ge=15, le=1440)
    maximum_booking_duration_minutes: int = Field(default=480, ge=15, le=10080)
    max_active_reservations_per_customer: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_duration_range(self):
        if (
            self.maximum_booking_duration_minutes
            < self.minimum_booking_duration_minutes
        ):
            raise ValueError(
                "maximum booking duration must be greater than or equal to minimum"
            )
        return self


class VenueCreate(VenueBookingRulesMixin):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    address: str = Field(min_length=2, max_length=255)
    free_cancellation_hours: int = Field(default=24, ge=0, le=720)
    late_cancellation_refund_percent: int = Field(default=50, ge=0, le=100)


class VenueCancellationPolicyUpdate(BaseModel):
    free_cancellation_hours: int = Field(ge=0, le=720)
    late_cancellation_refund_percent: int = Field(ge=0, le=100)


class VenueCancellationPolicyRead(BaseModel):
    venue_id: int
    free_cancellation_hours: int
    late_cancellation_refund_percent: int


class VenueBookingRulesUpdate(VenueBookingRulesMixin):
    pass


class VenueBookingRulesRead(VenueBookingRulesMixin):
    venue_id: int


class VenueRead(BaseModel):
    id: int
    name: str
    description: str | None
    address: str
    owner_id: int
    free_cancellation_hours: int
    late_cancellation_refund_percent: int
    minimum_booking_notice_minutes: int
    maximum_advance_booking_days: int
    minimum_booking_duration_minutes: int
    maximum_booking_duration_minutes: int
    max_active_reservations_per_customer: int

    model_config = {"from_attributes": True}


class VenueListRead(BaseModel):
    items: list[VenueRead]
    total: int
    limit: int
    offset: int
    has_next: bool
