"""One-at-a-time terminal information gathering loop."""

from collections.abc import Callable

from services.requirement_agent import RequiredField


class InformationAgent:
    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.input_fn = input_fn
        self.output_fn = output_fn

    def collect(
        self, fields: list[RequiredField], known_values: dict[str, str] | None = None
    ) -> dict[str, str]:
        collected = dict(known_values or {})
        pending = [field for field in fields if field.name not in collected]
        if pending:
            self.output_fn("\nI need some additional information before generation.")
            self.output_fn("Press Enter to keep a standardized placeholder.\n")

        for field in pending:
            suffix = "" if field.required else " (optional)"
            try:
                answer = self.input_fn(f"{field.question}{suffix}:\n> ").strip()
            except EOFError:
                answer = ""
            collected[field.name] = answer or field.placeholder
        return collected
