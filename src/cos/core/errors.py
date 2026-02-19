"""Exception hierarchy for cos."""


class CosError(Exception):
    """Base exception for all cos errors."""


class ConfigError(CosError):
    """Configuration-related errors."""


class AuthError(CosError):
    """Authentication and credential errors."""


class IntegrationError(CosError):
    """External service integration errors."""


class CosMemoryError(CosError):
    """Memory/knowledge engine errors."""


class AgentError(CosError):
    """Agent execution errors."""


class BudgetExceededError(CosError):
    """Token/cost budget exceeded."""
