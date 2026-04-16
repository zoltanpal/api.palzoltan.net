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
        a.title_search_vector @@ plainto_tsquery('english', :query)
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.is_analyzed = true
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
        a.title_search_vector @@ plainto_tsquery('english', :query)
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.is_analyzed = true
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
            a.title_search_vector @@ plainto_tsquery('english', :query)
            AND a.published_at >= NOW() - (:window_hours * 2 * INTERVAL '1 hour')
            AND a.is_analyzed = true
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
        a.title_search_vector @@ plainto_tsquery('english', :query)
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.is_analyzed = true
        AND ars.sentiment_label = :driver_label
    ORDER BY
        a.title_hash,
        a.published_at DESC,
        ABS(ars.sentiment_score) DESC
    LIMIT :limit
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
            a.title_search_vector @@ plainto_tsquery('english', :query)
            AND a.published_at >= p.range_start
            AND a.published_at <= p.range_end
            AND a.is_analyzed = true
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
        count(a.id) as current_articles_count
    FROM sources AS s
    LEFT JOIN articles AS a ON s.id=a.source_id
    WHERE s.is_active=True AND s.broken_rss_link=False
    GROUP BY s.name, s.site_url, s.category 
    ORDER BY s.name ASC;
    """
)
