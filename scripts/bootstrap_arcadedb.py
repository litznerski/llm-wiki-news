#!/usr/bin/env python3
"""
scripts/bootstrap_arcadedb.py
Clears legacy ArcadeDB databases/types (when --reset is passed) and initializes the clean
Sudan News & OSINT Multi-Model Schema in ArcadeDB (`http://localhost:2481`, database `news`):
  1. Vertex Types: Event, Actor, Location, Theme, Timeline, Source, Section, Tag
  2. Document Types: AliasLookup, IntentAnchor, ClaimDispute, SynthesisDelta
  3. Edge Types:
     - Micro-CoT & AST: PROGRESSES_TO, HAS_SECTION, TAGGED_WITH, CITES
     - Causal & Temporal: PRECEDES, TRIGGERS, RETALIATES_FOR, PART_OF_CAMPAIGN, MOTIVATED_BY
     - Actor Agency: PERPETRATED_BY, TARGETED, PARTICIPATED_IN, COMMANDED_BY, ALLIED_WITH, SPONSORED_BY, DEFECTED_TO
     - Spatio-Political: OCCURRED_AT, LOCATED_IN, CONTROLS_TERRITORY, DISPLACES_POPULATION
     - Provenance & Contradiction: EMPIRICALLY_GROUNDS, CORROBORATES, CONTRADICTS_CLAIM, ATTRIBUTES_BLAME_TO, DEBUNKS, PUBLISHED_BY
  4. Glossary & Safeguard Seeding:
     - Seeds cross-lingual Arabic/English AliasLookup records from wiki/glossary.md
     - Seeds baseline Sudan ADM0/ADM1 Location vertices (SD01-SD18) and core Actor vertices from wiki/glossary.md
     - Seeds safeguard IntentAnchor records from setup/safeguard_intent_anchors.md
"""

import os
import sys
import re
import json
import base64
import argparse
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bootstrap_arcadedb")

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Automatically source .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

ARCADEDB_URL = os.getenv("ARCADEDB_URL", "http://localhost:2481").rstrip("/")
DATABASE = os.getenv("ARCADEDB_DATABASE", "news")
USER = os.getenv("ARCADEDB_USER", "root")
PASSWORD = os.getenv("ARCADEDB_PASSWORD", "root_secret")


def http_request(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    auth: bool = True,
    timeout: int = 10,
) -> Tuple[int, str, Dict[str, Any]]:
    """Stdlib HTTP helper with Basic Auth and JSON serialization."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth:
        token = base64.b64encode(f"{USER}:{PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {}
            return status, body, parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {}
        return e.code, body, parsed


DDL_COMMANDS = [
    # 1. Core Sudan News & OSINT Vertex Types & Properties
    ("CREATE VERTEX TYPE Event IF NOT EXISTS", "Create vertex Event"),
    ("CREATE PROPERTY Event.title IF NOT EXISTS STRING", "Property Event.title"),
    ("CREATE PROPERTY Event.type IF NOT EXISTS STRING", "Property Event.type"),
    ("CREATE PROPERTY Event.subtype IF NOT EXISTS STRING", "Property Event.subtype"),
    ("CREATE PROPERTY Event.event_category IF NOT EXISTS STRING", "Property Event.event_category"),
    ("CREATE PROPERTY Event.event_sub_type IF NOT EXISTS STRING", "Property Event.event_sub_type"),
    ("CREATE PROPERTY Event.event_start_date IF NOT EXISTS STRING", "Property Event.event_start_date"),
    ("CREATE PROPERTY Event.event_end_date IF NOT EXISTS STRING", "Property Event.event_end_date"),
    ("CREATE PROPERTY Event.reported_date IF NOT EXISTS STRING", "Property Event.reported_date"),
    ("CREATE PROPERTY Event.pcode IF NOT EXISTS STRING", "Property Event.pcode"),
    ("CREATE PROPERTY Event.fatalities_low IF NOT EXISTS INTEGER", "Property Event.fatalities_low"),
    ("CREATE PROPERTY Event.fatalities_best IF NOT EXISTS INTEGER", "Property Event.fatalities_best"),
    ("CREATE PROPERTY Event.fatalities_high IF NOT EXISTS INTEGER", "Property Event.fatalities_high"),
    ("CREATE PROPERTY Event.verification_status IF NOT EXISTS STRING", "Property Event.verification_status"),
    ("CREATE PROPERTY Event.admiralty_rating IF NOT EXISTS STRING", "Property Event.admiralty_rating"),
    ("CREATE PROPERTY Event.reliability_score IF NOT EXISTS DOUBLE", "Property Event.reliability_score"),
    ("CREATE PROPERTY Event.contradiction_flags IF NOT EXISTS LIST OF STRING", "Property Event.contradiction_flags"),
    ("CREATE PROPERTY Event.last_updated IF NOT EXISTS STRING", "Property Event.last_updated"),
    ("CREATE INDEX IF NOT EXISTS ON Event (title) UNIQUE", "Index Event.title UNIQUE"),
    ("CREATE INDEX IF NOT EXISTS ON Event (event_start_date) NOTUNIQUE", "Index Event.event_start_date"),
    ("CREATE INDEX IF NOT EXISTS ON Event (pcode) NOTUNIQUE", "Index Event.pcode"),

    ("CREATE VERTEX TYPE Actor IF NOT EXISTS", "Create vertex Actor"),
    ("CREATE PROPERTY Actor.title IF NOT EXISTS STRING", "Property Actor.title"),
    ("CREATE PROPERTY Actor.acronym IF NOT EXISTS STRING", "Property Actor.acronym"),
    ("CREATE PROPERTY Actor.subtype IF NOT EXISTS STRING", "Property Actor.subtype"),
    ("CREATE PROPERTY Actor.acled_actor_type IF NOT EXISTS STRING", "Property Actor.acled_actor_type"),
    ("CREATE PROPERTY Actor.leader IF NOT EXISTS STRING", "Property Actor.leader"),
    ("CREATE PROPERTY Actor.aliases IF NOT EXISTS LIST OF STRING", "Property Actor.aliases"),
    ("CREATE PROPERTY Actor.summary_note IF NOT EXISTS STRING", "Property Actor.summary_note"),
    ("CREATE PROPERTY Actor.reliability_score IF NOT EXISTS DOUBLE", "Property Actor.reliability_score"),
    ("CREATE PROPERTY Actor.last_updated IF NOT EXISTS STRING", "Property Actor.last_updated"),
    ("CREATE INDEX IF NOT EXISTS ON Actor (title) UNIQUE", "Index Actor.title UNIQUE"),

    ("CREATE VERTEX TYPE Location IF NOT EXISTS", "Create vertex Location"),
    ("CREATE PROPERTY Location.title IF NOT EXISTS STRING", "Property Location.title"),
    ("CREATE PROPERTY Location.subtype IF NOT EXISTS STRING", "Property Location.subtype"),
    ("CREATE PROPERTY Location.pcode IF NOT EXISTS STRING", "Property Location.pcode"),
    ("CREATE PROPERTY Location.adm_level IF NOT EXISTS INTEGER", "Property Location.adm_level"),
    ("CREATE PROPERTY Location.capital_hub IF NOT EXISTS STRING", "Property Location.capital_hub"),
    ("CREATE PROPERTY Location.aliases IF NOT EXISTS LIST OF STRING", "Property Location.aliases"),
    ("CREATE PROPERTY Location.current_control IF NOT EXISTS STRING", "Property Location.current_control"),
    ("CREATE PROPERTY Location.humanitarian_ipc_phase IF NOT EXISTS INTEGER", "Property Location.humanitarian_ipc_phase"),
    ("CREATE PROPERTY Location.reliability_score IF NOT EXISTS DOUBLE", "Property Location.reliability_score"),
    ("CREATE PROPERTY Location.last_updated IF NOT EXISTS STRING", "Property Location.last_updated"),
    ("CREATE INDEX IF NOT EXISTS ON Location (title) UNIQUE", "Index Location.title UNIQUE"),
    ("CREATE INDEX IF NOT EXISTS ON Location (pcode) NOTUNIQUE", "Index Location.pcode"),

    ("CREATE VERTEX TYPE Theme IF NOT EXISTS", "Create vertex Theme"),
    ("CREATE PROPERTY Theme.title IF NOT EXISTS STRING", "Property Theme.title"),
    ("CREATE PROPERTY Theme.subtype IF NOT EXISTS STRING", "Property Theme.subtype"),
    ("CREATE PROPERTY Theme.reliability_score IF NOT EXISTS DOUBLE", "Property Theme.reliability_score"),
    ("CREATE PROPERTY Theme.last_updated IF NOT EXISTS STRING", "Property Theme.last_updated"),
    ("CREATE INDEX IF NOT EXISTS ON Theme (title) UNIQUE", "Index Theme.title UNIQUE"),

    ("CREATE VERTEX TYPE Timeline IF NOT EXISTS", "Create vertex Timeline"),
    ("CREATE PROPERTY Timeline.title IF NOT EXISTS STRING", "Property Timeline.title"),
    ("CREATE PROPERTY Timeline.subtype IF NOT EXISTS STRING", "Property Timeline.subtype"),
    ("CREATE PROPERTY Timeline.last_updated IF NOT EXISTS STRING", "Property Timeline.last_updated"),
    ("CREATE INDEX IF NOT EXISTS ON Timeline (title) UNIQUE", "Index Timeline.title UNIQUE"),

    ("CREATE VERTEX TYPE Source IF NOT EXISTS", "Create vertex Source"),
    ("CREATE PROPERTY Source.title IF NOT EXISTS STRING", "Property Source.title"),
    ("CREATE PROPERTY Source.slug IF NOT EXISTS STRING", "Property Source.slug"),
    ("CREATE PROPERTY Source.subtype IF NOT EXISTS STRING", "Property Source.subtype"),
    ("CREATE PROPERTY Source.language IF NOT EXISTS STRING", "Property Source.language"),
    ("CREATE PROPERTY Source.alignment IF NOT EXISTS STRING", "Property Source.alignment"),
    ("CREATE PROPERTY Source.admiralty_rating IF NOT EXISTS STRING", "Property Source.admiralty_rating"),
    ("CREATE PROPERTY Source.reliability_score IF NOT EXISTS DOUBLE", "Property Source.reliability_score"),
    ("CREATE PROPERTY Source.published_date IF NOT EXISTS STRING", "Property Source.published_date"),
    ("CREATE INDEX IF NOT EXISTS ON Source (slug) UNIQUE", "Index Source.slug UNIQUE"),

    ("CREATE VERTEX TYPE Section IF NOT EXISTS", "Create vertex Section"),
    ("CREATE PROPERTY Section.heading IF NOT EXISTS STRING", "Property Section.heading"),
    ("CREATE PROPERTY Section.content IF NOT EXISTS STRING", "Property Section.content"),
    ("CREATE PROPERTY Section.step_type IF NOT EXISTS STRING", "Property Section.step_type"),
    ("CREATE PROPERTY Section.vector IF NOT EXISTS LIST OF FLOAT", "Property Section.vector"),

    ("CREATE VERTEX TYPE Tag IF NOT EXISTS", "Create vertex Tag"),
    ("CREATE PROPERTY Tag.name IF NOT EXISTS STRING", "Property Tag.name"),
    ("CREATE INDEX IF NOT EXISTS ON Tag (name) UNIQUE", "Index Tag.name UNIQUE"),

    # 2. Document Collections & Key-Value Stores (AliasLookup, IntentAnchor, ClaimDispute, SynthesisDelta)
    ("CREATE DOCUMENT TYPE AliasLookup IF NOT EXISTS", "Create document AliasLookup"),
    ("CREATE PROPERTY AliasLookup.alias IF NOT EXISTS STRING", "Property AliasLookup.alias"),
    ("CREATE PROPERTY AliasLookup.canonical_title IF NOT EXISTS STRING", "Property AliasLookup.canonical_title"),
    ("CREATE PROPERTY AliasLookup.type IF NOT EXISTS STRING", "Property AliasLookup.type"),
    ("CREATE PROPERTY AliasLookup.pcode IF NOT EXISTS STRING", "Property AliasLookup.pcode"),
    ("CREATE INDEX IF NOT EXISTS ON AliasLookup (alias) UNIQUE", "Index AliasLookup.alias UNIQUE"),

    ("CREATE DOCUMENT TYPE IntentAnchor IF NOT EXISTS", "Create document IntentAnchor"),
    ("CREATE PROPERTY IntentAnchor.intent IF NOT EXISTS STRING", "Property IntentAnchor.intent"),
    ("CREATE PROPERTY IntentAnchor.category IF NOT EXISTS STRING", "Property IntentAnchor.category"),
    ("CREATE PROPERTY IntentAnchor.action IF NOT EXISTS STRING", "Property IntentAnchor.action"),
    ("CREATE PROPERTY IntentAnchor.utterance IF NOT EXISTS STRING", "Property IntentAnchor.utterance"),
    ("CREATE PROPERTY IntentAnchor.embedding IF NOT EXISTS LIST OF FLOAT", "Property IntentAnchor.embedding"),
    ("CREATE PROPERTY IntentAnchor.response_template IF NOT EXISTS STRING", "Property IntentAnchor.response_template"),
    ("CREATE INDEX IF NOT EXISTS ON IntentAnchor (utterance) FULL_TEXT", "Full-text index on IntentAnchor.utterance"),
    (
        'CREATE INDEX IF NOT EXISTS ON IntentAnchor (embedding) LSM_VECTOR METADATA {"dimensions": 768, "similarity": "COSINE"}',
        "JVector HNSW index on IntentAnchor.embedding"
    ),
    ("CREATE INDEX IF NOT EXISTS ON IntentAnchor (intent) NOTUNIQUE", "Index IntentAnchor.intent"),
    ("CREATE INDEX IF NOT EXISTS ON IntentAnchor (category) NOTUNIQUE", "Index IntentAnchor.category"),

    ("CREATE DOCUMENT TYPE ClaimDispute IF NOT EXISTS", "Create document ClaimDispute"),
    ("CREATE PROPERTY ClaimDispute.event_title IF NOT EXISTS STRING", "Property ClaimDispute.event_title"),
    ("CREATE PROPERTY ClaimDispute.conflict_type IF NOT EXISTS STRING", "Property ClaimDispute.conflict_type"),
    ("CREATE PROPERTY ClaimDispute.source_a IF NOT EXISTS STRING", "Property ClaimDispute.source_a"),
    ("CREATE PROPERTY ClaimDispute.claim_a IF NOT EXISTS STRING", "Property ClaimDispute.claim_a"),
    ("CREATE PROPERTY ClaimDispute.source_b IF NOT EXISTS STRING", "Property ClaimDispute.source_b"),
    ("CREATE PROPERTY ClaimDispute.claim_b IF NOT EXISTS STRING", "Property ClaimDispute.claim_b"),
    ("CREATE PROPERTY ClaimDispute.resolution_status IF NOT EXISTS STRING", "Property ClaimDispute.resolution_status"),
    ("CREATE PROPERTY ClaimDispute.verifying_source IF NOT EXISTS STRING", "Property ClaimDispute.verifying_source"),
    ("CREATE PROPERTY ClaimDispute.timestamp IF NOT EXISTS STRING", "Property ClaimDispute.timestamp"),
    ("CREATE INDEX IF NOT EXISTS ON ClaimDispute (event_title) NOTUNIQUE", "Index ClaimDispute.event_title"),
    ("CREATE INDEX IF NOT EXISTS ON ClaimDispute (conflict_type) NOTUNIQUE", "Index ClaimDispute.conflict_type"),

    ("CREATE DOCUMENT TYPE SynthesisDelta IF NOT EXISTS", "Create document SynthesisDelta"),
    ("CREATE PROPERTY SynthesisDelta.synthesis_slug IF NOT EXISTS STRING", "Property SynthesisDelta.synthesis_slug"),
    ("CREATE PROPERTY SynthesisDelta.section_uri IF NOT EXISTS STRING", "Property SynthesisDelta.section_uri"),
    ("CREATE PROPERTY SynthesisDelta.change_type IF NOT EXISTS STRING", "Property SynthesisDelta.change_type"),
    ("CREATE PROPERTY SynthesisDelta.diff_snippet IF NOT EXISTS STRING", "Property SynthesisDelta.diff_snippet"),
    ("CREATE PROPERTY SynthesisDelta.timestamp IF NOT EXISTS STRING", "Property SynthesisDelta.timestamp"),
    ("CREATE PROPERTY SynthesisDelta.resolved IF NOT EXISTS BOOLEAN", "Property SynthesisDelta.resolved"),
    ("CREATE INDEX IF NOT EXISTS ON SynthesisDelta (synthesis_slug) NOTUNIQUE", "Index SynthesisDelta.synthesis_slug"),

    # 3. Edge Types (Micro-CoT, Causal/Temporal, Agency, Spatio-Political, Provenance & Contradiction)
    ("CREATE EDGE TYPE PROGRESSES_TO IF NOT EXISTS", "Create edge PROGRESSES_TO"),
    ("CREATE EDGE TYPE HAS_SECTION IF NOT EXISTS", "Create edge HAS_SECTION"),
    ("CREATE EDGE TYPE TAGGED_WITH IF NOT EXISTS", "Create edge TAGGED_WITH"),
    ("CREATE EDGE TYPE CITES IF NOT EXISTS", "Create edge CITES"),

    ("CREATE EDGE TYPE PRECEDES IF NOT EXISTS", "Create edge PRECEDES"),
    ("CREATE EDGE TYPE TRIGGERS IF NOT EXISTS", "Create edge TRIGGERS"),
    ("CREATE EDGE TYPE RETALIATES_FOR IF NOT EXISTS", "Create edge RETALIATES_FOR"),
    ("CREATE EDGE TYPE PART_OF_CAMPAIGN IF NOT EXISTS", "Create edge PART_OF_CAMPAIGN"),
    ("CREATE EDGE TYPE MOTIVATED_BY IF NOT EXISTS", "Create edge MOTIVATED_BY"),

    ("CREATE EDGE TYPE PERPETRATED_BY IF NOT EXISTS", "Create edge PERPETRATED_BY"),
    ("CREATE EDGE TYPE TARGETED IF NOT EXISTS", "Create edge TARGETED"),
    ("CREATE EDGE TYPE PARTICIPATED_IN IF NOT EXISTS", "Create edge PARTICIPATED_IN"),
    ("CREATE EDGE TYPE COMMANDED_BY IF NOT EXISTS", "Create edge COMMANDED_BY"),
    ("CREATE EDGE TYPE ALLIED_WITH IF NOT EXISTS", "Create edge ALLIED_WITH"),
    ("CREATE EDGE TYPE SPONSORED_BY IF NOT EXISTS", "Create edge SPONSORED_BY"),
    ("CREATE EDGE TYPE DEFECTED_TO IF NOT EXISTS", "Create edge DEFECTED_TO"),

    ("CREATE EDGE TYPE OCCURRED_AT IF NOT EXISTS", "Create edge OCCURRED_AT"),
    ("CREATE EDGE TYPE LOCATED_IN IF NOT EXISTS", "Create edge LOCATED_IN"),
    ("CREATE EDGE TYPE CONTROLS_TERRITORY IF NOT EXISTS", "Create edge CONTROLS_TERRITORY"),
    ("CREATE EDGE TYPE DISPLACES_POPULATION IF NOT EXISTS", "Create edge DISPLACES_POPULATION"),

    ("CREATE EDGE TYPE EMPIRICALLY_GROUNDS IF NOT EXISTS", "Create edge EMPIRICALLY_GROUNDS"),
    ("CREATE EDGE TYPE CORROBORATES IF NOT EXISTS", "Create edge CORROBORATES"),
    ("CREATE EDGE TYPE CONTRADICTS_CLAIM IF NOT EXISTS", "Create edge CONTRADICTS_CLAIM"),
    ("CREATE EDGE TYPE ATTRIBUTES_BLAME_TO IF NOT EXISTS", "Create edge ATTRIBUTES_BLAME_TO"),
    ("CREATE EDGE TYPE DEBUNKS IF NOT EXISTS", "Create edge DEBUNKS"),
    ("CREATE EDGE TYPE PUBLISHED_BY IF NOT EXISTS", "Create edge PUBLISHED_BY"),

    # 4. Graph Vector & Fulltext Indexes
    (
        'CREATE INDEX IF NOT EXISTS ON Section (vector) LSM_VECTOR METADATA {"dimensions": 768, "similarity": "COSINE"}',
        "Create JVector HNSW index on Section.vector"
    ),
    ("CREATE INDEX IF NOT EXISTS ON Event (title) FULL_TEXT", "Full-text index on Event.title"),
    ("CREATE INDEX IF NOT EXISTS ON Actor (title) FULL_TEXT", "Full-text index on Actor.title"),
    ("CREATE INDEX IF NOT EXISTS ON Location (title) FULL_TEXT", "Full-text index on Location.title"),
    ("CREATE INDEX IF NOT EXISTS ON Theme (title) FULL_TEXT", "Full-text index on Theme.title"),
]


def wipe_existing_types_in_db(db_name: str):
    """Queries schema:types in db_name and drops all existing Edge, Vertex, and Document types."""
    query_endpoint = f"{ARCADEDB_URL}/api/v1/query/{db_name}"
    cmd_endpoint = f"{ARCADEDB_URL}/api/v1/command/{db_name}"

    status, _, res_json = http_request(
        "POST",
        query_endpoint,
        payload={"language": "sql", "command": "SELECT name, type FROM schema:types"},
        auth=True,
        timeout=10,
    )
    if status != 200:
        return

    rows = res_json.get("result", [])
    # Drop edges first, then vertices, then documents
    edges = [r["name"] for r in rows if r.get("type") == "edge"]
    vertices = [r["name"] for r in rows if r.get("type") == "vertex"]
    docs = [r["name"] for r in rows if r.get("type") == "document"]

    for t_name in edges + vertices + docs:
        d_status, d_err, _ = http_request(
            "POST",
            cmd_endpoint,
            payload={"language": "sql", "command": f"DROP TYPE {t_name} IF EXISTS UNSAFE"},
            auth=True,
            timeout=10,
        )
        if d_status == 200:
            logger.info("  - Dropped old type '%s' from '%s'", t_name, db_name)
        else:
            logger.warning("  ! Could not drop type '%s': %s", t_name, d_err)


def ensure_database(reset: bool = False):
    """Checks if the database exists; if reset=True, drops all existing databases and types and creates a clean 'news' database."""
    try:
        r_status, _, _ = http_request("GET", f"{ARCADEDB_URL}/api/v1/ready", auth=True, timeout=5)
        if r_status not in (200, 204):
            logger.error("ArcadeDB is not ready (status %s). Is the container running?", r_status)
            sys.exit(1)

        s_status, _, s_json = http_request("GET", f"{ARCADEDB_URL}/api/v1/server", auth=True, timeout=5)
        databases = s_json.get("databases", []) if s_status == 200 else []
        logger.info("Server status=%s, reported databases=%s", s_status, databases)

        if reset:
            # Also check common legacy database names in case /api/v1/server omits them
            candidate_dbs = list(set(databases + ["knowledgedb", DATABASE]))
            for db_name in candidate_dbs:
                # Check if db exists
                ex_status, _, ex_json = http_request("GET", f"{ARCADEDB_URL}/api/v1/exists/{db_name}", auth=True, timeout=5)
                if ex_status == 200 and ex_json.get("result") is True:
                    logger.info("Clearing existing database '%s'...", db_name)
                    wipe_existing_types_in_db(db_name)
                    d_status, d_text, _ = http_request(
                        "POST",
                        f"{ARCADEDB_URL}/api/v1/server",
                        payload={"command": f"drop database {db_name}"},
                        auth=True,
                        timeout=10,
                    )
                    if d_status == 200:
                        logger.info("✓ Dropped database '%s'.", db_name)

        ex_status, _, ex_json = http_request("GET", f"{ARCADEDB_URL}/api/v1/exists/{DATABASE}", auth=True, timeout=5)
        if not (ex_status == 200 and ex_json.get("result") is True):
            logger.info("Creating clean database '%s'...", DATABASE)
            c_status, c_text, _ = http_request(
                "POST",
                f"{ARCADEDB_URL}/api/v1/server",
                payload={"command": f"create database {DATABASE}"},
                auth=True,
                timeout=10,
            )
            if c_status == 200:
                logger.info("✓ Successfully created database '%s'.", DATABASE)
            else:
                logger.warning("Database creation response: %s %s", c_status, c_text)
        else:
            logger.info("Database '%s' is ready on server.", DATABASE)
    except urllib.error.URLError as e:
        logger.error("Could not connect to ArcadeDB at %s: %s", ARCADEDB_URL, e)
        sys.exit(1)


def execute_ddl():
    """Executes the DDL schema commands."""
    endpoint = f"{ARCADEDB_URL}/api/v1/command/{DATABASE}"

    logger.info("Starting schema bootstrap for database '%s'...", DATABASE)
    success_count = 0

    for sql, description in DDL_COMMANDS:
        payload = {"language": "sql", "command": sql}
        try:
            status, err_text, _ = http_request("POST", endpoint, payload=payload, auth=True, timeout=10)
            if status == 200:
                logger.info("✓ %s", description)
                success_count += 1
            else:
                if "already exists" in err_text.lower():
                    logger.info("✓ %s (already exists)", description)
                    success_count += 1
                else:
                    logger.warning("! Failed %s: %s (Status: %s)", description, err_text, status)
        except Exception as e:
            logger.error("Error executing '%s': %s", description, e)

    logger.info("Schema bootstrap finished. Successfully applied %d/%d DDL definitions.", success_count, len(DDL_COMMANDS))


def seed_glossary_aliases_and_nodes():
    """Seeds AliasLookup records AND baseline Sudan Actor & ADM1 Location vertices from wiki/glossary.md into ArcadeDB."""
    endpoint = f"{ARCADEDB_URL}/api/v1/command/{DATABASE}"
    glossary_path = VAULT_ROOT / "wiki" / "glossary.md"
    if not glossary_path.exists():
        return

    # 1. Seed root ADM0 Location: Sudan (SD)
    http_request(
        "POST",
        endpoint,
        payload={
            "language": "sql",
            "command": (
                "UPDATE Location SET title = 'Sudan', subtype = 'country', pcode = 'SD', "
                "adm_level = 0, aliases = ['Republic of the Sudan', 'السودان', 'جمهورية السودان'], "
                "current_control = 'contested', reliability_score = 1.0, last_updated = '2026-11-01' "
                "UPSERT WHERE title = 'Sudan'"
            ),
        },
        auth=True,
        timeout=5,
    )

    content = glossary_path.read_text(encoding="utf-8")
    alias_count = 0
    actor_count = 0
    location_count = 1  # Sudan root

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|") and not line.startswith("| :---"):
            cells = [c.strip() for c in line[1:-1].split("|")]
            if len(cells) >= 4 and cells[0] not in ("Term / Primary Acronym", "UN OCHA P-Code", "Term"):
                col0 = cells[0].replace("**", "").strip().strip("`")
                canonical = re.sub(r"^\[\[|\]\]$", "", cells[1].strip())
                raw_aliases = [a.strip().strip("`") for a in cells[2].split(",") if a.strip()]
                context = cells[3].strip()
                is_location = col0.startswith("SD") and len(col0) == 4 and col0[2:].isdigit()
                node_type = "location" if is_location else "actor"
                pcode = col0 if is_location else ""

                # Seed AliasLookup entries
                all_keys = set([col0.lower(), canonical.lower()] + [a.lower() for a in raw_aliases])
                for alias_key in all_keys:
                    if not alias_key:
                        continue
                    sql = "UPDATE AliasLookup SET alias = :alias, canonical_title = :canonical, type = :type, pcode = :pcode UPSERT WHERE alias = :alias"
                    status, _, _ = http_request(
                        "POST",
                        endpoint,
                        payload={
                            "language": "sql",
                            "command": sql,
                            "params": {
                                "alias": alias_key,
                                "canonical": canonical,
                                "type": node_type,
                                "pcode": pcode,
                            },
                        },
                        auth=True,
                        timeout=5,
                    )
                    if status == 200:
                        alias_count += 1

                # Seed baseline Location or Actor vertex
                if is_location:
                    loc_sql = (
                        "UPDATE Location SET title = :title, subtype = 'state_adm1', pcode = :pcode, "
                        "adm_level = 1, capital_hub = :hub, aliases = :aliases, "
                        "reliability_score = 1.0, last_updated = '2026-11-01' "
                        "UPSERT WHERE title = :title"
                    )
                    status, _, _ = http_request(
                        "POST",
                        endpoint,
                        payload={
                            "language": "sql",
                            "command": loc_sql,
                            "params": {
                                "title": canonical,
                                "pcode": pcode,
                                "hub": context,
                                "aliases": raw_aliases,
                            },
                        },
                        auth=True,
                        timeout=5,
                    )
                    if status == 200:
                        location_count += 1
                        http_request(
                            "POST",
                            endpoint,
                            payload={
                                "language": "cypher",
                                "command": (
                                    "MATCH (s:Location {title: $state}), (c:Location {title: 'Sudan'}) "
                                    "MERGE (s)-[r:LOCATED_IN]->(c) "
                                    "SET r.warrant = s.title + ' is an ADM1 State of Sudan (' + s.pcode + ')'"
                                ),
                                "params": {"state": canonical},
                            },
                            auth=True,
                            timeout=5,
                        )
                else:
                    sub_m = re.search(r"`([a-z_]+)`", context)
                    subtype = sub_m.group(1) if sub_m else "armed_group"
                    act_sql = (
                        "UPDATE Actor SET title = :title, acronym = :acronym, subtype = :subtype, "
                        "aliases = :aliases, summary_note = :summary_note, reliability_score = 0.95, "
                        "last_updated = '2026-11-01' UPSERT WHERE title = :title"
                    )
                    status, err_body, _ = http_request(
                        "POST",
                        endpoint,
                        payload={
                            "language": "sql",
                            "command": act_sql,
                            "params": {
                                "title": canonical,
                                "acronym": col0,
                                "subtype": subtype,
                                "aliases": raw_aliases,
                                "summary_note": context,
                            },
                        },
                        auth=True,
                        timeout=5,
                    )
                    if status == 200:
                        actor_count += 1
                    else:
                        logger.warning("! Actor seed failed for '%s': %s", canonical, err_body)

    # Seed baseline command & coalition edges between core seeded actors
    baseline_edges = [
        ("Sudanese Armed Forces", "COMMANDED_BY", "Abdel Fattah al-Burhan", "General Abdel Fattah al-Burhan is Commander-in-Chief of the Sudanese Armed Forces."),
        ("Rapid Support Forces", "COMMANDED_BY", "Mohamed Hamdan Dagalo", "General Mohamed Hamdan Dagalo (Hemedti) commands the Rapid Support Forces."),
        ("Sudanese Joint Force", "ALLIED_WITH", "Sudanese Armed Forces", "The Sudanese Joint Force of Darfur armed movements fights alongside the SAF."),
        ("Sudan Liberation Movement (Minnawi)", "ALLIED_WITH", "Sudanese Joint Force", "SLM-MM is a core signatory faction of the Sudanese Joint Force."),
        ("Justice and Equality Movement", "ALLIED_WITH", "Sudanese Joint Force", "JEM is a core signatory faction of the Sudanese Joint Force."),
        ("Sudan Shield Forces", "ALLIED_WITH", "Sudanese Armed Forces", "Sudan Shield Forces (al-Kibaish) aligned with SAF in Central/Eastern Sudan."),
    ]
    for src_title, edge_type, dst_title, warrant in baseline_edges:
        http_request(
            "POST",
            endpoint,
            payload={
                "language": "cypher",
                "command": (
                    f"MATCH (a:Actor {{title: $src}}), (b:Actor {{title: $dst}}) "
                    f"MERGE (a)-[r:{edge_type}]->(b) "
                    f"SET r.warrant = $warrant"
                ),
                "params": {"src": src_title, "dst": dst_title, "warrant": warrant},
            },
            auth=True,
            timeout=5,
        )

    logger.info(
        "✓ Seeded %d AliasLookup entries, %d Actor vertices, and %d Location vertices (SD + SD01-SD18) from wiki/glossary.md.",
        alias_count,
        actor_count,
        location_count,
    )


def seed_intent_anchors():
    """Seeds baseline IntentAnchor safeguard documents into ArcadeDB."""
    endpoint = f"{ARCADEDB_URL}/api/v1/command/{DATABASE}"
    query_endpoint = f"{ARCADEDB_URL}/api/v1/query/{DATABASE}"

    catalog_path = VAULT_ROOT / "setup" / "safeguard_intent_anchors.md"
    anchors = []

    if catalog_path.exists():
        logger.info("Parsing IntentAnchor definitions from %s...", catalog_path)
        content = catalog_path.read_text(encoding="utf-8")
        intent_blocks = re.findall(r"### \x60(.*?)\x60\n(.*?)(?=\n### |\Z)", content, re.DOTALL)
        for intent, body in intent_blocks:
            cat_m = re.search(r"\- \*\*Category\*\*:\s*\x60?(.*?)\x60?\n", body)
            act_m = re.search(r"\- \*\*Action\*\*:\s*\x60?(.*?)\x60?\n", body)
            tmpl_m = re.search(r"\- \*\*Response Template\*\*:\n(.*?)(?=\n\- \*\*Utterances\*\*:)", body, re.DOTALL)

            category = cat_m.group(1).strip() if cat_m else "unknown"
            action = act_m.group(1).strip() if act_m else "PROCEED"
            template = tmpl_m.group(1).strip() if tmpl_m else ""

            utterances = re.findall(r"^\s*-\s*\"(.*?)\"", body, re.MULTILINE)
            for u in utterances:
                clean_u = u.strip()
                if clean_u:
                    anchors.append({
                        "intent": intent,
                        "category": category,
                        "action": action,
                        "utterance": clean_u,
                        "response_template": template
                    })

    try:
        q_status, _, q_json = http_request(
            "POST",
            query_endpoint,
            payload={"language": "sql", "command": "SELECT count(*) AS total FROM IntentAnchor"},
            auth=True,
            timeout=5,
        )
        existing_count = q_json.get("result", [{}])[0].get("total", 0) if q_status == 200 else 0
    except Exception:
        existing_count = 0

    if existing_count > 0:
        logger.info("IntentAnchor collection already contains %d records. Skipping re-seed.", existing_count)
        return

    logger.info("Seeding %d IntentAnchor records into ArcadeDB...", len(anchors))
    seeded = 0
    for item in anchors:
        sql = (
            "INSERT INTO IntentAnchor SET "
            "intent = :intent, category = :category, action = :action, "
            "utterance = :utterance, response_template = :response_template"
        )
        payload = {"language": "sql", "command": sql, "params": item}
        status, _, _ = http_request("POST", endpoint, payload=payload, auth=True, timeout=5)
        if status == 200:
            seeded += 1

    logger.info("✓ Seeded %d/%d IntentAnchor records.", seeded, len(anchors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap ArcadeDB Multi-Model Schema & Glossary Seeding")
    parser.add_argument("--reset", action="store_true", help="Drop all existing ArcadeDB databases/types and recreate from scratch")
    args = parser.parse_args()

    ensure_database(reset=args.reset)
    execute_ddl()
    seed_glossary_aliases_and_nodes()
    seed_intent_anchors()
