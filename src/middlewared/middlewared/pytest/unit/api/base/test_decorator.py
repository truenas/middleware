import pytest
from typing import Annotated

from middlewared.api.base import BaseModel
from middlewared.api.base.decorator import check_method_annotations


class SimpleArgs(BaseModel):
    name: str
    count: int


class SimpleResult(BaseModel):
    result: str


class MultipleArgs(BaseModel):
    id_: int
    name: str
    enabled: bool


class MultipleResult(BaseModel):
    result: dict[str, int]


class TestCheckMethodAnnotations:
    """Tests for check_method_annotations function."""

    def test_valid_method_annotations(self):
        """Test that valid method annotations pass without error."""
        def method(self, name: str, count: int) -> str:
            pass

        # Should not raise
        check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_valid_method_annotations_multiple_args(self):
        """Test valid annotations with multiple arguments."""
        def method(self, id_: int, name: str, enabled: bool) -> dict[str, int]:
            pass

        # Should not raise
        check_method_annotations(method, 1, MultipleArgs, MultipleResult)

    def test_valid_method_no_self(self):
        """Test valid method without self parameter (static/class method)."""
        def method(name: str, count: int) -> str:
            pass

        # Should not raise
        check_method_annotations(method, 0, SimpleArgs, SimpleResult)

    def test_missing_parameter_annotation(self):
        """Test that missing parameter annotations raise ValueError."""
        def method(self, name, count: int) -> str:
            pass

        with pytest.raises(ValueError, match="must the following signature"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_wrong_parameter_annotation(self):
        """Test that wrong parameter type annotations raise ValueError."""
        def method(self, name: int, count: int) -> str:  # name should be str
            pass

        with pytest.raises(ValueError, match="must the following signature"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_missing_parameter(self):
        """Test that missing parameters raise ValueError."""
        def method(self, name: str) -> str:  # missing count parameter
            pass

        with pytest.raises(ValueError, match="must the following signature"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_extra_parameter(self):
        """Test that extra parameters raise ValueError."""
        def method(self, name: str, count: int, extra: str) -> str:
            pass

        with pytest.raises(ValueError, match="must the following signature"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_missing_return_annotation(self):
        """Test that missing return annotation raises ValueError."""
        def method(self, name: str, count: int):
            pass

        with pytest.raises(ValueError, match="must have a `return` annotation"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_wrong_return_annotation(self):
        """Test that wrong return type annotation raises ValueError."""
        def method(self, name: str, count: int) -> int:  # should return str
            pass

        with pytest.raises(ValueError, match="must have a `return` annotation"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_args_index_offset(self):
        """Test that args_index correctly skips prefix parameters."""
        # Simulating a method with app, job parameters before actual args
        def method(self, app, job, name: str, count: int) -> str:
            pass

        # Should not raise, args_index=3 skips self, app, job
        check_method_annotations(method, 3, SimpleArgs, SimpleResult)

    def test_args_index_offset_mismatch(self):
        """Test that wrong args_index causes validation to fail."""
        def method(self, app, job, name: str, count: int) -> str:
            pass

        # args_index=1 would try to validate app and job as name and count
        with pytest.raises(ValueError, match="must the following signature"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_complex_return_type(self):
        """Test method with complex return type annotation."""
        def method(self, id_: int, name: str, enabled: bool) -> dict[str, int]:
            pass

        # Should not raise
        check_method_annotations(method, 1, MultipleArgs, MultipleResult)

    def test_parameter_order_matters(self):
        """Test that parameter order is validated."""
        def method(self, count: int, name: str) -> str:  # wrong order
            pass

        with pytest.raises(ValueError, match="must the following signature"):
            check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_annotated_type(self):
        """Test that Annotated types work correctly."""
        class AnnotatedArgs(BaseModel):
            name: Annotated[str, "Some metadata"]
            count: int

        def method(self, name: Annotated[str, "Some metadata"], count: int) -> str:
            pass

        # Should not raise
        check_method_annotations(method, 1, AnnotatedArgs, SimpleResult)

    def test_optional_type(self):
        """Test that Optional/None types are validated."""
        class OptionalArgs(BaseModel):
            name: str | None
            count: int

        class OptionalResult(BaseModel):
            result: str | None

        def method(self, name: str | None, count: int) -> str | None:
            pass

        # Should not raise
        check_method_annotations(method, 1, OptionalArgs, OptionalResult)

    def test_no_parameters(self):
        """Test method with no parameters (besides self)."""
        class NoArgs(BaseModel):
            pass

        class NoArgsResult(BaseModel):
            result: str

        def method(self) -> str:
            pass

        # Should not raise
        check_method_annotations(method, 1, NoArgs, NoArgsResult)

    def test_async_method(self):
        """Test that async methods are validated the same way."""
        async def method(self, name: str, count: int) -> str:
            pass

        # Should not raise
        check_method_annotations(method, 1, SimpleArgs, SimpleResult)

    def test_error_message_includes_function_name(self):
        """Test that error messages include the function name."""
        def my_special_method(self, name: int, count: int) -> str:
            pass

        with pytest.raises(ValueError, match="my_special_method"):
            check_method_annotations(my_special_method, 1, SimpleArgs, SimpleResult)
