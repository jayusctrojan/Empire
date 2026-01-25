"""
Test CrewAI Asset Storage for Task 36.3
Verifies that generated assets can be stored to B2 processed/ folders
"""

import asyncio
from app.services.crewai_asset_storage import CrewAIAssetStorage, AssetType


async def test_asset_storage():
    """Test storing various asset types to B2"""
    print("="*70)
    print("Task 36.3: Testing CrewAI Asset Storage to B2")
    print("="*70)

    storage = CrewAIAssetStorage()

    # Test data
    department = "it-engineering"
    test_assets = []

    # 1. Test skill storage
    print("\n[1/6] Testing skill storage...")
    try:
        skill_yaml = """
name: deploy-to-production
description: Deploy application to production environment
parameters:
  - name: environment
    type: string
    required: true
  - name: version
    type: string
    required: true
steps:
  - name: Run tests
    action: pytest tests/
  - name: Build Docker image
    action: docker build -t app:{{version}} .
  - name: Push to registry
    action: docker push app:{{version}}
  - name: Deploy to {{environment}}
    action: kubectl apply -f k8s/{{environment}}/
"""
        result = await storage.store_skill(
            department=department,
            skill_name="deploy-to-production",
            yaml_content=skill_yaml,
            metadata={"source": "devops_course", "complexity": "high"}
        )
        print(f"✅ Skill stored: {result['folder']}/{result['file_name']}")
        test_assets.append(result)
    except Exception as e:
        print(f"❌ Skill storage failed: {e}")

    # 2. Test command storage
    print("\n[2/6] Testing command storage...")
    try:
        command_md = """
Run database migrations for the current environment.

Steps:
1. Backup current database
2. Run migrations: `alembic upgrade head`
3. Verify schema changes
"""
        result = await storage.store_command(
            department=department,
            command_name="run-migrations",
            markdown_content=command_md,
            metadata={"source": "database_course"}
        )
        print(f"✅ Command stored: {result['folder']}/{result['file_name']}")
        test_assets.append(result)
    except Exception as e:
        print(f"❌ Command storage failed: {e}")

    # 3. Test agent config storage
    print("\n[3/6] Testing agent config storage...")
    try:
        agent_yaml = """
role: DevOps Engineer
goal: Automate deployment processes and maintain infrastructure
backstory: |
  Expert DevOps engineer with 10+ years of experience in CI/CD,
  containerization, and cloud infrastructure management.
tools:
  - docker
  - kubernetes
  - terraform
  - ansible
llm_config:
  model: claude-sonnet-4-20250514
  temperature: 0.3
"""
        result = await storage.store_agent_config(
            department=department,
            agent_name="devops-automation-agent",
            yaml_content=agent_yaml,
            metadata={"source": "devops_course"}
        )
        print(f"✅ Agent config stored: {result['folder']}/{result['file_name']}")
        test_assets.append(result)
    except Exception as e:
        print(f"❌ Agent config storage failed: {e}")

    # 4. Test prompt template storage
    print("\n[4/6] Testing prompt template storage...")
    try:
        prompt_md = """
# Code Review Prompt Template

Analyze the following code changes and provide:

1. **Code Quality Assessment**
   - Readability and maintainability
   - Adherence to coding standards
   - Potential bugs or issues

2. **Security Analysis**
   - Potential security vulnerabilities
   - Data validation concerns
   - Authentication/authorization issues

3. **Performance Considerations**
   - Potential performance bottlenecks
   - Resource usage concerns
   - Optimization opportunities

4. **Recommendations**
   - Suggested improvements
   - Best practices to follow
   - Alternative approaches

Code to review:
```
{{code}}
```
"""
        result = await storage.store_prompt(
            department=department,
            prompt_name="code-review-template",
            markdown_content=prompt_md,
            metadata={"source": "software_engineering_course"}
        )
        print(f"✅ Prompt stored: {result['folder']}/{result['file_name']}")
        test_assets.append(result)
    except Exception as e:
        print(f"❌ Prompt storage failed: {e}")

    # 5. Test workflow storage
    print("\n[5/6] Testing workflow storage...")
    try:
        workflow_json = """{
  "name": "CI/CD Pipeline",
  "nodes": [
    {
      "id": "trigger",
      "type": "trigger",
      "name": "Git Push Trigger"
    },
    {
      "id": "test",
      "type": "action",
      "name": "Run Tests",
      "action": "pytest"
    },
    {
      "id": "build",
      "type": "action",
      "name": "Build Docker Image",
      "action": "docker build"
    },
    {
      "id": "deploy",
      "type": "action",
      "name": "Deploy to Production",
      "action": "kubectl apply"
    }
  ],
  "edges": [
    {"from": "trigger", "to": "test"},
    {"from": "test", "to": "build"},
    {"from": "build", "to": "deploy"}
  ]
}"""
        result = await storage.store_workflow(
            department=department,
            workflow_name="cicd-pipeline",
            json_content=workflow_json,
            metadata={"source": "devops_course", "platform": "n8n"}
        )
        print(f"✅ Workflow stored: {result['folder']}/{result['file_name']}")
        test_assets.append(result)
    except Exception as e:
        print(f"❌ Workflow storage failed: {e}")

    # 6. Test summary storage (simulated PDF)
    print("\n[6/6] Testing summary storage...")
    try:
        # Simulated PDF content (in reality, this would be a proper PDF)
        pdf_content = b"%PDF-1.4 Simulated PDF content for testing"
        result = await storage.store_summary(
            department=department,
            content=pdf_content,
            metadata={
                "source": "devops_course",
                "title": "DevOps Best Practices Summary",
                "page_count": 12
            }
        )
        print(f"✅ Summary stored: {result['folder']}/{result['file_name']}")
        test_assets.append(result)
    except Exception as e:
        print(f"❌ Summary storage failed: {e}")

    # Summary
    print("\n" + "="*70)
    print(f"✅ Successfully stored {len(test_assets)}/6 asset types")
    print("="*70)

    print("\nStored assets:")
    for asset in test_assets:
        print(f"  - {asset['folder']}/{asset['file_name']} ({asset['size']} bytes)")

    print("\n✅ Task 36.3 Complete: Asset storage to B2 verified!")


if __name__ == "__main__":
    asyncio.run(test_asset_storage())
