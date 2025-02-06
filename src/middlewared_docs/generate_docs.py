# -*- coding=utf-8 -*-
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import textwrap
import typing

from bs4 import BeautifulSoup
from json_schema_for_humans.generate import generate_from_filename
from json_schema_for_humans.generation_configuration import GenerationConfiguration

from middlewared.api.base.server.doc import APIDump, APIDumpMethod, APIDumpEvent

logger = logging.getLogger(__name__)


class DocumentationGenerator:
    def __init__(self, api: APIDump, output_dir: str):
        self.api = api
        self.output_dir = output_dir

    def generate(self):
        shutil.copytree("docs", self.output_dir, dirs_exist_ok=True)

        with open(f"{self.output_dir}/conf.py") as f:
            conf = f.read()

        conf = conf.replace("$VERSION", self.api.version)

        with open(f"{self.output_dir}/conf.py", "w") as f:
            f.write(conf)

        self._write_api_methods()
        self._write_api_events()

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

        result += f".. raw:: html\n\n"
        result += textwrap.indent(
            f"<div id=\"json-schema\">" + schemas_html + "</div><br><br>", " " * 4
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


def main(output_dir):
    data = json.loads(
        subprocess.run(
            ["middlewared", "--dump-api"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )
    for api_dump in data["versions"]:
        api = APIDump.model_validate(api_dump)

        rst_dir = f"{output_dir}/rst/{api.version}"
        DocumentationGenerator(api, rst_dir).generate()

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

    shutil.rmtree(f"{output_dir}/rst")
    shutil.rmtree(f"{output_dir}/html")

    for root, dirs, files in os.walk(output_dir):
        for filename in files:
            if filename.endswith(".html"):
                with open(f"{root}/{filename}") as f:
                    contents = f.read()

                # Make sphinx show a summary of the search result (sphinxbootstrap4theme breaks this)
                contents = contents.replace('<div class="bodywrapper">', '<div class="bodywrapper" role="main">')

                with open(f"{root}/{filename}", "w") as f:
                    f.write(contents)


if __name__ == "__main__":
    main(sys.argv[1])
