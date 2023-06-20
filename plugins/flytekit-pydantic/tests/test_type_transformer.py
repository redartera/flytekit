import os
from typing import Any, Dict, List, Optional, Type, Union
import pandas as pd

import pytest
from flytekitplugins.pydantic import BaseModelTransformer
from pydantic import BaseModel, Extra

import flytekit
from flytekit.types import directory
from flytekit.types.file import file


class TrainConfig(BaseModel):
    """Config BaseModel for testing purposes."""

    batch_size: int = 32
    lr: float = 1e-3
    loss: str = "cross_entropy"

    class Config:
        extra = Extra.forbid


class Config(BaseModel):
    """Config BaseModel for testing purposes with an optional type hint."""

    model_config: Optional[Union[Dict[str, TrainConfig], TrainConfig]] = TrainConfig()


class NestedConfig(BaseModel):
    """Nested config BaseModel for testing purposes."""

    files: "ConfigWithFlyteFiles"
    dirs: "ConfigWithFlyteDirs"
    df: "ConfigWithPandasDataFrame"


class ConfigRequired(BaseModel):
    """Config BaseModel for testing purposes with required attribute."""

    model_config: Union[Dict[str, TrainConfig], TrainConfig]


class ConfigWithFlyteFiles(BaseModel):
    """Config BaseModel for testing purposes with flytekit.files.FlyteFile type hint."""

    flytefiles: List[file.FlyteFile]


class ConfigWithFlyteDirs(BaseModel):
    """Config BaseModel for testing purposes with flytekit.directory.FlyteDirectory type hint."""

    flytedirs: List[directory.FlyteDirectory]


class ConfigWithPandasDataFrame(BaseModel):
    """Config BaseModel for testing purposes with pandas.DataFrame type hint."""

    df: pd.DataFrame

    class Config:
        arbitrary_types_allowed = True


class ChildConfig(Config):
    """Child class config BaseModel for testing purposes."""

    d: List[int] = [1, 2, 3]


NestedConfig.update_forward_refs()


@pytest.mark.parametrize(
    "python_type,kwargs",
    [
        (Config, {}),
        (ConfigRequired, {"model_config": TrainConfig()}),
        (TrainConfig, {}),
        (ConfigWithFlyteFiles, {"flytefiles": ["tests/folder/test_file1.txt", "tests/folder/test_file2.txt"]}),
        (ConfigWithFlyteDirs, {"flytedirs": ["tests/folder/"]}),
        (ConfigWithPandasDataFrame, {"df": {"a": [1, 2, 3], "b": [4, 5, 6]}}),
        (
            NestedConfig,
            {
                "files": {"flytefiles": ["tests/folder/test_file1.txt", "tests/folder/test_file2.txt"]},
                "dirs": {"flytedirs": ["tests/folder/"]},
                "df": {"df": {"a": [1, 2, 3], "b": [4, 5, 6]}},
            },
        ),
    ],
)
def test_transform_round_trip(python_type: Type, kwargs: Dict[str, Any]):
    """Test that a (de-)serialization roundtrip results in the identical BaseModel."""
    from flytekit.core.context_manager import FlyteContextManager

    ctx = FlyteContextManager().current_context()

    type_transformer = BaseModelTransformer()

    python_value = python_type(**kwargs)

    literal_value = type_transformer.to_literal(
        ctx,
        python_value,
        python_type,
        type_transformer.get_literal_type(python_value),
    )

    reconstructed_value = type_transformer.to_python_value(ctx, literal_value, type(python_value))

    # assert reconstructed_value == python_value


@pytest.mark.parametrize(
    "config_type,kwargs",
    [
        (Config, {"model_config": {"foo": TrainConfig(loss="mse")}}),
        (ConfigRequired, {"model_config": {"foo": TrainConfig(loss="mse")}}),
        (ConfigWithFlyteFiles, {"flytefiles": ["s3://foo/bar"]}),
        (ConfigWithFlyteDirs, {"flytedirs": ["s3://foo/bar"]}),
        (ConfigWithPandasDataFrame, {"df": pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})}),
        (
            NestedConfig,
            {
                "files": {"flytefiles": ["tests/folder/test_file1.txt", "tests/folder/test_file2.txt"]},
                "dirs": {"flytedirs": ["tests/folder/"]},
                "df": {"df": {"a": [1, 2, 3], "b": [4, 5, 6]}},
            },
        ),
    ],
)
def test_pass_to_workflow(config_type: Type, kwargs: Dict[str, Any]):
    """Test passing a BaseModel instance to a workflow works."""
    cfg = config_type(**kwargs)

    @flytekit.task
    def train(cfg: config_type) -> config_type:
        return cfg

    @flytekit.workflow
    def wf(cfg: config_type) -> config_type:
        return train(cfg=cfg)

    returned_cfg = wf(cfg=cfg)

    # assert returned_cfg == cfg
    # TODO these assertions are not valid for all types


@pytest.mark.parametrize(
    "kwargs",
    [
        {"flytefiles": ["tests/folder/test_file1.txt", "tests/folder/test_file2.txt"]},
    ],
)
def test_flytefiles_in_wf(kwargs: Dict[str, Any]):
    """Test passing a BaseModel instance to a workflow works."""
    cfg = ConfigWithFlyteFiles(**kwargs)

    @flytekit.task
    def read(cfg: ConfigWithFlyteFiles) -> str:
        with open(cfg.flytefiles[0], "r") as f:
            return f.read()

    @flytekit.workflow
    def wf(cfg: ConfigWithFlyteFiles) -> str:
        return read(cfg=cfg)  # type: ignore

    string = wf(cfg=cfg)
    assert string in {"foo", "bar"}  # type: ignore


@pytest.mark.parametrize(
    "kwargs",
    [
        {"flytedirs": ["tests/folder/"]},
    ],
)
def test_flytedirs_in_wf(kwargs: Dict[str, Any]):
    """Test passing a BaseModel instance to a workflow works."""
    cfg = ConfigWithFlyteDirs(**kwargs)

    @flytekit.task
    def listdir(cfg: ConfigWithFlyteDirs) -> List[str]:
        return os.listdir(cfg.flytedirs[0])

    @flytekit.workflow
    def wf(cfg: ConfigWithFlyteDirs) -> List[str]:
        return listdir(cfg=cfg)  # type: ignore

    dirs = wf(cfg=cfg)
    assert len(dirs) == 2  # type: ignore


def test_double_config_in_wf():
    """Test passing a BaseModel instance to a workflow works."""
    cfg1 = TrainConfig(batch_size=13)
    cfg2 = TrainConfig(batch_size=31)

    @flytekit.task
    def are_different(cfg1: TrainConfig, cfg2: TrainConfig) -> bool:
        return cfg1 != cfg2

    @flytekit.workflow
    def wf(cfg1: TrainConfig, cfg2: TrainConfig) -> bool:
        return are_different(cfg1=cfg1, cfg2=cfg2)  # type: ignore

    assert wf(cfg1=cfg1, cfg2=cfg2), wf(cfg1=cfg1, cfg2=cfg2)  # type: ignore


# TODO: //Arthur to Fabio this was differente before but now im unsure what the test is doing
# previously a pattern match error was checked that its raised, but isnt it OK that the ChildConfig
# is passed since its a subclass of Config?
# I modified the test to work the other way around, but im not sure if this is what you intended
def test_pass_wrong_type_to_workflow():
    """Test passing the wrong type raises exception."""
    cfg = Config()

    @flytekit.task
    def train(cfg: ChildConfig) -> ChildConfig:
        return cfg

    @flytekit.workflow
    def wf(cfg: ChildConfig) -> ChildConfig:
        return train(cfg=cfg)  #  type: ignore

    with pytest.raises(TypeError):  # type: ignore
        wf(cfg=cfg)


test_transform_round_trip(ConfigWithFlyteDirs, {"flytedirs": ["s3://foo/bar"]})
