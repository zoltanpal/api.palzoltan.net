from sqlalchemy import text

GET_DATASETS = text(
    """
    SELECT * FROM datasets;
    """
)