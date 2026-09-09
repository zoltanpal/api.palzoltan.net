from sqlalchemy import text

"""
Sentio sentiment worker validation

Read-only. Safe to run against production.
All checks in the first result set should report PASS.
The remaining result sets are informational snapshots.
"""

SENTIMENT_VALIDATION_SQL = text("""
    WITH checks AS (
        SELECT
            'analyzed_flag_without_sentiment' AS check_name,
            COUNT(*) AS issue_count
        FROM articles a
        WHERE a.sentiment_analyzed_at IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM article_sentiments ars
            WHERE ars.article_id = a.id
        )

        UNION ALL

        SELECT
            'sentiment_without_analyzed_flag',
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
            'sentiment_without_article',
            COUNT(*)
        FROM article_sentiments ars
        LEFT JOIN articles a
        ON a.id = ars.article_id
        WHERE a.id IS NULL

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
            'invalid_sentiment_label',
            COUNT(*)
        FROM article_sentiments ars
        WHERE ars.sentiment_label NOT IN (
            'positive',
            'neutral',
            'negative'
        )

        UNION ALL

        SELECT
            'sentiment_score_out_of_range',
            COUNT(*)
        FROM article_sentiments ars
        WHERE ars.sentiment_score < -1
        OR ars.sentiment_score > 1

        UNION ALL

        SELECT
            'empty_sentiment_model_metadata',
            COUNT(*)
        FROM article_sentiments ars
        WHERE BTRIM(ars.model_name) = ''
        OR BTRIM(ars.model_version) = ''

        UNION ALL

        SELECT
            'stale_pending_sentiment',
            COUNT(*)
        FROM articles a
        WHERE a.sentiment_analyzed_at IS NULL
        AND a.fetched_at < NOW() - INTERVAL '30 minutes'

        UNION ALL

        SELECT
            'invalid_sentiment_timestamps',
            COUNT(*)
        FROM article_sentiments ars
        JOIN articles a
        ON a.id = ars.article_id
        WHERE ars.analyzed_at > NOW() + INTERVAL '5 minutes'
        OR ars.created_at > NOW() + INTERVAL '5 minutes'
        OR a.sentiment_analyzed_at > NOW() + INTERVAL '5 minutes'
        OR a.sentiment_analyzed_at < a.fetched_at
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


# Sentiment worker queue and throughput during the last 24 hours.
STATISTICS_LAST_24_HOURS_SQL = text("""
    SELECT
        COUNT(*) AS articles_fetched,
        COUNT(*) FILTER (
            WHERE sentiment_analyzed_at IS NOT NULL
        ) AS analyzed,
        COUNT(*) FILTER (
            WHERE sentiment_analyzed_at IS NULL
        ) AS pending,
        ROUND(
            100.0 * COUNT(*) FILTER (
                WHERE sentiment_analyzed_at IS NOT NULL
            ) / NULLIF(COUNT(*), 0),
            2
        ) AS analyzed_pct
    FROM articles
    WHERE fetched_at >= NOW() - INTERVAL '24 hours';
""")

# Recent result distribution.
RECENT_RESULT_DISTRIBUTION_SQL = text("""
    SELECT
        ars.sentiment_label,
        COUNT(*) AS result_count,
        ROUND(AVG(ars.sentiment_score), 3) AS avg_score
    FROM article_sentiments ars
    WHERE ars.analyzed_at >= NOW() - INTERVAL '24 hours'
    GROUP BY ars.sentiment_label
    ORDER BY ars.sentiment_label;
""")

# Examples of incomplete or inconsistent articles.
INCOMPLETE_SENTIMENT_ARTICLES_SQL = text("""
    SELECT
        a.id AS article_id,
        a.title,
        a.fetched_at,
        a.sentiment_analyzed_at,
        COUNT(ars.id) AS sentiment_row_count
    FROM articles a
    LEFT JOIN article_sentiments ars
    ON ars.article_id = a.id
    WHERE (
            a.sentiment_analyzed_at IS NOT NULL
            AND ars.id IS NULL
        )
    OR (
            a.sentiment_analyzed_at IS NULL
            AND ars.id IS NOT NULL
        )
    OR (
            a.sentiment_analyzed_at IS NULL
            AND a.fetched_at < NOW() - INTERVAL '30 minutes'
        )
    GROUP BY
        a.id,
        a.title,
        a.fetched_at,
        a.sentiment_analyzed_at
    ORDER BY a.fetched_at DESC
    LIMIT 50;
""")
