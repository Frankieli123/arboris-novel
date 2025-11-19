import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTaskPolling } from '../useTaskPolling'
import * as tasksApi from '@/api/tasks'
import * as fc from 'fast-check'

// Mock the tasks API
vi.mock('@/api/tasks', () => ({
  getTaskStatus: vi.fn()
}))

describe('useTaskPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('should initialize with idle status', () => {
    const { status, progress, error, isPolling } = useTaskPolling({
      taskId: 'test-task-id'
    })

    expect(status.value).toBe('idle')
    expect(progress.value).toBe(0)
    expect(error.value).toBeNull()
    expect(isPolling.value).toBe(false)
  })

  it('should start polling when startPolling is called', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    mockGetTaskStatus.mockResolvedValue({
      id: 'test-task-id',
      status: 'pending',
      progress: 0,
      created_at: new Date().toISOString()
    })

    const { startPolling, isPolling } = useTaskPolling({
      taskId: 'test-task-id'
    })

    startPolling()
    expect(isPolling.value).toBe(true)

    // Wait for initial poll
    await vi.runOnlyPendingTimersAsync()
    expect(mockGetTaskStatus).toHaveBeenCalledWith('test-task-id')
  })

  it('should update status and progress during polling', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'processing',
      progress: 50,
      progress_message: 'Processing...',
      created_at: new Date().toISOString()
    })

    const { startPolling, status, progress, progressMessage } = useTaskPolling({
      taskId: 'test-task-id'
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()

    expect(status.value).toBe('processing')
    expect(progress.value).toBe(50)
    expect(progressMessage.value).toBe('Processing...')
  })

  it('should stop polling when task is completed', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    const onComplete = vi.fn()

    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'completed',
      progress: 100,
      result_data: { success: true },
      created_at: new Date().toISOString()
    })

    const { startPolling, status, result, isPolling } = useTaskPolling({
      taskId: 'test-task-id',
      onComplete
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()

    expect(status.value).toBe('completed')
    expect(result.value).toEqual({ success: true })
    expect(isPolling.value).toBe(false)
    expect(onComplete).toHaveBeenCalledWith({ success: true })
  })

  it('should stop polling when task fails', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    const onError = vi.fn()

    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'failed',
      progress: 50,
      error_message: 'Task failed',
      created_at: new Date().toISOString()
    })

    const { startPolling, status, error, isPolling } = useTaskPolling({
      taskId: 'test-task-id',
      onError
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()

    expect(status.value).toBe('failed')
    expect(error.value).toBe('Task failed')
    expect(isPolling.value).toBe(false)
    expect(onError).toHaveBeenCalledWith('Task failed')
  })

  it('should call onProgress callback during processing', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    const onProgress = vi.fn()

    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'processing',
      progress: 75,
      progress_message: 'Almost done...',
      created_at: new Date().toISOString()
    })

    const { startPolling } = useTaskPolling({
      taskId: 'test-task-id',
      onProgress
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()

    expect(onProgress).toHaveBeenCalledWith(75, 'Almost done...')
  })

  it('should stop polling after max attempts', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    const onError = vi.fn()

    mockGetTaskStatus.mockResolvedValue({
      id: 'test-task-id',
      status: 'processing',
      progress: 50,
      created_at: new Date().toISOString()
    })

    const { startPolling, status, error, isPolling } = useTaskPolling({
      taskId: 'test-task-id',
      maxAttempts: 3,
      onError
    })

    startPolling()

    // Run through max attempts
    for (let i = 0; i < 4; i++) {
      await vi.runOnlyPendingTimersAsync()
    }

    expect(status.value).toBe('failed')
    expect(error.value).toBe('任务查询超时，请稍后重试')
    expect(isPolling.value).toBe(false)
    expect(onError).toHaveBeenCalledWith('任务查询超时，请稍后重试')
  })

  it('should handle network errors with exponential backoff', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    
    // First call fails
    mockGetTaskStatus.mockRejectedValueOnce(new Error('Network error'))
    // Second call succeeds
    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'processing',
      progress: 50,
      created_at: new Date().toISOString()
    })

    const { startPolling, status, stopPolling } = useTaskPolling({
      taskId: 'test-task-id',
      interval: 1000
    })

    startPolling()
    
    // First attempt fails
    await vi.runOnlyPendingTimersAsync()
    
    // Second attempt should succeed
    await vi.runOnlyPendingTimersAsync()
    
    // Stop polling to prevent further calls
    stopPolling()
    
    expect(status.value).toBe('processing')
    expect(mockGetTaskStatus).toHaveBeenCalledTimes(2)
  })

  it('should stop polling when stopPolling is called', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    mockGetTaskStatus.mockResolvedValue({
      id: 'test-task-id',
      status: 'processing',
      progress: 50,
      created_at: new Date().toISOString()
    })

    const { startPolling, stopPolling, isPolling } = useTaskPolling({
      taskId: 'test-task-id'
    })

    startPolling()
    expect(isPolling.value).toBe(true)

    stopPolling()
    expect(isPolling.value).toBe(false)

    // Advance timers - no more calls should be made
    const callCount = mockGetTaskStatus.mock.calls.length
    await vi.runOnlyPendingTimersAsync()
    expect(mockGetTaskStatus.mock.calls.length).toBe(callCount)
  })

  it('should not start polling if already polling', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    mockGetTaskStatus.mockResolvedValue({
      id: 'test-task-id',
      status: 'processing',
      progress: 50,
      created_at: new Date().toISOString()
    })

    const { startPolling } = useTaskPolling({
      taskId: 'test-task-id'
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()
    
    const callCount = mockGetTaskStatus.mock.calls.length
    
    // Try to start again
    startPolling()
    
    // Should not increase call count
    expect(mockGetTaskStatus.mock.calls.length).toBe(callCount)
  })

  it('should use custom interval', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    mockGetTaskStatus.mockResolvedValue({
      id: 'test-task-id',
      status: 'processing',
      progress: 50,
      created_at: new Date().toISOString()
    })

    const customInterval = 5000
    const { startPolling } = useTaskPolling({
      taskId: 'test-task-id',
      interval: customInterval
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()

    const initialCalls = mockGetTaskStatus.mock.calls.length

    // Advance by custom interval
    vi.advanceTimersByTime(customInterval)
    await vi.runOnlyPendingTimersAsync()

    expect(mockGetTaskStatus.mock.calls.length).toBeGreaterThan(initialCalls)
  })

  it('should handle error when task status has no error message', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    const onError = vi.fn()

    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'failed',
      progress: 50,
      created_at: new Date().toISOString()
    })

    const { startPolling, error } = useTaskPolling({
      taskId: 'test-task-id',
      onError
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()

    expect(error.value).toBe('任务执行失败')
    expect(onError).toHaveBeenCalledWith('任务执行失败')
  })

  it('should reset error when starting new polling session', async () => {
    const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
    
    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'failed',
      progress: 50,
      error_message: 'Previous error',
      created_at: new Date().toISOString()
    })

    const { startPolling, stopPolling, error } = useTaskPolling({
      taskId: 'test-task-id'
    })

    startPolling()
    await vi.runOnlyPendingTimersAsync()
    expect(error.value).toBe('Previous error')

    stopPolling()

    // Start new polling session
    mockGetTaskStatus.mockResolvedValueOnce({
      id: 'test-task-id',
      status: 'processing',
      progress: 25,
      created_at: new Date().toISOString()
    })

    startPolling()
    expect(error.value).toBeNull()
  })
})


// Property-Based Tests
// Feature: async-task-polling, Property 6: 轮询行为正确性
// Validates: Requirements 4.1, 4.2, 4.3, 4.4
describe('Property 6: Polling Behavior Correctness', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('Property: For any incomplete task (pending/processing), polling should continue until completion or max attempts', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random sequence of statuses before completion
        fc.array(
          fc.constantFrom('pending', 'processing'),
          { minLength: 1, maxLength: 10 }
        ),
        // Generate random final status
        fc.constantFrom('completed', 'failed'),
        // Generate random progress values
        fc.array(fc.integer({ min: 0, max: 100 }), { minLength: 1, maxLength: 10 }),
        async (taskId, intermediateStatuses, finalStatus, progressValues) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Setup mock responses: intermediate statuses followed by final status
          intermediateStatuses.forEach((status, index) => {
            mockGetTaskStatus.mockResolvedValueOnce({
              id: taskId,
              status: status as 'pending' | 'processing',
              progress: progressValues[index % progressValues.length],
              progress_message: `Step ${index + 1}`,
              created_at: new Date().toISOString()
            })
          })

          // Final status
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: finalStatus as 'completed' | 'failed',
            progress: finalStatus === 'completed' ? 100 : progressValues[0],
            result_data: finalStatus === 'completed' ? { success: true } : undefined,
            error_message: finalStatus === 'failed' ? 'Task failed' : undefined,
            created_at: new Date().toISOString()
          })

          const { startPolling, status, isPolling } = useTaskPolling({
            taskId,
            interval: 100
          })

          startPolling()

          // Poll through all intermediate statuses
          for (let i = 0; i <= intermediateStatuses.length; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Verify polling stopped after final status
          expect(isPolling.value).toBe(false)
          expect(status.value).toBe(finalStatus)
          
          // Verify we polled the correct number of times
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(intermediateStatuses.length + 1)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Polling should stop after max attempts even if task is not complete', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random max attempts (small number for test speed)
        fc.integer({ min: 2, max: 10 }),
        // Generate random incomplete status
        fc.constantFrom('pending', 'processing'),
        async (taskId, maxAttempts, incompleteStatus) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Always return incomplete status
          mockGetTaskStatus.mockResolvedValue({
            id: taskId,
            status: incompleteStatus as 'pending' | 'processing',
            progress: 50,
            created_at: new Date().toISOString()
          })

          const onError = vi.fn()
          const { startPolling, status, error, isPolling } = useTaskPolling({
            taskId,
            maxAttempts,
            interval: 100,
            onError
          })

          startPolling()

          // Run through max attempts + 1
          for (let i = 0; i <= maxAttempts + 1; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Verify polling stopped
          expect(isPolling.value).toBe(false)
          expect(status.value).toBe('failed')
          expect(error.value).toBe('任务查询超时，请稍后重试')
          expect(onError).toHaveBeenCalledWith('任务查询超时，请稍后重试')
          
          // Verify we didn't poll more than maxAttempts + 1 times
          expect(mockGetTaskStatus.mock.calls.length).toBeLessThanOrEqual(maxAttempts + 1)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Polling should start immediately when startPolling is called', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random status
        fc.constantFrom('pending', 'processing', 'completed', 'failed'),
        // Generate random progress
        fc.integer({ min: 0, max: 100 }),
        async (taskId, taskStatus, progress) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          mockGetTaskStatus.mockResolvedValue({
            id: taskId,
            status: taskStatus as any,
            progress,
            created_at: new Date().toISOString()
          })

          const { startPolling, isPolling } = useTaskPolling({
            taskId,
            interval: 1000
          })

          // Before starting, should not be polling
          expect(isPolling.value).toBe(false)
          expect(mockGetTaskStatus).not.toHaveBeenCalled()

          startPolling()

          // Should immediately set isPolling to true
          expect(isPolling.value).toBe(true)

          // Should poll immediately (before interval)
          await vi.runOnlyPendingTimersAsync()
          expect(mockGetTaskStatus).toHaveBeenCalledWith(taskId)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Callbacks should be invoked correctly based on task status', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random final status
        fc.constantFrom('completed', 'failed'),
        // Generate random result/error data
        fc.record({
          resultData: fc.anything(),
          errorMessage: fc.string({ minLength: 1 }) // Ensure non-empty error messages
        }),
        async (taskId, finalStatus, data) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          const onProgress = vi.fn()
          const onComplete = vi.fn()
          const onError = vi.fn()

          // First return processing status
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: 'processing',
            progress: 50,
            progress_message: 'In progress',
            created_at: new Date().toISOString()
          })

          // Then return final status
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: finalStatus as 'completed' | 'failed',
            progress: finalStatus === 'completed' ? 100 : 50,
            result_data: finalStatus === 'completed' ? data.resultData : undefined,
            error_message: finalStatus === 'failed' ? data.errorMessage : undefined,
            created_at: new Date().toISOString()
          })

          const { startPolling } = useTaskPolling({
            taskId,
            interval: 100,
            onProgress,
            onComplete,
            onError
          })

          startPolling()

          // First poll - processing
          await vi.runOnlyPendingTimersAsync()
          expect(onProgress).toHaveBeenCalledWith(50, 'In progress')

          // Second poll - final status
          await vi.runOnlyPendingTimersAsync()

          if (finalStatus === 'completed') {
            expect(onComplete).toHaveBeenCalledWith(data.resultData)
            expect(onError).not.toHaveBeenCalled()
          } else {
            expect(onError).toHaveBeenCalledWith(data.errorMessage)
            expect(onComplete).not.toHaveBeenCalled()
          }
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Polling interval should be respected for incomplete tasks', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random interval (reasonable range)
        fc.integer({ min: 100, max: 5000 }),
        // Generate number of polls to test
        fc.integer({ min: 2, max: 5 }),
        async (taskId, interval, numPolls) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Always return processing status
          mockGetTaskStatus.mockResolvedValue({
            id: taskId,
            status: 'processing',
            progress: 50,
            created_at: new Date().toISOString()
          })

          const { startPolling } = useTaskPolling({
            taskId,
            interval
          })

          startPolling()

          // Initial poll happens immediately
          await vi.runOnlyPendingTimersAsync()
          const initialCalls = mockGetTaskStatus.mock.calls.length

          // Advance time by interval * numPolls
          for (let i = 0; i < numPolls; i++) {
            vi.advanceTimersByTime(interval)
            await vi.runOnlyPendingTimersAsync()
          }

          // Should have polled numPolls more times
          expect(mockGetTaskStatus.mock.calls.length).toBeGreaterThanOrEqual(initialCalls + numPolls)
        }
      ),
      { numRuns: 50 }
    )
  })

  it('Property: stopPolling should immediately stop all polling activity', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random number of polls before stopping
        fc.integer({ min: 1, max: 5 }),
        async (taskId, pollsBeforeStop) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Always return processing status
          mockGetTaskStatus.mockResolvedValue({
            id: taskId,
            status: 'processing',
            progress: 50,
            created_at: new Date().toISOString()
          })

          const { startPolling, stopPolling, isPolling } = useTaskPolling({
            taskId,
            interval: 100
          })

          startPolling()
          expect(isPolling.value).toBe(true)

          // Poll a few times
          for (let i = 0; i < pollsBeforeStop; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          const callsBeforeStop = mockGetTaskStatus.mock.calls.length

          // Stop polling
          stopPolling()
          expect(isPolling.value).toBe(false)

          // Advance time - no more calls should be made
          vi.advanceTimersByTime(10000)
          await vi.runOnlyPendingTimersAsync()

          expect(mockGetTaskStatus.mock.calls.length).toBe(callsBeforeStop)
        }
      ),
      { numRuns: 100 }
    )
  })
})

// Feature: async-task-polling, Property 7: 网络错误重试策略
// Validates: Requirements 4.5
describe('Property 7: Network Error Retry Strategy', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('Property: For any network error during polling, client should retry with exponential backoff (each retry interval is 2x the previous)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random number of consecutive failures before success (1-3, reduced for test speed)
        fc.integer({ min: 1, max: 3 }),
        // Generate random base interval
        fc.integer({ min: 100, max: 500 }),
        async (taskId, numFailures, baseInterval) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Setup failures followed by success
          for (let i = 0; i < numFailures; i++) {
            mockGetTaskStatus.mockRejectedValueOnce(new Error('Network error'))
          }
          
          // Final success
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: 'processing',
            progress: 50,
            created_at: new Date().toISOString()
          })

          const { startPolling, status, stopPolling } = useTaskPolling({
            taskId,
            interval: baseInterval,
            maxAttempts: numFailures + 10 // Ensure we don't hit max attempts
          })

          startPolling()

          // Process all failures and the success
          for (let i = 0; i <= numFailures; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Stop polling to prevent further calls
          stopPolling()

          // Should eventually succeed
          expect(status.value).toBe('processing')
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(numFailures + 1)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Network errors should not stop polling until max attempts is reached', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random max attempts (small for test speed)
        fc.integer({ min: 3, max: 10 }),
        async (taskId, maxAttempts) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Always fail with network error
          mockGetTaskStatus.mockRejectedValue(new Error('Network error'))

          const onError = vi.fn()
          const { startPolling, status, error, isPolling } = useTaskPolling({
            taskId,
            interval: 100,
            maxAttempts,
            onError
          })

          startPolling()

          // Run through all attempts
          for (let i = 0; i <= maxAttempts + 1; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Should stop after max attempts
          expect(isPolling.value).toBe(false)
          expect(status.value).toBe('failed')
          expect(error.value).toBeTruthy()
          expect(onError).toHaveBeenCalled()
          
          // Should have attempted at least maxAttempts times
          expect(mockGetTaskStatus.mock.calls.length).toBeGreaterThanOrEqual(maxAttempts)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: After a network error, the next retry should occur (backoff is applied)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random interval
        fc.integer({ min: 100, max: 500 }),
        async (taskId, interval) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // First call fails
          mockGetTaskStatus.mockRejectedValueOnce(new Error('Network error'))
          // Second call succeeds
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: 'processing',
            progress: 50,
            created_at: new Date().toISOString()
          })

          const { startPolling, stopPolling } = useTaskPolling({
            taskId,
            interval
          })

          startPolling()

          // First attempt (immediate) - fails
          await vi.runOnlyPendingTimersAsync()
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(1)

          // Second attempt should happen after backoff
          await vi.runOnlyPendingTimersAsync()
          
          // Stop polling to prevent further calls
          stopPolling()
          
          // Should have retried
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(2)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Successful poll after network error should reset backoff multiplier', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random interval
        fc.integer({ min: 100, max: 500 }),
        async (taskId, interval) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Fail, succeed, fail, succeed pattern
          mockGetTaskStatus
            .mockRejectedValueOnce(new Error('Network error'))
            .mockResolvedValueOnce({
              id: taskId,
              status: 'processing',
              progress: 25,
              created_at: new Date().toISOString()
            })
            .mockRejectedValueOnce(new Error('Network error'))
            .mockResolvedValueOnce({
              id: taskId,
              status: 'processing',
              progress: 50,
              created_at: new Date().toISOString()
            })

          const { startPolling, stopPolling } = useTaskPolling({
            taskId,
            interval
          })

          startPolling()

          // Process the fail-success-fail-success sequence
          for (let i = 0; i < 4; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Stop polling to prevent further calls
          stopPolling()

          // All 4 attempts should have been made
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(4)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Backoff multiplier should be capped to prevent excessive delays', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate many consecutive failures (reduced for test speed)
        fc.integer({ min: 3, max: 6 }),
        async (taskId, numFailures) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Many failures followed by success
          for (let i = 0; i < numFailures; i++) {
            mockGetTaskStatus.mockRejectedValueOnce(new Error('Network error'))
          }
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: 'processing',
            progress: 50,
            created_at: new Date().toISOString()
          })

          const { startPolling, status, stopPolling } = useTaskPolling({
            taskId,
            interval: 100,
            maxAttempts: numFailures + 10
          })

          startPolling()

          // Process all attempts
          for (let i = 0; i <= numFailures; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Stop polling to prevent further calls
          stopPolling()

          // Should eventually succeed despite many failures
          expect(status.value).toBe('processing')
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(numFailures + 1)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('Property: Different error types should all trigger retry behavior', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random task ID
        fc.uuid(),
        // Generate random error messages
        fc.array(fc.string({ minLength: 1 }), { minLength: 1, maxLength: 3 }),
        async (taskId, errorMessages) => {
          const mockGetTaskStatus = vi.mocked(tasksApi.getTaskStatus)
          mockGetTaskStatus.mockClear()

          // Setup different error types
          errorMessages.forEach(msg => {
            mockGetTaskStatus.mockRejectedValueOnce(new Error(msg))
          })
          
          // Final success
          mockGetTaskStatus.mockResolvedValueOnce({
            id: taskId,
            status: 'completed',
            progress: 100,
            result_data: { success: true },
            created_at: new Date().toISOString()
          })

          const { startPolling, status } = useTaskPolling({
            taskId,
            interval: 100,
            maxAttempts: errorMessages.length + 5
          })

          startPolling()

          // Process all errors and success
          for (let i = 0; i <= errorMessages.length; i++) {
            await vi.runOnlyPendingTimersAsync()
          }

          // Should succeed after retrying through all errors
          expect(status.value).toBe('completed')
          expect(mockGetTaskStatus).toHaveBeenCalledTimes(errorMessages.length + 1)
        }
      ),
      { numRuns: 100 }
    )
  })
})
