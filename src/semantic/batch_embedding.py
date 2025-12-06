"""
Batch Embedding Processor - Generate embeddings for multiple records efficiently.

Handles bulk embedding generation for:
- learning_atoms: Flashcard embeddings (front + back combined)
- concepts: Concept definition embeddings
- stg_anki_cards: Staging table embeddings

Supports incremental processing (skip existing) and regeneration modes.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from src.semantic.embedding_service import EmbeddingService


class BatchEmbeddingProcessor:
    """
    Generate embeddings for database records in batches.

    Efficiently processes large numbers of records with progress tracking
    and error handling. Stores results directly in the database.

    Example:
        >>> processor = BatchEmbeddingProcessor(db_session)
        >>> result = processor.generate_embeddings(source="learning_atoms")
        >>> print(f"Generated {result['records_processed']} embeddings")
    """

    SUPPORTED_SOURCES = {
        "learning_atoms": {
            "id_column": "id",
            "text_columns": ["front", "back"],
            "table": "learning_atoms",
        },
        "concepts": {
            "id_column": "id",
            "text_columns": ["name", "definition"],
            "table": "concepts",
        },
        "stg_anki_cards": {
            "id_column": "anki_note_id",
            "text_columns": ["front", "back"],
            "table": "stg_anki_cards",
        },
    }

    def __init__(
        self,
        db_session: Session,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """
        Initialize the batch processor.

        Args:
            db_session: SQLAlchemy database session.
            embedding_service: Optional custom embedding service.
        """
        self.db = db_session
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

    def generate_embeddings(
        self,
        source: str = "learning_atoms",
        batch_size: Optional[int] = None,
        regenerate: bool = False,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Generate embeddings for records in a source table.

        Args:
            source: Source table name (learning_atoms, concepts, stg_anki_cards).
            batch_size: Number of records per batch (default from config).
            regenerate: If True, regenerate all embeddings. If False, skip existing.
            limit: Maximum total records to process.

        Returns:
            Dictionary with processing statistics.
        """
        if source not in self.SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported source: {source}. Use: {list(self.SUPPORTED_SOURCES.keys())}")

        config = self.SUPPORTED_SOURCES[source]
        batch_size = batch_size or self.settings.embedding_batch_size

        # Create log entry
        batch_id = str(uuid4())[:8]
        log_id = self._create_log_entry(batch_id, source)

        try:
            result = self._process_source(
                config=config,
                batch_size=batch_size,
                regenerate=regenerate,
                limit=limit,
                batch_id=batch_id,
            )

            # Update log with success
            self._update_log_entry(
                log_id,
                status="completed",
                **result,
            )

            return result

        except Exception as e:
            logger.exception(f"Embedding generation failed for {source}")
            self._update_log_entry(
                log_id,
                status="failed",
                error_message=str(e),
            )
            raise

    def _process_source(
        self,
        config: dict,
        batch_size: int,
        regenerate: bool,
        limit: Optional[int],
        batch_id: str,
    ) -> dict:
        """
        Process all records from a source table.

        Args:
            config: Source configuration dictionary.
            batch_size: Records per batch.
            regenerate: Whether to regenerate existing embeddings.
            limit: Maximum records to process.
            batch_id: Batch identifier for logging.

        Returns:
            Processing statistics.
        """
        table = config["table"]
        id_col = config["id_column"]
        text_cols = config["text_columns"]

        # Build query for records needing embeddings
        if regenerate:
            where_clause = "WHERE TRUE"
        else:
            where_clause = "WHERE embedding IS NULL"

        limit_clause = f"LIMIT {limit}" if limit else ""

        # Count total records
        count_query = text(f"SELECT COUNT(*) FROM {table} {where_clause}")
        total_records = self.db.execute(count_query).scalar()

        logger.info(f"Processing {total_records} records from {table} (batch_id={batch_id})")

        if total_records == 0:
            return {
                "success": True,
                "total_records": 0,
                "records_processed": 0,
                "records_skipped": 0,
                "records_failed": 0,
                "errors": [],
            }

        # Process in batches
        offset = 0
        total_processed = 0
        total_skipped = 0
        total_failed = 0
        errors = []

        while True:
            # Fetch batch
            fetch_query = text(f"""
                SELECT {id_col}, {', '.join(text_cols)}
                FROM {table}
                {where_clause}
                ORDER BY {id_col}
                LIMIT :batch_size OFFSET :offset
            """)

            batch = self.db.execute(
                fetch_query,
                {"batch_size": batch_size, "offset": offset},
            ).fetchall()

            if not batch:
                break

            # Generate embeddings for batch
            try:
                processed, failed = self._process_batch(
                    batch=batch,
                    table=table,
                    id_col=id_col,
                    text_cols=text_cols,
                )
                total_processed += processed
                total_failed += failed

            except Exception as e:
                error_msg = f"Batch at offset {offset} failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                total_failed += len(batch)

            offset += batch_size

            # Progress logging
            if offset % (batch_size * 10) == 0:
                logger.info(f"Processed {total_processed} / {total_records} records")

            # Check limit
            if limit and total_processed >= limit:
                break

        return {
            "success": True,
            "total_records": total_records,
            "records_processed": total_processed,
            "records_skipped": total_skipped,
            "records_failed": total_failed,
            "errors": errors,
        }

    def _process_batch(
        self,
        batch: list,
        table: str,
        id_col: str,
        text_cols: List[str],
    ) -> tuple:
        """
        Process a single batch of records.

        Args:
            batch: List of database rows.
            table: Table name.
            id_col: ID column name.
            text_cols: Text column names for embedding.

        Returns:
            Tuple of (processed_count, failed_count).
        """
        # Combine text columns for each record
        texts = []
        record_ids = []

        for row in batch:
            # Get text from columns
            text_parts = []
            for col in text_cols:
                val = getattr(row, col, None)
                if val:
                    text_parts.append(str(val).strip())

            combined_text = self.embedding_service.combine_front_back(
                text_parts[0] if len(text_parts) > 0 else "",
                text_parts[1] if len(text_parts) > 1 else "",
            )

            if combined_text:
                texts.append(combined_text)
                record_ids.append(getattr(row, id_col))

        if not texts:
            return 0, 0

        # Generate embeddings
        results = self.embedding_service.generate_embeddings_batch(texts, show_progress=False)

        # Update database
        processed = 0
        failed = 0

        update_query = text(f"""
            UPDATE {table}
            SET embedding = :embedding,
                embedding_model = :model,
                embedding_generated_at = :generated_at
            WHERE {id_col} = :record_id
        """)

        for record_id, result in zip(record_ids, results):
            try:
                self.db.execute(
                    update_query,
                    {
                        "embedding": result.to_bytes(),  # Store as BYTEA
                        "model": result.model_name,
                        "generated_at": result.generated_at,
                        "record_id": str(record_id) if isinstance(record_id, (int, str)) else str(record_id),
                    },
                )
                processed += 1
            except Exception as e:
                logger.warning(f"Failed to update record {record_id}: {e}")
                failed += 1

        self.db.commit()
        return processed, failed

    def _create_log_entry(self, batch_id: str, source: str) -> str:
        """
        Create an embedding generation log entry.

        Args:
            batch_id: Batch identifier.
            source: Source table name.

        Returns:
            Log entry UUID.
        """
        query = text("""
            INSERT INTO embedding_generation_log
            (batch_id, source_table, model_name, batch_size)
            VALUES (:batch_id, :source, :model, :batch_size)
            RETURNING id
        """)

        result = self.db.execute(
            query,
            {
                "batch_id": batch_id,
                "source": source,
                "model": self.settings.embedding_model,
                "batch_size": self.settings.embedding_batch_size,
            },
        ).fetchone()

        self.db.commit()
        return str(result.id)

    def _update_log_entry(
        self,
        log_id: str,
        status: str,
        total_records: int = 0,
        records_processed: int = 0,
        records_skipped: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Update an embedding generation log entry.

        Args:
            log_id: Log entry UUID.
            status: New status.
            total_records: Total records found.
            records_processed: Records successfully processed.
            records_skipped: Records skipped (already had embeddings).
            records_failed: Records that failed.
            error_message: Error message if failed.
        """
        query = text("""
            UPDATE embedding_generation_log
            SET status = :status,
                completed_at = now(),
                total_records = :total_records,
                records_processed = :records_processed,
                records_skipped = :records_skipped,
                records_failed = :records_failed,
                error_message = :error_message
            WHERE id = :log_id::uuid
        """)

        self.db.execute(
            query,
            {
                "log_id": log_id,
                "status": status,
                "total_records": total_records,
                "records_processed": records_processed,
                "records_skipped": records_skipped,
                "records_failed": records_failed,
                "error_message": error_message,
            },
        )
        self.db.commit()

    def get_embedding_coverage(self) -> dict:
        """
        Get embedding coverage statistics for all supported sources.

        Returns:
            Dictionary with coverage info per source.
        """
        coverage = {}

        for source, config in self.SUPPORTED_SOURCES.items():
            query = text(f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
                    COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding
                FROM {config['table']}
            """)

            result = self.db.execute(query).fetchone()

            coverage[source] = {
                "total": result.total,
                "with_embedding": result.with_embedding,
                "without_embedding": result.without_embedding,
                "coverage_percent": round(
                    result.with_embedding * 100.0 / result.total if result.total > 0 else 0,
                    2,
                ),
            }

        return coverage

    def generate_for_new_atoms(self, atom_ids: List[str]) -> int:
        """
        Generate embeddings for specific new atoms.

        Useful for generating embeddings immediately after import.

        Args:
            atom_ids: List of atom UUIDs.

        Returns:
            Number of embeddings generated.
        """
        if not atom_ids:
            return 0

        # Fetch atoms
        query = text("""
            SELECT id, front, back
            FROM learning_atoms
            WHERE id = ANY(:ids::uuid[])
              AND embedding IS NULL
        """)

        atoms = self.db.execute(query, {"ids": atom_ids}).fetchall()

        if not atoms:
            return 0

        # Generate embeddings
        texts = []
        ids = []

        for atom in atoms:
            combined = self.embedding_service.combine_front_back(
                atom.front or "",
                atom.back or "",
            )
            if combined:
                texts.append(combined)
                ids.append(atom.id)

        results = self.embedding_service.generate_embeddings_batch(texts)

        # Update database
        update_query = text("""
            UPDATE learning_atoms
            SET embedding = :embedding,
                embedding_model = :model,
                embedding_generated_at = :generated_at
            WHERE id = :atom_id
        """)

        for atom_id, result in zip(ids, results):
            self.db.execute(
                update_query,
                {
                    "embedding": result.to_bytes(),  # Store as BYTEA
                    "model": result.model_name,
                    "generated_at": result.generated_at,
                    "atom_id": str(atom_id),
                },
            )

        self.db.commit()
        logger.info(f"Generated embeddings for {len(results)} new atoms")
        return len(results)
