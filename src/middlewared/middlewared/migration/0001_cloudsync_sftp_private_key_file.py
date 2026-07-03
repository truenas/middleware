# -*- coding=utf-8 -*-
import os


def migrate(middleware):
    for credential in middleware.call_sync("cloudsync.credentials.query", [["provider.type", "=", "SFTP"]]):
        if "key_file" in credential["provider"] and os.path.exists(credential["provider"]["key_file"]):
            middleware.logger.info("Migrating SFTP cloud credential %d to keychain", credential["id"])

            try:
                with open(credential["provider"]["key_file"]) as f:
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

                del credential["provider"]["key_file"]
                credential["provider"]["private_key"] = keypair_id

                middleware.call_sync("datastore.update", "system.cloudcredentials", credential["id"], {
                    "provider": credential["provider"],
                })
            except Exception as e:
                middleware.logger.warning("Error migrating SFTP cloud credential %d to keychain: %r",
                                          credential['id'], e)
