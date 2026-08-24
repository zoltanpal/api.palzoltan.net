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

DRIVERS_QUERY = text(
    """
    WITH deduplicated AS (
        SELECT DISTINCT ON (a.title_hash)
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
            AND ars.sentiment_label = :driver_label
        ORDER BY
            a.title_hash,
            a.published_at DESC
    )
    SELECT *
    FROM deduplicated
    ORDER BY
        ABS(sentiment_score) DESC,
        published_at DESC
    LIMIT :limit;
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

DETAILED_SOURCES = text(
    """
    SELECT 
        s.name, 
        s.site_url, 
        s.category, 
        count(a.id) as current_article_count
    FROM sources AS s
    LEFT JOIN articles AS a ON s.id=a.source_id
    WHERE s.is_active=True AND s.broken_rss_link=False
    GROUP BY s.name, s.site_url, s.category 
    ORDER BY s.name ASC;
    """
)


WHAT_DRIVING = text(
    """
    WITH matching_articles AS (
        SELECT
            a.id,
            a.source_id,
            a.published_at,
            ars.sentiment_score,
            ars.sentiment_label,
            acm.cluster_id,
            ac.article_count AS cluster_article_count
        FROM articles a
        JOIN article_sentiments ars
            ON ars.article_id = a.id
        JOIN article_cluster_members acm
            ON acm.article_id = a.id
        JOIN article_clusters ac
            ON ac.id = acm.cluster_id
        WHERE
            a.title_search_vector
                @@ plainto_tsquery('english', :query)
            AND a.published_at >= NOW()
                - (:window_hours * INTERVAL '1 hour')
            AND a.sentiment_analyzed_at IS NOT NULL
            AND a.entity_analyzed_at IS NOT NULL
            AND a.clustered_at IS NOT NULL
    ),
    cluster_stats AS (
        SELECT
            ma.cluster_id,
            COUNT(*) AS matching_article_count,
            MAX(ma.cluster_article_count)
                AS cluster_article_count,
            COUNT(DISTINCT ma.source_id)
                AS source_count,
            AVG(ma.sentiment_score)
                AS avg_sentiment_score,
            COUNT(*) FILTER (
                WHERE ma.sentiment_label = 'positive'
            ) AS positive_count,
            COUNT(*) FILTER (
                WHERE ma.sentiment_label = 'neutral'
            ) AS neutral_count,
            COUNT(*) FILTER (
                WHERE ma.sentiment_label = 'negative'
            ) AS negative_count,
            MIN(ma.published_at) AS first_seen_at,
            MAX(ma.published_at) AS last_seen_at
        FROM matching_articles ma
        GROUP BY ma.cluster_id
        HAVING COUNT(*) > 1
    ),
    representative_articles AS (
        SELECT DISTINCT ON (ma.cluster_id)
            ma.cluster_id,
            a.id AS representative_article_id,
            a.title AS representative_title,
            a.link AS representative_link,
            s.name AS representative_source,
            a.published_at AS representative_published_at
        FROM matching_articles ma
        JOIN articles a
            ON a.id = ma.id
        JOIN sources s
            ON s.id = a.source_id
        ORDER BY
            ma.cluster_id,
            a.published_at DESC
    )
    SELECT
        cs.matching_article_count AS article_count,
        cs.cluster_article_count,
        cs.source_count,
        ROUND(cs.avg_sentiment_score::numeric, 3)
            AS avg_sentiment_score,
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
        ra.representative_published_at
    FROM cluster_stats cs
    JOIN representative_articles ra
        ON ra.cluster_id = cs.cluster_id
    ORDER BY
        cs.matching_article_count DESC,
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
    --,COUNT(DISTINCT a.source_id) AS source_count
    FROM article_entities ae
    JOIN articles a ON a.id = ae.article_id
    JOIN entities e ON e.id = ae.entity_id
    WHERE a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
    AND e.entity_type NOT IN ('location')
    GROUP BY
        e.id,
        e.entity_text,
        e.entity_type
    ORDER BY
        article_count DESC,
        --source_count DESC,
        e.entity_text ASC
    LIMIT :limit;
    """
)