"""Student identity metadata shared by the GUI and export boundaries.

The identity is deliberately optional: simulations remain usable for demos and
automated workflows that do not identify a student.  Normalization only makes
the value safe to display and serialize; it preserves case, accents and
punctuation supplied by the student.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


_WHITESPACE = re.compile(r"\s+")


def normalize_identity_text(value: object) -> str:
    """Return a single-line, Unicode-normalized identity value.

    Leading/trailing whitespace and accidental repeated whitespace are removed,
    while meaningful spelling, case, accents and punctuation are retained.
    """

    normalized = unicodedata.normalize("NFC", str(value or ""))
    return _WHITESPACE.sub(" ", normalized).strip()


@dataclass(frozen=True)
class StudentIdentity:
    """Optional ownership metadata attached to sessions and exports."""

    name: str = ""
    student_id: str = ""

    @classmethod
    def normalized(cls, name: object = "", student_id: object = "") -> "StudentIdentity":
        return cls(
            name=normalize_identity_text(name),
            student_id=normalize_identity_text(student_id),
        )

    @property
    def is_empty(self) -> bool:
        return not (self.name or self.student_id)

    def display_label(self) -> str:
        """Return a concise French label suitable for Canvas screenshots."""

        parts = []
        if self.name:
            parts.append(self.name)
        if self.student_id:
            parts.append(f"matricule {self.student_id}")
        return "Étudiant : " + " · ".join(parts) if parts else ""
