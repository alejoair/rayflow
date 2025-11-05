"""Basic tests for RayFlow package."""

import rayflow


def test_package_import():
    """Test that rayflow package can be imported."""
    assert rayflow is not None


def test_version():
    """Test that version is defined."""
    assert hasattr(rayflow, "__version__")
    assert rayflow.__version__ == "0.1.0"
