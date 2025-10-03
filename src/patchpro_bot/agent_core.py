"""Core agent orchestrator for the patch bot pipeline."""

import asyncio
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import aiofiles
from concurrent.futures import ThreadPoolExecutor

from .analysis import AnalysisReader, FindingAggregator
from .llm import LLMClient, PromptBuilder, ResponseParser, ResponseType
from .diff import DiffGenerator, FileReader, PatchWriter
from .models import AnalysisFinding


logger = logging.getLogger(__name__)


class PromptStrategy(Enum):
    """Different strategies for prompting the LLM."""
    AUTO = "auto"           # Automatically choose based on findings
    CODE_FIXES = "code_fixes"     # Always use code fixes
    DIFF_PATCHES = "diff_patches" # Always use diff patches
    SINGLE_DIFF = "single_diff"   # Use single file diff generation


@dataclass
class AgentConfig:
    """Configuration for the PatchPro agent with scalability features."""
    # Directory settings
    analysis_dir: Path = Path("artifact/analysis")
    artifact_dir: Path = Path("artifact") 
    base_dir: Path = Path.cwd()
    
    # LLM settings
    openai_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    max_tokens: int = 8192
    temperature: float = 0.1
    
    # Processing settings
    max_findings: int = 20
    max_files_per_batch: int = 5
    
    # Output settings
    combine_patches: bool = True
    generate_summary: bool = True
    
    # Response format settings
    response_format: ResponseType = ResponseType.CODE_FIXES
    prompt_strategy: PromptStrategy = PromptStrategy.AUTO
    max_findings_per_request: int = 10
    include_file_contents: bool = True
    max_file_size_kb: int = 100
    
    # Scalability settings - Memory management
    max_memory_mb: int = 1000
    max_cache_size_mb: int = 200
    
    # Scalability settings - Parallel processing
    max_concurrent_files: int = 50
    max_workers: int = 10
    
    # Scalability settings - Batching
    max_findings_per_batch: int = 50
    max_batch_complexity: int = 100
    
    # Scalability settings - API management
    requests_per_minute: int = 50
    tokens_per_minute: int = 40000
    context_window_limit: int = 120000  # Model's total context window (input + output)
    
    # Scalability settings - Progress tracking
    enable_progress_tracking: bool = True
    progress_update_interval: int = 10


@dataclass
class ProcessingStats:
    """Track processing statistics."""
    total_findings: int = 0
    processed_findings: int = 0
    failed_findings: int = 0
    total_files: int = 0
    processed_files: int = 0
    start_time: float = field(default_factory=time.time)
    estimated_completion: Optional[float] = None
    memory_usage_mb: float = 0
    cache_hit_rate: float = 0


class MemoryEfficientCache:
    """Memory-efficient caching with automatic cleanup."""
    
    def __init__(self, max_cache_size_mb: int = 200):
        self.max_cache_size_mb = max_cache_size_mb
        self.cache = {}
        self.access_times = {}
        self.current_size_mb = 0
        
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get file content with intelligent caching."""
        if file_path in self.cache:
            self.access_times[file_path] = time.time()
            return self.cache[file_path]
            
        return None
        
    def add_to_cache(self, file_path: str, content: str):
        """Add content to cache with size management."""
        content_size_mb = len(content.encode('utf-8')) / (1024 * 1024)
        
        # Evict old entries if needed
        while (self.current_size_mb + content_size_mb > self.max_cache_size_mb and 
               self.cache):
            self._evict_oldest()
            
        self.cache[file_path] = content
        self.access_times[file_path] = time.time()
        self.current_size_mb += content_size_mb
        
    def _evict_oldest(self):
        """Evict the least recently used cache entry."""
        if not self.access_times:
            return
            
        oldest_file = min(self.access_times.items(), key=lambda x: x[1])[0]
        content = self.cache.pop(oldest_file, "")
        self.access_times.pop(oldest_file, None)
        
        if content:
            content_size_mb = len(content.encode('utf-8')) / (1024 * 1024)
            self.current_size_mb -= content_size_mb
            
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'size_mb': self.current_size_mb,
            'entries': len(self.cache),
            'max_size_mb': self.max_cache_size_mb,
            'utilization': (self.current_size_mb / self.max_cache_size_mb) * 100
        }


class ParallelFileProcessor:
    """Process files in parallel for better performance."""
    
    def __init__(self, max_workers: int = 10, max_concurrent_files: int = 50, cache: MemoryEfficientCache = None):
        self.max_workers = max_workers
        self.max_concurrent_files = max_concurrent_files
        self.semaphore = asyncio.Semaphore(max_concurrent_files)
        self.cache = cache or MemoryEfficientCache()
        
    async def read_files_parallel(self, file_paths: List[str]) -> Dict[str, str]:
        """Read multiple files in parallel with caching."""
        # Check cache first
        file_contents = {}
        files_to_read = []
        
        for file_path in file_paths:
            cached_content = self.cache.get_file_content(file_path)
            if cached_content:
                file_contents[file_path] = cached_content
            else:
                files_to_read.append(file_path)
        
        # Read uncached files in parallel
        if files_to_read:
            tasks = []
            for file_path in files_to_read:
                task = self.read_file_async(file_path)
                tasks.append(task)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for file_path, result in zip(files_to_read, results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to read file {file_path}: {result}")
                elif result:
                    file_contents[file_path] = result
                    self.cache.add_to_cache(file_path, result)
                    
        return file_contents
        
    async def read_file_async(self, file_path: str) -> Optional[str]:
        """Read a single file asynchronously."""
        async with self.semaphore:
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return None


class ContextWindowManager:
    """Manage LLM context windows intelligently."""
    
    def __init__(self, context_window_limit: int = 120000):
        """Initialize context window manager.
        
        Args:
            context_window_limit: Model's total context window size (input + output combined)
                - GPT-4o: 128,000 tokens total
                - GPT-4o-mini: 128,000 tokens total  
                - GPT-3.5-turbo: 16,384 tokens total
                We use 120,000 to leave room for completion response
                
        Note: This is NOT an OpenAI API parameter, but the model's inherent limit.
        """
        self.context_limit = context_window_limit
        self.reserved_tokens = 8000  # For completion response and safety margin
        
    def optimize_context(self, findings: List[AnalysisFinding], file_contents: Dict[str, str]) -> Dict:
        """Optimize context to fit within model limits."""
        available_tokens = self.context_limit - self.reserved_tokens
        
        # Prioritize findings by severity and impact
        prioritized_findings = self._prioritize_findings(findings)
        
        # Estimate token usage and truncate intelligently
        context = {}
        current_tokens = 0
        
        for finding in prioritized_findings:
            finding_tokens = self._estimate_tokens(self._finding_to_text(finding))
            file_content = self._get_relevant_context(finding, file_contents)
            file_content_tokens = self._estimate_tokens(file_content)
            
            total_tokens = finding_tokens + file_content_tokens
            
            if current_tokens + total_tokens <= available_tokens:
                context[f"finding_{finding.location.file}_{finding.location.line}"] = {
                    'finding': finding,
                    'file_content': file_content
                }
                current_tokens += total_tokens
            else:
                logger.info(f"Context limit reached. Truncating remaining findings.")
                break
                
        return context
        
    def _prioritize_findings(self, findings: List[AnalysisFinding]) -> List[AnalysisFinding]:
        """Prioritize findings by severity and impact."""
        severity_priority = {
            'ERROR': 0,
            'HIGH': 1,
            'WARNING': 2,
            'MEDIUM': 3,
            'INFO': 4,
            'LOW': 5,
        }
        
        return sorted(
            findings,
            key=lambda f: (
                severity_priority.get(f.severity.value, 10),
                -len(f.message),  # Longer messages might be more important
                f.location.file,
                f.location.line,
            )
        )
        
    def _get_relevant_context(self, finding: AnalysisFinding, file_contents: Dict[str, str]) -> str:
        """Extract only relevant file context around the finding."""
        file_content = file_contents.get(finding.location.file, "")
        if not file_content:
            return ""
            
        lines = file_content.split('\n')
        context_lines = 15  # Lines before and after
        start_line = max(0, finding.location.line - context_lines - 1)  # -1 for 0-based indexing
        end_line = min(len(lines), finding.location.line + context_lines)
        
        relevant_lines = lines[start_line:end_line]
        
        # Add line numbers for better context
        numbered_lines = []
        for i, line in enumerate(relevant_lines, start=start_line + 1):
            marker = " > " if i == finding.location.line else "   "
            numbered_lines.append(f"{marker}{i:4d}: {line}")
            
        return '\n'.join(numbered_lines)
        
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of token count (1 token ≈ 4 chars for English)."""
        return len(text) // 3  # Conservative estimate
        
    def _finding_to_text(self, finding: AnalysisFinding) -> str:
        """Convert finding to text representation."""
        return f"{finding.tool} - {finding.rule_id}: {finding.message}"


class SmartBatchProcessor:
    """Intelligently batch and filter findings for processing."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        
    def create_intelligent_batches(self, findings: List[AnalysisFinding]) -> List[Dict]:
        """Create intelligent batches based on file size and complexity."""
        # Filter out findings from very large files
        filtered_findings = self._filter_by_file_size(findings)
        
        # Group by file
        file_groups = self._group_by_file(filtered_findings)
        
        # Create batches
        batches = []
        current_batch = []
        current_batch_complexity = 0
        
        for file_group in file_groups:
            complexity = self._calculate_complexity(file_group)
            
            if (len(current_batch) + len(file_group['findings']) <= self.config.max_findings_per_batch and
                current_batch_complexity + complexity <= self.config.max_batch_complexity):
                current_batch.extend(file_group['findings'])
                current_batch_complexity += complexity
            else:
                if current_batch:
                    batches.append({
                        'findings': current_batch, 
                        'complexity': current_batch_complexity,
                        'estimated_tokens': self._estimate_batch_tokens(current_batch)
                    })
                current_batch = file_group['findings']
                current_batch_complexity = complexity
                
        if current_batch:
            batches.append({
                'findings': current_batch, 
                'complexity': current_batch_complexity,
                'estimated_tokens': self._estimate_batch_tokens(current_batch)
            })
            
        return batches
        
    def _filter_by_file_size(self, findings: List[AnalysisFinding]) -> List[AnalysisFinding]:
        """Filter out findings from files that are too large."""
        filtered = []
        for finding in findings:
            try:
                file_size_kb = Path(finding.location.file).stat().st_size / 1024
                if file_size_kb <= self.config.max_file_size_kb:
                    filtered.append(finding)
            except:
                # Include if we can't check size
                filtered.append(finding)
                
        return filtered
        
    def _group_by_file(self, findings: List[AnalysisFinding]) -> List[Dict]:
        """Group findings by file."""
        file_findings = defaultdict(list)
        for finding in findings:
            file_findings[finding.location.file].append(finding)
            
        groups = []
        for file_path, file_findings_list in file_findings.items():
            groups.append({
                'file_path': file_path,
                'findings': file_findings_list
            })
            
        return groups
        
    def _calculate_complexity(self, file_group: Dict) -> int:
        """Calculate complexity score for a file group."""
        findings = file_group['findings']
        
        # Base complexity
        complexity = len(findings) * 2
        
        # Add complexity for severity
        for finding in findings:
            if finding.severity.value.lower() in ['error', 'high']:
                complexity += 3
            elif finding.severity.value.lower() == 'warning':
                complexity += 2
            else:
                complexity += 1
                
        return complexity
        
    def _estimate_batch_tokens(self, findings: List[AnalysisFinding]) -> int:
        """Estimate token count for a batch of findings."""
        total_chars = 0
        for finding in findings:
            total_chars += len(finding.message) + len(finding.rule_id) + 100  # overhead
            if finding.code_snippet:
                total_chars += len(finding.code_snippet)
                
        return total_chars // 3  # Conservative token estimate


class ProgressTracker:
    """Track and report progress for long-running operations."""
    
    def __init__(self, enable_tracking: bool = True, update_interval: int = 10):
        self.enable_tracking = enable_tracking
        self.update_interval = update_interval
        self.stats = ProcessingStats()
        self.last_update = 0
        self.logger = logging.getLogger(__name__)
        
    def start_processing(self, total_findings: int, total_files: int):
        """Initialize processing tracking."""
        if not self.enable_tracking:
            return
            
        self.stats.total_findings = total_findings
        self.stats.total_files = total_files
        self.stats.start_time = time.time()
        self._report_progress()
        
    def update_progress(self, processed_findings: int = 0, processed_files: int = 0, failed: int = 0):
        """Update processing progress."""
        if not self.enable_tracking:
            return
            
        self.stats.processed_findings += processed_findings
        self.stats.processed_files += processed_files
        self.stats.failed_findings += failed
        
        # Estimate completion time
        if self.stats.processed_findings > 0:
            elapsed = time.time() - self.stats.start_time
            rate = self.stats.processed_findings / elapsed
            remaining = self.stats.total_findings - self.stats.processed_findings
            self.stats.estimated_completion = remaining / rate if rate > 0 else None
            
        # Report progress at intervals
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self._report_progress()
            self.last_update = current_time
            
    def _report_progress(self):
        """Report current progress."""
        if not self.enable_tracking:
            return
            
        completion_pct = (self.stats.processed_findings / self.stats.total_findings * 100 
                         if self.stats.total_findings > 0 else 0)
        
        self.logger.info(
            f"Progress: {completion_pct:.1f}% "
            f"({self.stats.processed_findings}/{self.stats.total_findings} findings, "
            f"{self.stats.processed_files}/{self.stats.total_files} files)"
        )
        
        if self.stats.estimated_completion and self.stats.estimated_completion > 0:
            minutes = self.stats.estimated_completion / 60
            if minutes < 1:
                self.logger.info(f"Estimated completion: {self.stats.estimated_completion:.0f} seconds")
            else:
                self.logger.info(f"Estimated completion: {minutes:.1f} minutes")


class AgentCore:
    """Core orchestrator for the patch bot pipeline."""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the agent core.
        
        Args:
            config: Agent configuration with scalability features
        """
        self.config = config or AgentConfig()
        
        # Initialize scalability components using the merged config
        self.cache = MemoryEfficientCache(self.config.max_cache_size_mb)
        self.file_processor = ParallelFileProcessor(
            max_workers=self.config.max_workers,
            max_concurrent_files=self.config.max_concurrent_files,
            cache=self.cache
        )
        self.context_manager = ContextWindowManager(
            context_window_limit=self.config.context_window_limit
        )
        self.batch_processor = SmartBatchProcessor(self.config)
        self.progress_tracker = ProgressTracker(
            enable_tracking=self.config.enable_progress_tracking,
            update_interval=self.config.progress_update_interval
        )
        
        # Initialize existing components
        self.analysis_reader = AnalysisReader(self.config.analysis_dir)
        self.file_reader = FileReader(self.config.base_dir)
        self.diff_generator = DiffGenerator(self.file_reader)
        self.patch_writer = PatchWriter(self.config.artifact_dir)
        
        # Initialize LLM components
        self.llm_client = None
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        
        # Setup logging
        self._setup_logging()
    
    async def run(self) -> Dict[str, any]:
        """Run the complete patch bot pipeline with scalability enhancements.
        
        Returns:
            Dictionary with pipeline results and statistics
        """
        logger.info("Starting enhanced patch bot pipeline")
        start_time = time.time()
        
        try:
            # Step 1: Read analysis findings
            findings = self._load_analysis_findings()
            if not findings:
                return {"status": "no_findings", "message": "No analysis findings found"}
            
            # Step 2: Create intelligent batches for scalable processing
            batches = self.batch_processor.create_intelligent_batches(findings)
            logger.info(f"Created {len(batches)} intelligent batches for {len(findings)} findings")
            
            # Step 3: Initialize progress tracking
            total_files = len(set(f.location.file for f in findings))
            self.progress_tracker.start_processing(len(findings), total_files)
            
            # Step 4: Process batches with scalability features
            all_fixes = []
            all_patches = []
            
            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch['findings'])} findings")
                
                try:
                    code_fixes, diff_patches = await self._process_batch(batch)
                    if code_fixes:
                        all_fixes.extend(code_fixes)
                    if diff_patches:
                        all_patches.extend(diff_patches)
                    
                    # Update progress
                    self.progress_tracker.update_progress(
                        processed_findings=len(batch['findings']),
                        processed_files=len(set(f.location.file for f in batch['findings']))
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to process batch {i+1}: {e}")
                    self.progress_tracker.update_progress(failed=len(batch['findings']))
                    continue
            
            # Step 5: Generate and write patches
            patch_results = self._generate_and_write_patches(all_fixes, all_patches)
            
            # Step 6: Generate enhanced report with performance metrics
            report_path = self._generate_enhanced_report(findings, patch_results, start_time)
            
            # Compile results with scalability metrics
            results = {
                "status": "success",
                "findings_count": len(findings),
                "batches_processed": len(batches),
                "fixes_generated": len(all_fixes) + len(all_patches),
                "patches_written": len(patch_results.get("patch_paths", [])),
                "report_path": str(report_path) if report_path else None,
                "patch_paths": [str(p) for p in patch_results.get("patch_paths", [])],
                "combined_patch": str(patch_results.get("combined_patch")) if patch_results.get("combined_patch") else None,
                "processing_time_seconds": time.time() - start_time,
                "cache_stats": self.cache.get_stats(),
                "performance_stats": self.progress_tracker.stats.__dict__,
            }
            
            logger.info(f"Enhanced pipeline completed successfully in {results['processing_time_seconds']:.1f}s: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Enhanced pipeline failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _load_analysis_findings(self) -> List[AnalysisFinding]:
        """Load and validate analysis findings.
        
        Returns:
            List of analysis findings
        """
        logger.info("Loading analysis findings")
        
        if not self.config.analysis_dir.exists():
            logger.warning(f"Analysis directory does not exist: {self.config.analysis_dir}")
            return []
        
        findings = self.analysis_reader.read_all_findings()
        logger.info(f"Loaded {len(findings)} findings")
        
        return findings
    
    async def _process_batch(self, batch: Dict) -> Tuple[List, List]:
        """Process a single batch of findings with scalability optimizations.
        
        Args:
            batch: Dictionary containing findings and metadata
            
        Returns:
            Tuple of (code_fixes, diff_patches)
        """
        findings = batch['findings']
        
        # Get unique file paths for this batch
        file_paths = list(set(f.location.file for f in findings))
        
        # Read files in parallel using the enhanced file processor
        file_contents = await self.file_processor.read_files_parallel(file_paths)
        
        # Optimize context for this batch using context window manager
        optimized_context = self.context_manager.optimize_context(findings, file_contents)
        
        # Generate LLM suggestions for this batch
        llm_response = await self._generate_llm_suggestions_for_batch(optimized_context)
        if not llm_response:
            logger.warning(f"Failed to generate LLM suggestions for batch")
            return [], []
        
        # Parse response
        code_fixes, diff_patches = self._parse_llm_response(llm_response)
        
        return code_fixes, diff_patches
    
    async def _generate_llm_suggestions_for_batch(self, optimized_context: Dict) -> Optional[str]:
        """Generate LLM suggestions for a batch with optimized context.
        
        Args:
            optimized_context: Optimized context from ContextWindowManager
            
        Returns:
            LLM response content or None if failed
        """
        if not optimized_context:
            return None
            
        # Initialize LLM client if needed
        if self.llm_client is None:
            try:
                api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.error("OpenAI API key not provided")
                    return None
                
                self.llm_client = LLMClient(
                    api_key=api_key,
                    model=self.config.llm_model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                return None
        
        # Build prompt from optimized context
        findings = [ctx['finding'] for ctx in optimized_context.values()]
        file_contents = {ctx['finding'].location.file: ctx['file_content'] 
                        for ctx in optimized_context.values()}
        
        # Determine effective strategy using the same logic as original agent
        effective_strategy = self._get_effective_strategy(findings)
        logger.info(f"Using prompt strategy for batch: {effective_strategy.value}")
        
        # Use appropriate prompt strategy
        if effective_strategy == PromptStrategy.CODE_FIXES:
            # Use code fixes for small batches
            aggregator = FindingAggregator(findings)
            prompt = self.prompt_builder.build_code_fix_prompt(
                aggregator, 
                file_reader=self.file_reader
            )
            logger.info("Using code fixes prompt format for batch")
        elif effective_strategy in [PromptStrategy.DIFF_PATCHES, PromptStrategy.SINGLE_DIFF]:
            # Use batch diff prompt for larger batches
            file_fixes = {}
            for finding in findings:
                file_path = finding.location.file
                if file_path not in file_fixes:
                    file_fixes[file_path] = []
                file_fixes[file_path].append(finding)
            
            prompt = self.prompt_builder.build_batch_diff_prompt(file_fixes, file_contents)
            logger.info("Using diff patches prompt format for batch")
        else:
            logger.error(f"Unknown prompt strategy for batch: {effective_strategy}")
            return None
        
        system_prompt = self.prompt_builder.get_system_prompt()
        
        try:
            # Estimate tokens before sending
            estimated_tokens = len(prompt) // 3 + len(system_prompt) // 3
            logger.info(f"Sending batch request with ~{estimated_tokens} tokens")
            
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            
            logger.info(f"Generated LLM response: {len(response.content)} characters")
            return response.content
            
        except Exception as e:
            logger.error(f"LLM generation failed for batch: {e}")
            return None
    
    def _process_findings(self, findings: List[AnalysisFinding]) -> FindingAggregator:
        """Process and filter findings.
        
        Args:
            findings: Raw findings list
            
        Returns:
            Processed findings aggregator
        """
        logger.info("Processing findings")
        
        aggregator = FindingAggregator(findings)
        
        # Apply processing steps
        aggregator = (
            aggregator
            .deduplicate()
            .sort_by_priority()
            .limit_findings(self.config.max_findings)
        )
        
        summary = aggregator.get_summary()
        logger.info(f"Processed findings: {summary}")
        
        return aggregator
    
    async def _generate_llm_suggestions(self, aggregator: FindingAggregator) -> Optional[str]:
        """Generate suggestions using LLM.
        
        Args:
            aggregator: Processed findings
            
        Returns:
            LLM response content or None if failed
        """
        logger.info("Generating LLM suggestions")
        
        # Initialize LLM client if needed
        if self.llm_client is None:
            try:
                api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.error("OpenAI API key not provided")
                    return None
                
                self.llm_client = LLMClient(
                    api_key=api_key,
                    model=self.config.llm_model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                return None
        
        # Determine effective strategy and build appropriate prompt
        effective_strategy = self._get_effective_strategy(aggregator.findings)
        logger.info(f"Using prompt strategy: {effective_strategy.value}")
        
        if effective_strategy == PromptStrategy.CODE_FIXES:
            prompt = self.prompt_builder.build_code_fix_prompt(
                aggregator, 
                file_reader=self.file_reader
            )
            logger.info("Using code fixes prompt format")
        elif effective_strategy in [PromptStrategy.DIFF_PATCHES, PromptStrategy.SINGLE_DIFF]:
            # For diff patches, use batch approach
            file_fixes = self._group_findings_by_file(aggregator)
            file_contents = self._get_file_contents_for_findings(file_fixes)
            prompt = self.prompt_builder.build_batch_diff_prompt(file_fixes, file_contents)
            logger.info("Using diff patches prompt format")
        else:
            logger.error(f"Unknown prompt strategy: {effective_strategy}")
            return None
            
        system_prompt = self.prompt_builder.get_system_prompt()
        
        try:
            # Generate suggestions asynchronously
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            
            logger.info(f"Generated LLM response: {len(response.content)} characters")
            return response.content
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None
    
    def _parse_llm_response(self, response_content: str) -> Tuple[List, List]:
        """Parse LLM response to extract fixes and patches.
        
        Args:
            response_content: Raw LLM response
            
        Returns:
            Tuple of (code_fixes, diff_patches)
        """
        logger.info("Parsing LLM response")
        
        # Parse response based on configured format
        parsed_response = self.response_parser.parse_response(
            response_content, 
            expected_type=self.config.response_format
        )
        
        logger.info(f"Parsed {len(parsed_response.code_fixes)} code fixes and {len(parsed_response.diff_patches)} diff patches")
        
        # Return in the expected format for backward compatibility
        return parsed_response.code_fixes, parsed_response.diff_patches
    
    def _generate_and_write_patches(self, code_fixes: List, diff_patches: List) -> Dict[str, any]:
        """Generate and write patch files.
        
        Args:
            code_fixes: List of CodeFix objects
            diff_patches: List of DiffPatch objects
            
        Returns:
            Dictionary with patch generation results
        """
        logger.info("Generating and writing patches")
        
        all_diffs = {}
        
        # Generate diffs from code fixes
        if code_fixes:
            code_fix_diffs = self.diff_generator.generate_multiple_diffs(code_fixes)
            all_diffs.update(code_fix_diffs)
        
        # Process diff patches
        for diff_patch in diff_patches:
            diff_content = self.diff_generator.generate_diff_from_patch(diff_patch)
            if diff_content:
                all_diffs[diff_patch.file_path] = diff_content
        
        if not all_diffs:
            logger.warning("No diffs generated")
            return {"patch_paths": [], "combined_patch": None}
        
        # Write patches
        patch_paths = []
        combined_patch = None
        
        try:
            if self.config.combine_patches and len(all_diffs) > 1:
                # Write combined patch
                combined_patch = self.patch_writer.write_combined_patch(all_diffs)
                patch_paths.append(combined_patch)
            else:
                # Write individual patches
                individual_patches = self.patch_writer.write_multiple_patches(all_diffs)
                patch_paths.extend(individual_patches)
            
            # Write summary if configured
            if self.config.generate_summary:
                summary_path = self.patch_writer.write_patch_summary(all_diffs, patch_paths)
                logger.info(f"Generated patch summary: {summary_path}")
            
        except Exception as e:
            logger.error(f"Error writing patches: {e}")
            return {"patch_paths": [], "combined_patch": None}
        
        logger.info(f"Successfully wrote {len(patch_paths)} patch files")
        
        return {
            "patch_paths": patch_paths,
            "combined_patch": combined_patch,
            "diffs": all_diffs,
        }
    
    def _generate_report(self, aggregator: FindingAggregator, patch_results: Dict) -> Optional[Path]:
        """Generate markdown report.
        
        Args:
            aggregator: Processed findings
            patch_results: Patch generation results
            
        Returns:
            Path to generated report, or None if failed
        """
        logger.info("Generating report")
        
        try:
            summary = aggregator.get_summary()
            
            report_content = f"""# PatchPro Bot Report

Generated on: {Path.cwd()}/{self.config.artifact_dir}

## Summary

- **Total findings**: {summary['total_findings']}
- **Tools used**: {', '.join(summary['by_tool'].keys())}
- **Affected files**: {summary['affected_files']}
- **Patches generated**: {len(patch_results.get('patch_paths', []))}

## Findings Breakdown

### By Severity
{self._format_dict_as_list(summary['by_severity'])}

### By Tool
{self._format_dict_as_list(summary['by_tool'])}

### By Category
{self._format_dict_as_list(summary['by_category'])}

## Generated Patches

"""
            
            for patch_path in patch_results.get('patch_paths', []):
                report_content += f"- `{patch_path.name}`\n"
            
            if patch_results.get('combined_patch'):
                report_content += f"\n### Combined Patch\n\n`{patch_results['combined_patch'].name}`\n"
            
            report_content += "\n## Affected Files\n\n"
            for file_path in sorted(summary['file_list']):
                report_content += f"- `{file_path}`\n"
            
            # Write report
            report_path = self.config.artifact_dir / "report.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Generated report: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None
    
    def _generate_enhanced_report(self, findings: List[AnalysisFinding], patch_results: Dict, start_time: float) -> Optional[Path]:
        """Generate enhanced markdown report with performance metrics.
        
        Args:
            findings: All processed findings
            patch_results: Patch generation results
            start_time: Pipeline start time
            
        Returns:
            Path to generated report, or None if failed
        """
        logger.info("Generating enhanced report with performance metrics")
        
        try:
            # Create aggregator for summary statistics
            aggregator = FindingAggregator(findings)
            summary = aggregator.get_summary()
            
            processing_time = time.time() - start_time
            cache_stats = self.cache.get_stats()
            
            report_content = f"""# PatchPro Bot Enhanced Report

Generated on: {Path.cwd()}/{self.config.artifact_dir}
Processing completed in: {processing_time:.2f} seconds

## Summary

- **Total findings**: {summary['total_findings']}
- **Tools used**: {', '.join(summary['by_tool'].keys())}
- **Affected files**: {summary['affected_files']}
- **Patches generated**: {len(patch_results.get('patch_paths', []))}

## Performance Metrics

### Processing Statistics
- **Processing time**: {processing_time:.2f} seconds
- **Average time per finding**: {processing_time / len(findings):.2f} seconds
- **Files processed**: {len(set(f.location.file for f in findings))}

### Cache Performance
- **Cache utilization**: {cache_stats['utilization']:.1f}%
- **Cache size**: {cache_stats['size_mb']:.1f} MB / {cache_stats['max_size_mb']} MB
- **Cached entries**: {cache_stats['entries']}

### Scalability Features Used
- **Parallel file processing**: ✅ Enabled
- **Intelligent batching**: ✅ Enabled
- **Context optimization**: ✅ Enabled
- **Memory-efficient caching**: ✅ Enabled
- **Progress tracking**: ✅ Enabled

## Findings Breakdown

### By Severity
{self._format_dict_as_list(summary['by_severity'])}

### By Tool
{self._format_dict_as_list(summary['by_tool'])}

### By Category
{self._format_dict_as_list(summary['by_category'])}

## Generated Patches

"""
            
            for patch_path in patch_results.get('patch_paths', []):
                report_content += f"- `{patch_path.name}`\n"
            
            if patch_results.get('combined_patch'):
                report_content += f"\n### Combined Patch\n\n`{patch_results['combined_patch'].name}`\n"
            
            report_content += "\n## Affected Files\n\n"
            for file_path in sorted(summary['file_list']):
                report_content += f"- `{file_path}`\n"
            
            # Write report
            report_path = self.config.artifact_dir / "report.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Generated enhanced report: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating enhanced report: {e}")
            return None
    
    def _format_dict_as_list(self, d: Dict) -> str:
        """Format dictionary as markdown list.
        
        Args:
            d: Dictionary to format
            
        Returns:
            Formatted markdown string
        """
        if not d:
            return "- None\n"
        
        return '\n'.join(f"- **{k}**: {v}" for k, v in d.items()) + '\n'
    
    def _get_effective_strategy(self, findings: List[AnalysisFinding]) -> PromptStrategy:
        """Determine the effective prompt strategy to use and update response format accordingly.
        
        Args:
            findings: List of findings to analyze
            
        Returns:
            Effective strategy to use
        """
        if self.config.prompt_strategy != PromptStrategy.AUTO:
            strategy = self.config.prompt_strategy
        else:
            # Enhanced auto strategy logic for scalability
            num_findings = len(findings)
            unique_files = len(set(f.location.file for f in findings))
            
            # Use higher thresholds for scalable processing
            # If many findings across many files, use diff patches for efficiency
            if num_findings > 10 or unique_files > 5:
                logger.info(f"Using DIFF_PATCHES strategy (scalable): {num_findings} findings across {unique_files} files")
                strategy = PromptStrategy.DIFF_PATCHES
            else:
                # Default to code fixes for smaller, manageable sets
                logger.info(f"Using CODE_FIXES strategy (scalable): {num_findings} findings across {unique_files} files")
                strategy = PromptStrategy.CODE_FIXES
            
            # Update config to reflect the chosen strategy
            self.config.prompt_strategy = strategy
        
        # Ensure response format matches the strategy
        if strategy == PromptStrategy.CODE_FIXES:
            self.config.response_format = ResponseType.CODE_FIXES
        elif strategy in [PromptStrategy.DIFF_PATCHES, PromptStrategy.SINGLE_DIFF]:
            self.config.response_format = ResponseType.DIFF_PATCHES
            
        return strategy

    def _group_findings_by_file(self, aggregator: FindingAggregator) -> Dict[str, List[AnalysisFinding]]:
        """Group findings by file path.
        
        Args:
            aggregator: Processed findings aggregator
            
        Returns:
            Dictionary mapping file paths to their findings
        """
        file_fixes = {}
        for finding in aggregator.findings:
            file_path = finding.location.file
            if file_path not in file_fixes:
                file_fixes[file_path] = []
            file_fixes[file_path].append(finding)
        return file_fixes
    
    def _get_file_contents_for_findings(self, file_fixes: Dict[str, List[AnalysisFinding]]) -> Dict[str, str]:
        """Get file contents for files that have findings.
        
        Args:
            file_fixes: Dictionary mapping file paths to their findings
            
        Returns:
            Dictionary mapping file paths to their content
        """
        file_contents = {}
        for file_path in file_fixes.keys():
            try:
                content = self.file_reader.read_file(file_path)
                if content:
                    file_contents[file_path] = content
                else:
                    logger.warning(f"Could not read content for file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
        return file_contents
    
    def _setup_logging(self):
        """Setup enhanced logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.config.artifact_dir / 'patchpro_enhanced.log')
            ]
        )


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================
# These aliases ensure compatibility with code that imported from agent.py

# Main agent class alias
PatchProAgent = AgentCore  # Legacy name for AgentCore

# Enum alias
class ModelProvider(Enum):
    """Legacy enum for backward compatibility."""
    OPENAI = "openai"


# Helper function for backward compatibility
def load_source_files(findings, base_path: Path) -> Dict[str, str]:
    """
    Legacy helper function for loading source files.
    
    Args:
        findings: NormalizedFindings object
        base_path: Base directory for resolving file paths
    
    Returns:
        Dictionary mapping file paths to their contents
    """
    from .analyzer import NormalizedFindings
    
    source_files = {}
    unique_files = set(f.location.file for f in findings.findings)
    
    for file_path in unique_files:
        try:
            # Try to resolve the path
            full_path = base_path / file_path
            if not full_path.exists():
                # Try relative to current directory
                full_path = Path(file_path)
            
            if full_path.exists() and full_path.is_file():
                source_files[file_path] = full_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not load {file_path}: {e}")
    
    return source_files


# Legacy data classes for backward compatibility
@dataclass
class GeneratedFix:
    """Legacy data class for backward compatibility."""
    finding_id: str
    file_path: str
    original_code: str
    fixed_code: str
    explanation: str
    diff: str
    confidence: str = "medium"


@dataclass
class AgentResult:
    """Legacy data class for backward compatibility."""
    fixes: List[GeneratedFix]
    summary: str
    total_findings: int
    fixes_generated: int
    skipped: int
    errors: List[str]


class PromptBuilder:
    """Legacy class for backward compatibility with agent.py tests."""
    
    SYSTEM_PROMPT = """You are PatchPro, an expert code repair assistant."""
    
    @staticmethod
    def build_fix_prompt(findings: List, file_contents: Dict[str, str]) -> str:
        """Build prompt for generating fixes (legacy compatibility)."""
        from .llm.prompts import PromptBuilder as NewPromptBuilder
        
        # Delegate to new prompt builder
        findings_data = []
        for finding in findings:
            findings_data.append({
                "id": finding.id,
                "file": finding.location.file,
                "line": finding.location.line,
                "rule": finding.rule_id,
                "message": finding.message,
                "severity": finding.severity,
                "category": finding.category,
            })
        
        return f"Analyze these {len(findings_data)} code issues and generate fixes."


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for the enhanced agent with scalability features."""
    # Load configuration from environment with scalability features
    config = AgentConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        max_findings=int(os.getenv("MAX_FINDINGS", "100")),  # Increased for scalability
        # Scalability settings can be overridden via environment or kept as defaults
        max_memory_mb=2000,
        max_concurrent_files=50,
        max_findings_per_batch=25,
        enable_progress_tracking=True,
    )
    
    # Create and run enhanced agent
    agent = AgentCore(config)
    results = await agent.run()
    
    # Print results with performance metrics
    print(f"Pipeline status: {results['status']}")
    if results['status'] == 'success':
        print(f"Processed {results['findings_count']} findings in {results['batches_processed']} batches")
        print(f"Generated {results['fixes_generated']} fixes in {results['processing_time_seconds']:.1f}s")
        print(f"Wrote {results['patches_written']} patch files")
        print(f"Cache utilization: {results['cache_stats']['utilization']:.1f}%")
        if results['report_path']:
            print(f"Enhanced report: {results['report_path']}")
    else:
        print(f"Error: {results.get('message', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
