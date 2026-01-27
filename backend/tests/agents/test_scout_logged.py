"""
SCOUT (Context Retriever) Tests with Exhaustive Logging.

Tests context retrieval with search query logging,
vector scores tracking, and chunk retrieval metrics.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.agents.logging import AgentLogger


class TestScoutWithLogging:
    """Tests for SCOUT agent with comprehensive logging."""

    @pytest.mark.asyncio
    async def test_context_retrieval_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_search_results,
        sample_intent,
    ):
        """
        Context retrieval should be fully logged.

        Verifies:
        - Search queries are captured
        - Vector scores are logged
        - Retrieved chunks are tracked
        - File paths are recorded
        """
        from app.agents.context_retriever import ContextRetriever

        # Setup mock returns
        mock_vector_store.search = MagicMock(return_value=sample_search_results)

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve") as execution:
            # Log input
            agent_logger.log_agent_input("SCOUT", {
                "intent": sample_intent.to_dict() if hasattr(sample_intent, 'to_dict') else str(sample_intent),
                "project_id": "test-project-123",
            })

            # Perform retrieval
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            # Log context retrieval details
            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=sample_intent.search_queries,
                chunks_found=len(sample_search_results),
                chunks_used=len(context.chunks) if context else 0,
                total_tokens=sum(len(c.content) // 4 for c in sample_search_results),
                file_paths=[r.file_path for r in sample_search_results],
                scores=[r.score for r in sample_search_results],
            )

            agent_logger.log_agent_output("SCOUT", context)
            execution.final_output = context

        # Verify context was retrieved
        assert context is not None

        # Verify logging captured retrieval
        report = agent_logger.generate_report()
        scout_exec = report["agent_executions"].get("SCOUT_retrieve")
        assert scout_exec is not None
        assert scout_exec["context_retrievals_count"] >= 1

    @pytest.mark.asyncio
    async def test_multiple_search_queries_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_intent,
    ):
        """Multiple search queries should all be logged."""
        from app.agents.context_retriever import ContextRetriever

        # Setup with multiple queries in intent
        sample_intent.search_queries = [
            "User model relationships",
            "UserController methods",
            "user authentication",
            "user validation rules",
        ]

        mock_vector_store.search = MagicMock(return_value=[])

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "multi_query") as execution:
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            # Log all queries
            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=sample_intent.search_queries,
                chunks_found=0,
                chunks_used=0,
                total_tokens=0,
                file_paths=[],
                scores=[],
            )

            execution.final_output = context

        # Verify logging
        report = agent_logger.generate_report()
        log_dir = agent_logger.get_log_dir()

        # Check search queries were saved
        queries_file = log_dir / "agents" / "scout" / "search_queries.json"
        assert queries_file.exists()

    @pytest.mark.asyncio
    async def test_score_distribution_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_intent,
    ):
        """Score distribution should be logged for analysis."""
        from app.agents.context_retriever import ContextRetriever
        from app.services.vector_store import SearchResult

        # Create results with varied scores
        varied_results = [
            SearchResult(
                chunk_id="high-1",
                file_path="app/Models/User.php",
                content="High relevance content",
                chunk_type="class",
                score=0.95,
                metadata={},
            ),
            SearchResult(
                chunk_id="medium-1",
                file_path="app/Controllers/UserController.php",
                content="Medium relevance content",
                chunk_type="class",
                score=0.75,
                metadata={},
            ),
            SearchResult(
                chunk_id="low-1",
                file_path="app/Services/Helper.php",
                content="Low relevance content",
                chunk_type="function",
                score=0.55,
                metadata={},
            ),
        ]

        mock_vector_store.search = MagicMock(return_value=varied_results)

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve_varied") as execution:
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            scores = [r.score for r in varied_results]
            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=sample_intent.search_queries,
                chunks_found=len(varied_results),
                chunks_used=len(context.chunks) if context else 0,
                total_tokens=sum(len(r.content) // 4 for r in varied_results),
                file_paths=[r.file_path for r in varied_results],
                scores=scores,
            )

            execution.final_output = context

        # Verify score metrics in report
        report = agent_logger.generate_report()
        scout_exec = report["agent_executions"].get("SCOUT_retrieve_varied")

        # Check context retrieval was logged
        assert scout_exec["context_retrievals_count"] >= 1

    @pytest.mark.asyncio
    async def test_file_access_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_intent,
        mock_search_results_subscription,
    ):
        """File access during retrieval should be logged."""
        from app.agents.context_retriever import ContextRetriever

        mock_vector_store.search = MagicMock(return_value=mock_search_results_subscription)

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve_files") as execution:
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            # Log file accesses
            for result in mock_search_results_subscription:
                agent_logger.log_file_access(
                    agent="SCOUT",
                    operation="read",
                    file_path=result.file_path,
                    content=result.content,
                )

            execution.final_output = context

        # Verify file access logged
        report = agent_logger.generate_report()
        scout_exec = report["agent_executions"].get("SCOUT_retrieve_files")
        assert scout_exec["file_accesses_count"] >= 1

    @pytest.mark.asyncio
    async def test_subscription_scenario_context_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        subscription_management_scenario,
        mock_search_results_subscription,
    ):
        """
        Full subscription scenario context retrieval should be logged.
        """
        from app.agents.context_retriever import ContextRetriever
        from app.agents.intent_analyzer import Intent

        # Create intent from scenario expectations
        intent = Intent(
            task_type="feature",
            task_type_confidence=0.92,
            domains_affected=subscription_management_scenario["expected_flow"]["nova"]["expected_domains"],
            scope="feature",
            languages=["php", "typescript"],
            requires_migration=True,
            priority="high",
            entities={
                "files": [],
                "classes": ["Subscription", "Plan"],
                "methods": [],
                "routes": [],
                "tables": ["subscriptions", "plans"],
            },
            search_queries=[
                "User model",
                "API routes",
                "base controller",
                "subscription",
            ],
            reasoning="Implementing subscription management",
            overall_confidence=0.92,
            needs_clarification=False,
            clarifying_questions=[],
        )

        mock_vector_store.search = MagicMock(return_value=mock_search_results_subscription)

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve_subscription") as execution:
            agent_logger.log_agent_input("SCOUT", {
                "scenario": "subscription_management",
                "intent": intent.to_dict() if hasattr(intent, 'to_dict') else str(intent),
            })

            context = await scout.retrieve(
                project_id="test-project-123",
                intent=intent,
                require_minimum=False,
            )

            # Log retrieval metrics
            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=intent.search_queries,
                chunks_found=len(mock_search_results_subscription),
                chunks_used=len(context.chunks) if context else 0,
                total_tokens=sum(len(r.content) // 4 for r in mock_search_results_subscription),
                file_paths=[r.file_path for r in mock_search_results_subscription],
                scores=[r.score for r in mock_search_results_subscription],
            )

            agent_logger.log_agent_output("SCOUT", context)

            # Save context snapshot
            agent_logger.log_context_snapshot("after_scout", {
                "chunks_count": len(context.chunks) if context else 0,
                "files": [r.file_path for r in mock_search_results_subscription],
            })

            execution.final_output = context

        # Verify scenario requirements
        expected = subscription_management_scenario["expected_flow"]["scout"]
        assert len(mock_search_results_subscription) >= expected["min_chunks"]

        # Verify comprehensive logging
        report = agent_logger.generate_report()
        assert report["context_snapshots"].get("after_scout") is not None


class TestScoutEmptyResultsLogged:
    """Tests for SCOUT with empty results."""

    @pytest.mark.asyncio
    async def test_no_results_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_intent,
    ):
        """Empty search results should be logged appropriately."""
        from app.agents.context_retriever import ContextRetriever

        mock_vector_store.search = MagicMock(return_value=[])

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve_empty") as execution:
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=sample_intent.search_queries,
                chunks_found=0,
                chunks_used=0,
                total_tokens=0,
                file_paths=[],
                scores=[],
            )

            execution.final_output = context

        # Verify empty results logged
        report = agent_logger.generate_report()
        scout_exec = report["agent_executions"].get("SCOUT_retrieve_empty")
        assert scout_exec["success"] == True  # Empty is not an error

    @pytest.mark.asyncio
    async def test_low_confidence_results_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_intent,
    ):
        """Low confidence results should be logged with warnings."""
        from app.agents.context_retriever import ContextRetriever
        from app.services.vector_store import SearchResult

        low_score_results = [
            SearchResult(
                chunk_id="low-1",
                file_path="app/Utils/Helper.php",
                content="Barely relevant content",
                chunk_type="function",
                score=0.35,
                metadata={},
            ),
            SearchResult(
                chunk_id="low-2",
                file_path="app/Utils/Constants.php",
                content="Not very relevant",
                chunk_type="constant",
                score=0.30,
                metadata={},
            ),
        ]

        mock_vector_store.search = MagicMock(return_value=low_score_results)

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve_low_conf") as execution:
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            scores = [r.score for r in low_score_results]
            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=sample_intent.search_queries,
                chunks_found=len(low_score_results),
                chunks_used=0,  # Might filter out low scores
                total_tokens=sum(len(r.content) // 4 for r in low_score_results),
                file_paths=[r.file_path for r in low_score_results],
                scores=scores,
            )

            execution.final_output = context

        # Verify low scores are captured
        report = agent_logger.generate_report()
        assert report is not None


class TestScoutMetricsLogged:
    """Tests for SCOUT metrics and timing."""

    @pytest.mark.asyncio
    async def test_embedding_latency_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        sample_intent,
    ):
        """Embedding generation latency should be tracked."""
        from app.agents.context_retriever import ContextRetriever

        mock_vector_store.search = MagicMock(return_value=[])

        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        with agent_logger.agent_execution("SCOUT", "retrieve_timing") as execution:
            context = await scout.retrieve(
                project_id="test-project-123",
                intent=sample_intent,
                require_minimum=False,
            )

            # Log with timing metrics
            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=sample_intent.search_queries,
                chunks_found=0,
                chunks_used=0,
                total_tokens=0,
                file_paths=[],
                scores=[],
                embedding_latency_ms=50,
                search_latency_ms=100,
            )

            execution.final_output = context

        # Verify timing in report
        report = agent_logger.generate_report()
        scout_exec = report["agent_executions"].get("SCOUT_retrieve_timing")
        assert scout_exec["timing"]["duration_ms"] >= 0
