-- Migration: Create async_tasks table
-- Description: Add async_tasks table for background task processing
-- Date: 2024-11-19

CREATE TABLE IF NOT EXISTS async_tasks (
    id CHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    progress INT DEFAULT 0,
    progress_message TEXT NULL,
    input_data JSON NOT NULL,
    result_data JSON NULL,
    error_message TEXT NULL,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    expires_at TIMESTAMP NOT NULL,
    CONSTRAINT fk_async_tasks_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for query optimization
CREATE INDEX idx_async_tasks_user_status ON async_tasks(user_id, status);
CREATE INDEX idx_async_tasks_status_created ON async_tasks(status, created_at);
CREATE INDEX idx_async_tasks_expires ON async_tasks(expires_at);
