"""Oracle-as-a-judge integration used by reproducibility CLI."""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .utils import ensure_dir, read_jsonl

SMARTNOTE_PROMPT = """
You are a Senior Technical Release Manager. Analyze the following commit message and decide if it belongs in user-facing release notes.

Criteria for 'Include':
- New features, bug fixes, or performance improvements visible to the user.
- Breaking changes to public APIs.
- Critical security updates.

Criteria for 'Exclude':
- Internal chores (CI, build scripts, tests, linters).
- Refactoring with no external behavioral change.
- Version bumps, typos, or minor dependency updates.

Commit message:
{body}

Instructions:
1. Analyze the commit to determine its impact on the end-user.
2. Provide your concise reasoning in the "reasoning" field.
3. Assign the final label ("Include" or "Exclude").

Return ONLY valid JSON with no markdown formatting.
""".lstrip()

RNSUM_PROMPT = """
You are a QA Lead auditing a release note against the actual commit logs. Your task is to identify and count factual hallucinations.

A "Hallucination" is any claim in the release note that is NOT supported by the Commit Logs.
- Check for mentioned files, function names, or features that do not exist in the commits.
- Check for claims of "fixed" bugs that are not referenced in the commits.
- General high-level summaries are accepted if they reflect the gist of the commits.

Commit logs:
{commits}

Release note:
{release_note}

Instructions:
1. Compare each claim in the note against the evidence.
2. In the "reasoning" field, list any unsupported claims you found.
3. Output the total count of hallucinations as an integer.
""".lstrip()

LABEL_RE = re.compile(r'"label"\s*:\s*"(include|exclude)"', re.IGNORECASE)
HALL_RE = re.compile(r'"hallucination_count"\s*:\s*(\d+)', re.IGNORECASE)
RETRY_RE = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)
JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
GEMINI_RPM_LIMIT = 150
DEFAULT_MIN_INTERVAL = 60.0 / GEMINI_RPM_LIMIT


def parse_json(text: str) -> Optional[Dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = JSON_RE.search(text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _parse_fallback(raw: str) -> Dict[str, Optional[object]]:
    cleaned = raw.strip().removeprefix("```")
    if cleaned.startswith("json"):
        cleaned = cleaned[len("json") :].lstrip()
    parsed = parse_json(cleaned)
    if not parsed:
        parsed = {}
    return parsed


def parse_candidate(raw: str) -> Dict[str, Optional[object]]:
    parsed = parse_json(raw)
    if parsed is not None:
        parsed.setdefault("parse_error", None)
        return parsed

    parsed = _parse_fallback(raw)
    if parsed:
        parsed.setdefault("parse_error", "partial_parse")
        return parsed

    label_match = LABEL_RE.search(raw)
    halluc_match = HALL_RE.search(raw)
    if not label_match and not halluc_match:
        return {
            "parse_error": raw.strip()[:240] if raw else "empty",
        }

    result: Dict[str, Optional[object]] = {}
    if label_match:
        result["label"] = label_match.group(1).capitalize()
    if halluc_match:
        result["hallucination_count"] = int(halluc_match.group(1))
    if not result:
        result["parse_error"] = raw.strip()[:240] if raw else "unparseable"
    return result


def _serializable_payload(response: object) -> object:
    if response is None:
        return None
    if isinstance(response, (dict, list, str, int, float, bool)):
        return response
    if isinstance(response, tuple):
        return list(response)

    for attr in ("to_dict", "dict", "model_dump"):
        method = getattr(response, attr, None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass

    if hasattr(response, "__dict__"):
        payload: Dict[str, object] = {}
        for key, value in response.__dict__.items():
            if key.startswith("_"):
                continue
            payload[key] = value
        if payload:
            return payload

    return {"text": str(response)}


def extract_text_gemini(response: Dict) -> Optional[str]:
    if isinstance(response, list):
        candidates = response
    else:
        candidates = response.get("candidates") or []
    if not candidates:
        return None

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
    if not texts:
        return None
    return "".join(texts).strip()


def build_prompt_smartnote(body: str) -> str:
    return SMARTNOTE_PROMPT.format(body=body)


def build_prompt_rnsum(commits: str, release_note: str) -> str:
    return RNSUM_PROMPT.format(commits=commits, release_note=release_note)


def _retry_delay_from_error(message: str, default_delay: float) -> float:
    match = RETRY_RE.search(message)
    if match:
        try:
            return max(default_delay, float(match.group(1)))
        except ValueError:
            return default_delay
    return default_delay


def _label_to_binary(dataset: str, parsed: Dict[str, object]) -> Optional[int]:
    if dataset == "smartnote":
        label = parsed.get("label") if isinstance(parsed, dict) else None
        if isinstance(label, str):
            return 1 if label.lower().startswith("include") else 0
        return None

    count = parsed.get("hallucination_count") if isinstance(parsed, dict) else None
    try:
        return 1 if int(count) > 0 else 0
    except (TypeError, ValueError):
        return None


def _build_tasks(df: pd.DataFrame, dataset: str) -> List[Dict]:
    tasks = []
    for idx, row in df.iterrows():
        task: Dict[str, object] = {
            "audit_id": f"{dataset}_{idx}",
            "dataset": dataset,
            "proxy_score": float(row["risk_score"]),
        }
        if dataset == "smartnote":
            task["body"] = str(row.get("body", ""))
        else:
            task["input_text"] = str(row.get("input_text", ""))
            task["target_text"] = str(row.get("target_text", ""))
        tasks.append(task)
    return tasks


def _build_raw_row(
    task: Dict,
    raw_output: object,
    parsed_output: Dict[str, Optional[object]],
    error_detail: Optional[str],
    oracle_label: Optional[int],
) -> Dict[str, object]:
    return {
        "audit_id": task["audit_id"],
        "dataset": task["dataset"],
        "proxy_score": task["proxy_score"],
        "raw_output": raw_output,
        "parsed_output": parsed_output,
        "oracle_label": oracle_label,
        "error": abs(float(oracle_label) - float(task["proxy_score"])) if oracle_label is not None else None,
        "error_detail": error_detail,
    }


def _audit_one(
    task: Dict,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
    max_retries: int,
    min_delay: float,
    limiter: Optional["RateLimiter"],
) -> Dict:
    if task["dataset"] == "smartnote":
        prompt = build_prompt_smartnote(task["body"])
    else:
        prompt = build_prompt_rnsum(task["input_text"], task["target_text"])

    last_error: Optional[str] = None
    raw_output: object = ""
    parsed: Dict[str, Optional[object]] = {}

    for _ in range(max_retries + 1):
        try:
            if limiter is not None:
                limiter.wait()

            if provider == "gemini":
                raw_output, parsed = gemini_call(model, prompt, temperature, max_tokens)
            else:
                raw_output, parsed = bedrock_call(model, prompt, temperature, max_tokens)
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(_retry_delay_from_error(last_error, min_delay))

    if last_error:
        return {
            **task,
            "oracle_label": None,
            "raw_output": {"error": str(last_error)},
            "parsed_output": {"parse_error": str(last_error)},
            "error": None,
            "error_detail": last_error,
        }

    parsed = parsed or {}
    oracle_label = _label_to_binary(task["dataset"], parsed)
    error = abs(float(oracle_label) - float(task["proxy_score"])) if oracle_label is not None else None
    return {
        **task,
        "oracle_label": oracle_label,
        "raw_output": raw_output,
        "parsed_output": parsed,
        "error": error,
        "error_detail": None,
    }


def gemini_call(model: str, prompt: str, temperature: float, max_tokens: int) -> Tuple[object, Dict[str, Optional[object]]]:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY/GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    thinking_budget = 128 if "pro" in model.lower() else 0
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget, include_thoughts=False),
        ),
    )
    response_text = ""
    if response is not None:
        response_text = getattr(response, "text", "") or ""
        if not response_text:
            response_text = str(response)
    return _serializable_payload(response), parse_candidate(response_text)


def bedrock_call(model: str, prompt: str, temperature: float, max_tokens: int) -> Tuple[object, Dict[str, Optional[object]]]:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION"))
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }
    response = client.invoke_model(modelId=model, body=json.dumps(payload))
    raw = response.get("body")
    data = json.loads(raw.read()) if raw else {}
    content = data.get("content") or []
    text = ""
    if content and isinstance(content, list):
        text = content[0].get("text", "")
    return _serializable_payload(data), parse_candidate(text)


def gemini_batch(
    tasks: List[Dict],
    out_path: Path,
    raw_path: Path,
    model: str,
    temperature: float,
    max_tokens: int,
    poll_interval: int,
    batch_dir: Path,
) -> None:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY/GEMINI_API_KEY for Gemini batch mode")

    client = genai.Client(api_key=api_key)
    batch_dir.mkdir(parents=True, exist_ok=True)
    request_file = batch_dir / f"requests_gemini_audit_{int(time.time())}.jsonl"

    model_lower = model.lower()
    thinking_budget = 128 if "pro" in model_lower else 0
    with request_file.open("w", encoding="utf-8") as stream:
        for task in tasks:
            prompt = build_prompt_smartnote(task["body"]) if task["dataset"] == "smartnote" else build_prompt_rnsum(task["input_text"], task["target_text"])
            payload = {
                "key": task["audit_id"],
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generation_config": {
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                        "response_mime_type": "application/json",
                        "thinking_config": {
                            "thinking_budget": thinking_budget,
                            "include_thoughts": False,
                        },
                    },
                },
            }
            stream.write(json.dumps(payload) + "\n")

    uploaded = client.files.upload(
        file=str(request_file),
        config=types.UploadFileConfig(display_name=request_file.stem, mime_type="jsonl"),
    )
    batch_job = client.batches.create(
        model=model,
        src=uploaded.name,
        config={"display_name": f"audit_{request_file.stem}"},
    )

    batch_id = batch_job.name
    state = None
    while True:
        batch_job = client.batches.get(name=batch_id)
        state_obj = getattr(batch_job, "state", None)
        state = getattr(state_obj, "name", None) or str(state_obj)
        if state in {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}:
            break
        time.sleep(poll_interval)

    if state != "JOB_STATE_SUCCEEDED":
        error_name = getattr(batch_job, "state", state)
        raise RuntimeError(f"Gemini batch failed: state={error_name}")

    output_file_name = None
    if getattr(batch_job, "dest", None) and getattr(batch_job.dest, "file_name", None):
        output_file_name = batch_job.dest.file_name
    if not output_file_name:
        raise RuntimeError("Gemini batch succeeded but no output file returned")

    downloaded = client.files.download(file=output_file_name)
    payload_bytes = downloaded.read() if hasattr(downloaded, "read") else downloaded
    text = payload_bytes.decode("utf-8") if isinstance(payload_bytes, (bytes, bytearray)) else str(payload_bytes)

    ensure_dir(out_path.parent)
    ensure_dir(raw_path.parent)
    tasks_by_id = {task["audit_id"]: task for task in tasks}
    with out_path.open("a", encoding="utf-8") as out_stream, raw_path.open("a", encoding="utf-8") as raw_stream:
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            key = obj.get("key") or (obj.get("metadata") or {}).get("key")
            if not key:
                continue
            task = tasks_by_id.get(key)
            if task is None:
                continue

            response = obj.get("response")
            error_obj = obj.get("error") or obj.get("status")
            if response is None and isinstance(obj.get("candidates"), list):
                response = obj

            if error_obj:
                parsed = {
                    "parse_error": str(error_obj),
                }
                output_text = extract_text_gemini(response) if isinstance(response, dict) else None
                raw_output = _serializable_payload(response) if response is not None else _serializable_payload(error_obj)
                row = {
                    **task,
                    "oracle_label": None,
                    "raw_output": raw_output,
                    "parsed_output": {},
                    "error": None,
                    "error_detail": str(error_obj),
                }
            else:
                output_text = extract_text_gemini(response) if isinstance(response, dict) else str(response)
                parsed = parse_candidate(output_text or "") if output_text is not None else {}
                oracle_label = _label_to_binary(task["dataset"], parsed)
                error_val = abs(float(oracle_label) - float(task["proxy_score"])) if oracle_label is not None else None
                row = {
                    **task,
                    "oracle_label": oracle_label,
                    "raw_output": _serializable_payload(response),
                    "parsed_output": parsed,
                    "error": error_val,
                    "error_detail": None,
                }

            out_stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            raw_row = {
                "audit_id": task["audit_id"],
                "dataset": task["dataset"],
                "proxy_score": task["proxy_score"],
                "raw_output": row["raw_output"],
                "parsed_output": row["parsed_output"],
                "oracle_label": row["oracle_label"],
                "error": row["error"],
                "error_detail": row["error_detail"],
            }
            raw_stream.write(json.dumps(raw_row, ensure_ascii=False) + "\n")


def compute_bin_summary(df: pd.DataFrame, bins: List[float]) -> Dict[str, Dict[str, float]]:
    if df.empty:
        return {}

    scored = df.dropna(subset=["error", "proxy_score"]).copy()
    if scored.empty:
        return {}

    scored["bin"] = pd.cut(scored["proxy_score"], bins=bins, include_lowest=True, right=True)
    summary: Dict[str, Dict[str, float]] = {}
    for key, group in scored.groupby("bin", dropna=False):
        if group.empty:
            continue
        group_errors = pd.to_numeric(group["error"], errors="coerce")
        summary[str(key)] = {
            "count": int(len(group_errors)),
            "error_p95": float(group_errors.quantile(0.95)),
            "error_mean": float(group_errors.mean()),
        }
    return summary


class RateLimiter:
    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_time = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            delta = now - self._last_time
            if delta < self._min_interval:
                time.sleep(self._min_interval - delta)
            self._last_time = time.time()


def load_existing(out_path: Path) -> Dict[str, Dict]:
    completed: Dict[str, Dict] = {}
    if not out_path.exists():
        return completed
    for row in read_jsonl(out_path):
        key = row.get("audit_id")
        if key:
            completed[str(key)] = row
    return completed


def run_audit(
    smartnote_proxy: Path,
    rnsum_proxy: Path,
    out: Path,
    summary_out: Path,
    sample_size: int,
    seed: int,
    provider: str,
    model: str,
    mode: str,
    batch_dir: Path,
    batch_poll_interval: int,
    max_workers: int,
    max_retries: int,
    min_delay: float,
    min_interval: float,
    temperature: float,
    max_tokens: int,
    bins: List[float],
    overwrite: bool = False,
    raw_out: Path | None = None,
    skip_if_missing: bool = False,
) -> Dict[str, object]:
    out = Path(out)
    summary_out = Path(summary_out)
    raw_out_path = Path(raw_out or out.with_name(f"{out.stem}_raw.jsonl"))

    existing_rows: list[Dict[str, object]] = []
    if out.exists() and overwrite:
        out.unlink()
    if raw_out_path.exists() and overwrite:
        raw_out_path.unlink()
    ensure_dir(out.parent)
    ensure_dir(raw_out_path.parent)
    ensure_dir(summary_out.parent)

    if skip_if_missing and sample_size <= 0:
        summary = {
            "rows": 0,
            "provider": provider,
            "model": model,
            "sample_size": sample_size,
            "bins": bins,
            "smartnote": {},
            "rnsum": {},
            "skip_if_missing": True,
            "skip_reason": "sample_size_zero",
        }
        summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        raw_out_path.write_text("", encoding="utf-8")
        out.write_text("", encoding="utf-8")
        return {
            **summary,
        }

    if skip_if_missing and provider == "gemini" and not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        summary = {
            "rows": 0,
            "provider": provider,
            "model": model,
            "sample_size": sample_size,
            "bins": bins,
            "smartnote": {},
            "rnsum": {},
            "skip_if_missing": True,
            "skip_reason": "missing_api_credentials",
        }
        summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        raw_out_path.write_text("", encoding="utf-8")
        out.write_text("", encoding="utf-8")
        return summary

    if skip_if_missing and provider == "bedrock" and not (
        os.environ.get("AWS_ACCESS_KEY_ID")
        and os.environ.get("AWS_SECRET_ACCESS_KEY")
        and os.environ.get("AWS_DEFAULT_REGION")
    ):
        summary = {
            "rows": 0,
            "provider": provider,
            "model": model,
            "sample_size": sample_size,
            "bins": bins,
            "smartnote": {},
            "rnsum": {},
            "skip_if_missing": True,
            "skip_reason": "missing_api_credentials",
        }
        summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        raw_out_path.write_text("", encoding="utf-8")
        out.write_text("", encoding="utf-8")
        return summary

    if provider not in {"gemini", "bedrock"}:
        raise ValueError(f"Unsupported provider: {provider}")

    if not smartnote_proxy.exists():
        raise FileNotFoundError(f"Missing SmartNote proxy file: {smartnote_proxy}")
    if not rnsum_proxy.exists():
        raise FileNotFoundError(f"Missing RNSum proxy file: {rnsum_proxy}")

    smart_df = pd.read_parquet(smartnote_proxy, columns=["body", "risk_score"])
    rnsum_df = pd.read_parquet(rnsum_proxy, columns=["input_text", "target_text", "risk_score"])

    smart_df = smart_df.sample(n=min(sample_size, len(smart_df)), random_state=seed).reset_index(drop=True)
    rnsum_df = rnsum_df.sample(n=min(sample_size, len(rnsum_df)), random_state=seed).reset_index(drop=True)

    tasks = _build_tasks(smart_df, "smartnote") + _build_tasks(rnsum_df, "rnsum")
    completed = load_existing(out)
    pending = [task for task in tasks if task["audit_id"] not in completed]
    if out.exists():
        existing_rows = list(read_jsonl(out))

    if pending:
        if mode == "batch":
            if provider != "gemini":
                raise ValueError("Batch mode is only supported for provider=gemini")
            gemini_batch(
                tasks=pending,
                out_path=out,
                raw_path=raw_out_path,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                poll_interval=batch_poll_interval,
                batch_dir=batch_dir,
            )
        else:
            limiter = RateLimiter(min_interval) if min_interval > 0 else None
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(
                        _audit_one,
                        task=task,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        max_retries=max_retries,
                        min_delay=min_delay,
                        limiter=limiter,
                    )
                    for task in pending
                ]
                pending_rows = [future.result() for future in concurrent.futures.as_completed(futures)]
            existing_rows.extend(pending_rows)

    if pending:
        if mode == "batch":
            existing_rows = list(read_jsonl(out))
        # keep deterministic ordering for reproducibility and restart safety
        existing_rows = sorted(
            existing_rows,
            key=lambda item: (str(item.get("dataset", "")), str(item.get("audit_id", ""))),
        )
        with out.open("w", encoding="utf-8") as output_stream, raw_out_path.open("w", encoding="utf-8") as raw_stream:
            for row in existing_rows:
                output_stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                raw_stream.write(
                    json.dumps(
                        _build_raw_row(
                            task={k: row[k] for k in ("audit_id", "dataset", "proxy_score")},
                            raw_output=row.get("raw_output", ""),
                            parsed_output=row.get("parsed_output", {}),
                            error_detail=row.get("error_detail"),
                            oracle_label=row.get("oracle_label"),
                        ),
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    merged_rows = []
    if out.exists():
        merged_rows = list(read_jsonl(out))
    merged_df = pd.DataFrame(merged_rows)

    summary = {
        "rows": int(len(merged_df)),
        "provider": provider,
        "model": model,
        "sample_size": sample_size,
        "bins": bins,
        "smartnote": compute_bin_summary(merged_df[merged_df["dataset"] == "smartnote"], bins),
        "rnsum": compute_bin_summary(merged_df[merged_df["dataset"] == "rnsum"], bins),
        "skip_if_missing": bool(skip_if_missing),
    }

    ensure_dir(summary_out.parent)
    summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# Compatibility entrypoint with the old CLI.
def add_audit_parser(subparsers) -> None:  # pragma: no cover
    parser = subparsers.add_parser("audit", help="Run oracle-as-a-judge audit")
    parser.add_argument("--smartnote-proxy", default="outputs/risk_proxy/smartnote_proxy.parquet")
    parser.add_argument("--rnsum-proxy", default="outputs/risk_proxy/rnsum_proxy.parquet")
    parser.add_argument("--out", default="outputs/audit/oracle_audit.jsonl")
    parser.add_argument("--summary", default="outputs/audit/oracle_audit_summary.json")
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--provider", choices=["gemini", "bedrock"], default="gemini")
    parser.add_argument("--model", default="models/gemini-2.5-pro")
    parser.add_argument("--mode", choices=["standard", "batch"], default="standard")
    parser.add_argument("--batch-dir", default="outputs/audit/batch")
    parser.add_argument("--batch-poll-interval", type=int, default=30)
    parser.add_argument("--max-workers", type=int, default=50)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--min-delay", type=float, default=2.0)
    parser.add_argument("--min-interval", type=float, default=DEFAULT_MIN_INTERVAL)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")


def run_audit_parser(args) -> Dict[str, object]:  # pragma: no cover
    return run_audit(
        smartnote_proxy=Path(args.smartnote_proxy),
        rnsum_proxy=Path(args.rnsum_proxy),
        out=Path(args.out),
        summary_out=Path(args.summary),
        sample_size=args.sample_size,
        seed=args.seed,
        provider=args.provider,
        model=args.model,
        mode=args.mode,
        batch_dir=Path(args.batch_dir),
        batch_poll_interval=args.batch_poll_interval,
        max_workers=args.max_workers,
        max_retries=args.max_retries,
        min_delay=args.min_delay,
        min_interval=args.min_interval,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        bins=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        overwrite=args.overwrite,
        raw_out=None,
        skip_if_missing=False,
    )
