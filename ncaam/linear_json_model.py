from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinearJsonModelMetadata:
    market: str
    model_type: str
    target_mode: str
    feature_names: list[str]
    metadata: dict


class LinearJsonModel:
    """Minimal loader/inference for the repo's JSON linear/logistic artifacts.

    This is intentionally independent of any backtesting code and lives outside
    `testing/` so it can be used by scripts and services without coupling.
    """

    def __init__(
        self,
        model_type: str,
        weights: list[float],
        intercept: float,
        means: list[float],
        stds: list[float],
    ) -> None:
        self.model_type = model_type
        self.weights = [float(w) for w in (weights or [])]
        self.intercept = float(intercept)
        self.means = [float(m) for m in (means or [])]
        self.stds = [float(s) for s in (stds or [])]

        if len(self.weights) != len(self.means) or len(self.weights) != len(self.stds):
            raise ValueError(
                "Invalid model artifact: weights/means/stds lengths must match "
                f"(weights={len(self.weights)}, means={len(self.means)}, stds={len(self.stds)})"
            )

    def _transform_row(self, row: list[float]) -> list[float]:
        if len(row) != len(self.weights):
            raise ValueError(
                f"Expected {len(self.weights)} features, got {len(row)}"
            )
        out: list[float] = []
        for x, mean, std in zip(row, self.means, self.stds, strict=True):
            denom = std if std != 0.0 else 1.0
            out.append((float(x) - mean) / denom)
        return out

    def predict(self, X: list[list[float]] | tuple[tuple[float, ...], ...]) -> list[float]:
        """Return predictions for a batch of rows."""
        preds: list[float] = []
        for row in X:
            xz = self._transform_row(list(row))
            raw = self.intercept
            for w, v in zip(self.weights, xz, strict=True):
                raw += w * v
            if self.model_type == "linear":
                preds.append(raw)
            else:
                # logistic
                preds.append(1.0 / (1.0 + math.exp(-raw)))
        return preds


def load_linear_json_model(
    path: str | Path,
    *,
    allow_linear: bool = False,
) -> tuple[LinearJsonModel | None, list[str] | None, dict | None]:
    """Load a JSON model artifact.

    Returns: (model, feature_names, metadata)
    - model is None if file doesn't exist or model type is disallowed.
    - metadata always includes `target_mode` and `model_type` when available.
    """
    p = Path(path)
    if not p.exists():
        return None, None, None

    data = json.loads(p.read_text(encoding="utf-8"))

    model_type = data.get("model_type")
    metadata = dict(data.get("metadata", {}) or {})
    metadata["target_mode"] = data.get("target_mode", "raw")
    metadata["model_type"] = model_type

    if model_type != "logistic" and not allow_linear:
        return None, None, metadata

    model = LinearJsonModel(
        model_type=model_type,
        weights=data.get("weights", []),
        intercept=data.get("intercept", 0.0),
        means=data.get("means", []),
        stds=data.get("stds", []),
    )
    return model, data.get("feature_names"), metadata
