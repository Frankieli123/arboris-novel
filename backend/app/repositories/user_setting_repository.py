from typing import Optional

from sqlalchemy import select

from .base import BaseRepository
from ..models import UserSetting


class UserSettingRepository(BaseRepository[UserSetting]):
    model = UserSetting

    async def get_value(self, user_id: int, key: str) -> Optional[str]:
        result = await self.session.execute(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        record = result.scalars().first()
        return record.value if record else None

    async def set_value(self, user_id: int, key: str, value: str) -> None:
        result = await self.session.execute(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        record = result.scalars().first()
        if record:
            await self.update_fields(record, value=value)
        else:
            setting = UserSetting(user_id=user_id, key=key, value=value)
            await self.add(setting)
