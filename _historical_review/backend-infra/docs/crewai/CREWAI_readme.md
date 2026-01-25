What would be the files exactly that I should have CrewAI 
look at when configuring agents?  CrewAI_Ouput_guidelines.md 
and what other files 

⏺ Great question! Let me identify the essential files CrewAI
  agents should reference when analyzing courses and
  generating suggestions:

  Essential Files for CrewAI Agent Configuration

  1. Primary Reference Files (MUST READ)

  CREWAI_OUTPUT_GUIDELINES.md - Output standards
  - Filename naming convention
  - Asset type templates (skills, commands, agents, prompts,
  workflows)
  - Quality standards
  - Department codes
  - File size limits

  B2_FOLDER_STRUCTURE.md - Department taxonomy &
  classification context
  - Complete 10-department taxonomy
  - AI classification keywords for each department
  - Subdepartment structure
  - Common course titles per department
  - Classification logic and examples

  empire-arch.txt - System architecture overview
  - Complete Empire architecture
  - Technology stack
  - Service integrations
  - Workflow patterns
  - Input/output formats

  2. Department-Specific Context Files (HIGH VALUE)

  Each department section in B2_FOLDER_STRUCTURE.md contains:
  - Core focus areas
  - AI classification keywords
  - Common course titles
  - Subdepartment breakdowns
  - Real-world examples

  3. Technical Specifications (REFERENCE AS NEEDED)

  01_introduction.md through 10_n8n_orchestration.md
  - Detailed requirements
  - System capabilities
  - Integration patterns
  - Performance targets

  Recommended CrewAI Agent Configuration

  # FILE: crewai_course_analyzer_config.yaml

  agents:
    - name: course_classifier_agent
      role: Course Classification Specialist
      goal: Accurately classify courses into correct
  departments

      knowledge_sources:
        - B2_FOLDER_STRUCTURE.md        # Department taxonomy 
  (CRITICAL)
        - CREWAI_OUTPUT_GUIDELINES.md   # Output format 
  standards
        - empire-arch.txt               # System context

      tools:
        - file_reader
        - department_classifier
        - keyword_extractor

      context: |
        You analyze course content and classify into 1 of 10 
  departments.
        Use B2_FOLDER_STRUCTURE.md for classification keywords
   and logic.
        Output filenames MUST follow: 
  {department}_{name}.{ext}

    - name: skill_generator_agent
      role: Claude Skills Generator
      goal: Generate YAML skill definitions for Claude Code

      knowledge_sources:
        - CREWAI_OUTPUT_GUIDELINES.md   # Skill template 
  (CRITICAL)
        - B2_FOLDER_STRUCTURE.md        # Department context
        - 03_specific_requirements.md   # Technical 
  requirements

      output_format: YAML
      filename_pattern: "{department}_skill-name.yaml"

      context: |
        Extract actionable skills from course content.
        Use CREWAI_OUTPUT_GUIDELINES.md skill template.
        Include department prefix in filename.

    - name: command_generator_agent
      role: Claude Commands Generator
      goal: Generate Markdown slash commands

      knowledge_sources:
        - CREWAI_OUTPUT_GUIDELINES.md   # Command template 
  (CRITICAL)
        - B2_FOLDER_STRUCTURE.md        # Department context

      output_format: Markdown
      filename_pattern: "{department}_command-name.md"

    - name: prompt_generator_agent
      role: AI Prompt Template Generator
      goal: Extract reusable prompt patterns

      knowledge_sources:
        - CREWAI_OUTPUT_GUIDELINES.md   # Prompt template 
  (CRITICAL)
        - B2_FOLDER_STRUCTURE.md        # Department context

      output_format: Markdown or YAML
      filename_pattern: "{department}_prompt-name.md"

    - name: workflow_generator_agent
      role: n8n Workflow Generator
      goal: Design automation workflows

      knowledge_sources:
        - CREWAI_OUTPUT_GUIDELINES.md   # Workflow template 
  (CRITICAL)
        - 10_n8n_orchestration.md       # n8n patterns
        - empire-arch.txt               # Integration points

      output_format: JSON
      filename_pattern: "{department}_workflow-name.json"

  Priority Reading Order

  Phase 1: Foundation (READ FIRST)

  1. CREWAI_OUTPUT_GUIDELINES.md (5-10 min)
    - Understand output format requirements
    - Learn filename convention
    - Review all asset type templates
  2. B2_FOLDER_STRUCTURE.md (10-15 min)
    - Memorize 10 department codes
    - Study classification keywords per department
    - Review classification examples
  3. empire-arch.txt (5-10 min)
    - System overview
    - Technology stack
    - Integration patterns

  Phase 2: Deep Dive (AS NEEDED)

  4. Department-specific sections in B2_FOLDER_STRUCTURE.md
    - Read relevant department details when classifying
  specific courses
  5. Technical docs (01-10 SRS sections)
    - Reference for specific technical requirements
    - Integration patterns
    - System capabilities

  Key Sections to Extract

  From CREWAI_OUTPUT_GUIDELINES.md:

  ✅ MUST EXTRACT:
  - Filename naming convention: {department}_{name}.{ext}
  - Department codes (all 11)
  - Asset type templates:
    • Claude Skills (YAML structure)
    • Claude Commands (Markdown structure)
    • Agents (YAML structure)
    • Prompts (Markdown/YAML structure)
    • Workflows (JSON structure)
  - Required fields (version, department, description, 
  created)
  - Quality standards

  From B2_FOLDER_STRUCTURE.md:

  ✅ MUST EXTRACT:
  - 10 Department taxonomy:
    1. it-engineering
    2. sales-marketing
    3. customer-support
    4. operations-hr-supply
    5. finance-accounting
    6. project-management
    7. real-estate
    8. private-equity-ma
    9. consulting
    10. personal-continuing-ed

  - Per department:
    • Core focus keywords
    • AI classification keywords
    • Common course title patterns
    • Subdepartment structure

  From empire-arch.txt:

  ✅ MUST EXTRACT:
  - Input sources (B2, YouTube, web scraping)
  - Processing pipeline stages
  - Technology stack:
    • Claude Sonnet/Haiku
    • Supabase + pgvector
    • Neo4j
    • n8n
    • CrewAI
  - Integration patterns

  Minimal File Set (If Limited Context)

  If CrewAI has limited context window, prioritize these 3
  files:

  1. CREWAI_OUTPUT_GUIDELINES.md (CRITICAL)
    - All output format requirements
    - Templates for all asset types
  2. B2_FOLDER_STRUCTURE.md (CRITICAL)
    - Department taxonomy
    - Classification keywords
  3. empire-arch.txt (IMPORTANT)
    - System overview
    - Integration context

  CrewAI Agent Prompt Template

  # Example: Configure CrewAI agent with knowledge sources

  from crewai import Agent, Task, Crew

  # Load knowledge sources
  with open('CREWAI_OUTPUT_GUIDELINES.md') as f:
      output_guidelines = f.read()

  with open('B2_FOLDER_STRUCTURE.md') as f:
      department_taxonomy = f.read()

  with open('empire-arch.txt') as f:
      system_architecture = f.read()

  # Configure agent
  course_analyzer = Agent(
      role='Course Analysis & Suggestion Generator',
      goal='Analyze courses and generate production-ready 
  assets',
      backstory=f"""
      You are an expert at analyzing educational content and 
  generating
      actionable tools. You have deep knowledge of:
      
      1. OUTPUT STANDARDS:
      {output_guidelines[:2000]}  # First 2000 chars
      
      2. DEPARTMENT TAXONOMY:
      {department_taxonomy[:2000]}  # First 2000 chars
      
      3. SYSTEM ARCHITECTURE:
      {system_architecture[:1000]}  # First 1000 chars
      
      Your outputs MUST follow the filename convention:
      {{department}}_{{asset-name}}.{{ext}}
      
      Available departments: it-engineering, sales-marketing, 
      customer-support, operations-hr-supply, 
  finance-accounting,
      project-management, real-estate, private-equity-ma, 
      consulting, personal-continuing-ed, _global
      """,
      verbose=True,
      allow_delegation=False
  )

  Summary

  Essential Files (3):
  1. CREWAI_OUTPUT_GUIDELINES.md - Output format & templates
  2. B2_FOLDER_STRUCTURE.md - Department taxonomy &
  classification
  3. empire-arch.txt - System architecture & context

  Optional but Helpful (10):
  - 01_introduction.md through 10_n8n_orchestration.md for
  detailed requirements

  Critical Information to Extract:
  - ✅ Filename convention: {department}_{name}.{ext}
  - ✅ 10 department codes + _global
  - ✅ Asset type templates (5 types)
  - ✅ Classification keywords per department
  - ✅ Quality standards & validation rules

  Would you like me to create a condensed "CrewAI Quick
  Reference" document that combines the most critical
  information from these files into a single, optimized file
  for agent context?
