from typing import Annotated

from pydantic import StringConstraints

# Local wall-clock time, deliberately without a date or UTC offset.
StayTime = Annotated[str, StringConstraints(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
