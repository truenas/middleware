__all__ = ["serialize_result"]


def serialize_result(model, result, expose_secrets):
    if expose_secrets:
        return result

    return model(result=result).model_dump(
        context={"expose_secrets": expose_secrets},
        warnings=False,
        by_alias=True,
    )["result"]
