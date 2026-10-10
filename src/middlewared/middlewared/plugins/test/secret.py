from pydantic import Secret

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.service import Service, job


class TestSecretArgs(BaseModel):
    pass


class TestSecretResult(BaseModel):
    result: Secret[str]


class TestSecretDict(BaseModel):
    username: str
    password: Secret[str]


class TestSecretDictResult(BaseModel):
    result: TestSecretDict


class TestService(Service):
    class Config:
        private = True

    @api_method(TestSecretArgs, TestSecretResult, authorization_required=False)
    async def test_secret(self):
        return "canary"

    @api_method(TestSecretArgs, TestSecretResult, authorization_required=False)
    @job()
    async def test_secret_job(self, job):
        return "canary"

    @api_method(TestSecretArgs, TestSecretDictResult, authorization_required=False)
    async def test_secret_dict(self):
        return {"username": "bob", "password": "canary"}

    @api_method(TestSecretArgs, TestSecretDictResult, authorization_required=False)
    @job()
    async def test_secret_dict_job(self, job):
        return {"username": "bob", "password": "canary"}

    @api_method(TestSecretArgs, TestSecretResult, authorization_required=False)
    async def test_secret_object(self):
        return TestSecretDict(username="bob", password="canary").password

    @api_method(TestSecretArgs, TestSecretResult, authorization_required=False)
    @job()
    async def test_secret_object_job(self, job):
        return TestSecretDict(username="bob", password="canary").password
