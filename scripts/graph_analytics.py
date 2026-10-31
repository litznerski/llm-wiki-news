#!/usr/bin/env python3
"""
scripts/graph_analytics.py
Graph centrality calculation and automated learning path discovery for the Knowledge Lab Obsidian Wiki.

Usage:
    python3 scripts/graph_analytics.py rank [--limit 20]
    python3 scripts/graph_analytics.py path "<Start Concept>" "<Target Concept>"
    python3 scripts/graph_analytics.py prerequisites "<Target Concept>"
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict, deque

VAULT_ROOT = Path(__file__).resolve().parent.parent
CONCEPTS_DIR = VAULT_ROOT / "wiki" / "concepts"

def load_graph():
    """Load concept nodes, calculate metrics, and build adjacency graphs."""
    concepts = {}
    edges = defaultdict(set)     # src -> set of dst
    in_edges = defaultdict(set)  # dst -> set of src
    
    if not CONCEPTS_DIR.exists():
        print(f"Error: Concepts directory not found at {CONCEPTS_DIR}", file=sys.stderr)
        sys.exit(1)
        
    for p in CONCEPTS_DIR.glob("*.md"):
        content = p.read_text(encoding="utf-8")
        stem = p.stem
        # Extract reliability score
        reliability = 1.0
        m_rel = re.search(r"reliability_score:\s*([0-9\.]+)", content)
        if m_rel:
            try:
                reliability = float(m_rel.group(1))
            except ValueError:
                pass
                
        # Extract 1-line description / definition
        summary = ""
        m_sum = re.search(r"(?:^|\n)\*\*([^*]+)\*\*\s+is\s+([^.\n]+)", content)
        if m_sum:
            summary = m_sum.group(0).strip()
        else:
            m_sum2 = re.search(r"(?:^|\n)The\s+\*\*([^*]+)\*\*\s+is\s+([^.\n]+)", content)
            if m_sum2:
                summary = m_sum2.group(0).strip()
                
        concepts[stem] = {
            "path": p,
            "reliability": reliability,
            "summary": summary
        }
        
        # Parse wikilinks, ignoring code blocks
        clean_content = re.sub(r"```[\s\S]*?```", "", content)
        for raw in re.findall(r"\[\[(.*?)\]\]", clean_content):
            target = raw.split("|")[0].split("\\|")[0].split("#")[0].strip()
            target_name = target.split("/")[-1]
            if target_name.endswith(".md"):
                target_name = target_name[:-3]
            if (CONCEPTS_DIR / f"{target_name}.md").exists() and target_name != stem:
                edges[stem].add(target_name)
                in_edges[target_name].add(stem)
                
    return concepts, edges, in_edges

def compute_pagerank(nodes, edges, in_edges, d=0.85, max_iter=50):
    N = len(nodes)
    if N == 0:
        return {}
    pr = {n: 1.0 / N for n in nodes}
    for _ in range(max_iter):
        new_pr = {}
        dangling_sum = sum(pr[n] for n in nodes if len(edges[n]) == 0)
        for n in nodes:
            rank_sum = sum(pr[src] / len(edges[src]) for src in in_edges[n])
            new_pr[n] = (1 - d) / N + d * (rank_sum + dangling_sum / N)
        pr = new_pr
    return pr

def compute_betweenness(nodes, edges):
    """Brandes algorithm for betweenness centrality."""
    N = len(nodes)
    cb = {n: 0.0 for n in nodes}
    for s in nodes:
        S = []
        P = {w: [] for w in nodes}
        sigma = {w: 0 for w in nodes}
        sigma[s] = 1
        d_dist = {w: -1 for w in nodes}
        d_dist[s] = 0
        Q = deque([s])
        while Q:
            v = Q.popleft()
            S.append(v)
            for w in edges[v]:
                if d_dist[w] < 0:
                    d_dist[w] = d_dist[v] + 1
                    Q.append(w)
                if d_dist[w] == d_dist[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = {w: 0.0 for w in nodes}
        while S:
            w = S.pop()
            for v in P[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]
    if N > 2:
        scale = 1.0 / ((N - 1) * (N - 2))
        for n in nodes:
            cb[n] *= scale
    return cb

def cmd_rank(args):
    concepts, edges, in_edges = load_graph()
    nodes = list(concepts.keys())
    pr = compute_pagerank(nodes, edges, in_edges)
    cb = compute_betweenness(nodes, edges)
    
    # Sort by PageRank
    sorted_nodes = sorted(nodes, key=lambda n: pr.get(n, 0), reverse=True)
    limit = min(args.limit, len(sorted_nodes))
    
    print(f"\n# Top {limit} Concepts by Centrality & Importance\n")
    print("| Rank | Concept Title | PageRank | In-Degree | Out-Degree | Betweenness | Reliability |")
    print("| :---: | :--- | :---: | :---: | :---: | :---: | :---: |")
    for idx, n in enumerate(sorted_nodes[:limit], 1):
        rel = concepts[n]["reliability"]
        in_d = len(in_edges[n])
        out_d = len(edges[n])
        p_val = pr.get(n, 0)
        c_val = cb.get(n, 0)
        print(f"| {idx} | [[{n}]] | {p_val:.4f} | {in_d} | {out_d} | {c_val:.4f} | {rel:.2f} |")
    print("")

def cmd_path(args):
    concepts, edges, in_edges = load_graph()
    nodes = set(concepts.keys())
    
    src = args.start_concept.strip().replace("[[", "").replace("]]", "")
    dst = args.target_concept.strip().replace("[[", "").replace("]]", "")
    
    if src not in nodes:
        print(f"Error: Start concept '{src}' not found in wiki/concepts/.", file=sys.stderr)
        return 1
    if dst not in nodes:
        print(f"Error: Target concept '{dst}' not found in wiki/concepts/.", file=sys.stderr)
        return 1
        
    pr = compute_pagerank(list(nodes), edges, in_edges)
    
    # Build bidirectional graph for path search
    adj = {n: edges[n] | in_edges[n] for n in nodes}
    queue = deque([[src]])
    visited = {src}
    shortest = None
    
    while queue:
        path = queue.popleft()
        curr = path[-1]
        if curr == dst:
            shortest = path
            break
        # Sort neighbors by PageRank to favor authoritative scaffold nodes
        nbrs = sorted(adj[curr] - visited, key=lambda n: pr.get(n, 0), reverse=True)
        for nbr in nbrs:
            visited.add(nbr)
            queue.append(path + [nbr])
            
    if not shortest:
        print(f"No path found between '{src}' and '{dst}'.")
        return 1
        
    print(f"\n# Pedagogical Learning Path: [[{src}]] → [[{dst}]]\n")
    print(f"**Path Depth**: {len(shortest) - 1} transitions ({len(shortest)} concepts)\n")
    
    for idx, step in enumerate(shortest, 1):
        role = "Starting Anchor" if idx == 1 else ("Target Mastery" if idx == len(shortest) else "Scaffold Bridge")
        pr_score = pr.get(step, 0)
        print(f"### Stage {idx}: [[{step}]] ({role})")
        print(f"- **PageRank**: {pr_score:.4f} | **In-Degree**: {len(in_edges[step])}")
        if concepts[step]["summary"]:
            print(f"- **Summary**: {concepts[step]['summary']}")
        print("")
        
    # Render Mermaid diagram
    print("```mermaid")
    print("flowchart TD")
    for i in range(len(shortest) - 1):
        c1 = shortest[i]
        c2 = shortest[i+1]
        print(f'    node{i}["{i+1}. [[{c1}]]"] --> node{i+1}["{i+2}. [[{c2}]]"]')
    print("```\n")

def cmd_prerequisites(args):
    concepts, edges, in_edges = load_graph()
    target = args.target_concept.strip().replace("[[", "").replace("]]", "")
    
    if target not in concepts:
        print(f"Error: Target concept '{target}' not found in wiki/concepts/.", file=sys.stderr)
        return 1
        
    pr = compute_pagerank(list(concepts.keys()), edges, in_edges)
    
    # Directly connected incoming concepts
    prereqs = list(in_edges[target])
    # Also include concepts target links out to if they have higher PageRank
    for out_c in edges[target]:
        if pr.get(out_c, 0) > pr.get(target, 0) and out_c not in prereqs:
            prereqs.append(out_c)
            
    prereqs.sort(key=lambda n: pr.get(n, 0), reverse=True)
    
    print(f"\n# Prerequisite Subgraph for [[{target}]]\n")
    print(f"Found {len(prereqs)} foundational concept(s):\n")
    print("| Order | Prerequisite Concept | PageRank | In-Degree | Pedagogical Function |")
    print("| :---: | :--- | :---: | :---: | :--- |")
    for idx, n in enumerate(prereqs, 1):
        p_val = pr.get(n, 0)
        in_d = len(in_edges[n])
        print(f"| {idx} | [[{n}]] | {p_val:.4f} | {in_d} | Foundational Antecedent |")
    print("")

def main():
    parser = argparse.ArgumentParser(description="Graph Centrality & Learning Path CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    
    # Subcommand: rank
    p_rank = subparsers.add_parser("rank", help="Rank concepts by centrality metrics")
    p_rank.add_argument("--limit", type=int, default=20, help="Number of nodes to return")
    p_rank.set_defaults(func=cmd_rank)
    
    # Subcommand: path
    p_path = subparsers.add_parser("path", help="Find pedagogical learning path between two concepts")
    p_path.add_argument("start_concept", help="Starting concept name")
    p_path.add_argument("target_concept", help="Target concept name")
    p_path.set_defaults(func=cmd_path)
    
    # Subcommand: prerequisites
    p_pre = subparsers.add_parser("prerequisites", help="Find prerequisites for a target concept")
    p_pre.add_argument("target_concept", help="Target concept name")
    p_pre.set_defaults(func=cmd_prerequisites)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
