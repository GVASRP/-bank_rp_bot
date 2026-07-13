from aiogram import Router
from .start import router as start_router
from .user import router as user_router
from .admin import router as admin_router
from .game import router as game_router
from .salary import router as salary_router
from .fuel import router as fuel_router
from .trailers import router as trailer_router
from .orgs import router as org_router
from .businesses import router as businesses_router
from .betting import router as betting_router
from .insurance import router as insurance_router

router = Router()
router.include_routers(start_router, user_router, admin_router, game_router, salary_router, fuel_router, trailer_router, org_router, businesses_router, betting_router, insurance_router)
