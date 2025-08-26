import contextlib
import re
from typing import Annotated, Callable, Literal, TypeAlias, Union

from pydantic import AfterValidator, create_model, Field
from pydantic.fields import FieldInfo

from middlewared.api.base import LongString, match_validator, NotRequired
from middlewared.api.base.handler.accept import validate_model
from middlewared.service_exception import ValidationErrors
from middlewared.utils import filter_list

from .pydantic_utils import AbsolutePath, BaseModel, create_length_validated_type, HostPath, IPvAnyAddress, URI


class NotProvided:
    pass


CONTEXT_KEY_NAME = 'ix_context'
RESERVED_NAMES = [
    ('ix_certificates', dict),
    ('ix_certificate_authorities', dict),
    ('ix_volumes', dict),
    (CONTEXT_KEY_NAME, dict),
]
NOT_PROVIDED = NotProvided()
USER_VALUES: TypeAlias = dict | NotProvided


# Functionality we are concerned about which we would like to port over
#
# Make sure immutable types are only supported for basic types strings/booleans/integers/path
# Make sure we have tests for min/max/min_length/max_length

# Functionality to remove (these are not being used and we should remove them to reduce complexity)
# 1) Cron type
# 2) hostpathdirectory type
# 3) hostpathfile type
# 4) additional_attrs field attr is not being used
# 5) subquestions are being removed
# 6) show_subquestions_if are being removed
# 7) removing editable fields


def remove_not_required(data):
    """Recursively remove fields with NotRequired values from the data structure."""
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            # Check if the value is the NotRequired sentinel
            if v is NotRequired or (hasattr(v, '__class__') and v.__class__.__name__ == '_NotRequired'):
                continue  # Skip this field
            # Also check for string representations of NotRequired objects
            if isinstance(v, str) and v.startswith('<middlewared.api.base.model._NotRequired object at'):
                continue  # Skip this field
            result[k] = remove_not_required(v)
        return result
    elif isinstance(data, list):
        return [remove_not_required(item) for item in data]
    return data


def construct_schema(
    item_version_details: dict, new_values: dict, update: bool, old_values: USER_VALUES = NOT_PROVIDED,
) -> dict:
    schema_name = f'app_{"update" if update else "create"}'
    model = generate_pydantic_model(item_version_details['schema']['questions'], schema_name, new_values, old_values)
    verrors = ValidationErrors()
    try:
        # Validate the new values against the generated model
        # exclude_unset=False ensures defaults are populated for fields not provided by user
        new_values = validate_model(model, new_values, exclude_unset=False, expose_secrets=False)
        # Remove any fields that have NotRequired as their value
        new_values = remove_not_required(new_values)
    except ValidationErrors as e:
        # Don't add 'values' prefix - just extend the errors directly
        verrors.extend(e)

    return {
        'verrors': verrors,
        'new_values': new_values,
        'schema_name': schema_name,
    }


def generate_pydantic_model(
    dict_attrs: list[dict], model_name: str, new_values: USER_VALUES = NOT_PROVIDED,
    old_values: USER_VALUES = NOT_PROVIDED, parent_hidden: bool = False,
) -> type[BaseModel]:
    """
    Generate a Pydantic model from a list of dictionary attributes.
    """
    fields = {}
    nested_models = {}
    show_if_attrs = {}
    # Build a context with values and defaults for show_if evaluation
    eval_context = {}
    if isinstance(new_values, dict):
        eval_context.update(new_values)

    # Add defaults for fields that aren't in new_values
    for attr in dict_attrs:
        var_name = attr['variable']
        if var_name not in eval_context and 'default' in attr['schema']:
            eval_context[var_name] = attr['schema']['default']

    for attr in dict_attrs:
        var_name = attr['variable']
        schema_def = attr['schema']
        attr_value = new_values.get(var_name, NOT_PROVIDED) if isinstance(new_values, dict) else NOT_PROVIDED
        old_attr_value = old_values.get(var_name, NOT_PROVIDED) if isinstance(old_values, dict) else NOT_PROVIDED

        # Check if this field should be visible based on its show_if
        field_hidden = parent_hidden
        if not parent_hidden and schema_def.get('show_if'):
            # Evaluate show_if condition against sibling values with defaults
            if eval_context and not filter_list([eval_context], schema_def['show_if']):
                field_hidden = True

        field_type, field_info, nested_model = process_schema_field(
            schema_def, f'{model_name}_{var_name}', attr_value, old_attr_value,
            field_hidden=field_hidden,
        )
        if nested_model:
            nested_models[var_name] = nested_model
        if schema_def.get('show_if'):
            show_if_attrs[var_name] = schema_def['show_if']
        fields[var_name] = (field_type, field_info)

    # Create the model dynamically
    model = create_model(model_name, __base__=BaseModel, **fields)

    if show_if_attrs and not parent_hidden:
        # What we want to do here is make sure that we are not injecting default values
        # for fields which have conditional defaults set
        provided_values = new_values if isinstance(new_values, dict) else {}
        defaults = get_defaults(model, provided_values)
        rebuild = False
        # If we were not able to get defaults, no need to do the below magic
        # It just means that a validation error occurred and we are going to raise it anyways
        # Also if a user already has provided value for some attr which has show_if set, there is
        # no need to mark that field as NotRequired etc
        for attr in filter(lambda k: k not in provided_values, [] if defaults is None else show_if_attrs):
            if not filter_list([defaults], show_if_attrs[attr]):
                # This means we should not be injecting default values here and instead mark it as NotRequired
                fields[attr][1].default = NotRequired
                fields[attr][1].default_factory = None
                rebuild = True

        if rebuild:
            model = create_model(model_name, __base__=BaseModel, **fields)

    return model


def get_defaults(model: type[BaseModel], new_values: dict) -> dict | None:
    # We will try to get default values form the current model being passed by dumping values
    # if we are not able to do that, it is fine - it just probably means that we had
    # required fields and they were not found, in this case we will be raising a validation
    # error to the user anyways
    with contextlib.suppress(ValidationErrors):
        return validate_model(model, new_values)


def process_schema_field(
    schema_def: dict, model_name: str, new_values: USER_VALUES, old_values: USER_VALUES,
    field_hidden: bool = False,
) -> tuple[type, FieldInfo, type[BaseModel] | None]:
    """
    Process a schema field type / field information and any nested model if applicable which was generated.
    """
    schema_type = schema_def['type']
    field_type = nested_model = None
    field_info = create_field_info_from_schema(schema_def, field_hidden=field_hidden)
    match schema_type:
        case 'int':
            field_type = int
        case 'string' | 'text':
            field_type = str if schema_type == 'string' else LongString
            # We can probably have more complex logic here for string types
        case 'boolean':
            field_type = bool
        case 'ipaddr':
            field_type = IPvAnyAddress
        case 'uri':
            field_type = URI
        case 'hostpath':
            if 'min_length' in schema_def or 'max_length' in schema_def:
                field_type = create_length_validated_type(
                    HostPath,
                    min_length=schema_def.get('min_length'),
                    max_length=schema_def.get('max_length'),
                )
            else:
                field_type = HostPath
        case 'path':
            if 'min_length' in schema_def or 'max_length' in schema_def:
                field_type = create_length_validated_type(
                    AbsolutePath,
                    min_length=schema_def.get('min_length'),
                    max_length=schema_def.get('max_length'),
                )
            else:
                field_type = AbsolutePath
        case 'dict':
            if dict_attrs := schema_def.get('attrs', []):
                # Pass field_hidden to nested model generation
                field_type = nested_model = generate_pydantic_model(
                    dict_attrs, model_name, new_values, old_values, parent_hidden=field_hidden
                )
                if not field_hidden:
                    field_info.default_factory = nested_model
            else:
                # We have a generic dict type without specific attributes
                field_type = dict
        case 'list':
            annotated_items = []
            if list_items := schema_def.get('items', []):
                # Get the single item schema (we assume only 1 or 0 items)
                item_schema = list_items[0]['schema']

                # Get actual list values for model generation
                actual_list_values = []
                if isinstance(new_values, list):
                    actual_list_values = new_values
                elif 'default' in schema_def and isinstance(schema_def['default'], list):
                    actual_list_values = schema_def['default']

                # Check if any item has immutable fields
                has_immutable_fields = False
                if item_schema['type'] == 'dict' and 'attrs' in item_schema:
                    for attr in item_schema['attrs']:
                        if attr['schema'].get('immutable'):
                            has_immutable_fields = True
                            break

                # Generate models based on actual values if we have them and it's a dict type
                if actual_list_values and item_schema['type'] == 'dict' and 'attrs' in item_schema:
                    # Check for single discriminator field
                    discriminator = None
                    # Collect all fields referenced in show_if conditions
                    show_if_fields = set()
                    for attr in item_schema['attrs']:
                        if show_if := attr['schema'].get('show_if'):
                            for condition in show_if:
                                if len(condition) == 3 and condition[1] == '=':
                                    show_if_fields.add(condition[0])

                    # Only use discriminator if ALL show_ifs reference the SAME field
                    if len(show_if_fields) == 1:
                        discriminator = show_if_fields.pop()
                    elif len(show_if_fields) > 1:
                        # This should not be the case and should be ensured by apps validation
                        # If this happens, then we don't use any discriminator
                        discriminator = None

                    # Generate a model for each actual list value
                    item_models = []
                    for idx, item_value in enumerate(actual_list_values):
                        # Get old value for immutability checks
                        old_item = (
                            old_values[idx] if isinstance(old_values, list) and idx < len(old_values)
                            else NOT_PROVIDED
                        )

                        # Apply discriminator logic if we have a single clear discriminator
                        attrs_to_use = item_schema['attrs']
                        if discriminator and isinstance(item_value, dict) and discriminator in item_value:
                            # Single discriminator found, using Literal type for proper Union discrimination
                            attrs_to_use = []
                            disc_value = item_value[discriminator]

                            for attr in item_schema['attrs']:
                                if attr['variable'] == discriminator:
                                    # Force Literal type for this specific value
                                    attr_copy = {
                                        'variable': attr['variable'],
                                        'schema': {**attr['schema'], 'enum': [{'value': disc_value}]}
                                    }
                                    attrs_to_use.append(attr_copy)
                                else:
                                    attrs_to_use.append(attr)

                        # Generate model with actual values for proper show_if evaluation
                        # This ensures nested show_if conditions work correctly
                        item_model = generate_pydantic_model(
                            attrs_to_use,
                            f"{model_name}_item_{idx}",
                            item_value if isinstance(item_value, dict) else {},
                            old_item,
                            parent_hidden=field_hidden
                        )
                        item_models.append(item_model)

                    # Create union of all models
                    if item_models:
                        # Use Union for all item models since each has a unique name
                        field_type = list[Union[*item_models]]

                        # Apply immutability validator if needed
                        if has_immutable_fields and isinstance(old_values, list):
                            field_type = Annotated[
                                field_type,
                                AfterValidator(create_list_immutable_validator(list_items, old_values))
                            ]
                else:
                    # No actual values or non-dict items - fallback to existing behavior
                    if has_immutable_fields and old_values is not NOT_PROVIDED and isinstance(old_values, list):
                        # Process items normally but without old values for type generation
                        for item in list_items:
                            item_type, item_info, _ = process_schema_field(
                                item['schema'], f'{model_name}_{item["variable"]}', NOT_PROVIDED, NOT_PROVIDED,
                                field_hidden=field_hidden
                            )
                            annotated_items.append(Annotated[item_type, item_info])
                        # Apply the validator to the list type
                        field_type = Annotated[
                            list[Union[*annotated_items]],
                            AfterValidator(create_list_immutable_validator(list_items, old_values))
                        ]
                    else:
                        # Normal processing without immutability checks
                        for item in list_items:
                            item_type, item_info, _ = process_schema_field(
                                item['schema'], f'{model_name}_{item["variable"]}', NOT_PROVIDED, NOT_PROVIDED,
                                field_hidden=field_hidden
                            )
                            annotated_items.append(Annotated[item_type, item_info])
                        field_type = list[Union[*annotated_items]]
            else:
                # We have a generic list type without specific items
                field_type = list
        case _:
            raise ValueError(f'Unsupported schema type: {schema_type!r}')

    assert field_type is not None

    if schema_def.get('null', False):
        field_type = Union[field_type, None]

    if schema_def.get('immutable') and schema_type in (
        'string', 'int', 'boolean', 'path'
    ) and old_values is not NOT_PROVIDED:
        # If we have a value for this field in old_values, we should not allow it to be changed
        field_type = Literal[old_values]
    elif schema_def.get('enum') and schema_type == 'string':
        enum_values = [v['value'] for v in schema_def['enum']]
        if enum_values:  # Only create Literal if there are actual enum values
            field_type = Literal[*enum_values]

    if schema_def.get('valid_chars'):
        # If valid_chars is specified, we can use a match_validator to ensure the value matches the regex
        field_type = Annotated[field_type, AfterValidator(match_validator(re.compile(schema_def['valid_chars'])))]

    return field_type, field_info, nested_model


def create_field_info_from_schema(schema_def: dict, field_hidden: bool = False) -> FieldInfo:
    """
    Create Pydantic Field info from schema definition.
    """
    field_kwargs = {}

    if 'description' in schema_def:
        field_kwargs['description'] = schema_def['description']

    if 'title' in schema_def:
        field_kwargs['title'] = schema_def['title']

    # If field is hidden by parent's show_if, make it NotRequired
    if field_hidden:
        field_kwargs['default'] = NotRequired
    elif 'default' in schema_def:
        field_kwargs['default'] = schema_def['default']
    elif not schema_def.get('required', False):
        # If a field is not marked as required, we set default to NotRequired
        # which means that it is fine if this field is not set/specified and will
        # not be added to normalized data
        # lists/dicts are special in our old implementation as they always have their
        # defaults populated if none are set
        if schema_def['type'] == 'list':
            field_kwargs['default_factory'] = list
        elif schema_def['type'] == 'dict':
            field_kwargs['default_factory'] = dict
        else:
            field_kwargs['default'] = NotRequired

    # Add validation constraints
    if schema_def['type'] == 'list':
        # For lists, min/max refer to the number of items
        if 'min' in schema_def:
            field_kwargs['min_length'] = schema_def['min']
        if 'max' in schema_def:
            field_kwargs['max_length'] = schema_def['max']
    elif schema_def['type'] in ('string', 'text', 'path'):
        # For string types, use min_length/max_length
        # Skip hostpath if it has length constraints (handled in type)
        if 'min_length' in schema_def:
            field_kwargs['min_length'] = schema_def['min_length']
        if 'max_length' in schema_def:
            field_kwargs['max_length'] = schema_def['max_length']
    else:
        # For numeric types (int), min/max are bounds
        if 'min' in schema_def:
            field_kwargs['ge'] = schema_def['min']
        if 'max' in schema_def:
            field_kwargs['le'] = schema_def['max']

    return Field(**field_kwargs)


def create_list_immutable_validator(item_schemas: list, old_list: list) -> Callable:
    # Create a validator that will check immutability at runtime
    def validate_immutable_list(v):
        if not isinstance(v, list):
            return v

        # Validate each item against its old value
        for i, item in enumerate(v):
            if i < len(old_list) and isinstance(old_list[i], dict):
                old_item = old_list[i]
                # Check each field in the item
                for item_schema in item_schemas:
                    if item_schema['schema']['type'] == 'dict' and 'attrs' in item_schema['schema']:
                        for attr in item_schema['schema']['attrs']:
                            field_name = attr['variable']
                            if attr['schema'].get('immutable') and field_name in old_item:
                                # The item might be a Pydantic model, not a dict
                                if hasattr(item, field_name):
                                    new_value = getattr(item, field_name)
                                elif isinstance(item, dict):
                                    new_value = item.get(field_name)
                                else:
                                    continue

                                if new_value != old_item[field_name]:
                                    raise ValueError(
                                        f"Cannot change immutable field '{field_name}' "
                                        f"from '{old_item[field_name]}' to '{new_value}'"
                                    )
        return v

    return validate_immutable_list
