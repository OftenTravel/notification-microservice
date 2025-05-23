from app.providers.registry import ProviderRegistry
from app.providers.mock_provider import MockProvider

# Register providers
ProviderRegistry.register("mock", MockProvider)
