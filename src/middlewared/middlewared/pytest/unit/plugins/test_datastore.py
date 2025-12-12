from contextlib import asynccontextmanager
import datetime
from unittest.mock import ANY, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from middlewared.plugins.datastore.write import NoRowsWereUpdatedException
from middlewared.sqlalchemy import EncryptedText, JSON, Time

import middlewared.plugins.datastore  # noqa
import middlewared.plugins.datastore.connection  # noqa
import middlewared.plugins.datastore.schema  # noqa
import middlewared.plugins.datastore.util  # noqa

from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware

DatastoreService = load_compound_service("datastore")

Model = declarative_base()


@asynccontextmanager
async def datastore_test(mocked_calls=None):
    mocked_calls = mocked_calls or {}
    m = Middleware()
    with patch("middlewared.plugins.datastore.connection.FREENAS_DATABASE", ":memory:"):
        with patch("middlewared.plugins.datastore.schema.Model", Model):
            with patch("middlewared.plugins.datastore.util.Model", Model):
                ds = DatastoreService(m)
                ds.setup()

                for part in ds.parts:
                    if hasattr(part, "connection"):
                        Model.metadata.create_all(bind=part.connection)
                        break
                else:
                    raise RuntimeError("Could not find part that provides connection")

                m["datastore.execute"] = ds.execute
                m["datastore.execute_write"] = ds.execute_write
                m["datastore.fetchall"] = ds.fetchall

                m["datastore.query"] = ds.query
                m["datastore.send_insert_events"] = ds.send_insert_events
                m["datastore.send_update_events"] = ds.send_update_events
                m["datastore.send_delete_events"] = ds.send_delete_events

                m["datastore.insert"] = ds.insert
                m["datastore.update"] = ds.update
                m["datastore.delete"] = ds.delete

                for call_name, call_func in mocked_calls.items():
                    m[call_name] = call_func

                yield ds


class UserModel(Model):
    __tablename__ = 'account_bsdusers'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdusr_uid = sa.Column(sa.Integer(), nullable=False)
    bsdusr_group_id = sa.Column(sa.ForeignKey('account_bsdgroups.id'), nullable=False)


class GroupModel(Model):
    __tablename__ = 'account_bsdgroups'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrp_gid = sa.Column(sa.Integer(), nullable=False)


class GroupMembershipModel(Model):
    __tablename__ = 'account_bsdgroupmembership'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrpmember_group_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdgroups.id", ondelete="CASCADE"),
                                      nullable=False)
    bsdgrpmember_user_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdusers.id", ondelete="CASCADE"),
                                     nullable=False)


class UserCascadeModel(Model):
    __tablename__ = 'account_bsdusers_cascade'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdusr_uid = sa.Column(sa.Integer(), nullable=False)
    bsdusr_group_id = sa.Column(sa.ForeignKey('account_bsdgroups.id', ondelete='CASCADE'), nullable=False)


@pytest.mark.asyncio
async def test__relationship_load():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (10, 1010)")
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")
        ds.execute("INSERT INTO `account_bsdgroupmembership` VALUES (1, 10, 5)")

        assert await ds.query("account.bsdgroupmembership") == [
            {
                "id": 1,
                "bsdgrpmember_group": {
                    "id": 10,
                    "bsdgrp_gid": 1010,
                },
                "bsdgrpmember_user": {
                    "id": 5,
                    "bsdusr_uid": 55,
                    "bsdusr_group": {
                        "id": 20,
                        "bsdgrp_gid": 2020,
                    },
                }
            }
        ]


@pytest.mark.asyncio
async def test__filter_join():

    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (10, 1010)")
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (4, 44, 10)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")

        result = await ds.query("account.bsdusers", [("bsdusr_group__bsdgrp_gid", "=", 2020)])
        assert len(result) == 1
        assert result[0]["id"] == 5


@pytest.mark.asyncio
async def test__prefix():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")

        assert await ds.query("account.bsdusers", [], {"prefix": "bsdusr_"}) == [
            {
                "id": 5,
                "uid": 55,
                "group": {
                    "id": 20,
                    "bsdgrp_gid": 2020,
                },
            }
        ]


@pytest.mark.asyncio
async def test__prefix_filter():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")

        assert await ds.query("account.bsdusers", [("uid", "=", 55)], {"prefix": "bsdusr_"}) == [
            {
                "id": 5,
                "uid": 55,
                "group": {
                    "id": 20,
                    "bsdgrp_gid": 2020,
                },
            }
        ]
        assert await ds.query("account.bsdusers", [("uid", "=", 56)], {"prefix": "bsdusr_"}) == []

        with pytest.raises(Exception):
            assert await ds.query("account.bsdusers", [("uuid", "=", 55)], {"prefix": "bsdusr_"})


@pytest.mark.asyncio
async def test__fk_filter():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")

        assert await ds.query("account.bsdusers", [("group", "=", 20)], {"prefix": "bsdusr_"}) == [
            {
                "id": 5,
                "uid": 55,
                "group": {
                    "id": 20,
                    "bsdgrp_gid": 2020,
                },
            }
        ]


@pytest.mark.asyncio
async def test__inserted_primary_key():
    async with datastore_test() as ds:
        assert await ds.insert("account.bsdgroups", {"bsdgrp_gid": 5}) == 1
        assert await ds.insert("account.bsdgroups", {"bsdgrp_gid": 10}) == 2


@pytest.mark.asyncio
async def test__update_filter__too_much_rows():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (30, 3030)")

        with pytest.raises(RuntimeError):
            await ds.update("account_bsdgroups", [("bsdgrp_gid", ">", 1000)], {"bsdgrp_gid": 1000})


@pytest.mark.asyncio
async def test__update_fk():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (30, 3030)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")

        await ds.update("account_bsdusers", 5, {"bsdusr_uid": 100, "bsdusr_group": 30})

        ds.middleware.call_hook_inline.assert_called_once_with(
            "datastore.post_execute_write",
            "UPDATE account_bsdusers SET bsdusr_uid=?, bsdusr_group_id=? WHERE account_bsdusers.id = ?",
            [100, 30, 5],
            ANY,
        )


@pytest.mark.asyncio
async def test__bad_fk_update():
    async with datastore_test() as ds:
        with pytest.raises(NoRowsWereUpdatedException):
            ds.execute("INSERT INTO `account_bsdgroups` VALUES (5, 50)")
            assert await ds.update("account.bsdgroups", 1, {"bsdgrp_gid": 5})


@pytest.mark.asyncio
async def test__bad_fk_insert():
    async with datastore_test() as ds:
        with pytest.raises(IntegrityError):
            assert await ds.insert("account.bsdusers", {"bsdusr_uid": 100, "bsdusr_group": 30})


@pytest.mark.asyncio
async def test__bad_fk_load():
    async with datastore_test() as ds:
        ds.execute("PRAGMA foreign_keys=OFF")
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 21)")

        assert await ds.query("account.bsdusers", [], {"prefix": "bsdusr_"}) == [
            {
                "id": 5,
                "uid": 55,
                "group": None,
            }
        ]


@pytest.mark.asyncio
async def test__delete_fk():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers` VALUES (5, 55, 20)")

        with pytest.raises(IntegrityError):
            await ds.delete("account.bsdgroups", 20)


@pytest.mark.asyncio
async def test__delete_fk_cascade():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `account_bsdgroups` VALUES (20, 2020)")
        ds.execute("INSERT INTO `account_bsdusers_cascade` VALUES (5, 55, 20)")

        await ds.delete("account.bsdgroups", 20)

        assert await ds.query("account.bsdgroups") == []


@pytest.mark.asyncio
async def test__get_backrefs():
    async with datastore_test() as ds:
        assert await ds.get_backrefs("account.bsdgroups") == [
            ("account.bsdusers", "bsdusr_group"),
        ]


class NullableFkModel(Model):
    __tablename__ = 'test_nullablefk'

    id = sa.Column(sa.Integer(), primary_key=True)
    user_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdusers.id"), nullable=True)


@pytest.mark.asyncio
async def test__null_fk_load():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO `test_nullablefk` VALUES (1, NULL)")

        assert await ds.query("test.nullablefk") == [
            {
                "id": 1,
                "user": None,
            }
        ]


class StringModel(Model):
    __tablename__ = 'test_string'

    id = sa.Column(sa.Integer(), primary_key=True)
    string = sa.Column(sa.String(100), nullable=True)


@pytest.mark.parametrize("filter_,ids", [
    ([("string", "~", "(e|u)m")], [1, 2]),
    ([("string", "~", "L?rem")], [1]),

    ([("string", "in", ["Ipsum", "dolor"])], [2]),
    ([("string", "nin", ["Ipsum", "dolor"])], [1]),

    ([("string", "in", [None, "Ipsum"])], [2, 3]),
    ([("string", "nin", [None, "Ipsum"])], [1]),
    ([("string", "in", [None])], [3]),
    ([("string", "nin", [None])], [1, 2]),

    ([("string", "^", "Lo")], [1]),
    ([("string", "$", "um")], [2]),
])
@pytest.mark.asyncio
async def test__string_filters(filter_, ids):
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_string VALUES (1, 'Lorem')")
        ds.execute("INSERT INTO test_string VALUES (2, 'Ipsum')")
        ds.execute("INSERT INTO test_string VALUES (3, NULL)")

        assert [row["id"] for row in await ds.query("test.string", filter_)] == ids


@pytest.mark.asyncio
async def test_delete_not_in():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_string VALUES (1, 'Lorem')")
        ds.execute("INSERT INTO test_string VALUES (2, 'Ipsum')")
        ds.execute("INSERT INTO test_string VALUES (3, 'dolor')")
        ds.execute("INSERT INTO test_string VALUES (4, 'sit')")
        ds.execute("INSERT INTO test_string VALUES (5, 'amer')")

        await ds.delete("test_string", [["string", "nin", ["Lorem", "dolor"]]])

        assert [row["id"] for row in await ds.query("test.string")] == [1, 3]


class IntegerModel(Model):
    __tablename__ = 'test_integer'

    id = sa.Column(sa.Integer(), primary_key=True)
    integer = sa.Column(sa.Integer())


@pytest.mark.parametrize("filter_,ids", [
    ([("integer", ">", 1), ("integer", "<", 5)], [2, 3, 4]),
    ([("OR", [("integer", ">=", 4), ("integer", "<=", 2)])], [1, 2, 4, 5]),
])
@pytest.mark.asyncio
async def test__logic(filter_, ids):
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_integer VALUES (1, 1)")
        ds.execute("INSERT INTO test_integer VALUES (2, 2)")
        ds.execute("INSERT INTO test_integer VALUES (3, 3)")
        ds.execute("INSERT INTO test_integer VALUES (4, 4)")
        ds.execute("INSERT INTO test_integer VALUES (5, 5)")

        assert [row["id"] for row in await ds.query("test.integer", filter_)] == ids


@pytest.mark.parametrize("order_by,ids", [
    (["integer", "id"], [1, 2, 3, 4]),
    (["integer", "-id"], [1, 3, 2, 4]),
])
@pytest.mark.asyncio
async def test__order_by(order_by, ids):
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_integer VALUES (1, 1)")
        ds.execute("INSERT INTO test_integer VALUES (2, 2)")
        ds.execute("INSERT INTO test_integer VALUES (3, 2)")
        ds.execute("INSERT INTO test_integer VALUES (4, 3)")

        assert [row["id"] for row in await ds.query("test.integer", [], {"order_by": order_by})] == ids


class JSONModel(Model):
    __tablename__ = 'test_json'

    id = sa.Column(sa.Integer(), primary_key=True)
    json_dict = sa.Column(JSON())
    json_list = sa.Column(JSON(list))


@pytest.mark.parametrize("id_, json_dict, json_list, json_dict_result, json_list_result", [
    (1, '{"key": "value"}', '[1, 2]', {"key": "value"}, [1, 2]),  # proper JSON
    (2, '{"key": "value"', '[1, 2', {}, []),                      # improper JSON
])
@pytest.mark.asyncio
async def test__json_load(id_, json_dict, json_list, json_dict_result, json_list_result):
    async with datastore_test() as ds:
        ds.execute(f"INSERT INTO test_json VALUES ({id_}, '{json_dict}', '{json_list}')")
        row = await ds.query("test.json", [["id", "=", id_]], {"get": True})
        assert row["json_dict"] == json_dict_result and row["json_list"] == json_list_result


@pytest.mark.asyncio
async def test__json_save():
    async with datastore_test() as ds:
        await ds.insert("test.json", {"json_dict": {"key": "value"}, "json_list": [1, 2]})
        row = ds.fetchall("SELECT * FROM test_json")[0]
        assert row["json_dict"] == '{"key": "value"}' and row["json_list"] == '[1, 2]'


class EncryptedJSONModel(Model):
    __tablename__ = 'test_encryptedjson'

    id = sa.Column(sa.Integer(), primary_key=True)
    json_dict = sa.Column(JSON(encrypted=True))
    json_list = sa.Column(JSON(list, encrypted=True))


class EncryptedTextModel(Model):
    __tablename__ = 'test_encryptedtext'

    id = sa.Column(sa.Integer(), primary_key=True)
    object = sa.Column(EncryptedText(), nullable=True)


def decrypt(s, _raise=False):
    assert _raise is True

    if not s.startswith("!"):
        raise Exception("Decryption failed")

    return s[1:]


def decrypt_safe(s):
    if not s.startswith("!"):
        return ""

    return s[1:]


def encrypt(s):
    return f"!{s}"


@pytest.mark.parametrize("id_, json_dict, json_list, json_dict_result, json_list_result", [
    (1, '!{"key": "value"}', '![1, 2]', {"key": "value"}, [1, 2]),  # proper JSON
    (2, '!{"key": "value"', '![1, 2', {}, []),                      # improper JSON
    (3, '{"key": "value"}', '[1, 2]', {}, []),                      # not encrypted
])
@pytest.mark.asyncio
async def test__encrypted_json_load(id_, json_dict, json_list, json_dict_result, json_list_result):
    async with datastore_test() as ds:
        ds.execute(f"INSERT INTO test_encryptedjson VALUES ({id_}, '{json_dict}', '{json_list}')")

        with patch("middlewared.sqlalchemy.decrypt", decrypt):
            row = await ds.query("test.encryptedjson", [["id", "=", id_]], {"get": True})
            assert row["json_dict"] == json_dict_result and row["json_list"] == json_list_result


@pytest.mark.asyncio
async def test__encrypted_json_save():
    async with datastore_test() as ds:
        with patch("middlewared.sqlalchemy.encrypt", encrypt):
            await ds.insert("test.encryptedjson", {"json_dict": {"key": "value"}, "json_list": [1, 2]})

        row = ds.fetchall("SELECT * FROM test_encryptedjson")[0]
        assert row["json_dict"] == '!{"key": "value"}' and row["json_list"] == '![1, 2]'

        ds.middleware.call_hook_inline.assert_called_once_with(
            "datastore.post_execute_write",
            "INSERT INTO test_encryptedjson (json_dict, json_list) VALUES (?, ?)",
            ['!{"key": "value"}', '![1, 2]'],
            ANY,
        )


@pytest.mark.parametrize("string,object_", [
    ('!Text', 'Text'),
    ('Text', ''),
])
@pytest.mark.asyncio
async def test__encrypted_text_load(string, object_):
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_encryptedtext VALUES (1, ?)", string)

        with patch("middlewared.sqlalchemy.decrypt", decrypt_safe):
            assert (await ds.query("test.encryptedtext", [], {"get": True}))["object"] == object_


@pytest.mark.asyncio
async def test__encrypted_text_save():
    async with datastore_test() as ds:
        with patch("middlewared.sqlalchemy.encrypt", encrypt):
            await ds.insert("test.encryptedtext", {"object": 'Text'})

        assert (ds.fetchall("SELECT * FROM test_encryptedtext"))[0]["object"] == '!Text'

        ds.middleware.call_hook_inline.assert_called_once_with(
            "datastore.post_execute_write",
            "INSERT INTO test_encryptedtext (object) VALUES (?)",
            ['!Text'],
            ANY,
        )


@pytest.mark.asyncio
async def test__encrypted_text_load_null():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_encryptedtext VALUES (1, NULL)")

        with patch("middlewared.sqlalchemy.decrypt", decrypt_safe):
            assert (await ds.query("test.encryptedtext", [], {"get": True}))["object"] is None


@pytest.mark.asyncio
async def test__encrypted_text_save_null():
    async with datastore_test() as ds:
        with patch("middlewared.sqlalchemy.encrypt", encrypt):
            await ds.insert("test.encryptedtext", {"object": None})

        assert (ds.fetchall("SELECT * FROM test_encryptedtext"))[0]["object"] is None

        ds.middleware.call_hook_inline.assert_called_once_with(
            "datastore.post_execute_write",
            "INSERT INTO test_encryptedtext (object) VALUES (?)",
            [None],
            ANY,
        )


class CustomPkModel(Model):
    __tablename__ = 'test_custompk'

    custom_identifier = sa.Column(sa.String(42), primary_key=True)
    custom_name = sa.Column(sa.String(120))


@pytest.mark.asyncio
async def test__custom_pk_query():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_custompk VALUES ('ID1', 'Test 1')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID2', 'Test 2')")

        result = await ds.query("test.custompk", [("identifier", "=", "ID1")], {"prefix": "custom_", "get": True})
        assert result == {"identifier": "ID1", "name": "Test 1"}


@pytest.mark.asyncio
async def test__custom_pk_count():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_custompk VALUES ('ID1', 'Test 1')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID2', 'Test 2')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID3', 'Other Test')")

        assert await ds.query("test.custompk", [("name", "^", "Test")], {"prefix": "custom_", "count": True}) == 2


@pytest.mark.asyncio
async def test__custom_pk_update():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_custompk VALUES ('ID1', 'Test 1')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID2', 'Test 2')")

        await ds.update("test.custompk", "ID1", {"name": "Updated"}, {"prefix": "custom_"})

        result = await ds.query("test.custompk", [("identifier", "=", "ID1")], {"prefix": "custom_", "get": True})
        assert result == {"identifier": "ID1", "name": "Updated"}


@pytest.mark.asyncio
async def test__custom_pk_delete():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_custompk VALUES ('ID1', 'Test 1')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID2', 'Test 2')")

        await ds.delete("test.custompk", "ID1")

        assert await ds.query("test.custompk", [], {"count": True}) == 1


@pytest.mark.asyncio
async def test__delete_by_filter():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO test_custompk VALUES ('ID1', 'Test 1')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID2', 'Test 2')")
        ds.execute("INSERT INTO test_custompk VALUES ('ID3', 'Other Test')")

        await ds.delete("test.custompk", [("custom_name", "^", "Test")])

        assert await ds.query("test.custompk", [], {"count": True}) == 1


class DiskModel(Model):
    __tablename__ = 'storage_disk'

    id = sa.Column(sa.Integer(), primary_key=True)


class SMARTTestModel(Model):
    __tablename__ = 'tasks_smarttest'

    id = sa.Column(sa.Integer(), primary_key=True)

    smarttest_disks = relationship('DiskModel', secondary=lambda: SMARTTestDiskModel.__table__)


class SMARTTestDiskModel(Model):
    __tablename__ = 'tasks_smarttest_smarttest_disks'

    id = sa.Column(sa.Integer(), primary_key=True)
    smarttest_id = sa.Column(sa.Integer(), sa.ForeignKey('tasks_smarttest.id'))
    disk_id = sa.Column(sa.Integer(), sa.ForeignKey('storage_disk.id'))


@pytest.mark.asyncio
async def test__bad_fk_insert_rollback():
    async with datastore_test() as ds:
        with pytest.raises(IntegrityError):
            assert await ds.insert("tasks.smarttest", {"smarttest_disks": [1]})

        assert await ds.query("tasks.smarttest") == []


@pytest.mark.asyncio
async def test__mtm_loader():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO storage_disk VALUES (10)")
        ds.execute("INSERT INTO storage_disk VALUES (20)")
        ds.execute("INSERT INTO storage_disk VALUES (30)")
        ds.execute("INSERT INTO tasks_smarttest VALUES (100)")
        ds.execute("INSERT INTO tasks_smarttest_smarttest_disks VALUES (NULL, 100, 10)")
        ds.execute("INSERT INTO tasks_smarttest_smarttest_disks VALUES (NULL, 100, 30)")

        assert await ds.query("tasks.smarttest", [], {"prefix": "smarttest_"}) == [
            {
                "id": 100,
                "disks": [{"id": 10}, {"id": 30}],
            }
        ]


@pytest.mark.asyncio
async def test__mtm_insert():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO storage_disk VALUES (10)")
        ds.execute("INSERT INTO storage_disk VALUES (20)")
        ds.execute("INSERT INTO storage_disk VALUES (30)")

        await ds.insert("tasks.smarttest", {"disks": [10, 30]}, {"prefix": "smarttest_"})

        assert await ds.query("tasks.smarttest", [], {"prefix": "smarttest_"}) == [
            {
                "id": 1,
                "disks": [{"id": 10}, {"id": 30}],
            }
        ]


@pytest.mark.asyncio
async def test__mtm_update():
    async with datastore_test() as ds:
        ds.execute("INSERT INTO storage_disk VALUES (10)")
        ds.execute("INSERT INTO storage_disk VALUES (20)")
        ds.execute("INSERT INTO storage_disk VALUES (30)")
        ds.execute("INSERT INTO tasks_smarttest VALUES (100)")
        ds.execute("INSERT INTO tasks_smarttest_smarttest_disks VALUES (NULL, 100, 10)")
        ds.execute("INSERT INTO tasks_smarttest_smarttest_disks VALUES (NULL, 100, 30)")

        await ds.update("tasks.smarttest", 100, {"disks": [20, 30]}, {"prefix": "smarttest_"})

        assert await ds.query("tasks.smarttest", [], {"prefix": "smarttest_"}) == [
            {
                "id": 100,
                "disks": [{"id": 20}, {"id": 30}],
            }
        ]


class DefaultModel(Model):
    __tablename__ = "test_default"

    id = sa.Column(sa.Integer(), primary_key=True)
    string = sa.Column(sa.String(100), default="DEFAULT")


@pytest.mark.asyncio
async def test__insert_default():
    async with datastore_test() as ds:
        await ds.insert("test.default", {})

        assert (await ds.query("test.default", [], {"get": True}))["string"] == "DEFAULT"


@pytest.mark.asyncio
async def test__insert_default_has_value():
    async with datastore_test() as ds:
        await ds.insert("test.default", {"string": "VALUE"})

        assert (await ds.query("test.default", [], {"get": True}))["string"] == "VALUE"


class CallableDefaultModel(Model):
    __tablename__ = "test_callable_default"

    id = sa.Column(sa.Integer(), primary_key=True)
    string = sa.Column(sa.String(100), default=lambda: "DEFAULT")


@pytest.mark.asyncio
async def test__insert_callable_default():
    async with datastore_test() as ds:
        await ds.insert("test.callable_default", {})

        assert (await ds.query("test.callable_default", [], {"get": True}))["string"] == "DEFAULT"


class StringPrimaryKeyModel(Model):
    __tablename__ = 'test_stringprimarykey'

    string_id = sa.Column(sa.String(100), primary_key=True)
    value = sa.Column(sa.Integer(), nullable=True)


class BigIntegerPrimaryKeyModel(Model):
    __tablename__ = 'test_bigintegerprimarykey'

    integer_id = sa.Column(sa.BigInteger(), primary_key=True)
    value = sa.Column(sa.Integer(), nullable=True)


@pytest.mark.asyncio
async def test__insert_string_pk_record():
    async with datastore_test() as ds:
        payload = {"string_id": "unique_key", "value": 1}
        pk = await ds.insert("test.stringprimarykey", payload)

        assert pk == payload["string_id"]
        assert len(await ds.query("test.stringprimarykey", [["string_id", "=", pk]])) == 1


@pytest.mark.asyncio
async def test__insert_default_integer_pk_value():
    async with datastore_test() as ds:
        pk = await ds.insert("test.default", {"string": "VALUE"})

        assert len(await ds.query("test.default", [["id", "=", pk]])) == 1


@pytest.mark.asyncio
async def test__insert_integer_pk_record():
    async with datastore_test() as ds:
        payload = {"integer_id": 120093877, "value": 1}
        pk = await ds.insert("test.bigintegerprimarykey", payload)

        assert pk == payload["integer_id"]
        assert len(await ds.query("test.bigintegerprimarykey", [["integer_id", "=", pk]])) == 1


class SMBModel(Model):
    __tablename__ = 'test_smb'

    id = sa.Column(sa.Integer(), primary_key=True)
    cifs_srv_netbiosname = sa.Column(sa.String(120))
    cifs_SID = sa.Column(sa.String(120), nullable=True)


@pytest.mark.asyncio
async def test__already_has_prefix():
    async with datastore_test() as ds:
        await ds.insert("test.smb", {"cifs_srv_netbiosname": "", "cifs_SID": None})

        await ds.update("test.smb", 1, {"netbiosname": "localhost", "cifs_SID": "ABCDEF"}, {"prefix": "cifs_srv_"})

        assert (await ds.query("test.smb", [], {"prefix": "cifs_srv_", "get": True})) == {
            "id": 1,
            "netbiosname": "localhost",
            "cifs_SID": "ABCDEF",
        }


class TimeModel(Model):
    __tablename__ = 'test_time'

    id = sa.Column(sa.Integer(), primary_key=True)
    time = sa.Column(Time())


@pytest.mark.asyncio
async def test__time():
    async with datastore_test() as ds:
        await ds.insert("test.time", {"time": datetime.time(21, 30)})

        assert (await ds.query("test.time", [], {"get": True}))["time"] == datetime.time(21, 30)
        assert (await ds.sql("SELECT * FROM test_time"))[0]["time"] == "21:30:00"


class NullModel(Model):
    __tablename__ = 'test_null'

    id = sa.Column(sa.Integer(), primary_key=True)
    value = sa.Column(sa.Integer(), nullable=True)


@pytest.mark.parametrize("order_by,result", [
    (["value"], [2, 3, 1]),
    (["-value"], [1, 3, 2]),
    (["nulls_last:value"], [3, 1, 2]),
    (["nulls_first:-value"], [2, 1, 3]),
])
@pytest.mark.asyncio
async def test__null_order_by(order_by, result):
    async with datastore_test() as ds:
        await ds.insert("test.null", {"value": 3})
        await ds.insert("test.null", {"value": None})
        await ds.insert("test.null", {"value": 1})

        assert [row["id"] for row in await ds.query("test.null", [], {"order_by": order_by})] == result


class AuditModel(Model):
    __tablename__ = 'audit_middleware_0_1'

    ROW_ID = sa.Column(sa.Integer(), primary_key=True)
    event_data = sa.Column(sa.String())
    username = sa.Column(sa.String())


@pytest.mark.parametrize("filters,expected_ids", [
    # Existing tests - full array/object matching
    ([['$.event_data.params', '=', [38]]], [1]),
    ([['$.event_data.nested', '=', {'key': 'value1'}]], [1]),
    ([['$.event_data.params', '=', [40, 41]]], [3]),
    ([['username', '=', 'admin']], [1, 2]),
    ([['username', '=', 'admin'], ['$.event_data.params', '=', [38]]], [1]),
    ([['$.event_data.method', '=', 'user.delete']], [1, 3]),

    # NEW - Array index access tests
    # Access first element of params array
    ([['$.event_data.params[0]', '=', 38]], [1]),
    ([['$.event_data.params[0]', '=', 39]], [2]),
    ([['$.event_data.params[0]', '=', 40]], [3]),
    # Access second element of params array (only row 3 has two elements)
    ([['$.event_data.params[1]', '=', 41]], [3]),
    # Combine array index with other filters
    ([['$.event_data.method', '=', 'user.delete'], ['$.event_data.params[0]', '=', 38]], [1]),
    ([['username', '=', 'admin'], ['$.event_data.params[0]', '=', 38]], [1]),
    # Access nested object property
    ([['$.event_data.nested.key', '=', 'value1']], [1]),
    ([['$.event_data.nested.key', '=', 'value2']], [2]),
])
@pytest.mark.asyncio
async def test__json_path_filters(filters, expected_ids):
    async with datastore_test() as ds:
        ds.execute(
            "INSERT INTO audit_middleware_0_1 VALUES (1, "
            "'{\"method\": \"user.delete\", \"params\": [38], \"nested\": {\"key\": \"value1\"}}', 'admin')"
        )
        ds.execute(
            "INSERT INTO audit_middleware_0_1 VALUES (2, "
            "'{\"method\": \"user.create\", \"params\": [39], \"nested\": {\"key\": \"value2\"}}', 'admin')"
        )
        ds.execute(
            "INSERT INTO audit_middleware_0_1 VALUES (3, "
            "'{\"method\": \"user.delete\", \"params\": [40, 41], \"nested\": {\"key\": \"value3\"}}', 'root')"
        )

        result = await ds.query("audit.middleware_0_1", filters)
        assert [row["ROW_ID"] for row in result] == expected_ids


# =============================================================================
# NEW - Tests for top-level array column access (e.g., $.roles[0])
# This tests the case where the JSON column itself contains an array
# =============================================================================

class RolesModel(Model):
    """Model with a JSON column that stores an array directly (not nested in object)"""
    __tablename__ = 'test_roles'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String())
    roles = sa.Column(sa.String())  # JSON array stored as string


@pytest.mark.parametrize("filters,expected_ids", [
    # Top-level array index access - currently BROKEN, needs json_path_parse() fix
    ([['$.roles[0]', '=', 'FULL_ADMIN']], [1]),
    ([['$.roles[0]', '=', 'READONLY_ADMIN']], [2]),
    ([['$.roles[1]', '=', 'SHARING_ADMIN']], [1]),  # Second role
    # Combine with regular column filter
    ([['name', '=', 'Local Administrator'], ['$.roles[0]', '=', 'FULL_ADMIN']], [1]),
    # Single column JSONPath (no array index) - currently BROKEN
    ([['$.roles', '=', '["FULL_ADMIN", "SHARING_ADMIN"]']], [1]),
])
@pytest.mark.asyncio
async def test__json_path_top_level_array(filters, expected_ids):
    """Test filtering on JSON columns that contain arrays at the top level"""
    async with datastore_test() as ds:
        ds.execute(
            "INSERT INTO test_roles VALUES (1, 'Local Administrator', '[\"FULL_ADMIN\", \"SHARING_ADMIN\"]')"
        )
        ds.execute(
            "INSERT INTO test_roles VALUES (2, 'Read-Only Administrator', '[\"READONLY_ADMIN\"]')"
        )
        ds.execute(
            "INSERT INTO test_roles VALUES (3, 'Sharing Administrator', '[\"SHARING_ADMIN\"]')"
        )

        result = await ds.query("test.roles", filters)
        assert [row["id"] for row in result] == expected_ids


# =============================================================================
# NEW - Tests for complex nested JSON with array access (audit-like use case)
# =============================================================================

class AuditComplexModel(Model):
    """Model simulating real audit event_data structure with params array containing objects"""
    __tablename__ = 'audit_complex'

    id = sa.Column(sa.Integer(), primary_key=True)
    event_data = sa.Column(sa.String())  # JSON with nested structure


@pytest.mark.parametrize("filters,expected_ids", [
    # Access property of first object in params array (main audit use case)
    # Note: Row 1 and Row 3 both have username=barney in params[0]
    ([['$.event_data.params[0].username', '=', 'barney']], [1, 3]),
    ([['$.event_data.params[0].username', '=', 'fred']], [2]),
    # Access nested property in array element
    ([['$.event_data.params[0].settings.theme', '=', 'dark']], [1]),
    ([['$.event_data.params[0].settings.theme', '=', 'light']], [2]),
    # Combine method filter with params array access (this filters to just row 1)
    ([['$.event_data.method', '=', 'user.create'], ['$.event_data.params[0].username', '=', 'barney']], [1]),
    # Access second positional argument
    ([['$.event_data.params[1].notify', '=', True]], [1]),
    ([['$.event_data.params[1].notify', '=', False]], [2]),
])
@pytest.mark.asyncio
async def test__json_path_nested_array_object_access(filters, expected_ids):
    """Test filtering on array elements that contain objects (audit params use case)"""
    async with datastore_test() as ds:
        # Row 1: user.create for barney with dark theme, notify=true
        ds.execute(
            "INSERT INTO audit_complex VALUES (1, '"
            '{"method": "user.create", "params": ['
            '{"username": "barney", "settings": {"theme": "dark"}}, {"notify": true}]}'
            "')"
        )
        # Row 2: user.create for fred with light theme, notify=false
        ds.execute(
            "INSERT INTO audit_complex VALUES (2, '"
            '{"method": "user.create", "params": ['
            '{"username": "fred", "settings": {"theme": "light"}}, {"notify": false}]}'
            "')"
        )
        # Row 3: user.delete for barney (different method)
        ds.execute(
            "INSERT INTO audit_complex VALUES (3, '"
            '{"method": "user.delete", "params": [{"username": "barney"}]}'
            "')"
        )

        result = await ds.query("audit.complex", filters)
        assert [row["id"] for row in result] == expected_ids


class LinkedToModel(Model):
    __tablename__ = 'test_linkedto'

    id = sa.Column(sa.Integer(), primary_key=True)
    linkedto_value = sa.Column(sa.Integer())


class LinkedFromModel(Model):
    __tablename__ = 'test_linkedfrom'

    id = sa.Column(sa.Integer(), primary_key=True)
    linkedfrom_linkedto_id = sa.Column(sa.ForeignKey('test_linkedto.id'), index=True)
    linkedfrom_value = sa.Column(sa.Integer())


@pytest.mark.parametrize("extend_fk_attrs, filter_, options, expected_result", [
    pytest.param(
        {},
        [],
        {'prefix': 'linkedfrom_'},
        [{'id': 1,
          'linkedto': {'id': 2, 'linkedto_value': 42},
          'value': 142},
         {'id': 2,
          'linkedto': {'id': 3, 'linkedto_value': 43},
          'value': 143}],
        id='extend_pk NOT supplied, no filter, no extend'),

    pytest.param(
        {},
        [],
        {'prefix': 'linkedfrom_', 'count': True},
        2,
        id='extend_pk NOT supplied, no filter, no extend, count(2)'),

    pytest.param(
        {},
        [['id', '=', 2]],
        {'prefix': 'linkedfrom_', 'count': True},
        1,
        id='extend_pk NOT supplied, filter, no extend, count(1)'),

    pytest.param(
        {},
        [['id', '=', 525600]],
        {'prefix': 'linkedfrom_', 'count': True},
        0,
        id='extend_pk NOT supplied, filter, no extend, count(0)'),

    pytest.param(
        {},
        [['linkedto_id', '=', 3]],
        {'prefix': 'linkedfrom_', 'count': True},
        1,
        id='extend_pk NOT supplied, filter(underscore), no extend, count(1)'),

    pytest.param(
        {},
        [['linkedto_id', '=', 525600]],
        {'prefix': 'linkedfrom_', 'count': True},
        0,
        id='extend_pk NOT supplied, filter(underscore), no extend, count(0)'),

    pytest.param(
        {},
        [],
        {'prefix': 'linkedfrom_', 'extend': 'fake.extend.triple_value'},
        [{'id': 1,
          'linkedto': {'id': 2, 'linkedto_value': 42},
          'value': 426},
         {'id': 2,
          'linkedto': {'id': 3, 'linkedto_value': 43},
          'value': 429}],
        id='extend_pk NOT supplied, no filter, extend(from)'),

    pytest.param(
        {},
        [['linkedto_id', '=', 3]],
        {'prefix': 'linkedfrom_', 'extend': 'fake.extend.triple_value'},
        [{'id': 2,
          'linkedto': {'id': 3, 'linkedto_value': 43},
          'value': 429}],
        id='extend_pk NOT supplied, filter, extend(from)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': None, 'extend_context': None},
        [],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto']},
        [{'id': 1,
          'linkedto': {'id': 2, 'value': 42},
          'value': 142},
         {'id': 2,
          'linkedto': {'id': 3, 'value': 43},
          'value': 143}],
        id='extend_pk supplied, no filter, no extend'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': None, 'extend_context': None},
        [['linkedto_id', '=', 2]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto']},
        [{'id': 1,
          'linkedto': {'id': 2, 'value': 42},
          'value': 142}],
        id='extend_pk supplied, filter (underscore), no extend'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': None, 'extend_context': None},
        [['linkedto__id', '=', 2]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto']},
        [{'id': 1,
          'linkedto': {'id': 2, 'value': 42},
          'value': 142}],
        id='extend_pk supplied, filter (double underscore), no extend'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': None, 'extend_context': None},
        [['linkedto.id', '=', 2]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto']},
        [{'id': 1,
          'linkedto': {'id': 2, 'value': 42},
          'value': 142}],
        id='extend_pk supplied, filter (period), no extend'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto.id', '=', 2]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto']},
        [{'id': 1,
          'linkedto': {'id': 2, 'value': 84},
          'value': 142}],
        id='extend_pk supplied, filter (period), extend'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto.id', '=', 2]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'extend': 'fake.extend.triple_value'},
        [{'id': 1,
          'linkedto': {'id': 2, 'value': 84},
          'value': 426}],
        id='extend_pk supplied, filter (period), extend (twice)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        2,
        id='extend_pk supplied, no filter, extend, count(2)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['id', '=', 2]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        1,
        id='extend_pk supplied, filter, extend, count(1)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['id', '=', 525600]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        0,
        id='extend_pk supplied, filter, extend, count(0)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto_id', '=', 3]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        1,
        id='extend_pk supplied, filter(underscore), extend, count(1)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto_id', '=', 525600]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        0,
        id='extend_pk supplied, filter(underscore), extend, count(0)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto__id', '=', 3]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        1,
        id='extend_pk supplied, filter(double underscore), extend, count(1)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto__id', '=', 525600]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        0,
        id='extend_pk supplied, filter(double underscore), extend, count(0)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto.id', '=', 3]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        1,
        id='extend_pk supplied, filter(period), extend, count(1)'),

    pytest.param(
        {'prefix': 'linkedto_', 'extend': 'fake.extend.double_value', 'extend_context': None},
        [['linkedto.id', '=', 525600]],
        {'prefix': 'linkedfrom_', 'extend_fk': ['linkedto'], 'count': True},
        0,
        id='extend_pk supplied, filter(period), extend, count(0)'),

])
@pytest.mark.asyncio
async def test__extend_fk(extend_fk_attrs, filter_, options, expected_result):
    def multiply(times):
        def by(data):
            if curval := data.get('value', None):
                if isinstance(curval, int):
                    data['value'] = curval * times
            return data
        return by

    mocked_calls = {
        'datastore.get_service_config_attrs': lambda ftn: extend_fk_attrs,
        'fake.extend.double_value': multiply(2),
        'fake.extend.triple_value': multiply(3),
    }
    async with datastore_test(mocked_calls) as ds:
        await ds.insert("test.linkedto", {"linkedto_value": 1})
        await ds.insert("test.linkedto", {"linkedto_value": 42})
        await ds.insert("test.linkedto", {"linkedto_value": 43})
        await ds.insert("test.linkedfrom", {"linkedfrom_value": 142, "linkedfrom_linkedto_id": 2})
        await ds.insert("test.linkedfrom", {"linkedfrom_value": 143, "linkedfrom_linkedto_id": 3})

        query_result = await ds.query("test.linkedfrom", filter_, options)
        assert query_result == expected_result
