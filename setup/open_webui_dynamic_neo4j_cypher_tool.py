"""
title: Dynamic Neo4j Cypher & GDS Generator (Text2Cypher)
author: Knowledge Lab
version: 2.6.0
requirements: neo4j, requests
description: Translates natural language questions or direct Cypher queries into executable Neo4j Cypher and Graph Data Science (GDS) queries against the ki knowledge graph. Supports shortest epistemic conceptual paths, Dual-Flow Chain of Thought (solutions, mechanisms, traps, and step transitions), Entity Agency handshakes, GDS PageRank authority ranking, Louvain thematic clustering, frontmatter tag filtering, and taxonomy alias/acronym matching.
"""

import os
import json
import re
from pydantic import BaseModel, Field
import requests
from neo4j import GraphDatabase


class Tools:
    class Valves(BaseModel):
        neo4j_uri: str = Field(
            default=os.getenv("NEO4J_URI", "bolt://neo4j-ki:7687"),
            description="Bolt connection URI to Neo4j container on wiki-net or Aura cloud",
        )
        neo4j_user: str = Field(
            default=os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j")),
            description="Neo4j database username",
        )
        neo4j_password: str = Field(
            default=os.getenv("NEO4J_PASSWORD", "password"),
            description="Neo4j database password",
        )
        ollama_url: str = Field(
            default="http://host.containers.internal:11434/api/generate",
            description="Local Ollama endpoint for Cypher translation",
        )
        llm_model: str = Field(
            default="llama3.1-fast",
            description="Model used for Text-to-Cypher generation",
        )

    def __init__(self):
        self.valves = self.Valves()

    def generate_and_run_cypher(self, question: str) -> str:
        """
        Queries the Neo4j knowledge graph using either a natural language question OR a direct Cypher query, executes it, and returns results in Markdown.
        ALWAYS invoke this tool whenever you need to:
        - Query prescriptive solutions, mitigations, countermeasures, or architectural fixes for any problem, trap, or dilemma (traverses [:REMEDIES_DILEMMA])
        - Query what dilemmas or problems a given solution mitigates or resolves
        - Query underlying cognitive mechanisms or theoretical foundations (traverses [:EXTENDS_THEORY])
        - Query failure modes, traps, or pathologies precipitated by a concept (traverses [:PRECIPITATES])
        - Query sequential argument steps or cognitive arcs inside a note (traverses [:PROGRESSES_TO])
        - Look up specific concepts, entities, or authors by title, German umlauts, French accents, acronyms, or aliases
        - Retrieve most foundational or highest-authority concepts (ranked by GDS PageRank)
        - Find notes tagged with specific topics (e.g. 'instructional-design', 'cognitive-offloading')
        - Find citations, shortest learning paths, or Louvain communities between notes
        :param question: A natural language inquiry (e.g. "What remedies solve Cognitive Surrender?") OR a direct Cypher query starting with MATCH.
        :return: Executed Cypher query and formatted Markdown results table.
        """
        clean_q = re.sub(r"```(cypher)?", "", question).replace("```", "").strip()
        first_token = clean_q.split()[0].upper() if clean_q.split() else ""
        is_direct_cypher = first_token in ["MATCH", "OPTIONAL", "CALL", "WITH", "UNWIND"]

        if is_direct_cypher:
            cypher = clean_q
        else:
            schema_context = """
            You are an expert Neo4j Cypher generator for an Obsidian Personal Knowledge Graph indexed by ki with Graph Data Science (GDS) metrics, Dual-Flow Chain of Thought (CoT), and taxonomy alias matching.

            NODE LABELS & PROPERTIES:
            - (:Document) with sub-labels (:Concept), (:Entity), (:Source), (:Synthesis):
              - title: Canonical title string (e.g. 'Productive Cognitive Friction', 'Cognitive Surrender', 'Stephan Tränkler').
              - name: Filename string (e.g. 'Cognitive Surrender.md').
              - type: 'concept', 'entity', 'source', or 'synthesis'.
              - aliases: List of human-readable aliases.
              - normalized_aliases: List of lowercase search tokens (umlauts ä/ö/ü -> ae/oe/ue, accents normalized).
              - acronyms: List of uppercase acronyms (e.g. ['RAG', 'PF', 'ADDIE', 'SAM']).
              - reliability_score: Float between 0.0 and 1.0.
              - gds_pagerank: Float network authority (higher = more foundational, e.g. > 1.5).
              - gds_community: Integer thematic cluster ID.
              - gds_betweenness: Float bridge score.

            - (:Tag):
              - name: Lowercase tag name in kebab-case (e.g. 'instructional-design', 'cognitive-offloading').

            - (:Section) with epistemic sub-labels:
              - Epistemic labels: (:Summary) [lead Definitional Anchor callout], (:CoreThesis) [section 1 Core Thesis], (:DefinitionalAnchor), (:MechanisticDeepen), (:ManifestationTrap), (:PrescriptiveSolution), (:EmpiricalBoundary), (:SynthesisCatalog), (:DilemmaProblem)
              - displayName: Section heading string (e.g. '4. Prescriptive Mitigations & Counter-Architectures').
              - headingLevel: Integer (1 to 6).
              - content: Markdown section text.
              - step_type: 'DEFINITIONAL_ANCHOR', 'CORE_THESIS', 'MECHANISTIC_DEEPEN', 'MANIFESTATION_TRAP', 'PRESCRIPTIVE_SOLUTION', 'EMPIRICAL_BOUNDARY', 'SYNTHESIS_CATALOG'.

            RELATIONSHIPS:
            - Dual-Flow Chain of Thought (CoT):
              - (:Concept)-[r:REMEDIES_DILEMMA]->(:Concept)
                Direction: (problem)-[r:REMEDIES_DILEMMA]->(solution). A dilemma or failure mode points to its prescriptive solution/safeguard.
                Properties on r: r.warrant (string explanation), r.weight (integer).
              - (:Concept)-[r:EXTENDS_THEORY]->(:Concept)
                Direction: (concept)-[r:EXTENDS_THEORY]->(foundational_theory).
                Properties on r: r.warrant (string), r.weight (integer).
              - (:Concept)-[r:PRECIPITATES]->(:Concept)
                Direction: (concept)-[r:PRECIPITATES]->(trap_or_failure_mode).
                Properties on r: r.warrant (string), r.weight (integer).
              - (:Source)-[r:EMPIRICALLY_GROUNDS]->(:Concept)
                Properties on r: r.warrant (string), r.weight (integer).
              - (:Section)-[r:PROGRESSES_TO]->(:Section)
                Properties on r: r.transition_type (string), r.warrant (string).

            - Entity Agency (Macro-CoT):
              - (:Entity)-[r:ORIGINATES_THEORY]->(:Concept)
              - (:Entity)-[r:CHAMPIONS_SOLUTION]->(:Concept)
              - (:Entity)-[r:CRITIQUES_PARADIGM]->(:Concept)
              - (:Entity)-[r:OPERATIONALIZES]->(:Concept)
              - (:Entity)-[r:AFFILIATED_WITH]->(:Entity)
              - (:Entity)-[r:INTELLECTUAL_LINEAGE]->(:Entity)

            - Structural:
              - (:Document)-[:TAGGED_WITH]->(:Tag)
              - (:Document)-[:CITES]->(:Document)
              - (:Document)-[:HAS*1..3]->(:Section)

            SYNTAX & OPERATOR RULES:
            1. NEVER write data types or property definitions like {warrant: STRING} in MATCH patterns.
            2. ALWAYS bind the relationship variable r (e.g. `-[r:REMEDIES_DILEMMA]->`) if you reference r.warrant in RETURN.
            3. CRITICAL: `normalized_aliases` is a LIST of strings, NOT a single string.
               NEVER write: `node.normalized_aliases CONTAINS 'keyword'` (which produces NULL).
               ALWAYS write: `toLower('keyword') IN node.normalized_aliases` OR `toLower(node.title) CONTAINS toLower('keyword')`.
            4. ONLY generate READ-ONLY queries (MATCH, RETURN, WHERE, WITH, ORDER BY, LIMIT). Never generate CREATE, MERGE, DELETE, or SET.
            5. Return ONLY the raw Cypher query. No explanations, no markdown fences.
            6. SHORTEST PATH & LEARNING TRAJECTORY RULE:
               When finding paths, bridges, or sequences between two concepts or entities, ALWAYS use `shortestPath()` with the semantic relationship whitelist:
               `[:REMEDIES_DILEMMA|EXTENDS_THEORY|PRECIPITATES|ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM|OPERATIONALIZES|EMPIRICALLY_GROUNDS|CITES*..8]`
               Anchor endpoints to `(:Concept)` or `(:Entity)` and return `[n IN nodes(p) | coalesce(n.title, n.displayName)] AS ConceptualPath`, `[r IN relationships(p) | type(r)] AS RelationshipTypes`, and `length(p) AS PathLength`.

            FEW-SHOT EXAMPLES:
            - Find shortest learning or conceptual path between concept X and concept Y:
              MATCH (start:Concept), (target:Concept)
              WHERE (toLower(start.title) = toLower('prompt dilution') OR toLower('prompt dilution') IN start.normalized_aliases)
                AND (toLower(target.title) = toLower('addie') OR toLower('addie') IN target.normalized_aliases)
              MATCH p = shortestPath((start)-[:REMEDIES_DILEMMA|EXTENDS_THEORY|PRECIPITATES|ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM|OPERATIONALIZES|EMPIRICALLY_GROUNDS|CITES*..8]-(target))
              RETURN [n IN nodes(p) | coalesce(n.title, n.displayName)] AS ConceptualPath,
                     [r IN relationships(p) | type(r)] AS RelationshipTypes,
                     length(p) AS PathLength

            - Find all shortest conceptual paths between X and Y:
              MATCH (start:Concept), (target:Concept)
              WHERE (toLower(start.title) = toLower('synthetic fluency') OR toLower('synthetic fluency') IN start.normalized_aliases)
                AND (toLower(target.title) = toLower('single-query hybrid retrieval') OR toLower('single-query hybrid retrieval') IN target.normalized_aliases)
              MATCH p = allShortestPaths((start)-[:REMEDIES_DILEMMA|EXTENDS_THEORY|PRECIPITATES|ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM|OPERATIONALIZES|EMPIRICALLY_GROUNDS|CITES*..8]-(target))
              RETURN [n IN nodes(p) | coalesce(n.title, n.displayName)] AS ConceptualPath,
                     [r IN relationships(p) | type(r)] AS RelationshipTypes,
                     length(p) AS PathLength
              LIMIT 5

            - Query solutions/remedies for problem/dilemma X:
              MATCH (problem:Concept)-[r:REMEDIES_DILEMMA]->(solution:Concept)
              WHERE toLower(problem.title) CONTAINS toLower('keyword')
                 OR toLower('keyword') IN problem.normalized_aliases
              RETURN problem.title AS Problem, solution.title AS RecommendedSolution, r.warrant AS WhyItWorks, solution.reliability_score AS Confidence
              ORDER BY solution.reliability_score DESC
              LIMIT 10

            - Query what problem/dilemma a solution Y fixes:
              MATCH (problem:Concept)-[r:REMEDIES_DILEMMA]->(solution:Concept)
              WHERE toLower(solution.title) CONTAINS toLower('keyword')
                 OR toLower('keyword') IN solution.normalized_aliases
              RETURN solution.title AS Solution, problem.title AS RemediedProblem, r.warrant AS WhyItWorks
              LIMIT 10

            - Query causal mechanisms and theoretical foundations for X:
              MATCH (concept:Concept)-[r:EXTENDS_THEORY]->(theory:Concept)
              WHERE toLower(concept.title) CONTAINS toLower('keyword')
                 OR toLower('keyword') IN concept.normalized_aliases
              RETURN concept.title AS Concept, theory.title AS FoundationalTheory, r.warrant AS Connection
              LIMIT 10

            - Query failure modes or traps precipitated by X:
              MATCH (concept:Concept)-[r:PRECIPITATES]->(trap:Concept)
              WHERE toLower(concept.title) CONTAINS toLower('keyword')
                 OR toLower('keyword') IN concept.normalized_aliases
              RETURN concept.title AS Concept, trap.title AS ResultingTrap, r.warrant AS Mechanism
              LIMIT 10

            - Query internal argument steps / cognitive flow in note X:
              MATCH (d:Document)-[:HAS*1..3]->(s1:CognitiveStep)-[r:PROGRESSES_TO]->(s2:CognitiveStep)
              WHERE toLower(d.title) CONTAINS toLower('keyword')
                 OR toLower('keyword') IN d.normalized_aliases
              RETURN s1.displayName AS FromStep, r.transition_type AS Transition, r.warrant AS Warrant, s2.displayName AS ToStep
              LIMIT 15

            - Query core/foundational concepts in a topic:
              MATCH (c:Concept)-[:TAGGED_WITH]->(t:Tag)
              WHERE replace(toLower(t.name), '-', ' ') CONTAINS toLower('keyword')
              RETURN c.title AS Concept, round(c.gds_pagerank, 2) AS PageRank, c.gds_community AS Community
              ORDER BY c.gds_pagerank DESC
              LIMIT 10
            """

            prompt = f"{schema_context}\n\nUser Question: {question}\nCypher:"

            try:
                res = requests.post(
                    self.valves.ollama_url,
                    json={
                        "model": self.valves.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.0},
                    },
                    timeout=60,
                )
                raw_cypher = res.json().get("response", "").strip()
                cypher = raw_cypher
            except Exception as e:
                return f"Failed to generate Cypher query via LLM: {str(e)}"

        # 2. Automated Cypher Sanitizer & Repair
        cypher = re.sub(r"```(cypher)?", "", cypher).replace("```", "").strip()
        # Strip accidental type annotations inside relationship patterns (e.g. {warrant: STRING, weight: INTEGER})
        cypher = re.sub(r"-\[([a-zA-Z0-9_:]*)\s*\{[^}]*\}\]->", r"-[\1]->", cypher)
        cypher = re.sub(r"-\[([a-zA-Z0-9_:]*)\s*\{[^}]*\}\]-", r"-[\1]-", cypher)
        # If r. is referenced in RETURN/WHERE/ORDER BY but [r: was omitted in pattern, auto-bind r
        if re.search(r"\br\.", cypher) and not re.search(r"\[\s*r\s*:", cypher):
            cypher = re.sub(r"-\[:([A-Za-z0-9_]+)\]->", r"-[r:\1]->", cypher, count=1)
            cypher = re.sub(r"-\[:([A-Za-z0-9_]+)\]-", r"-[r:\1]-", cypher, count=1)
            cypher = re.sub(r"<-\[:([A-Za-z0-9_]+)\]-", r"<-[r:\1]-", cypher, count=1)

        # Fix invalid 'normalized_aliases CONTAINS ...' list comparison into valid '... IN normalized_aliases'
        cypher = re.sub(
            r"([a-zA-Z0-9_]+)\.normalized_aliases\s+CONTAINS\s+((?:'[^']*'|\"[^\"]*\"))",
            r"toLower(\2) IN \1.normalized_aliases",
            cypher,
            flags=re.IGNORECASE,
        )

        # 3. Security Guardrail: Enforce Read-Only Operations
        disallowed = ["CREATE", "DELETE", "SET", "MERGE", "DROP", "ALTER", "REMOVE"]
        if any(re.search(rf"\b{word}\b", cypher, re.IGNORECASE) for word in disallowed):
            return f"Security Guardrail Triggered: Disallowed write operation detected in generated Cypher: `{cypher}`"

        # 4. Execute Cypher against Neo4j Container
        driver = GraphDatabase.driver(
            self.valves.neo4j_uri,
            auth=(self.valves.neo4j_user, self.valves.neo4j_password),
        )

        try:
            with driver.session() as session:
                results = session.run(cypher)
                records = [record.data() for record in results]

                if not records:
                    return f"**Executed Cypher:**\n```cypher\n{cypher}\n```\n*No records matched this query in the knowledge graph.*"

                headers = list(records[0].keys())
                table = "| " + " | ".join(headers) + " |\n"
                table += "| " + " | ".join(["---"] * len(headers)) + " |\n"

                for row in records[:25]:
                    formatted_row = []
                    for h in headers:
                        val = str(row[h]).replace("|", "\\|")
                        if val.endswith(".md"):
                            val = f"[[{val[:-3]}]]"
                        formatted_row.append(val)
                    table += "| " + " | ".join(formatted_row) + " |\n"

                return f"**Executed Cypher:**\n```cypher\n{cypher}\n```\n\n**Query Results:**\n\n{table}"

        except Exception as e:
            return f"**Error executing Cypher:** `{str(e)}`\n**Generated Cypher:**\n```cypher\n{cypher}\n```"
        finally:
            driver.close()
