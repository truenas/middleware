__all__ = ["serialize_result"]


def serialize_result(model, result, expose_secrets):
    """
    Serializes a `result` of the method execution using the corresponding `model`.

    :param model: `BaseModel` that defines method return value.
    :param result: method return value.
    :param expose_secrets: if false, will replace `Secret` parameters with a placeholder.
    :return: serialized method execution result.
    """
    return model(result=result).model_dump(
        context={"expose_secrets": expose_secrets},
        warnings=False,
        by_alias=True,
    )["result"]
