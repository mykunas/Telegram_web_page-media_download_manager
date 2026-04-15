from typing import Any


def success_response(data: Any = None, message: str = "success") -> dict[str, Any]:
    """Unified success response payload."""

    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error_response(message: str = "error", code: int = 1) -> dict[str, Any]:
    """Unified error response payload."""

    return {
        "code": code,
        "message": message,
        "data": None,
    }


def paginated_response(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    message: str = "success",
) -> dict[str, Any]:
    """Unified paginated success response payload."""

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return success_response(
        data={
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
        message=message,
    )
