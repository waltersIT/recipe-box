from dataclasses import asdict, dataclass, field


class ImportFailed(Exception):
    """Raised with a user-facing message when a recipe can't be imported."""


@dataclass
class RecipeDraft:
    """An imported-but-not-yet-saved recipe. Field names match the Recipe model."""

    title: str = ""
    description: str = ""
    ingredients: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    notes: str = ""
    servings: str = ""
    prep_time: int | None = None
    cook_time: int | None = None
    total_time: int | None = None
    source_url: str = ""
    source_name: str = ""
    author: str = ""
    image_url: str = ""
    tags: list[str] = field(default_factory=list)
    nutrition: dict[str, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.ingredients or self.instructions)


@dataclass
class ImportResult:
    draft: RecipeDraft
    method: str  # matches Recipe.ImportMethod values
    parser: str  # "schema.org" | "claude" | "text"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "draft": asdict(self.draft),
            "method": self.method,
            "parser": self.parser,
            "warnings": self.warnings,
        }
