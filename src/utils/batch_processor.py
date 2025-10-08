# src/utils/batch_processor.py
import asyncio
from typing import List, Callable, Any, TypeVar
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')

class BatchProcessor:
    """
    Utility for processing items in batches with rate limiting.
    Optimizes external API calls.
    """
    
    def __init__(
        self,
        batch_size: int = 100,
        rate_limit: float = 0.34,  # seconds between batches
        max_retries: int = 3
    ):
        self.batch_size = batch_size
        self.rate_limit = rate_limit
        self.max_retries = max_retries
    
    async def process_batches(
        self,
        items: List[T],
        process_func: Callable[[List[T]], List[R]]
    ) -> List[R]:
        """
        Process items in batches with rate limiting.
        
        Args:
            items: List of items to process
            process_func: Async function that processes a batch
            
        Returns:
            Flattened list of all results
        """
        all_results = []
        
        # Split into batches
        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]
        
        logger.info(f"Processing {len(items)} items in {len(batches)} batches")
        
        for idx, batch in enumerate(batches):
            retry_count = 0
            
            while retry_count <= self.max_retries:
                try:
                    batch_results = await process_func(batch)
                    all_results.extend(batch_results)
                    
                    # Rate limiting (except for last batch)
                    if idx < len(batches) - 1:
                        await asyncio.sleep(self.rate_limit)
                    
                    break  # Success, exit retry loop
                
                except Exception as e:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error(f"Batch {idx} failed after {self.max_retries} retries: {str(e)}")
                        # Add error results for failed batch
                        all_results.extend([
                            {'error': str(e), 'item': item} 
                            for item in batch
                        ])
                    else:
                        logger.warning(f"Batch {idx} failed, retrying ({retry_count}/{self.max_retries})")
                        await asyncio.sleep(self.rate_limit * retry_count)  # Exponential backoff
        
        return all_results