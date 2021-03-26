from . import falconBase
app = falconBase.app
max_body = falconBase.max_body

#####
# Load all REST service modules below
from .actorService import ActorService
ActorService(app)
