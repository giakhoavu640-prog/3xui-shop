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
        Собирает vless:// ссылки со всех активных серверов со всеми квантовыми параметрами Reality.
        """
        servers = list(self.server_pool_service._servers.values())
        if not servers:
            logger.warning("No active servers found in server pool during config generation.")
            return ""

        links = []

        for connection in servers:
            try:
                # Получаем список инбаундов
                inbounds = await connection.api.inbound.get_list()
                if not inbounds:
                    logger.warning(f"No inbounds found on server: {connection.server.name}")
                    continue
                
                inbound = inbounds[0]
                
                # 1. Безопасно переводим stream_settings в словарь
                if isinstance(inbound.stream_settings, str):
                    stream_settings = json.loads(inbound.stream_settings)
                elif hasattr(inbound.stream_settings, "model_dump"):
                    stream_settings = inbound.stream_settings.model_dump()
                elif hasattr(inbound.stream_settings, "__dict__"):
                    stream_settings = inbound.stream_settings.__dict__
                else:
                    stream_settings = dict(inbound.stream_settings)

                # 2. Безопасно переводим settings в словарь
                if isinstance(inbound.settings, str):
                    settings = json.loads(inbound.settings)
                elif hasattr(inbound.settings, "model_dump"):
                    settings = inbound.settings.model_dump()
                elif hasattr(inbound.settings, "__dict__"):
                    settings = inbound.settings.__dict__
                else:
                    settings = dict(inbound.settings)

                # ВЫВОДИМ СЫРЫЕ ДАННЫЕ ДЛЯ ОТЛАДКИ В ЛОГИ
                logger.info(f"=== СЫРЫЕ НАСТРОЙКИ СЕРВЕРА {connection.server.name} ===")
                logger.info(f"stream_settings: {stream_settings}")
                logger.info(f"settings: {settings}")
                logger.info("=====================================================")

                security = stream_settings.get("security", "none")
                network_type = stream_settings.get("network", "tcp")
                
                # Извлекаем хост ноды
                server_host = connection.server.host.split("//")[-1].split(":")[0]
                
                # Базовые query params
                query_params = [
                    "encryption=none",
                    f"type={network_type}"
                ]
                
                if security == "reality":
                    reality_settings = stream_settings.get("reality_settings", stream_settings.get("realitySettings", {}))
                    inner_settings = reality_settings.get("settings", {})
                    
                    public_key = inner_settings.get("publicKey", inner_settings.get("public_key", ""))
                    if not public_key:
                        public_key = reality_settings.get("public_key", reality_settings.get("publicKey", ""))

                    fp = inner_settings.get("fingerprint", inner_settings.get("fp", "chrome"))
                    spider_x = inner_settings.get("spiderX", inner_settings.get("spider_x", "/"))

                    short_ids = reality_settings.get("short_ids", reality_settings.get("shortIds", []))
                    short_id = short_ids[0] if short_ids else ""
                    
                    server_names = reality_settings.get("server_names", reality_settings.get("serverNames", []))
                    sni = server_names[0] if server_names else ""
                    
                    query_params.extend([
                        "security=reality",
                        f"pbk={public_key}",
                        f"sni={sni}",
                        f"sid={short_id}",
                        f"fp={fp}",
                        f"spx={spider_x}"
                    ])
                    
                    mldsa_verify = inner_settings.get("mldsa65Verify", inner_settings.get("mldsa65_verify", ""))
                    if mldsa_verify:
                        query_params.append(f"mldsa65Verify={mldsa_verify}")
                    
                    if network_type == "grpc":
                        grpc_settings = stream_settings.get("grpc_settings", stream_settings.get("grpcSettings", {}))
                        service_name = grpc_settings.get("service_name", grpc_settings.get("serviceName", ""))
                        if not service_name:
                            service_name = settings.get("serviceName", settings.get("service_name", ""))
                        query_params.append(f"serviceName={service_name}")
                    elif network_type == "tcp":
                        query_params.append("flow=xtls-rprx-vision")
                        
                elif security == "tls":
                    tls_settings = stream_settings.get("tls_settings", stream_settings.get("tlsSettings", {}))
                    server_names = tls_settings.get("server_names", tls_settings.get("serverNames", [""]))
                    sni = server_names[0] if server_names else ""
                    query_params.extend([
                        "security=tls",
                        f"sni={sni}"
                    ])

                query_str = "&".join(query_params)
                remark = f"{connection.server.name}"
                
                vless_link = f"vless://{user.vpn_id}@{server_host}:{inbound.port}?{query_str}#{remark}"
                logger.info(f"Сгенерирована ссылка для {connection.server.name}: {vless_link}")
                links.append(vless_link)
                
            except Exception as e:
                logger.error(f"Error parsing inbound on {connection.server.name}: {e}", exc_info=True)
                continue

        return "\n".join(links)
