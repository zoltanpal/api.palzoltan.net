from sqlalchemy import text


# Sentio clustering diagnostics

# Read-only. Run this when sentio_health_check.sql reports a clustering failure.
# Each section returns at most 50 examples.


# Clustering worker queue and coverage during the last 24 hours.
CLUSTERING_QUEUE_AND_COVERAGE_SQL = text("""
SELECT
    COUNT(*) FILTER (
        WHERE a.sentiment_analyzed_at IS NOT NULL
          AND a.entity_analyzed_at IS NOT NULL
    ) AS ready_for_clustering,
    COUNT(*) FILTER (
        WHERE a.sentiment_analyzed_at IS NOT NULL
          AND a.entity_analyzed_at IS NOT NULL
          AND a.clustered_at IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM article_cluster_members acm
              WHERE acm.article_id = a.id
          )
    ) AS clustered,
    COUNT(*) FILTER (
        WHERE a.sentiment_analyzed_at IS NOT NULL
          AND a.entity_analyzed_at IS NOT NULL
          AND a.clustered_at IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM article_cluster_members acm
              WHERE acm.article_id = a.id
          )
    ) AS pending,
    COUNT(*) FILTER (
        WHERE a.clustered_at IS NULL
          AND EXISTS (
              SELECT 1
              FROM article_cluster_members acm
              WHERE acm.article_id = a.id
          )
    ) AS inconsistent,
    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM article_embeddings ae
            WHERE ae.article_id = a.id
        )
    ) AS with_embedding,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE a.sentiment_analyzed_at IS NOT NULL
              AND a.entity_analyzed_at IS NOT NULL
              AND a.clustered_at IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM article_cluster_members acm
                  WHERE acm.article_id = a.id
              )
        ) / NULLIF(
            COUNT(*) FILTER (
                WHERE a.sentiment_analyzed_at IS NOT NULL
                  AND a.entity_analyzed_at IS NOT NULL
            ),
            0
        ),
        2
    ) AS clustered_pct
FROM articles a
WHERE a.fetched_at >= NOW() - INTERVAL '24 hours';
""")


# Cluster creation and membership activity during the last 24 hours.
CLUSTER_ACTIVITY_SQL = text("""
WITH active_cluster_sizes AS (
    SELECT
        recent.cluster_id,
        COUNT(all_members.article_id) AS current_article_count
    FROM (
        SELECT DISTINCT cluster_id
        FROM article_cluster_members
        WHERE added_at >= NOW() - INTERVAL '24 hours'
    ) recent
    JOIN article_cluster_members all_members
      ON all_members.cluster_id = recent.cluster_id
    GROUP BY recent.cluster_id
)
SELECT
    (
        SELECT COUNT(*)
        FROM article_clusters
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    ) AS clusters_created,
    (
        SELECT COUNT(*)
        FROM article_cluster_members
        WHERE added_at >= NOW() - INTERVAL '24 hours'
    ) AS memberships_added,
    COUNT(*) AS clusters_touched,
    COUNT(*) FILTER (
        WHERE current_article_count = 1
    ) AS current_single_article_clusters,
    COUNT(*) FILTER (
        WHERE current_article_count > 1
    ) AS current_multi_article_clusters,
    ROUND(AVG(current_article_count), 2) AS avg_current_cluster_size,
    MAX(current_article_count) AS largest_current_cluster_size
FROM active_cluster_sizes;
""")


# Additional clustering integrity checks. All counts should be zero.
CLUSTERING_INTEGRITY_SQL = text("""
WITH checks AS (
    SELECT
        'invalid_similarity_score' AS check_name,
        COUNT(*) AS issue_count
    FROM article_cluster_members acm
    WHERE acm.similarity_score IS NULL
       OR acm.similarity_score < -1
       OR acm.similarity_score > 1

    UNION ALL

    SELECT
        'invalid_cluster_time_range',
        COUNT(*)
    FROM article_clusters ac
    WHERE ac.first_seen_at > ac.last_seen_at

    UNION ALL

    SELECT
        'cluster_time_range_mismatch',
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

    UNION ALL

    SELECT
        'label_timestamp_mismatch',
        COUNT(*)
    FROM article_clusters ac
    WHERE (
            NULLIF(BTRIM(ac.short_label), '') IS NULL
            AND ac.label_updated_at IS NOT NULL
          )
       OR (
            NULLIF(BTRIM(ac.short_label), '') IS NOT NULL
            AND ac.label_updated_at IS NULL
          )

    UNION ALL

    SELECT
        'embedding_model_mismatch',
        COUNT(*)
    FROM article_cluster_members acm
    JOIN article_clusters ac
      ON ac.id = acm.cluster_id
    JOIN article_embeddings ae
      ON ae.article_id = acm.article_id
    WHERE ae.model_name <> ac.model_name

    UNION ALL

    SELECT
        'representative_article_not_in_cluster',
        COUNT(*)
    FROM article_clusters ac
    WHERE ac.representative_article_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM article_cluster_members acm
          WHERE acm.cluster_id = ac.id
            AND acm.article_id = ac.representative_article_id
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


# Membership exists, but the article was not marked as clustered.
UNMARKED_CLUSTERED_ARTICLES_SQL = text("""
SELECT
    a.id AS article_id,
    a.title,
    a.published_at,
    acm.cluster_id,
    acm.similarity_score,
    acm.added_at,
    ac.short_label
FROM articles a
JOIN article_cluster_members acm
  ON acm.article_id = a.id
JOIN article_clusters ac
  ON ac.id = acm.cluster_id
WHERE a.clustered_at IS NULL
ORDER BY a.published_at DESC
LIMIT 20;
""")

# Multi-article clusters for which label generation did not complete.
UNLABELED_MULTI_ARTICLE_CLUSTERS_SQL = text("""
WITH affected_clusters AS (
    SELECT ac.id
    FROM article_clusters ac
    JOIN article_cluster_members acm
      ON acm.cluster_id = ac.id
    WHERE NULLIF(BTRIM(ac.short_label), '') IS NULL
    GROUP BY ac.id
    HAVING COUNT(acm.article_id) > 1
    ORDER BY ac.id DESC
    LIMIT 50
)
SELECT
    ac.id AS cluster_id,
    ac.article_count AS stored_article_count,
    COUNT(acm.article_id) AS actual_article_count,
    MIN(a.published_at) AS first_article_at,
    MAX(a.published_at) AS last_article_at,
    ARRAY_AGG(
        a.title
        ORDER BY a.published_at DESC
    ) AS titles
FROM affected_clusters affected
JOIN article_clusters ac
  ON ac.id = affected.id
JOIN article_cluster_members acm
  ON acm.cluster_id = ac.id
JOIN articles a
  ON a.id = acm.article_id
GROUP BY ac.id, ac.article_count
ORDER BY last_article_at DESC;
""")


# Stored cluster article_count differs from the actual membership count.
CLUSTER_ARTICLE_COUNT_MISMATCHES_SQL = text("""
SELECT
    ac.id AS cluster_id,
    ac.article_count AS stored_article_count,
    COUNT(acm.article_id) AS actual_article_count,
    ac.first_seen_at,
    ac.last_seen_at,
    ac.short_label
FROM article_clusters ac
LEFT JOIN article_cluster_members acm
  ON acm.cluster_id = ac.id
GROUP BY
    ac.id,
    ac.article_count,
    ac.first_seen_at,
    ac.last_seen_at,
    ac.short_label
HAVING ac.article_count <> COUNT(acm.article_id)
ORDER BY ac.last_seen_at DESC
LIMIT 20;
""")


# Recently active multi-article clusters for a quick quality review.
RECENT_MULTI_ARTICLE_CLUSTERS_SQL = text("""
SELECT
    ac.id AS cluster_id,
    ac.article_count AS stored_article_count,
    COUNT(acm.article_id) AS actual_article_count,
    ac.short_label,
    ac.label_updated_at,
    ac.first_seen_at,
    ac.last_seen_at,
    ARRAY_AGG(
        a.title
        ORDER BY a.published_at DESC
    ) AS titles
FROM article_clusters ac
JOIN article_cluster_members acm
  ON acm.cluster_id = ac.id
JOIN articles a
  ON a.id = acm.article_id
WHERE ac.last_seen_at >= NOW() - INTERVAL '24 hours'
GROUP BY
    ac.id,
    ac.article_count,
    ac.short_label,
    ac.label_updated_at,
    ac.first_seen_at,
    ac.last_seen_at
HAVING COUNT(acm.article_id) > 1
ORDER BY ac.last_seen_at DESC
LIMIT 10;
""")
