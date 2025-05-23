from app.providers.registry import ProviderRegistry
from app.providers.mock_provider import MockProvider
from app.providers.msg91_provider import MSG91Provider

# Register providers
ProviderRegistry.register("mock", MockProvider)
ProviderRegistry.register("msg91", MSG91Provider)
