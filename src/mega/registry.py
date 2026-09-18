"""Canonical mega report section registry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    identifier: str
    title: str
    optional: bool = False


SECTIONS = (
    Section("kpi_cover", "KPI Cover"),
    Section("income", "Income"),
    Section("savings", "Savings"),
    Section("home", "Home"),
    Section("common", "Common spending"),
    Section("personal_partner_a", "Personal spending - Partner A"),
    Section("personal_partner_b", "Personal spending - Partner B"),
    Section("trips", "Trips"),
    Section("recommendations", "Recommendations", optional=True),
    Section("monthlies", "Monthly Reports"),
    Section("cc_paydowns", "Credit-card paydowns"),
    Section("excluded", "Excluded categories"),
    Section("appendices", "Appendices"),
)


def active_sections(include_recommendations: bool = False) -> tuple[Section, ...]:
    """Return ordered sections, omitting optional recommendations by default."""
    return tuple(
        section
        for section in SECTIONS
        if include_recommendations or not section.optional
    )


def numbered_sections(
    include_recommendations: bool = False,
) -> tuple[tuple[int, Section], ...]:
    """Derive contiguous display numbers from the active registry."""
    return tuple(enumerate(active_sections(include_recommendations), start=1))


def section_by_id(
    identifier: str, include_recommendations: bool = False
) -> tuple[int, Section] | None:
    """Find an active section and its registry-derived number."""
    return next(
        (
            (number, section)
            for number, section in numbered_sections(include_recommendations)
            if section.identifier == identifier
        ),
        None,
    )


def valid_ids(include_recommendations: bool = False) -> tuple[str, ...]:
    return tuple(
        section.identifier for section in active_sections(include_recommendations)
    )
