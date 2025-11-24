from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.user_setting_repository import UserSettingRepository


class UserSettingService:
    """用户级 KV 配置服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserSettingRepository(session)

    async def get(self, user_id: int, key: str, default: Optional[str] = None) -> Optional[str]:
        value = await self.repo.get_value(user_id, key)
        return value if value is not None else default

    async def set(self, user_id: int, key: str, value: str) -> None:
        await self.repo.set_value(user_id, key, value)
        await self.session.commit()
