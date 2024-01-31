import enum


class ACLType(enum.Enum):
    NFS4 = (['tag', 'id', 'perms', 'flags', 'type'], ["owner@", "group@", "everyone@"])
    POSIX1E = (['default', 'tag', 'id', 'perms'], ["USER_OBJ", "GROUP_OBJ", "OTHER", "MASK"])
    DISABLED = ([], [])

    def _validate_id(self, id_, special):
        if id_ is None or id_ < 0:
            return True if special else False

        return False if special else True

    def _validate_entry(self, idx, entry, errors):
        is_special = entry['tag'] in self.value[1]

        if is_special and entry.get('type') == 'DENY':
            errors.append((
                idx,
                f'{entry["tag"]}: DENY entries for this principal are not permitted.',
                'tag'
            ))

        if not self._validate_id(entry['id'], is_special):
            errors.append(
                (idx, 'ACL entry has invalid id for tag type.', 'id')
            )

    def validate(self, theacl):
        errors = []
        ace_keys = self.value[0]

        if self != ACLType.NFS4 and theacl.get('nfs41flags'):
            errors.append(f"NFS41 ACL flags are not valid for ACLType [{self.name}]")

        for idx, entry in enumerate(theacl['dacl']):
            extra = set(entry.keys()) - set(ace_keys)
            missing = set(ace_keys) - set(entry.keys())
            if extra:
                errors.append(
                    (idx, f"ACL entry contains invalid extra key(s): {extra}", None)
                )
            if missing:
                errors.append(
                    (idx, f"ACL entry is missing required keys(s): {missing}", None)
                )

            if extra or missing:
                continue

            self._validate_entry(idx, entry, errors)

        return {"is_valid": len(errors) == 0, "errors": errors}

    def _is_inherited(self, ace):
        if ace['flags'].get("BASIC"):
            return False

        return ace['flags'].get('INHERITED', False)

    def canonicalize(self, theacl):
        """
        Order NFS4 ACEs according to MS guidelines:
        1) Deny ACEs that apply to the object itself (NOINHERIT)
        2) Allow ACEs that apply to the object itself (NOINHERIT)
        3) Deny ACEs that apply to a subobject of the object (INHERIT)
        4) Allow ACEs that apply to a subobject of the object (INHERIT)

        See http://docs.microsoft.com/en-us/windows/desktop/secauthz/order-of-aces-in-a-dacl
        Logic is simplified here because we do not determine depth from which ACLs are inherited.
        """
        if self == ACLType.POSIX1E:
            return

        out = []
        acl_groups = {
            "deny_noinherit": [],
            "deny_inherit": [],
            "allow_noinherit": [],
            "allow_inherit": [],
        }

        for ace in theacl:
            key = f'{ace.get("type", "ALLOW").lower()}_{"inherit" if self._is_inherited(ace) else "noinherit"}'
            acl_groups[key].append(ace)

        for g in acl_groups.values():
            out.extend(g)

        return out

    def xattr_names():
        return set([
            "system.posix_acl_access",
            "system.posix_acl_default",
            "system.nfs4_acl_xdr"
        ])

    def __calculate_inherited_posix1e(self, theacl, isdir):
        inherited = []
        for entry in theacl['acl']:
            if entry['default'] is False:
                continue

            # add access entry
            inherited.append(entry.copy() | {'default': False})

            if isdir:
                # add default entry
                inherited.append(entry)

        return inherited

    def __calculate_inherited_nfs4(self, theacl, isdir):
        inherited = []
        for entry in theacl['acl']:
            if not (flags := entry.get('flags', {}).copy()):
                continue

            if (basic := flags.get('BASIC')) == 'NOINHERIT':
                continue
            elif basic == 'INHERIT':
                flags['INHERITED'] = True
                inherited.append(entry)
                continue
            elif not flags.get('FILE_INHERIT', False) and not flags.get('DIRECTORY_INHERIT', False):
                # Entry has no inherit flags
                continue
            elif not isdir and not flags.get('FILE_INHERIT'):
                # File and this entry doesn't inherit on files
                continue

            if isdir:
                if not flags.get('DIRECTORY_INHERIT', False):
                    if flags['NO_PROPAGATE_INHERIT']:
                        # doesn't apply to this dir and shouldn't apply to contents.
                        continue

                    # This is a directoy ACL and we have entry that only applies to files.
                    flags['INHERIT_ONLY'] = True
                elif flags.get('INHERIT_ONLY', False):
                    flags['INHERIT_ONLY'] = False
                elif flags.get('NO_PROPAGATE_INHERIT'):
                    flags['DIRECTORY_INHERIT'] = False
                    flags['FILE_INHERIT'] = False
                    flags['NO_PROPAGATE_INHERIT'] = False
            else:
                flags['DIRECTORY_INHERIT'] = False
                flags['FILE_INHERIT'] = False
                flags['NO_PROPAGATE_INHERIT'] = False
                flags['INHERIT_ONLY'] = False

            inherited.append({
                'tag': entry['tag'],
                'id': entry['id'],
                'type': entry['type'],
                'perms': entry['perms'],
                'flags': flags | {'INHERITED': True}
            })

        return inherited

    def calculate_inherited(self, theacl, isdir=True):
        if self.name != theacl['acltype']:
            raise ValueError('ACLType does not match')

        if self == ACLType.POSIX1E:
            return self.__calculate_inherited_posix1e(theacl, isdir)

        elif self == ACLType.NFS4:
            return self.__calculate_inherited_nfs4(theacl, isdir)

        raise ValueError('ACLType does not support inheritance')
