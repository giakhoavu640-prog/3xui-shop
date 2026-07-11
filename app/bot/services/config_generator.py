import logging
import base64
import json
from py3xui import AsyncApi
from app.db.models import User
from app.config import Config
from .server_pool import ServerPoolService

logger = logging.getLogger(__name__)

class ConfigGeneratorService:
    def __init__(self, config: Config, server_pool_service: ServerPoolService) -> None:
        self.config = config
        self.server_pool_service = server_pool_service
        logger.info("Config Generator Service initialized.")

    async def generate_vless_links(self, user: User) -> str:
        """
        Собирает vless:// ссылки со всех активных серверов для конкретного пользователя.
        """
        servers = list(self.server_pool_service._servers.values())
        if not servers:
            return ""

        links = []

        for connection in servers:
            try:
                # Получаем список всех инбаундов на сервере
                inbounds = await connection.api.inbound.get_list()
                if not inbounds:
                    continue
                
                # Берем первый инбаунд (как и в оригинальном коде пула)
                inbound = inbounds[0]
                
                # Загружаем JSON-настройки сети (транспорт, реалити и т.д.)
                stream_settings = json.loads(inbound.stream_settings)
                settings = json.loads(inbound.settings)
                
                # Собираем параметры безопасности
                security = stream_settings.get("security", "none")
                network_type = stream_settings.get("network", "tcp") # grpc / tcp / ws
                
                # Базовый URL-шаблон
                # Извлекаем IP или домен из host панели (чистим http/https и порты)
                server_host = connection.server.host.split("//")[-1].split(":")[0]
                
                # Формируем параметры запроса (query params)
                query_params = [
                    "encryption=none",
                    f"type={network_type}"
                ]
                
                if security == "reality":
                    reality_settings = stream_settings.get("realitySettings", {})
                    # Вытаскиваем настройки Reality
                    public_key = reality_settings.get("publicKey", "")
                    short_ids = reality_settings.get("shortIds", [""])
                    short_id = short_ids[0] if short_ids else ""
                    
                    # Берем SNI из настроек инбаунда
                    server_names = reality_settings.get("serverNames", [""])
                    sni = server_names[0] if server_names else ""
                    
                    query_params.extend([
                        "security=reality",
                        f"pbk={public_key}",
                        f"sni={sni}",
                        f"sid={short_id}"
                    ])
                    
                    # Если транспорт - gRPC, добавляем имя сервиса
                    if network_type == "grpc":
                        grpc_settings = stream_settings.get("grpcSettings", {})
                        service_name = grpc_settings.get("serviceName", "")
                        query_params.append(f"serviceName={service_name}")
                    # Если TCP Reality, добавляем flow
                    elif network_type == "tcp":
                        query_params.append("flow=xtls-rprx-vision")
                        
                elif security == "tls":
                    tls_settings = stream_settings.get("tlsSettings", {})
                    server_names = tls_settings.get("serverNames", [""])
                    sni = server_names[0] if server_names else ""
                    query_params.extend([
                        "security=tls",
                        f"sni={sni}"
                    ])

                # Склеиваем параметры
                query_str = "&".join(query_params)
                
                # Метка сервера в приложении (Имя сервера из админки бота)
                remark = f"{connection.server.name}"
                
                # Финальная сборка VLESS строки
                vless_link = f"vless://{user.vpn_id}@{server_host}:{inbound.port}?{query_str}#{remark}"
                links.append(vless_link)
                
            except Exception as e:
                logger.error(f"Error parsing inbound on {connection.server.name}: {e}")
                continue

        # Возвращаем все ссылки, разделенные переносом строки
        return "\n".join(links)