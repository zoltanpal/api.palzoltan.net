from sqlalchemy import text


AGGREGATED_QUERY = text(
    """
    SELECT
        COUNT(*) AS total_articles,
        COALESCE(AVG(s.sentiment_score), 0) AS avg_sentiment_score,
        COUNT(*) FILTER (WHERE s.sentiment_label = 'positive') AS positive_count,
        COUNT(*) FILTER (WHERE s.sentiment_label = 'neutral') AS neutral_count,
        COUNT(*) FILTER (WHERE s.sentiment_label = 'negative') AS negative_count
    FROM articles a
    JOIN article_sentiments s ON s.article_id = a.id
    WHERE
        a.search_vector @@ plainto_tsquery('english', :query)
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.clustered_at IS NOT NULL
    """
)

HEADLINES_QUERY = text(
    """
    SELECT
        a.id,
        a.title,
        a.title_hash,
        a.summary,
        a.link,
        a.published_at,
        s.name AS source_name,
        ars.sentiment_label,
        ars.sentiment_score,
        ars.sentiment_raw
    FROM articles a
    JOIN article_sentiments ars ON ars.article_id = a.id
    JOIN sources s ON s.id = a.source_id
    WHERE
        a.search_vector @@ plainto_tsquery('english', :query)
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.clustered_at IS NOT NULL
    ORDER BY a.published_at DESC
    LIMIT :limit
    """
)

SENTIMENT_CHANGE_QUERY = text(
    """
    WITH matched_articles AS (
        SELECT
            a.id,
            a.published_at,
            ars.sentiment_score
        FROM articles a
        JOIN article_sentiments ars ON ars.article_id = a.id
        WHERE
            a.search_vector @@ plainto_tsquery('english', :query)
            AND a.published_at >= NOW() - (:window_hours * 2 * INTERVAL '1 hour')
            AND a.clustered_at IS NOT NULL
    ),
    windowed AS (
        SELECT
            CASE
                WHEN published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                    THEN 'current'
                ELSE 'previous'
            END AS window_name,
            sentiment_score
        FROM matched_articles
    )
    SELECT
        window_name,
        COUNT(*) AS article_count,
        COALESCE(AVG(sentiment_score), 0) AS avg_sentiment_score
    FROM windowed
    GROUP BY window_name
    """
)

SENTIMENT_SCORES_PER_HOUR_QUERY = text(
    """
    WITH params AS (
        SELECT
            NOW() - (:window_hours * INTERVAL '1 hour') AS range_start,
            NOW() AS range_end,
            CAST(:bucket_interval AS interval) AS bucket_interval
    ),
    buckets AS (
        SELECT generate_series(
            date_bin(p.bucket_interval, p.range_start, TIMESTAMP '2000-01-01'),
            date_bin(p.bucket_interval, p.range_end, TIMESTAMP '2000-01-01'),
            p.bucket_interval
        ) AS bucket_start
        FROM params p
    ),
    aggregated AS (
        SELECT
            date_bin(p.bucket_interval, a.published_at, TIMESTAMP '2000-01-01') AS bucket_start,
            COUNT(*) AS article_count,
            AVG(ars.sentiment_score) AS avg_sentiment_score,
            COUNT(*) FILTER (WHERE ars.sentiment_label = 'positive') AS positive_count,
            COUNT(*) FILTER (WHERE ars.sentiment_label = 'neutral') AS neutral_count,
            COUNT(*) FILTER (WHERE ars.sentiment_label = 'negative') AS negative_count
        FROM articles a
        JOIN article_sentiments ars
            ON ars.article_id = a.id
        CROSS JOIN params p
        WHERE
            a.search_vector @@ plainto_tsquery('english', :query)
            AND a.published_at >= p.range_start
            AND a.published_at <= p.range_end
            AND a.clustered_at IS NOT NULL
        GROUP BY 1
    )
    SELECT
        b.bucket_start,
        COALESCE(a.article_count, 0) AS article_count,
        a.avg_sentiment_score,
        COALESCE(a.positive_count, 0) AS positive_count,
        COALESCE(a.neutral_count, 0) AS neutral_count,
        COALESCE(a.negative_count, 0) AS negative_count
    FROM buckets b
    LEFT JOIN aggregated a
        ON a.bucket_start = b.bucket_start
    ORDER BY b.bucket_start ASC;
    """
)

DETAILED_SOURCES_QUERY = text(
    """
    SELECT
        s.name,
        s.site_url,
        s.category,
        COUNT(a.id) AS current_article_count
    FROM sources AS s
    LEFT JOIN articles AS a ON s.id = a.source_id
    WHERE s.is_active = TRUE AND s.broken_rss_link = FALSE
    GROUP BY s.name, s.site_url, s.category
    ORDER BY s.name ASC;
    """
)


WHAT_DRIVING_QUERY = text(
    """
    WITH candidate_cluster_ids AS (
        SELECT DISTINCT
            acm.cluster_id
        FROM articles a
        JOIN article_cluster_members acm
            ON acm.article_id = a.id
        WHERE
            a.search_vector @@ plainto_tsquery(
                'english',
                :query
            )
            AND a.published_at >= NOW()
                - (:window_hours * INTERVAL '1 hour')
            AND a.sentiment_analyzed_at IS NOT NULL
            AND a.entity_analyzed_at IS NOT NULL
    ),
    cluster_articles AS (
        SELECT
            a.id,
            a.title,
            a.source_id,
            s.name AS source_name,
            a.published_at,
            ars.sentiment_score,
            ars.sentiment_label,
            acm.cluster_id,
            acm.similarity_score
        FROM candidate_cluster_ids cci
        JOIN article_cluster_members acm
            ON acm.cluster_id = cci.cluster_id
        JOIN articles a
            ON a.id = acm.article_id
        JOIN article_sentiments ars
            ON ars.article_id = a.id
        JOIN sources s
            ON s.id = a.source_id
        WHERE
            a.published_at >= NOW()
                - (:window_hours * INTERVAL '1 hour')
            AND a.sentiment_analyzed_at IS NOT NULL
            AND a.entity_analyzed_at IS NOT NULL
    ),
    cluster_stats AS (
        SELECT
            ca.cluster_id,
            COUNT(DISTINCT ca.id) AS article_count,
            COUNT(DISTINCT ca.source_id) AS source_count,
            AVG(ca.sentiment_score) AS avg_sentiment_score,
            COUNT(DISTINCT ca.id) FILTER (
                WHERE ca.sentiment_label = 'positive'
            ) AS positive_count,
            COUNT(DISTINCT ca.id) FILTER (
                WHERE ca.sentiment_label = 'neutral'
            ) AS neutral_count,
            COUNT(DISTINCT ca.id) FILTER (
                WHERE ca.sentiment_label = 'negative'
            ) AS negative_count,
            MIN(ca.published_at) AS first_seen_at,
            MAX(ca.published_at) AS last_seen_at
        FROM cluster_articles ca
        GROUP BY ca.cluster_id
        HAVING COUNT(DISTINCT ca.id) > 1
    ),
    representative_articles AS (
        SELECT DISTINCT ON (ca.cluster_id)
            ca.cluster_id,
            ca.title AS representative_title,
            ca.source_name AS representative_source,
            ca.published_at AS representative_published_at
        FROM cluster_articles ca
        ORDER BY
            ca.cluster_id,
            ca.published_at DESC,
            ca.id DESC
    ),
    cluster_headlines AS (
        SELECT
            ca.cluster_id,
            JSONB_AGG(
                JSONB_BUILD_OBJECT(
                    'article_id', ca.id,
                    'title', ca.title,
                    'source', ca.source_name,
                    'published_at', ca.published_at,
                    'sentiment_label', ca.sentiment_label,
                    'sentiment_score',
                        ROUND(ca.sentiment_score::numeric, 3)
                )
                ORDER BY
                    ca.similarity_score DESC NULLS LAST,
                    ca.published_at DESC
            ) AS headlines
        FROM cluster_articles ca
        GROUP BY ca.cluster_id
    )
    SELECT
        cs.cluster_id,
        COALESCE(
            NULLIF(BTRIM(ac.short_label), ''),
            ra.representative_title
        ) AS driver_label,
        cs.article_count,
        cs.source_count,
        ROUND(
            cs.avg_sentiment_score::numeric,
            3
        ) AS avg_sentiment_score,
        cs.positive_count,
        cs.neutral_count,
        cs.negative_count,
        CASE
            WHEN cs.positive_count >= cs.neutral_count
            AND cs.positive_count >= cs.negative_count
                THEN 'positive'
            WHEN cs.negative_count >= cs.positive_count
            AND cs.negative_count >= cs.neutral_count
                THEN 'negative'
            ELSE 'neutral'
        END AS dominant_sentiment,
        ra.representative_title,
        ra.representative_source,
        ra.representative_published_at,
        COALESCE(
            ch.headlines,
            '[]'::jsonb
        ) AS headlines
    FROM cluster_stats cs
    JOIN article_clusters ac
        ON ac.id = cs.cluster_id
    JOIN representative_articles ra
        ON ra.cluster_id = cs.cluster_id
    JOIN cluster_headlines ch
        ON ch.cluster_id = cs.cluster_id
    ORDER BY
        cs.article_count DESC,
        cs.source_count DESC,
        cs.last_seen_at DESC
    LIMIT :limit;
    """
)

TOP_ENTITIES_QUERY = text(
    """
    SELECT
        e.entity_text,
        e.entity_type,
        COUNT(DISTINCT ae.article_id) AS article_count
    FROM article_entities ae
    JOIN articles a ON a.id = ae.article_id
    JOIN entities e ON e.id = ae.entity_id
    WHERE
        a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.entity_analyzed_at IS NOT NULL
        AND a.clustered_at IS NOT NULL
        AND e.entity_type <> 'location'
    GROUP BY
        e.id,
        e.entity_text,
        e.entity_type
    ORDER BY
        article_count DESC,
        e.entity_text ASC
    LIMIT :limit;
    """
)
