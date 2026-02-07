from handlers.start import register_start_handlers
from handlers.add_channel import register_add_channel_handlers
from handlers.manage_channels import register_manage_channels_handlers
from handlers.create_giveaway import register_create_giveaway_handlers
from handlers.giveaway_callbacks import register_giveaway_callback_handlers
from handlers.dashboard import register_dashboard_handlers
from handlers.help_support import register_help_handlers
from handlers.broadcast import register_broadcast_handlers
from handlers.template_manager import register_template_handlers

def register_handlers(app):
    register_start_handlers(app)
    register_add_channel_handlers(app)
    register_manage_channels_handlers(app)
    register_create_giveaway_handlers(app)
    register_giveaway_callback_handlers(app)
    register_dashboard_handlers(app)
    register_help_handlers(app)
    register_broadcast_handlers(app)
    register_template_handlers(app)
