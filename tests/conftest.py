import pytest
import pathlib
import gltest.direct as direct

@pytest.fixture
def direct_vm():
    vm = direct.VMContext()
    with vm.activate():
        yield vm

@pytest.fixture
def direct_alice():
    return direct.create_address("alice")

@pytest.fixture
def direct_bob():
    return direct.create_address("bob")

@pytest.fixture
def direct_charlie():
    return direct.create_address("charlie")

@pytest.fixture
def direct_deploy(direct_vm):
    def _deploy(contract_path, *args, **kwargs):
        path = pathlib.Path(contract_path).resolve()
        return direct.deploy_contract(path, direct_vm, *args, **kwargs)
    return _deploy
