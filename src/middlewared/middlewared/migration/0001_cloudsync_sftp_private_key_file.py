# -*- coding=utf-8 -*-
import os


def migrate(middleware):
    # Read raw rows: `key_file` is a legacy attribute that the typed credential models no longer describe.
    for credential in middleware.call_sync("datastore.query", "system.cloudcredentials", [["provider", "=", "SFTP"]]):
        attributes = credential["attributes"]
        if "key_file" in attributes and os.path.exists(attributes["key_file"]):
            middleware.logger.info("Migrating SFTP cloud credential %d to keychain", credential["id"])

            try:
                with open(attributes["key_file"]) as f:
                    private_key = f.read()

                for keypair in middleware.call_sync2(
                    middleware.services.keychaincredential.query, [["type", "=", "SSH_KEY_PAIR"]]
                ):
                    if keypair.attributes.get_secret_value().private_key.strip() == private_key.strip():
                        keypair_id = keypair.id
                        break
                else:
                    keypair_id = middleware.call_sync2(middleware.services.keychaincredential.create, {
                        "name": credential["name"],
                        "type": "SSH_KEY_PAIR",
                        "attributes": {
                            "private_key": private_key,
                        }
                    }).id

                del attributes["key_file"]
                attributes["private_key"] = keypair_id

                middleware.call_sync("datastore.update", "system.cloudcredentials", credential["id"], {
                    "attributes": attributes,
                })
            except Exception as e:
                middleware.logger.warning("Error migrating SFTP cloud credential %d to keychain: %r",
                                          credential['id'], e)
