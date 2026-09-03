from sqlalchemy import text

"""
Sentio ingestion liveness and cleanup validation

Read-only. Safe to run against production.
Retention is seven days; the validation uses an eight-day threshold to allow
for a daily cleanup schedule. All checks in the first result set should PASS.
"""

INGESTION_CLEANUP_VALIDATION_SQL = text("""

WITH checks AS (
    SELECT
        'article_without_source' AS check_name,
        COUNT(*) AS issue_count
    FROM articles a
    LEFT JOIN sources s
      ON s.id = a.source_id
    WHERE s.id IS NULL

    UNION ALL

    SELECT
        'empty_required_article_fields',
        COUNT(*)
    FROM articles a
    WHERE BTRIM(a.title) = ''
       OR BTRIM(a.link) = ''
       OR BTRIM(a.link_hash) = ''

    UNION ALL

    SELECT
        'duplicate_article_link_hashes',
        COUNT(*)
    FROM (
        SELECT a.link_hash
        FROM articles a
        GROUP BY a.link_hash
        HAVING COUNT(*) > 1
    ) duplicates

    UNION ALL

    SELECT
        'stale_articles_without_search_vector',
        COUNT(*)
    FROM articles a
    WHERE a.search_vector IS NULL
      AND a.fetched_at < NOW() - INTERVAL '30 minutes'

    UNION ALL

    SELECT
        'invalid_article_timestamps',
        COUNT(*)
    FROM articles a
    WHERE a.fetched_at > NOW() + INTERVAL '5 minutes'
       OR a.published_at > NOW() + INTERVAL '24 hours'

    UNION ALL

    SELECT
        'invalid_source_poll_interval',
        COUNT(*)
    FROM sources s
    WHERE s.poll_interval_minutes <= 0

    UNION ALL

    SELECT
        'duplicate_source_slugs',
        COUNT(*)
    FROM (
        SELECT LOWER(BTRIM(s.slug))
        FROM sources s
        GROUP BY LOWER(BTRIM(s.slug))
        HAVING COUNT(*) > 1
    ) duplicates

    UNION ALL

    SELECT
        'duplicate_source_rss_urls',
        COUNT(*)
    FROM (
        SELECT BTRIM(s.rss_url)
        FROM sources s
        GROUP BY BTRIM(s.rss_url)
        HAVING COUNT(*) > 1
    ) duplicates

    UNION ALL

    SELECT
        'stale_active_sources',
        COUNT(*)
    FROM sources s
    WHERE s.is_active
      AND NOT s.broken_rss_link
      AND (
          s.last_success_at IS NULL
          OR s.last_success_at < NOW() - (
              GREATEST(s.poll_interval_minutes * 3, 30)
              * INTERVAL '1 minute'
          )
      )

    UNION ALL

    SELECT
        'active_sources_with_current_error',
        COUNT(*)
    FROM sources s
    WHERE s.is_active
      AND NOT s.broken_rss_link
      AND s.last_error_at IS NOT NULL
      AND (
          s.last_success_at IS NULL
          OR s.last_error_at > s.last_success_at
      )

    UNION ALL

    SELECT
        'articles_past_retention_grace',
        COUNT(*)
    FROM articles a
    WHERE COALESCE(a.published_at, a.fetched_at)
          < NOW() - INTERVAL '8 days'

    UNION ALL

    SELECT
        'empty_clusters_after_cleanup',
        COUNT(*)
    FROM article_clusters ac
    WHERE NOT EXISTS (
        SELECT 1
        FROM article_cluster_members acm
        WHERE acm.cluster_id = ac.id
    )

    UNION ALL

    SELECT
        'cluster_time_range_mismatch_after_cleanup',
        COUNT(*)
    FROM (
        SELECT ac.id
        FROM article_clusters ac
        JOIN article_cluster_members acm
          ON acm.cluster_id = ac.id
        JOIN articles a
          ON a.id = acm.article_id
        GROUP BY
            ac.id,
            ac.first_seen_at,
            ac.last_seen_at
        HAVING ac.first_seen_at IS DISTINCT FROM MIN(a.published_at)
            OR ac.last_seen_at IS DISTINCT FROM MAX(a.published_at)
    ) mismatches
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


# Ingestion volume and active source status.
INGESTION_VOLUME_AND_SOURCE_STATUS_SQL = text("""
SELECT
    COUNT(*) FILTER (
        WHERE a.fetched_at >= NOW() - INTERVAL '1 hour'
    ) AS articles_fetched_1h,
    COUNT(*) FILTER (
        WHERE a.fetched_at >= NOW() - INTERVAL '24 hours'
    ) AS articles_fetched_24h,
    (
        SELECT COUNT(*)
        FROM sources s
        WHERE s.is_active
          AND NOT s.broken_rss_link
    ) AS active_sources,
    (
        SELECT COUNT(*)
        FROM sources s
        WHERE s.is_active
          AND NOT s.broken_rss_link
          AND s.last_success_at >= NOW() - (
              GREATEST(s.poll_interval_minutes * 3, 30)
              * INTERVAL '1 minute'
          )
    ) AS recently_successful_sources
FROM articles a;
""")


# Active sources that are stale or whose latest outcome is an error.
UNHEALTHY_ACTIVE_SOURCES_SQL = text("""
SELECT
    s.id AS source_id,
    s.name,
    s.poll_interval_minutes,
    s.last_fetched_at,
    s.last_success_at,
    s.last_error_at,
    s.last_error_message
FROM sources s
WHERE s.is_active
  AND NOT s.broken_rss_link
  AND (
      s.last_success_at IS NULL
      OR s.last_success_at < NOW() - (
          GREATEST(s.poll_interval_minutes * 3, 30)
          * INTERVAL '1 minute'
      )
      OR (
          s.last_error_at IS NOT NULL
          AND (
              s.last_success_at IS NULL
              OR s.last_error_at > s.last_success_at
          )
      )
  )
ORDER BY s.last_success_at NULLS FIRST, s.name
LIMIT 50;
""")

# Articles that remain beyond the retention period plus one-day grace.
ARTICLES_PAST_RETENTION_GRACE_SQL = text("""
SELECT
    a.id AS article_id,
    a.title,
    a.published_at,
    a.fetched_at,
    NOW() - COALESCE(a.published_at, a.fetched_at) AS age
FROM articles a
WHERE COALESCE(a.published_at, a.fetched_at)
      < NOW() - INTERVAL '8 days'
ORDER BY COALESCE(a.published_at, a.fetched_at)
LIMIT 50;
""")
