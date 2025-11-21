# MCP Plugin System - Manual Testing Guide

This guide provides step-by-step instructions for manually testing the MCP plugin system with real MCP servers.

## Prerequisites

1. Backend server running (`python -m uvicorn app.main:app --reload`)
2. Database initialized with migrations applied
3. Admin user account created
4. API client (Postman, curl, or frontend)

## Test Scenario 1: Configure and Test Exa Search Plugin

### Step 1: Start a Mock MCP Server (Optional)

If you don't have access to a real MCP server, you can create a simple mock:

```python
# mock_mcp_server.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Tool(BaseModel):
    name: str
    description: str
    inputSchema: dict

@app.post("/mcp/initialize")
async def initialize():
    return {"protocolVersion": "1.0", "serverInfo": {"name": "mock", "version": "1.0"}}

@app.post("/mcp/tools/list")
async def list_tools():
    return {
        "tools": [
            {
                "name": "search",
                "description": "Search the web",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        ]
    }

@app.post("/mcp/tools/call")
async def call_tool(request: dict):
    tool_name = request.get("name")
    arguments = request.get("arguments", {})
    
    if tool_name == "search":
        query = arguments.get("query", "")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Search results for: {query}\n1. Result 1\n2. Result 2\n3. Result 3"
                }
            ]
        }
    
    return {"error": "Unknown tool"}

# Run with: uvicorn mock_mcp_server:app --port 9000
```

### Step 2: Create Plugin via API

**Request:**
```http
POST /api/mcp/plugins
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "plugin_name": "exa_search",
  "display_name": "Exa Search",
  "plugin_type": "http",
  "server_url": "http://localhost:9000",
  "enabled": true,
  "category": "search",
  "headers": {
    "Authorization": "Bearer your-api-key-here"
  }
}
```

**Expected Response:**
```json
{
  "id": 1,
  "plugin_name": "exa_search",
  "display_name": "Exa Search",
  "plugin_type": "http",
  "server_url": "http://localhost:9000",
  "enabled": true,
  "category": "search",
  "user_enabled": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Verification:**
- ✅ Plugin created successfully
- ✅ Plugin ID returned
- ✅ All fields match input

### Step 3: Test Plugin Connection

**Request:**
```http
POST /api/mcp/plugins/1/test
Authorization: Bearer <admin_token>
```

**Expected Response:**
```json
{
  "success": true,
  "message": "✅ 插件测试完成",
  "tools_count": 1,
  "suggestions": [
    "✅ 连接成功",
    "📊 发现 1 个工具",
    "🤖 选择工具: search",
    "✅ 工具调用成功"
  ]
}
```

**Verification:**
- ✅ Connection established
- ✅ Tools discovered
- ✅ Test call succeeded

### Step 4: Enable Plugin for User

**Request:**
```http
POST /api/mcp/plugins/1/toggle
Authorization: Bearer <user_token>
Content-Type: application/json

{
  "enabled": true
}
```

**Expected Response:**
```json
{
  "enabled": true
}
```

**Verification:**
- ✅ Plugin enabled for user
- ✅ Status returned correctly

### Step 5: Verify Plugin in User's List

**Request:**
```http
GET /api/mcp/plugins
Authorization: Bearer <user_token>
```

**Expected Response:**
```json
[
  {
    "id": 1,
    "plugin_name": "exa_search",
    "display_name": "Exa Search",
    "enabled": true,
    "user_enabled": true,
    ...
  }
]
```

**Verification:**
- ✅ Plugin appears in list
- ✅ `user_enabled` is true

### Step 6: Test Chapter Generation with MCP Tools

**Request:**
```http
POST /api/projects/{project_id}/chapters/{chapter_id}/generate
Authorization: Bearer <user_token>
Content-Type: application/json

{
  "prompt": "Write a chapter about a detective investigating a mysterious case. Use web search to find information about detective techniques."
}
```

**Expected Behavior:**
1. System retrieves user's enabled plugins
2. System includes search tool in AI request
3. AI decides to call search tool
4. System executes tool call via MCP
5. System sends tool results back to AI
6. AI generates final chapter content

**Verification:**
- ✅ Chapter generated successfully
- ✅ Check logs for tool call execution
- ✅ Content quality improved with external data

### Step 7: Check Metrics

**Request:**
```http
GET /api/mcp/metrics
Authorization: Bearer <admin_token>
```

**Expected Response:**
```json
{
  "exa_search.search": {
    "tool_name": "exa_search.search",
    "total_calls": 1,
    "success_calls": 1,
    "failed_calls": 0,
    "avg_duration_ms": 150.5,
    "success_rate": 1.0
  }
}
```

**Verification:**
- ✅ Metrics recorded
- ✅ Call count correct
- ✅ Success rate calculated

## Test Scenario 2: Test Error Handling

### Step 1: Create Plugin with Invalid URL

**Request:**
```http
POST /api/mcp/plugins
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "plugin_name": "invalid_plugin",
  "display_name": "Invalid Plugin",
  "server_url": "http://invalid-url-that-does-not-exist:9999",
  "enabled": true
}
```

### Step 2: Test Connection

**Request:**
```http
POST /api/mcp/plugins/2/test
Authorization: Bearer <admin_token>
```

**Expected Response:**
```json
{
  "success": false,
  "message": "❌ 插件测试失败",
  "tools_count": 0,
  "error": "Connection timeout" or "Connection refused"
}
```

**Verification:**
- ✅ Error handled gracefully
- ✅ Appropriate error message returned
- ✅ No server crash

### Step 3: Enable Invalid Plugin and Generate Content

**Request:**
```http
POST /api/mcp/plugins/2/toggle
Authorization: Bearer <user_token>
Content-Type: application/json

{
  "enabled": true
}
```

Then generate chapter content.

**Expected Behavior:**
- System attempts to load plugin
- Connection fails
- System continues with other plugins or without tools
- Generation completes successfully (graceful degradation)

**Verification:**
- ✅ Generation doesn't fail
- ✅ Error logged
- ✅ User receives content

## Test Scenario 3: Test Multi-User Isolation

### Step 1: Create Two Users

- User A: Enables plugin 1
- User B: Enables plugin 2

### Step 2: Generate Content for Both Users

**Expected Behavior:**
- User A's generation uses plugin 1 tools only
- User B's generation uses plugin 2 tools only
- No cross-contamination

**Verification:**
- ✅ Check logs for correct tool usage
- ✅ Verify metrics per user
- ✅ No shared state issues

## Test Scenario 4: Test Plugin Updates

### Step 1: Update Plugin Configuration

**Request:**
```http
PUT /api/mcp/plugins/1
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "display_name": "Updated Exa Search",
  "server_url": "http://localhost:9001"
}
```

### Step 2: Verify Changes Take Effect

- Test plugin connection again
- Generate content
- Verify new URL is used

**Verification:**
- ✅ Configuration updated
- ✅ New URL used for connections
- ✅ Old sessions cleaned up

## Test Scenario 5: Test Cache Behavior

### Step 1: Generate Content Multiple Times

Make 3-5 chapter generation requests in quick succession.

**Expected Behavior:**
- First request: Fetches tools from MCP server
- Subsequent requests: Use cached tools
- Check logs for cache hits

**Verification:**
- ✅ Cache hit logged
- ✅ Reduced latency on subsequent requests
- ✅ No unnecessary MCP server calls

### Step 2: Clear Cache

**Request:**
```http
POST /api/mcp/cache/clear
Authorization: Bearer <admin_token>
```

### Step 3: Generate Content Again

**Expected Behavior:**
- Cache miss
- Tools fetched from server again

**Verification:**
- ✅ Cache cleared
- ✅ Fresh fetch logged

## Test Scenario 6: Test Plugin Deletion

### Step 1: Delete Plugin

**Request:**
```http
DELETE /api/mcp/plugins/1
Authorization: Bearer <admin_token>
```

### Step 2: Verify Cleanup

**Checks:**
1. Plugin no longer in database
2. User preferences removed
3. Registry sessions closed
4. Cache entries removed

**Verification:**
- ✅ Complete cleanup
- ✅ No orphaned data
- ✅ No memory leaks

## Logging Verification

Throughout testing, monitor logs for:

1. **Connection Events:**
   ```
   INFO: MCP 插件连接成功: exa_search, 用户: 1
   ```

2. **Tool Calls:**
   ```
   INFO: 工具调用成功: exa_search.search, 耗时: 150.25ms
   ```

3. **Errors:**
   ```
   ERROR: 工具调用失败: invalid_plugin.search, 错误: Connection timeout
   ```

4. **Cache Events:**
   ```
   DEBUG: 工具缓存命中: 1:exa_search (命中次数: 3)
   ```

5. **Metrics:**
   ```
   INFO: 工具指标更新: exa_search.search, 成功率: 0.95
   ```

## Performance Testing

### Load Test

1. Create 10 users
2. Enable plugins for all users
3. Generate 100 concurrent chapter requests
4. Monitor:
   - Response times
   - Error rates
   - Memory usage
   - Connection pool behavior

**Expected:**
- All requests complete successfully
- Average response time < 5 seconds
- No connection pool exhaustion
- LRU eviction working correctly

## Checklist

- [ ] Plugin creation works
- [ ] Plugin testing works
- [ ] Plugin connection succeeds
- [ ] Tools are discovered
- [ ] User can enable/disable plugins
- [ ] Chapter generation uses MCP tools
- [ ] Tool calls execute successfully
- [ ] Metrics are recorded
- [ ] Cache works correctly
- [ ] Error handling is graceful
- [ ] Multi-user isolation works
- [ ] Plugin updates propagate
- [ ] Plugin deletion cleans up
- [ ] Logs are informative
- [ ] Performance is acceptable

## Troubleshooting

### Plugin Connection Fails

1. Check MCP server is running
2. Verify server URL is correct
3. Check network connectivity
4. Verify authentication headers
5. Check server logs for errors

### Tools Not Appearing

1. Verify plugin is enabled globally
2. Verify user has enabled plugin
3. Check cache hasn't expired
4. Verify MCP server returns tools
5. Check logs for errors

### Generation Doesn't Use Tools

1. Verify AI model supports function calling
2. Check tool definitions are valid
3. Verify prompt encourages tool use
4. Check logs for tool call attempts
5. Verify LLM service integration

### Performance Issues

1. Check connection pool size
2. Verify cache is working
3. Check for memory leaks
4. Monitor database query performance
5. Check MCP server response times

## Notes

- Always test with both mock and real MCP servers
- Test error scenarios thoroughly
- Monitor logs during all tests
- Document any unexpected behavior
- Test with realistic data volumes
- Verify cleanup after each test
