from sqlalchemy import text

"""
Sentio entity worker validation

Read-only. Safe to run against production.
An analyzed article with no article_entities rows is valid: the model may find
no supported entity in a headline. All checks in the first result set should
report PASS.
"""



ENTITY_VALIDATION_SQL = text("""
WITH checks AS (
    SELECT
        'entity_mapping_without_analyzed_flag' AS check_name,
        COUNT(*) AS issue_count
    FROM articles a
    WHERE a.entity_analyzed_at IS NULL
      AND EXISTS (
          SELECT 1
          FROM article_entities ae
          WHERE ae.article_id = a.id
      )

    UNION ALL

    SELECT
        'entity_mapping_without_article',
        COUNT(*)
    FROM article_entities ae
    LEFT JOIN articles a
      ON a.id = ae.article_id
    WHERE a.id IS NULL

    UNION ALL

    SELECT
        'entity_mapping_without_entity',
        COUNT(*)
    FROM article_entities ae
    LEFT JOIN entities e
      ON e.id = ae.entity_id
    WHERE e.id IS NULL

    UNION ALL

    SELECT
        'duplicate_canonical_entities',
        COUNT(*)
    FROM (
        SELECT
            LOWER(BTRIM(e.normalized_text)),
            LOWER(BTRIM(e.entity_type))
        FROM entities e
        GROUP BY
            LOWER(BTRIM(e.normalized_text)),
            LOWER(BTRIM(e.entity_type))
        HAVING COUNT(*) > 1
    ) duplicates

    UNION ALL

    SELECT
        'empty_entity_fields',
        COUNT(*)
    FROM entities e
    WHERE BTRIM(e.entity_text) = ''
       OR BTRIM(e.normalized_text) = ''
       OR BTRIM(e.entity_type) = ''

    UNION ALL

    SELECT
        'entity_confidence_out_of_range',
        COUNT(*)
    FROM article_entities ae
    WHERE ae.confidence_score < 0
       OR ae.confidence_score > 1

    UNION ALL

    SELECT
        'stale_pending_entities',
        COUNT(*)
    FROM articles a
    WHERE a.sentiment_analyzed_at IS NOT NULL
      AND a.entity_analyzed_at IS NULL
      AND a.fetched_at < NOW() - INTERVAL '30 minutes'

    UNION ALL

    SELECT
        'invalid_entity_timestamps',
        COUNT(*)
    FROM articles a
    WHERE a.entity_analyzed_at IS NOT NULL
      AND (
          a.entity_analyzed_at > NOW() + INTERVAL '5 minutes'
          OR a.entity_analyzed_at < a.fetched_at
      )
)
SELECT
    CASE
        WHEN issue_count = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    check_name,
    issue_count
FROM checks
ORDER BY
    CASE WHEN issue_count = 0 THEN 1 ELSE 0 END,
    check_name;
""")


# Entity worker queue and coverage during the last 24 hours.
ENTITY_QUEUE_AND_COVERAGE_SQL = text("""
SELECT
    COUNT(*) FILTER (
        WHERE a.sentiment_analyzed_at IS NOT NULL
    ) AS ready_for_entities,
    COUNT(*) FILTER (
        WHERE a.entity_analyzed_at IS NOT NULL
    ) AS analyzed,
    COUNT(*) FILTER (
        WHERE a.sentiment_analyzed_at IS NOT NULL
          AND a.entity_analyzed_at IS NULL
    ) AS pending,
    COUNT(*) FILTER (
        WHERE a.entity_analyzed_at IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM article_entities ae
              WHERE ae.article_id = a.id
          )
    ) AS analyzed_with_entities,
    COUNT(*) FILTER (
        WHERE a.entity_analyzed_at IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM article_entities ae
              WHERE ae.article_id = a.id
          )
    ) AS analyzed_without_entities
FROM articles a
WHERE a.fetched_at >= NOW() - INTERVAL '24 hours';
""")


# Recent entity type distribution.
RECENT_ENTITY_TYPE_DISTRIBUTION_SQL = text("""
SELECT
    e.entity_type,
    COUNT(*) AS mapping_count,
    COUNT(DISTINCT ae.article_id) AS article_count
FROM article_entities ae
JOIN entities e
  ON e.id = ae.entity_id
JOIN articles a
  ON a.id = ae.article_id
WHERE a.entity_analyzed_at >= NOW() - INTERVAL '24 hours'
GROUP BY e.entity_type
ORDER BY mapping_count DESC, e.entity_type;
""")


# Examples that are stuck or have a mapping/flag inconsistency.
INCOMPLETE_ENTITY_ARTICLES_SQL = text("""
SELECT
    a.id AS article_id,
    a.title,
    a.fetched_at,
    a.sentiment_analyzed_at,
    a.entity_analyzed_at,
    COUNT(ae.entity_id) AS entity_count
FROM articles a
LEFT JOIN article_entities ae
  ON ae.article_id = a.id
WHERE (
        a.entity_analyzed_at IS NULL
        AND ae.entity_id IS NOT NULL
      )
   OR (
        a.sentiment_analyzed_at IS NOT NULL
        AND a.entity_analyzed_at IS NULL
        AND a.fetched_at < NOW() - INTERVAL '30 minutes'
      )
GROUP BY
    a.id,
    a.title,
    a.fetched_at,
    a.sentiment_analyzed_at,
    a.entity_analyzed_at
ORDER BY a.fetched_at DESC
LIMIT 50;
""")
