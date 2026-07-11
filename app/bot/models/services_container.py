from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services import (
        NotificationService,
        PlanService,
        ServerPoolService,
        VPNService,
        ConfigGeneratorService,
        ReferralService,
        SubscriptionService,
        PaymentStatsService,
        InviteStatsService,
    )

from dataclasses import dataclass


@dataclass
class ServicesContainer:
    server_pool: ServerPoolService
    plan: PlanService
    vpn: VPNService
    config_generator: ConfigGeneratorService
    notification: NotificationService
    referral: ReferralService
    subscription: SubscriptionService
    payment_stats: PaymentStatsService
    invite_stats: InviteStatsService