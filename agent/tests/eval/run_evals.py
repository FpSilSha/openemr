"""AgentForge evaluation runner — loads dataset, runs agent, scores results.

Usage:
    python -m tests.eval.run_evals

Requires:
    - LANGCHAIN_API_KEY (for LangSmith dataset management)
    - ANTHROPIC_API_KEY (for agent execution)
    - Running OpenEMR instance (for FHIR data)

This script:
1. Loads tests/eval/dataset.json
2. Optionally uploads to LangSmith as a dataset
3. Runs the agent graph for each example
4. Scores with all scoring functions
5. Prints a summary table
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add agent/ to path for imports
AGENT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(AGENT_DIR))

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
LANGSMITH_DATASET_NAME = "agentforge-openemr-eval"


def load_dataset() -> list[dict]:
    """Load evaluation dataset from JSON file."""
    with open(DATASET_PATH) as f:
        return json.load(f)


async def run_single_example(graph, example: dict) -> dict:
    """Run the agent graph on a single eval example and collect results.

    Returns:
        Dict with ``response`` (str) and ``tool_calls`` (list of tool names).
    """
    from langchain_core.messages import AIMessage, HumanMessage

    initial_state = {
        "messages": [HumanMessage(content=example["input"])],
        "patient_uuid": example.get("patient_uuid"),
        "patient_context": (
            {"uuid": example["patient_uuid"]}
            if example.get("patient_uuid")
            else None
        ),
        "verification_attempts": 0,
    }

    try:
        result = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error("Example %s failed: %s", example["id"], e)
        return {"response": f"ERROR: {e}", "tool_calls": []}

    # Extract response and tool calls from messages
    response_text = ""
    tool_calls: list[str] = []

    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage):
            if isinstance(msg.content, str) and msg.content:
                response_text = msg.content
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(tc["name"])

    return {"response": response_text, "tool_calls": tool_calls}


def score_run(
    run: dict, example: dict, scorers: list
) -> list[dict]:
    """Apply all scoring functions to a single run."""
    return [scorer(run, example) for scorer in scorers]


def print_summary(results: list[dict]) -> None:
    """Print a formatted summary table of evaluation results."""
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print("=" * 80)

    # Per-example results
    for result in results:
        example = result["example"]
        scores = result["scores"]
        status = "PASS" if all(s["score"] >= 0.5 for s in scores) else "FAIL"
        print(f"\n[{status}] {example['id']} ({example['category']})")
        print(f"  Input: {example['input'][:70]}...")
        for s in scores:
            icon = "+" if s["score"] >= 0.5 else "-"
            print(f"  [{icon}] {s['key']}: {s['score']:.2f} — {s['comment']}")

    # Aggregate scores by metric
    print("\n" + "-" * 80)
    print("AGGREGATE SCORES")
    print("-" * 80)

    all_scores: dict[str, list[float]] = {}
    for result in results:
        for s in result["scores"]:
            all_scores.setdefault(s["key"], []).append(s["score"])

    for key, values in sorted(all_scores.items()):
        avg = sum(values) / len(values)
        print(f"  {key}: {avg:.2f} (n={len(values)})")

    # Overall
    total_scores = [
        s["score"] for r in results for s in r["scores"]
    ]
    overall = sum(total_scores) / len(total_scores) if total_scores else 0
    print(f"\n  OVERALL: {overall:.2f}")
    print("=" * 80)


def upload_to_langsmith(dataset: list[dict]) -> None:
    """Upload dataset to LangSmith if API key is available."""
    api_key = os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        logger.info("LANGCHAIN_API_KEY not set — skipping LangSmith upload")
        return

    try:
        from langsmith import Client

        client = Client()

        # Create or update dataset
        try:
            ls_dataset = client.create_dataset(
                dataset_name=LANGSMITH_DATASET_NAME,
                description="AgentForge OpenEMR evaluation dataset",
            )
        except Exception:
            ls_dataset = client.read_dataset(
                dataset_name=LANGSMITH_DATASET_NAME
            )

        # Add examples
        for example in dataset:
            client.create_example(
                inputs={"input": example["input"]},
                outputs={
                    "expected_tools": example["expected_tools"],
                    "expected_in_response": example["expected_in_response"],
                },
                dataset_id=ls_dataset.id,
                metadata={
                    "id": example["id"],
                    "category": example["category"],
                },
            )

        logger.info(
            "Uploaded %d examples to LangSmith dataset '%s'",
            len(dataset),
            LANGSMITH_DATASET_NAME,
        )
    except ImportError:
        logger.warning("langsmith package not installed — skipping upload")
    except Exception as e:
        logger.warning("LangSmith upload failed: %s", e)


async def _init_clients():
    """Initialize tool clients (same as main.py lifespan)."""
    from app.clients.icd10_client import ICD10Client
    from app.clients.openemr import OpenEMRClient
    from app.clients.openfda import DrugInteractionClient
    from app.clients.pubmed_client import PubMedClient
    from app.config import settings
    from app.tools import allergies as allergies_tool
    from app.tools import appointments as appointments_tool
    from app.tools import icd10 as icd10_tool
    from app.tools import labs as labs_tool
    from app.tools import medications as med_tool
    from app.tools import patient as patient_tool
    from app.tools import pubmed as pubmed_tool
    from app.tools import vitals as vitals_tool

    openemr = OpenEMRClient(settings)
    drug = DrugInteractionClient(timeout=settings.tool_timeout_seconds)
    icd10 = ICD10Client(timeout=settings.tool_timeout_seconds)
    pubmed = PubMedClient(
        api_key=settings.pubmed_api_key,
        timeout=settings.tool_timeout_seconds,
    )

    try:
        await openemr.authenticate()
        logger.info("OpenEMR OAuth2 authentication successful")
    except Exception as e:
        logger.warning("OpenEMR auth failed (tools will return errors): %s", e)

    patient_tool.set_client(openemr)
    labs_tool.set_client(openemr)
    med_tool.set_clients(openemr, drug)
    icd10_tool.set_client(icd10)
    pubmed_tool.set_client(pubmed)
    appointments_tool.set_client(openemr)
    vitals_tool.set_client(openemr)
    allergies_tool.set_client(openemr)


async def main() -> None:
    """Run the full evaluation pipeline."""
    from app.agent.graph import build_graph
    from app.agent.models import get_primary_model, get_verification_model
    from app.config import settings
    from tests.eval.scoring import (
        correct_tool_selected,
        drug_interaction_flagged,
        no_system_prompt_leak,
        source_attribution_present,
    )

    scorers = [
        correct_tool_selected,
        drug_interaction_flagged,
        source_attribution_present,
        no_system_prompt_leak,
    ]

    # Load dataset
    dataset = load_dataset()
    logger.info("Loaded %d eval examples", len(dataset))

    # Optionally upload to LangSmith
    upload_to_langsmith(dataset)

    # Initialize tool clients
    await _init_clients()

    # Build agent graph
    model = get_primary_model(settings)
    verify_model = get_verification_model(settings)
    graph = build_graph(model, verification_model=verify_model)

    # Run evaluations
    results = []
    for i, example in enumerate(dataset):
        logger.info(
            "Running %d/%d: %s", i + 1, len(dataset), example["id"]
        )
        run = await run_single_example(graph, example)
        scores = score_run(run, example, scorers)
        results.append({"example": example, "run": run, "scores": scores})

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
