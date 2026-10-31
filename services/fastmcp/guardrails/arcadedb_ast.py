"""
services/fastmcp/guardrails/arcadedb_ast.py
AST Validation, Sandboxing, and Query Sanitization Engine for ArcadeDB.
Enforces read-only semantics, rejects ANSI SQL joins, injects limits, and auto-repairs Cypher idioms.
"""

import re
from typing import List


class DialectSecurityError(ValueError):
    """Raised when an unauthorized mutation or administrative command is detected."""
    pass


class DialectSyntaxError(ValueError):
    """Raised when an invalid dialect construct (e.g. ANSI SQL JOIN) is detected."""
    pass


class ArcadeDBASTGuard:
    """Security validator and AST sanitizer for ArcadeDB SQL and OpenCypher queries."""

    DISALLOWED_MUTATIONS = [
        "CREATE", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", 
        "GRANT", "REVOKE", "SET", "MERGE", "REMOVE"
    ]

    @classmethod
    def strip_code_fences(cls, query: str) -> str:
        """Removes markdown code fences and cleans trailing whitespace/semicolons."""
        clean = re.sub(r"```(sql|cypher)?", "", query, flags=re.IGNORECASE)
        clean = clean.replace("```", "").strip().rstrip(";")
        return clean

    @classmethod
    def assert_read_only(cls, query: str) -> None:
        """Asserts that no mutating DDL/DML statements exist in the query."""
        upper = query.upper()
        for verb in cls.DISALLOWED_MUTATIONS:
            # Check for word boundary
            if re.search(rf"\b{verb}\b", upper):
                raise DialectSecurityError(
                    f"Security Restriction: Mutating or administrative operation '{verb}' is prohibited in analytical queries."
                )

    @classmethod
    def sanitize_sql(cls, sql_query: str) -> str:
        """
        Enforces ArcadeDB Multi-Model SQL invariants:
        1. Strips markdown fences.
        2. Asserts read-only.
        3. Rejects ANSI SQL JOINs with educational guidance.
        4. Injects default LIMIT 50 if missing.
        """
        clean = cls.strip_code_fences(sql_query)
        cls.assert_read_only(clean)
        upper = clean.upper()

        # Reject ANSI Joins
        join_patterns = [
            r"\bINNER\s+JOIN\b",
            r"\bLEFT\s+JOIN\b",
            r"\bRIGHT\s+JOIN\b",
            r"\bFULL\s+JOIN\b",
            r"\bCROSS\s+JOIN\b",
            r"\bJOIN\b",
        ]
        for pat in join_patterns:
            if re.search(pat, upper):
                raise DialectSyntaxError(
                    "Dialect Error: ANSI SQL 'JOIN' is not supported in ArcadeDB. "
                    "Use graph traversal operators out('EdgeType'), in('EdgeType'), expand(), or MATCH patterns instead."
                )

        # Inject default safety limit if missing.
        # Queries must end with LIMIT clause to prevent ArcadeDB REST engine from appending its own limit.
        if not re.search(r"\bLIMIT\s+\d+\b", upper):
            clean += " LIMIT 50"

        return clean

    @classmethod
    def repair_cypher_shadowing(cls, cypher_query: str) -> str:
        """
        Repairs alias shadowing where a return alias matches a vertex or edge variable name.
        Example: 'RETURN remedy.title AS remedy, remedy.pagerank AS pagerank' when variable is 'remedy:Concept'.
        In ArcadeDB OpenCypher, aliasing a property to the vertex name converts the identifier into a string,
        causing subsequent references (e.g. 'remedy.pagerank') to fail with:
        'Cannot access property on String value'.
        Rewrites 'remedy.title AS remedy' to 'remedy.title AS remedy_title'.
        """
        # 1. Identify declared variables in MATCH / OPTIONAL MATCH / WITH
        declared_vars = set(
            re.findall(
                r'(?:[([]\s*|\bshortestPath\(\s*[(])([a-zA-Z0-9_]+)\s*(?::|[)\]]|\s+[a-zA-Z0-9_])',
                cypher_query,
            )
        )
        keywords = {'MATCH', 'WHERE', 'RETURN', 'WITH', 'OPTIONAL', 'DISTINCT', 'AND', 'OR', 'NOT'}
        declared_vars = {v for v in declared_vars if v.upper() not in keywords}

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            prop = match.group(2)
            other_expr = match.group(3)
            alias = match.group(4)
            # If alias shadows a declared variable or is direct self-aliasing (<var>.<prop> AS <var>)
            if (alias in declared_vars) or (var_name and alias.lower() == var_name.lower()):
                if prop:
                    return f"{var_name}.{prop} AS {alias}_{prop}"
                elif other_expr:
                    return f"{other_expr} AS {alias}_val"
            return match.group(0)

        pattern = r'\b(?:([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)|([a-zA-Z0-9_()]+))\s+AS\s+([a-zA-Z0-9_]+)\b'
        repaired = re.sub(pattern, replacer, cypher_query, flags=re.IGNORECASE)
        return repaired

    @classmethod
    def repair_cypher_relationship_binding(cls, cypher_query: str) -> str:
        """
        Auto-binds relationship variable 'r' if r.warrant or r.property is referenced in RETURN/WHERE,
        but the relationship pattern was anonymous: -[:REL]-> becomes -[r:REL]->.
        """
        if re.search(r"\br\.", cypher_query) and not re.search(r"\[\s*r\s*:", cypher_query):
            # Bind outgoing
            cypher_query = re.sub(r"-\[:([A-Za-z0-9_]+)\]->", r"-[r:\1]->", cypher_query, count=1)
            # Bind undirected
            cypher_query = re.sub(r"-\[:([A-Za-z0-9_]+)\]-", r"-[r:\1]-", cypher_query, count=1)
            # Bind incoming
            cypher_query = re.sub(r"<-\[:([A-Za-z0-9_]+)\]-", r"<-[r:\1]-", cypher_query, count=1)
        return cypher_query

    @classmethod
    def repair_cypher_list_contains(cls, cypher_query: str) -> str:
        """
        Converts invalid 'node.normalized_aliases CONTAINS ...' list comparison
        into valid '... IN node.normalized_aliases'.
        """
        repaired = re.sub(
            r"([a-zA-Z0-9_]+)\.normalized_aliases\s+CONTAINS\s+((?:'[^']*'|\"[^\"]*\"))",
            r"toLower(\2) IN \1.normalized_aliases",
            cypher_query,
            flags=re.IGNORECASE,
        )
        return repaired

    @classmethod
    def sanitize_cypher(cls, cypher_query: str) -> str:
        """
        Enforces OpenCypher 25 invariants:
        1. Strips markdown fences.
        2. Asserts read-only.
        3. Repairs alias shadowing.
        4. Auto-binds relationship variable if referenced.
        5. Repairs list comparison syntax.
        """
        clean = cls.strip_code_fences(cypher_query)
        cls.assert_read_only(clean)

        clean = cls.repair_cypher_shadowing(clean)
        clean = cls.repair_cypher_relationship_binding(clean)
        clean = cls.repair_cypher_list_contains(clean)

        return clean

    @classmethod
    def validate_and_sanitize(cls, query: str, dialect: str) -> str:
        """Universal validation and sanitization entry point."""
        d = dialect.lower()
        if d == "sql":
            return cls.sanitize_sql(query)
        elif d == "cypher":
            return cls.sanitize_cypher(query)
        else:
            # Auto-detect dialect based on first token
            first_token = query.strip().split()[0].upper() if query.strip().split() else ""
            if first_token in ["SELECT", "FROM"]:
                return cls.sanitize_sql(query)
            return cls.sanitize_cypher(query)
