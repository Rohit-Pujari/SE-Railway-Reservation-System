"""Shared input validation primitives used across feature services."""


def positive_int(value, field, error_type, verb="Enter"):
    """Parse a canonical positive integer, rejecting booleans and lossy values.

    ``error_type`` lets each feature expose its own public domain exception
    while keeping the validation rule and accepted input format consistent.
    """
    message = f"{verb} a valid {field}."
    if isinstance(value, bool):
        raise error_type(message)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise error_type(message) from None
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise error_type(message)
    return parsed
