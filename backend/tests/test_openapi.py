from backend.main import app


def resolve(schema: dict, spec: dict) -> dict:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return spec["components"]["schemas"][name]
    return schema


def operations(spec: dict):
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            yield f"{method.upper()} {path}", operation


def test_every_operation_has_an_id_and_a_one_line_docstring():
    spec = app.openapi()
    ids = []
    for name, operation in operations(spec):
        assert operation.get("operationId"), name
        description = operation.get("description", "")
        assert description, name
        assert "\n" not in description.strip(), name
        ids.append(operation["operationId"])
    assert len(ids) == len(set(ids))


def test_no_operation_has_optional_inputs():
    spec = app.openapi()
    for name, operation in operations(spec):
        for parameter in operation.get("parameters", []):
            assert parameter["required"], f"{name}: {parameter['name']}"
        if "requestBody" in operation:
            assert operation["requestBody"]["required"], name
            content = operation["requestBody"]["content"]["application/json"]
            body = resolve(content["schema"], spec)
            assert set(body["properties"]) == set(body.get("required", [])), name
