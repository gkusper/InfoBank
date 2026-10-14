import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRICES_FILE = REPO_ROOT / "prices.json"

if PRICES_FILE.exists():
    with open(PRICES_FILE, "r", encoding="utf-8") as f:
        PRICING_DATA = json.load(f).get("models", {})
else:
    PRICING_DATA = {}

def format_cost(cost: float) -> str:
    """Formats cost to 6 decimal places as a string to avoid scientific notation."""
    return f"{cost:.6f}"

def inject_cost_into_record(record: dict) -> dict:
    """Calculates broken-down costs and injects them into the record."""
    usage = record.get("api_usage", {})
    model = record.get("generator_model", "gpt-4o-mini")
    
    in_tokens = usage.get("input_tokens") or 0
    cached_in_tokens = usage.get("cached_input_tokens") or 0
    uncached_in_tokens = max(0, in_tokens - cached_in_tokens)
    out_tokens = usage.get("output_tokens") or 0
    
    prices = PRICING_DATA.get(model, {})
    in_price_rate = prices.get("input_usd_per_1m", 0) / 1_000_000
    cached_in_price_rate = prices.get("cached_input_usd_per_1m", 0) / 1_000_000
    out_price_rate = prices.get("output_usd_per_1m", 0) / 1_000_000
    
    input_cost = uncached_in_tokens * in_price_rate
    cached_input_cost = cached_in_tokens * cached_in_price_rate
    output_cost = out_tokens * out_price_rate
    total_cost = input_cost + cached_input_cost + output_cost
    
    record["api_usage"]["input_cost_usd"] = format_cost(input_cost)
    record["api_usage"]["cached_input_cost_usd"] = format_cost(cached_input_cost)
    record["api_usage"]["output_cost_usd"] = format_cost(output_cost)
    record["api_usage"]["total_cost_usd"] = format_cost(total_cost)
    
    if "estimated_cost_usd" in record["api_usage"]:
        del record["api_usage"]["estimated_cost_usd"]
        
    return record

def save_cost_summary(records: list, output_dir: Path):
    """Aggregates all costs and saves a summary file."""
    mode_totals = {}
    for record in records:
        mode = record.get("mode", "unknown")
        usage = record.get("api_usage", {})
        
        input_cost = float(usage.get("input_cost_usd", 0.0))
        cached_input_cost = float(usage.get("cached_input_cost_usd", 0.0))
        output_cost = float(usage.get("output_cost_usd", 0.0))
        total_cost = float(usage.get("total_cost_usd", 0.0))
        
        in_tokens = usage.get("input_tokens") or 0
        cached_in_tokens = usage.get("cached_input_tokens") or 0
        out_tokens = usage.get("output_tokens") or 0
        
        if mode not in mode_totals:
            mode_totals[mode] = {
                "total_input_tokens": 0,
                "total_cached_input_tokens": 0,
                "total_output_tokens": 0,
                "input_cost_usd": 0.0,
                "cached_input_cost_usd": 0.0,
                "output_cost_usd": 0.0,
                "total_cost_usd": 0.0
            }
        
        mode_totals[mode]["total_input_tokens"] += max(0, in_tokens - cached_in_tokens)
        mode_totals[mode]["total_cached_input_tokens"] += cached_in_tokens
        mode_totals[mode]["total_output_tokens"] += out_tokens
        
        mode_totals[mode]["input_cost_usd"] += input_cost
        mode_totals[mode]["cached_input_cost_usd"] += cached_input_cost
        mode_totals[mode]["output_cost_usd"] += output_cost
        mode_totals[mode]["total_cost_usd"] += total_cost
        
    for mode in mode_totals:
        mode_totals[mode]["input_cost_usd"] = format_cost(mode_totals[mode]["input_cost_usd"])
        mode_totals[mode]["cached_input_cost_usd"] = format_cost(mode_totals[mode]["cached_input_cost_usd"])
        mode_totals[mode]["output_cost_usd"] = format_cost(mode_totals[mode]["output_cost_usd"])
        mode_totals[mode]["total_cost_usd"] = format_cost(mode_totals[mode]["total_cost_usd"])

    with open(output_dir / "cost_summary.json", "w", encoding="utf-8") as f:
        json.dump(mode_totals, f, indent=2)