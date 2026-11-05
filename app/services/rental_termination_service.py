from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.models.rental_agreement import RentalCharge, RentalTermination
from app.services.rental_agreement_service import RentalAgreementService, month_date


class RentalTerminationService(RentalAgreementService):
    async def history(self, agreement_id, user, offset=0):
        await self.get(agreement_id, user)
        return list(
            (
                await self.db.scalars(
                    select(RentalTermination)
                    .where(RentalTermination.agreement_id == agreement_id)
                    .order_by(RentalTermination.id.desc())
                    .offset(offset)
                    .limit(10)
                )
            ).all()
        )

    async def affected(self, agreement, end_date):
        if agreement.status != "accepted" or agreement.terminated_on is not None:
            raise HTTPException(409, "Agreement cannot be ended again")
        if end_date < self.today(agreement.timezone) or end_date not in {
            month_date(agreement.start_date, index)
            for index in range(1, agreement.months)
        }:
            raise HTTPException(
                409, "Choose a future monthly boundary before the original end"
            )
        charges = list(
            (
                await self.db.scalars(
                    select(RentalCharge)
                    .where(
                        RentalCharge.agreement_id == agreement.id,
                        RentalCharge.sequence > 0,
                        RentalCharge.due_date >= end_date,
                    )
                    .order_by(RentalCharge.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        if not charges or any(row.paid or row.voided_at is not None for row in charges):
            raise HTTPException(
                409,
                "Future rent has a payment record; "
                "resolve it before ending the agreement",
            )
        return charges

    async def propose(self, agreement_id, data, user):
        self.writable()
        agreement = await self.get(agreement_id, user, lock=True)
        if user.id != agreement.owner_id:
            raise HTTPException(403, "Only the owner can propose an early end")
        previous = await self.db.scalar(
            select(RentalTermination).where(
                RentalTermination.agreement_id == agreement_id,
                RentalTermination.request_id == str(data.request_id),
            )
        )
        if previous:
            if previous.end_date != data.end_date or previous.notes != data.notes:
                raise HTTPException(409, "Request identifier was already used")
            return previous
        if agreement.version != data.version:
            raise HTTPException(409, "Agreement changed; refresh before continuing")
        await self.affected(agreement, data.end_date)
        if await self.db.scalar(
            select(RentalTermination.id).where(
                RentalTermination.agreement_id == agreement_id,
                RentalTermination.status.in_(("proposed", "accepted")),
            )
        ):
            raise HTTPException(409, "An active end proposal already exists")
        row = RentalTermination(
            agreement_id=agreement_id,
            request_id=str(data.request_id),
            end_date=data.end_date,
            notes=data.notes,
            status="proposed",
            version=1,
        )
        self.db.add(row)
        self.notify(
            agreement,
            False,
            "Predlog prevremenog završetka najma",
            "Pregledaj datum i posledice pre potvrde.",
        )
        await self.db.commit()
        return row

    async def decide(self, agreement_id, termination_id, data, user):
        self.writable()
        agreement = await self.get(agreement_id, user, lock=True)
        row = await self.db.scalar(
            select(RentalTermination)
            .where(
                RentalTermination.id == termination_id,
                RentalTermination.agreement_id == agreement_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise HTTPException(404, "End proposal not found")
        expected = (
            agreement.owner_id if data.action == "withdraw" else agreement.tenant_id
        )
        if user.id != expected:
            raise HTTPException(403, "You cannot perform this action")
        if row.status != "proposed" or row.version != data.version:
            raise HTTPException(409, "End proposal changed; refresh before continuing")
        now = datetime.now(UTC)
        if data.action == "accept":
            charges = await self.affected(agreement, row.end_date)
            for charge in charges:
                charge.voided_at = now
                charge.updated_at = now
                charge.version += 1
            agreement.terminated_on = row.end_date
            agreement.version += 1
        row.status = {
            "accept": "accepted",
            "decline": "declined",
            "withdraw": "withdrawn",
        }[data.action]
        row.version += 1
        row.decided_at = now
        self.notify(
            agreement,
            data.action != "withdraw",
            "Odluka o završetku najma",
            {
                "accept": "Predlog je prihvaćen. Pregledaj ažurirani raspored kirija.",
                "decline": "Predlog je odbijen. Uslovi najma ostaju na snazi.",
                "withdraw": "Predlog je povučen. Uslovi najma ostaju na snazi.",
            }[data.action],
        )
        await self.db.commit()
        return row
