from sqlalchemy import text

"""
Sentio database health check

Read-only. Safe to run against production.
All checks in the first result set should report PASS.
The second result set is a queue snapshot; small non-zero values can be normal
while workers are actively processing articles.
"""


HEALTH_CHECK_SQL = text("""
    WITH checks AS (
        SELECT
            'membership_without_clustered_at' AS check_name,
            COUNT(*) AS issue_count
        FROM articles a
        JOIN article_cluster_members acm
        ON acm.article_id = a.id
        WHERE a.clustered_at IS NULL

        UNION ALL

        SELECT
            'clustered_without_membership',
            COUNT(*)
        FROM articles a
        WHERE a.clustered_at IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM article_cluster_members acm
            WHERE acm.article_id = a.id
        )

        UNION ALL

        SELECT
            'membership_without_embedding',
            COUNT(*)
        FROM article_cluster_members acm
        WHERE NOT EXISTS (
            SELECT 1
            FROM article_embeddings ae
            WHERE ae.article_id = acm.article_id
        )

        UNION ALL

        SELECT
            'embedding_without_membership',
            COUNT(*)
        FROM article_embeddings ae
        WHERE NOT EXISTS (
            SELECT 1
            FROM article_cluster_members acm
            WHERE acm.article_id = ae.article_id
        )

        UNION ALL

        SELECT
            'empty_clusters',
            COUNT(*)
        FROM article_clusters ac
        WHERE NOT EXISTS (
            SELECT 1
            FROM article_cluster_members acm
            WHERE acm.cluster_id = ac.id
        )

        UNION ALL

        SELECT
            'clusters_without_centroid',
            COUNT(*)
        FROM article_clusters ac
        WHERE ac.centroid IS NULL

        UNION ALL

        SELECT
            'incorrect_cluster_article_count',
            COUNT(*)
        FROM (
            SELECT ac.id
            FROM article_clusters ac
            LEFT JOIN article_cluster_members acm
            ON acm.cluster_id = ac.id
            GROUP BY ac.id, ac.article_count
            HAVING ac.article_count <> COUNT(acm.article_id)
        ) inconsistent_counts

        UNION ALL

        SELECT
            'multi_article_clusters_without_label',
            COUNT(*)
        FROM (
            SELECT ac.id
            FROM article_clusters ac
            JOIN article_cluster_members acm
            ON acm.cluster_id = ac.id
            WHERE NULLIF(BTRIM(ac.short_label), '') IS NULL
            GROUP BY ac.id
            HAVING COUNT(acm.article_id) > 1
        ) unlabeled_clusters

        UNION ALL

        SELECT
            'duplicate_cluster_memberships',
            COUNT(*)
        FROM (
            SELECT acm.article_id
            FROM article_cluster_members acm
            GROUP BY acm.article_id
            HAVING COUNT(*) > 1
        ) duplicates

        UNION ALL

        SELECT
            'multiple_sentiments_per_article',
            COUNT(*)
        FROM (
            SELECT ars.article_id
            FROM article_sentiments ars
            GROUP BY ars.article_id
            HAVING COUNT(*) > 1
        ) duplicates

        UNION ALL

        SELECT
            'sentiment_flag_without_result',
            COUNT(*)
        FROM articles a
        WHERE a.sentiment_analyzed_at IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM article_sentiments ars
            WHERE ars.article_id = a.id
        )

        UNION ALL

        SELECT
            'sentiment_result_without_flag',
            COUNT(*)
        FROM articles a
        WHERE a.sentiment_analyzed_at IS NULL
        AND EXISTS (
            SELECT 1
            FROM article_sentiments ars
            WHERE ars.article_id = a.id
        )

        UNION ALL

        SELECT
            'entity_mapping_without_flag',
            COUNT(*)
        FROM articles a
        WHERE a.entity_analyzed_at IS NULL
        AND EXISTS (
            SELECT 1
            FROM article_entities ae
            WHERE ae.article_id = a.id
        )

        UNION ALL

        SELECT
            'clustered_before_analysis_completed',
            COUNT(*)
        FROM articles a
        WHERE a.clustered_at IS NOT NULL
        AND (
            a.sentiment_analyzed_at IS NULL
            OR a.entity_analyzed_at IS NULL
        )

        UNION ALL

        SELECT
            'cluster_member_without_article',
            COUNT(*)
        FROM article_cluster_members acm
        LEFT JOIN articles a
        ON a.id = acm.article_id
        WHERE a.id IS NULL

        UNION ALL

        SELECT
            'cluster_member_without_cluster',
            COUNT(*)
        FROM article_cluster_members acm
        LEFT JOIN article_clusters ac
        ON ac.id = acm.cluster_id
        WHERE ac.id IS NULL

        UNION ALL

        SELECT
            'embedding_without_article',
            COUNT(*)
        FROM article_embeddings ae
        LEFT JOIN articles a
        ON a.id = ae.article_id
        WHERE a.id IS NULL

        UNION ALL

        SELECT
            'sentiment_without_article',
            COUNT(*)
        FROM article_sentiments ars
        LEFT JOIN articles a
        ON a.id = ars.article_id
        WHERE a.id IS NULL

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
            'article_without_source',
            COUNT(*)
        FROM articles a
        LEFT JOIN sources s
        ON s.id = a.source_id
        WHERE s.id IS NULL

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

        UNION ALL

        SELECT
            'stale_articles_without_search_vector',
            COUNT(*)
        FROM articles a
        WHERE a.search_vector IS NULL
        AND a.fetched_at < NOW() - INTERVAL '30 minutes'

        UNION ALL

        SELECT
            'stale_pending_sentiment',
            COUNT(*)
        FROM articles a
        WHERE a.sentiment_analyzed_at IS NULL
        AND a.fetched_at < NOW() - INTERVAL '30 minutes'

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
            'stale_pending_clustering',
            COUNT(*)
        FROM articles a
        WHERE a.sentiment_analyzed_at IS NOT NULL
        AND a.entity_analyzed_at IS NOT NULL
        AND a.clustered_at IS NULL
        AND a.fetched_at < NOW() - INTERVAL '30 minutes'
        AND NOT EXISTS (
            SELECT 1
            FROM article_cluster_members acm
            WHERE acm.article_id = a.id
        )

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
            'invalid_article_timestamps',
            COUNT(*)
        FROM articles a
        WHERE a.fetched_at > NOW() + INTERVAL '5 minutes'
        OR a.published_at > NOW() + INTERVAL '24 hours'

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
            'invalid_membership_similarity',
            COUNT(*)
        FROM article_cluster_members acm
        WHERE acm.similarity_score IS NULL
        OR acm.similarity_score < -1
        OR acm.similarity_score > 1

        UNION ALL

        SELECT
            'cluster_label_timestamp_mismatch',
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
            'cluster_embedding_model_mismatch',
            COUNT(*)
        FROM article_cluster_members acm
        JOIN article_clusters ac
        ON ac.id = acm.cluster_id
        JOIN article_embeddings ae
        ON ae.article_id = acm.article_id
        WHERE ae.model_name <> ac.model_name
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

#  Current pipeline queue snapshot. These are informational, not failures.
CURRENT_PIPELINE_QUEUE_SQL = text("""
    SELECT
        COUNT(*) FILTER (
            WHERE sentiment_analyzed_at IS NULL
        ) AS pending_sentiment,
        COUNT(*) FILTER (
            WHERE sentiment_analyzed_at IS NOT NULL
            AND entity_analyzed_at IS NULL
        ) AS pending_entities,
        COUNT(*) FILTER (
            WHERE sentiment_analyzed_at IS NOT NULL
            AND entity_analyzed_at IS NOT NULL
            AND clustered_at IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM article_cluster_members acm
                WHERE acm.article_id = articles.id
            )
        ) AS pending_clustering,
        COUNT(*) FILTER (
            WHERE clustered_at IS NOT NULL
        ) AS clustered_articles
    FROM articles;
""")
