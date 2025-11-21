from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token
from ..db.session import get_session
from ..repositories.user_repository import UserRepository
from ..schemas.user import UserInDB
from ..services.auth_service import AuthService
from ..mcp.registry import MCPPluginRegistry

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> UserInDB:
    payload = decode_access_token(token)
    username = payload["sub"]
    repo = UserRepository(session)
    user = await repo.get_by_username(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")
    service = AuthService(session)
    schema = UserInDB.model_validate(user)
    schema.must_change_password = service.requires_password_reset(user)
    return schema


async def get_current_admin(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def get_mcp_registry(request: Request) -> MCPPluginRegistry:
    """获取 MCP 插件注册表实例。
    
    从应用状态中获取在启动时初始化的 MCP 插件注册表。
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        MCP 插件注册表实例
        
    Raises:
        HTTPException: 如果注册表未初始化
    """
    registry = getattr(request.app.state, "mcp_registry", None)
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MCP 插件注册表未初始化"
        )
    return registry
