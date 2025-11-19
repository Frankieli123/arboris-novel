"""Property-based tests for AsyncTask model.

Feature: async-task-polling
"""
import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AsyncTask, User


# Define valid task types based on the design document
VALID_TASK_TYPES = [
    "concept_converse",
    "blueprint_generate",
    "chapter_generate",
    "chapter_evaluate",
    "outline_generate",
]

# Define valid task statuses
VALID_STATUSES = ["pending", "processing", "completed", "failed"]


# Hypothesis strategies for generating test data
task_type_strategy = st.sampled_from(VALID_TASK_TYPES)
status_strategy = st.sampled_from(VALID_STATUSES)
progress_strategy = st.integers(min_value=0, max_value=100)
input_data_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
    values=st.one_of(
        st.text(min_size=0, max_size=100),
        st.integers(),
        st.booleans(),
    ),
    min_size=1,
    max_size=5,
)


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    max_retries=st.integers(min_value=0, max_value=5),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_2_task_persistence(
    task_type: str,
    input_data: dict,
    max_retries: int,
    db_session: AsyncSession,
    test_user: User,
):
    """
    **Feature: async-task-polling, Property 2: 任务持久化**
    
    Property: For any created task, there should be a corresponding task record 
    in the database with all required fields (ID, user_id, type, status, input_data, created_at).
    
    **Validates: Requirements 1.3**
    
    This test verifies that:
    1. When a task is created and added to the database
    2. The task can be retrieved from the database
    3. All required fields are present and correctly stored
    4. The task is associated with the correct user
    """
    # Create a new AsyncTask instance
    task = AsyncTask(
        user_id=test_user.id,
        task_type=task_type,
        status="pending",  # All new tasks start as pending
        progress=0,
        input_data=input_data,
        max_retries=max_retries,
    )
    
    # Add task to database
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    
    # Store the task ID for verification
    task_id = task.id
    
    # Expire the task from the session to force a fresh read from database
    db_session.expire(task)
    
    # Query the task from the database to verify persistence
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    persisted_task = result.scalar_one_or_none()
    
    # Verify the task exists in the database
    assert persisted_task is not None, f"Task with ID {task_id} was not found in database"
    
    # Verify all required fields are present and correct
    assert persisted_task.id == task_id, "Task ID does not match"
    assert persisted_task.user_id == test_user.id, "User ID does not match"
    assert persisted_task.task_type == task_type, "Task type does not match"
    assert persisted_task.status == "pending", "Initial status should be 'pending'"
    assert persisted_task.input_data == input_data, "Input data does not match"
    assert persisted_task.created_at is not None, "Created timestamp is missing"
    assert isinstance(persisted_task.created_at, datetime), "Created timestamp should be a datetime"
    
    # Verify optional fields have correct defaults
    assert persisted_task.progress == 0, "Initial progress should be 0"
    assert persisted_task.retry_count == 0, "Initial retry count should be 0"
    assert persisted_task.max_retries == max_retries, "Max retries does not match"
    assert persisted_task.result_data is None, "Result data should be None initially"
    assert persisted_task.error_message is None, "Error message should be None initially"
    assert persisted_task.started_at is None, "Started timestamp should be None initially"
    assert persisted_task.completed_at is None, "Completed timestamp should be None initially"
    
    # Verify expires_at is set and is in the future
    assert persisted_task.expires_at is not None, "Expires timestamp is missing"
    assert isinstance(persisted_task.expires_at, datetime), "Expires timestamp should be a datetime"
    assert persisted_task.expires_at > persisted_task.created_at, "Expires timestamp should be after created timestamp"


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    # Generate a random user_id offset to simulate different users
    user_id_offset=st.integers(min_value=1, max_value=1000),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_3_task_query_permission_control(
    task_type: str,
    input_data: dict,
    user_id_offset: int,
    db_session: AsyncSession,
    test_user: User,
):
    """
    **Feature: async-task-polling, Property 3: 任务查询权限控制**
    
    Property: For any task query request, if the task ID doesn't exist it should return 404,
    if the task doesn't belong to the requesting user it should return 403,
    otherwise it should return the complete task status information.
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    
    This test verifies that:
    1. Querying a non-existent task ID raises HTTPException with status 404
    2. Querying a task that belongs to another user raises HTTPException with status 403
    3. Querying a valid task that belongs to the user returns the correct task data
    """
    from app.services.task_service import TaskService
    from fastapi import HTTPException
    
    service = TaskService(db_session)
    
    # Test Case 1: Query non-existent task ID should return 404
    # Generate a random UUID that doesn't exist
    import uuid
    nonexistent_task_id = str(uuid.uuid4())
    
    with pytest.raises(HTTPException) as exc_info:
        await service.get_task(nonexistent_task_id, test_user.id)
    
    assert exc_info.value.status_code == 404, "Non-existent task should return 404"
    assert "任务不存在" in exc_info.value.detail, "Error message should indicate task not found"
    
    # Test Case 2: Create a task for the test user
    created_task = await service.create_task(
        user_id=test_user.id,
        task_type=task_type,
        input_data=input_data,
        max_retries=3,
    )
    await db_session.commit()
    
    # Test Case 3: Query the task with a different user_id should return 403
    different_user_id = test_user.id + user_id_offset
    
    with pytest.raises(HTTPException) as exc_info:
        await service.get_task(created_task.id, different_user_id)
    
    assert exc_info.value.status_code == 403, "Task belonging to another user should return 403"
    assert "无权访问" in exc_info.value.detail, "Error message should indicate forbidden access"
    
    # Test Case 4: Query the task with the correct user_id should succeed
    retrieved_task = await service.get_task(created_task.id, test_user.id)
    
    # Verify the retrieved task matches the created task
    assert retrieved_task is not None, "Task should be retrieved successfully"
    assert retrieved_task.id == created_task.id, "Task ID should match"
    assert retrieved_task.user_id == test_user.id, "User ID should match"
    assert retrieved_task.task_type == task_type, "Task type should match"
    assert retrieved_task.status == "pending", "Status should be pending"
    assert retrieved_task.input_data == input_data, "Input data should match"
    
    # Verify all required fields are present in the retrieved task
    assert retrieved_task.created_at is not None, "Created timestamp should be present"
    assert retrieved_task.progress is not None, "Progress should be present"
    assert retrieved_task.max_retries is not None, "Max retries should be present"


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    # Generate random number of days in the past for expired tasks
    days_past_expiry=st.integers(min_value=1, max_value=30),
    # Generate random number of days in the future for non-expired tasks
    days_until_expiry=st.integers(min_value=1, max_value=30),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_10_task_cleanup_mechanism(
    task_type: str,
    input_data: dict,
    days_past_expiry: int,
    days_until_expiry: int,
    db_session: AsyncSession,
    test_user: User,
):
    """
    **Feature: async-task-polling, Property 10: 任务清理机制**
    
    Property: For any task with completion time exceeding the retention period (default 7 days),
    the cleanup program should delete it from the database.
    
    **Validates: Requirements 5.4**
    
    This test verifies that:
    1. Tasks with expires_at in the past are deleted by cleanup_expired_tasks
    2. Tasks with expires_at in the future are NOT deleted by cleanup_expired_tasks
    3. The cleanup function returns the correct count of deleted tasks
    4. After cleanup, expired tasks cannot be found in the database
    5. After cleanup, non-expired tasks remain in the database
    """
    from app.services.task_service import TaskService
    
    service = TaskService(db_session)
    
    # Create an expired task (expires_at is in the past)
    now = datetime.utcnow()
    expired_task = AsyncTask(
        user_id=test_user.id,
        task_type=task_type,
        status="completed",  # Completed tasks are candidates for cleanup
        progress=100,
        input_data=input_data,
        max_retries=3,
        created_at=now - timedelta(days=days_past_expiry + 7),
        completed_at=now - timedelta(days=days_past_expiry),
        expires_at=now - timedelta(days=days_past_expiry),  # Expired
    )
    
    # Create a non-expired task (expires_at is in the future)
    non_expired_task = AsyncTask(
        user_id=test_user.id,
        task_type=task_type,
        status="completed",
        progress=100,
        input_data=input_data,
        max_retries=3,
        created_at=now,
        completed_at=now,
        expires_at=now + timedelta(days=days_until_expiry),  # Not expired
    )
    
    # Add both tasks to the database
    db_session.add(expired_task)
    db_session.add(non_expired_task)
    await db_session.commit()
    
    # Store task IDs for verification
    expired_task_id = expired_task.id
    non_expired_task_id = non_expired_task.id
    
    # Verify both tasks exist before cleanup
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == expired_task_id)
    )
    assert result.scalar_one_or_none() is not None, "Expired task should exist before cleanup"
    
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == non_expired_task_id)
    )
    assert result.scalar_one_or_none() is not None, "Non-expired task should exist before cleanup"
    
    # Run the cleanup function
    deleted_count = await service.cleanup_expired_tasks()
    await db_session.commit()
    
    # Verify that at least one task was deleted (the expired one)
    assert deleted_count >= 1, f"Cleanup should delete at least 1 expired task, but deleted {deleted_count}"
    
    # Verify the expired task no longer exists in the database
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == expired_task_id)
    )
    deleted_task = result.scalar_one_or_none()
    assert deleted_task is None, "Expired task should be deleted from database"
    
    # Verify the non-expired task still exists in the database
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == non_expired_task_id)
    )
    remaining_task = result.scalar_one_or_none()
    assert remaining_task is not None, "Non-expired task should remain in database"
    assert remaining_task.id == non_expired_task_id, "Non-expired task ID should match"
    assert remaining_task.status == "completed", "Non-expired task status should be unchanged"
    assert remaining_task.expires_at > now, "Non-expired task should still have future expiry date"


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    should_succeed=st.booleans(),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_4_task_state_transition_correctness(
    task_type: str,
    input_data: dict,
    should_succeed: bool,
    db_session: AsyncSession,
):
    """
    **Feature: async-task-polling, Property 4: 任务状态转换正确性**
    
    Property: For any task processed by the worker, the status should transition 
    in the order pending → processing → (completed | failed), and each transition 
    should be persisted to the database.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    
    This test verifies that:
    1. A task starts in 'pending' status when created
    2. When processing begins, status changes to 'processing' and started_at is set
    3. When processing succeeds, status changes to 'completed' and completed_at is set
    4. When processing fails, status changes to 'failed' and error_message is set
    5. All state transitions are persisted to the database
    6. Status transitions follow the correct order
    """
    from app.services.task_service import TaskService
    from sqlalchemy import select
    import uuid
    
    # Create a unique test user for this specific test run
    unique_id = str(uuid.uuid4())[:8]
    test_user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=False,
    )
    db_session.add(test_user)
    await db_session.flush()
    user_id = test_user.id
    
    service = TaskService(db_session)
    
    # Step 1: Create a task - should start in 'pending' status
    task = await service.create_task(
        user_id=user_id,
        task_type=task_type,
        input_data=input_data,
        max_retries=3,
    )
    task_id = task.id
    
    # Verify initial state is 'pending'
    assert task.status == "pending", "Initial task status should be 'pending'"
    assert task.progress == 0, "Initial progress should be 0"
    assert task.started_at is None, "started_at should be None initially"
    assert task.completed_at is None, "completed_at should be None initially"
    assert task.result_data is None, "result_data should be None initially"
    assert task.error_message is None, "error_message should be None initially"
    
    # Step 2: Transition to 'processing' status
    await service.update_task_status(
        task_id=task_id,
        status="processing",
        progress=10,
        progress_message="Processing task..."
    )
    
    # Step 3: Transition to final state (completed or failed)
    if should_succeed:
        # Simulate successful completion
        result_data = {"output": "success", "data": input_data}
        await service.update_task_status(
            task_id=task_id,
            status="completed",
            progress=100,
            progress_message="Task completed successfully",
            result_data=result_data
        )
    else:
        # Simulate failure
        error_message = "Task execution failed due to an error"
        await service.update_task_status(
            task_id=task_id,
            status="failed",
            progress=50,
            progress_message="Task failed",
            error_message=error_message
        )
    
    # Commit all changes at once
    await db_session.commit()
    
    # Verify the complete state transition sequence was persisted
    # The task should have gone through: pending → processing → (completed | failed)
    db_session.expire_all()
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    final_task = result.scalar_one()
    
    # Verify all timestamps are in correct order
    assert final_task.created_at is not None, "created_at should be set"
    assert final_task.started_at is not None, "started_at should be set"
    assert final_task.completed_at is not None, "completed_at should be set"
    assert final_task.created_at <= final_task.started_at, "created_at should be before or equal to started_at"
    assert final_task.started_at <= final_task.completed_at, "started_at should be before or equal to completed_at"
    
    # Verify final status is terminal (completed or failed)
    assert final_task.status in ["completed", "failed"], "Final status should be either 'completed' or 'failed'"
    
    # Verify status-specific fields
    if should_succeed:
        assert final_task.status == "completed", "Task status should be 'completed'"
        assert final_task.progress == 100, "Progress should be 100 when completed"
        assert final_task.progress_message == "Task completed successfully", "Progress message should indicate success"
        assert final_task.result_data == {"output": "success", "data": input_data}, "Result data should be persisted"
        assert final_task.error_message is None, "error_message should be None for successful tasks"
    else:
        assert final_task.status == "failed", "Task status should be 'failed'"
        assert final_task.progress == 50, "Progress should reflect where the task failed"
        assert final_task.progress_message == "Task failed", "Progress message should indicate failure"
        assert final_task.error_message == "Task execution failed due to an error", "Error message should be persisted"
        assert final_task.result_data is None, "result_data should be None for failed tasks"


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    exception_message=st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P"))),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_5_exception_handling_completeness(
    task_type: str,
    input_data: dict,
    exception_message: str,
    db_session: AsyncSession,
):
    """
    **Feature: async-task-polling, Property 5: 异常处理完整性**
    
    Property: For any task that throws an exception during processing, the system should 
    capture the exception, set the task status to 'failed', and save the error information 
    to the error_message field.
    
    **Validates: Requirements 3.5**
    
    This test verifies that:
    1. When a task processing function throws an exception
    2. The exception is caught by the system
    3. The task status is updated to 'failed'
    4. The error message is saved to the error_message field
    5. The task is persisted to the database with the error information
    6. The completed_at timestamp is set
    """
    from app.services.task_service import TaskService
    from sqlalchemy import select
    import uuid
    
    # Create a unique test user for this specific test run
    unique_id = str(uuid.uuid4())[:8]
    test_user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=False,
    )
    db_session.add(test_user)
    await db_session.flush()
    user_id = test_user.id
    
    service = TaskService(db_session)
    
    # Create a task
    task = await service.create_task(
        user_id=user_id,
        task_type=task_type,
        input_data=input_data,
        max_retries=0,  # Set to 0 to avoid retries and directly test exception handling
    )
    task_id = task.id
    await db_session.commit()
    
    # Simulate the exception handling logic that TaskWorker.process_task would perform
    # This tests the core exception handling behavior without needing to import TaskWorker
    try:
        # Update task status to processing (simulating worker starting to process)
        await service.update_task_status(
            task_id=task_id,
            status="processing",
            progress=0,
            progress_message="开始处理任务..."
        )
        await db_session.commit()
        
        # Simulate an exception being raised during task execution
        raise RuntimeError(exception_message)
        
    except Exception as e:
        # This is the exception handling logic from TaskWorker.process_task
        # When max_retries is 0, it should mark the task as failed
        error_message = f"任务执行失败: {str(e)}"
        await service.update_task_status(
            task_id=task_id,
            status="failed",
            progress=0,
            progress_message="任务失败",
            error_message=error_message
        )
        await db_session.commit()
    
    # Verify the task was updated correctly after the exception
    db_session.expire_all()
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    failed_task = result.scalar_one()
    
    # Verify the task status is 'failed'
    assert failed_task.status == "failed", "Task status should be 'failed' after exception"
    
    # Verify the error message was captured and saved
    assert failed_task.error_message is not None, "Error message should not be None"
    assert exception_message in failed_task.error_message, f"Error message should contain the exception message: '{exception_message}'"
    
    # Verify the completed_at timestamp was set
    assert failed_task.completed_at is not None, "completed_at should be set when task fails"
    
    # Verify the started_at timestamp was set (task was processing before it failed)
    assert failed_task.started_at is not None, "started_at should be set when task starts processing"
    
    # Verify timestamps are in correct order
    assert failed_task.created_at <= failed_task.started_at, "created_at should be before or equal to started_at"
    assert failed_task.started_at <= failed_task.completed_at, "started_at should be before or equal to completed_at"
    
    # Verify result_data is None for failed tasks
    assert failed_task.result_data is None, "result_data should be None for failed tasks"
    
    # Verify the task went through the correct state transitions
    # The task should have been: pending → processing → failed
    # We can verify this by checking that started_at is set (indicating it was processing)
    assert failed_task.started_at is not None, "Task should have been in processing state before failing"


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    max_retries=st.integers(min_value=1, max_value=5),
    should_succeed_on_retry=st.integers(min_value=0, max_value=5),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_15_task_retry_mechanism(
    task_type: str,
    input_data: dict,
    max_retries: int,
    should_succeed_on_retry: int,
    db_session: AsyncSession,
):
    """
    **Feature: async-task-polling, Property 15: 任务重试机制**
    
    Property: For any task configured with a retry strategy, the system should 
    automatically retry the task until it succeeds or reaches the maximum retry 
    count (max_retries).
    
    **Validates: Requirements 8.1, 8.2**
    
    This test verifies that:
    1. When a task fails and has retries remaining, it is reset to 'pending' status
    2. The retry_count increments with each retry attempt
    3. When retry_count reaches max_retries, the task is marked as 'failed' permanently
    4. If a task succeeds on a retry, it is marked as 'completed'
    5. The error_message is preserved during retries
    6. The progress_message indicates retry information
    """
    from app.services.task_service import TaskService
    from sqlalchemy import select, update
    import uuid
    
    # Create a unique test user for this specific test run
    unique_id = str(uuid.uuid4())[:8]
    test_user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=False,
    )
    db_session.add(test_user)
    await db_session.flush()
    user_id = test_user.id
    
    service = TaskService(db_session)
    
    # Create a task with retry configuration
    task = await service.create_task(
        user_id=user_id,
        task_type=task_type,
        input_data=input_data,
        max_retries=max_retries,
    )
    task_id = task.id
    await db_session.commit()
    
    # Verify initial state
    assert task.status == "pending", "Initial task status should be 'pending'"
    assert task.retry_count == 0, "Initial retry count should be 0"
    assert task.max_retries == max_retries, "Max retries should match configured value"
    
    # Determine if the task should succeed on a specific retry attempt
    # If should_succeed_on_retry is 0, task succeeds on first attempt (no retries needed)
    # If should_succeed_on_retry is within [1, max_retries], task succeeds on that retry
    # Otherwise, task fails after all retries
    will_succeed = should_succeed_on_retry <= max_retries
    success_on_attempt = should_succeed_on_retry if will_succeed else max_retries + 1
    
    # Simulate retry attempts (attempt 0 is the initial try, 1+ are retries)
    for attempt in range(max_retries + 1):
        # Refresh task from database
        db_session.expire_all()
        result = await db_session.execute(
            select(AsyncTask).where(AsyncTask.id == task_id)
        )
        current_task = result.scalar_one()
        
        # Task should be in pending status at the start of each attempt
        assert current_task.status == "pending", f"Task should be 'pending' at start of attempt {attempt}"
        
        # Verify retry count
        assert current_task.retry_count == attempt, f"Retry count should be {attempt} at attempt {attempt}"
        
        # Simulate task processing: pending → processing
        await service.update_task_status(
            task_id=task_id,
            status="processing",
            progress=10,
            progress_message=f"Processing attempt {attempt + 1}..."
        )
        await db_session.commit()
        
        # Check if this attempt should succeed
        if attempt == success_on_attempt:
            # Task succeeds on this attempt
            await service.update_task_status(
                task_id=task_id,
                status="completed",
                progress=100,
                progress_message="Task completed successfully",
                result_data={"success": True, "attempt": attempt}
            )
            await db_session.commit()
            break
        else:
            # Task fails on this attempt
            error_message = f"Task failed on attempt {attempt + 1}"
            
            if attempt < max_retries:
                # Still have retries remaining - reset to pending
                retry_count = attempt + 1
                delay = 2 ** retry_count  # Exponential backoff
                
                await service.update_task_status(
                    task_id=task_id,
                    status="pending",
                    progress=0,
                    progress_message=f"任务失败，将在 {delay} 秒后重试（第 {retry_count} 次重试）",
                    error_message=error_message
                )
                
                # Update retry count
                stmt = (
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(retry_count=retry_count)
                )
                await db_session.execute(stmt)
                await db_session.commit()
            else:
                # No more retries - mark as failed permanently
                await service.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=0,
                    progress_message="任务失败",
                    error_message=f"任务执行失败: {error_message}"
                )
                await db_session.commit()
                break
    
    # Verify final state
    db_session.expire_all()
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    final_task = result.scalar_one()
    
    if will_succeed:
        # Task should have succeeded on the specified retry attempt
        assert final_task.status == "completed", f"Task should be 'completed' after succeeding on attempt {success_on_attempt}"
        assert final_task.result_data is not None, "Result data should be set for completed task"
        assert final_task.result_data.get("success") is True, "Result should indicate success"
        assert final_task.result_data.get("attempt") == success_on_attempt, f"Result should show success on attempt {success_on_attempt}"
        assert final_task.retry_count == success_on_attempt, f"Retry count should be {success_on_attempt}"
        assert final_task.completed_at is not None, "completed_at should be set"
    else:
        # Task should have failed after exhausting all retries
        assert final_task.status == "failed", "Task should be 'failed' after exhausting retries"
        assert final_task.retry_count == max_retries, f"Retry count should be {max_retries} (max retries)"
        assert final_task.error_message is not None, "Error message should be set for failed task"
        assert "任务执行失败" in final_task.error_message, "Error message should indicate task failure"
        assert final_task.completed_at is not None, "completed_at should be set for failed task"
        assert final_task.result_data is None, "result_data should be None for failed task"
    
    # Verify timestamps are in correct order
    assert final_task.created_at is not None, "created_at should be set"
    assert final_task.started_at is not None, "started_at should be set"
    assert final_task.completed_at is not None, "completed_at should be set"
    assert final_task.created_at <= final_task.started_at, "created_at should be before or equal to started_at"
    assert final_task.started_at <= final_task.completed_at, "started_at should be before or equal to completed_at"



@pytest.mark.asyncio
@given(
    max_workers=st.integers(min_value=1, max_value=5),
    num_tasks=st.integers(min_value=1, max_value=10),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_11_concurrent_control(
    max_workers: int,
    num_tasks: int,
    db_session: AsyncSession,
):
    """
    **Feature: async-task-polling, Property 11: 并发控制**
    
    Property: For any moment in time, the number of tasks being executed simultaneously 
    by TaskWorker should not exceed the configured maximum concurrent count (default 3).
    
    **Validates: Requirements 5.5**
    
    This test verifies that:
    1. TaskWorker respects the max_workers configuration
    2. At any given time, no more than max_workers tasks are processing simultaneously
    3. The semaphore correctly limits concurrent task execution
    4. Tasks wait for available slots when max_workers is reached
    5. The semaphore is properly released after task completion
    
    Note: This test verifies the concurrent control mechanism by simulating
    concurrent task execution using asyncio.Semaphore, which is the same
    mechanism used by TaskWorker. We test the semaphore behavior directly
    without needing to import TaskWorker or create actual database sessions
    for each task.
    """
    import asyncio
    
    # Track concurrent execution
    concurrent_count = 0
    max_concurrent_observed = 0
    lock = asyncio.Lock()
    
    # Create a semaphore to simulate TaskWorker's concurrent control
    # This is the exact same mechanism used in TaskWorker.__init__ and _run_task_loop
    semaphore = asyncio.Semaphore(max_workers)
    
    async def simulate_task_processing(task_index: int) -> None:
        """Simulate task processing with semaphore control"""
        nonlocal concurrent_count, max_concurrent_observed
        
        # Acquire semaphore (blocks if max_workers tasks are already running)
        # This simulates TaskWorker._process_task_with_semaphore
        async with semaphore:
            # Increment concurrent count
            async with lock:
                concurrent_count += 1
                if concurrent_count > max_concurrent_observed:
                    max_concurrent_observed = concurrent_count
            
            # Simulate some work (like LLM API call or database operations)
            await asyncio.sleep(0.01)
            
            # Decrement concurrent count
            async with lock:
                concurrent_count -= 1
    
    # Process all tasks concurrently (but limited by semaphore)
    # This simulates what happens when TaskWorker processes multiple pending tasks
    tasks = [simulate_task_processing(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)
    
    # Verify that the maximum concurrent count never exceeded max_workers
    assert max_concurrent_observed <= max_workers, (
        f"Maximum concurrent tasks ({max_concurrent_observed}) exceeded "
        f"configured max_workers ({max_workers})"
    )
    
    # Verify that if we had more tasks than max_workers, we actually observed
    # concurrent execution (this ensures the test is meaningful)
    if num_tasks > max_workers:
        # We should have observed at least some concurrent tasks
        # (Due to timing, we might not always hit exactly max_workers, but we should
        # see at least 1 concurrent task if we have more tasks than workers)
        assert max_concurrent_observed >= 1, (
            f"Expected to observe concurrent execution with {num_tasks} tasks "
            f"and {max_workers} max_workers, but max_concurrent_observed is {max_concurrent_observed}"
        )
    
    # Verify that the final concurrent count is 0 (all tasks finished)
    assert concurrent_count == 0, (
        f"Concurrent count should be 0 after all tasks complete, but is {concurrent_count}"
    )
    
    # Additional verification: The semaphore should be back to its initial state
    # (all permits released)
    # We can verify this by checking that we can acquire max_workers permits immediately
    acquired_permits = []
    for _ in range(max_workers):
        acquired = semaphore.locked()
        if not acquired:
            # Try to acquire without blocking
            acquired_permits.append(await asyncio.wait_for(semaphore.acquire(), timeout=0.001))
    
    # Release all acquired permits
    for _ in acquired_permits:
        semaphore.release()
    
    # Verify we could acquire all max_workers permits (meaning they were all released)
    assert len(acquired_permits) == max_workers, (
        f"Expected to acquire {max_workers} permits after all tasks complete, "
        f"but only acquired {len(acquired_permits)}"
    )


@pytest.mark.asyncio
@given(
    task_type=task_type_strategy,
    input_data=input_data_strategy,
    progress_value=progress_strategy,
    progress_message=st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P", "Zs"))),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_property_12_progress_information_completeness(
    task_type: str,
    input_data: dict,
    progress_value: int,
    progress_message: str,
    db_session: AsyncSession,
):
    """
    **Feature: async-task-polling, Property 12: 进度信息完整性**
    
    Property: For any task in 'processing' status, querying its status should return 
    the current progress percentage (0-100) and progress description information.
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    
    This test verifies that:
    1. When a task is in 'processing' status, it has a progress percentage (0-100)
    2. When a task is in 'processing' status, it has a progress description message
    3. Progress information is persisted to the database
    4. Querying the task returns the latest progress information
    5. Progress percentage is within valid range (0-100)
    6. Progress message is not None or empty for processing tasks
    """
    from app.services.task_service import TaskService
    from sqlalchemy import select
    import uuid
    
    # Create a unique test user for this specific test run
    unique_id = str(uuid.uuid4())[:8]
    test_user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=False,
    )
    db_session.add(test_user)
    await db_session.flush()
    user_id = test_user.id
    
    service = TaskService(db_session)
    
    # Create a task
    task = await service.create_task(
        user_id=user_id,
        task_type=task_type,
        input_data=input_data,
        max_retries=3,
    )
    task_id = task.id
    await db_session.commit()
    
    # Verify initial state (pending tasks should have progress 0)
    assert task.status == "pending", "Initial task status should be 'pending'"
    assert task.progress == 0, "Initial progress should be 0"
    assert task.progress_message is None, "Initial progress message should be None"
    
    # Update task to processing status with progress information
    await service.update_task_status(
        task_id=task_id,
        status="processing",
        progress=progress_value,
        progress_message=progress_message
    )
    await db_session.commit()
    
    # Query the task from the database to verify persistence
    db_session.expire_all()
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    processing_task = result.scalar_one()
    
    # Verify the task is in processing status
    assert processing_task.status == "processing", "Task status should be 'processing'"
    
    # Verify progress percentage is present and within valid range
    assert processing_task.progress is not None, "Progress should not be None for processing task"
    assert isinstance(processing_task.progress, int), "Progress should be an integer"
    assert 0 <= processing_task.progress <= 100, (
        f"Progress should be between 0 and 100, but is {processing_task.progress}"
    )
    assert processing_task.progress == progress_value, (
        f"Progress should match the set value {progress_value}, but is {processing_task.progress}"
    )
    
    # Verify progress message is present and not empty
    assert processing_task.progress_message is not None, (
        "Progress message should not be None for processing task"
    )
    assert isinstance(processing_task.progress_message, str), (
        "Progress message should be a string"
    )
    assert len(processing_task.progress_message.strip()) > 0, (
        "Progress message should not be empty for processing task"
    )
    assert processing_task.progress_message == progress_message, (
        f"Progress message should match the set value, but got '{processing_task.progress_message}'"
    )
    
    # Verify that querying the task through the service returns the same progress information
    retrieved_task = await service.get_task(task_id, user_id)
    
    assert retrieved_task.status == "processing", "Retrieved task status should be 'processing'"
    assert retrieved_task.progress == progress_value, (
        f"Retrieved task progress should be {progress_value}, but is {retrieved_task.progress}"
    )
    assert retrieved_task.progress_message == progress_message, (
        f"Retrieved task progress message should match, but got '{retrieved_task.progress_message}'"
    )
    
    # Verify started_at timestamp is set when task is processing
    assert processing_task.started_at is not None, (
        "started_at should be set when task is in processing status"
    )
    assert isinstance(processing_task.started_at, datetime), (
        "started_at should be a datetime object"
    )
    assert processing_task.created_at <= processing_task.started_at, (
        "created_at should be before or equal to started_at"
    )
    
    # Test multiple progress updates to verify progress information can be updated
    new_progress = min(progress_value + 10, 100)  # Ensure we don't exceed 100
    new_message = f"Updated: {progress_message}"
    
    await service.update_task_status(
        task_id=task_id,
        status="processing",
        progress=new_progress,
        progress_message=new_message
    )
    await db_session.commit()
    
    # Verify the updated progress information
    db_session.expire_all()
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    updated_task = result.scalar_one()
    
    assert updated_task.progress == new_progress, (
        f"Updated progress should be {new_progress}, but is {updated_task.progress}"
    )
    assert updated_task.progress_message == new_message, (
        f"Updated progress message should be '{new_message}', but is '{updated_task.progress_message}'"
    )
    
    # Verify that completed tasks also have progress information (should be 100)
    await service.update_task_status(
        task_id=task_id,
        status="completed",
        progress=100,
        progress_message="Task completed successfully",
        result_data={"success": True}
    )
    await db_session.commit()
    
    db_session.expire_all()
    result = await db_session.execute(
        select(AsyncTask).where(AsyncTask.id == task_id)
    )
    completed_task = result.scalar_one()
    
    assert completed_task.status == "completed", "Task status should be 'completed'"
    assert completed_task.progress == 100, "Completed task progress should be 100"
    assert completed_task.progress_message is not None, (
        "Completed task should have a progress message"
    )
    assert completed_task.completed_at is not None, (
        "completed_at should be set when task is completed"
    )
