---
title: "GDELT BigQuery Ingestion Pipeline: Retrieval & Trafilatura Extraction"
status: "done"
completed_at: 2026-11-01
deliverable: "[[_input/drafts/GDELT BigQuery Ingestion and Trafilatura Article Extraction Plan.md]]"
---

I want to use Google BigQuery with the GDELT data to identify relevant news article.

I want to start with the following query:
```sql
WITH verified_publishers AS (

SELECT domain, tier FROM UNNEST([

-- 1. Global Wire Services & Major Fact-Checking Outlets

STRUCT('reuters.com' AS domain, 'Tier 1 Wire' AS tier),

STRUCT('apnews.com', 'Tier 1 Wire'),

STRUCT('afp.com', 'Tier 1 Wire'),

STRUCT('bbc.com', 'Tier 1 International'),

STRUCT('aljazeera.com', 'Tier 1 International'),

STRUCT('theguardian.com', 'Tier 1 International'),

STRUCT('dw.com', 'Tier 1 International'),

STRUCT('france24.com', 'Tier 1 International'),

-- 2. Respected Sudan-Focused & Regional Media

STRUCT('dabangasudan.org', 'Regional / Local Field'),

STRUCT('sudantribune.com', 'Regional / Local Field'),

STRUCT('ayinp.net', 'Regional / Local Field'),

STRUCT('sudanspost.com', 'Regional / Local Field')

])

)

SELECT

PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(g.DATE AS STRING)) AS published_at,

vp.tier,

g.SourceCommonName AS publisher,

g.DocumentIdentifier AS article_url,

-- Extracts and displays ONLY Sudan-specific locations (strips Washington, Cairo, Geneva, etc.)

(

SELECT STRING_AGG(DISTINCT REGEXP_EXTRACT(loc, r'^[1-5]#([^#]+)#'), '; ')

FROM UNNEST(SPLIT(g.V2Locations, ';')) AS loc

WHERE REGEXP_CONTAINS(loc, r'^[1-5]#[^#]+#SU#')

) AS sudan_locations,

-- Dynamic Classification: War Economy, Economy & Livelihoods, or Security / Conflict

CASE

WHEN (

g.V2Themes LIKE '%ECON%' OR g.V2Themes LIKE '%POVERTY%' OR g.V2Themes LIKE '%AGRICULTURE%'

OR REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),

r'(econom|inflat|currenc|pound|sdg|exchange[-_]?rate|bank|food[-_]?price|cash|remittanc|livelihood|gold|trade|salary|salaries)')

) AND (

g.V2Themes LIKE '%ARMEDCONFLICT%' OR g.V2Themes LIKE '%WAR%' OR g.V2Themes LIKE '%MILITARY%' OR g.V2Themes LIKE '%AIRSTRIKE%'

OR REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),

r'(rsf|rapid[-_]?support|saf|burhan|hemedti|dagalo|clash|bombardment|drone|shelling|airstrike)')

) THEN 'War Economy / Intersect'

WHEN (

g.V2Themes LIKE '%ECON%' OR g.V2Themes LIKE '%POVERTY%' OR g.V2Themes LIKE '%AGRICULTURE%'

OR REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),

r'(econom|inflat|currenc|pound|sdg|exchange[-_]?rate|bank|food[-_]?price|cash|remittanc|livelihood|gold|trade|salary|salaries)')

) THEN 'Economy & Livelihoods'

ELSE 'Security / Conflict'

END AS topic_focus,

-- Sentiment score (-10 to +10)

CAST(SPLIT(g.V2Tone, ',')[OFFSET(0)] AS FLOAT64) AS tone_score,

g.V2Themes

FROM

`gdelt-bq.gdeltv2.gkg_partitioned` g

JOIN

verified_publishers vp

ON

g.SourceCommonName = vp.domain

WHERE

-- 1. Date Partition: Scans strictly yesterday's 24-hour shard

g._PARTITIONDATE = DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)

-- 2. Strict Sudan Geographic Requirement:

-- Requires at least one location block whose 3rd field is FIPS code 'SU'

AND REGEXP_CONTAINS(g.V2Locations, r'(^|;)[1-5]#[^#]+#SU#')

-- 3. Geographic & Entity Exclusions:

-- Exclude South Sudan (FIPS 'OD')

AND g.V2Locations NOT LIKE '%#OD#%'

AND NOT REGEXP_CONTAINS(LOWER(g.DocumentIdentifier), r'south[-_]?sudan')

-- Exclude Iraqi Prime Minister Al-Sudani false positives

AND NOT REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Persons, ''))), r'al[-_ ]?sudani')

-- 4. Thematic Filter: Conflict OR Economic Crisis

AND (

g.V2Themes LIKE '%ARMEDCONFLICT%'

OR g.V2Themes LIKE '%WAR%'

OR g.V2Themes LIKE '%MILITARY%'

OR g.V2Themes LIKE '%AIRSTRIKE%'

OR g.V2Themes LIKE '%DRONE%'

OR g.V2Themes LIKE '%DISPLACEMENT%'

OR g.V2Themes LIKE '%HUMAN_RIGHTS_ABUSES%'

OR g.V2Themes LIKE '%ECON_%'

OR g.V2Themes LIKE '%ECONOMY%'

OR g.V2Themes LIKE '%POVERTY%'

OR g.V2Themes LIKE '%AGRICULTURE%'

OR g.V2Themes LIKE '%UNGP_FORECAST_FAMINE%'

OR g.V2Themes LIKE '%WB_470_MACROECONOMIC_VULNERABILITY%'

OR g.V2Themes LIKE '%WB_530_FINANCIAL_SECTOR_DEVELOPMENT%'

OR REGEXP_CONTAINS(

LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),

r'(rsf|rapid[-_]?support|saf|burhan|hemedti|dagalo|clash|bombardment|drone|shelling|airstrike|ceasefire|paramilitary|darfur|kordofan|gezira|el[-_]?fasher|econom|inflat|currenc|exchange[-_]?rate|sudanese[-_]?pound|sdg|bank|banking|cash[-_]?crisis|remittanc|food[-_]?price|famine|livelihood|gold[-_]?mining|gold[-_]?smuggling|wages|salary|salaries)'

)

)

ORDER BY

published_at DESC

LIMIT 150;
```

Task1: 
1. Create a python script that retrieves the data and saves the output in a JSON in a new folder "/root/news" in.
2. Create a python script that uses the URL from the news JSON to retrieve the articles using Trafilatura and save it into /raw/articles
3. Add research if required

Deliverables:
Create an implementation plan, save in /drafts
