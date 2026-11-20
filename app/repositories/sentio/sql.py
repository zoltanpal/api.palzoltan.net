from sqlalchemy import text


AGGREGATED_QUERY = text(
    """
    SELECT
        COUNT(*) AS total_articles,
        AVG(s.sentiment_score) AS avg_sentiment_score,
        COUNT(*) FILTER (WHERE s.sentiment_label = 'positive') AS positive_count,
        COUNT(*) FILTER (WHERE s.sentiment_label = 'neutral') AS neutral_count,
        COUNT(*) FILTER (WHERE s.sentiment_label = 'negative') AS negative_count,
        COUNT(DISTINCT a.source_id) AS source_count
    FROM articles a
    JOIN article_sentiments s ON s.article_id = a.id
    WHERE
        (
            (
                CAST(:entity_id AS BIGINT) IS NULL
                AND a.search_vector @@ plainto_tsquery('english', :query)
            )
            OR
            (
                CAST(:entity_id AS BIGINT) IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM article_entities ae
                    WHERE ae.article_id = a.id
                    AND ae.entity_id = CAST(:entity_id AS BIGINT)
                )
            )
        )
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.published_at < NOW()
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
        (
            (
                CAST(:entity_id AS BIGINT) IS NULL
                AND a.search_vector @@ plainto_tsquery('english', :query)
            )
            OR
            (
                CAST(:entity_id AS BIGINT) IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM article_entities ae
                    WHERE ae.article_id = a.id
                    AND ae.entity_id = CAST(:entity_id AS BIGINT)
                )
            )
        )
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.published_at < NOW()
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
            (
                (
                    CAST(:entity_id AS BIGINT) IS NULL
                    AND a.search_vector @@ plainto_tsquery('english', :query)
                )
                OR
                (
                    CAST(:entity_id AS BIGINT) IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM article_entities ae
                        WHERE ae.article_id = a.id
                        AND ae.entity_id = CAST(:entity_id AS BIGINT)
                    )
                )
            )
            AND a.published_at >= NOW() - (:window_hours * 2 * INTERVAL '1 hour')
            AND a.published_at < NOW()
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
        AVG(sentiment_score) AS avg_sentiment_score
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
            (
                (
                    CAST(:entity_id AS BIGINT) IS NULL
                    AND a.search_vector @@ plainto_tsquery('english', :query)
                )
                OR
                (
                    CAST(:entity_id AS BIGINT) IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM article_entities ae
                        WHERE ae.article_id = a.id
                        AND ae.entity_id = CAST(:entity_id AS BIGINT)
                    )
                )
            )
            AND a.published_at >= p.range_start
            AND a.published_at < p.range_end
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
            a.search_vector @@ plainto_tsquery('english', :query)
            AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
            AND a.published_at < NOW()
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
        JOIN article_cluster_members acm ON acm.cluster_id = cci.cluster_id
        JOIN articles a ON a.id = acm.article_id
        JOIN article_sentiments ars ON ars.article_id = a.id
        JOIN sources s ON s.id = a.source_id
        WHERE
            a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
            AND a.published_at < NOW()
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
        e.id,
        e.entity_text as name,
        e.entity_type as type,
        COUNT(DISTINCT ae.article_id) AS article_count
    FROM article_entities ae
    JOIN articles a ON a.id = ae.article_id
    JOIN entities e ON e.id = ae.entity_id
    WHERE
        lower(e.entity_text) <> ALL(CAST(:stop_words AS text[])) 
        AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
        AND a.published_at < NOW()
        AND a.entity_analyzed_at IS NOT NULL
        AND a.clustered_at IS NOT NULL
        AND e.entity_type NOT IN ('location')
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


PREVIOUS_DRIVERS_QUERY = text(
    """
    SELECT
        acm.cluster_id,
        COUNT(DISTINCT a.id) AS previous_article_count,
        COUNT(DISTINCT a.source_id) AS previous_source_count
    FROM article_cluster_members acm
    JOIN articles a
        ON a.id = acm.article_id
    WHERE
        acm.cluster_id = ANY(CAST(:current_driver_ids AS BIGINT[]))
        AND a.published_at >= :previous_from
        AND a.published_at < :previous_to
        AND a.search_vector @@ websearch_to_tsquery('english', :query)
    GROUP BY acm.cluster_id
    """
)

CREATE_USER = text(
    """
    INSERT INTO public.users (
        firebase_uid,
        email,
        nickname
    )
    VALUES (
        :firebase_uid,
        :email,
        :nickname
    )
    ON CONFLICT (firebase_uid)
    DO UPDATE SET
        email = EXCLUDED.email,
        updated_at = now()
    RETURNING id, firebase_uid, email, nickname, created_at, updated_at;
    """
)

GET_DB_USER = text(
    """
    SELECT * FROM users WHERE firebase_uid=:firebase_uid;
    """
)

GET_ENTITY = text(
    """
    SELECT * FROM entities WHERE id=:entity_id;
    """
)


CREATE_USER_WATCHLIST = text(
    """
    INSERT INTO public.user_watchlist (user_id, entity_id)
    VALUES (:user_id, :entity_id)
    ON CONFLICT (user_id, entity_id) DO NOTHING
    RETURNING entity_id;
    """
)

DELETE_USER_WATCHLIST = text(
    """
    DELETE FROM public.user_watchlist
    WHERE user_id = :user_id
      AND entity_id = :entity_id
    RETURNING entity_id;
    """
)

USER_WATCHLISTS = text(
    """
    SELECT e.id as entity_id, 
        e.entity_text as entity_name, 
        e.normalized_text as entity_label,
        e.entity_type,
        uw.created_at as entity_added
    FROM public.user_watchlist AS uw
    JOIN public.entities AS e ON e.id = uw.entity_id
    WHERE uw.user_id = :user_id
    ORDER BY e.entity_text, e.id;
    """
)


SEARCH_ENTITY_BY_NAME = text(
    """
    SELECT id, 
        entity_text as name, 
        entity_type as type
    FROM public.entities
    WHERE normalized_text LIKE :query
    ORDER BY normalized_text, id
    LIMIT :limit;
    """
)

USER_WATCHLISTS_OVERVIEW = text(
    """
    WITH params AS (
        SELECT
            NOW() AS as_of,
            CAST(:window_hours AS INTEGER) * INTERVAL '1 hour' AS window_size
    ),
    followed_entities AS (
        SELECT
            e.id AS entity_id,
            e.entity_text AS entity_name,
            e.entity_type AS entity_type,
            uw.created_at AS followed_at
        FROM
            user_watchlist uw
            JOIN entities e ON e.id = uw.entity_id
        WHERE
            uw.user_id = :user_id
    ),
    activity AS (
        SELECT
            ae.entity_id,
            a.id AS article_id,
            a.title,
            a.link,
            a.source_id,
            a.published_at,
            s.sentiment_score,
            s.sentiment_label,
            (a.published_at >= p.as_of - p.window_size) AS is_current
        FROM
            followed_entities fe
            JOIN article_entities ae ON ae.entity_id = fe.entity_id
            JOIN articles a ON a.id = ae.article_id
            CROSS JOIN params p
            JOIN article_sentiments s ON s.article_id = a.id
        WHERE
            a.published_at >= p.as_of - 2 * p.window_size
            AND a.published_at < p.as_of
            AND a.clustered_at IS NOT NULL
    ),
    metrics AS (
        SELECT
            entity_id,
            COUNT(*) FILTER (
                WHERE is_current
            ) AS article_count,
            COUNT(*) FILTER (
                WHERE NOT is_current
            ) AS previous_article_count,
            COUNT(*) FILTER (
                WHERE is_current AND sentiment_score IS NOT NULL
            ) AS analyzed_count,
            AVG(sentiment_score) FILTER (
                WHERE is_current
            ) AS avg_sentiment,
            AVG(sentiment_score) FILTER (
                WHERE NOT is_current
            ) AS previous_avg_sentiment,
            COUNT(*) FILTER (
                WHERE is_current AND sentiment_label = 'positive'
            ) AS positive_count,
            COUNT(*) FILTER (
                WHERE is_current AND sentiment_label = 'neutral'
            ) AS neutral_count,
            COUNT(*) FILTER (
                WHERE is_current AND sentiment_label = 'negative'
            ) AS negative_count,
            COUNT(DISTINCT source_id) FILTER (
                WHERE is_current
            ) AS source_count
        FROM activity
        GROUP BY entity_id
    ),
    latest_articles AS (
        SELECT DISTINCT
            ON (entity_id) entity_id,
            title,
            link,
            published_at
        FROM activity
        WHERE is_current
        ORDER BY
            entity_id,
            published_at DESC,
            article_id DESC
    )
    SELECT
        fe.entity_id,
        fe.entity_name,
        fe.entity_type,
        fe.followed_at,
        COALESCE(m.article_count, 0) AS article_count,
        COALESCE(m.previous_article_count, 0) AS previous_article_count,
        COALESCE(m.analyzed_count, 0) AS analyzed_count,
        ROUND(m.avg_sentiment::NUMERIC, 3) AS avg_sentiment,
        ROUND(m.previous_avg_sentiment::NUMERIC, 3) AS previous_avg_sentiment,
        ROUND(
            (m.avg_sentiment - m.previous_avg_sentiment)::NUMERIC,
            3
        ) AS sentiment_change,
        COALESCE(m.positive_count, 0) AS positive_count,
        COALESCE(m.neutral_count, 0) AS neutral_count,
        COALESCE(m.negative_count, 0) AS negative_count,
        COALESCE(m.source_count, 0) AS source_count,
        la.title AS latest_title,
        la.link AS latest_link,
        la.published_at AS latest_published_at
    FROM
        followed_entities fe
        LEFT JOIN metrics m ON m.entity_id = fe.entity_id
        LEFT JOIN latest_articles la ON la.entity_id = fe.entity_id
    ORDER BY
        fe.followed_at DESC,
        fe.entity_id;
    """
)