from aiogram import Router
from .start import router as start_router
from .user import router as user_router
from .admin import router as admin_router
from .game import router as game_router

router = Router()
router.include_routers(start_router, user_router, admin_router, game_router)
