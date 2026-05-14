"""truth.x — Evaluation framework for deepfake detection metrics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from backend.utils.logger import logger


def compute_metrics(
    y_true: List[int],
    y_pred: List[int],
    y_scores: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Compute classification metrics.

    Args:
        y_true: Ground truth labels (0 = real, 1 = fake).
        y_pred: Predicted labels (0 = real, 1 = fake).
        y_scores: Predicted probabilities for the positive class (fake).

    Returns:
        Dictionary with accuracy, precision, recall, F1, ROC-AUC, and confusion matrix.
    """
    y_true_arr = np.array(y_true, dtype=int)
    y_pred_arr = np.array(y_pred, dtype=int)

    if len(y_true_arr) == 0:
        return {"error": "Empty input arrays"}

    # Confusion matrix components
    tp = int(np.sum((y_pred_arr == 1) & (y_true_arr == 1)))
    tn = int(np.sum((y_pred_arr == 0) & (y_true_arr == 0)))
    fp = int(np.sum((y_pred_arr == 1) & (y_true_arr == 0)))
    fn = int(np.sum((y_pred_arr == 0) & (y_true_arr == 1)))

    accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    metrics: Dict[str, Any] = {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confusion_matrix": {
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
        },
        "total_samples": len(y_true_arr),
    }

    # ROC-AUC (only if we have probability scores)
    if y_scores is not None and len(y_scores) == len(y_true):
        try:
            roc_auc = _compute_roc_auc(y_true_arr, np.array(y_scores, dtype=float))
            metrics["roc_auc"] = round(roc_auc, 4)
        except Exception as e:
            logger.warning("ROC-AUC computation failed: %s", e)
            metrics["roc_auc"] = None

    # Per-class metrics
    metrics["per_class"] = {
        "real": {
            "precision": round(tn / max(tn + fn, 1), 4),
            "recall": round(tn / max(tn + fp, 1), 4),
            "support": int(np.sum(y_true_arr == 0)),
        },
        "fake": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "support": int(np.sum(y_true_arr == 1)),
        },
    }

    logger.info(
        "Evaluation: accuracy=%.4f, precision=%.4f, recall=%.4f, F1=%.4f",
        accuracy, precision, recall, f1,
    )
    return metrics


def _compute_roc_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Compute ROC-AUC using the trapezoidal rule (no sklearn dependency)."""
    # Sort by descending score
    desc_order = np.argsort(-y_scores)
    y_true_sorted = y_true[desc_order]

    total_pos = np.sum(y_true == 1)
    total_neg = np.sum(y_true == 0)

    if total_pos == 0 or total_neg == 0:
        return 0.5  # Undefined, return chance

    tpr_list = [0.0]
    fpr_list = [0.0]
    tp_count = 0
    fp_count = 0

    for label in y_true_sorted:
        if label == 1:
            tp_count += 1
        else:
            fp_count += 1
        tpr_list.append(tp_count / total_pos)
        fpr_list.append(fp_count / total_neg)

    # Trapezoidal integration
    auc = 0.0
    for i in range(1, len(fpr_list)):
        auc += (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2.0

    return auc


def evaluate_robustness(
    predict_fn,
    frames: list,
    perturbations: List[str] = ("compression", "blur", "resize", "noise"),
) -> Dict[str, Any]:
    """Test model robustness against common perturbations.

    Args:
        predict_fn: Callable that takes a list of PIL Images and returns a result dict.
        frames: List of PIL Image frames.
        perturbations: List of perturbation types to apply.

    Returns:
        Dictionary with per-perturbation results showing score stability.
    """
    import cv2
    from PIL import Image

    results = {}
    baseline = predict_fn(frames)
    baseline_conf = baseline.get("confidence", 0.5)
    baseline_label = baseline.get("label", "unknown")
    results["baseline"] = {"label": baseline_label, "confidence": round(baseline_conf, 4)}

    for perturb in perturbations:
        try:
            modified = [_apply_perturbation(f, perturb) for f in frames]
            result = predict_fn(modified)
            conf = result.get("confidence", 0.5)
            label = result.get("label", "unknown")
            drift = abs(conf - baseline_conf)
            label_flip = label != baseline_label

            results[perturb] = {
                "label": label,
                "confidence": round(conf, 4),
                "confidence_drift": round(drift, 4),
                "label_flipped": label_flip,
                "robust": drift < 0.15 and not label_flip,
            }
        except Exception as e:
            logger.warning("Perturbation '%s' failed: %s", perturb, e)
            results[perturb] = {"error": str(e)}

    return results


def _apply_perturbation(image, perturb_type: str):
    """Apply a single perturbation to a PIL Image."""
    import cv2
    from PIL import Image

    arr = np.array(image)

    if perturb_type == "compression":
        # Simulate JPEG compression at quality=30
        from io import BytesIO
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=30)
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    elif perturb_type == "blur":
        blurred = cv2.GaussianBlur(arr, (7, 7), 2.0)
        return Image.fromarray(blurred)

    elif perturb_type == "resize":
        h, w = arr.shape[:2]
        small = cv2.resize(arr, (w // 2, h // 2))
        back = cv2.resize(small, (w, h))
        return Image.fromarray(back)

    elif perturb_type == "noise":
        noise = np.random.normal(0, 10, arr.shape).astype(np.int16)
        noisy = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(noisy)

    return image
