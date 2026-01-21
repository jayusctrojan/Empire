# Task ID: 118

**Title:** Implement chunking strategy factory and registration

**Status:** done

**Dependencies:** 112 ✓, 117 ✓

**Priority:** medium

**Description:** Create a factory pattern for chunking strategies and register the new MarkdownChunkerStrategy

**Details:**

Implement a factory pattern for chunking strategies to allow dynamic selection and registration of strategies, including the new MarkdownChunkerStrategy.

Implementation details:
1. Create a ChunkerStrategyFactory class
2. Implement registration mechanism for chunking strategies
3. Add logic to select the appropriate strategy based on document type
4. Register all existing strategies (semantic, code, transcript)
5. Register the new MarkdownChunkerStrategy
6. Ensure backward compatibility with existing code

Pseudo-code:
```python
class ChunkerStrategyFactory:
    _strategies = {}
    
    @classmethod
    def register_strategy(cls, name, strategy_class):
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get_strategy(cls, name, **kwargs):
        strategy_class = cls._strategies.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown chunking strategy: {name}")
        return strategy_class(**kwargs)
    
    @classmethod
    def get_strategy_for_document(cls, document, **kwargs):
        # Select strategy based on document type
        if is_llamaparse_markdown(document):
            return cls.get_strategy('markdown', **kwargs)
        elif is_code_document(document):
            return cls.get_strategy('code', **kwargs)
        elif is_transcript(document):
            return cls.get_strategy('transcript', **kwargs)
        else:
            return cls.get_strategy('sentence', **kwargs)

# Register strategies
ChunkerStrategyFactory.register_strategy('sentence', SentenceChunkerStrategy)
ChunkerStrategyFactory.register_strategy('code', CodeChunkerStrategy)
ChunkerStrategyFactory.register_strategy('transcript', TranscriptChunkerStrategy)
ChunkerStrategyFactory.register_strategy('markdown', MarkdownChunkerStrategy)
```

**Test Strategy:**

1. Unit test the ChunkerStrategyFactory class
2. Test registration of strategies
3. Test retrieval of strategies by name
4. Test automatic strategy selection based on document type
5. Verify all existing strategies are properly registered
6. Test with various document types to ensure correct strategy selection
