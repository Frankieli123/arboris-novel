import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...repositories.system_config_repository import SystemConfigRepository
from ...schemas.user import UserInDB
from ...schemas.user_settings import UserGeneralSettings
from ...services.admin_setting_service import AdminSettingService
from ...services.user_setting_service import UserSettingService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user-settings", tags=["User Settings"])


def get_user_setting_service(session: AsyncSession = Depends(get_session)) -> UserSettingService:
    return UserSettingService(session)


def get_admin_setting_service(session: AsyncSession = Depends(get_session)) -> AdminSettingService:
    return AdminSettingService(session)


@router.get("/general", response_model=UserGeneralSettings)
async def get_general_settings(
    session: AsyncSession = Depends(get_session),
    user_settings: UserSettingService = Depends(get_user_setting_service),
    admin_settings: AdminSettingService = Depends(get_admin_setting_service),
    current_user: UserInDB = Depends(get_current_user),
) -> UserGeneralSettings:
    """获取当前用户的常规设置。

    优先使用用户个人设置，其次回退到后台全局配置或系统默认值。
    """

    user_id = current_user.id

    # 自动拆分每条大纲的章节数
    user_target = await user_settings.get(user_id, "auto_expand_target_chapter_count")
    target_count: int
    if user_target is not None:
        try:
            target_count = int(user_target)
        except (TypeError, ValueError):
            target_count = 3
    else:
        admin_value = await admin_settings.get("auto_expand_target_chapter_count", "3")
        try:
            target_count = int(admin_value or 3)
        except (TypeError, ValueError):
            target_count = 3
    if target_count < 1:
        target_count = 1
    if target_count > 10:
        target_count = 10

    # 生成蓝图后是否自动拆分章节
    user_enabled = await user_settings.get(user_id, "auto_expand_enabled")
    if user_enabled is not None:
        enabled_source = user_enabled
    else:
        enabled_source = await admin_settings.get("auto_expand_enabled", "false")
    enabled = str(enabled_source).strip().lower() in {"1", "true", "yes", "y", "on"}

    # 每次生成章节的候选版本数量
    user_version_value = await user_settings.get(user_id, "writer.chapter_versions")
    version_count: int
    if user_version_value is not None:
        try:
            version_count = int(user_version_value)
        except (TypeError, ValueError):
            version_count = 3
    else:
        repo = SystemConfigRepository(session)
        record = await repo.get_by_key("writer.chapter_versions")
        if record:
            try:
                version_count = int(record.value)
            except (TypeError, ValueError):
                version_count = 3
        else:
            version_count = 3
    if version_count < 1:
        version_count = 1
    if version_count > 5:
        version_count = 5

    logger.info(
        "用户 %s 获取常规设置：auto_expand_enabled=%s, auto_expand_target_chapter_count=%s, chapter_version_count=%s",
        user_id,
        enabled,
        target_count,
        version_count,
    )

    return UserGeneralSettings(
        auto_expand_enabled=enabled,
        auto_expand_target_chapter_count=target_count,
        chapter_version_count=version_count,
    )


@router.put("/general", response_model=UserGeneralSettings)
async def update_general_settings(
    payload: UserGeneralSettings,
    session: AsyncSession = Depends(get_session),
    user_settings: UserSettingService = Depends(get_user_setting_service),
    current_user: UserInDB = Depends(get_current_user),
) -> UserGeneralSettings:
    """更新当前用户的常规设置，仅对该用户生效。"""

    user_id = current_user.id

    await user_settings.set(user_id, "auto_expand_enabled", "1" if payload.auto_expand_enabled else "0")
    await user_settings.set(
        user_id,
        "auto_expand_target_chapter_count",
        str(payload.auto_expand_target_chapter_count),
    )
    await user_settings.set(user_id, "writer.chapter_versions", str(payload.chapter_version_count))

    logger.info(
        "用户 %s 更新常规设置：auto_expand_enabled=%s, auto_expand_target_chapter_count=%s, chapter_version_count=%s",
        user_id,
        payload.auto_expand_enabled,
        payload.auto_expand_target_chapter_count,
        payload.chapter_version_count,
    )

    return payload
