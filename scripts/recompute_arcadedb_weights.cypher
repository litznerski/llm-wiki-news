// scripts/recompute_arcadedb_weights.cypher
// In-engine Cypher weight propagation & Graph OLAP re-calculation

// 1. Propagate section weights to all Toulmin containment edges
MATCH (c:Concept)-[e:HAS_GROUNDS|HAS_WARRANT|HAS_CLAIM|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_BACKING]->(s:Section)
WHERE s.weight IS NOT NULL
SET e.weight = s.weight;

// 2. Apply negative signed weight to rebuttal attack edges
MATCH (c:Concept)-[e:HAS_REBUTTAL]->(s:Section)
WHERE s.weight IS NOT NULL
SET e.signed_weight = -1.0 * s.weight;

// 3. In-engine Graph OLAP PageRank using updated Toulmin weights
CALL algo.pagerank({dampingFactor: 0.85, maxIterations: 20, weightProperty: 'weight'})
YIELD node, score
WITH toString(node) AS rid_str, score
MATCH (n) WHERE elementId(n) = rid_str
SET n.pagerank = score;
