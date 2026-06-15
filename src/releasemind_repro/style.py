"""Shared plot styling for reproducibility figures."""

from __future__ import annotations

from dataclasses import dataclass
import pathlib

import matplotlib as mpl


@dataclass(frozen=True)
class VisualIdentity:
    ink: str = "#1A1B1E"
    fog: str = "#F7F5F2"
    slate: str = "#6B6E76"
    blue: str = "#1F6FEB"
    teal: str = "#0F766E"
    orange: str = "#D97706"
    magenta: str = "#A855F7"
    green: str = "#15803D"
    red: str = "#B91C1C"
    amber: str = "#B45309"
    grid: str = "#E6E2DD"

    def series(self) -> list[str]:
        return [self.blue, self.teal, self.orange, self.magenta, self.green, self.red, self.amber]


IDENTITY = VisualIdentity()


def apply_theme() -> None:
    mpl.rcParams.update({
        "figure.facecolor": IDENTITY.fog,
        "axes.facecolor": IDENTITY.fog,
        "axes.edgecolor": IDENTITY.ink,
        "axes.labelcolor": IDENTITY.ink,
        "text.color": IDENTITY.ink,
        "xtick.color": IDENTITY.ink,
        "ytick.color": IDENTITY.ink,
        "grid.color": IDENTITY.grid,
        "grid.linewidth": 0.6,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "lines.linewidth": 2.0,
        "lines.markersize": 5,
        "font.family": "DejaVu Sans",
        "savefig.dpi": 300,
        "figure.dpi": 150,
    })


def save_figure(fig, out_path: str | pathlib.Path) -> None:
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    if out.suffix.lower() == ".pdf":
        out.with_suffix(".png").parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out.with_suffix(".png"))
