"""
Telemetry infrastructure for PatchPro.

Captures trace logs of LLM interactions for debugging, analysis, and improvement.
Implements Level 2 observability from industry-standard AI systems (Hamel/Jason Liu).
"""
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from .models import AnalysisFinding


logger = logging.getLogger(__name__)


@dataclass
class PatchTrace:
    """Complete trace of a patch generation attempt.
    
    Captures everything needed to understand what happened:
    - What we asked the LLM (prompt, context)
    - What the LLM returned (response, tokens, cost)
    - What validation said (success/failure, specific errors)
    - Metadata for analysis (rule type, file type, complexity)
    """
    
    # Identifiers
    trace_id: str
    timestamp: str  # ISO 8601 format
    
    # Finding context
    rule_id: str
    rule_category: str  # "import-order", "docstring", "unused-import", etc.
    file_path: str
    file_type: str  # ".py", ".js", etc.
    line_number: int
    finding_message: str
    finding_complexity: str  # "simple", "moderate", "complex"
    
    # LLM interaction
    strategy: str  # "generate_single_patch" or "generate_batch_patch"
    prompt: str  # Full prompt sent to LLM
    system_prompt: str  # System instructions
    llm_response: str  # Full LLM response
    model: str  # "gpt-4o-mini", etc.
    
    # Validation
    patch_generated: Optional[str]  # The actual patch content
    validation_passed: bool
    validation_errors: List[str]  # Specific git apply errors
    
    # Retry context
    retry_attempt: int  # 1, 2, 3
    previous_errors: List[str]  # Errors from previous attempt (for feedback loop)
    
    # Performance metrics
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: float
    
    # Outcome
    final_status: str  # "success", "failed", "exhausted_retries"


class PatchTracer:
    """Trace logger for patch generation.
    
    Stores traces in:
    1. SQLite database for queries/analysis
    2. JSON files for human inspection
    
    Usage:
        tracer = PatchTracer()
        
        with tracer.trace_patch_generation(finding, strategy) as trace_ctx:
            # Call LLM
            response = llm.generate(...)
            
            # Update trace
            trace_ctx.set_llm_response(response, tokens, cost, latency)
            trace_ctx.set_patch(patch_content)
            trace_ctx.set_validation(success, errors)
    """
    
    def __init__(self, trace_dir: Optional[Path] = None):
        """Initialize tracer.
        
        Args:
            trace_dir: Directory for trace files (default: .patchpro/traces/)
        """
        self.trace_dir = trace_dir or Path.cwd() / ".patchpro" / "traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite database for queries
        self.db_path = self.trace_dir / "traces.db"
        self._init_database()
        
        logger.info(f"Initialized PatchTracer at {self.trace_dir}")
    
    def _init_database(self):
        """Create SQLite tables for traces."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                timestamp TEXT,
                rule_id TEXT,
                rule_category TEXT,
                file_path TEXT,
                file_type TEXT,
                line_number INTEGER,
                finding_message TEXT,
                finding_complexity TEXT,
                strategy TEXT,
                model TEXT,
                validation_passed BOOLEAN,
                retry_attempt INTEGER,
                tokens_used INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                latency_ms INTEGER,
                cost_usd REAL,
                final_status TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_id ON traces (rule_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON traces (final_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy ON traces (strategy)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON traces (timestamp)")
        
        conn.commit()
        conn.close()
    
    @contextmanager
    def trace_patch_generation(
        self,
        finding: AnalysisFinding,
        strategy: str,
        retry_attempt: int = 1,
        previous_errors: Optional[List[str]] = None
    ):
        """Context manager for tracing a patch generation attempt.
        
        Args:
            finding: The finding being fixed
            strategy: Which tool is being used
            retry_attempt: Attempt number (1, 2, 3)
            previous_errors: Errors from previous attempt (for feedback)
            
        Yields:
            TraceContext: Object to update trace as execution progresses
        """
        # Generate trace ID (use basename to keep filename short)
        from pathlib import Path as PathLib
        file_basename = PathLib(finding.location.file).name
        trace_id = f"{finding.rule_id}_{file_basename}_{finding.location.line}_{retry_attempt}_{int(time.time() * 1000)}"
        
        # Create trace context
        ctx = TraceContext(
            trace_id=trace_id,
            finding=finding,
            strategy=strategy,
            retry_attempt=retry_attempt,
            previous_errors=previous_errors or []
        )
        
        try:
            yield ctx
        finally:
            # Save trace on context exit (success or failure)
            self._save_trace(ctx.build_trace())
    
    def _save_trace(self, trace: PatchTrace):
        """Save trace to both SQLite and JSON.
        
        Args:
            trace: Complete trace object
        """
        # Save to SQLite
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO traces VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            trace.trace_id,
            trace.timestamp,
            trace.rule_id,
            trace.rule_category,
            trace.file_path,
            trace.file_type,
            trace.line_number,
            trace.finding_message,
            trace.finding_complexity,
            trace.strategy,
            trace.model,
            trace.validation_passed,
            trace.retry_attempt,
            trace.tokens_used,
            trace.prompt_tokens,
            trace.completion_tokens,
            trace.latency_ms,
            trace.cost_usd,
            trace.final_status,
        ))
        
        conn.commit()
        conn.close()
        
        # Save to JSON (human-readable)
        json_file = self.trace_dir / f"{trace.trace_id}.json"
        with open(json_file, 'w') as f:
            json.dump(asdict(trace), f, indent=2)
        
        logger.debug(f"Saved trace: {trace.trace_id} ({trace.final_status})")
    
    def query_traces(
        self,
        rule_id: Optional[str] = None,
        status: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query traces from SQLite.
        
        Args:
            rule_id: Filter by rule ID
            status: Filter by final status
            strategy: Filter by strategy
            limit: Max results
            
        Returns:
            List of trace dictionaries
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Return dict-like rows
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT * FROM traces WHERE 1=1"
        params = []
        
        if rule_id:
            query += " AND rule_id = ?"
            params.append(rule_id)
        
        if status:
            query += " AND final_status = ?"
            params.append(status)
        
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics from all traces.
        
        Returns:
            Dictionary with metrics: total traces, success rate, avg cost, etc.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Total traces
        cursor.execute("SELECT COUNT(*) FROM traces")
        total = cursor.fetchone()[0]
        
        # Success rate
        cursor.execute("SELECT COUNT(*) FROM traces WHERE validation_passed = 1")
        successes = cursor.fetchone()[0]
        
        # Average cost
        cursor.execute("SELECT AVG(cost_usd) FROM traces")
        avg_cost = cursor.fetchone()[0] or 0
        
        # Average latency
        cursor.execute("SELECT AVG(latency_ms) FROM traces")
        avg_latency = cursor.fetchone()[0] or 0
        
        # Cost by strategy
        cursor.execute("SELECT strategy, AVG(cost_usd) FROM traces GROUP BY strategy")
        cost_by_strategy = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Most common failures
        cursor.execute("""
            SELECT rule_id, COUNT(*) as count 
            FROM traces 
            WHERE validation_passed = 0 
            GROUP BY rule_id 
            ORDER BY count DESC 
            LIMIT 5
        """)
        top_failures = [{"rule_id": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "total_traces": total,
            "successful_traces": successes,
            "success_rate": successes / total if total > 0 else 0,
            "avg_cost_usd": avg_cost,
            "avg_latency_ms": avg_latency,
            "cost_by_strategy": cost_by_strategy,
            "top_failures": top_failures,
        }


class TraceContext:
    """Context object for building a trace during execution.
    
    Accumulates information as patch generation progresses:
    1. Created with finding + strategy
    2. Update with LLM response + metrics
    3. Update with validation results
    4. Build complete trace at end
    """
    
    def __init__(
        self,
        trace_id: str,
        finding: AnalysisFinding,
        strategy: str,
        retry_attempt: int,
        previous_errors: List[str]
    ):
        """Initialize trace context."""
        self.trace_id = trace_id
        self.timestamp = datetime.utcnow().isoformat()
        self.finding = finding
        self.strategy = strategy
        self.retry_attempt = retry_attempt
        self.previous_errors = previous_errors
        
        # To be filled in
        self.prompt: Optional[str] = None
        self.system_prompt: Optional[str] = None
        self.llm_response: Optional[str] = None
        self.model: Optional[str] = None
        self.tokens_used: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.latency_ms: int = 0
        self.cost_usd: float = 0.0
        self.patch_generated: Optional[str] = None
        self.validation_passed: bool = False
        self.validation_errors: List[str] = []
        self.final_status: str = "unknown"
    
    def set_prompt(self, prompt: str, system_prompt: str):
        """Record the prompt sent to LLM."""
        self.prompt = prompt
        self.system_prompt = system_prompt
    
    def set_llm_response(
        self,
        response: str,
        model: str,
        tokens_used: int,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        cost_usd: float
    ):
        """Record LLM response and metrics."""
        self.llm_response = response
        self.model = model
        self.tokens_used = tokens_used
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms
        self.cost_usd = cost_usd
    
    def set_patch(self, patch_content: Optional[str]):
        """Record generated patch."""
        self.patch_generated = patch_content
    
    def set_validation(self, passed: bool, errors: List[str]):
        """Record validation results."""
        self.validation_passed = passed
        self.validation_errors = errors
        
        # Set final status
        if passed:
            self.final_status = "success"
        elif self.retry_attempt >= 3:
            self.final_status = "exhausted_retries"
        else:
            self.final_status = "failed"
    
    def build_trace(self) -> PatchTrace:
        """Build complete trace object."""
        # Categorize rule
        rule_category = self._categorize_rule(self.finding.rule_id)
        
        # Determine complexity
        complexity = self._determine_complexity(self.finding)
        
        # File type
        file_type = Path(self.finding.location.file).suffix
        
        return PatchTrace(
            trace_id=self.trace_id,
            timestamp=self.timestamp,
            rule_id=self.finding.rule_id,
            rule_category=rule_category,
            file_path=self.finding.location.file,
            file_type=file_type,
            line_number=self.finding.location.line,
            finding_message=self.finding.message,
            finding_complexity=complexity,
            strategy=self.strategy,
            prompt=self.prompt or "",
            system_prompt=self.system_prompt or "",
            llm_response=self.llm_response or "",
            model=self.model or "unknown",
            patch_generated=self.patch_generated,
            validation_passed=self.validation_passed,
            validation_errors=self.validation_errors,
            retry_attempt=self.retry_attempt,
            previous_errors=self.previous_errors,
            tokens_used=self.tokens_used,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            latency_ms=self.latency_ms,
            cost_usd=self.cost_usd,
            final_status=self.final_status,
        )
    
    @staticmethod
    def _categorize_rule(rule_id: str) -> str:
        """Categorize rule for analysis.
        
        Groups rules into broader categories for pattern recognition.
        """
        if rule_id.startswith("I"):
            return "import-order"
        elif rule_id.startswith("F401"):
            return "unused-import"
        elif rule_id.startswith("F"):
            return "pyflakes"
        elif rule_id.startswith("D"):
            return "docstring"
        elif rule_id.startswith("E") or rule_id.startswith("W"):
            return "style"
        elif rule_id.startswith("RET"):
            return "return-logic"
        else:
            return "other"
    
    @staticmethod
    def _determine_complexity(finding: AnalysisFinding) -> str:
        """Estimate finding complexity.
        
        Used to identify which types of fixes are harder for LLM.
        """
        # Simple: single-line changes, mechanical fixes
        simple_rules = ["I001", "F401", "E501", "W291"]
        
        # Complex: multi-line changes, semantic changes
        complex_rules = ["D100", "D101", "D102", "D103"]  # Docstrings
        
        if finding.rule_id in simple_rules:
            return "simple"
        elif finding.rule_id in complex_rules:
            return "complex"
        else:
            return "moderate"
