"""
scripts/test_openwebui_inlet_filter.py
End-to-end regression testing of open_webui_arcadedb_fastmcp_pipe.py
Simulates OpenWebUI message processing across all 5 regression scenarios:
1. PageRank ranking query
2. Macro-CoT remedy traversal
3. Shortest-Path calculation
4. JVector similarity search
5. OpenCypher variable shadowing auto-repair (the user's failing query)
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from setup.open_webui_arcadedb_fastmcp_pipe import Filter


async def run_regression_suite():
    print("==================================================")
    print("Starting OpenWebUI FastMCP Inlet Filter Test Suite")
    print("==================================================")

    f = Filter()
    # Point to published host port 8000
    f.valves.fastmcp_url = "http://localhost:8000/inlet"

    async def mock_event_emitter(event: dict):
        status = event.get("data", {}).get("description", "")
        done = event.get("data", {}).get("done", False)
        prefix = "  [DONE]" if done else "  [WAIT]"
        print(f"{prefix} Status Event: {status}")

    test_cases = [
        (
            "PageRank Ranking",
            "Show the top 3 ranked concepts by authority",
            ["title", "pagerank"],
        ),
        (
            "Macro-CoT Remedy",
            "What solutions or mitigations remedy Cognitive Surrender?",
            ["solution_title", "Artifact vs. Defense Assessment"],
        ),
        (
            "Shortest Path",
            "Find the shortest path between AI Learning Paradox and Cognitive Surrender",
            ["path", "hops"],
        ),
        (
            "JVector Similarity",
            "Find the 5 most similar sections to the Core Thesis using vector search",
            ["distance", "step_type"],
        ),
        (
            "User's Variable Shadowing Query",
            (
                "MATCH (remedy:Concept)-[:REMEDIES_DILEMMA]->(target:Concept {title: 'Cognitive Surrender'})\n"
                "RETURN remedy.title AS remedy,\n"
                "       remedy.pagerank AS pagerank\n"
                "ORDER BY remedy.pagerank DESC;"
            ),
            ["remedy_title", "pagerank"],
        ),
    ]

    for title, prompt, expected_tokens in test_cases:
        print(f"\n--- Testing Scenario: {title} ---")
        print(f"Prompt: {prompt.splitlines()[0]}")
        body = {
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        res = await f.inlet(body, __event_emitter__=mock_event_emitter)
        final_content = res["messages"][-1]["content"]

        assert "> [!DATA] Grounded ArcadeDB Knowledge Context" in final_content, "Missing grounded context card"
        for token in expected_tokens:
            assert token in final_content, f"Expected '{token}' in final content"

        print(f"✓ Scenario '{title}' PASSED! Context injected successfully.")

    print("\n==================================================")
    print("🎉 ALL 5 OPENWEBUI REGRESSION SCENARIOS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_regression_suite())
