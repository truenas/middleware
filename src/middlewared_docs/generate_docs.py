# -*- coding=utf-8 -*-
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

from changelog import Changelog, SchemaChange, compute_changelog

logger = logging.getLogger(__name__)


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
            "api_methods",
            changelog.methods_removed,
            removed=True,
        )
        result += self._render_schema_changes_section(
            "Methods with Schema Changes",
            "api_methods",
            changelog.methods_changed,
        )

        with open(f"{self.output_dir}/changelog.rst", "w") as f:
            f.write(result)

    def _render_changelog_section(self, title: str, doc_prefix: str, names: list[str],
                                  removed: bool = False) -> str:
        if not names:
            return ""
        out = f"{title}\n{'-' * len(title)}\n\n"
        for plugin, plugin_names in self._group_by_plugin(names):
            out += f"**{plugin}**\n\n"
            for name in plugin_names:
                if removed:
                    # The method/event no longer exists in this version's build, so link to its
                    # page in the previous version's sibling Sphinx site via a relative URL.
                    changelog = self.changelog
                    assert changelog is not None
                    url = f"../{changelog.previous_version}/{doc_prefix}_{name}.html"
                    out += f"- `{name} <{url}>`__\n"
                else:
                    out += f"- :doc:`{name} <{doc_prefix}_{name}>`\n"
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
    # Load API models
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

    # Compute changelogs between versions
    changelogs: dict[str, Changelog | None] = {apis_sorted[0].version: None}
    for previous, current in zip(apis_sorted, apis_sorted[1:]):
        changelogs[current.version] = compute_changelog(previous, current)

    # Generate docs pages
    work_items = [(api, changelogs[api.version]) for api in apis]
    with multiprocessing.Pool() as p:
        p.map(functools.partial(build_api, output_dir), work_items)

    shutil.rmtree(f"{output_dir}/rst")
    shutil.rmtree(f"{output_dir}/html")

    apis_sorted.reverse()
    for version in os.listdir(output_dir):
        cwd = f"{output_dir}/{version}"
        version_switch = [
            (
                f'<option value="{api.version}" {"selected" if api.version == version else ""}>' +
                f'{api.version_title}' +
                '</option>'
            )
            for api in apis_sorted
        ]
        version_switch = (
            '<form class="form-inline">'
            '<select class="form-control" onchange="navigateToVersion(this.value);">' +
            ''.join(version_switch) +
            '</select>'
            '</form>'
        )

        for root, dirs, files in os.walk(cwd):
            for filename in filter(lambda fname: fname.endswith(".html"), files):
                with open(f"{root}/{filename}") as f:
                    contents = f.read()

                # Version switch
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
