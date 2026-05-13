# -*- coding=utf-8 -*-
import dataclasses
import functools
import json
import logging
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import typing

from bs4 import BeautifulSoup
from json_schema_for_humans.generate import generate_from_filename
from json_schema_for_humans.generation_configuration import GenerationConfiguration

from middlewared.fake_env import setup_fake_middleware_env
setup_fake_middleware_env()

from middlewared.api.base.server.doc import APIDump, APIDumpMethod, APIDumpEvent

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SchemaChange:
    name: str
    call_params_diff: list[str]
    return_value_diff: list[str]


@dataclasses.dataclass
class Changelog:
    previous_version: str
    methods_added: list[str] = dataclasses.field(default_factory=list)
    methods_removed: list[str] = dataclasses.field(default_factory=list)
    methods_changed: list[SchemaChange] = dataclasses.field(default_factory=list)
    events_added: list[str] = dataclasses.field(default_factory=list)
    events_removed: list[str] = dataclasses.field(default_factory=list)
    events_changed: list[SchemaChange] = dataclasses.field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.methods_added or self.methods_removed or self.methods_changed or
            self.events_added or self.events_removed or self.events_changed
        )


def _type_summary(schema: dict) -> str:
    """Render a brief human-readable type summary for a JSON-Schema fragment."""
    if not isinstance(schema, dict):
        return "unknown"

    for combiner in ("anyOf", "oneOf"):
        if combiner in schema:
            return " | ".join(_type_summary(s) for s in schema[combiner])

    t = schema.get("type")
    if isinstance(t, list):
        return " | ".join(t)
    if t:
        return t
    if "enum" in schema:
        return "enum"
    if "const" in schema:
        return "const"
    return "unknown"


def _diff_object_properties(old: dict, new: dict, label: str) -> list[str]:
    """Diff top-level properties of two object schemas. `label` is e.g. `parameter` or `field`."""
    old_props = old.get("properties", {}) if isinstance(old, dict) else {}
    new_props = new.get("properties", {}) if isinstance(new, dict) else {}
    lines = []
    for name in sorted(set(new_props) - set(old_props)):
        lines.append(f"added {label} `{name}`")
    for name in sorted(set(old_props) - set(new_props)):
        lines.append(f"removed {label} `{name}`")
    for name in sorted(set(old_props) & set(new_props)):
        old_type = _type_summary(old_props[name])
        new_type = _type_summary(new_props[name])
        if old_type != new_type:
            lines.append(f"{label} `{name}` type changed ({old_type} → {new_type})")
    return lines


def _diff_call_parameters(old: dict, new: dict) -> list[str]:
    """Brief top-level diff of the `Call parameters` array schema."""
    old_items = old.get("prefixItems", []) if isinstance(old, dict) else []
    new_items = new.get("prefixItems", []) if isinstance(new, dict) else []
    old_by_name = {item.get("title"): item for item in old_items if isinstance(item, dict)}
    new_by_name = {item.get("title"): item for item in new_items if isinstance(item, dict)}

    lines = []
    for name in sorted(k for k in new_by_name if k not in old_by_name and k is not None):
        lines.append(f"added parameter `{name}`")
    for name in sorted(k for k in old_by_name if k not in new_by_name and k is not None):
        lines.append(f"removed parameter `{name}`")
    for name in sorted(k for k in new_by_name if k in old_by_name and k is not None):
        old_type = _type_summary(old_by_name[name])
        new_type = _type_summary(new_by_name[name])
        if old_type != new_type:
            lines.append(f"parameter `{name}` type changed ({old_type} → {new_type})")
    return lines


def _diff_return_value(old: dict, new: dict) -> list[str]:
    """Brief top-level diff of the `Return value` schema."""
    old_type = _type_summary(old) if isinstance(old, dict) else "unknown"
    new_type = _type_summary(new) if isinstance(new, dict) else "unknown"
    if old_type != new_type:
        return [f"return value type changed ({old_type} → {new_type})"]
    if isinstance(old, dict) and isinstance(new, dict) and old.get("type") == "object":
        return _diff_object_properties(old, new, "field")
    return []


def compute_schema_diff(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """Compare two method/event schemas. Returns (call_params_diff, return_value_diff)."""
    if old == new:
        return [], []

    old_props = old.get("properties", {}) if isinstance(old, dict) else {}
    new_props = new.get("properties", {}) if isinstance(new, dict) else {}

    call_diff = _diff_call_parameters(
        old_props.get("Call parameters", {}),
        new_props.get("Call parameters", {}),
    )
    return_diff = _diff_return_value(
        old_props.get("Return value", {}),
        new_props.get("Return value", {}),
    )
    return call_diff, return_diff


def _diff_items(previous: list, current: list) -> tuple[list[str], list[str], list[SchemaChange]]:
    """Compute added/removed/changed for a list of APIDumpMethod or APIDumpEvent."""
    prev_by_name = {item.name: item for item in previous}
    cur_by_name = {item.name: item for item in current}

    added = sorted(set(cur_by_name) - set(prev_by_name))
    removed = sorted(set(prev_by_name) - set(cur_by_name))
    changed = []
    for name in sorted(set(cur_by_name) & set(prev_by_name)):
        old_schemas = prev_by_name[name].schemas
        new_schemas = cur_by_name[name].schemas
        if old_schemas == new_schemas:
            continue
        call_diff, return_diff = compute_schema_diff(old_schemas, new_schemas)
        if not call_diff and not return_diff:
            # The schemas differ but our shallow diff couldn't surface anything meaningful
            # (e.g. nested-only change). Record the method as changed with a generic note.
            call_diff = []
            return_diff = ["schema changed (see method page for details)"]
        changed.append(SchemaChange(name=name, call_params_diff=call_diff, return_value_diff=return_diff))

    return added, removed, changed


def compute_changelog(previous: APIDump, current: APIDump) -> Changelog:
    methods_added, methods_removed, methods_changed = _diff_items(previous.methods, current.methods)
    events_added, events_removed, events_changed = _diff_items(previous.events, current.events)
    return Changelog(
        previous_version=previous.version,
        methods_added=methods_added,
        methods_removed=methods_removed,
        methods_changed=methods_changed,
        events_added=events_added,
        events_removed=events_removed,
        events_changed=events_changed,
    )


class DocumentationGenerator:
    def __init__(self, api: APIDump, output_dir: str, changelog: Changelog | None = None):
        self.api = api
        self.output_dir = output_dir
        self.changelog = changelog

    def generate(self):
        shutil.copytree("docs", self.output_dir, dirs_exist_ok=True)

        with open(f"{self.output_dir}/conf.py") as f:
            conf = f.read()

        conf = conf.replace("$VERSION", self.api.version_title)

        with open(f"{self.output_dir}/conf.py", "w") as f:
            f.write(conf)

        with open(f"{self.output_dir}/index.rst") as f:
            index = f.read()

        if self.changelog is not None and not self.changelog.is_empty():
            index = index.replace("$CHANGELOG_ENTRY\n", "   changelog.rst\n")
        else:
            index = index.replace("$CHANGELOG_ENTRY\n", "")

        with open(f"{self.output_dir}/index.rst", "w") as f:
            f.write(index)

        self._write_api_methods()
        self._write_api_events()
        if self.changelog is not None and not self.changelog.is_empty():
            self._write_changelog()

    def _write_changelog(self):
        changelog = self.changelog
        assert changelog is not None
        title = "Changelog"
        result = f"{title}\n{'=' * len(title)}\n\n"
        result += (
            f"Summary of API changes since version {changelog.previous_version}.\n\n"
        )

        result += self._render_changelog_section(
            "Methods Added",
            "api_methods",
            changelog.methods_added,
        )
        result += self._render_changelog_section(
            "Methods Removed",
            None,
            changelog.methods_removed,
        )
        result += self._render_schema_changes_section(
            "Methods with Schema Changes",
            "api_methods",
            changelog.methods_changed,
        )
        result += self._render_changelog_section(
            "Events Added",
            "api_events",
            changelog.events_added,
        )
        result += self._render_changelog_section(
            "Events Removed",
            None,
            changelog.events_removed,
        )
        result += self._render_schema_changes_section(
            "Events with Schema Changes",
            "api_events",
            changelog.events_changed,
        )

        with open(f"{self.output_dir}/changelog.rst", "w") as f:
            f.write(result)

    def _render_changelog_section(self, title: str, doc_prefix: str | None, names: list[str]) -> str:
        if not names:
            return ""
        out = f"{title}\n{'-' * len(title)}\n\n"
        for plugin, plugin_names in self._group_by_plugin(names):
            out += f"**{plugin}**\n\n"
            for name in plugin_names:
                if doc_prefix:
                    out += f"- :doc:`{name} <{doc_prefix}_{name}>`\n"
                else:
                    out += f"- ``{name}``\n"
            out += "\n"
        return out

    def _render_schema_changes_section(self, title: str, doc_prefix: str,
                                       changes: list[SchemaChange]) -> str:
        if not changes:
            return ""
        out = f"{title}\n{'-' * len(title)}\n\n"
        by_plugin: dict[str, list[SchemaChange]] = {}
        for change in changes:
            plugin = change.name.rsplit(".", 1)[0]
            by_plugin.setdefault(plugin, []).append(change)
        for plugin in sorted(by_plugin):
            out += f"**{plugin}**\n\n"
            for change in sorted(by_plugin[plugin], key=lambda c: c.name):
                out += f"- :doc:`{change.name} <{doc_prefix}_{change.name}>`\n"
                for line in change.call_params_diff:
                    out += f"   - Call parameters: {line}\n"
                for line in change.return_value_diff:
                    out += f"   - Return value: {line}\n"
            out += "\n"
        return out

    def _group_by_plugin(self, names: list[str]) -> list[tuple[str, list[str]]]:
        groups: dict[str, list[str]] = {}
        for name in names:
            plugin = name.rsplit(".", 1)[0]
            groups.setdefault(plugin, []).append(name)
        return [(plugin, sorted(groups[plugin])) for plugin in sorted(groups)]

    def _write_api_methods(self):
        return self._write_api_index(
            "api_methods",
            "API Methods",
            self.api.methods,
            self._api_method_html_process,
        )

    def _write_api_events(self):
        return self._write_api_index(
            "api_events",
            "API Events",
            self.api.events,
            self._api_event_html_process,
        )

    def _write_api_index(self, filename: str, title: str, items: list[APIDumpMethod | APIDumpEvent],
                         html_process: typing.Callable[[BeautifulSoup], None]):
        plugins = sorted({method.name.rsplit(".", 1)[0] for method in items})

        index = textwrap.dedent(f"""\
            {title}
            {'-' * len(title)}

            .. toctree::

        """)
        for plugin in plugins:
            plugin_items = [
                item
                for item in items
                if item.name.rsplit(".", 1)[0] == plugin
            ]
            if not plugin_items:
                continue

            index += f"   {filename}_{plugin}\n"

            self._write_plugin(filename, plugin, plugin_items, html_process)

        with open(f"{self.output_dir}/{filename}.rst", "w") as f:
            f.write(index)

    def _write_plugin(self, prefix: str, plugin: str, items: list[APIDumpMethod | APIDumpEvent],
                      html_process: typing.Callable[[BeautifulSoup], None]):
        index = textwrap.dedent(f"""\
            {plugin}
            {'-' * len(plugin)}

            .. toctree::

        """)

        for item in items:
            with open(f"{self.output_dir}/{prefix}_{item.name}.rst", "w") as f:
                f.write(self._generate_item_rst(item, self._generate_item_schemas_html(prefix, item, html_process)))

            index += f"   {prefix}_{item.name}\n"

        with open(f"{self.output_dir}/{prefix}_{plugin}.rst", "w") as f:
            f.write(index)

    def _generate_item_schemas_html(self, prefix: str, item: APIDumpMethod | APIDumpEvent,
                                    process: typing.Callable[[BeautifulSoup], None]) -> str:
        json_path = f"{self.output_dir}/{prefix}_{item.name}.json"
        try:
            with open(json_path, "w") as f:
                json.dump(item.schemas, f)

            html_path = f"{self.output_dir}/{prefix}_{item.name}.html"
            try:
                config = GenerationConfiguration(
                    show_breadcrumbs=False,
                    collapse_long_descriptions=False,
                    collapse_long_examples=False,
                    copy_css=False,
                    copy_js=False,
                    with_footer=False,
                )
                generate_from_filename(json_path, html_path, config=config)

                with open(html_path) as f:
                    html = f.read()
            finally:
                os.unlink(html_path)

            soup = BeautifulSoup(html)

            # Elements like `Each item of this array must be:`
            for h4 in soup.find_all("h4"):
                if h4.text.endswith(":"):
                    h5 = soup.new_tag("h5")
                    h5.string = h4.text
                    h4.replace_with(h5)

            process(soup)

            # Multi-line default values (usually, non-trivial JSON arrays/objects)
            for default_value in soup.find_all("span", class_="default-value"):
                value = default_value.text.split(": ", 1)[1]
                if len(value) > 40 and value.startswith(("[", "{")):
                    try:
                        value_decoded = json.loads(value)
                    except ValueError:
                        continue

                    new_default_value_value = soup.new_tag("div", **{"class": "value"})
                    new_default_value_value.string = json.dumps(value_decoded, indent=2)
                    new_default_value = soup.new_tag("div", **{"class": "json-default-value"})
                    new_default_value.string = "Default:"
                    new_default_value.insert(1, new_default_value_value)
                    default_value.replace_with(new_default_value)

            return soup.find("body").decode_contents()
        finally:
            os.unlink(json_path)

    def _generate_item_rst(self, item: APIDumpMethod | APIDumpEvent, schemas_html: str) -> str:
        result = f"{item.name}\n" + "=" * len(item.name) + "\n\n"

        if item.doc:
            result += f"{item.doc}\n\n"

        if item.removed_in:
            result += f"*DEPRECATED: this method is scheduled to be removed in {item.removed_in}.*\n\n"

        if isinstance(item, APIDumpMethod):
            if item.name == "core.download":
                # Add downloadable jobs list for core.download
                downloadable_jobs = [
                    m for m in self.api.methods
                    if m.output_pipes
                ]
                if downloadable_jobs:
                    result += "**Jobs that can be downloaded:**\n\n"
                    for job in sorted(downloadable_jobs, key=lambda m: m.name):
                        result += f"- :doc:`{job.name} <api_methods_{job.name}>`\n"
                    result += "\n"
            else:
                modal = "MUST" if item.check_pipes else "CAN"
                if item.input_pipes:
                    # Add note about file upload for jobs with input pipes
                    result += f"*This job {modal} be used with file upload.* See :ref:`uploading-files`.\n\n"
                if item.output_pipes:
                    # Add note about core.download for jobs with output pipes
                    result += f"*This job {modal} be used with* :doc:`core.download <api_methods_core.download>`.\n\n"

        result += ".. raw:: html\n\n"
        result += textwrap.indent(
            "<div id=\"json-schema\">" + schemas_html + "</div><br><br>", " " * 4
        ) + "\n\n"

        result += "*Required roles:* " + " | ".join(item.roles) + "\n\n"

        return result

    def _api_method_html_process(self, soup: BeautifulSoup):
        for h5 in soup.find("div", {"id": "Call_parameters"}).find().find_all("h5", recursive=False):
            if m := re.match("Item at ([0-9]+) must be:", h5.text):
                number = int(m.group(1))

                next_sibling = h5.next_sibling
                while next_sibling and next_sibling.name is None:
                    next_sibling = next_sibling.next_sibling

                name = next_sibling.find("h4").text
                h5.string = f"Parameter {number}: {name}"

    def _api_event_html_process(self, soup: BeautifulSoup):
        pass


def docs_filename(version: str):
    return f"truenas-{version}-docs.zip"


def build_api(output_dir: str, api_and_changelog: tuple[APIDump, Changelog | None]):
    api, changelog = api_and_changelog
    rst_dir = f"{output_dir}/rst/{api.version}"
    DocumentationGenerator(api, rst_dir, changelog).generate()

    with open(f"{rst_dir}/index.rst") as f:
        index = f.read()

    index = index.replace("<download URL>", f"<{docs_filename(api.version)}>")

    with open(f"{rst_dir}/index.rst", "w") as f:
        f.write(index)

    build_dir = f"{output_dir}/html/{api.version}"
    subprocess.run(
        [
            os.path.join(os.path.dirname(sys.executable), "sphinx-build"),
            "-M", "html",
            rst_dir,
            build_dir,
        ],
        check=True,
    )

    shutil.move(f"{build_dir}/html", f"{output_dir}/{api.version}")


def main(output_dir):
    data = json.loads(
        subprocess.run(
            ["middlewared", "--dump-api"],
            check=True,
            env={"FAKE_ENV": "1"},
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )
    apis = [APIDump.model_validate(api_dump) for api_dump in data["versions"]]
    apis_sorted = sorted(apis, key=lambda api: api.version)
    changelogs: dict[str, Changelog | None] = {apis_sorted[0].version: None}
    for previous, current in zip(apis_sorted, apis_sorted[1:]):
        changelogs[current.version] = compute_changelog(previous, current)
    work_items = [(api, changelogs[api.version]) for api in apis]
    with multiprocessing.Pool() as p:
        p.map(functools.partial(build_api, output_dir), work_items)

    shutil.rmtree(f"{output_dir}/rst")
    shutil.rmtree(f"{output_dir}/html")

    for version in os.listdir(output_dir):
        cwd = f"{output_dir}/{version}"

        for root, dirs, files in os.walk(cwd):
            for filename in files:
                if filename.endswith(".html"):
                    with open(f"{root}/{filename}") as f:
                        contents = f.read()

                    # Version switch
                    version_switch = [
                        (
                            f'<option value="{api.version}" {"selected" if api.version == version else ""}>' +
                            f'{api.version_title}' +
                            '</option>'
                        )
                        for api in sorted(apis, key=lambda api: api.version, reverse=True)
                    ]
                    version_switch = (
                        '<form class="form-inline">'
                        '<select class="form-control" onchange="navigateToVersion(this.value);">' +
                        ''.join(version_switch) +
                        '</select>'
                        '</form>'
                    )
                    navbar = '<ul class="navbar-nav mr-auto">'
                    contents = contents.replace(navbar, version_switch + navbar)

                    # Make sphinx show a summary of the search result (sphinxbootstrap4theme breaks this)
                    contents = contents.replace('<div class="bodywrapper">', '<div class="bodywrapper" role="main">')

                    with open(f"{root}/{filename}", "w") as f:
                        f.write(contents)

        with tempfile.NamedTemporaryFile() as tf:
            shutil.make_archive(tf.name, "zip", cwd)
            shutil.move(f"{tf.name}.zip", cwd + "/" + docs_filename(version))


if __name__ == "__main__":
    main(sys.argv[1])
