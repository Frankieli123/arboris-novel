"""Property-based tests for API endpoints.

Feature: async-task-polling
"""
import pytest
import time
from hypothesis import given, strategies as st, settings, HealthCheck
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


# Hypothesis strategies for generating test data
task_type_strategy = st.sampled_from([
    "concept_converse",
    "blueprint_generate",
    "chapter_generate",
    "chapter_evaluate",
    "outline_generate",
])

project_id_strategy = st.text(
    min_size=1,
    max_size=36,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-")
)

chapter_number_strategy = st.integers(min_value=1, max_value=100)


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    project_id=project_id_strategy,
    chapter_number=chapter_number_strategy,
)
@settings(
    max_examples=10,  # Reduced for initial testing
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_1_task_creation_immediate_response(
    task_type: str,
    project_id: str,
    chapter_number: int,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """
    **Feature: async-task-polling, Property 1: 任务创建立即响应**
    
    Property: For any long-running operation request (concept converse, blueprint generate, 
    chapter generate, etc.), the API should return a response containing task_id and 
    pending status within 3 seconds, without waiting for the operation to complete.
    
    **Validates: Requirements 1.1, 1.2, 1.4, 1.5**
    
    This test verifies that:
    1. Task creation endpoints respond within 3 seconds
    2. The response contains a task_id
    3. The response contains status='pending'
    4. The response contains a created_at timestamp
    5. The task is persisted to the database immediately
    6. The response format matches the TaskResponse schema
    """
    from app.main import app
    from sqlalchemy import select
    from app.models import AsyncTask
    
    # Prepare request data based on task type
    if task_type == "concept_converse":
        endpoint = "/api/tasks/concept-converse"
        request_data = {
            "project_id": project_id,
            "user_input": {"value": "test input"},
            "conversation_state": {"step": 1}
        }
    elif task_type == "blueprint_generate":
        endpoint = "/api/tasks/blueprint-generate"
        request_data = {
            "project_id": project_id
        }
    elif task_type == "chapter_generate":
        endpoint = "/api/tasks/chapter-generate"
        request_data = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "writing_notes": "test notes"
        }
    elif task_type == "chapter_evaluate":
        endpoint = "/api/tasks/chapter-evaluate"
        request_data = {
            "project_id": project_id,
            "chapter_number": chapter_number
        }
    elif task_type == "outline_generate":
        endpoint = "/api/tasks/outline-generate"
        request_data = {
            "project_id": project_id,
            "start_chapter": chapter_number,
            "num_chapters": 5
        }
    else:
        pytest.skip(f"Unknown task type: {task_type}")
    
    # Measure response time
    start_time = time.time()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            endpoint,
            json=request_data,
            headers=auth_headers
        )
    
    end_time = time.time()
    response_time = end_time - start_time
    
    # Verify response time is within 3 seconds
    assert response_time < 3.0, (
        f"Task creation took {response_time:.2f} seconds, "
        f"which exceeds the 3 second requirement"
    )
    
    # Verify HTTP status code is 201 Created
    assert response.status_code == 201, (
        f"Expected status code 201, got {response.status_code}. "
        f"Response: {response.text}"
    )
    
    # Verify response contains required fields
    response_data = response.json()
    assert "task_id" in response_data, "Response should contain 'task_id'"
    assert "status" in response_data, "Response should contain 'status'"
    assert "created_at" in response_data, "Response should contain 'created_at'"
    
    # Verify task_id is a non-empty string
    task_id = response_data["task_id"]
    assert isinstance(task_id, str), "task_id should be a string"
    assert len(task_id) > 0, "task_id should not be empty"
    
    # Verify status is 'pending'
    assert response_data["status"] == "pending", (
        f"Initial task status should be 'pending', got '{response_data['status']}'"
    )
    
    # Verify created_at is a valid timestamp string
    created_at = response_data["created_at"]
    assert isinstance(created_at, str), "created_at should be a string"
    assert len(created_at) > 0, "created_at should not be empty"
    
    # Verify the task was persisted to the database
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    persisted_task = result.scalar_one_or_none()
    
    assert persisted_task is not None, (
        f"Task with ID {task_id} should be persisted to database"
    )
    
    # Verify persisted task has correct fields
    assert persisted_task.user_id == test_user.id, "Task should belong to the requesting user"
    assert persisted_task.task_type == task_type, f"Task type should be '{task_type}'"
    assert persisted_task.status == "pending", "Persisted task status should be 'pending'"
    assert persisted_task.progress == 0, "Initial progress should be 0"
    assert persisted_task.input_data is not None, "Input data should be persisted"
    assert persisted_task.created_at is not None, "Created timestamp should be set"
    assert persisted_task.expires_at is not None, "Expires timestamp should be set"
    
    # Verify input data was correctly persisted
    assert "project_id" in persisted_task.input_data, "Input data should contain project_id"
    assert persisted_task.input_data["project_id"] == project_id, "Project ID should match"
    
    if task_type in ["chapter_generate", "chapter_evaluate"]:
        assert "chapter_number" in persisted_task.input_data, "Input data should contain chapter_number"
        assert persisted_task.input_data["chapter_number"] == chapter_number, "Chapter number should match"


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    project_id=project_id_strategy,
    chapter_number=chapter_number_strategy,
)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_14_api_async_migration_consistency(
    task_type: str,
    project_id: str,
    chapter_number: int,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """
    **Feature: async-task-polling, Property 14: API异步迁移一致性**
    
    Property: For any long-running operation API endpoint (concept converse, blueprint generate,
    chapter generate, chapter evaluate, outline generate), calling it should immediately return
    a task_id instead of waiting for the operation to complete.
    
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    
    This test verifies that:
    1. The migrated API endpoints return immediately (within 3 seconds)
    2. The response contains a task_id field
    3. The response does NOT contain the final result data
    4. The task is created in pending status
    5. All five long-running operations have been migrated to async mode
    
    Note: This test validates the MIGRATED endpoints (the original API paths that now
    return task IDs), not the /api/tasks/* endpoints which are tested by Property 1.
    """
    from app.main import app
    from sqlalchemy import select
    from app.models import AsyncTask
    
    # Map task types to their MIGRATED API endpoints (original paths)
    if task_type == "concept_converse":
        endpoint = f"/api/novels/{project_id}/concept/converse"
        request_data = {
            "user_input": {"value": "test input"},
            "conversation_state": {"step": 1}
        }
    elif task_type == "blueprint_generate":
        endpoint = f"/api/novels/{project_id}/blueprint/generate"
        request_data = {}
    elif task_type == "chapter_generate":
        endpoint = f"/api/writer/novels/{project_id}/chapters/generate"
        request_data = {
            "chapter_number": chapter_number,
            "writing_notes": "test notes"
        }
    elif task_type == "chapter_evaluate":
        endpoint = f"/api/writer/novels/{project_id}/chapters/evaluate"
        request_data = {
            "chapter_number": chapter_number
        }
    elif task_type == "outline_generate":
        endpoint = f"/api/writer/novels/{project_id}/chapters/outline"
        request_data = {
            "start_chapter": chapter_number,
            "num_chapters": 5
        }
    else:
        pytest.skip(f"Unknown task type: {task_type}")
    
    # Measure response time
    start_time = time.time()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            endpoint,
            json=request_data,
            headers=auth_headers
        )
    
    end_time = time.time()
    response_time = end_time - start_time
    
    # Verify response time is within 3 seconds (async migration requirement)
    assert response_time < 3.0, (
        f"Migrated API endpoint {endpoint} took {response_time:.2f} seconds, "
        f"which exceeds the 3 second requirement. The endpoint should return "
        f"a task_id immediately instead of waiting for the operation to complete."
    )
    
    # Verify HTTP status code
    # After migration, these endpoints should return 202 Accepted (async) or 201 Created
    assert response.status_code in [200, 201, 202], (
        f"Expected status code 200/201/202, got {response.status_code}. "
        f"Response: {response.text}"
    )
    
    response_data = response.json()
    
    # Verify the response contains a task_id (indicating async migration)
    assert "task_id" in response_data, (
        f"Migrated endpoint {endpoint} should return a 'task_id' field. "
        f"This indicates the endpoint has been migrated to async mode. "
        f"Response keys: {list(response_data.keys())}"
    )
    
    task_id = response_data["task_id"]
    assert isinstance(task_id, str), "task_id should be a string"
    assert len(task_id) > 0, "task_id should not be empty"
    
    # Verify the response does NOT contain final result data
    # (which would indicate the endpoint is still synchronous)
    result_fields = {
        "concept_converse": ["ai_message", "ui_control", "conversation_state"],
        "blueprint_generate": ["blueprint"],
        "chapter_generate": ["chapters", "blueprint"],
        "chapter_evaluate": ["chapters", "blueprint"],
        "outline_generate": ["outlines", "blueprint"],
    }
    
    disallowed_fields = result_fields.get(task_type, [])
    for field in disallowed_fields:
        assert field not in response_data, (
            f"Migrated endpoint {endpoint} should NOT return '{field}' in the immediate response. "
            f"The endpoint should return only task_id and status, not the final result. "
            f"This indicates the endpoint has not been properly migrated to async mode."
        )
    
    # Verify the task was created in the database
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    persisted_task = result.scalar_one_or_none()
    
    assert persisted_task is not None, (
        f"Task with ID {task_id} should be persisted to database"
    )
    
    # Verify task properties
    assert persisted_task.user_id == test_user.id, "Task should belong to the requesting user"
    assert persisted_task.task_type == task_type, f"Task type should be '{task_type}'"
    assert persisted_task.status == "pending", (
        "Task should be in 'pending' status immediately after creation"
    )
    assert persisted_task.progress == 0, "Initial progress should be 0"
    
    # Verify input data was correctly persisted
    assert persisted_task.input_data is not None, "Input data should be persisted"
    assert "project_id" in persisted_task.input_data, "Input data should contain project_id"
    assert persisted_task.input_data["project_id"] == project_id, "Project ID should match"
    
    if task_type in ["chapter_generate", "chapter_evaluate"]:
        assert "chapter_number" in persisted_task.input_data, "Input data should contain chapter_number"
        assert persisted_task.input_data["chapter_number"] == chapter_number, "Chapter number should match"
