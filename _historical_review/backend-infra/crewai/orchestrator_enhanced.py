#!/usr/bin/env python3
"""
Empire v7.2 - Enhanced Orchestrator with Advanced Decision Logic
Includes integration with Mac Studio local processing and intelligent routing
"""

import json
import os
from typing import Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path
import hashlib

class ContentAnalyzer:
    """Advanced content analysis for intelligent routing decisions"""

    def __init__(self):
        self.privacy_keywords = [
            'confidential', 'proprietary', 'internal', 'restricted',
            'personal', 'private', 'sensitive', 'pii', 'phi', 'hipaa'
        ]

        self.complexity_indicators = {
            'simple': ['basic', 'simple', 'quick', 'easy', 'straightforward'],
            'moderate': ['standard', 'typical', 'common', 'regular'],
            'complex': ['advanced', 'complex', 'sophisticated', 'multi-step', 'framework']
        }

        self.asset_indicators = {
            'skill': [
                'automate', 'automation', 'workflow', 'process', 'routine',
                'repetitive', 'task', 'operation', 'procedure', 'script'
            ],
            'command': [
                'quick', 'shortcut', 'alias', 'snippet', 'one-liner',
                'simple command', 'utility', 'helper', 'tool'
            ],
            'agent': [
                'analyze', 'research', 'investigate', 'evaluate', 'assess',
                'review', 'examine', 'study', 'explore', 'intelligent'
            ],
            'prompt': [
                'template', 'format', 'structure', 'pattern', 'example',
                'boilerplate', 'scaffold', 'outline', 'model', 'guide'
            ],
            'workflow': [
                'pipeline', 'sequence', 'flow', 'chain', 'integration',
                'orchestrate', 'coordinate', 'synchronize', 'connect'
            ]
        }

    def analyze_privacy_level(self, content: str) -> str:
        """Determine if content requires local-only processing"""
        content_lower = content.lower()

        for keyword in self.privacy_keywords:
            if keyword in content_lower:
                return "local_only"

        # Check for patterns that indicate sensitive data
        if self._contains_pii(content):
            return "local_only"

        return "cloud_eligible"

    def _contains_pii(self, content: str) -> bool:
        """Check for PII patterns (simplified)"""
        import re

        # SSN pattern
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b', content):
            return True

        # Email pattern
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content):
            return True

        # Phone number pattern
        if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', content):
            return True

        return False

    def assess_complexity(self, content: str) -> str:
        """Assess content complexity level"""
        content_lower = content.lower()

        scores = {
            'simple': 0,
            'moderate': 0,
            'complex': 0
        }

        for level, indicators in self.complexity_indicators.items():
            for indicator in indicators:
                if indicator in content_lower:
                    scores[level] += 1

        # Additional complexity factors
        if len(content) > 5000:
            scores['complex'] += 2
        elif len(content) > 2000:
            scores['moderate'] += 1
        else:
            scores['simple'] += 1

        # Count technical indicators
        technical_terms = ['api', 'database', 'algorithm', 'architecture', 'framework']
        tech_count = sum(1 for term in technical_terms if term in content_lower)
        if tech_count > 3:
            scores['complex'] += 2
        elif tech_count > 1:
            scores['moderate'] += 1

        return max(scores, key=scores.get)

    def suggest_asset_types(self, content: str, context: Dict = None) -> List[str]:
        """Suggest appropriate asset types based on content analysis"""
        content_lower = content.lower()
        suggestions = []
        scores = {}

        for asset_type, indicators in self.asset_indicators.items():
            score = sum(1 for indicator in indicators if indicator in content_lower)
            if score > 0:
                scores[asset_type] = score

        # Sort by score and take top suggestions
        sorted_assets = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Always include at least a prompt as fallback
        if not sorted_assets:
            return ['prompt']

        # Take assets with significant scores
        max_score = sorted_assets[0][1]
        for asset, score in sorted_assets:
            if score >= max_score * 0.5:  # Within 50% of max score
                suggestions.append(asset)

        # Special rules
        if context:
            if context.get('is_educational', False):
                if 'agent' not in suggestions:
                    suggestions.append('agent')  # Educational content often needs analysis agents

            if context.get('has_repetitive_tasks', False):
                if 'skill' not in suggestions:
                    suggestions.insert(0, 'skill')  # Prioritize automation

        return suggestions[:3]  # Return top 3 suggestions

class DepartmentRouter:
    """Intelligent department classification with ML-like scoring"""

    def __init__(self):
        self.department_keywords = {
            'it-engineering': {
                'primary': ['code', 'api', 'software', 'development', 'programming', 'database', 'backend', 'frontend'],
                'secondary': ['git', 'docker', 'kubernetes', 'cloud', 'aws', 'azure', 'devops'],
                'weight': 1.0
            },
            'sales-marketing': {
                'primary': ['sales', 'marketing', 'lead', 'customer', 'campaign', 'crm', 'pipeline', 'revenue'],
                'secondary': ['funnel', 'conversion', 'prospect', 'outreach', 'brand', 'seo'],
                'weight': 1.0
            },
            'customer-support': {
                'primary': ['support', 'ticket', 'helpdesk', 'service', 'issue', 'resolution', 'complaint'],
                'secondary': ['escalation', 'sla', 'satisfaction', 'response', 'chat', 'call'],
                'weight': 1.0
            },
            'operations-hr-supply': {
                'primary': ['operations', 'hr', 'human resources', 'supply', 'logistics', 'warehouse', 'inventory'],
                'secondary': ['recruitment', 'hiring', 'employee', 'benefits', 'payroll', 'shipping'],
                'weight': 1.0
            },
            'finance-accounting': {
                'primary': ['finance', 'accounting', 'budget', 'financial', 'expense', 'revenue', 'profit'],
                'secondary': ['invoice', 'payment', 'tax', 'audit', 'forecast', 'cash flow'],
                'weight': 1.0
            },
            'project-management': {
                'primary': ['project', 'management', 'agile', 'scrum', 'milestone', 'gantt', 'sprint'],
                'secondary': ['stakeholder', 'timeline', 'deliverable', 'resource', 'planning'],
                'weight': 1.0
            },
            'real-estate': {
                'primary': ['real estate', 'property', 'lease', 'tenant', 'rental', 'mortgage', 'building'],
                'secondary': ['landlord', 'apartment', 'commercial', 'residential', 'listing'],
                'weight': 1.0
            },
            'private-equity-ma': {
                'primary': ['private equity', 'merger', 'acquisition', 'valuation', 'investment', 'portfolio'],
                'secondary': ['due diligence', 'lbo', 'ebitda', 'multiple', 'exit', 'fund'],
                'weight': 1.0
            },
            'consulting': {
                'primary': ['consulting', 'strategy', 'advisory', 'analysis', 'recommendation', 'assessment'],
                'secondary': ['framework', 'methodology', 'engagement', 'client', 'solution'],
                'weight': 1.0
            },
            'personal-continuing-ed': {
                'primary': ['education', 'learning', 'course', 'training', 'skill', 'personal', 'development'],
                'secondary': ['certification', 'online', 'tutorial', 'workshop', 'webinar'],
                'weight': 1.0
            }
        }

    def classify(self, content: str, filename: str = None) -> Tuple[str, float]:
        """
        Classify content into department with confidence score
        Returns: (department, confidence_score)
        """
        content_lower = content.lower()
        scores = {}

        # Analyze content against each department
        for dept, keywords in self.department_keywords.items():
            score = 0.0

            # Primary keywords (higher weight)
            for keyword in keywords['primary']:
                if keyword in content_lower:
                    score += 2.0 * keywords['weight']

            # Secondary keywords (lower weight)
            for keyword in keywords['secondary']:
                if keyword in content_lower:
                    score += 1.0 * keywords['weight']

            # Filename hints
            if filename and dept.replace('-', '_') in filename.lower():
                score += 3.0

            scores[dept] = score

        # Get the best match
        if not scores or max(scores.values()) == 0:
            return '_global', 0.0

        best_dept = max(scores, key=scores.get)
        confidence = scores[best_dept] / sum(scores.values()) if sum(scores.values()) > 0 else 0

        # If confidence is too low, use _global
        if confidence < 0.3:
            return '_global', confidence

        return best_dept, confidence

class ProcessingRouter:
    """Route processing between Mac Studio and cloud based on various factors"""

    def __init__(self):
        self.mac_studio_capacity = {
            'max_concurrent': 10,
            'gpu_cores': 60,
            'neural_cores': 32,
            'memory_gb': 96,
            'current_load': 0
        }

        self.routing_rules = {
            'video': 'local',  # Always process video locally
            'sensitive': 'local',  # Privacy-sensitive content
            'large_batch': 'local',  # Large batches benefit from local GPU
            'realtime': 'local',  # Real-time processing needs low latency
            'simple_query': 'cloud',  # Simple queries can use cloud
            'web_content': 'cloud'  # Web-scraped content can use cloud
        }

    def determine_route(self, content_type: str, privacy_level: str,
                       complexity: str, size_mb: float) -> Dict[str, Any]:
        """Determine optimal processing route"""

        route = {
            'location': 'local',
            'reason': [],
            'estimated_time': 0,
            'cost': 0.0
        }

        # Privacy check (highest priority)
        if privacy_level == 'local_only':
            route['location'] = 'local'
            route['reason'].append('Privacy requirements')
            route['estimated_time'] = self._estimate_local_time(size_mb, complexity)
            return route

        # Content type routing
        if content_type in self.routing_rules:
            route['location'] = self.routing_rules[content_type]
            route['reason'].append(f'Content type: {content_type}')

        # Complexity-based routing
        if complexity == 'complex' and self.mac_studio_capacity['current_load'] < 70:
            route['location'] = 'local'
            route['reason'].append('Complex processing benefits from local GPU')
        elif complexity == 'simple' and size_mb < 10:
            route['location'] = 'cloud'
            route['reason'].append('Simple task suitable for cloud')
            route['cost'] = 0.001  # Estimated API cost

        # Size-based routing
        if size_mb > 100:
            route['location'] = 'local'
            route['reason'].append('Large file benefits from local processing')

        # Load balancing
        if self.mac_studio_capacity['current_load'] > 80:
            route['location'] = 'cloud'
            route['reason'].append('Mac Studio at high load')
            route['cost'] = size_mb * 0.0001  # Cost per MB

        route['estimated_time'] = self._estimate_time(route['location'], size_mb, complexity)

        return route

    def _estimate_local_time(self, size_mb: float, complexity: str) -> float:
        """Estimate processing time on Mac Studio"""
        base_time = size_mb * 0.1  # 0.1 seconds per MB base

        complexity_multiplier = {
            'simple': 0.5,
            'moderate': 1.0,
            'complex': 2.0
        }

        return base_time * complexity_multiplier.get(complexity, 1.0)

    def _estimate_time(self, location: str, size_mb: float, complexity: str) -> float:
        """Estimate processing time"""
        if location == 'local':
            return self._estimate_local_time(size_mb, complexity)
        else:
            # Cloud processing includes network latency
            return self._estimate_local_time(size_mb, complexity) + 2.0  # +2 seconds for network

class EnhancedOrchestrator:
    """Main orchestrator with all enhanced capabilities"""

    def __init__(self):
        self.content_analyzer = ContentAnalyzer()
        self.department_router = DepartmentRouter()
        self.processing_router = ProcessingRouter()
        self.processing_stats = {
            'total_processed': 0,
            'local_processed': 0,
            'cloud_processed': 0,
            'total_cost': 0.0,
            'time_saved': 0.0
        }

    def process_content(self, content: str, filename: str = None,
                       metadata: Dict = None) -> Dict[str, Any]:
        """
        Main processing pipeline with all decision logic
        """

        # Initialize result structure
        result = {
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'decisions': {},
            'outputs': {},
            'metrics': {}
        }

        # Step 1: Analyze content characteristics
        privacy_level = self.content_analyzer.analyze_privacy_level(content)
        complexity = self.content_analyzer.assess_complexity(content)

        # Step 2: Department classification
        department, confidence = self.department_router.classify(content, filename)

        # Step 3: Asset type suggestions
        context = {
            'is_educational': 'course' in content.lower() or 'training' in content.lower(),
            'has_repetitive_tasks': 'automate' in content.lower() or 'repetitive' in content.lower()
        }
        asset_types = self.content_analyzer.suggest_asset_types(content, context)

        # Step 4: Determine processing route
        size_mb = len(content.encode('utf-8')) / (1024 * 1024)
        content_type = self._detect_content_type(content, filename)
        routing = self.processing_router.determine_route(
            content_type, privacy_level, complexity, size_mb
        )

        # Step 5: Determine if PDF summary needed
        needs_summary = self._should_create_summary(content, complexity, content_type)

        # Compile all decisions
        result['decisions'] = {
            'department': {
                'value': department,
                'confidence': confidence
            },
            'privacy_level': privacy_level,
            'complexity': complexity,
            'asset_types': asset_types,
            'processing_route': routing,
            'needs_summary': needs_summary
        }

        # Generate output paths
        result['outputs'] = self._generate_output_paths(department, asset_types, needs_summary)

        # Calculate metrics
        result['metrics'] = {
            'estimated_processing_time': routing['estimated_time'],
            'estimated_cost': routing['cost'],
            'content_size_mb': size_mb,
            'asset_count': len(asset_types) + (1 if needs_summary else 0)
        }

        # Update statistics
        self._update_stats(routing)

        return result

    def _detect_content_type(self, content: str, filename: str = None) -> str:
        """Detect the type of content"""
        if filename:
            ext = Path(filename).suffix.lower()
            if ext in ['.mp4', '.mov', '.avi']:
                return 'video'
            elif ext in ['.pdf', '.doc', '.docx']:
                return 'document'
            elif ext in ['.py', '.js', '.java']:
                return 'code'

        # Content-based detection
        if 'http' in content and 'www' in content:
            return 'web_content'
        elif 'def ' in content or 'function ' in content:
            return 'code'

        return 'general'

    def _should_create_summary(self, content: str, complexity: str, content_type: str) -> bool:
        """Determine if a PDF summary should be created"""

        # Always summarize certain content types
        if content_type in ['video', 'document']:
            return True

        # Educational content
        educational_keywords = ['course', 'lesson', 'module', 'training', 'tutorial', 'workshop']
        if any(keyword in content.lower() for keyword in educational_keywords):
            return True

        # Complex content benefits from summary
        if complexity == 'complex' and len(content) > 3000:
            return True

        # Content with structured data
        if 'table' in content.lower() or '|' in content:
            return True

        return False

    def _generate_output_paths(self, department: str, asset_types: List[str],
                               needs_summary: bool) -> Dict[str, str]:
        """Generate output file paths"""
        paths = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if needs_summary:
            paths['summary'] = f"processed/crewai-summaries/{department}/{department}_summary_{timestamp}.pdf"

        for asset_type in asset_types:
            asset_name = f"{department}_{asset_type}_{timestamp}"
            if asset_type == 'skill':
                paths[asset_type] = f"processed/crewai-suggestions/claude-skills/drafts/{asset_name}.yaml"
            elif asset_type == 'command':
                paths[asset_type] = f"processed/crewai-suggestions/claude-commands/drafts/{asset_name}.md"
            elif asset_type == 'agent':
                paths[asset_type] = f"processed/crewai-suggestions/agents/drafts/{asset_name}.yaml"
            elif asset_type == 'prompt':
                paths[asset_type] = f"processed/crewai-suggestions/prompts/drafts/{asset_name}.md"
            elif asset_type == 'workflow':
                paths[asset_type] = f"processed/crewai-suggestions/workflows/drafts/{asset_name}.json"

        return paths

    def _update_stats(self, routing: Dict):
        """Update processing statistics"""
        self.processing_stats['total_processed'] += 1

        if routing['location'] == 'local':
            self.processing_stats['local_processed'] += 1
        else:
            self.processing_stats['cloud_processed'] += 1
            self.processing_stats['total_cost'] += routing['cost']

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.processing_stats,
            'local_percentage': (self.processing_stats['local_processed'] /
                               max(self.processing_stats['total_processed'], 1)) * 100,
            'average_cost': self.processing_stats['total_cost'] /
                          max(self.processing_stats['total_processed'], 1)
        }

# Example usage and testing
if __name__ == "__main__":
    orchestrator = EnhancedOrchestrator()

    # Test with sample content
    test_content = """
    Advanced Sales Pipeline Management Framework

    This comprehensive training module covers sophisticated techniques for
    managing enterprise B2B sales pipelines, including:

    - Lead scoring algorithms using ML
    - Opportunity stage optimization
    - Predictive forecasting models
    - CRM automation workflows
    - Integration with marketing automation

    The framework includes detailed implementation guides, Excel templates,
    and Python scripts for sales analytics.
    """

    result = orchestrator.process_content(
        content=test_content,
        filename="sales_pipeline_advanced.pdf"
    )

    print(json.dumps(result, indent=2))

    # Show statistics
    print("\n=== Processing Statistics ===")
    print(json.dumps(orchestrator.get_statistics(), indent=2))