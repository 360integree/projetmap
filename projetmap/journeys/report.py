"""Markdown report exporter for user journeys."""

from pathlib import Path

from projetmap.journeys.models import JourneyReport


def export_journeys_report(report: JourneyReport, output_path: Path) -> Path:
    """Export journey report as Markdown.

    Args:
        report: The JourneyReport to export.
        output_path: Path to write the Markdown file.

    Returns:
        The output path.
    """
    lines = [
        "# User Journeys",
        "",
        f"*{report.total_journeys} journeys discovered across "
        f"{len(report.by_feature)} features*",
        "",
    ]

    # Summary table
    if report.by_feature:
        lines.extend([
            "## Summary by Feature",
            "",
            "| Feature | Journeys |",
            "|---------|----------|",
        ])
        for feature, count in sorted(report.by_feature.items(), key=lambda x: -x[1]):
            lines.append(f"| {feature} | {count} |")
        lines.append("")

    # Step type breakdown
    if report.by_step_type:
        lines.extend([
            "## Step Types",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for stype, count in sorted(report.by_step_type.items(), key=lambda x: -x[1]):
            lines.append(f"| {stype} | {count} |")
        lines.append("")

    # Confidence distribution
    if report.confidence_distribution:
        lines.extend([
            "## Confidence Distribution",
            "",
            "| Range | Journeys |",
            "|-------|----------|",
        ])
        for range_str, count in report.confidence_distribution.items():
            lines.append(f"| {range_str} | {count} |")
        lines.append("")

    # Per-journey detail
    if report.journeys:
        lines.extend(["---", "", "## Journeys", ""])

        for journey in sorted(report.journeys, key=lambda j: -j.confidence):
            conf_pct = f"{journey.confidence:.0%}"
            lines.extend([
                f"### {journey.name}",
                "",
                f"**Confidence:** {conf_pct} | "
                f"**Feature:** {journey.feature} | "
                f"**Steps:** {len(journey.steps)} | "
                f"**Entry:** `{journey.entry_point}`",
                "",
            ])

            if journey.steps:
                lines.extend([
                    "| # | Type | Name | File | Line |",
                    "|---|------|------|------|------|",
                ])
                for i, step in enumerate(journey.steps, 1):
                    lines.append(
                        f"| {i} | `{step.step_type.value}` | "
                        f"{step.name} | `{step.file}` | {step.line} |"
                    )
                lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path
