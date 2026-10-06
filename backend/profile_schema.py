"""Shared, allowlisted personal profile validation for registration and support."""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

PROFILE_FIELDS = frozenset({
    "display_name", "first_name", "last_name", "phone", "location", "headline", "language",
    "gender", "date_of_birth", "street", "postal_code", "city", "country", "spoken_languages",
})

# ISO 3166-1 alpha-2 assigned country and territory codes. Empty means undisclosed.
COUNTRY_CODES = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ
CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO
FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE
JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN
MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS
PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ
TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())

SpokenLanguage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
SupportReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class AccountPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email_notifications: bool = False


class AccountProfileFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field("", max_length=200)
    first_name: str = Field("", max_length=100)
    last_name: str = Field("", max_length=100)
    phone: str = Field("", max_length=100)
    location: str = Field("", max_length=300)
    headline: str = Field("", max_length=300)
    language: Literal["de", "en", "sq"] = "de"
    gender: Literal["undisclosed", "female", "male", "diverse"] = "undisclosed"
    date_of_birth: date | None = None
    street: str = Field("", max_length=300)
    postal_code: str = Field("", max_length=32)
    city: str = Field("", max_length=200)
    country: str = Field("", max_length=2)
    spoken_languages: list[SpokenLanguage] = Field(default_factory=list, max_length=20)

    @field_validator(
        "display_name", "first_name", "last_name", "phone", "location", "headline", "language",
        "gender", "street", "postal_code", "city", mode="before",
    )
    @classmethod
    def trim_profile_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def iso_birth_date(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Geburtsdatum muss ein ISO-Datum sein (JJJJ-MM-TT).")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def real_past_date(cls, value):
        if value and value > datetime.now(UTC).date():
            raise ValueError("Geburtsdatum darf nicht in der Zukunft liegen.")
        return value

    @field_validator("country", mode="before")
    @classmethod
    def country_code(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip().upper()
        if value and value not in COUNTRY_CODES:
            raise ValueError("Land muss ein gültiger ISO-Ländercode sein.")
        return value


class AccountProfileUpdate(AccountProfileFields):
    preferences: AccountPreferences = Field(default_factory=AccountPreferences)


class AdminProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: AccountProfileUpdate
    expected_updated_at: datetime | None = Field(...)
    reason: SupportReason

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def timestamp_only(cls, value):
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("expected_updated_at muss ein ISO-Zeitstempel sein.")
        return value

    @field_validator("expected_updated_at")
    @classmethod
    def normalize_timestamp(cls, value):
        if value and value.tzinfo:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def require_profile_changes(self):
        if not self.profile.model_fields_set:
            raise ValueError("Mindestens ein Profilfeld ist erforderlich.")
        return self


class AdminPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: SupportReason
