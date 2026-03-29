"""Example usage of draft_writer sub-agent."""

import asyncio
import json

from app.sub_agents.draft_writer import draft_writer_service


async def example_usage():
    """Example: generate draft replies for different query types."""
    
    queries = [
        "How do I install Directorist?",  # Tier 1 - Basic
        "How do I connect Stripe payments to Directorist?",  # Tier 2 - Configuration
        "Listings not showing after plugin update",  # Tier 3 - Troubleshooting
        "Write a hook to add a field after the listing title",  # Tier 4 - Code
    ]
    
    for query in queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        try:
            result = await draft_writer_service.generate_draft(
                user_query=query,
                use_cache=False,  # Fresh classification for demo
            )
            
            print(f"\nTier: {result['tier']}")
            print(f"Model: {result['model']}")
            print(f"Confidence: {result['confidence']:.2f}")
            print(f"Chunks Used: {result['chunks_used']}")
            print(f"\nClassification:")
            print(json.dumps(result['classification'], indent=2))
            print(f"\nDraft Reply:")
            print(result['draft'])
            
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
