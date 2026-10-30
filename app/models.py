"""Lead payload sent by the ElevenLabs `save_lead` tool.

The enums below are the contract between the LLM and the backend: the tool schema
offers the agent exactly these values, and Pydantic rejects anything else. Each enum
also maps to the human-readable label used in Notion.

Design rule: never lose a lead over formatting. Only fields the scoring and the
pipeline truly depend on are required; everything else is optional, and a malformed
email is kept in the notes instead of rejecting the whole request.
"""
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class BusinessType(str, Enum):
    restaurant = "restaurant"
    clinic = "clinic"
    retail_store = "retail_store"
    office = "office"
    industrial_logistics = "industrial_logistics"
    other = "other"


class PropertyType(str, Enum):
    retail_unit = "retail_unit"
    office = "office"
    warehouse = "warehouse"
    land = "land"


class Operation(str, Enum):
    lease = "lease"
    purchase = "purchase"


class Timeframe(str, Enum):
    immediate = "immediate"          # less than 1 month
    one_to_three = "1_3_months"
    three_to_six = "3_6_months"
    six_plus = "6_plus_months"
    undefined = "undefined"


class DecisionRole(str, Enum):
    decision_maker = "decision_maker"
    influencer = "influencer"
    researching_for_other = "researching_for_other"


# Labels as they appear in the Notion select options. One table per enum: str-based
# enums with the same value (BusinessType.office / PropertyType.office) would collide
# as keys of a single dict.
NOTION_LABELS = {
    BusinessType: {
        BusinessType.restaurant: "Restaurant",
        BusinessType.clinic: "Clinic",
        BusinessType.retail_store: "Retail store",
        BusinessType.office: "Office",
        BusinessType.industrial_logistics: "Industrial/Logistics",
        BusinessType.other: "Other",
    },
    PropertyType: {
        PropertyType.retail_unit: "Retail unit",
        PropertyType.office: "Office",
        PropertyType.warehouse: "Warehouse",
        PropertyType.land: "Land",
    },
    Operation: {
        Operation.lease: "Lease",
        Operation.purchase: "Purchase",
    },
    Timeframe: {
        Timeframe.immediate: "Immediate (<1 mo)",
        Timeframe.one_to_three: "1–3 months",
        Timeframe.three_to_six: "3–6 months",
        Timeframe.six_plus: "6+ months",
        Timeframe.undefined: "Undefined",
    },
    DecisionRole: {
        DecisionRole.decision_maker: "Decision maker",
        DecisionRole.influencer: "Influencer",
        DecisionRole.researching_for_other: "Researching for someone else",
    },
}


def notion_label(member: Enum) -> str:
    return NOTION_LABELS[type(member)][member]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# ElevenLabs sends an empty or literal placeholder when a system variable is unset.
_EMPTY_MARKERS = {"", "none", "null", "undefined", "unknown"}


def _blank_to_none(value):
    if isinstance(value, str) and value.strip().lower() in _EMPTY_MARKERS:
        return None
    return value.strip() if isinstance(value, str) else value


class LeadIn(BaseModel):
    # Who
    full_name: str = Field(min_length=2, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=200)
    company: Optional[str] = Field(default=None, max_length=200)
    business_type: BusinessType

    # What they need
    property_type: PropertyType
    operation: Operation
    space_m2: Optional[float] = Field(default=None, gt=0, le=1_000_000)
    zone: Optional[str] = Field(default=None, max_length=300)
    budget_min_mxn: Optional[float] = Field(default=None, ge=0)
    budget_max_mxn: Optional[float] = Field(default=None, ge=0)
    timeframe: Timeframe

    # Qualification
    decision_role: DecisionRole
    notes: Optional[str] = Field(default=None, max_length=5000)

    # Filled by ElevenLabs system variables, not by the LLM
    conversation_id: Optional[str] = Field(default=None, max_length=200)
    caller_id: Optional[str] = Field(default=None, max_length=40)

    @field_validator(
        "phone", "email", "company", "zone", "notes", "conversation_id", "caller_id",
        mode="before",
    )
    @classmethod
    def empty_strings_are_none(cls, value):
        return _blank_to_none(value)

    @field_validator("budget_min_mxn", "budget_max_mxn", "space_m2", mode="before")
    @classmethod
    def zero_or_blank_is_unknown(cls, value):
        # The LLM sometimes sends 0 or "" to mean "not given".
        value = _blank_to_none(value)
        return None if value in (0, "0") else value

    @model_validator(mode="after")
    def normalize(self):
        # Spoken emails arrive with stray spaces or capitals ("Juan @ Gmail.com").
        if self.email:
            candidate = self.email.replace(" ", "").lower()
            if EMAIL_RE.match(candidate):
                self.email = candidate
            else:
                self.notes = f"{self.notes or ''}\n[Unparsed email: {self.email}]".strip()
                self.email = None

        # A range given backwards is still a range.
        if (
            self.budget_min_mxn is not None
            and self.budget_max_mxn is not None
            and self.budget_min_mxn > self.budget_max_mxn
        ):
            self.budget_min_mxn, self.budget_max_mxn = self.budget_max_mxn, self.budget_min_mxn

        # Without a single way to reach the lead, the record is useless.
        if not (self.phone or self.email or self.caller_id):
            raise ValueError("At least one contact method is required: phone, email or caller_id.")
        return self

    @property
    def best_phone(self) -> Optional[str]:
        return self.phone or self.caller_id

    @property
    def source(self) -> str:
        # Phone calls carry a caller ID; web widget conversations do not.
        return "Voice agent – phone" if self.caller_id else "Voice agent – web"


class LeadOut(BaseModel):
    status: str                 # "created" or "updated"
    score: str                  # Hot / Warm / Cold (internal; the agent must not say it)
    follow_up_message: str      # Spanish sentence the agent reads to close the call
    notion_page_id: str
