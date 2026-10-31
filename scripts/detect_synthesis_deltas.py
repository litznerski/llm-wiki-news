#!/usr/bin/env python3
"""
scripts/detect_synthesis_deltas.py
Automated Synthesis Delta Sentinel & Invalidation Engine for ArcadeDB.

Detects epistemic drift between pre-compiled Golden Syntheses (wiki/syntheses/)
and underlying concept/entity sections by comparing live markdown section hashes
against ArcadeDB SYNTHESIZES_SECTION.expected_hash.

Features:
- Deterministic SHA-256 (16-char) section hashing.
- Surgical section-level invalidation (zero false alarms for unrelated sections).
- Zero-bloat logging into decoupled SynthesisDelta document collection (no search pollution).
- Automatic flag management: s.stale = true/false, s.stale_reason.
- Re-anchoring support via --reset flag.
- JSON output support via --json flag.
"""

import sys
import os
import re
import json
import time
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.ingest_to_arcadedb import (
    ArcadeDBClient,
    parse_frontmatter,
    parse_sections,
    process_section_diagrams,
    WIKI_DIR,
    ARCADEDB_DATABASE,
    ARCADEDB_URL,
    ARCADEDB_USER,
    ARCADEDB_PASSWORD,
)


def compute_live_section_hash(vault_root: Path, sec_uri: str, fallback_heading: str = "") -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parses the live markdown file on disk for a given section_uri.
    Returns: (live_hash, clean_snippet, matched_heading) or (None, None, None) if not found.
    """
    # Clean sec_uri: e.g. "wiki/concepts/Cognitive Surrender.md#3" or "concepts/Cognitive Surrender.md#3"
    clean_uri = sec_uri.strip()
    if clean_uri.startswith("wiki/"):
        rel_path_str = clean_uri[5:]
    else:
        rel_path_str = clean_uri

    if "#" in rel_path_str:
        file_part, idx_part = rel_path_str.split("#", 1)
        try:
            target_idx = int(idx_part)
        except ValueError:
            target_idx = None
    else:
        file_part = rel_path_str
        target_idx = None

    file_path = vault_root / "wiki" / file_part
    if not file_path.exists():
        # Fallback to direct path
        file_path = vault_root / clean_uri.split("#")[0]
        if not file_path.exists():
            return None, None, None

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return None, None, None

    _, body = parse_frontmatter(content)
    raw_secs = parse_sections(str(file_path.relative_to(vault_root)), body)

    matched = None
    if target_idx is not None:
        for s in raw_secs:
            if s["idx"] == target_idx:
                matched = s
                break

    if not matched and fallback_heading:
        fh_lower = fallback_heading.lower().strip()
        for s in raw_secs:
            sh_lower = s["title"].lower().strip()
            if fh_lower == sh_lower or fh_lower in sh_lower or sh_lower in fh_lower:
                matched = s
                break

    if not matched:
        return None, None, None

    clean_content, _ = process_section_diagrams(sec_uri, matched["title"], matched["content"])
    sec_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()[:16]
    snippet = clean_content[:200].replace("\n", " ").strip()
    return sec_hash, snippet, matched["title"]


def detect_synthesis_deltas(
    client: ArcadeDBClient,
    vault_root: Path,
    reset_anchor: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Queries all SYNTHESIZES_SECTION edges from ArcadeDB and verifies them against disk.
    """
    if verbose:
        print("=================================================================")
        print("  ArcadeDB Synthesis Epistemic Drift & Delta Sentinel")
        print(f"  Target Database : {client.database} @ {client.base_url}")
        if reset_anchor:
            print("  MODE            : RE-ANCHOR (--reset: updating expected hashes)")
        else:
            print("  MODE            : VERIFICATION & DRIFT DETECTION")
        print("=================================================================\n")

    query = """
    MATCH (s:Synthesis)-[r:SYNTHESIZES_SECTION]->(sec:Section)
    RETURN s.slug AS synth_slug, s.title AS synth_title, id(s) AS s_rid, s.stale AS current_stale,
           r.grounded_heading AS grounded_heading, r.expected_hash AS expected_hash,
           r.drift_detected AS drift_detected, id(r) AS r_rid,
           sec.uri AS sec_uri, sec.heading AS sec_heading, sec.content_hash AS db_hash, id(sec) AS sec_rid
    ORDER BY s.slug, sec.uri
    """

    try:
        edges = client.query(query, language="cypher")
    except Exception as e:
        print(f"[!] Error querying SYNTHESIZES_SECTION edges: {e}")
        return {"error": str(e), "total_syntheses": 0, "stale_syntheses": 0, "deltas": []}

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Group edges by synthesis
    synths: Dict[str, Dict[str, Any]] = {}
    for row in edges:
        slug = row["synth_slug"]
        if slug not in synths:
            synths[slug] = {
                "slug": slug,
                "title": row["synth_title"],
                "s_rid": row["s_rid"],
                "current_stale": bool(row.get("current_stale", False)),
                "edges": []
            }
        synths[slug]["edges"].append(row)

    total_synths = len(synths)
    stale_count = 0
    drifted_edges_count = 0
    detected_deltas = []

    for slug, synth_info in synths.items():
        s_rid = synth_info["s_rid"]
        title = synth_info["title"]
        synth_drift_detected = False
        drift_reasons = []

        if verbose:
            print(f"[*] Analyzing Synthesis: '{title}' ({slug})")
            print(f"    Grounded Section Edges: {len(synth_info['edges'])}")

        for edge in synth_info["edges"]:
            sec_uri = edge["sec_uri"]
            r_rid = edge["r_rid"]
            grounded_heading = edge.get("grounded_heading") or edge.get("sec_heading") or ""
            expected_hash = edge.get("expected_hash") or ""
            edge_drift_flag = bool(edge.get("drift_detected", False))

            live_hash, snippet, matched_heading = compute_live_section_hash(
                vault_root, sec_uri, fallback_heading=grounded_heading
            )

            # Check if section was removed or altered
            if live_hash is None:
                change_type = "SECTION_REMOVED"
                is_drift = True
                curr_hash = "NOT_FOUND"
                reason_desc = f"Section removed or unreachable: {grounded_heading} ({sec_uri})"
            elif not expected_hash:
                # Unanchored edge -> anchor it
                is_drift = False
                curr_hash = live_hash
                reason_desc = ""
                # Initialize expected hash
                try:
                    cypher_anchor = f"""
                    MATCH (s:Synthesis {{slug: '{slug}'}})-[r:SYNTHESIZES_SECTION]->(sec:Section {{uri: '{sec_uri}'}})
                    SET r.expected_hash = '{live_hash}', r.drift_detected = false, r.last_checked = '{now_iso}'
                    """
                    client.execute_command(cypher_anchor, language="cypher")
                except Exception:
                    pass
            elif reset_anchor:
                # Explicit re-anchor mode
                is_drift = False
                curr_hash = live_hash
                reason_desc = ""
                try:
                    cypher_anchor = f"""
                    MATCH (s:Synthesis {{slug: '{slug}'}})-[r:SYNTHESIZES_SECTION]->(sec:Section {{uri: '{sec_uri}'}})
                    SET r.expected_hash = '{live_hash}', r.drift_detected = false, r.last_checked = '{now_iso}'
                    """
                    client.execute_command(cypher_anchor, language="cypher")
                except Exception:
                    pass
            elif live_hash != expected_hash:
                change_type = "CONTENT_MODIFIED"
                is_drift = True
                curr_hash = live_hash
                reason_desc = f"Modified: {grounded_heading} ({sec_uri})"
            else:
                is_drift = False
                curr_hash = live_hash
                reason_desc = ""

            if is_drift:
                synth_drift_detected = True
                drifted_edges_count += 1
                drift_reasons.append(reason_desc)

                delta_item = {
                    "synthesis_slug": slug,
                    "synthesis_title": title,
                    "section_uri": sec_uri,
                    "grounded_heading": grounded_heading,
                    "change_type": change_type,
                    "expected_hash": expected_hash,
                    "live_hash": curr_hash,
                    "diff_snippet": snippet or "Section content divergence detected.",
                    "timestamp": now_iso
                }
                detected_deltas.append(delta_item)

                if verbose:
                    print(f"    [!] DRIFT DETECTED: {grounded_heading}")
                    print(f"        Expected: {expected_hash} | Live: {curr_hash}")
                    print(f"        URI: {sec_uri}")

                # Update Edge in ArcadeDB
                try:
                    cypher_edge = f"""
                    MATCH (s:Synthesis {{slug: '{slug}'}})-[r:SYNTHESIZES_SECTION]->(sec:Section {{uri: '{sec_uri}'}})
                    SET r.drift_detected = true, r.last_checked = '{now_iso}'
                    """
                    client.execute_command(cypher_edge, language="cypher")
                except Exception as e:
                    if verbose:
                        print(f"        [!] Failed to update edge: {e}")

                # Check if existing unresolved delta already recorded
                try:
                    escaped_uri = sec_uri.replace("'", "\\'")
                    existing = client.query(
                        f"SELECT count(*) AS cnt FROM SynthesisDelta WHERE synthesis_slug = '{slug}' AND section_uri = '{escaped_uri}' AND resolved = false",
                        language="sql"
                    )
                    cnt = existing[0].get("cnt", 0) if existing else 0
                    if cnt == 0:
                        safe_snippet = (snippet or "").replace("'", "\\'").replace('"', '\\"')[:250]
                        safe_heading = grounded_heading.replace("'", "\\'")
                        insert_cmd = f"""
                        INSERT INTO SynthesisDelta CONTENT {{
                            "synthesis_slug": "{slug}",
                            "section_uri": "{escaped_uri}",
                            "grounded_heading": "{safe_heading}",
                            "change_type": "{change_type}",
                            "diff_snippet": "{safe_snippet}",
                            "expected_hash": "{expected_hash}",
                            "live_hash": "{curr_hash}",
                            "timestamp": "{now_iso}",
                            "resolved": false
                        }}
                        """
                        client.execute_command(insert_cmd, language="sql")
                except Exception as e:
                    if verbose:
                        print(f"        [!] Failed to log SynthesisDelta: {e}")

            else:
                # No drift on this edge
                if edge_drift_flag:
                    try:
                        cypher_edge = f"""
                        MATCH (s:Synthesis {{slug: '{slug}'}})-[r:SYNTHESIZES_SECTION]->(sec:Section {{uri: '{sec_uri}'}})
                        SET r.drift_detected = false, r.last_checked = '{now_iso}'
                        """
                        client.execute_command(cypher_edge, language="cypher")
                    except Exception:
                        pass

        # Update Synthesis vertex status
        if synth_drift_detected:
            stale_count += 1
            combined_reason = "; ".join(drift_reasons)[:250].replace("'", "\\'")
            try:
                cypher_synth = f"""
                MATCH (s:Synthesis {{slug: '{slug}'}})
                SET s.stale = true, s.stale_reason = '{combined_reason}'
                """
                client.execute_command(cypher_synth, language="cypher")
            except Exception as e:
                if verbose:
                    print(f"    [!] Failed to update synthesis stale flag: {e}")
            if verbose:
                print(f"    → Synthesis Status: [STALE] ({len(drift_reasons)} diverged sections)\n")
        else:
            try:
                cypher_synth = f"""
                MATCH (s:Synthesis {{slug: '{slug}'}})
                SET s.stale = false, s.stale_reason = ''
                """
                client.execute_command(cypher_synth, language="cypher")
                client.execute_command(
                    f"UPDATE SynthesisDelta SET resolved = true WHERE synthesis_slug = '{slug}' AND resolved = false",
                    language="sql"
                )
            except Exception as e:
                if verbose:
                    print(f"    [!] Failed to update synthesis clean flag: {e}")
            if verbose:
                print("    → Synthesis Status: [FRESH] (100% section parity)\n")

    summary = {
        "status": "success",
        "timestamp": now_iso,
        "mode": "reset" if reset_anchor else "check",
        "total_syntheses": total_synths,
        "stale_syntheses": stale_count,
        "fresh_syntheses": total_synths - stale_count,
        "drifted_edges": drifted_edges_count,
        "deltas": detected_deltas
    }

    if verbose:
        print("=================================================================")
        print(f"  Summary: {total_synths} Syntheses Analyzed")
        print(f"  Fresh   : {total_synths - stale_count}")
        print(f"  Stale   : {stale_count} ({drifted_edges_count} total diverged section edges)")
        print("=================================================================")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Automated Synthesis Delta Sentinel for ArcadeDB")
    parser.add_argument("--reset", action="store_true", help="Re-anchor expected hashes to live file hashes and clear stale flags")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format")
    parser.add_argument("--url", default=ARCADEDB_URL, help="ArcadeDB server URL")
    parser.add_argument("--db", default=ARCADEDB_DATABASE, help="Target database name")
    parser.add_argument("--user", default=ARCADEDB_USER, help="ArcadeDB username")
    parser.add_argument("--password", default=ARCADEDB_PASSWORD, help="ArcadeDB password")

    args = parser.parse_args()

    client = ArcadeDBClient(base_url=args.url, database=args.db, user=args.user, password=args.password)
    vault_root = REPO_ROOT

    summary = detect_synthesis_deltas(
        client=client,
        vault_root=vault_root,
        reset_anchor=args.reset,
        verbose=not args.json
    )

    if args.json:
        print(json.dumps(summary, indent=2))

    if summary.get("stale_syntheses", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
