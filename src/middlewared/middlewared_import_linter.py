import sys

from importlinter import Contract, ContractCheck, fields, output


class APISchemaContract(Contract):
    def check(self, graph, verbose):
        errors = []
        whitelist = {
            "annotated_types",
            "pydantic",
            "typing_extensions",
            "middlewared.api.base",
            "middlewared.utils.lang",
            # FIXME: These should not be imported
            "cryptography",
            "lexicon",
            "middlewared.plugins.account_.constants",
            "middlewared.plugins.idmap_.idmap_constants",
            "middlewared.plugins.smb_.constants",
            "middlewared.plugins.zfs_.validation_utils",
            "middlewared.utils",
            "middlewared.utils.auth",
            "middlewared.utils.cron",
            "middlewared.utils.directoryservices.credential",
            "middlewared.utils.directoryservices.krb5_conf",
            "middlewared.utils.filesystem.acl",
            "middlewared.utils.filesystem.stat_x",
            "middlewared.utils.security",
            "middlewared.utils.smb",
            "zettarepl",
        }
        for api_module in sorted(graph.find_children("middlewared.api")):
            if not api_module.startswith("middlewared.api.v"):
                continue

            for inspected_module in sorted({api_module} | graph.find_descendants(api_module)):
                for imported_module in sorted(graph.find_modules_directly_imported_by(inspected_module)):
                    # API modules can import stdlib modules
                    if imported_module in sys.stdlib_module_names:
                        continue

                    if imported_module in whitelist:
                        continue

                    if imported_module.startswith(f"{api_module}."):
                        continue

                    import_details = graph.get_import_details(
                        importer=inspected_module,
                        imported=imported_module,
                    )

                    errors.append((inspected_module, imported_module, import_details))

        return ContractCheck(
            kept=not errors,
            metadata={
                "errors": errors,
            }
        )

    def render_broken_contract(self, check):
        for inspected_module, imported_module, import_details in check.metadata["errors"]:
            output.print_error(
                f"API module {inspected_module} cannot import {imported_module}:",
                bold=True,
            )
            output.new_line()
            for details in import_details:
                filename = inspected_module.replace(".", "/") + ".py"
                line_number = details["line_number"]
                line_contents = details["line_contents"]
                output.indent_cursor()
                output.print_error(f"{filename}:{line_number}: {line_contents}")
                output.new_line()
