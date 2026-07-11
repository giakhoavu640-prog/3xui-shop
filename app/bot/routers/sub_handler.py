import logging
import base64
from aiohttp.web import Request, Response, HTTPNotFound
from sqlalchemy import select
from app.db.models import User

logger = logging.getLogger(__name__)

async def handle_subscription(request: Request) -> Response:
    # 1. Извлекаем vpn_id из параметров пути
    vpn_id = request.match_info.get("vpn_id")
    if not vpn_id:
        return Response(status=400, text="Missing subscription ID")

    # 2. Достаем диспетчер по правильному системному ключу aiogram
    dispatcher = request.app.get("dispatcher")
    if not dispatcher:
        logger.error("Aiogram dispatcher not found in aiohttp app context")
        return Response(status=500, text="Internal Server Error")
        
    db = dispatcher.workflow_data.get("db")
    services = dispatcher.workflow_data.get("services")
    
    if not db or not services:
        logger.error("Database or ServicesContainer not found in workflow data")
        return Response(status=500, text="Internal Server Error")

    # 3. Ищем пользователя в БД по его vpn_id
    async with db.session() as session:
        query = await session.execute(select(User).where(User.vpn_id == vpn_id))
        user = query.scalar_one_or_none()

    if not user:
        logger.warning(f"Subscription request with unknown vpn_id: {vpn_id}")
        raise HTTPNotFound(text="Subscription not found")

    # 4. Проверяем состояние подписки через vpn_service
    client_data = await services.vpn.get_client_data(user)
    
    # Если подписка истекла или клиента нет на серверах — отдаем пустой список
    if not client_data or client_data.has_subscription_expired:
        logger.info(f"Expired or inactive subscription requested for user {user.tg_id}")
        return Response(text="", content_type="text/plain", charset="utf-8")

    # 5. Генерируем мультиссылку VLESS
    links = await services.config_generator.generate_vless_links(user)
    
    # Кодируем в Base64 для совместимости с клиентами (Nekobox, v2rayN и др.)
    encoded_links = base64.b64encode(links.encode("utf-8")).decode("utf-8")

    logger.info(f"Successfully served multi-subscription for user {user.tg_id}")
    return Response(text=encoded_links, content_type="text/plain", charset="utf-8")
